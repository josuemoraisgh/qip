# -*- coding: utf-8 -*-
import os, shutil, tempfile
from datetime import datetime
import numpy as np
import pandas as pd

from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier

# ================== CONFIG ==================
ARQUIVO = r"c:\SourceCode\qip\python\banco_dados.xlsx"

ABA_DADOS            = "TDados"
ABA_PONTOS           = "Pontuação"            # fallback se não houver a tunada
ABA_PONTOS_TUNADA    = "Pontuação_Tunada"     # preferencial para p^(H)
LINHA_INICIO_PONTOS  = 3                      # linhas 3..13 definem as classes
COLUNA_TAM           = 11                     # número de classes clínicas (sem 'Sem Transtorno')
COL_ALVO             = "Alvo"
NORMAL_LABEL         = "Sem Transtorno"
TOPK                 = 3

# Grid da regra "Sem Transtorno"
GRID_T1 = np.linspace(0.18, 0.60, 12)         # p_top1
GRID_T2 = np.linspace(0.02, 0.20, 10)         # margem (top1-top2)
GRID_G  = np.linspace(0.30, 0.75, 10)         # fração γ

# Grid do ensemble α
GRID_ALPHA = np.linspace(0.0, 1.0, 11)        # 0.0,0.1,...,1.0

RANDOM_STATE = 42
EPS = 1e-12
# ============================================

def softmax_rows(mat, axis=1, eps=1e-12):
    x = mat - np.max(mat, axis=axis, keepdims=True)
    e = np.exp(x)
    return e / (np.sum(e, axis=axis, keepdims=True) + eps)

def save_preserving_sheets(target_path, dfs_and_sheets):
    """Preserva todas as abas do arquivo e substitui apenas as listadas."""
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
    return (s.replace("ã","a").replace("á","a").replace("â","a")
             .replace("é","e").replace("ê","e")
             .replace("í","i").replace("î","i")
             .replace("ó","o").replace("ô","o")
             .replace("ú","u").replace("û","u"))

def parse_multilabel(series, class_names, normal_label=NORMAL_LABEL):
    """
    Mapeia Alvo (string) -> lista de rótulos reconhecidos.
    Regras:
      - separadores aceitos: | ; ,
      - 'não/nao' -> normal_label
      - demais rótulos: aceitos se batem EXACT com class_names
    """
    KNOWN = set(class_names) | {normal_label}
    DELIMS = ["|",";",","]
    out = []
    for val in series.astype(str).tolist():
        s = val
        for d in DELIMS:
            s = s.replace(d, "|")
        parts = [p.strip() for p in s.split("|") if p.strip()]
        labs = []
        for raw in parts:
            if normalize_token(raw) == "nao":
                labs.append(normal_label)
            elif raw in KNOWN:
                labs.append(raw)
        out.append(labs)
    return out

def build_Ybin(y_lists, class_to_idx, K):
    """Matriz binária multilabel (n,K) — 1 se classe presente na linha."""
    n = len(y_lists)
    Y = np.zeros((n, K), dtype=int)
    for i, labs in enumerate(y_lists):
        for c in labs:
            if c in class_to_idx:
                Y[i, class_to_idx[c]] = 1
    return Y

def macro_topk(y_lists, proba, class_to_idx, idx_to_class, k=3):
    """Macro top-k: média, por classe com suporte >0, da fração de linhas em que a classe aparece no top-k."""
    order = np.argsort(-proba, axis=1)[:, :k]
    accs = []
    K = proba.shape[1]
    for c in range(K):
        cname = idx_to_class[c]
        mask = np.array([cname in labs for labs in y_lists], dtype=bool)
        sup = int(mask.sum())
        if sup == 0:
            continue
        idxs = np.where(mask)[0]
        hits = sum(c in order[i] for i in idxs)
        accs.append(hits / sup)
    return float(np.mean(accs)) if accs else 0.0

def add_normal_by_rule(P, T1, T2, gamma):
    """Aplica a regra do 'Sem Transtorno' e retorna P' (n,K+1) e a máscara de acionamento."""
    n, K = P.shape
    order = np.argsort(-P, axis=1)
    top1 = P[np.arange(n), order[:,0]]
    top2 = P[np.arange(n), order[:,1]]
    margin = top1 - top2

    hits = (top1 < T1) & (margin < T2)
    P_scaled = P.copy()
    P_scaled[hits] *= (1.0 - gamma)
    p_norm = np.zeros(n, dtype=float)
    p_norm[hits] = gamma

    P_aug = np.concatenate([P_scaled, p_norm[:,None]], axis=1)
    P_aug = P_aug / np.maximum(P_aug.sum(axis=1, keepdims=True), EPS)
    return P_aug, hits

