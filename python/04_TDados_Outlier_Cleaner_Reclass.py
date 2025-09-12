# -*- coding: utf-8 -*-
"""
TDados Outlier Cleaner + Reclass (Jayne)
- Lê classes válidas de Pontuação!A3:A13 (Excel, inclusivo).
- Regras:
  (1) Rótulo fora das classes válidas -> "nao"
  (2) Outlier da própria classe -> "nao"
  (3) Dentro de "nao": baixa ativação -> "Sem Transtorno"
- Saída: TDados_clean, Outlier_Score, Stats_Reclass, Nao_Energy
"""

import os, shutil, tempfile
from datetime import datetime
import numpy as np
import pandas as pd

# ================== CONFIG ==================
ARQUIVO     = r"c:\SourceCode\qip\python\banco_dados.xlsx"
ABA_DADOS   = "TDados"
ABA_PONTOS  = "Pontuação"
COL_ALVO    = "Alvo"

# Detectores / limiares (ajustados para reduzir reclassificação excessiva)
LAMBDA_RIDGE   = 1e-3
PERC_MAHA      = 99.7      # ↑ mais tolerante
Z_MAX          = 5.2       # ↑
ENERGY_QUANT   = (0.5, 99.5)

MIN_PER_CLASS  = 8
RIDGE_MIN_VAR  = 1e-3

# "Sem Transtorno" somente se houver amostra suficiente de "nao"
NAO_LOW_ENERGY_PERC = 5.0   # 5% mais baixo
NAO_MIN_FOR_ST      = 10    # mínimo de linhas "nao" para habilitar ST
ABS_MIN_ENERGY      = 0.0   # piso absoluto opcional (desligado)

# ================== UTIL ==================
def normalize_token(s: str) -> str:
    s = (s or "").strip().lower()
    rep = {"ã":"a","á":"a","â":"a","à":"a",
           "é":"e","ê":"e",
           "í":"i",
           "ó":"o","ô":"o","õ":"o",
           "ú":"u","ü":"u",
           "ç":"c"}
    for k,v in rep.items():
        s = s.replace(k,v)
    return s

def parse_labels(series: pd.Series) -> list[list[str]]:
    """Lista de rótulos; 'nao'/'não'/vazio -> desconhecido (lista vazia)."""
    out = []
    for val in series.astype(object).tolist():
        if pd.isna(val) or str(val).strip() == "":
            out.append([]); continue
        s = str(val)
        for d in ["|",";",","]:
            s = s.replace(d, "|")
        labs_raw = [p.strip() for p in s.split("|") if p.strip()]
        labs, unknown = [], False
        for lab in labs_raw:
            tok = normalize_token(lab)
            if tok in {"nao","não"}:
                unknown = True; break
            labs.append(lab)
        out.append([] if unknown else labs)
    return out

def read_valid_classes_from_pontuacao(path: str, sheet: str) -> dict:
    """
    Lê EXATAMENTE Pontuação!A3:A13 (linhas do Excel, inclusivo) como classes válidas.
    Usa header=None para alinhar 1:1 com linhas do Excel.
    Retorna dict {norm: canônico}.
    """
    colA = pd.read_excel(path, sheet_name=sheet, usecols="A", header=None)
    # Excel row 3..13 -> iloc[2:13] (fim exclusivo inclui 13)
    vals = colA.iloc[2:13, 0].astype(object).tolist()
    canon = [str(x).strip() for x in vals if pd.notna(x) and str(x).strip() != ""]
    mapping = {normalize_token(c): c for c in canon}
    return mapping

def robust_center_cov(X, ridge=LAMBDA_RIDGE):
    mu = np.nanmean(X, axis=0)
    Xc = X - mu
    cov = (Xc.T @ Xc) / max(1, Xc.shape[0])
    diag = np.diag(cov)
    diag = np.maximum(diag, RIDGE_MIN_VAR)
    cov = cov.copy()
    np.fill_diagonal(cov, diag + ridge)
    return mu, cov

def mahalanobis_rows(X, mu, cov):
    Xc = X - mu
    cov_inv = np.linalg.pinv(cov)
    d2 = np.sum((Xc @ cov_inv) * Xc, axis=1)
    return np.sqrt(np.maximum(d2, 0.0))

def robust_z_row(x, med, madv, std):
    z = np.zeros_like(x, dtype=float)
    scale = madv * 1.4826
    for j in range(len(x)):
        if scale[j] > 1e-9:
            z[j] = abs(x[j] - med[j]) / scale[j]
        else:
            z[j] = abs(x[j] - med[j]) / max(std[j], 1e-9)
    return z

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

