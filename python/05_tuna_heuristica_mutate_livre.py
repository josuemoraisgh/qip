# -*- coding: utf-8 -*-
"""
03_tuna_heuristica_live_mutate.py — treino contínuo com mutações até tecla específica
- Itera indefinidamente tentando melhorar (grad + mutação de 5 colunas por iteração)
- **Só sai do loop** quando você pressiona uma tecla específica (default: 'q')
- Depois de sair, grava as abas no Excel e encerra
- Regras adicionais do usuário:
  * NUNCA mutar colunas (features) onde TODOS os pesos em W0 são ZERO
  * Em cada iteração mutar EXATAMENTE 5 colunas mutáveis
- Segurança:
  * Clamp estrito: |W−W0| ≤ MAX_DRIFT e W ∈ [EPS_W, 1.0]
  * τ fixo (estável)
  * Grid/refino para (T1, T2, γ) em cada avaliação
  * Logs periódicos
"""

import os, shutil, tempfile, time, sys
from datetime import datetime
import numpy as np
import pandas as pd

# ================== CONFIG ==================
ARQUIVO = r"c:\SourceCode\qip\python\banco_dados.xlsx"
ABA_DADOS = "TDados"
ABA_PONTOS = "Pontuação"
ABA_PONTOS_TUNADA = "Pontuação_Tunada"
ABA_RES_HEUR_TUN = "Resultado_Heuristica_Tunada"
ABA_MET_HEUR_TUN = "Metricas_Heuristica_Tunada"
ABA_EXPLICAO     = "Explicacao_Resultados"
ABA_REGRAS_NORMAL= "Regras_Normal"

COLUNA_TAM = 11
LINHA_INICIO_PONTOS = 3
COL_ALVO = "Alvo"
TOPK = 3

# Otimizador / Regularização
LAMBDA_L1 = 3e-3
LAMBDA_L2 = 5e-2
LR_INIT   = 0.06
LR_FINAL  = 0.02
MAX_DRIFT = 0.05   # delta absoluto máximo por elemento
MAX_STEP  = 0.008  # delta máximo por iteração por elemento
CHECK_EVERY = 10
EPS_W = 1e-6
RANDOM_STATE = 42

# Softmax (τ fixo)
TAU = 1.0

# Grid focado
GRID_T1 = np.linspace(0.55, 0.65, 9)
GRID_T2 = np.linspace(0.16, 0.26, 11)
GRID_G  = np.linspace(0.20, 0.35, 7)

# Overrides (opcionais): se todos definidos, ignora grid
T1_OVERRIDE = None   # 0.60
T2_OVERRIDE = None   # 0.20
G_OVERRIDE  = None   # 0.30

# Refino local leve
REFINE_STEPS = 1
REFINE_SCALE = 0.5

# MUTAÇÃO "5 colunas por vez"
N_MUTATE_COLS  = 5        # exatamente 5 colunas (features) por iteração
MUTATION_STD   = 0.012    # intensidade do ruído
ACCEPT_TOL     = 1e-6     # melhora mínima para aceitar

# Controle do loop infinito por TECLA (Windows)
STOP_KEY = 'q'  # pressione 'q' para salvar e sair
USE_MSVC = os.name == 'nt'
if USE_MSVC:
    import msvcrt

# ================== FUNÇÕES ==================
def softmax_rows_tau(mat, tau=1.0, axis=1, eps=1e-12):
    x = mat / max(tau, 1e-6)
    x = x - np.max(x, axis=axis, keepdims=True)
    e = np.exp(x)
    return e / (np.sum(e, axis=axis, keepdims=True) + eps)

def save_preserving_sheets(target_path, dfs_and_sheets):
    import openpyxl
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

