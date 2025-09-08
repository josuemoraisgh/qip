# -*- coding: utf-8 -*-
"""
v4_guardW: protege W por feature
--------------------------------
O que foi adicionado em cima do v4:
1) **Freeze de features cujo W0 é zero em TODAS as classes**:
   - `ALLOW_NEW_FEATURES = False`: não ativa colunas novas.
   - `mutable_feature_mask = adjustable_mask & nonzero_in_W0`.
2) **Não "zerar" questões** (não remover feature):
   - Mantém `W >= EPS_W` (já havia).
   - Adiciona **piso por questão**: a soma por linha (feature) não pode
     cair abaixo de `ROW_SUM_FLOOR_FRAC * soma_inicial(W0)`.
     Se cair, reescala a linha para atingir o piso, respeitando os limites
     `[W0 - MAX_DRIFT, W0 + MAX_DRIFT]` e `[EPS_W, 1.0]`.
3) Toda atualização de W (gradiente, push, mutação, repair) passa por
   `project_bounds_guarded(...)`, que aplica **freeze** e **piso de soma**.

Restante da lógica do v4: treino K-only (Macro@Top3) + Etapa 3 (grid T1/T2/γ + tau_cal),
com TDados_clean no treino/validação.
"""

import os, shutil, tempfile, time
import numpy as np
import pandas as pd
from datetime import datetime

# ================== CONFIG ==================
ARQUIVO = r"c:\SourceCode\qip\python\banco_dados.xlsx"
ABA_DADOS = "TDados"
ABA_DADOS_CLEAN = "TDados_clean"
ABA_PONTOS = "Pontuação"

ABA_PONTOS_TUNADA = "Pontuação_Tunada"
ABA_RES_HEUR_TUN  = "Resultado_Heuristica_Tunada"
ABA_MET_HEUR_TUN  = "Metricas_Heuristica_Tunada"
ABA_REGRAS_NORMAL = "Regras_Normal"

ABA_RES_VALID     = "Resultado_Validacao"
ABA_MET_VALID     = "Metricas_Validacao"
ABA_SPLIT_INFO    = "Split_Info"
ABA_RESULTADO_FINAL = "Resultado_Final"

COLUNA_TAM = 11
LINHA_INICIO_PONTOS = 3
COL_ALVO = "Alvo"
TOPK = 3

# Otimizador / Regularização (mantém v4)
LAMBDA_L1 = 0.0
LAMBDA_L2 = 1e-4
LR_INIT   = 0.25
LR_FINAL  = 0.18
MAX_DRIFT = 1.50
DRIFT_CAP = 3.00
MAX_STEP  = 0.15
CHECK_EVERY = 10
EPS_W = 1e-4         # piso por elemento (maior que 1e-6 p/ evitar "sumir")
RANDOM_STATE = 42

# Piso da soma por questão (linha/feature)
ROW_SUM_FLOOR_FRAC = 0.10   # não deixar a soma dos pesos da questão cair abaixo de 10% da soma inicial de W0

# Softmax (base)
TAU_BASE = 1.2
TAU_MIN  = 0.7

# Etapa 3: grade + calibração
GRID_T1 = np.linspace(0.30, 0.98, 28)
GRID_T2 = np.linspace(0.02, 0.60, 25)
GRID_G  = np.linspace(0.05, 0.85, 17)
GRID_TAU_CAL = np.linspace(0.5, 1.8, 14)
DELTA_TIE = 1e-4

# Mutação
N_MUTATE_COLS  = 6
MUTATION_STD   = 0.05
ACCEPT_TOL     = 0.0   # aceita só se melhorar

# Lookahead / EMA
LOOKAHEAD_ALPHA = 0.5
LOOKAHEAD_K     = 5
EMA_BETA        = 0.98
USE_EMA_FOR_TUNED = False

# Dropout
DROP_RATE = 0.00

# BB step
BB_PERIOD = 50
LR_MIN, LR_MAX = 1e-4, 0.6

