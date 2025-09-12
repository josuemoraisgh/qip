# -*- coding: utf-8 -*-
import os, shutil, tempfile
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

COLUNA_TAM = 11           # número de classes do modelo heurístico original
LINHA_INICIO_PONTOS = 3   # linhas 3..13
COL_ALVO = "Alvo"
TOPK = 3

# Penalização p/ ficar perto de W0 (Elastic Net)
LAMBDA_L1 = 1e-3
LAMBDA_L2 = 1e-2
LR        = 0.1
MAX_ITERS = 1000
CHECK_EVERY = 10
TARGET_MACRO_TOP3 = 0.99
EPS_W = 1e-6
RANDOM_STATE = 42

# Grid para aprender a regra do "Sem Transtorno"
GRID_T1 = np.linspace(0.18, 0.60, 12)        # limiar p/ top1_prob
GRID_T2 = np.linspace(0.02, 0.20, 10)        # limiar p/ (top1 - top2)
GRID_G  = np.linspace(0.30, 0.75, 10)        # fração de prob. alocada ao "Sem Transtorno"
# ============================================

def softmax_rows(mat, axis=1, eps=1e-12):
    x = mat - np.max(mat, axis=axis, keepdims=True)
    e = np.exp(x)
    return e / (np.sum(e, axis=axis, keepdims=True) + eps)

def save_preserving_sheets(target_path, dfs_and_sheets):
    """Preserva todas as abas e substitui apenas as listadas."""
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
    # tolera 'nao' sem acento
    return s.replace("ã", "a").replace("á","a").replace("â","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u")

def parse_multilabel(series, class_names, normal_label="Sem Transtorno"):
    """
    Mapeia rótulos do Alvo para classes conhecidas; o texto 'não'/'nao' vira 'Sem Transtorno'.
    Delimitadores aceitos: | ; ,
    """
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
            if tok == "nao":  # 'não' ou 'nao'
                labs.append(normal_label)
            else:
                # mantém o original se for classe conhecida
                if lab in KNOWN:
                    labs.append(lab)
        out.append(labs)
    return out

def y_distribution(y_lists, class_to_idx, K):
    """Distribuição-alvo por linha (soma=1 entre rótulos positivos)."""
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
    """Macro top-k: média, por classe (com suporte > 0), da fração de linhas onde a classe aparece no top-k."""
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
    """
    Dado P (n,K), insere a coluna p_Sem Transtorno (n,1) aplicando a regra:
      - se top1_prob < T1 e (top1_prob - top2_prob) < T2 -> aloca fração 'gamma' ao 'Sem Transtorno'
      - senão, p_normal = 0
    Em seguida reescala as K probabilidades para que SOMA(P_aug[i,:]) == 1.
    Retorna P_aug (n, K+1), hits_mask (regra acionou por linha, bool array).
    """
    n, K = P.shape
    order = np.argsort(-P, axis=1)
    top1_idx = order[:, 0]
    top2_idx = order[:, 1]
    top1 = P[np.arange(n), top1_idx]
    top2 = P[np.arange(n), top2_idx]
    margin = top1 - top2

    hits = (top1 < T1) & (margin < T2)
    p_norm = np.zeros(n, dtype=float)
    p_norm[hits] = gamma

    # reescala: parte (1-gamma) para as K classes quando aciona; mantém P original quando não
    scale = np.ones(n, dtype=float)
    scale[hits] = (1.0 - gamma)
    P_scaled = P * scale[:, None]

    # concatena a coluna do Normal
    P_aug = np.concatenate([P_scaled, p_norm[:, None]], axis=1)
    # renormaliza (por segurança numérica)
    P_aug = P_aug / np.maximum(P_aug.sum(axis=1, keepdims=True), 1e-12)
    return P_aug, hits