def parse_multilabel(series, class_names, normal_label="Sem Transtorno"):
    KNOWN = set(class_names) | {normal_label}
    DELIMS = ["|",";",","]
    out = []
    for val in series.astype(str).tolist():
        s = val
        for d in DELIMS:
            s = s.replace(d, "|")
        labs_raw = [p.strip() for p in s.split("|") if p.strip()]
        labs = []
        for lab in labs_raw:
            tok = normalize_token(lab)
            if tok == "nao":
                labs.append(normal_label)
            else:
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

def macro_topk(y_lists, proba, class_to_idx, idx_to_class, k=3):
    K = proba.shape[1]
    order = np.argsort(-proba, axis=1)
    topk = order[:, :k]
    accs = []
    for c in range(K):
        c_name = idx_to_class[c]
        mask = np.array([c_name in labs for labs in y_lists], dtype=bool)
        sup = int(mask.sum())
        if sup == 0:
            continue
        idxs = np.where(mask)[0]
        hits = sum(c in topk[i] for i in idxs)
        accs.append(hits / sup)
    return (float(np.mean(accs)) if accs else 0.0)

def add_normal_by_rule(P, T1, T2, gamma):
    n, K = P.shape
    order = np.argsort(-P, axis=1)
    top1 = P[np.arange(n), order[:,0]]
    top2 = P[np.arange(n), order[:,1]]
    margin = top1 - top2

    hits = (top1 < T1) & (margin < T2)
    p_norm = np.zeros(n, dtype=float); p_norm[hits] = gamma

    scale = np.ones(n, dtype=float);   scale[hits] = (1.0 - gamma)
    P_scaled = P * scale[:, None]

    P_aug = np.concatenate([P_scaled, p_norm[:, None]], axis=1)
    P_aug = P_aug / np.maximum(P_aug.sum(axis=1, keepdims=True), 1e-12)
    return P_aug, hits

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

def project_bounds(W, adjustable_mask, W0, eps=1e-6):
    Wp = W.copy()
    Wp[~adjustable_mask, :] = W0[~adjustable_mask, :]
    # primeiro clip valores válidos
    Wp = np.clip(Wp, eps, 1.0)
    # depois trust region ao redor de W0
    low  = W0 - MAX_DRIFT
    high = W0 + MAX_DRIFT
    Wp = np.minimum(np.maximum(Wp, low), high)
    # sanity check estrito
    max_delta = float(np.max(np.abs(Wp - W0)))
    if max_delta > MAX_DRIFT + 1e-10:
        print(f"[WARN] |W-W0| max {max_delta:.6f} > MAX_DRIFT {MAX_DRIFT:.6f} — clamp forçado.")
        Wp = np.minimum(np.maximum(Wp, W0 - MAX_DRIFT), W0 + MAX_DRIFT)
        Wp = np.clip(Wp, eps, 1.0)
    return Wp

def proximal_step(W, grad, W0, lr, l1, l2, adjustable_mask, eps):
    G = grad.copy()
    G[~adjustable_mask, :] = 0.0
    G = np.clip(G, -0.1, 0.1)  # clipping

    # parte suave (CE + L2)
    W_tent = W - lr * (G + 2*l2*(W - W0))

    # proximal L1 em torno de W0
    Delta = W_tent - W0
    thr = lr * l1
    Delta = np.sign(Delta) * np.maximum(np.abs(Delta) - thr, 0.0)

    # limita passo por iteração
    Delta = np.clip(Delta, -MAX_STEP, MAX_STEP)
    W_new = W0 + Delta
    W_new = project_bounds(W_new, adjustable_mask, W0, eps)
    return W_new

def _norm_stats(W, W0):
    D = W - W0
    return {"L2": float(np.linalg.norm(D)),
            "L1": float(np.sum(np.abs(D))),
            "max_abs": float(np.max(np.abs(D)))}

