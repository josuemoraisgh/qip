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

COLUNA_TAM = 11           # número de classes
LINHA_INICIO_PONTOS = 3   # linhas 3..13
COL_ALVO = "Alvo"
TOPK = 3

# Hiperparâmetros do ajuste
LAMBDA_L1 = 1e-3          # penaliza |W - W0|
LAMBDA_L2 = 1e-2          # penaliza ||W - W0||^2
LR        = 0.1           # passo do gradiente
MAX_ITERS = 800           # iterações máx.
CHECK_EVERY = 10          # checar macro-top3 a cada N passos
TARGET_MACRO_TOP3 = 0.99  # meta
EPS_W = 1e-6              # limite inferior dos pesos PERMITIDOS (evita zero exato)
RANDOM_STATE = 42
# ============================================

def softmax_rows(mat, axis=1, eps=1e-12):
    x = mat - np.max(mat, axis=axis, keepdims=True)
    e = np.exp(x)
    return e / (np.sum(e, axis=axis, keepdims=True) + eps)

def save_preserving_sheets(target_path, dfs_and_sheets):
    """Preserva todas as abas e substitui apenas as listadas."""
    import openpyxl  # garantimos dependência
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

def parse_multilabel(series, class_names):
    KNOWN = set(class_names)
    DELIMS = ["|",";",","]
    out = []
    for val in series.astype(str).tolist():
        s = val
        for d in DELIMS:
            s = s.replace(d, "|")
        labs = [p.strip() for p in s.split("|") if p.strip()]
        out.append([l for l in labs if l in KNOWN])
    return out

def y_distribution(y_lists, class_to_idx, K):
    """Distribuição-alvo por linha (soma=1 entre rótulos positivos)."""
    n = len(y_lists)
    Y = np.zeros((n, K), dtype=float)
    for i, labs in enumerate(y_lists):
        if labs:
            w = 1.0 / len(labs)
            for lab in labs:
                Y[i, class_to_idx[lab]] = w
    return Y

def macro_topk(y_lists, proba, class_to_idx, idx_to_class, k=3):
    """Taxa macro: média, por classe, da fração de linhas onde a classe (se presente) aparece no top-k."""
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

def topk_table(proba, class_names, k=3):
    """Gera colunas top1/top2/top3."""
    n, K = proba.shape
    order = np.argsort(-proba, axis=1)
    tops = []
    for i in range(n):
        rec = {}
        for t in range(min(k, K)):
            c = order[i, t]
            rec[f"top{t+1}_classe"] = class_names[c]
            rec[f"top{t+1}_prob"] = float(proba[i, c])
        tops.append(rec)
    return pd.DataFrame(tops)

def project_bounds(W, allow_mask, eps=1e-6):
    """
    Projeta para limites:
      - features PROIBIDAS (allow_mask==False) -> exatamente 0
      - features PERMITIDAS (allow_mask==True) -> [eps, 1]
    """
    Wp = W.copy()
    Wp[~allow_mask, :] = 0.0
    Wp[allow_mask, :] = np.clip(Wp[allow_mask, :], eps, 1.0)
    return Wp

def proximal_step(W, grad, W0, lr, l1, l2, allow_mask, eps):
    """
    Passo proximal (Elastic Net em torno de W0) + projeção de limites.
    Only features with allow_mask=True are allowed to move away from 0.
    """
    # gradiente da parte suave (CE + L2)
    W_tent = W - lr * (grad + 2*l2*(W - W0))
    # proximal L1 em torno de W0 (soft-threshold no delta)
    Delta = W_tent - W0
    thr = lr * l1
    Delta = np.sign(Delta) * np.maximum(np.abs(Delta) - thr, 0.0)
    W_new = W0 + Delta
    # projeção nos limites
    W_new = project_bounds(W_new, allow_mask, eps)
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