def grid_search_normal(P, y_lists_aug, class_names_aug, topk=3):
    """
    Busca T1, T2, gamma para maximizar a macro top-k incluindo a classe 'Sem Transtorno'.
    """
    best = (-1.0, None, None, None, None)  # (macro, T1, T2, gamma, hits_ratio)
    K = P.shape[1]
    class_to_idx_aug = {c:i for i,c in enumerate(class_names_aug)}
    idx_to_class_aug = {i:c for c,i in class_to_idx_aug.items()}

    for T1 in GRID_T1:
        for T2 in GRID_T2:
            for g in GRID_G:
                P_aug, hits = add_normal_by_rule(P, T1, T2, g)
                macro = macro_topk(y_lists_aug, P_aug, class_to_idx_aug, idx_to_class_aug, k=topk)
                if macro > best[0] + 1e-9:
                    best = (macro, T1, T2, g, float(hits.mean()))
    return best  # macro, T1, T2, gamma, hits_ratio

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
    """
    Projeção:
      - colunas NÃO ajustáveis -> exatamente W0 (não mexe, não zera)
      - colunas ajustáveis     -> clip para [eps, 1]
    """
    Wp = W.copy()
    Wp[~adjustable_mask, :] = W0[~adjustable_mask, :]
    if np.any(adjustable_mask):
        Wp[adjustable_mask, :] = np.clip(Wp[adjustable_mask, :], eps, 1.0)
    return Wp

def proximal_step(W, grad, W0, lr, l1, l2, adjustable_mask, eps):
    """
    Passo proximal (Elastic Net em torno de W0) + projeção.
    """
    G = grad.copy()
    G[~adjustable_mask, :] = 0.0  # não move colunas congeladas

    # parte suave (CE + L2)
    W_tent = W - lr * (G + 2*l2*(W - W0))
    # proximal L1 em torno de W0
    Delta = W_tent - W0
    thr = lr * l1
    Delta = np.sign(Delta) * np.maximum(np.abs(Delta) - thr, 0.0)
    W_new = W0 + Delta

    # projeção
    W_new = project_bounds(W_new, adjustable_mask, W0, eps)
    return W_new

# -------------- leitura --------------
df_dados = pd.read_excel(ARQUIVO, sheet_name=ABA_DADOS)
df_pont  = pd.read_excel(ARQUIVO, sheet_name=ABA_PONTOS)

# X (colunas da B em diante)
cols_dados = df_dados.columns[1:]
if len(cols_dados) == 0:
    raise ValueError("TDados não possui colunas a partir da coluna B.")
X = df_dados[cols_dados].apply(pd.to_numeric, errors="coerce").fillna(0.0).values
n, m = X.shape

# Seleção de linhas/classes na Pontuação
r0 = LINHA_INICIO_PONTOS - 2
linhas_modelos = df_pont.index[r0: r0 + COLUNA_TAM]
if len(linhas_modelos) != COLUNA_TAM:
    raise ValueError(f"Aba 'Pontuação' não tem {COLUNA_TAM} linhas a partir da linha {LINHA_INICIO_PONTOS}.")

faltantes = [c for c in cols_dados if c not in df_pont.columns]
if faltantes:
    raise ValueError(f"Colunas de TDados ausentes em 'Pontuação': {faltantes[:10]}{'...' if len(faltantes)>10 else ''}")

# W original (m, K) — linhas=features, colunas=classes
W_block = df_pont.loc[linhas_modelos, cols_dados]
W0 = W_block.apply(pd.to_numeric, errors="coerce").fillna(0.0).values.T
if W0.shape != (m, COLUNA_TAM):
    raise ValueError(f"Dimensão inesperada de W: {W0.shape}, esperado ({m}, {COLUNA_TAM}).")
K = W0.shape[1]

# nomes de classes
if "Tipo de Transtorno" in df_pont.columns:
    class_names = df_pont.loc[linhas_modelos, "Tipo de Transtorno"].astype(str).tolist()
else:
    class_names = [f"Classe_{i+1}" for i in range(COLUNA_TAM)]

# saneamento X
X = np.nan_to_num(X, nan=0.0, neginf=0.0, posinf=1.0)
X = np.clip(X, 0.0, 1.0)