def grid_search_normal(P, y_lists, class_names_aug, topk=3):
    best = (-1.0, None, None, None, None)
    class_to_idx_aug = {c:i for i,c in enumerate(class_names_aug)}
    idx_to_class_aug = {i:c for c,i in class_to_idx_aug.items()}
    for T1 in GRID_T1:
        for T2 in GRID_T2:
            for g in GRID_G:
                P_aug, hits = add_normal_by_rule(P, T1, T2, g)
                macro = macro_topk(y_lists, P_aug, class_to_idx_aug, idx_to_class_aug, k=topk)
                if macro > best[0] + 1e-9:
                    best = (float(macro), float(T1), float(T2), float(g), float(hits.mean()))
    return best

def refine_rule(P, best, bounds, y_lists, class_names_aug, topk=3):
    macro_b, T1_b, T2_b, g_b, _ = best
    (T1_lo, T1_hi), (T2_lo, T2_hi), (g_lo, g_hi) = bounds
    dT1, dT2, dg = 0.03, 0.03, 0.03
    class_to_idx_aug = {c:i for i,c in enumerate(class_names_aug)}
    idx_to_class_aug = {i:c for c,i in class_to_idx_aug.items()}
    cur_best = best
    for _ in range(REFINE_STEPS):
        cand = []
        for d1 in (-dT1, 0.0, dT1):
            for d2 in (-dT2, 0.0, dT2):
                for dg_ in (-dg, 0.0, dg):
                    T1 = float(np.clip(T1_b + d1, T1_lo, T1_hi))
                    T2 = float(np.clip(T2_b + d2, T2_lo, T2_hi))
                    g  = float(np.clip(g_b  + dg_, g_lo, g_hi))
                    P_aug, hits = add_normal_by_rule(P, T1, T2, g)
                    macro = macro_topk(y_lists, P_aug, class_to_idx_aug, idx_to_class_aug, k=topk)
                    cand.append((macro, T1, T2, g, float(hits.mean())))
        cur_best = max(cand, key=lambda t: t[0])
        macro_b, T1_b, T2_b, g_b, _ = cur_best
        dT1 *= REFINE_SCALE; dT2 *= REFINE_SCALE; dg *= REFINE_SCALE
    return cur_best

# ---------- MUTAÇÃO DE 5 COLUNAS ----------
def mutate_five_columns(W_base, W0, mutable_feature_mask, rng, std):
    """Cria uma cópia de W_base onde APENAS 5 features (colunas) recebem ruído ~N(0,std)."""
    Wc = W_base.copy()
    m, K = Wc.shape
    idxs = np.where(mutable_feature_mask)[0]
    if len(idxs) == 0:
        return Wc, np.array([], dtype=int)
    k = min(N_MUTATE_COLS, len(idxs))
    chosen = rng.choice(idxs, size=k, replace=False)
    noise = rng.normal(0.0, std, size=(k, K))
    Wc[chosen, :] += noise
    Wc = project_bounds(Wc, mutable_feature_mask, W0, EPS_W)  # mantém não-mutáveis em W0
    return Wc, chosen

def evaluate_W(Wcand, X, y_lists_all, class_names_aug, topk=TOPK, tau=TAU):
    S = X @ Wcand
    P_tau = softmax_rows_tau(S, tau=tau)
    best = grid_search_normal(P_tau, y_lists_all, class_names_aug, topk=topk)
    bounds = ((0.50, 0.75), (0.12, 0.30), (0.10, 0.45))
    best = refine_rule(P_tau, best, bounds, y_lists_all, class_names_aug, topk=topk)
    macro, T1, T2, G, hit = best
    return float(macro), (T1, T2, G, hit)

# ================== CARREGA DADOS ==================
df_dados = pd.read_excel(ARQUIVO, sheet_name=ABA_DADOS)
df_pont  = pd.read_excel(ARQUIVO, sheet_name=ABA_PONTOS)

cols_dados = df_dados.columns[1:]
if len(cols_dados) == 0:
    raise ValueError("TDados não possui colunas a partir da coluna B.")
X = df_dados[cols_dados].apply(pd.to_numeric, errors="coerce").fillna(0.0).values
n, m = X.shape

