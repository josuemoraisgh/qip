"""
Treino com 'Sem Transtorno' COMO CLASSE (K+1) — v4 (mask-safe + best-fix)
-------------------------------------------------------------------------
Atende aos requisitos:
1) NÃO alterar linhas (questões) cujo W0 é **todo zero** em todas as classes.
2) NÃO permitir que linhas com algum peso > 0 em W0 fiquem **totalmente zeradas**.
   - Piso de soma por linha e piso de maior elemento por linha (entre entradas mutáveis).
3) Corrigido o "best": passa a acompanhar a MESMA métrica exibida no log (Macro@Top3 K+1).
4) Logs trazem diagnóstico de cobertura de linhas treináveis e um "upper bound" micro para as linhas imutáveis.

Guard-rails adicionais (iguais à v3):
- Mutação/Push com gating por drift.
- Momentum no gradiente e balanceamento por classe.
- Split garante, quando possível, amostras em TREINO e VALIDAÇÃO para todas as classes, incluindo 'Sem Transtorno'.
"""

import os
import numpy as np
import pandas as pd
from datetime import datetime

# ================== CONFIG ==================
ARQUIVO = r"c:\SourceCode\qip\python\banco_dados.xlsx"
ABA_DADOS = "TDados"
ABA_DADOS_CLEAN = "TDados_clean"
ABA_PONTOS = "Pontuação"

ABA_PONTOS_TUNADA = "Pontuação_Tunada"
ABA_PONTOS_TUNADA_KP1 = "Pontuação_Tunada_Kplus1"
ABA_RES_HEUR_TUN  = "Resultado_Heuristica_Tunada"
ABA_MET_HEUR_TUN  = "Metricas_Heuristica_Tunada"

ABA_RES_VALID     = "Resultado_Validacao"
ABA_MET_VALID     = "Metricas_Validacao"
ABA_SPLIT_INFO    = "Split_Info"
ABA_REGRAS_NORMAL = "Regras_Normal"
ABA_RESULTADO_FINAL = "Resultado_Final"

COLUNA_TAM = 11   # K classes originais
LINHA_INICIO_PONTOS = 3
COL_ALVO = "Alvo"
TOPK = 3

# --------- Otimizador / Guardas ---------
LAMBDA_L1 = 0.0
LAMBDA_L2 = 5e-4

LR_INIT   = 0.10
LR_FINAL  = 0.05
MAX_DRIFT = 0.12
MAX_STEP  = 0.025
CHECK_EVERY = 20
EPS_W = 1e-4
RANDOM_STATE = 42

ROW_SUM_FLOOR_FRAC = 0.15    # fração do somatório inicial (mutável) a manter por linha
ROW_SUM_ABS_FLOOR  = 1e-3    # piso absoluto adicional para somatório de linha (mutável)
ROW_MAX_ABS_FLOOR  = 7e-4    # pelo menos um elemento mutável por linha deve >= esse valor

TAU_SOFTMAX = 1.0

# Mutação / Lookahead / Push
N_MUTATE_ROWS  = 3
MUTATION_STD   = 0.025
ACCEPT_TOL     = 0.0

LOOKAHEAD_ALPHA = 0.4
LOOKAHEAD_K     = 8

USE_TOPK_PUSH   = True
PUSH_ALPHA      = 0.04
PUSH_FRAC       = 0.80

# Momentum
USE_MOMENTUM = True
BETA_MOM = 0.8

# Early drift schedule
DRIFT_WARM_ITERS = 4000  # 70% -> 100% do cap ao longo dessas iterações

STOP_KEY = 'q'
USE_MSVC = os.name == 'nt'
if USE_MSVC:
    import msvcrt

# ================== FUNÇÕES ==================
def softmax_rows_tau(mat, tau=1.0, axis=1, eps=1e-12):
    x = mat / max(tau, 1e-6)
    x = x - np.max(x, axis=axis, keepdims=True)
    e = np.exp(x)
    return e / (np.sum(e, axis=axis, keepdims=True) + eps)

def softmax_rows(mat, axis=1, eps=1e-12):
    return softmax_rows_tau(mat, tau=TAU_SOFTMAX, axis=axis, eps=eps)

