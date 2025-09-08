# -*- coding: utf-8 -*-
"""
TDados Outlier Cleaner (Jayne)
------------------------------
Analisa estatisticamente a planilha TDados e cria:
 - TDados_clean: igual à TDados, mas **sem** as linhas suspeitas de rótulo/outlier por classe.
 - Outlier_Score: relatório com escores por linha e motivo(s) do flag.
 - Stats_Outliers: contagem por classe (quantos foram sinalizados/removidos).

Regras principais:
 - "Outlier" aqui significa: a linha declarou pertencer a alguma(s) classe(s), mas seu vetor
   de características (colunas B..fim) está muito distante do perfil típico da(s) classe(s).
 - Linhas onde Alvo é "não/nao" ou vazio NÃO são removidas (ficam como desconhecidas).
 - Multi-rótulo: medimos distância da linha a **cada** classe declarada e usamos o **menor** score.
 - Métricas usadas (com parâmetros ajustáveis):

   (A) Distância de Mahalanobis por classe com regularização (cov + λI).
       - Para cada classe c, calculamos média e covariância nas linhas que têm c.
       - Score_A = menor distância da linha até as classes que declarou.
       - Threshold por classe: percentil PERC_MAHA (ex.: 99º) da distribuição de distâncias dentro da classe.
       - Flag_A = Score_A > limiar_{classe_escolhida}.

   (B) Z-score univariado máximo por classe (robusto).
       - Para cada classe c, computamos mediana e MAD (desvio absoluto mediano) por coluna.
       - z_robusto = |x - mediana| / (MAD * 1.4826) (fallback para desvio padrão se MAD~0)
       - Score_B = maior z_robusto dentre as colunas.
       - Flag_B se Score_B > Z_MAX (ex.: 4.5).

   (C) Anomalia por energia (soma das features) em relação à classe.
       - Soma de features s = sum(x)
       - Flag_C se s está fora do intervalo [p_low, p_high] (ex.: [1º, 99º] percentis) da classe.

Uma linha é removida se:  (Flag_A) OR (Flag_B AND Flag_C)
   - Ou seja, Mahalanobis sozinho já remove (forte evidência);
   - Se só Z-score estourar, exigimos também anomalia na soma para robustez.

Parâmetros podem ser ajustados no topo do script.

Saída: mantém todas as abas do arquivo Excel e adiciona/atualiza TDados_clean, Outlier_Score e Stats_Outliers.

Requisitos: pandas, numpy, openpyxl (já usados no seu projeto).
"""

import os, shutil, tempfile
from datetime import datetime
import numpy as np
import pandas as pd

# ================== CONFIG ==================
ARQUIVO = r"c:\SourceCode\qip\python\banco_dados.xlsx"
ABA_DADOS = "TDados"
COL_ALVO = "Alvo"

# Parâmetros dos detectores
LAMBDA_RIDGE = 1e-3      # regularização na covariância (λI)
PERC_MAHA = 99.0         # percentil da distância de Mahalanobis por classe
Z_MAX = 4.5              # z-score robusto máximo por classe (cutoff)
ENERGY_QUANT = (1.0, 99.0)  # percentis para soma das features por classe

# Mínimos para estatística estável
MIN_PER_CLASS = 8        # mínimo de amostras por classe para estimar covariância robusta
RIDGE_MIN_VAR = 1e-3     # variância mínima por coluna (evita divisão por zero)
EPS = 1e-12

# ================== UTIL ==================
def normalize_token(s: str) -> str:
    s = (s or "").strip().lower()
    return (s.replace("ã","a").replace("á","a").replace("â","a")
             .replace("é","e").replace("í","i").replace("ó","o").replace("ú","u"))

def parse_labels(series):
    """Retorna lista de rótulos por linha. Trata 'nao'/'não' e vazio como desconhecido -> lista vazia."""
    out = []
    for val in series.astype(object).tolist():
        if pd.isna(val) or str(val).strip() == "":
            out.append([]); continue
        s = str(val)
        for d in ["|",";",","]:
            s = s.replace(d, "|")
        labs_raw = [p.strip() for p in s.split("|") if p.strip()]
        labs = []
        unknown = False
        for lab in labs_raw:
            tok = normalize_token(lab)
            if tok == "nao":
                unknown = True; break
            labs.append(lab)
        out.append([] if unknown else labs)
    return out