r0 = LINHA_INICIO_PONTOS - 2
linhas_modelos = df_pont.index[r0: r0 + COLUNA_TAM]
if len(linhas_modelos) != COLUNA_TAM:
    raise ValueError(f"Aba 'Pontuação' não tem {COLUNA_TAM} linhas a partir da linha {LINHA_INICIO_PONTOS}.")

faltantes = [c for c in cols_dados if c not in df_pont.columns]
if faltantes:
    raise ValueError(f"Colunas de TDados ausentes em 'Pontuação': {faltantes[:10]}{'...' if len(faltantes)>10 else ''}")

W_block = df_pont.loc[linhas_modelos, cols_dados]
W0 = W_block.apply(pd.to_numeric, errors="coerce").fillna(0.0).values.T
if W0.shape != (m, COLUNA_TAM):
    raise ValueError(f"Dimensão inesperada de W: {W0.shape}, esperado ({m}, {COLUNA_TAM}).")
K = W0.shape[1]

if "Tipo de Transtorno" in df_pont.columns:
    class_names = df_pont.loc[linhas_modelos, "Tipo de Transtorno"].astype(str).tolist()
else:
    class_names = [f"Classe_{i+1}" for i in range(COLUNA_TAM)]

X = np.nan_to_num(X, nan=0.0, neginf=0.0, posinf=1.0)
X = np.clip(X, 0.0, 1.0)

NORMAL_LABEL = "Sem Transtorno"
y_lists_all = parse_multilabel(df_dados[COL_ALVO], class_names, normal_label=NORMAL_LABEL)
keep = [len(l)>0 for l in y_lists_all]
X = X[keep]
df_dados = df_dados.loc[keep].reset_index(drop=True)
y_lists_all = [l for l,k in zip(y_lists_all, keep) if k]
n = X.shape[0]

# Máscaras:
adjustable_mask = (X.max(axis=0) > 0)
nonzero_in_W0 = (np.abs(W0).sum(axis=1) > 0)
mutable_feature_mask = adjustable_mask & nonzero_in_W0  # só estas podem receber mutação
print(f"[INFO] Colunas congeladas (X coluna toda = 0): {int((~adjustable_mask).sum())}")
print(f"[INFO] Colunas com todos pesos W0=0 (nunca mutar): {int((~nonzero_in_W0).sum())}")
print(f"[INFO] Colunas mutáveis (p/ grad + mutação): {int(mutable_feature_mask.sum())}")

class_to_idx = {c:i for i,c in enumerate(class_names)}
idx_to_class = {i:c for c,i in class_to_idx.items()}
Ydist = y_distribution(y_lists_all, class_to_idx, K)

# ---------- baseline ----------
S0 = X @ W0
P0 = softmax_rows_tau(S0, tau=TAU)

class_names_aug = class_names + [NORMAL_LABEL]

def eval_with_normal(P):
    if (T1_OVERRIDE is not None) and (T2_OVERRIDE is not None) and (G_OVERRIDE is not None):
        P_aug, hits = add_normal_by_rule(P, float(T1_OVERRIDE), float(T2_OVERRIDE), float(G_OVERRIDE))
        class_to_idx_aug = {c:i for i,c in enumerate(class_names_aug)}
        idx_to_class_aug = {i:c for c,i in class_to_idx_aug.items()}
        macro = macro_topk(y_lists_all, P_aug, class_to_idx_aug, idx_to_class_aug, k=TOPK)
        return macro, float(T1_OVERRIDE), float(T2_OVERRIDE), float(G_OVERRIDE), float(hits.mean())
    best = grid_search_normal(P, y_lists_all, class_names_aug, topk=TOPK)
    bounds = ((0.50, 0.75), (0.12, 0.30), (0.10, 0.45))
    best = refine_rule(P, best, bounds, y_lists_all, class_names_aug, topk=TOPK)
    return best