# Top-3 Hinge Push
USE_TOPK_PUSH   = True
PUSH_ALPHA      = 0.08
PUSH_FRAC       = 0.95

# Repair pass
USE_REPAIR_PASS = True
REPAIR_LOOPS    = 3
REPAIR_ALPHA    = 0.10
REPAIR_MAX_CASES= 800

# Multi-restarts
NUM_RESTARTS    = 3
ITERS_PER_RESTART = 3000

# Parada por tecla (Windows)
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
    x = mat - np.max(mat, axis=axis, keepdims=True)
    e = np.exp(x)
    return e / (np.sum(e, axis=axis, keepdims=True) + eps)

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

def parse_multilabel_known(series, class_names):
    KNOWN = set(class_names)
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
            if tok in ("nao","sem transtorno"):
                labs = []; break
            if lab in KNOWN:
                labs.append(lab)
        out.append(labs)
    return out

def parse_multilabel_all(series, class_names):
    KNOWN = set(class_names)
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
            if tok in ("nao","sem transtorno"):
                labs = []; break
            if lab in KNOWN:
                labs.append(lab)
        out.append(labs)
    return out

def y_distribution(y_lists, class_to_idx, K):
    n = len(y_lists)
    Y = np.zeros((n, K), dtype=float)
    for i, labs in enumerate(y_lists):
        pos = [class_to_idx[c] for c in labs if c in class_to_idx]
        if pos:
            w = 1.0 / len(pos)
            for j in pos:
                Y[i, j] = w
    return Y

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

# ===== GUARD-RAILS DO W =====
def project_bounds_guarded(W, mutable_mask, W0, eps, row_floor_frac):
    """Aplica:
       - Freeze em linhas cujo W0 é todo zero (mutable_mask=False)
       - Limites por elemento: [EPS_W, 1.0]
       - Caixa W0±MAX_DRIFT
       - Piso de soma por linha (>= frac * soma(W0))
    """
    Wp = W.copy()
    # Freeze linhas imutáveis
    Wp[~mutable_mask, :] = W0[~mutable_mask, :]
    # Limites elementares
    Wp = np.clip(Wp, eps, 1.0)
    # Caixa relativa a W0
    low, high = W0 - MAX_DRIFT, W0 + MAX_DRIFT
    Wp = np.minimum(np.maximum(Wp, low), high)
    # Piso de soma por linha
    row_sum0 = W0.sum(axis=1)
    row_floor = row_floor_frac * row_sum0
    # filas onde W0 tem soma zero -> já estão congeladas acima
    need_boost = (row_sum0 > 0) & (Wp.sum(axis=1) < np.maximum(row_floor, eps*Wp.shape[1]))
    if np.any(need_boost):
        idxs = np.where(need_boost)[0]
        for i in idxs:
            s_now = float(Wp[i,:].sum())
            s_min = float(max(row_floor[i], eps*Wp.shape[1]))
            if s_now <= 0:
                # distribui uniformemente, respeitando caixa
                base = max(eps, s_min / Wp.shape[1])
                Wp[i,:] = base
            else:
                factor = s_min / s_now
                Wp[i,:] = Wp[i,:] * factor
            # reaplica limites
            Wp[i,:] = np.clip(Wp[i,:], eps, 1.0)
            lo, hi = low[i,:], high[i,:]
            Wp[i,:] = np.minimum(np.maximum(Wp[i,:], lo), hi)
    return Wp

def proximal_step(W, grad, W0, lr, l1, l2, mutable_mask, eps, row_floor_frac):
    G = grad.copy()
    G[~mutable_mask, :] = 0.0
    # Sem L1 (já está 0), mantém L2 leve
    W_tent = W - lr * (G + 2*l2*(W - W0))
    Delta = W_tent - W0
    Delta = np.clip(Delta, -MAX_STEP, MAX_STEP)
    W_new = project_bounds_guarded(W0 + Delta, mutable_mask, W0, eps, row_floor_frac)
    return W_new