def save_preserving_sheets(target_path, dfs_and_sheets):
    import openpyxl, tempfile, shutil, os
    tmpdir = tempfile.mkdtemp()
    tmpfile = os.path.join(tmpdir, "tmp.xlsx")
    base_existed = False
    try:
        shutil.copyfile(target_path, tmpfile)
        base_existed = True
    except Exception:
        with pd.ExcelWriter(tmpfile, engine="openpyxl", mode="w") as writer:
            pass
    mode = "a" if base_existed else "w"
    with pd.ExcelWriter(tmpfile, engine="openpyxl", mode=mode, if_sheet_exists="replace") as writer:
        for df, sheet in dfs_and_sheets:
            df.to_excel(writer, sheet_name=sheet, index=False)
    try:
        os.replace(tmpfile, target_path)
        saved = target_path
    except PermissionError:
        carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
        alt_path = target_path.replace(".xlsx", f"_{carimbo}.xlsx")
        shutil.copyfile(tmpfile, alt_path)
        saved = alt_path
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return saved

def normalize_token(s: str) -> str:
    s = (s or "").strip().lower()
    return (s.replace("ã", "a").replace("á","a").replace("â","a")
             .replace("é","e").replace("í","i").replace("ó","o").replace("ú","u"))

def parse_multilabel_keep_ST(series, class_names_aug):
    KNOWN = set(class_names_aug)
    DELIMS = ["|",";",","]
    out = []
    for val in series.astype(object).tolist():
        if pd.isna(val) or str(val).strip() == "":
            out.append([]); continue
        s = str(val)
        for d in DELIMS:
            s = s.replace(d, "|")
        labs_raw = [p.strip() for p in s.split("|") if p.strip()]
        labs = []
        for lab in labs_raw:
            tok = normalize_token(lab)
            if tok in ("nao","não"):
                labs = []; break
            if lab in KNOWN:
                labs.append(lab)
        out.append(labs)
    return out

def parse_multilabel_all_aug(series, class_names_aug):
    KNOWN = set(class_names_aug)
    DELIMS = ["|",";",","]
    out = []
    for val in series.astype(object).tolist():
        if pd.isna(val) or str(val).strip() == "":
            out.append([]); continue
        s = str(val)
        for d in DELIMS:
            s = s.replace(d, "|")
        labs_raw = [p.strip() for p in s.split("|") if p.strip()]
        labs = []
        ok = True
        for lab in labs_raw:
            tok = normalize_token(lab)
            if tok in ("nao","não"):
                ok = False; break
            if lab in KNOWN:
                labs.append(lab)
        out.append(labs if ok else [])
    return out

def y_distribution(y_lists, class_to_idx, Kp1):
    n = len(y_lists)
    Y = np.zeros((n, Kp1), dtype=float)
    for i, labs in enumerate(y_lists):
        pos = [class_to_idx[c] for c in labs if c in class_to_idx]
        if pos:
            w = 1.0 / len(pos)
            for j in pos:
                Y[i, j] = w
    return Y

def macro_topk(y_lists, proba, class_to_idx, idx_to_class, k=3):
    Kp1 = proba.shape[1]
    order = np.argsort(-proba, axis=1)
    topk = order[:, :k]
    accs = []
    for c in range(Kp1):
        c_name = idx_to_class[c]
        mask = np.array([c_name in labs for labs in y_lists], dtype=bool)
        sup = int(mask.sum())
        if sup == 0: continue
        idxs = np.where(mask)[0]
        hits = sum(c in topk[i] for i in idxs)
        accs.append(hits / sup)
    return (float(np.mean(accs)) if accs else 0.0)

def topk_table(P, class_names, k=3):
    n, K = P.shape
    order = np.argsort(-P, axis=1)
    tops = []
    for i in range(n):
        rec = {}
        for t in range(min(k, K)):
            c = order[i, t]
            rec[f"top{t+1}_classe"] = class_names[c]
            rec[f"top{t+1}_prob"] = float(P[i, c])
        tops.append(rec)
    return pd.DataFrame(tops)