macro0, T1_0, T2_0, G_0, hit_rate0 = eval_with_normal(P0)
print(f"[INFO] Macro top-{TOPK} baseline (com 'Sem Transtorno' via regra): {macro0:.3%} | T1={T1_0:.3f}, T2={T2_0:.3f}, gamma={G_0:.3f} | regra_acionada={hit_rate0:.1%}")

# ---------- treino contínuo ----------
rng = np.random.default_rng(RANDOM_STATE)
W = project_bounds(W0.copy(), mutable_feature_mask, W0, EPS_W)

best_W = W.copy()
best_macro = macro0
best_T1, best_T2, best_G, best_hit = T1_0, T2_0, G_0, hit_rate0

it = 0
print(f"\n▶ Rodando indefinidamente. Pressione '{STOP_KEY}' para salvar e sair.\n")
last_log_time = time.time()

while True:
    it += 1
    # LR cosine-ish decay cíclico leve (mantém iteração infinita estável)
    phase = (it % 500) / 500.0
    LR = LR_FINAL + (LR_INIT - LR_FINAL) * (1 - 0.5*(1 - np.cos(np.pi*phase)))

    # ===== Prox-grad =====
    S = X @ W
    P = softmax_rows_tau(S, tau=1.0)  # grad com tau=1
    Gs = (P - Ydist) / n
    Gw = X.T @ Gs
    W = proximal_step(W, Gw, W0, LR, LAMBDA_L1, LAMBDA_L2, mutable_feature_mask, EPS_W)

    # ===== Mutar 5 colunas =====
    Wcand, chosen = mutate_five_columns(W, W0, mutable_feature_mask, rng, std=MUTATION_STD)
    macro_c, (t1c, t2c, gc, hitc) = evaluate_W(Wcand, X, y_lists_all, class_names_aug, topk=TOPK, tau=TAU)
    if macro_c > best_macro + ACCEPT_TOL:
        best_macro = macro_c; best_W = Wcand.copy()
        best_T1, best_T2, best_G, best_hit = t1c, t2c, gc, hitc
        W = Wcand  # segue a partir do melhor
        print(f"[MUT @ {it:05d}] ✔ ganho: macro→{best_macro:.3%} | cols_mutadas={chosen.tolist()}")

    # ===== Logging periódico =====
    if (it % CHECK_EVERY == 0) or (time.time() - last_log_time > 60):
        S_eval = X @ W
        P_eval = softmax_rows_tau(S_eval, tau=TAU)
        macro_now, _, _, _, _ = eval_with_normal(P_eval)
        s = _norm_stats(W, W0)
        print(f"[IT {it:05d}] macro_now={macro_now:.3%} best={best_macro:.3%} | T1={best_T1:.3f} T2={best_T2:.3f} γ={best_G:.3f} acion={best_hit:.1%} | Δ L2={s['L2']:.4f} L1={s['L1']:.4f} max|Δ|={s['max_abs']:.4f}")
        last_log_time = time.time()

    # ===== Tecla para sair =====
    if USE_MSVC and msvcrt.kbhit():
        ch = msvcrt.getch()
        try:
            key = ch.decode('utf-8', errors='ignore').lower()
        except Exception:
            key = ''
        if key == STOP_KEY.lower():
            print(f"\n🔴 Tecla '{STOP_KEY}' detectada. Finalizando treino e salvando...")
            break
    else:
        # para ambientes sem msvcrt (não-Windows), não interrompe por tecla
        pass

# ---------- Final: salvar usando o melhor modelo encontrado ----------
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

W_tuned = project_bounds(best_W, mutable_feature_mask, W0, EPS_W)
S_final = X @ W_tuned
P_final_tau = softmax_rows_tau(S_final, tau=TAU)
P_aug, hits_mask = add_normal_by_rule(P_final_tau, best_T1, best_T2, best_G)