def macro_topk_konly(y_lists, proba, class_to_idx, idx_to_class, k=3):
    K = proba.shape[1]
    order = np.argsort(-proba, axis=1)
    topk = order[:, :k]
    accs = []
    for c in range(K):
        c_name = idx_to_class[c]
        mask = np.array([c_name in labs for labs in y_lists], dtype=bool)
        sup = int(mask.sum())
        if sup == 0: continue
        idxs = np.where(mask)[0]
        hits = sum(c in topk[i] for i in idxs)
        accs.append(hits / sup)
    return (float(np.mean(accs)) if accs else 0.0)

def add_normal_by_rule(P, T1, T2, gamma):
    n, K = P.shape
    order = np.argsort(-P, axis=1)
    top1_idx = order[:, 0]
    top2_idx = order[:, 1]
    top1 = P[np.arange(n), top1_idx]
    top2 = P[np.arange(n), top2_idx]
    margin = top1 - top2
    hits = (top1 < T1) & (margin < T2)
    p_norm = np.zeros(n, dtype=float); p_norm[hits] = gamma
    scale = np.ones(n, dtype=float);   scale[hits] = (1.0 - gamma)
    P_scaled = P * scale[:, None]
    P_aug = np.concatenate([P_scaled, p_norm[:, None]], axis=1)
    P_aug = P_aug / np.maximum(P_aug.sum(axis=1, keepdims=True), 1e-12)
    return P_aug, hits

def grid_search_normal_with_tau(P, y_lists_aug, class_names_aug, topk=3):
    best = (-1.0, None, None, None, None, None)  # (macro, T1, T2, g, hit, tau_cal)
    for tau_cal in GRID_TAU_CAL:
        P_cal = softmax_rows_tau(np.log(np.maximum(P, 1e-12)), tau=tau_cal)
        for T1 in GRID_T1:
            for T2 in GRID_T2:
                for g in GRID_G:
                    P_aug, hits = add_normal_by_rule(P_cal, T1, T2, g)
                    Kp1 = P_aug.shape[1]
                    order = np.argsort(-P_aug, axis=1)[:, :topk]
                    accs = []
                    for c in range(Kp1):
                        c_name = class_names_aug[c]
                        mask = np.array([c_name in labs for labs in y_lists_aug], dtype=bool)
                        sup = int(mask.sum())
                        if sup == 0: continue
                        idxs = np.where(mask)[0]
                        hits_c = sum(c in order[i] for i in idxs)
                        accs.append(hits_c / sup)
                    macro = float(np.mean(accs)) if accs else 0.0
                    hit_rate = float(hits.mean())
                    if (macro > best[0] + 1e-9) or (abs(macro - best[0]) <= DELTA_TIE and hit_rate > (best[4] or 0.0)):
                        best = (macro, float(T1), float(T2), float(g), hit_rate, float(tau_cal))
    return best

def counts_by_class(y_lists_subset, classes):
    return {c: int(sum(c in labs for labs in y_lists_subset)) for c in classes}

# Push e Repair usam sempre a projeção "guarded"
def top3_hinge_push_guarded(W, X, y_lists, class_to_idx, mutable_mask, W0, eps, row_floor_frac,
                            k=3, alpha=0.05, frac=0.7, rng=None):
    n, d = X.shape
    K = W.shape[1]
    S = X @ W  # logits
    order = np.argsort(-S, axis=1)
    topk = order[:, :k]
    bad = []
    for i in range(n):
        labs = y_lists[i]
        if not labs: 
            continue
        true_idx = [class_to_idx[c] for c in labs if c in class_to_idx]
        if not true_idx:
            continue
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
        x = X[i][:, None]  # d x 1
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

    W_new = W + dW
    W_new = project_bounds_guarded(W_new, mutable_mask, W0, eps, row_floor_frac)
    return W_new, len(pick)