def grid_search_normal(P, y_lists, class_names_aug, k=3):
    """Busca T1, T2, γ maximizando macro top-k (inclui 'Sem Transtorno')."""
    class_to_idx_aug = {c:i for i,c in enumerate(class_names_aug)}
    idx_to_class_aug = {i:c for c,i in class_to_idx_aug.items()}
    best = (-1.0, None, None, None, None)  # (macro, T1, T2, γ, hit_rate)
    for T1 in GRID_T1:
        for T2 in GRID_T2:
            for g in GRID_G:
                P_aug, hits = add_normal_by_rule(P, T1, T2, g)
                macro = macro_topk(y_lists, P_aug, class_to_idx_aug, idx_to_class_aug, k=k)
                if macro > best[0] + 1e-9:
                    best = (macro, T1, T2, g, float(hits.mean()))
    return best

def topk_table(P, class_names, k=3):
    order = np.argsort(-P, axis=1)
    recs = []
    for i in range(P.shape[0]):
        d = {}
        for t in range(min(k, P.shape[1])):
            cls = order[i, t]
            d[f"top{t+1}_classe"] = class_names[cls]
            d[f"top{t+1}_prob"]   = float(P[i, cls])
        recs.append(d)
    return pd.DataFrame(recs)

def main():
    # ---------- leitura ----------
    df_dados = pd.read_excel(ARQUIVO, sheet_name=ABA_DADOS)
    # tenta ler a tunada; se não houver, cai para a original
    try:
        df_pont = pd.read_excel(ARQUIVO, sheet_name=ABA_PONTOS_TUNADA)
        usando_tunada = True
    except Exception:
        df_pont = pd.read_excel(ARQUIVO, sheet_name=ABA_PONTOS)
        usando_tunada = False

    # features
    cols_dados = df_dados.columns[1:]
    if len(cols_dados) == 0:
        raise ValueError("TDados não possui colunas a partir da coluna B.")
    X = df_dados[cols_dados].apply(pd.to_numeric, errors="coerce").fillna(0.0).values
    # saneamento
    neg_cols = []
    for j, c in enumerate(cols_dados):
        mn, mx = float(np.min(X[:,j])), float(np.max(X[:,j]))
        if mn < 0.0 or mx > 1.0:
            neg_cols.append((c, mn, mx))
    if neg_cols:
        print("[ALERTA] Colunas com valores fora de 0..1 (serão clipadas):")
        for c, mn, mx in neg_cols[:10]:
            print(f"  - {c}: min={mn:.6g} max={mx:.6g}")
    X = np.nan_to_num(X, nan=0.0, neginf=0.0, posinf=1.0)
    X = np.clip(X, 0.0, 1.0)
    n, m = X.shape

    # classes (linhas 3..13)
    r0 = LINHA_INICIO_PONTOS - 2
    linhas_modelos = df_pont.index[r0:r0+COLUNA_TAM]
    if len(linhas_modelos) != COLUNA_TAM:
        raise ValueError(f"Aba de pesos não tem {COLUNA_TAM} linhas a partir da {LINHA_INICIO_PONTOS}.")

    if "Tipo de Transtorno" in df_pont.columns:
        class_names = df_pont.loc[linhas_modelos, "Tipo de Transtorno"].astype(str).tolist()
    else:
        class_names = [f"Classe_{i+1}" for i in range(COLUNA_TAM)]
    class_to_idx = {c:i for i,c in enumerate(class_names)}
    idx_to_class = {i:c for c,i in class_to_idx.items()}

    # --- probabilidades da heurística p^(H) para TODAS as linhas ---
    W_block = df_pont.loc[linhas_modelos, cols_dados]
    W = W_block.apply(pd.to_numeric, errors="coerce").fillna(0.0).values.T   # (m,K)
    if W.shape != (m, COLUNA_TAM):
        raise ValueError(f"Dimensão inesperada de W: {W.shape} != ({m},{COLUNA_TAM})")
    P_H = softmax_rows(X @ W)  # (n,K)

    # --- rótulos multilabel a partir do Alvo ---
    if COL_ALVO not in df_dados.columns:
        raise ValueError("Coluna 'Alvo' não encontrada em TDados.")
    y_lists_all = parse_multilabel(df_dados[COL_ALVO], class_names, normal_label=NORMAL_LABEL)

    # máscaras p/ avaliação e treino
    has_any_label = np.array([len(l)>0 for l in y_lists_all], dtype=bool)  # inclui 'Sem Transtorno'
    has_clinical  = np.array([any(lbl in class_names for lbl in labs) for labs in y_lists_all], dtype=bool)

    # --- treino do modelo discriminativo (One-vs-Rest Logística) ---
    Ybin = build_Ybin(y_lists_all, class_to_idx, COLUNA_TAM)   # multilabel binária
    X_tr  = X[has_clinical]
    Y_tr  = Ybin[has_clinical]

    if X_tr.shape[0] == 0:
        raise RuntimeError("Não há linhas com rótulos clínicos para treinar o modelo discriminativo.")

    base_lr = LogisticRegression(
        solver="lbfgs",
        class_weight="balanced",
        max_iter=2000,
        random_state=RANDOM_STATE,
        n_jobs=None
    )
    clf = OneVsRestClassifier(base_lr, n_jobs=None)
    clf.fit(X_tr, Y_tr)

    # Probabilidades por classe (sigmoide por cabeça), normalizadas p/ somar 1
    # predict_proba retorna (n, K) com prob de classe positiva
    P_M_sig = clf.predict_proba(X)  # (n,K)
    row_sums = P_M_sig.sum(axis=1, keepdims=True)
    P_M = P_M_sig / np.maximum(row_sums, EPS)
    # fallback para linhas com tudo zero (caso raro): uniforme
    zero_rows = (row_sums[:,0] < EPS)
    if np.any(zero_rows):
        P_M[zero_rows] = 1.0 / COLUNA_TAM

    # --- regra 'Sem Transtorno' para o MODELO ---
    class_names_aug = class_names + [NORMAL_LABEL]
    macro_M, T1_M, T2_M, G_M, hit_M = grid_search_normal(P_M, y_lists_all, class_names_aug, k=TOPK)
    P_M_aug, _ = add_normal_by_rule(P_M, T1_M, T2_M, G_M)

    # Métrica do MODELO (somente em linhas com algum rótulo reconhecido)
    class_to_idx_aug = {c:i for i,c in enumerate(class_names_aug)}
    idx_to_class_aug = {i:c for c,i in class_to_idx_aug.items()}
    P_M_eval = P_M_aug[has_any_label]
    y_eval   = [l for l,ok in zip(y_lists_all, has_any_label) if ok]
    macro_M_eval = macro_topk(y_eval, P_M_eval, class_to_idx_aug, idx_to_class_aug, k=TOPK)

    # --- ensemble: escolher α e (re)aprender T1,T2,γ no blend ---
    best = (-1.0, None, None, None, None, None)  # (macro, alpha, T1, T2, G, hit_rate)
    for alpha in GRID_ALPHA:
        P_mix = (1.0 - alpha) * P_H + alpha * P_M    # já soma 1 por linha
        macro_E, T1_E, T2_E, G_E, hit_E = grid_search_normal(P_mix, y_lists_all, class_names_aug, k=TOPK)
        if macro_E > best[0] + 1e-9:
            best = (macro_E, alpha, T1_E, T2_E, G_E, hit_E)

    macro_E_best, alpha_best, T1_E, T2_E, G_E, hit_E = best
    P_mix_best = (1.0 - alpha_best) * P_H + alpha_best * P_M
    P_E_aug, _ = add_normal_by_rule(P_mix_best, T1_E, T2_E, G_E)

    # Métrica do ENSEMBLE (em linhas com rótulo reconhecido)
    P_E_eval = P_E_aug[has_any_label]
    macro_E_eval = macro_topk(y_eval, P_E_eval, class_to_idx_aug, idx_to_class_aug, k=TOPK)

    # ---------- montar saídas ----------
    id_col = df_dados.columns[0]
    base_cols = [id_col]
    if COL_ALVO in df_dados.columns:
        base_cols.append(COL_ALVO)
    df_base = df_dados[base_cols].copy()

    # Resultado_Modelo (com Sem Transtorno e topK)
    df_res_M = df_base.copy()
    for j, name in enumerate(class_names):
        df_res_M[f"pM_{name}"] = P_M_aug[:, j]
    df_res_M[f"pM_{NORMAL_LABEL}"] = P_M_aug[:, -1]
    df_res_M = pd.concat([df_res_M, topk_table(P_M_aug, class_names_aug, k=TOPK)], axis=1)

    # Resultado_Ensemble (com Sem Transtorno e topK)
    df_res_E = df_base.copy()
    for j, name in enumerate(class_names):
        df_res_E[f"pE_{name}"] = P_E_aug[:, j]
    df_res_E[f"pE_{NORMAL_LABEL}"] = P_E_aug[:, -1]
    df_res_E = pd.concat([df_res_E, topk_table(P_E_aug, class_names_aug, k=TOPK)], axis=1)

    # Métricas por classe — MODELO
    rows_M = []
    order_M = np.argsort(-P_M_aug, axis=1)[:, :TOPK]
    for c_idx, c_name in enumerate(class_names_aug):
        mask = np.array([c_name in labs for labs in y_lists_all], dtype=bool)
        sup = int(mask.sum())
        if sup == 0:
            rows_M.append({"classe": c_name, "top3_rate": np.nan, "suporte": 0})
            continue
        idxs = np.where(mask)[0]
        hits = sum(c_idx in order_M[i] for i in idxs)
        rows_M.append({"classe": c_name, "top3_rate": hits/sup, "suporte": sup})
    df_met_M = pd.DataFrame(rows_M)
    df_met_Msum = pd.DataFrame([{
        "macro_top3": df_met_M["top3_rate"].mean(skipna=True),
        "observacao": "média das taxas top-3 por classe (inclui 'Sem Transtorno')."
    }])
    df_metricas_M = pd.concat([
        pd.DataFrame([{"secao":"agregado", **df_met_Msum.iloc[0].to_dict()}]),
        df_met_M.assign(secao="por_classe")
    ], ignore_index=True)

    # Métricas por classe — ENSEMBLE
    rows_E = []
    order_E = np.argsort(-P_E_aug, axis=1)[:, :TOPK]
    for c_idx, c_name in enumerate(class_names_aug):
        mask = np.array([c_name in labs for labs in y_lists_all], dtype=bool)
        sup = int(mask.sum())
        if sup == 0:
            rows_E.append({"classe": c_name, "top3_rate": np.nan, "suporte": 0})
            continue
        idxs = np.where(mask)[0]
        hits = sum(c_idx in order_E[i] for i in idxs)
        rows_E.append({"classe": c_name, "top3_rate": hits/sup, "suporte": sup})
    df_met_E = pd.DataFrame(rows_E)
    df_met_Esum = pd.DataFrame([{
        "macro_top3": df_met_E["top3_rate"].mean(skipna=True),
        "observacao": "média das taxas top-3 por classe (inclui 'Sem Transtorno')."
    }])
    df_metricas_E = pd.concat([
        pd.DataFrame([{"secao":"agregado", **df_met_Esum.iloc[0].to_dict()}]),
        df_met_E.assign(secao="por_classe")
    ], ignore_index=True)

    # Params / Regras
    df_params_modelo = pd.DataFrame([
        {"param":"T1_top1_prob_max", "value": T1_M},
        {"param":"T2_margem_top1_top2_max", "value": T2_M},
        {"param":"gamma_fracao_para_SemTranstorno", "value": G_M},
        {"param":"taxa_acionamento_regra", "value": hit_M},
        {"param":"macro_top3_final", "value": macro_M_eval},
    ])
    df_params_ensemble = pd.DataFrame([
        {"param":"alpha_blend", "value": alpha_best},
        {"param":"T1_top1_prob_max", "value": T1_E},
        {"param":"T2_margem_top1_top2_max", "value": T2_E},
        {"param":"gamma_fracao_para_SemTranstorno", "value": G_E},
        {"param":"taxa_acionamento_regra", "value": hit_E},
        {"param":"macro_top3_final", "value": macro_E_eval},
        {"observacao": f"Usando W de {'Pontuação_Tunada' if usando_tunada else 'Pontuação'} para p^(H)."}
    ])

    # ---------- gravar ----------
    saved_path = save_preserving_sheets(
        ARQUIVO,
        [
            (df_res_M,         "Resultado_Modelo"),
            (df_metricas_M,    "Metricas_Modelo"),
            (df_params_modelo, "Regras_Normal_Modelo"),
            (df_res_E,         "Resultado_Ensemble"),
            (df_metricas_E,    "Metricas_Ensemble"),
            (df_params_ensemble,"Ensemble_Params"),
        ]
    )

    print("✅ Abas criadas/atualizadas:",
          "Resultado_Modelo", "Metricas_Modelo", "Regras_Normal_Modelo",
          "Resultado_Ensemble", "Metricas_Ensemble", "Ensemble_Params")
    print(f"💾 Arquivo salvo em: {saved_path}")
    print(f"[INFO] α* = {alpha_best:.2f} | Macro(Modelo)={macro_M_eval:.3%} | Macro(Ensemble)={macro_E_eval:.3%}")

if __name__ == "__main__":
    main()