# alvo multilabel + mapeamento para 'Sem Transtorno' (texto 'não')
NORMAL_LABEL = "Sem Transtorno"
y_lists_all = parse_multilabel(df_dados[COL_ALVO], class_names, normal_label=NORMAL_LABEL)
# manter linhas com pelo menos 1 rótulo (classe ou normal)
keep = [len(l)>0 for l in y_lists_all]
X = X[keep]
df_dados = df_dados.loc[keep].reset_index(drop=True)
y_lists_all = [l for l,k in zip(y_lists_all, keep) if k]
n = X.shape[0]

# Máscara: só ajusta colunas com ALGUM valor > 0 em X
adjustable_mask = (X.max(axis=0) > 0)
print(f"[INFO] Colunas congeladas (X coluna toda = 0): {int((~adjustable_mask).sum())}")
print(f"[INFO] Colunas ajustáveis (X tem algum valor >0): {int(adjustable_mask.sum())}")

# Mapas SEM o 'Sem Transtorno' (para treino da heurística via CE)
class_to_idx = {c:i for i,c in enumerate(class_names)}
idx_to_class = {i:c for c,i in class_to_idx.items()}

# Distribuição somente para classes tradicionais (K)
# (linhas cujo y só é 'Sem Transtorno' terão vetor alvo tudo zero aqui)
Ydist = y_distribution(y_lists_all, class_to_idx, K)  # (n, K)

# ---------- baseline (antes de ajustar) ----------
S0 = X @ W0
P0 = softmax_rows(S0)

# métricas incluindo "Sem Transtorno" (via grid best T1/T2/gamma)
class_names_aug = class_names + [NORMAL_LABEL]
class_to_idx_aug = {c:i for i,c in enumerate(class_names_aug)}
idx_to_class_aug = {i:c for c,i in class_to_idx_aug.items()}

def eval_with_normal(P):
    macro_best, T1_b, T2_b, G_b, hit_b = grid_search_normal(P, y_lists_all, class_names_aug, topk=TOPK)
    return macro_best, T1_b, T2_b, G_b, hit_b

macro0, T1_0, T2_0, G_0, hit_rate0 = eval_with_normal(P0)
print(f"[INFO] Macro top-{TOPK} baseline (com 'Sem Transtorno' via regra): {macro0:.3%} | T1={T1_0:.3f}, T2={T2_0:.3f}, gamma={G_0:.2f} | regra_acionada={hit_rate0:.1%}")

# ---------- otimização (prox-grad + projeção), escolhendo o melhor W considerando a regra ----------
rng = np.random.default_rng(RANDOM_STATE)
W = project_bounds(W0.copy(), adjustable_mask, W0, EPS_W)

best_W = W.copy()
best_macro = macro0
best_T1, best_T2, best_G, best_hit = T1_0, T2_0, G_0, hit_rate0
no_improve = 0

for it in range(1, MAX_ITERS+1):
    S = X @ W
    P = softmax_rows(S)                  # (n, K)

    # gradiente da cross-entropy (somente p/ classes tradicionais)
    Gs = (P - Ydist) / n
    Gw = X.T @ Gs

    # passo proximal + projeção (respeitando congelamento)
    W = proximal_step(W, Gw, W0, LR, LAMBDA_L1, LAMBDA_L2, adjustable_mask, EPS_W)

    if it % CHECK_EVERY == 0 or it == 1 or it == MAX_ITERS:
        P_chk = softmax_rows(X @ W)
        macro_chk, T1_c, T2_c, G_c, hit_c = eval_with_normal(P_chk)
        if macro_chk > best_macro + 1e-6:
            best_macro = macro_chk
            best_W = W.copy()
            best_T1, best_T2, best_G, best_hit = T1_c, T2_c, G_c, hit_c
            no_improve = 0
        else:
            no_improve += 1
        print(f"[IT {it:03d}] macro_top{TOPK} (com Normal)={macro_chk:.3%}  best={best_macro:.3%}  | T1={T1_c:.3f} T2={T2_c:.3f} γ={G_c:.2f}  acion={hit_c:.1%}")
        if best_macro >= TARGET_MACRO_TOP3:
            print("[PARAR] Atingiu meta de macro top-3 (com 'Sem Transtorno').")
            break
        if no_improve >= 100:
            print("[PARAR] Sem melhora por muito tempo (early stop).")
            break