def robust_center_cov(X, ridge=LAMBDA_RIDGE):
    """Centro (média) e covariância regularizada. Usa pinv para estabilidade."""
    mu = np.nanmean(X, axis=0)
    Xc = X - mu
    # cov populacional (n no denominador) para robustez com poucos pontos
    cov = (Xc.T @ Xc) / max(1, Xc.shape[0])
    # garante variância mínima e ridge
    diag = np.diag(cov)
    diag = np.maximum(diag, RIDGE_MIN_VAR)
    cov = cov.copy()
    np.fill_diagonal(cov, diag + ridge)
    return mu, cov

def mahalanobis_rows(X, mu, cov):
    """Distância de Mahalanobis por linha (com pinv para estabilidade)."""
    Xc = X - mu
    cov_inv = np.linalg.pinv(cov)  # robusto a singularidade
    left = Xc @ cov_inv
    d2 = np.sum(left * Xc, axis=1)
    d2 = np.maximum(d2, 0.0)
    return np.sqrt(d2)

def mad(x):
    med = np.median(x)
    dev = np.median(np.abs(x - med))
    return med, dev

def robust_z_row(x, med, madv, std):
    """z-score robusto por coluna: |x-med| / (MAD*1.4826) (fallback p/ std)."""
    z = np.zeros_like(x, dtype=float)
    scale = madv * 1.4826
    for j in range(len(x)):
        if scale[j] > 1e-9:
            z[j] = abs(x[j] - med[j]) / scale[j]
        else:
            z[j] = abs(x[j] - med[j]) / max(std[j], 1e-9)
    return z

def save_preserving_sheets(target_path, dfs_and_sheets):
    """Preserva todas as abas e substitui apenas as listadas."""
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

