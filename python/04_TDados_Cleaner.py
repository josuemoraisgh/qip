# -*- coding: utf-8 -*-
"""
Marcar 'não' como 'Sem Transtorno' por baixa ativação
----------------------------------------------------
Lê as features de TDados_clean (se existir) ou TDados, calcula as probabilidades
(softmax de X @ W) usando os pesos da aba Pontuação_Tunada (se existir) ou Pontuação,
e altera o Alvo de linhas 'não/nao' (ou vazias) para 'Sem Transtorno' quando:
    top1_prob < T1  e  (top1_prob - top2_prob) < T2

Parâmetros T1/T2:
- Se a aba 'Regras_Normal' existir e contiver 'T1_top1_prob_max' e
  'T2_margem_top1_top2_max', usa esses valores.
- Caso contrário, usa T1=0.40 e T2=0.05 (ajuste livre).

Saídas:
- Atualiza/Cria 'TDados_clean' sem mudar a ordem das linhas
- 'SemTranstorno_Analise' com diagnóstico por linha analisada
- 'SemTranstorno_Stats' com contagens antes/depois
"""

import numpy as np
import pandas as pd

# ================== CONFIG ==================
ARQUIVO = r"c:\SourceCode\qip\python\banco_dados.xlsx"

ABA_DADOS        = "TDados"
ABA_DADOS_CLEAN  = "TDados_clean"
ABA_PONTOS       = "Pontuação"
ABA_PONTOS_TUN   = "Pontuação_Tunada"
ABA_REGRAS       = "Regras_Normal"

ABA_DIAG         = "SemTranstorno_Analise"
ABA_STATS        = "SemTranstorno_Stats"

COL_ALVO = "Alvo"
COL_TIPO = "Tipo de Transtorno"
LINHA_INICIO_PONTOS = 3
COLUNA_TAM = 11

# Defaults (se não houver Regras_Normal)
T1_DEFAULT = 0.40
T2_DEFAULT = 0.05

EPS = 1e-12

# ================== UTIL ==================
def normalize_token(s: str) -> str:
    s = (s or "").strip().lower()
    return (s.replace("ã", "a").replace("á","a").replace("â","a")
             .replace("é","e").replace("í","i").replace("ó","o").replace("ú","u"))

def is_unknown(val) -> bool:
    if val is None:
        return True
    s = str(val).strip()
    if s == "":
        return True
    tok = normalize_token(s)
    return tok in ("nao", "não")

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
        from datetime import datetime
        carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
        alt_path = target_path.replace(".xlsx", f"_{carimbo}.xlsx")
        shutil.copyfile(tmpfile, alt_path)
        saved = alt_path
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return saved