# alvo multilabel
if COL_ALVO not in df_dados.columns:
    raise ValueError(f"A coluna de alvo '{COL_ALVO}' não foi encontrada em TDados.")
def _parse(series):
    KNOWN = set(class_names); DELIMS = ["|",";",","]
    out=[]
    for v in series.astype(str).tolist():
        s=v
        for d in DELIMS: s=s.replace(d,"|")
        labs=[p.strip() for p in s.split("|") if p.strip()]
        out.append([l for l in labs if l in KNOWN])
    return out
y_lists = _parse(df_dados[COL_ALVO])
keep = [len(l)>0 for l in y_lists]
X = X[keep]; df_dados = df_dados.loc[keep].reset_index(drop=True); y_lists = [l for l,k in zip(y_lists, keep) if k]
n = X.shape[0]

# ==== NOVO: máscara de features permitidas ====
# (a) coluna de TDados tem algum valor > 0
has_value_in_X = (X.max(axis=0) > 0)
# (b) na Pontuação original W0, existe ao menos um peso != 0 em alguma classe
has_nonzero_weight = np.any(W0 != 0.0, axis=1)  # shape (m,)
# Só pode ajustar onde (a) e (b) forem verdadeiros
allow_mask = has_value_in_X & has_nonzero_weight

num_frozen = int((~allow_mask).sum())
num_free   = int(allow_mask.sum())
print(f"[INFO] Features congeladas (tudo zero em TDados ou na Pontuação original): {num_frozen}")
print(f"[INFO] Features ajustáveis: {num_free}")

# Mapas
class_to_idx = {c:i for i,c in enumerate(class_names)}
idx_to_class = {i:c for c,i in class_to_idx.items()}

# ---------- baseline (antes de ajustar) ----------
S0 = X @ W0
P0 = softmax_rows(S0)
macro0 = macro_topk(y_lists, P0, class_to_idx, idx_to_class, k=TOPK)
print(f"[INFO] Macro top-{TOPK} baseline (heurística original): {macro0:.3%}")

# ---------- alvo "distribuição" p/ perda de entropia cruzada ----------
def y_distribution(y_lists, class_to_idx, K):
    n = len(y_lists)
    Y = np.zeros((n, K), dtype=float)
    for i, labs in enumerate(y_lists):
        if labs:
            w = 1.0 / len(labs)
            for lab in labs:
                Y[i, class_to_idx[lab]] = w
    return Y
Ydist = y_distribution(y_lists, class_to_idx, K)  # (n, K)

# ---------- otimização (prox-grad + projeção) ----------
rng = np.random.default_rng(RANDOM_STATE)

# ponto inicial: respeitando máscara (proibidas = 0; permitidas clipadas para [EPS_W,1])
W = project_bounds(W0, allow_mask, EPS_W)

best_W = W.copy()
best_macro = macro0
no_improve = 0

for it in range(1, MAX_ITERS+1):
    S = X @ W
    P = softmax_rows(S)                  # (n, K)

    # gradiente da cross-entropy (para distribuição alvo Ydist)
    Gs = (P - Ydist) / n
    Gw = X.T @ Gs

    # zera gradiente nas features congeladas (garantia extra)
    Gw[~allow_mask, :] = 0.0

    # passo proximal + projeção
    W = proximal_step(W, Gw, W0, LR, LAMBDA_L1, LAMBDA_L2, allow_mask, EPS_W)

    if it % CHECK_EVERY == 0 or it == 1 or it == MAX_ITERS:
        P_chk = softmax_rows(X @ W)
        macro = macro_topk(y_lists, P_chk, class_to_idx, idx_to_class, k=TOPK)
        if macro > best_macro + 1e-6:
            best_macro = macro
            best_W = W.copy()
            no_improve = 0
        else:
            no_improve += 1
        print(f"[IT {it:03d}] macro_top{TOPK}={macro:.3%}  (best={best_macro:.3%})")
        if best_macro >= TARGET_MACRO_TOP3:
            print("[PARAR] Atingiu meta de macro top-3.")
            break
        if no_improve >= 20:
            print("[PARAR] Sem melhora por muito tempo (early stop).")
            break

