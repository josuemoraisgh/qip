# -*- coding: utf-8 -*-
"""
Analise estatística de W (pesos) e contribuição das variáveis
-------------------------------------------------------------
- Lê TDados, Pontuação e (se existir) Pontuação_Tunada do arquivo Excel.
- Reconstrói W0 (heurístico) e W (tunado, se disponível).
- Calcula previsões (softmax) e indicadores de erro (top-k).
- Gera métricas por variável: normas dos pesos, correlação com erro, "contribuição média" (x_j * w_jc),
  correlação com probabilidades por classe, VIF e colinearidade, estabilidade W vs W0.
- Exporta um relatório Excel com múltiplas abas.
Requisitos:
    pip install pandas numpy scipy scikit-learn statsmodels openpyxl
Ajuste os caminhos em CONFIG conforme necessário.
"""
import os
import math
from dataclasses import dataclass
from typing import List, Tuple, Dict

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.feature_selection import mutual_info_classif
from sklearn.preprocessing import MinMaxScaler
from statsmodels.stats.outliers_influence import variance_inflation_factor as _vif

# ================== CONFIG ==================
ARQUIVO = r"c:\SourceCode\qip\python\banco_dados.xlsx"
ABA_DADOS = "TDados"
ABA_PONTOS = "Pontuação"
ABA_PONTOS_TUNADA = "Pontuação_Tunada"   # opcional
COL_ALVO = "Alvo"
TOPK = 3
NORMAL_LABEL = "Sem Transtorno"
SAIDA_XLSX = "analise_W_relatorio.xlsx"
# ============================================

def softmax_rows(mat, axis=1, eps=1e-12):
    x = mat - np.max(mat, axis=axis, keepdims=True)
    e = np.exp(x)
    return e / (np.sum(e, axis=axis, keepdims=True) + eps)

def normalize_token(s: str) -> str:
    s = (s or "").strip().lower()
    return (s.replace("ã","a").replace("á","a").replace("â","a")
             .replace("é","e").replace("ê","e")
             .replace("í","i").replace("ó","o").replace("ô","o")
             .replace("ú","u"))

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

def topk_hits(y_lists, proba, class_to_idx, k=3):
    """Retorna vetor binário: 1 se qualquer rótulo verdadeiro aparece no top-k das K classes tradicionais"""
    order = np.argsort(-proba, axis=1)[:, :k]
    hits = []
    for i, labs in enumerate(y_lists):
        true_idx = [class_to_idx[c] for c in labs if c in class_to_idx]
        if not true_idx:
            hits.append(0)  # sem rótulo entre as K tradicionais, considere como erro aqui
            continue
        ok = any(t in order[i] for t in true_idx)
        hits.append(1 if ok else 0)
    return np.array(hits, dtype=int)

def mutual_info_per_feature(X, y_bin):
    """MI(x_j, y) com discretização automática via sklearn; retorna array shape (m,)"""
    # Escala para [0,1] (robustez dos estimadores de MI)
    scaler = MinMaxScaler()
    Xs = scaler.fit_transform(X)
    try:
        mi = mutual_info_classif(Xs, y_bin, discrete_features=False, random_state=0)
    except Exception:
        # fallback: zeros
        mi = np.zeros(X.shape[1], dtype=float)
    return mi

def safe_pearson(x, y):
    try:
        r, p = stats.pearsonr(x, y)
    except Exception:
        r, p = np.nan, np.nan
    return r, p

def safe_spearman(x, y):
    try:
        r, p = stats.spearmanr(x, y, nan_policy="omit")
    except Exception:
        r, p = np.nan, np.nan
    return r, p