# ================== MAIN ==================
def main():
    # --- Carregar TDados/TDados_clean ---
    try:
        df_clean = pd.read_excel(ARQUIVO, sheet_name=ABA_DADOS_CLEAN)
        base_sheet = ABA_DADOS_CLEAN
    except Exception:
        df_clean = pd.read_excel(ARQUIVO, sheet_name=ABA_DADOS)
        base_sheet = ABA_DADOS
    df_all = df_clean.copy()
    if df_all.shape[1] < 2:
        raise ValueError("Esperado: ID em A, features a partir de B, e coluna 'Alvo'.")

    # --- Escolher pesos (Pontuação_Tunada ou Pontuação) ---
    try:
        df_p = pd.read_excel(ARQUIVO, sheet_name=ABA_PONTOS_TUN)
        fonte_w = ABA_PONTOS_TUN
    except Exception:
        df_p = pd.read_excel(ARQUIVO, sheet_name=ABA_PONTOS)
        fonte_w = ABA_PONTOS

    # Colunas de features (B..)
    cols_feat = df_all.columns[1:]
    faltantes = [c for c in cols_feat if c not in df_p.columns]
    if faltantes:
        raise ValueError(f"Colunas de feature ausentes em '{fonte_w}': {faltantes[:10]}{'...' if len(faltantes)>10 else ''}")

    # Extrair W (d x K) da janela correta
    r0 = LINHA_INICIO_PONTOS - 2
    linhas_modelos = df_p.index[r0: r0 + COLUNA_TAM]
    if len(linhas_modelos) != COLUNA_TAM:
        raise ValueError(f"Aba '{fonte_w}' não tem {COLUNA_TAM} linhas a partir de {LINHA_INICIO_PONTOS}.")
    W_block = df_p.loc[linhas_modelos, cols_feat].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    W = W_block.values.T  # (d x K)
    K = W.shape[1]

    # Nomes das classes
    if COL_TIPO in df_p.columns:
        class_names = df_p.loc[linhas_modelos, COL_TIPO].astype(str).tolist()
    else:
        class_names = [f"Classe_{i+1}" for i in range(COLUNA_TAM)]

    # Ativações
    X = df_all[cols_feat].apply(pd.to_numeric, errors="coerce").fillna(0.0).clip(0,1).values
    P = softmax_rows(X @ W)  # (n x K)

    # Carregar T1/T2 das regras (se existir)
    T1, T2 = T1_DEFAULT, T2_DEFAULT
    try:
        df_reg = pd.read_excel(ARQUIVO, sheet_name=ABA_REGRAS)
        df_reg = df_reg.rename(columns={c:str(c).strip() for c in df_reg.columns})
        param_col = "param" if "param" in df_reg.columns else df_reg.columns[0]
        value_col = "value" if "value" in df_reg.columns else df_reg.columns[1]
        lut = dict(zip(df_reg[param_col].astype(str), df_reg[value_col]))
        if "T1_top1_prob_max" in lut:
            T1 = float(lut["T1_top1_prob_max"])
        if "T2_margem_top1_top2_max" in lut:
            T2 = float(lut["T2_margem_top1_top2_max"])
        print(f"[INFO] Usando T1/T2 da aba '{ABA_REGRAS}': T1={T1:.3f} T2={T2:.3f}")
    except Exception:
        print(f"[WARN] '{ABA_REGRAS}' não encontrada. Usando defaults: T1={T1:.3f} T2={T2:.3f}")

    # Diagnóstico e marcação
    order = np.argsort(-P, axis=1)
    top1 = P[np.arange(P.shape[0]), order[:,0]]
    top2 = P[np.arange(P.shape[0]), order[:,1]]
    margin = top1 - top2

    is_unknown_mask = df_all[COL_ALVO].apply(is_unknown).values
    low_act_mask = (top1 < T1) & (margin < T2)
    to_sem_transtorno = is_unknown_mask & low_act_mask

    # Preparar análise por linha apenas para as 'não/vazias'
    rows = []
    for i in range(len(df_all)):
        if not is_unknown_mask[i]:
            continue
        rec = {
            "linha_excel": i+2,
            "alvo_original": df_all.loc[i, COL_ALVO],
            "top1_classe": class_names[order[i,0]],
            "top1_prob": float(top1[i]),
            "top2_classe": class_names[order[i,1]],
            "top2_prob": float(top2[i]),
            "margem_top1_top2": float(margin[i]),
            "criterio_baixa_ativacao": bool(low_act_mask[i]),
            "marcar_sem_transtorno": bool(to_sem_transtorno[i]),
        }
        rows.append(rec)
    df_diag = pd.DataFrame(rows)

    # Atualizar TDados_clean (ou TDados se não existir) — sem mudar ordem
    df_clean_update = df_all.copy()
    n_before_unknown = int(is_unknown_mask.sum())
    n_mark = int(to_sem_transtorno.sum())
    df_clean_update.loc[to_sem_transtorno, COL_ALVO] = "Sem Transtorno"

    df_stats = pd.DataFrame([
        {"metrica":"linhas_analizadas_nao_ou_vazio", "valor": n_before_unknown},
        {"metrica":"marcadas_para_Sem_Transtorno",   "valor": n_mark},
        {"metrica":"nao_marcadas",                   "valor": n_before_unknown - n_mark},
        {"metrica":"T1_usado",                       "valor": T1},
        {"metrica":"T2_usado",                       "valor": T2},
        {"metrica":"fonte_W",                        "valor": fonte_w},
        {"metrica":"base_features",                  "valor": base_sheet},
    ])

    # Escrever de volta
    saved = save_preserving_sheets(
        ARQUIVO,
        [
            (df_clean_update, ABA_DADOS_CLEAN),
            (df_diag,         ABA_DIAG),
            (df_stats,        ABA_STATS),
        ]
    )
    print("✅ Abas criadas/atualizadas:", ABA_DADOS_CLEAN, ABA_DIAG, ABA_STATS)
    print("💾 Arquivo salvo em:", saved)

if __name__ == "__main__":
    main()