def repair_pass_guarded(W, X, y_lists, class_to_idx, mutable_mask, W0, eps, row_floor_frac,
                        max_cases=500, alpha=0.10):
    n, d = X.shape
    S = X @ W
    order = np.argsort(-S, axis=1)
    topk = order[:, :TOPK]
    diffs = []
    for i, labs in enumerate(y_lists):
        if not labs: 
            continue
        true_idx = [class_to_idx[c] for c in labs if c in class_to_idx]
        if not true_idx: continue
        best_true = max(S[i, j] for j in true_idx)
        worst_topk = min(S[i, j] for j in topk[i])
        ok = any(j in topk[i] for j in true_idx)
        if not ok:
            diffs.append((best_true - worst_topk, i))
    if not diffs:
        return W, 0
    diffs.sort()
    pick = [i for _, i in diffs[:max_cases]]
    dW = np.zeros_like(W)
    for i in pick:
        x = X[i][:, None]
        labs = y_lists[i]
        true_idx = [class_to_idx[c] for c in labs if c in class_to_idx]
        if not true_idx: continue
        j_true = max(true_idx, key=lambda j: S[i, j])
        cand = [c for c in topk[i] if c not in true_idx]
        if not cand:
            continue
        j_imp = cand[-1]
        dW[:, j_true:j_true+1] += alpha * x
        dW[:, j_imp :j_imp +1] -= alpha * x
    W_new = W + dW
    W_new = project_bounds_guarded(W_new, mutable_mask, W0, eps, row_floor_frac)
    return W_new, len(pick)

# ================== CARREGAR DADOS ==================
df_all = pd.read_excel(ARQUIVO, sheet_name=ABA_DADOS)

# Tenta usar TDados_clean
try:
    df_clean = pd.read_excel(ARQUIVO, sheet_name=ABA_DADOS_CLEAN)
    using_clean = True
    print("[INFO] Usando TDados_clean para TREINO/VALIDAÇÃO.")
except Exception:
    df_clean = df_all.copy()
    using_clean = False
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

# Pesos W0
r0 = LINHA_INICIO_PONTOS - 2
linhas_modelos = df_pont.index[r0: r0 + COLUNA_TAM]
if len(linhas_modelos) != COLUNA_TAM:
    raise ValueError(f"Aba 'Pontuação' não tem {COLUNA_TAM} linhas a partir da linha {LINHA_INICIO_PONTOS}.")

faltantes = [c for c in cols_dados if c not in df_pont.columns]
if faltantes:
    raise ValueError(f"Colunas de TDados/clean ausentes em 'Pontuação': {faltantes[:10]}{'...' if len(faltantes)>10 else ''}")

W_block = df_pont.loc[linhas_modelos, cols_dados]
W0 = W_block.apply(pd.to_numeric, errors="coerce").fillna(0.0).values.T
if W0.shape != (d, COLUNA_TAM):
    raise ValueError(f"Dimensão inesperada de W: {W0.shape}, esperado ({d}, {COLUNA_TAM}).")
K = W0.shape[1]

if "Tipo de Transtorno" in df_pont.columns:
    class_names = df_pont.loc[linhas_modelos, "Tipo de Transtorno"].astype(str).tolist()
else:
    class_names = [f"Classe_{i+1}" for i in range(COLUNA_TAM)]

# ------- Conjuntos -------
def parse_known_and_all():
    y_lists_known_clean = parse_multilabel_known(df_clean[COL_ALVO], class_names)
    idx_known_clean = [i for i,l in enumerate(y_lists_known_clean) if len(l) > 0]
    X_known = X_clean[idx_known_clean]
    df_known = df_clean.iloc[idx_known_clean].reset_index(drop=True)
    y_known = [y_lists_known_clean[i] for i in idx_known_clean]

    ids_all = df_all.iloc[:,0].astype(str).tolist()
    ids_clean = set(df_clean.iloc[:,0].astype(str).tolist())
    y_lists_all = parse_multilabel_all(df_all[COL_ALVO], class_names)
    for i, idv in enumerate(ids_all):
        if idv not in ids_clean:
            y_lists_all[i] = []
    return X_known, df_known, y_known, y_lists_all

X_known, df_known, y_known, y_lists_all = parse_known_and_all()