class_names_aug = class_names + [NORMAL_LABEL]
class_to_idx_aug = {c:i for i,c in enumerate(class_names_aug)}
idx_to_class_aug = {i:c for c,i in class_to_idx_aug.items()}
macro_final = macro_topk(y_lists_all, P_aug, class_to_idx_aug, idx_to_class_aug, k=TOPK)

print(f"[RESULTADO] Macro top-{TOPK} final (com 'Sem Transtorno'): {macro_final:.3%}  (ganho={macro_final - macro0:+.3%})")
print(f"[REGRAS] T1={best_T1:.3f}  T2={best_T2:.3f}  gamma={best_G:.3f}  acionamento={best_hit:.1%}")

# ---------- saídas ----------
df_pont_tun = pd.DataFrame(W_tuned.T, columns=cols_dados)
df_pont_tun.insert(0, "Tipo de Transtorno", class_names)

df_res = df_dados[[df_dados.columns[0]]].copy()
if COL_ALVO in df_dados.columns:
    df_res[COL_ALVO] = df_dados[COL_ALVO]
for j, name in enumerate(class_names):
    df_res[f"p_{name}"] = P_aug[:, j]
df_res[f"p_{NORMAL_LABEL}"] = P_aug[:, -1]
df_res = pd.concat([df_res, topk_table(P_aug, class_names_aug, k=TOPK)], axis=1)

rows = []
for c_idx, c_name in enumerate(class_names_aug):
    mask = np.array([c_name in labs for labs in y_lists_all], dtype=bool)
    sup = int(mask.sum())
    if sup == 0:
        rows.append({"classe": c_name, "top3_rate": np.nan, "suporte": 0})
        continue
    order = np.argsort(-P_aug[mask], axis=1)[:, :TOPK]
    hits = np.sum([c_idx in order[r] for r in range(order.shape[0])])
    rows.append({"classe": c_name, "top3_rate": hits / sup, "suporte": sup})
df_met_cls = pd.DataFrame(rows)
df_met_sum = pd.DataFrame([{
    "macro_top3": df_met_cls["top3_rate"].mean(skipna=True),
    "observacao": ("macro_top3 = média das taxas por classe (inclui 'Sem Transtorno'); "
                   "conta acerto se qualquer rótulo verdadeiro está no top-3 da linha.")
}])
df_metricas_tun = pd.concat([
    pd.DataFrame([{"secao":"agregado", **df_met_sum.iloc[0].to_dict()}]),
    df_met_cls.assign(secao="por_classe")
], ignore_index=True)

df_regras = pd.DataFrame([
    {"param": "T1_top1_prob_max", "value": float(best_T1)},
    {"param": "T2_margem_top1_top2_max", "value": float(best_T2)},
    {"param": "gamma_fracao_para_SemTranstorno", "value": float(best_G)},
    {"param": "taxa_acionamento_regra", "value": float(best_hit)},
    {"param": "macro_top3_final", "value": float(macro_final)},
    {"param": "tau_softmax", "value": float(TAU)},
    {"param": "mutation_cols_per_iter", "value": int(N_MUTATE_COLS)},
    {"param": "mutation_std", "value": float(MUTATION_STD)},
    {"param": "stop_key", "value": STOP_KEY},
])

saved_path = save_preserving_sheets(
    ARQUIVO,
    [
        (df_pont_tun, ABA_PONTOS_TUNADA),
        (df_res,      ABA_RES_HEUR_TUN),
        (df_metricas_tun, ABA_MET_HEUR_TUN),
        (df_regras,   ABA_REGRAS_NORMAL),
    ]
)

print("✅ Abas criadas/atualizadas:",
      ABA_PONTOS_TUNADA, ABA_RES_HEUR_TUN, ABA_MET_HEUR_TUN, ABA_REGRAS_NORMAL, ABA_EXPLICAO)
print(f"💾 Arquivo salvo em: {saved_path}")
print(f"➡️ Macro top-{TOPK} (com 'Sem Transtorno') final: {macro_final:.3%}")
