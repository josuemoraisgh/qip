# -*- coding: utf-8 -*-
"""
Marcar 'não' como 'Sem Transtorno' — com controle de cobertura
--------------------------------------------------------------
Este script marca linhas cujo Alvo é "não/nao" (ou vazio) como "Sem Transtorno"
quando a ativação é baixa, e permite **aumentar** o volume marcado via:
  (A) MODO FIXO: alterar/forçar T1/T2 ou aplicar um BOOST nos T1/T2 da Regras_Normal.
  (B) MODO AUTO: escolher T1/T2 automaticamente para atingir uma **cobertura alvo**
      (percentual das linhas desconhecidas que serão marcadas).

CONDICAO base:
    top1_prob < T1  e  (top1_prob - top2_prob) < T2

Probabilidades são calculadas com:
    P = softmax( (X @ W) / TAU_SOFTMAX )

- W vem de 'Pontuação_Tunada' (se existir) senão 'Pontuação'.
- T1/T2 base vêm de 'Regras_Normal', se existir; caso contrário, parte de defaults.

Saídas:
- TDados_clean (atualizado em posição, trocando 'não'->'Sem Transtorno' conforme regra)
- SemTranstorno_Analise (diagnóstico por linha desconhecida)
- SemTranstorno_Stats   (contagens, thresholds usados e modo)
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

# ============ MODOS DE OPERAÇÃO ============
MODE = "auto"     # "fixed" ou "auto"

# --- FIXED --- (usado se MODE == "fixed")
OVERRIDE_T1 = None   # ex.: 0.50  (se None, usa Regras_Normal ou default)
OVERRIDE_T2 = None   # ex.: 0.10  (se None, usa Regras_Normal ou default)

# Boost incremental sobre T1/T2 base (Regras_Normal ou default). Útil para "aumentar" marcações.
BOOST_T1 = 0.07      # aumenta T1 (mais fácil passar no critério top1<T1) — ex.: 0.05
BOOST_T2 = 0.04      # aumenta T2 (margem permitida maior) — ex.: 0.03

# --- AUTO --- (usado se MODE == "auto")
TARGET_MARK_RATIO = 0.20  # alvo: marcar ~20% das linhas 'não/nao' (ajuste como quiser)
T1_GRID = np.linspace(0.18, 0.80, 32)  # grade ampla para T1
T2_GRID = np.linspace(0.02, 0.30, 29)  # grade ampla para T2

# --- Probabilidade - Temperatura ---
TAU_SOFTMAX = 1.20  # >1 deixa P mais "achatado" => reduz top1 e aumenta marcações (1.0 = neutro)

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

def softmax_rows_tau(mat, tau=1.0, axis=1, eps=1e-12):
    x = mat / max(tau, 1e-6)
    x = x - np.max(x, axis=axis, keepdims=True)
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

    # Ativações com temperatura
    X = df_all[cols_feat].apply(pd.to_numeric, errors="coerce").fillna(0.0).clip(0,1).values
    S = X @ W
    P = softmax_rows_tau(S, tau=TAU_SOFTMAX)  # (n x K)

    # Carregar T1/T2 base das Regras_Normal (se existir)
    T1_base, T2_base = T1_DEFAULT, T2_DEFAULT
    try:
        df_reg = pd.read_excel(ARQUIVO, sheet_name=ABA_REGRAS)
        df_reg = df_reg.rename(columns={c:str(c).strip() for c in df_reg.columns})
        param_col = "param" if "param" in df_reg.columns else df_reg.columns[0]
        value_col = "value" if "value" in df_reg.columns else df_reg.columns[1]
        lut = dict(zip(df_reg[param_col].astype(str), df_reg[value_col]))
        if "T1_top1_prob_max" in lut:
            T1_base = float(lut["T1_top1_prob_max"])
        if "T2_margem_top1_top2_max" in lut:
            T2_base = float(lut["T2_margem_top1_top2_max"])
        print(f"[INFO] T1/T2 base da '{ABA_REGRAS}': T1={T1_base:.3f} T2={T2_base:.3f}")
    except Exception:
        print(f"[WARN] '{ABA_REGRAS}' não encontrada. Usando defaults: T1={T1_base:.3f} T2={T2_base:.3f}")

    # Preparar top1/top2/margem
    order = np.argsort(-P, axis=1)
    top1 = P[np.arange(P.shape[0]), order[:,0]]
    top2 = P[np.arange(P.shape[0]), order[:,1]]
    margin = top1 - top2

    is_unknown_mask = df_all[COL_ALVO].apply(is_unknown).values
    idx_unknown = np.where(is_unknown_mask)[0]
    n_unknown = int(len(idx_unknown))

    # ---------- Escolha de T1/T2 ----------
    mode_used = MODE
    if MODE.lower() == "fixed":
        T1_eff = float(OVERRIDE_T1) if OVERRIDE_T1 is not None else float(T1_base)
        T2_eff = float(OVERRIDE_T2) if OVERRIDE_T2 is not None else float(T2_base)
        T1_eff = min(max(T1_eff + BOOST_T1, 0.0), 1.0)
        T2_eff = min(max(T2_eff + BOOST_T2, 0.0), 1.0)
        note = "fixed"
    else:
        # AUTO: escolhe T1/T2 para atingir cobertura alvo (entre desconhecidos)
        best = (None, None, None)  # (gap_abs, T1, T2)
        target = TARGET_MARK_RATIO
        for T1_c in T1_GRID:
            for T2_c in T2_GRID:
                mark = (top1 < T1_c) & (margin < T2_c) & is_unknown_mask
                ratio = mark.sum() / n_unknown if n_unknown > 0 else 0.0
                gap = abs(ratio - target)
                if (best[0] is None) or (gap < best[0]) or (abs(gap - best[0]) < 1e-9 and ratio > ( (best[1] is not None) and (mark.sum() / n_unknown) or -1 )):
                    best = (gap, T1_c, T2_c)
        if best[1] is None:
            T1_eff, T2_eff = T1_base + BOOST_T1, T2_base + BOOST_T2
            note = "auto_fallback"
        else:
            T1_eff, T2_eff = float(best[1]), float(best[2])
            note = "auto_target"

    low_act_mask = (top1 < T1_eff) & (margin < T2_eff)
    to_sem_transtorno = is_unknown_mask & low_act_mask

    # ---------- Diagnóstico por linha desconhecida ----------
    rows = []
    for i in idx_unknown:
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
    df_diag = pd.DataFrame(rows).sort_values(["marcar_sem_transtorno","top1_prob"], ascending=[False, True])

    # ---------- Atualizar TDados_clean em posição ----------
    df_clean_update = df_all.copy()
    n_mark = int(to_sem_transtorno.sum())
    df_clean_update.loc[to_sem_transtorno, COL_ALVO] = "Sem Transtorno"

    # ---------- Stats ----------
    used_source = "Pontuação_Tunada" if fonte_w == ABA_PONTOS_TUN else "Pontuação"
    df_stats = pd.DataFrame([
        {"metrica":"modo",                         "valor": mode_used},
        {"metrica":"nota_modo",                   "valor": note},
        {"metrica":"n_desconhecidos",             "valor": n_unknown},
        {"metrica":"marcadas_para_Sem_Transtorno", "valor": n_mark},
        {"metrica":"cobertura_marcada",           "valor": (n_mark / n_unknown) if n_unknown>0 else 0.0},
        {"metrica":"T1_usado",                    "valor": float(T1_eff)},
        {"metrica":"T2_usado",                    "valor": float(T2_eff)},
        {"metrica":"TAU_SOFTMAX",                 "valor": float(TAU_SOFTMAX)},
        {"metrica":"fonte_W",                     "valor": used_source},
        {"metrica":"base_features",               "valor": base_sheet},
    ])

    # ---------- Salvar ----------
    saved = save_preserving_sheets(
        ARQUIVO,
        [
            (df_clean_update, ABA_DADOS_CLEAN),
            (df_diag,         ABA_DIAG),
            (df_stats,        ABA_STATS),
        ]
    )
    print(f"[INFO] modo={mode_used} note={note} T1={T1_eff:.3f} T2={T2_eff:.3f} TAU={TAU_SOFTMAX:.2f}")
    print("✅ Abas criadas/atualizadas:", ABA_DADOS_CLEAN, ABA_DIAG, ABA_STATS)
    print("💾 Arquivo salvo em:", saved)

if __name__ == "__main__":
    main()