# projeção final (garantia)
W_tuned = project_bounds(best_W, adjustable_mask, W0, EPS_W)

# ---------- resultados finais ----------
# probabilidades tradicionais (K) e com 'Sem Transtorno' (K+1)
P_final = softmax_rows(X @ W_tuned)
P_aug, hits_mask = add_normal_by_rule(P_final, best_T1, best_T2, best_G)
macro_final = macro_topk(y_lists_all, P_aug, class_to_idx_aug, idx_to_class_aug, k=TOPK)
print(f"[RESULTADO] Macro top-{TOPK} final (com 'Sem Transtorno'): {macro_final:.3%}  (ganho={macro_final - macro0:+.3%})")
print(f"[REGRAS] T1={best_T1:.3f}  T2={best_T2:.3f}  gamma={best_G:.2f}  acionamento={best_hit:.1%}")

# ---------- preparar saídas ----------
# 1) Pontuação_Tunada (linhas=classes, colunas=features)
df_pont_tun = pd.DataFrame(W_tuned.T, columns=cols_dados)
df_pont_tun.insert(0, "Tipo de Transtorno", class_names)

# 2) Resultado_Heuristica_Tunada  (ID, Alvo, p_<classe>, p_Sem Transtorno, top1..top3 com normal)
df_res = df_dados[[df_dados.columns[0]]].copy()
if COL_ALVO in df_dados.columns:
    df_res[COL_ALVO] = df_dados[COL_ALVO]
# p_<classe>
for j, name in enumerate(class_names):
    df_res[f"p_{name}"] = P_aug[:, j]
# p_Sem Transtorno
df_res[f"p_{NORMAL_LABEL}"] = P_aug[:, -1]
# ranking top1..top3 (com a classe nova)
df_res = pd.concat([df_res, topk_table(P_aug, class_names_aug, k=TOPK)], axis=1)

# 3) Metricas_Heuristica_Tunada (macro top-3 por classe + agregado) — incluindo 'Sem Transtorno'
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

# 4) Regras_Normal (parâmetros aprendidos e estatísticas)
df_regras = pd.DataFrame([{
    "param": "T1_top1_prob_max", "value": best_T1
}, {
    "param": "T2_margem_top1_top2_max", "value": best_T2
}, {
    "param": "gamma_fracao_para_SemTranstorno", "value": best_G
}, {
    "param": "taxa_acionamento_regra", "value": best_hit
}, {
    "param": "macro_top3_final", "value": macro_final
}])

# 5) Linha explicativa para Explicacao_Resultados
df_expl_add = pd.DataFrame([{
    "Aba": ABA_RES_HEUR_TUN,
    "Descricao": ("Probabilidades heurísticas com pesos tunados + classe adicional 'Sem Transtorno' por regra: "
                  "se top1_prob < T1 e (top1-top2) < T2, aloca-se γ à nova classe e reescala as demais. "
                  "T1/T2/γ aprendidos para maximizar macro top-3.")
}])

# -------------- gravar --------------
saved_path = save_preserving_sheets(
    ARQUIVO,
    [
        (df_pont_tun, ABA_PONTOS_TUNADA),
        (df_res,      ABA_RES_HEUR_TUN),
        (df_metricas_tun, ABA_MET_HEUR_TUN),
        (df_regras,   ABA_REGRAS_NORMAL),
        (df_expl_add, ABA_EXPLICAO),
    ]
)

print("✅ Abas criadas/atualizadas:",
      ABA_PONTOS_TUNADA, ABA_RES_HEUR_TUN, ABA_MET_HEUR_TUN, ABA_REGRAS_NORMAL, ABA_EXPLICAO)
print(f"💾 Arquivo salvo em: {saved_path}")
print(f"➡️ Macro top-{TOPK} (com 'Sem Transtorno') final: {macro_final:.3%}")