def _enforce_row_floors(Wp, entry_mask, W0, eps, row_floor_frac, abs_sum_floor, abs_max_floor, drift_cap):
    """
    Garante:
    - piso de soma por linha (apenas nas entradas mutáveis) >= max(row_floor_frac * sum(W0*mask), abs_sum_floor se havia algo mutável)
    - pelo menos um elemento mutável por linha >= abs_max_floor (se a linha tinha algo mutável em W0)
    Tudo respeitando os limites [W0 - cap, W0 + cap] e [eps, 1.0].
    """
    Kp1 = Wp.shape[1]
    row_sum0_mut = (W0 * entry_mask).sum(axis=1)
    mut_counts = entry_mask.sum(axis=1)

    # Linhas com alguma entrada mutável no W0
    rows_has_mut0 = (row_sum0_mut > 0) & (mut_counts > 0)

    if not np.any(rows_has_mut0):
        return Wp

    # Piso de soma
    row_floor = np.maximum(row_floor_frac * row_sum0_mut, abs_sum_floor * rows_has_mut0.astype(float))

    cur_mut_sum = (Wp * entry_mask).sum(axis=1)
    need_sum = rows_has_mut0 & (cur_mut_sum < row_floor)
    idxs = np.where(need_sum)[0]
    for i in idxs:
        mut_cols = entry_mask[i, :]
        s_now = float(Wp[i, mut_cols].sum())
        s_min = float(row_floor[i])
        if s_now <= 0:
            base = max(eps, s_min / mut_cols.sum())
            Wp[i, mut_cols] = base
        else:
            factor = s_min / s_now
            Wp[i, mut_cols] = Wp[i, mut_cols] * factor
        lo_i = (W0[i, :] - drift_cap); hi_i = (W0[i, :] + drift_cap)
        Wp[i, mut_cols] = np.minimum(np.maximum(Wp[i, mut_cols], lo_i[mut_cols]), hi_i[mut_cols])
        Wp[i, mut_cols] = np.clip(Wp[i, mut_cols], eps, 1.0)

    # Piso de máximo por linha (ao menos um coef grande o suficiente)
    # Se nenhum >= abs_max_floor, força o maior coef. mutável a ser >= abs_max_floor (dentro do cap)
    rows = np.where(rows_has_mut0)[0]
    for i in rows:
        mut_cols = entry_mask[i, :]
        if not np.any(mut_cols):
            continue
        m = float(Wp[i, mut_cols].max())
        if m < abs_max_floor:
            j = np.argmax(Wp[i, :])  # índice do maior (entre todas), vamos buscar um mutável
            # caso o maior não seja mutável, escolha o primeiro mutável
            if not mut_cols[j]:
                j = np.where(mut_cols)[0][0]
            lo_ij = W0[i, j] - drift_cap
            hi_ij = W0[i, j] + drift_cap
            target = np.clip(abs_max_floor, lo_ij, hi_ij)
            Wp[i, j] = max(Wp[i, j], target, eps)
    return Wp

def project_bounds_guarded_entry(W, entry_mask, W0, eps, row_floor_frac, drift_cap=None):
    cap = MAX_DRIFT if drift_cap is None else float(drift_cap)
    Wp = W.copy()
    # Entradas imutáveis ficam idênticas ao W0
    Wp[~entry_mask] = W0[~entry_mask]
    if np.any(entry_mask):
        low = (W0 - cap); high = (W0 + cap)
        Wp[entry_mask] = np.minimum(np.maximum(Wp[entry_mask], low[entry_mask]), high[entry_mask])
        Wp[entry_mask] = np.clip(Wp[entry_mask], eps, 1.0)
        # Enforce pisos por linha
        Wp = _enforce_row_floors(Wp, entry_mask, W0, eps, row_floor_frac, ROW_SUM_ABS_FLOOR, ROW_MAX_ABS_FLOOR, cap)
    return Wp

def proximal_step(W, grad, W0, lr, l1, l2, entry_mask, eps, row_floor_frac, drift_cap=None):
    G = grad.copy()
    G[~entry_mask] = 0.0
    W_tent = W - lr * (G + 2*l2*(W - W0))
    Delta = W_tent - W0
    Delta[~entry_mask] = 0.0
    Delta = np.clip(Delta, -MAX_STEP, MAX_STEP)
    W_new = project_bounds_guarded_entry(W0 + Delta, entry_mask, W0, eps, row_floor_frac, drift_cap=drift_cap)
    return W_new

def top3_hinge_push_guarded_entry(W, X, y_lists, class_to_idx, entry_mask, W0, eps, row_floor_frac,
                                  k=3, alpha=0.05, frac=0.7, rng=None, drift_cap=None):
    n, d = X.shape
    S = X @ W
    order = np.argsort(-S, axis=1)
    topk = order[:, :k]
    bad = []
    for i in range(n):
        labs = y_lists[i]
        if not labs: 
            continue
        true_idx = [class_to_idx[c] for c in labs if c in class_to_idx]
        if not true_idx: continue
        if not any(t in topk[i] for t in true_idx):
            bad.append(i)
    if not bad:
        return W, 0
    if rng is None:
        rng = np.random.default_rng(42)
    m = int(np.ceil(len(bad) * frac))
    pick = rng.choice(bad, size=m, replace=False)

    dW = np.zeros_like(W)
    for i in pick:
        x = X[i][:, None]
        labs = y_lists[i]
        true_idx = [class_to_idx[c] for c in labs if c in class_to_idx]
        if not true_idx: 
            continue
        j_true = max(true_idx, key=lambda j: S[i, j])
        cand = [c for c in topk[i] if c not in true_idx]
        if not cand:
            continue
        j_imp = cand[-1]
        dW[:, j_true:j_true+1] += alpha * x
        dW[:, j_imp :j_imp +1] -= alpha * x

    dW[~entry_mask] = 0.0
    W_new = W + dW
    W_new = project_bounds_guarded_entry(W_new, entry_mask, W0, eps, row_floor_frac, drift_cap=drift_cap)
    return W_new, len(pick)