# congela garantidamente as proibidas em 0 antes de salvar
W_tuned = project_bounds(best_W, allow_mask, EPS_W)
# sanity check: proibidas = 0
assert np.allclose(W_tuned[~allow_mask, :], 0.0), "Há feature proibida não-zero nos pesos finais!"

# ---------- resultados com W_tuned ----------
P_tuned = softmax_rows(X @ W_tuned)
macro1 = macro_topk(y_lists, P_tuned, class_to_idx, idx_to_class, k=TOPK)
print(f"[RESULTADO] Macro top-{TOPK} tunado: {macro1:.3%}  (ganho={macro1 - macro0:+.3%})")

# ---------- preparar saídas ----------
# 1) Pontuação_Tunada (linhas=classes, colunas=features)
df_pont_tun = pd.DataFrame(W_tuned.T, columns=cols_dados)
df_pont_tun.insert(0, "Tipo de Transtorno", class_names)

# 2) Resultado_Heuristica_Tunada
df_res = df_dados[[df_dados.columns[0]]].copy()
if COL_ALVO in df_dados.columns:
    df_res[COL_ALVO] = df_dados[COL_ALVO]
for j, name in enumerate(class_names):
    df_res[f"p_{name}"] = P_tuned[:, j]
df_res = pd.concat([df_res, topk_table(P_tuned, class_names, k=TOPK)], axis=1)

# 3) Metricas_Heuristica_Tunada (macro top-3 por classe + agregado)
rows = []
for c_idx, c_name in enumerate(class_names):
    mask = np.array([c_name in labs for labs in y_lists], dtype=bool)
    sup = int(mask.sum())
    if sup == 0:
        rows.append({"classe": c_name, "top3_rate": np.nan, "suporte": 0})
        continue
    order = np.argsort(-P_tuned[mask], axis=1)[:, :TOPK]
    hits = np.sum([c_idx in order[r] for r in range(order.shape[0])])
    rows.append({"classe": c_name, "top3_rate": hits / sup, "suporte": sup})
df_met_cls = pd.DataFrame(rows)
df_met_sum = pd.DataFrame([{
    "macro_top3": df_met_cls["top3_rate"].mean(skipna=True),
    "observacao": "macro_top3 = média das taxas por classe; conta acerto se qualquer rótulo verdadeiro está no top-3 da linha."
}])
df_metricas_tun = pd.concat([
    pd.DataFrame([{"secao":"agregado", **df_met_sum.iloc[0].to_dict()}]),
    df_met_cls.assign(secao="por_classe")
], ignore_index=True)

# 4) Linha explicativa para Explicacao_Resultados
df_expl_add = pd.DataFrame([{
    "Aba": ABA_PONTOS_TUNADA,
    "Descricao": "Matriz de pesos heurística ajustada SOMENTE em features permitidas: (i) colunas com algum valor >0 em TDados e (ii) colunas com pelo menos um peso !=0 na Pontuação original. Demais colunas permanecem 0."
}])

# -------------- gravar --------------
saved_path = save_preserving_sheets(
    ARQUIVO,
    [
        (df_pont_tun, ABA_PONTOS_TUNADA),
        (df_res,      ABA_RES_HEUR_TUN),
        (df_metricas_tun, ABA_MET_HEUR_TUN),
        (df_expl_add, ABA_EXPLICAO),
    ]
)

print("✅ Abas criadas/atualizadas:",
      ABA_PONTOS_TUNADA, ABA_RES_HEUR_TUN, ABA_MET_HEUR_TUN, ABA_EXPLICAO)
print(f"💾 Arquivo salvo em: {saved_path}")
print(f"➡️ Macro top-{TOPK} antes: {macro0:.3%} | depois: {macro1:.3%}")