# ------ Split TREINO/VALIDAÇÃO (no CLEAN, apenas rótulos conhecidos) ------
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
    train_quota = {}
    for c in class_names_all:
        m = len(cls_to_idxs[c])
        if m == 0: train_quota[c] = 0
        elif m == 1: train_quota[c] = 0
        else: train_quota[c] = (m // 2) + (1 if (m % 2) == 1 else 0)
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
    return train_idx, val_idx, train_quota

train_idx_rel, val_idx_rel, quota = iterative_half_split_known(y_known, class_names, seed=RANDOM_STATE)

X_tr, X_va = X_known[train_idx_rel], X_known[val_idx_rel]
df_tr = df_known.iloc[train_idx_rel].reset_index(drop=True)
df_va = df_known.iloc[val_idx_rel].reset_index(drop=True)
y_tr = [y_known[i] for i in train_idx_rel]
y_va = [y_known[i] for i in val_idx_rel]

print(f"[SPLIT] (usando {'TDados_clean' if True else 'TDados'}) treino={len(train_idx_rel)}  valid={len(val_idx_rel)}  desconhecidos(all)={len(y_lists_all) - len(y_known)}  total_all={len(df_all)}")

# Máscaras de features
adjustable_mask = (X_tr.max(axis=0) > 0)
nonzero_in_W0   = (W0.sum(axis=1) > 0)             # linha cujo W0 é totalmente zero => imutável
ALLOW_NEW_FEATURES = False                         # <== ATENÇÃO: não ativar colunas novas
mutable_feature_mask = adjustable_mask & nonzero_in_W0

print(f"[INFO] Colunas congeladas (X_tr coluna toda = 0): {int((~adjustable_mask).sum())}")
print(f"[INFO] Colunas com soma(W0)==0 (imutáveis): {int((~nonzero_in_W0).sum())}")
print(f"[INFO] Colunas mutáveis: {int(mutable_feature_mask.sum())} (ALLOW_NEW_FEATURES={ALLOW_NEW_FEATURES})")

# Mapas
class_to_idx = {c:i for i,c in enumerate(class_names)}
idx_to_class = {i:c for c,i in class_to_idx.items()}

# Distribuição alvo (K classes) no treino
def y_distribution(y_lists, class_to_idx, K):
    n = len(y_lists)
    Y = np.zeros((n, K), dtype=float)
    for i, labs in enumerate(y_lists):
        pos = [class_to_idx[c] for c in labs if c in class_to_idx]
        if pos:
            w = 1.0 / len(pos)
            for j in pos:
                Y[i, j] = w
    return Y

Ydist_tr = y_distribution(y_tr, class_to_idx, K)

# Pesos por classe (freq inversa)
freq = np.maximum(1, np.array([sum(c in labs for labs in y_tr) for c in class_names], dtype=int))
w_c = 1.0 / freq
w_c = w_c / w_c.mean()

# ---------- baseline K-only ----------
rng_global = np.random.default_rng(RANDOM_STATE)
W = project_bounds_guarded(W0.copy(), mutable_mask=mutable_feature_mask, W0=W0, eps=EPS_W, row_floor_frac=ROW_SUM_FLOOR_FRAC)

S0 = X_tr @ W0
P0_tr = softmax_rows(S0)
def macro_topk_konly(y_lists, proba, class_to_idx, idx_to_class, k=3):
    K = proba.shape[1]
    order = np.argsort(-proba, axis=1)
    topk = order[:, :k]
    accs = []
    for c in range(K):
        c_name = idx_to_class[c]
        mask = np.array([c_name in labs for labs in y_lists], dtype=bool)
        sup = int(mask.sum())
        if sup == 0: continue
        idxs = np.where(mask)[0]
        hits = sum(c in topk[i] for i in idxs)
        accs.append(hits / sup)
    return (float(np.mean(accs)) if accs else 0.0)

macro0_tr = macro_topk_konly(y_tr, P0_tr, class_to_idx, idx_to_class, k=TOPK)
print(f"[BASE TREINO] Macro@Top{TOPK} (K-only): {macro0_tr:.3%}")

best_W = W.copy()
best_macro = macro0_tr

W_slow = W.copy()
W_ema  = W.copy()

it = 0
stale_checks = 0

print(f"\n▶ Treinando (objetivo = Macro@Top{TOPK} K-only). Pressione '{STOP_KEY}' (Windows) para seguir p/ VAL + ETAPA 3.\n")

W_prev = None
Gw_prev = None

while True:
    it += 1
    # LR cíclico + BB mix
    phase = (it % 500) / 500.0
    LR_cyc = LR_FINAL + (LR_INIT - LR_FINAL) * (1 - 0.5*(1 - np.cos(np.pi*phase)))
    LR = LR_cyc

    # ----- forward -----
    S = X_tr @ W
    tau = TAU_BASE - (TAU_BASE - TAU_MIN) * min(1.0, it/2000)
    P = softmax_rows_tau(S, tau=tau)

    # ----- grad CE ponderado -----
    Gs = (P - Ydist_tr) / max(len(X_tr),1)
    Gs = Gs * w_c[None, :]
    Gw = X_tr.T @ Gs

    # ----- passo proximal (com guardas) -----
    W = proximal_step(W, Gw, W0, LR, LAMBDA_L1, LAMBDA_L2, mutable_feature_mask, EPS_W, ROW_SUM_FLOOR_FRAC)

    # ----- Top-3 Hinge Push (guardado) -----
    if USE_TOPK_PUSH and (it % 2 == 0):
        W_push, used = top3_hinge_push_guarded(W, X_tr, y_tr, class_to_idx,
                                               mutable_mask=mutable_feature_mask, W0=W0,
                                               eps=EPS_W, row_floor_frac=ROW_SUM_FLOOR_FRAC,
                                               k=TOPK, alpha=PUSH_ALPHA, frac=PUSH_FRAC, rng=rng_global)
        if used > 0:
            W = W_push

    # ----- mutação (apenas aceita se melhorar), respeitando mask -----
    g_norm = np.linalg.norm(Gw, axis=1)
    cands = np.where(mutable_feature_mask)[0]
    n_guided = min(4, len(cands))
    top_grad = cands[np.argsort(-g_norm[cands])[:n_guided]]
    remain = np.setdiff1d(cands, top_grad, assume_unique=False)
    n_rand = min(max(0, N_MUTATE_COLS - n_guided), len(remain))
    rand_pick = rng_global.choice(remain, size=n_rand, replace=False) if n_rand>0 else np.array([], dtype=int)
    chosen = np.concatenate([top_grad, rand_pick]) if n_rand>0 else top_grad
    noise = rng_global.normal(0.0, MUTATION_STD, size=(len(chosen), K))
    Wcand = W.copy(); Wcand[chosen, :] += noise
    Wcand = project_bounds_guarded(Wcand, mutable_feature_mask, W0, EPS_W, ROW_SUM_FLOOR_FRAC)

    # ----- avaliar candidato -----
    P_cand = softmax_rows_tau(X_tr @ Wcand, tau=max(tau, TAU_MIN))
    macro_c = macro_topk_konly(y_tr, P_cand, class_to_idx, idx_to_class, k=TOPK)

    # ----- aceitação (apenas se melhorar) -----
    improve = (macro_c > best_macro + ACCEPT_TOL)
    if improve:
        best_macro = macro_c; best_W = Wcand.copy()
        W = Wcand
        W_ema = EMA_BETA*W_ema + (1-EMA_BETA)*W
        stale_checks = 0
    else:
        stale_checks += 1

    # ----- Lookahead -----
    if it % LOOKAHEAD_K == 0:
        W_slow = W_slow + LOOKAHEAD_ALPHA * (W - W_slow)
        W = project_bounds_guarded(W_slow.copy(), mutable_feature_mask, W0, EPS_W, ROW_SUM_FLOOR_FRAC)

    # ----- BB step -----
    if it % BB_PERIOD == 0:
        if (W_prev is not None) and (Gw_prev is not None):
            s = (W - W_prev).ravel()
            y = (Gw - Gw_prev).ravel()
            denom = float(np.dot(y, y) + 1e-12)
            lr_bb = np.clip(float(np.dot(s, y)/denom), LR_MIN, LR_MAX)
            LR = 0.5*LR + 0.5*lr_bb
        W_prev = W.copy(); Gw_prev = Gw.copy()

    # ----- logs -----
    if it % CHECK_EVERY == 0:
        P_eval = softmax_rows_tau(X_tr @ W, tau=max(tau, TAU_MIN))
        macro_now = macro_topk_konly(y_tr, P_eval, class_to_idx, idx_to_class, k=TOPK)
        delta = np.abs(W - W0)
        row_sum = W.sum(axis=1)
        min_row_sum = float(row_sum.min()) if row_sum.size>0 else 0.0
        print(f"[IT {it:05d}] macroK@Top{TOPK}={macro_now:.3%} best={best_macro:.3%} | max|Δ|={float(delta.max()):.4f} minRowSum={min_row_sum:.4f} τ={tau:.2f}")

    # ----- tecla para sair -----
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
W_tuned = project_bounds_guarded(best_W, mutable_feature_mask, W0, EPS_W, ROW_SUM_FLOOR_FRAC)

# ==============================
# -------- 3ª ETAPA -----------
# ==============================
logits_full = X_full @ W_tuned
P_full_K = softmax_rows(logits_full)

class_names_aug_all = class_names + ["Sem Transtorno"]
def y_for_stage3():
    ids_all = df_all.iloc[:,0].astype(str).tolist()
    ids_clean = set(df_clean.iloc[:,0].astype(str).tolist())
    y_all = parse_multilabel_all(df_all[COL_ALVO], class_names)
    for i, idv in enumerate(ids_all):
        if idv not in ids_clean:
            y_all[i] = []
    return y_all

y_lists_all_stage3 = y_for_stage3()

macro_all, T1_b, T2_b, G_b, hit_b, tau_cal = grid_search_normal_with_tau(P_full_K, y_lists_all_stage3, class_names_aug_all, topk=TOPK)
print(f"[ETAPA3] Macro@Top{TOPK} (todos) = {macro_all:.3%} | T1={T1_b:.3f} T2={T2_b:.3f} γ={G_b:.2f} tau_cal={tau_cal:.2f} | acionamento={hit_b:.1%}")

P_cal = softmax_rows_tau(np.log(np.maximum(P_full_K, 1e-12)), tau=tau_cal)
P_final_aug, _ = add_normal_by_rule(P_cal, T1_b, T2_b, G_b)

# --------- Resultado_Final ---------
df_final = pd.DataFrame({COL_ALVO: df_all[COL_ALVO].astype(object)})
for j, name in enumerate(class_names):
    df_final[f"p_{name}"] = P_final_aug[:, j]
df_final["p_Sem Transtorno"] = P_final_aug[:, -1]
df_final = pd.concat([df_final, topk_table(P_final_aug, class_names_aug_all, k=TOPK)], axis=1)

# ---- TREINO/VALIDAÇÃO (usando MESMO tau_cal e T1/T2/γ) ----
def apply_stage3_post(PK):
    Pk_cal = softmax_rows_tau(np.log(np.maximum(PK, 1e-12)), tau=tau_cal)
    Pk_aug, _ = add_normal_by_rule(Pk_cal, T1_b, T2_b, G_b)
    return Pk_aug

P_tr = softmax_rows(X_tr @ W_tuned)
P_va = softmax_rows(X_va @ W_tuned)
P_tr_aug = apply_stage3_post(P_tr)
P_va_aug = apply_stage3_post(P_va)

# ---- Métricas resumidas ----
def metricas_por_classe(P_aug, y_lists, classes_aug, k=TOPK):
    rows = []
    for c_idx, c_name in enumerate(classes_aug):
        mask = np.array([c_name in labs for labs in y_lists], dtype=bool)
        sup = int(mask.sum())
        if sup == 0:
            rows.append({"classe": c_name, "top3_rate": np.nan, "suporte": 0})
            continue
        order = np.argsort(-P_aug[mask], axis=1)[:, :k]
        hits = np.sum([c_idx in order[r] for r in range(order.shape[0])])
        rows.append({"classe": c_name, "top3_rate": hits / sup, "suporte": sup})
    df_cls = pd.DataFrame(rows)
    df_sum = pd.DataFrame([{"macro_top3": df_cls["top3_rate"].mean(skipna=True)}])
    return df_cls, df_sum

df_met_cls_tr, df_met_sum_tr = metricas_por_classe(P_tr_aug, y_tr, class_names_aug_all, k=TOPK)
df_metricas_tr = pd.concat([
    pd.DataFrame([{"secao":"agregado", **df_met_sum_tr.iloc[0].to_dict()}]),
    df_met_cls_tr.assign(secao="por_classe")
], ignore_index=True)

df_met_cls_va, df_met_sum_va = metricas_por_classe(P_va_aug, y_va, class_names_aug_all, k=TOPK)
df_metricas_va = pd.concat([
    pd.DataFrame([{"secao":"agregado", **df_met_sum_va.iloc[0].to_dict()}]),
    df_met_cls_va.assign(secao="por_classe")
], ignore_index=True)

# ---- SPLIT INFO ----
df_split_info = (
    pd.DataFrame({"treino": counts_by_class(y_tr, class_names),
                  "valid": counts_by_class(y_va, class_names)})
      .rename_axis("classe")
      .reset_index()
      .sort_values("classe")
)

# --------- Regras_Normal (parâmetros da etapa 3) ---------
df_regras = pd.DataFrame([
    {"param": "T1_top1_prob_max", "value": T1_b},
    {"param": "T2_margem_top1_top2_max", "value": T2_b},
    {"param": "gamma_fracao_para_SemTranstorno", "value": G_b},
    {"param": "tau_calibracao", "value": tau_cal},
    {"param": "taxa_acionamento_regra_todos", "value": hit_b},
    {"param": "macro_top3_todos_com_Normal", "value": macro_all},
])

# ---------- Tabelas para salvar ----------
df_pont_tun = pd.DataFrame(W_tuned.T, columns=cols_dados)
df_pont_tun.insert(0, "Tipo de Transtorno", class_names)

df_res_tr = df_tr[[COL_ALVO]].copy()
for j, name in enumerate(class_names):
    df_res_tr[f"p_{name}"] = P_tr_aug[:, j]
df_res_tr["p_Sem Transtorno"] = P_tr_aug[:, -1]
df_res_tr = pd.concat([df_res_tr, topk_table(P_tr_aug, class_names_aug_all, k=TOPK)], axis=1)

df_res_va = df_va[[COL_ALVO]].copy()
for j, name in enumerate(class_names):
    df_res_va[f"p_{name}"] = P_va_aug[:, j]
df_res_va["p_Sem Transtorno"] = P_va_aug[:, -1]
df_res_va = pd.concat([df_res_va, topk_table(P_va_aug, class_names_aug_all, k=TOPK)], axis=1)

# -------------- GRAVAR --------------
saved_path = save_preserving_sheets(
    ARQUIVO,
    [
        (df_pont_tun,      ABA_PONTOS_TUNADA),
        (df_res_tr,        ABA_RES_HEUR_TUN),
        (df_metricas_tr,   ABA_MET_HEUR_TUN),
        (df_res_va,        ABA_RES_VALID),
        (df_metricas_va,   ABA_MET_VALID),
        (df_split_info,    ABA_SPLIT_INFO),
        (df_regras,        ABA_REGRAS_NORMAL),
        (df_final,         ABA_RESULTADO_FINAL),
    ]
)

print("✅ Abas criadas/atualizadas:",
      ABA_PONTOS_TUNADA, ABA_RES_HEUR_TUN, ABA_MET_HEUR_TUN, ABA_RES_VALID, ABA_MET_VALID, ABA_SPLIT_INFO, ABA_REGRAS_NORMAL, ABA_RESULTADO_FINAL)
print(f"💾 Arquivo salvo em: {saved_path}")