# ================== CARREGAR DADOS ==================
df_all = pd.read_excel(ARQUIVO, sheet_name=ABA_DADOS)
try:
    df_clean = pd.read_excel(ARQUIVO, sheet_name=ABA_DADOS_CLEAN)
    print("[INFO] Usando TDados_clean para TREINO/VALIDAÇÃO.")
except Exception:
    df_clean = df_all.copy()
    print("[WARN] TDados_clean não encontrada. Usando TDados para TREINO/VALIDAÇÃO.")

df_pont  = pd.read_excel(ARQUIVO, sheet_name=ABA_PONTOS)

# Features
cols_dados_all = df_all.columns[1:]
cols_dados_clean = df_clean.columns[1:]
if not all(cols_dados_all == cols_dados_clean):
    raise ValueError("As colunas de features em TDados e TDados_clean não coincidem.")
cols_dados = cols_dados_all

# Matrizes
X_full = df_all[cols_dados].apply(pd.to_numeric, errors="coerce").fillna(0.0).clip(0,1).values
X_clean = df_clean[cols_dados].apply(pd.to_numeric, errors="coerce").fillna(0.0).clip(0,1).values
n_full, d = X_full.shape

# Pesos W0 (K classes originais)
r0 = LINHA_INICIO_PONTOS - 2
linhas_modelos = df_pont.index[r0: r0 + COLUNA_TAM]
if len(linhas_modelos) != COLUNA_TAM:
    raise ValueError(f"Aba 'Pontuação' não tem {COLUNA_TAM} linhas a partir da linha {LINHA_INICIO_PONTOS}.")

faltantes = [c for c in cols_dados if c not in df_pont.columns]
if faltantes:
    raise ValueError(f"Colunas de TDados/clean ausentes em 'Pontuação': {faltantes[:10]}{'...' if len(faltantes)>10 else ''}")

W_block = df_pont.loc[linhas_modelos, cols_dados]
W0_K = W_block.apply(pd.to_numeric, errors="coerce").fillna(0.0).values.T   # (d x K)
K = W0_K.shape[1]

# Classes
if "Tipo de Transtorno" in df_pont.columns:
    class_names_K = df_pont.loc[linhas_modelos, "Tipo de Transtorno"].astype(str).tolist()
else:
    class_names_K = [f"Classe_{i+1}" for i in range(COLUNA_TAM)]
class_names_aug = class_names_K + ["Sem Transtorno"]
Kp1 = K + 1

# ------- Conjuntos -------
y_lists_known_clean = parse_multilabel_keep_ST(df_clean[COL_ALVO], class_names_aug)
idx_known_clean = [i for i,l in enumerate(y_lists_known_clean) if len(l) > 0]
X_known = X_clean[idx_known_clean]
df_known = df_clean.iloc[idx_known_clean].reset_index(drop=True)
y_known = [y_lists_known_clean[i] for i in idx_known_clean]

# Todos (ETAPA 3)
y_lists_all = parse_multilabel_all_aug(df_all[COL_ALVO], class_names_aug)