def compute_vif(X, cols):
    """Calcula VIF para cada coluna contínua; retorna DataFrame."""
    # Remoção de colunas constantes
    keep = [j for j in range(X.shape[1]) if np.nanstd(X[:, j]) > 0]
    if not keep:
        return pd.DataFrame(columns=["feature","vif"])
    Xk = X[:, keep]
    features = [cols[j] for j in keep]
    # Remove colinearidade exata
    # statsmodels VIF pode falhar com colinearidade forte; tenta tratar NaN
    Xk = np.nan_to_num(Xk, nan=0.0, posinf=0.0, neginf=0.0)
    vifs = []
    for j in range(Xk.shape[1]):
        try:
            v = _vif(Xk, j)
        except Exception:
            v = np.inf
        vifs.append(v)
    return pd.DataFrame({"feature": features, "vif": vifs}).sort_values("vif", ascending=False).reset_index(drop=True)

def main():
    # --------- leitura básica ---------
    df_dados = pd.read_excel(ARQUIVO, sheet_name=ABA_DADOS)
    df_pont  = pd.read_excel(ARQUIVO, sheet_name=ABA_PONTOS)

    # features (colunas da B em diante)
    cols_dados = df_dados.columns[1:]
    if len(cols_dados) == 0:
        raise ValueError("TDados não possui colunas a partir da coluna B.")
    X = df_dados[cols_dados].apply(pd.to_numeric, errors="coerce").fillna(0.0).values
    n, m = X.shape

    # nomes de classes e W0
    if "Tipo de Transtorno" in df_pont.columns:
        class_names = df_pont["Tipo de Transtorno"].dropna().astype(str).unique().tolist()
        # Reconstituir W0: linhas que contêm as classes, colunas = features
        # Suporta duas organizações: classes em linhas adjacentes OU planilha "completa".
        # Aqui vamos filtrar apenas as linhas cujo "Tipo de Transtorno" está na lista class_names (mantendo ordem de aparição).
        df_pont_classes = df_pont[df_pont["Tipo de Transtorno"].astype(str).isin(class_names)].copy()
        # Se houver colunas que não estão em cols_dados, descartar
        inter_cols = [c for c in cols_dados if c in df_pont_classes.columns]
        W0 = df_pont_classes[inter_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).values.T
        K = W0.shape[1]
        # garantir alinhamento de nomes (ordem da df)
        class_names = df_pont_classes["Tipo de Transtorno"].astype(str).tolist()
    else:
        # fallback simples — assume primeiras K linhas são classes
        K_default = 11
        W0 = df_pont.loc[:K_default-1, cols_dados].apply(pd.to_numeric, errors="coerce").fillna(0.0).values.T
        K = W0.shape[1]
        class_names = [f"Classe_{i+1}" for i in range(K)]

    # saneamento X
    X = np.nan_to_num(X, nan=0.0, neginf=0.0, posinf=1.0)
    X = np.clip(X, 0.0, 1.0)

    # y multilabel (sem "Sem Transtorno" nas K tradicionais)
    y_lists_all = parse_multilabel(df_dados.get(COL_ALVO, pd.Series([""]*n)), class_names, normal_label=NORMAL_LABEL)

    # W tunado (se existir)
    W = None
    try:
        df_tun = pd.read_excel(ARQUIVO, sheet_name=ABA_PONTOS_TUNADA)
        # espera-se formato: linhas=classes, colunas=features, com coluna "Tipo de Transtorno"
        inter_cols_t = [c for c in cols_dados if c in df_tun.columns]
        # garantir mesma ordem de classes
        df_tun_ord = df_tun.set_index("Tipo de Transtorno").loc[class_names].reset_index()
        W = df_tun_ord[inter_cols_t].apply(pd.to_numeric, errors="coerce").fillna(0.0).values.T
        if W.shape != W0.shape:
            print("[AVISO] Dimensão de W tunado difere de W0; usando W0 para análises.")
            W = None
    except Exception:
        pass

    W_use = W if W is not None else W0
    weights_source = "Tunado" if W is not None else "Heurístico (W0)"

    # ---------- previsões ----------
    S = X @ W_use
    P = softmax_rows(S)

    class_to_idx = {c:i for i,c in enumerate(class_names)}

    # hits top-k (somente classes tradicionais)
    hits_topk = topk_hits(y_lists_all, P, class_to_idx, k=TOPK)
    err_topk = 1 - hits_topk

    # ========= 1) Resumo por variável =========
    # normas por coluna (ao longo das classes)
    L1 = np.sum(np.abs(W_use), axis=1)
    L2 = np.sqrt(np.sum(W_use**2, axis=1))
    max_abs = np.max(np.abs(W_use), axis=1)
    arg_max = np.argmax(np.abs(W_use), axis=1)
    classe_max = [class_names[i] for i in arg_max]

    # contribuição média absoluta para a(s) classe(s) verdadeira(s)
    # Para cada linha i e classe c verdadeira: contrib_i,j = |x_ij * w_jc|; média ao longo de linhas e classes verdadeiras
    contrib_abs = np.zeros(m, dtype=float)
    count = 0
    for i, labs in enumerate(y_lists_all):
        true_idx = [class_to_idx[c] for c in labs if c in class_to_idx]
        if not true_idx:
            continue
        x_i = X[i, :]
        for c in true_idx:
            contrib_abs += np.abs(x_i * W_use[:, c])
            count += 1
    if count > 0:
        contrib_abs /= count

    # correlação de cada X_j com prob. da classe de maior peso (apenas para dar um sinal interpretável)
    corr_with_topclass = []
    pval_with_topclass = []
    for j in range(m):
        c = arg_max[j]
        r, pval = safe_spearman(X[:, j], P[:, c])
        corr_with_topclass.append(r)
        pval_with_topclass.append(pval)

    df_feat = pd.DataFrame({
        "feature": cols_dados,
        "L1_along_classes": L1,
        "L2_along_classes": L2,
        "max_abs_weight": max_abs,
        "class_of_max_weight": classe_max,
        "avg_abs_contrib_true": contrib_abs,
        "spearman_with_P_of_class_maxWeight": corr_with_topclass,
        "pval_spearman": pval_with_topclass
    }).sort_values(["avg_abs_contrib_true","max_abs_weight"], ascending=False).reset_index(drop=True)

    # ========= 2) Correlação com erro (point-biserial ~ Pearson) =========
    # r(X_j, erro_topk); também Spearman
    r_pear = []
    p_pear = []
    r_spear = []
    p_spear = []
    for j in range(m):
        r, p = safe_pearson(X[:, j], err_topk)   # point-biserial
        r_pear.append(r); p_pear.append(p)
        rs, ps = safe_spearman(X[:, j], err_topk)
        r_spear.append(rs); p_spear.append(ps)

    df_err_corr = pd.DataFrame({
        "feature": cols_dados,
        "pearson_with_error": r_pear,
        "pearson_pvalue": p_pear,
        "spearman_with_error": r_spear,
        "spearman_pvalue": p_spear
    }).sort_values("pearson_with_error", ascending=False).reset_index(drop=True)

    # ========= 3) Mutual Information com erro (robusto a monotonia) =========
    try:
        mi = mutual_info_per_feature(X, err_topk)
    except Exception:
        mi = np.zeros(m)
    df_mi = pd.DataFrame({"feature": cols_dados, "mutual_info_with_error": mi}).sort_values(
        "mutual_info_with_error", ascending=False).reset_index(drop=True)

    # ========= 4) VIF (multicolinearidade) =========
    df_vif = compute_vif(X, list(cols_dados))

    # ========= 5) Correlação entre features (top pares) =========
    corr = pd.DataFrame(X, columns=cols_dados).corr(method="spearman")
    # Selecionar top pares por |corr| > 0.8
    pairs = []
    cols = list(cols_dados)
    for i in range(len(cols)):
        for j in range(i+1, len(cols)):
            val = corr.iloc[i, j]
            if abs(val) >= 0.8:
                pairs.append((cols[i], cols[j], float(val)))
    df_pairs = pd.DataFrame(pairs, columns=["feature_i","feature_j","spearman_corr_abs>=0.8"]).sort_values(
        "spearman_corr_abs>=0.8", ascending=False).reset_index(drop=True)

    # ========= 6) Pesos por classe =========
    df_w_by_class = pd.DataFrame(W_use.T, columns=cols_dados)
    df_w_by_class.insert(0, "classe", class_names)

    # ========= 7) Estabilidade W vs W0 =========
    df_stab = pd.DataFrame(columns=["feature","class","w0","w","delta","abs_delta"])
    if W is not None:
        deltas = W - W0
        rows = []
        for j in range(m):
            for c in range(len(class_names)):
                w0 = W0[j, c]; w1 = W[j, c]; d = w1 - w0
                rows.append((cols_dados[j], class_names[c], w0, w1, d, abs(d)))
        df_stab = pd.DataFrame(rows, columns=["feature","class","w0","w","delta","abs_delta"]).sort_values(
            "abs_delta", ascending=False).reset_index(drop=True)

    # ========= 8) Contribuição média por classe =========
    # para cada classe c: média_i (sum_j x_ij * w_jc) e também média do |x_ij * w_jc| por feature
    class_contrib = []
    for c, cname in enumerate(class_names):
        contrib_i = (X @ W_use[:, c])
        class_contrib.append({
            "classe": cname,
            "mean_logit": float(np.mean(contrib_i)),
            "std_logit": float(np.std(contrib_i)),
            "mean_prob": float(np.mean(P[:, c])),
            "std_prob": float(np.std(P[:, c]))
        })
    df_class_contrib = pd.DataFrame(class_contrib).sort_values("mean_prob", ascending=False).reset_index(drop=True)

    # ========= 9) Correlação X_j com P[:,c] (matriz m x K) =========
    spearman_mat = np.zeros((m, len(class_names)))
    for j in range(m):
        for c in range(len(class_names)):
            r, _ = safe_spearman(X[:, j], P[:, c])
            spearman_mat[j, c] = r
    df_corr_feat_prob = pd.DataFrame(spearman_mat, index=cols_dados, columns=class_names)

    # ========= 10) Notas =========
    notas = [{
        "pesos_utilizados": weights_source,
        "n_amostras": n,
        "m_variaveis": m,
        "k_classes": len(class_names),
        "topk": TOPK,
        "taxa_acerto_topk": float(np.mean(hits_topk)),
    }]
    df_notas = pd.DataFrame(notas)

    # --------- Exporta Excel ---------
    with pd.ExcelWriter(SAIDA_XLSX, engine="openpyxl", mode="w") as wr:
        df_feat.to_excel(wr, sheet_name="01_Feature_Summary", index=False)
        df_err_corr.to_excel(wr, sheet_name="02_Error_Correlation", index=False)
        df_mi.to_excel(wr, sheet_name="03_Mutual_Info_Error", index=False)
        df_vif.to_excel(wr, sheet_name="04_VIF", index=False)
        df_pairs.to_excel(wr, sheet_name="05_HighCorr_Pairs", index=False)
        df_w_by_class.to_excel(wr, sheet_name="06_Weights_ByClass", index=False)
        df_class_contrib.to_excel(wr, sheet_name="07_Class_Contrib", index=False)
        df_corr_feat_prob.reset_index(names="feature").to_excel(wr, sheet_name="08_Spearman_X_vs_Pc", index=False)
        df_stab.to_excel(wr, sheet_name="09_Stability_W_vs_W0", index=False)
        df_notas.to_excel(wr, sheet_name="10_Notas", index=False)

    print(f"✅ Relatório gerado: {os.path.abspath(SAIDA_XLSX)}")

if __name__ == "__main__":
    main()