# ================== MAIN ==================
def main():
    df = pd.read_excel(ARQUIVO, sheet_name=ABA_DADOS)
    if df.shape[1] < 2:
        raise ValueError("TDados precisa ter coluna de ID em A e features a partir de B.")
    cols_feat = df.columns[1:]
    X_all = df[cols_feat].apply(pd.to_numeric, errors="coerce").fillna(0.0).values
    X_all = np.clip(X_all, 0.0, 1.0)  # mantém compatível com pipeline
    y_lists = parse_labels(df[COL_ALVO])

    # identifica linhas com rótulo conhecido (não 'nao' nem vazio)
    idx_known = [i for i,l in enumerate(y_lists) if len(l) > 0]

    # mapeia todas as classes distintas nos rótulos conhecidos
    classes = sorted({lab for labs in y_lists for lab in labs})
    print("[INFO] Classes detectadas:", classes)

    # estatísticas por classe
    stats = {}
    for c in classes:
        idx_c = [i for i in idx_known if c in y_lists[i]]
        Xc = X_all[idx_c] if idx_c else np.empty((0, len(cols_feat)))
        if len(idx_c) >= MIN_PER_CLASS:
            mu, cov = robust_center_cov(Xc, ridge=LAMBDA_RIDGE)
            d_maha = mahalanobis_rows(Xc, mu, cov)
            thr = float(np.percentile(d_maha, PERC_MAHA)) if len(d_maha) > 0 else np.inf
            # robust stats por coluna
            med = np.median(Xc, axis=0) if len(idx_c) > 0 else np.zeros(len(cols_feat))
            madv = np.median(np.abs(Xc - med), axis=0) if len(idx_c) > 0 else np.ones(len(cols_feat))*1e-6
            std = np.std(Xc, axis=0, ddof=0)
            std = np.maximum(std, np.sqrt(RIDGE_MIN_VAR))
            # energia (soma)
            s = Xc.sum(axis=1) if len(idx_c) > 0 else np.array([])
            if len(s) >= 5:
                p_low, p_high = np.percentile(s, ENERGY_QUANT)
            else:
                p_low, p_high = -np.inf, np.inf
            stats[c] = dict(idx=idx_c, mu=mu, cov=cov, thr=thr, med=med, mad=madv, std=std, s_low=p_low, s_high=p_high)
        else:
            # estatística fraca: fallback simples (diagonal)
            mu = np.nanmean(Xc, axis=0) if len(idx_c)>0 else np.zeros(len(cols_feat))
            var = np.var(Xc, axis=0, ddof=0) if len(idx_c)>0 else np.ones(len(cols_feat))*RIDGE_MIN_VAR
            var = np.maximum(var, RIDGE_MIN_VAR)
            cov = np.diag(var + LAMBDA_RIDGE)
            thr = np.inf  # não remover por Mahalanobis para classe com pouca amostra
            med = np.median(Xc, axis=0) if len(idx_c)>0 else np.zeros(len(cols_feat))
            madv = np.median(np.abs(Xc - med), axis=0) if len(idx_c)>0 else np.ones(len(cols_feat))*1e-6
            std = np.sqrt(var)
            s = Xc.sum(axis=1) if len(idx_c) > 0 else np.array([])
            if len(s) >= 5:
                p_low, p_high = np.percentile(s, ENERGY_QUANT)
            else:
                p_low, p_high = -np.inf, np.inf
            stats[c] = dict(idx=idx_c, mu=mu, cov=cov, thr=thr, med=med, mad=madv, std=std, s_low=p_low, s_high=p_high)

    # ----- scoring por linha conhecida -----
    rows = []
    remove_flags = np.zeros(len(df), dtype=bool)

    for i in idx_known:
        x = X_all[i]
        labs = y_lists[i]

        # calcula scores por classe declarada
        scoreA_list = []
        thr_list = []
        scoreB_list = []
        flagB_list = []
        flagC_list = []

        for c in labs:
            st = stats[c]
            # (A) Mahalanobis
            d = float(mahalanobis_rows(x[None,:], st["mu"], st["cov"])[0])
            scoreA_list.append(d)
            thr_list.append(st["thr"])
            # (B) Z robusto max
            z = robust_z_row(x, st["med"], st["mad"], st["std"])
            scoreB_list.append(float(np.max(z)))
            # (C) Energia
            s = float(np.sum(x))
            flagC_list.append(bool(s < st["s_low"] or s > st["s_high"]))

        # agregação por menor distância (classe mais compatível)
        if scoreA_list:
            j_best = int(np.argmin(scoreA_list))
            best_class = labs[j_best]
            Score_A = scoreA_list[j_best]
            Thr_A   = thr_list[j_best]
            Score_B = scoreB_list[j_best]
            Flag_A = bool(Score_A > Thr_A)
            Flag_B = bool(Score_B > Z_MAX)
            Flag_C = bool(flagC_list[j_best])
        else:
            best_class = ""
            Score_A = Thr_A = Score_B = 0.0
            Flag_A = Flag_B = Flag_C = False

        # regra de remoção
        remove = Flag_A or (Flag_B and Flag_C)
        remove_flags[i] = remove

        rows.append({
            "linha_excel": i+2,  # +2 por conta do header + índice 0
            COL_ALVO: df.loc[i, COL_ALVO],
            "classe_mais_proxima": best_class,
            "Score_A_maha": Score_A,
            "Thr_A_maha": Thr_A,
            "Flag_A_maha": Flag_A,
            "Score_B_zmax": Score_B,
            "Flag_B_zmax": Flag_B,
            "Flag_C_energia": Flag_C,
            "remover": remove
        })

    df_scores = pd.DataFrame(rows).sort_values(["remover","Score_A_maha"], ascending=[False, False])

    # ----- criar TDados_clean -----
    df_clean = df.copy()
    df_clean = df_clean.loc[~remove_flags].reset_index(drop=True)

    # ----- estatística final -----
    def count_by_class(mask):
        d = {}
        for c in classes:
            idx_c = [i for i in idx_known if c in y_lists[i]]
            d[c] = int(np.sum(mask[idx_c])) if idx_c else 0
        return d

    removed_by_class = count_by_class(remove_flags)
    kept_by_class = count_by_class(~remove_flags)

    df_stats = pd.DataFrame({
        "classe": classes,
        "removidos": [removed_by_class[c] for c in classes],
        "mantidos": [kept_by_class[c] for c in classes]
    })

    # ----- salvar -----
    saved = save_preserving_sheets(
        ARQUIVO,
        [
            (df_clean, "TDados_clean"),
            (df_scores, "Outlier_Score"),
            (df_stats, "Stats_Outliers"),
        ]
    )
    print("✅ Abas criadas/atualizadas: TDados_clean, Outlier_Score, Stats_Outliers")
    print("💾 Arquivo salvo em:", saved)

if __name__ == "__main__":
    main()