# ================== MAIN ==================
def main():
    # --- Ler dados
    df = pd.read_excel(ARQUIVO, sheet_name=ABA_DADOS)
    if df.shape[1] < 2:
        raise ValueError("TDados precisa ter coluna de ID em A e features a partir de B.")
    cols_feat = df.columns[1:]
    X_all = df[cols_feat].apply(pd.to_numeric, errors="coerce").fillna(0.0).values
    X_all = np.clip(X_all, 0.0, 1.0)
    y_lists = parse_labels(df[COL_ALVO])

    # --- Ler classes válidas (Pontuação!A3:A13)
    canon_map = read_valid_classes_from_pontuacao(ARQUIVO, ABA_PONTOS)
    valid_norm = set(canon_map.keys())
    print(f"[INFO] Classes válidas (Pontuação!A3:A13): {[canon_map[k] for k in valid_norm]}")

    # --- Normalizar e padronizar rótulos de TDados, marcando inválidos
    y_std = []
    invalid_mask = np.zeros(len(df), dtype=bool)
    for i, labs in enumerate(y_lists):
        std_labs = []
        if not labs:
            y_std.append(std_labs); continue
        for lab in labs:
            n = normalize_token(lab)
            if n in valid_norm:
                std_labs.append(canon_map[n])   # padroniza nome canônico
            else:
                invalid_mask[i] = True          # terá reclassificação p/ "nao"
        y_std.append(std_labs)

    # --- Estatísticas por classe (somente válidas/observadas)
    observed_valid = sorted({c for labs in y_std for c in labs})
    print("[INFO] Classes observadas e válidas:", observed_valid)

    MIN_PER = MIN_PER_CLASS
    stats = {}
    for c in observed_valid:
        idx_c = [i for i, labs in enumerate(y_std) if c in labs]
        Xc = X_all[idx_c] if idx_c else np.empty((0, len(cols_feat)))
        if len(idx_c) >= MIN_PER:
            mu, cov = robust_center_cov(Xc, ridge=LAMBDA_RIDGE)
            d_maha = mahalanobis_rows(Xc, mu, cov)
            thr = float(np.percentile(d_maha, PERC_MAHA)) if len(d_maha) else np.inf
            med = np.median(Xc, axis=0) if len(idx_c) > 0 else np.zeros(len(cols_feat))
            madv = np.median(np.abs(Xc - med), axis=0) if len(idx_c) > 0 else np.ones(len(cols_feat))*1e-6
            std = np.maximum(np.std(Xc, axis=0, ddof=0), np.sqrt(RIDGE_MIN_VAR))
            s = Xc.sum(axis=1) if len(idx_c) > 0 else np.array([])
            if len(s) >= 5:
                p_low, p_high = np.percentile(s, ENERGY_QUANT)
            else:
                p_low, p_high = -np.inf, np.inf
            stats[c] = dict(mu=mu, cov=cov, thr=thr, med=med, mad=madv, std=std, s_low=p_low, s_high=p_high)
        else:
            # fallback (não faz corte por Mahalanobis quando poucos pontos)
            mu = np.nanmean(Xc, axis=0) if len(idx_c)>0 else np.zeros(len(cols_feat))
            var = np.maximum(np.var(Xc, axis=0, ddof=0), RIDGE_MIN_VAR)
            cov = np.diag(var + LAMBDA_RIDGE)
            thr = np.inf
            med = np.median(Xc, axis=0) if len(idx_c)>0 else np.zeros(len(cols_feat))
            madv = np.median(np.abs(Xc - med), axis=0) if len(idx_c)>0 else np.ones(len(cols_feat))*1e-6
            std = np.sqrt(var)
            s = Xc.sum(axis=1) if len(idx_c) > 0 else np.array([])
            if len(s) >= 5:
                p_low, p_high = np.percentile(s, ENERGY_QUANT)
            else:
                p_low, p_high = -np.inf, np.inf
            stats[c] = dict(mu=mu, cov=cov, thr=thr, med=med, mad=madv, std=std, s_low=p_low, s_high=p_high)

    # --- Passo 1: inválidas e outliers -> "nao"
    y_new = []
    rows_score = []
    to_nao = np.zeros(len(df), dtype=bool)

    for i in range(len(df)):
        x = X_all[i]
        labs = y_std[i]

        # rótulo inválido em relação a Pontuação -> "nao"
        if invalid_mask[i] and labs:
            y_new.append([]); to_nao[i] = True
            rows_score.append({
                "linha_excel": i+2,
                COL_ALVO: " | ".join(labs),
                "classe_mais_proxima": "",
                "Score_A_maha": np.nan,
                "Thr_A_maha": np.nan,
                "Score_B_zmax": np.nan,
                "Flag_B_zmax": False,
                "Flag_C_energia": False,
                "reclassificada_para": "nao",
                "motivo": "fora_das_classes_avaliacao(Pontuacao)"
            })
            continue

        # desconhecido original ou sem rótulo válido
        if not labs:
            y_new.append([])
            rows_score.append({
                "linha_excel": i+2,
                COL_ALVO: "nao",
                "classe_mais_proxima": "",
                "Score_A_maha": np.nan,
                "Thr_A_maha": np.nan,
                "Score_B_zmax": np.nan,
                "Flag_B_zmax": False,
                "Flag_C_energia": False,
                "reclassificada_para": "nao",
                "motivo": "original_nao_ou_sem_rotulo_valido"
            })
            continue

        # Outlier vs classes válidas
        scoreA_list, thr_list, scoreB_list, flagC_list, labs_used = [], [], [], [], []
        for c in labs:
            st = stats.get(c)
            if st is None:
                continue
            d = float(mahalanobis_rows(x[None,:], st["mu"], st["cov"])[0])
            z = robust_z_row(x, st["med"], st["mad"], st["std"])
            s = float(np.sum(x))
            scoreA_list.append(d);   thr_list.append(st["thr"])
            scoreB_list.append(float(np.max(z)))
            flagC_list.append(bool(s < st["s_low"] or s > st["s_high"]))
            labs_used.append(c)

        if scoreA_list:
            j_best = int(np.argmin(scoreA_list))
            best_class = labs_used[j_best]
            Score_A, Thr_A = scoreA_list[j_best], thr_list[j_best]
            Score_B = scoreB_list[j_best]
            Flag_A = bool(Score_A > Thr_A)
            Flag_B = bool(Score_B > Z_MAX)
            Flag_C = bool(flagC_list[j_best])
        else:
            best_class = ""; Score_A = Thr_A = Score_B = 0.0
            Flag_A = Flag_B = Flag_C = False

        is_outlier = Flag_A or (Flag_B and Flag_C)
        if is_outlier:
            y_new.append([]); to_nao[i] = True
            reclass = "nao"; motivo = "outlier_da_classe"
        else:
            y_new.append(labs); reclass = " | ".join(labs); motivo = "mantido"

        rows_score.append({
            "linha_excel": i+2,
            COL_ALVO: " | ".join(labs),
            "classe_mais_proxima": best_class,
            "Score_A_maha": Score_A,
            "Thr_A_maha": Thr_A,
            "Score_B_zmax": Score_B,
            "Flag_B_zmax": Flag_B,
            "Flag_C_energia": Flag_C,
            "reclassificada_para": reclass,
            "motivo": motivo
        })

    # --- Passo 2: "nao" com baixa ativação -> "Sem Transtorno"
    sums = X_all.sum(axis=1)
    idx_nao = [i for i, labs in enumerate(y_new) if len(labs) == 0]
    nao_sums = sums[idx_nao] if idx_nao else np.array([])

    sem_flags = np.zeros(len(df), dtype=bool)
    thr_nao = np.nan
    if len(idx_nao) >= NAO_MIN_FOR_ST:
        thr_nao = float(np.percentile(nao_sums, NAO_LOW_ENERGY_PERC))
        thr_final = max(thr_nao, ABS_MIN_ENERGY)
        for k, i in enumerate(idx_nao):
            if nao_sums[k] <= thr_final:
                y_new[i] = ["Sem Transtorno"]
                sem_flags[i] = True

    # --- TDados_clean
    df_clean = df.copy()
    df_clean[COL_ALVO] = [" | ".join(l) if l else "nao" for l in y_new]

    # --- Relatórios
    df_scores = pd.DataFrame(rows_score)
    nao_audit = [{"linha_excel": i+2,
                  "soma_features": float(sums[i]),
                  "limiar_perc_nao": thr_nao,
                  "classificado": "Sem Transtorno" if sem_flags[i] else "nao"}
                 for i in idx_nao]
    df_nao_energy = pd.DataFrame(nao_audit)

    # Stats de reclassificação
    to_nao_by_class = {}
    for c in observed_valid:
        idx_c = [i for i in range(len(df)) if c in (y_std[i] if y_std[i] else [])]
        to_nao_by_class[c] = int(np.sum(to_nao[idx_c])) if idx_c else 0
    stats_rows = [{"classe_base": c, "reclass_para_nao": to_nao_by_class.get(c, 0)}
                  for c in observed_valid]
    stats_rows.append({"classe_base": "nao",
                       "reclass_para_SemTranstorno": int(np.sum(sem_flags[idx_nao])) if idx_nao else 0})
    df_stats = pd.DataFrame(stats_rows)

    # --- Salvar
    saved = save_preserving_sheets(
        ARQUIVO,
        [
            (df_clean,     "TDados_clean"),
            (df_scores,    "Outlier_Score"),
            (df_stats,     "Stats_Reclass"),
            (df_nao_energy,"Nao_Energy"),
        ]
    )
    print("✅ Abas criadas/atualizadas: TDados_clean, Outlier_Score, Stats_Reclass, Nao_Energy")
    print("💾 Arquivo salvo em:", saved)

if __name__ == "__main__":
    main()