# ------ Split TREINO/VALIDAÇÃO ------
def iterative_half_split_known(y_lists, class_names_all, seed=42):
    rng = np.random.default_rng(seed)
    cls_to_idxs = {c: [] for c in class_names_all}
    valid_rows = []
    for i, labs in enumerate(y_lists):
        if labs:
            valid_rows.append(i)
            for c in labs:
                if c in cls_to_idxs:
                    cls_to_idxs[c].append(i)
    # Quota inicial
    train_quota = {}
    for c in class_names_all:
        m = len(cls_to_idxs[c])
        if m == 0: 
            train_quota[c] = 0
        elif m == 1: 
            train_quota[c] = 1
        else: 
            train_quota[c] = (m // 2) + (1 if (m % 2) == 1 else 0)
    assigned = {i: -1 for i in valid_rows}
    remaining_quota = train_quota.copy()
    classes_by_rarity = sorted(class_names_all, key=lambda c: len(cls_to_idxs[c]))
    for _round in range(3):
        for c in classes_by_rarity:
            idxs = [i for i in cls_to_idxs[c] if assigned[i] == -1]
            rng.shuffle(idxs)
            need = remaining_quota[c]
            for i in idxs:
                if assigned[i] != -1: continue
                labs_i = [lab for lab in y_lists[i] if lab in class_names_all]
                needs_here = sum(1 for lab in labs_i if remaining_quota[lab] > 0)
                if needs_here > 0 and need > 0:
                    assigned[i] = 1
                    for lab in labs_i:
                        if remaining_quota[lab] > 0: remaining_quota[lab] -= 1
                    need = remaining_quota[c]
    for i in valid_rows:
        if assigned[i] != -1: continue
        labs_i = [lab for lab in y_lists[i] if lab in class_names_all]
        if any(remaining_quota[lab] > 0 for lab in labs_i):
            assigned[i] = 1
            for lab in labs_i:
                if remaining_quota[lab] > 0: remaining_quota[lab] -= 1
        else:
            assigned[i] = 0
    train_idx = sorted([i for i, a in assigned.items() if a == 1])
    val_idx   = sorted([i for i, a in assigned.items() if a == 0])

    # Pós-fix de equilíbrio
    train_set = set(train_idx)
    val_set   = set(val_idx)
    for c in class_names_all:
        idxs = cls_to_idxs[c]
        m = len(idxs)
        if m < 2:
            continue
        has_train = any(i in train_set for i in idxs)
        has_val   = any(i in val_set   for i in idxs)
        if not has_train:
            cand = [i for i in idxs if i in val_set]
            if cand:
                j = cand[0]
                val_set.remove(j); train_set.add(j)
        elif not has_val:
            cand = [i for i in idxs if i in train_set]
            if cand:
                j = cand[0]
                train_set.remove(j); val_set.add(j)
    train_idx = sorted(train_set)
    val_idx   = sorted(val_set)
    return train_idx, val_idx, {c: len(cls_to_idxs[c]) for c in class_names_all}

train_idx_rel, val_idx_rel, support = iterative_half_split_known(y_known, class_names_aug, seed=RANDOM_STATE)

X_tr, X_va = X_known[train_idx_rel], X_known[val_idx_rel]
df_tr = df_known.iloc[train_idx_rel].reset_index(drop=True)
df_va = df_known.iloc[val_idx_rel].reset_index(drop=True)
y_tr = [y_known[i] for i in train_idx_rel]
y_va = [y_known[i] for i in val_idx_rel]

print(f"[SPLIT] treino={len(train_idx_rel)}  valid={len(val_idx_rel)}  total_all={len(df_all)}")
print("[SUPORTE por classe]")
for c in class_names_aug:
    s_tr = sum(c in labs for labs in y_tr)
    s_va = sum(c in labs for labs in y_va)
    print(f"  - {c:>20s}: treino={s_tr} | valid={s_va} | total={support[c]}")

# ====== Construir W0 AUG (K+1) ======
W0 = np.zeros((d, Kp1), dtype=float)
W0[:, :K] = W0_K

# Máscaras e permissões
feature_used_any_K = (W0_K.sum(axis=1) > 0)     # linha i tem algum peso em alguma classe original
feature_has_signal = (X_tr.max(axis=0) > 0)     # linha i tem sinal no treino
allow_ST_feature   = feature_used_any_K & feature_has_signal

# Inicialização suave para ST somente nas linhas permitidas
W0[:, K] = 0.05 * allow_ST_feature.astype(float)

# ----- Máscara por ENTRADA (K+1) -----
entry_mutable_mask = np.zeros_like(W0, dtype=bool)
entry_mutable_mask[:, :K] = (W0_K > 0) & feature_has_signal[:, None]
entry_mutable_mask[:, K]  = allow_ST_feature

# Linhas que NUNCA devem mudar (W0 == 0 em TODAS as classes, incluindo ST inicial)
row_all_zero_W0 = (W0.sum(axis=1) == 0.0)
# Elas já estão protegidas porque entry_mutable_mask é totalmente False nelas

row_has_any_mut = entry_mutable_mask.any(axis=1)

print(f"[INFO] Entradas mutáveis: {int(entry_mutable_mask.sum())}/{W0.size} "
      f"({entry_mutable_mask.sum()/W0.size:.1%}) | Linhas com algum mutável: {int(row_has_any_mut.sum())}/{len(row_has_any_mut)}")
print(f"[INFO] Linhas com W0 totalmente zero (intocáveis): {int(row_all_zero_W0.sum())}")

# ---------- Diagnóstico Upper-Bound (micro, aproximação) ----------
# Considerando treinamento: linhas sem mutáveis não mudam. Calcula micro@Top3 para essas com W0 e supõe que todas mutáveis
# poderiam ser "consertadas". Isso dá um teto aproximado.
def micro_top3_hits(y_lists, P, class_to_idx, k=3):
    order = np.argsort(-P, axis=1)[:, :k]
    hits = 0; total = 0
    for i, labs in enumerate(y_lists):
        if not labs: 
            continue
        total += 1
        true_idx = [class_to_idx[c] for c in labs if c in class_to_idx]
        if any(t in order[i] for t in true_idx):
            hits += 1
    return hits, total

class_to_idx = {c:i for i,c in enumerate(class_names_aug)}
idx_to_class = {i:c for c,i in class_to_idx.items()}

P0_tr = softmax_rows(X_tr @ W0)
hits_immut, tot_immut = micro_top3_hits([y_tr[i] for i in range(len(y_tr)) if not row_has_any_mut[i]],
                                        P0_tr[~row_has_any_mut], class_to_idx, k=TOPK)
tot_mut = int(row_has_any_mut.sum())
UB_micro = (hits_immut + tot_mut) / max(1, hits_immut + (tot_immut - hits_immut) + tot_mut)
print(f"[UB aprox micro] imutáveis: hits={hits_immut}/{tot_immut} | mutáveis={tot_mut} => upper_bound≈{UB_micro:.3%}")

# ---------- baseline ----------
rng_global = np.random.default_rng(RANDOM_STATE)
W = project_bounds_guarded_entry(W0.copy(), entry_mutable_mask, W0, EPS_W, ROW_SUM_FLOOR_FRAC, drift_cap=MAX_DRIFT*0.7)

macro0_tr = macro_topk(y_tr, P0_tr, class_to_idx, idx_to_class, k=TOPK)
print(f"[BASE TREINO] Macro@Top{TOPK} (K+1, com W0): {macro0_tr:.3%}")

best_W = W.copy()
best_macro = macro0_tr

W_slow = W.copy()
M_mom = np.zeros_like(W)  # momentum

it = 0
drift_hits = 0
stale = 0

print(f"\n▶ Treinando (objetivo = Macro@Top{TOPK} com {Kp1} classes). Pressione '{STOP_KEY}' (Windows) para validar + avaliar todos.\n\")")

while True:
    it += 1
    warm_frac = min(1.0, it / max(1, DRIFT_WARM_ITERS))
    drift_cap_now = MAX_DRIFT * (0.7 + 0.3*warm_frac)

    phase = (it % 400) / 400.0
    LR_cyc = LR_FINAL + (LR_INIT - LR_FINAL) * (1 - 0.5*(1 - np.cos(np.pi*phase)))
    LR_eff = LR_cyc * (0.5 if drift_hits >= 3 else 1.0) * (0.7 if stale >= 1500 else 1.0)

    # forward
    S = X_tr @ W
    P = softmax_rows(S)

    # grad CE com pesos por classe (1/sqrt(suporte))
    support_tr = {c: max(1, sum(c in labs for labs in y_tr)) for c in class_names_aug}
    w_class = {c: (1.0 / (support_tr[c]**0.5)) for c in class_names_aug}
    mean_w = np.mean(list(w_class.values()))
    w_class = {c: w_class[c]/mean_w for c in class_names_aug}
    w_sample = np.array([np.mean([w_class[c] for c in labs]) if labs else 1.0 for labs in y_tr], dtype=float)
    w_sample = w_sample / np.mean(w_sample)

    Gs = (P - y_distribution(y_tr, class_to_idx, Kp1)) * w_sample[:, None]
    Gs /= max(1.0, w_sample.sum())
    Gw = X_tr.T @ Gs

    # momentum + clipping
    Gw_clip = Gw.copy()
    Gw_clip[~entry_mutable_mask] = 0.0
    if USE_MOMENTUM:
        M_mom = BETA_MOM * M_mom + (1.0 - BETA_MOM) * Gw_clip
        Gw_use = M_mom
    else:
        Gw_use = Gw_clip

    if entry_mutable_mask.any():
        gmax = np.quantile(np.abs(Gw_use[entry_mutable_mask]), 0.98)
        if gmax > 0:
            Gw_use[entry_mutable_mask] = np.clip(Gw_use[entry_mutable_mask], -gmax, gmax)

    # passo proximal
    W_new = proximal_step(W, Gw_use, W0, LR_eff, LAMBDA_L1, LAMBDA_L2, entry_mutable_mask, EPS_W, ROW_SUM_FLOOR_FRAC, drift_cap=drift_cap_now)

    # drift monitor
    delta = np.abs(W_new - W0)
    if entry_mutable_mask.any():
        delta_max = float(delta[entry_mutable_mask].max())
        delta_rel = min(1.0, delta_max / max(1e-12, drift_cap_now))
    else:
        delta_max = 0.0
        delta_rel = 0.0
    if delta_rel >= 1.0 - 1e-6:
        drift_hits += 1
    else:
        drift_hits = max(0, drift_hits - 1)

    W = W_new

    # Push top-k (gated)
    if USE_TOPK_PUSH and (it % 2 == 0) and (drift_hits < 3):
        W_push, used = top3_hinge_push_guarded_entry(W, X_tr, y_tr, class_to_idx,
                                                     entry_mask=entry_mutable_mask, W0=W0,
                                                     eps=EPS_W, row_floor_frac=ROW_SUM_FLOOR_FRAC,
                                                     k=TOPK, alpha=PUSH_ALPHA, frac=PUSH_FRAC, rng=rng_global,
                                                     drift_cap=drift_cap_now)
        if used > 0:
            W = W_push

    # Mutação (gated)
    if (it % 3 == 0) and (drift_hits < 2):
        g_norm = np.linalg.norm(Gw_use, axis=1)
        row_cands = np.where(row_has_any_mut)[0]
        if len(row_cands) > 0:
            n_guided = min(2, len(row_cands))
            top_grad_rows = row_cands[np.argsort(-g_norm[row_cands])[:n_guided]]
            remain = np.setdiff1d(row_cands, top_grad_rows, assume_unique=False)
            n_rand = min(max(0, N_MUTATE_ROWS - n_guided), len(remain))
            rand_rows = rng_global.choice(remain, size=n_rand, replace=False) if n_rand>0 else np.array([], dtype=int)
            chosen_rows = np.concatenate([top_grad_rows, rand_rows]) if n_rand>0 else top_grad_rows
            Wcand = W.copy()
            noise = rng_global.normal(0.0, MUTATION_STD, size=(len(chosen_rows), Kp1))
            mask_rows = entry_mutable_mask[chosen_rows, :]
            noise[~mask_rows] = 0.0
            Wcand[chosen_rows, :] += noise
            Wcand = project_bounds_guarded_entry(Wcand, entry_mutable_mask, W0, EPS_W, ROW_SUM_FLOOR_FRAC, drift_cap=drift_cap_now)

            P_cand = softmax_rows(X_tr @ Wcand)
            macro_c = macro_topk(y_tr, P_cand, class_to_idx, idx_to_class, k=TOPK)

            if macro_c > best_macro + ACCEPT_TOL:
                best_macro = macro_c; best_W = Wcand.copy(); W = Wcand; stale = 0
            else:
                stale += 1
    else:
        stale += 1

    # Lookahead
    if it % LOOKAHEAD_K == 0:
        W_slow = W_slow + LOOKAHEAD_ALPHA * (W - W_slow)
        W = project_bounds_guarded_entry(W_slow.copy(), entry_mutable_mask, W0, EPS_W, ROW_SUM_FLOOR_FRAC, drift_cap=drift_cap_now)

    # logs + atualização de "best" (agora com a mesma métrica do objetivo)
    if it % CHECK_EVERY == 0:
        P_eval = softmax_rows(X_tr @ W)
        macro_now = macro_topk(y_tr, P_eval, class_to_idx, idx_to_class, k=TOPK)
        mut_rows = np.where(row_has_any_mut)[0]
        min_row_mut_sum = float((W[mut_rows, :] * entry_mutable_mask[mut_rows, :]).sum(axis=1).min()) if len(mut_rows)>0 else 0.0
        print(f"[IT {it:07d}] macro@Top{TOPK}={macro_now:.3%} best={best_macro:.3%} | Δ_rel={delta_rel:.4f} "
              f"minRowMutSum={min_row_mut_sum:.4f} driftHits={drift_hits} stale={stale} driftCap={drift_cap_now:.3f}")
        if macro_now > best_macro + 1e-12:
            best_macro = macro_now
            best_W = W.copy()
            stale = 0

    # tecla para sair
    if USE_MSVC and msvcrt.kbhit():
        ch = msvcrt.getch()
        try:
            key = ch.decode('utf-8', errors='ignore').lower()
        except Exception:
            key = ''
        if key == STOP_KEY.lower():
            print(f"\n🔴 Tecla '{STOP_KEY}' detectada. Finalizando treino e iniciando VALIDAÇÃO + ETAPA 3...")
            break

# ============== Pós-treino: VAL + ETAPA 3 + SALVAR ==============
W_tuned = project_bounds_guarded_entry(best_W, entry_mutable_mask, W0, EPS_W, ROW_SUM_FLOOR_FRAC)

# ---------- Probabilidades (K+1) ----------
P_tr = softmax_rows(X_tr @ W_tuned)
P_va = softmax_rows(X_va @ W_tuned)
P_full = softmax_rows(X_full @ W_tuned)

# ---- Métricas resumidas ----
def metricas_por_classe(P, y_lists, classes, k=TOPK):
    rows = []
    for c_idx, c_name in enumerate(classes):
        mask = np.array([c_name in labs for labs in y_lists], dtype=bool)
        sup = int(mask.sum())
        if sup == 0:
            rows.append({"classe": c_name, "top3_rate": np.nan, "suporte": 0})
            continue
        order = np.argsort(-P[mask], axis=1)[:, :k]
        hits = np.sum([c_idx in order[r] for r in range(order.shape[0])])
        rows.append({"classe": c_name, "top3_rate": hits / sup, "suporte": sup})
    df_cls = pd.DataFrame(rows)
    df_sum = pd.DataFrame([{"macro_top3": df_cls["top3_rate"].mean(skipna=True)}])
    return df_cls, df_sum

df_met_cls_tr, df_met_sum_tr = metricas_por_classe(P_tr, y_tr, class_names_aug, k=TOPK)
df_metricas_tr = pd.concat([
    pd.DataFrame([{"secao":"agregado", **df_met_sum_tr.iloc[0].to_dict()}]),
    df_met_cls_tr.assign(secao="por_classe")
], ignore_index=True)

df_met_cls_va, df_met_sum_va = metricas_por_classe(P_va, y_va, class_names_aug, k=TOPK)
df_metricas_va = pd.concat([
    pd.DataFrame([{"secao":"agregado", **df_met_sum_va.iloc[0].to_dict()}]),
    df_met_cls_va.assign(secao="por_classe")
], ignore_index=True)

# ---- SPLIT INFO ----
def counts_by_class(y_lists_subset, classes):
    return {c: int(sum(c in labs for labs in y_lists_subset)) for c in classes}

df_split_info = (
    pd.DataFrame({"treino": counts_by_class(y_tr, class_names_aug),
                  "valid": counts_by_class(y_va, class_names_aug)})
      .rename_axis("classe")
      .reset_index()
      .sort_values("classe")
)

# --------- 'Regras_Normal' informativa ---------
df_regras = pd.DataFrame([
    {"param": "modo", "value": "treino_com_SemTranstorno_v4_maskSafe_bestFix"},
    {"param": "observacao", "value": "Linhas W0==0 intocáveis; piso por linha evita zerar; best corrigido."},
])

# ---------- Saídas ----------
df_pont_tun_K = pd.DataFrame(W_tuned[:, :K].T, columns=cols_dados)
df_pont_tun_K.insert(0, "Tipo de Transtorno", class_names_K)

df_pont_tun_Kp1 = pd.DataFrame(W_tuned.T, columns=cols_dados)
df_pont_tun_Kp1.insert(0, "Tipo de Transtorno", class_names_aug)

df_res_tr = df_tr[[COL_ALVO]].copy()
for j, name in enumerate(class_names_aug):
    df_res_tr[f"p_{name}"] = P_tr[:, j]
df_res_tr = pd.concat([df_res_tr, topk_table(P_tr, class_names_aug, k=TOPK)], axis=1)

df_res_va = df_va[[COL_ALVO]].copy()
for j, name in enumerate(class_names_aug):
    df_res_va[f"p_{name}"] = P_va[:, j]
df_res_va = pd.concat([df_res_va, topk_table(P_va, class_names_aug, k=TOPK)], axis=1)

df_final = pd.DataFrame({COL_ALVO: df_all[COL_ALVO].astype(object)})
for j, name in enumerate(class_names_aug):
    df_final[f"p_{name}"] = P_full[:, j]
df_final = pd.concat([df_final, topk_table(P_full, class_names_aug, k=TOPK)], axis=1)

# -------------- GRAVAR --------------
saved_path = save_preserving_sheets(
    ARQUIVO,
    [
        (df_pont_tun_K,     ABA_PONTOS_TUNADA),
        (df_pont_tun_Kp1,   ABA_PONTOS_TUNADA_KP1),
        (df_res_tr,         ABA_RES_HEUR_TUN),
        (df_metricas_tr,    ABA_MET_HEUR_TUN),
        (df_res_va,         ABA_RES_VALID),
        (df_metricas_va,    ABA_MET_VALID),
        (df_split_info,     ABA_SPLIT_INFO),
        (df_regras,         ABA_REGRAS_NORMAL),
        (df_final,          ABA_RESULTADO_FINAL),
    ]
)

print("✅ Abas criadas/atualizadas:",
      ABA_PONTOS_TUNADA, ABA_PONTOS_TUNADA_KP1, ABA_RES_HEUR_TUN, ABA_MET_HEUR_TUN,
      ABA_RES_VALID, ABA_MET_VALID, ABA_SPLIT_INFO, ABA_REGRAS_NORMAL, ABA_RESULTADO_FINAL)
print(f"💾 Arquivo salvo em: {saved_path}")
