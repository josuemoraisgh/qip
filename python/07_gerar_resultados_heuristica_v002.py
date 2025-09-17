# -*- coding: utf-8 -*-
# 07_gerar_resultados_heuristica.py
# Inferência (sem treino) usando pesos da aba Pontuação_Tunada (ou Pontuação),
# alinhando ESTRITAMENTE as colunas entre as abas.
#
# Uso:
#   python 07_gerar_resultados_heuristica.py --input caminho\banco.xlsx --output caminho\saida.xlsx
#
import os
import argparse
import json
from datetime import datetime
import numpy as np
import pandas as pd

def softmax_rows(mat, axis=1, eps=1e-12):
    x = mat - np.max(mat, axis=axis, keepdims=True)
    e = np.exp(x)
    return e / (np.sum(e, axis=axis, keepdims=True) + eps)

def normalize_token(s: str) -> str:
    s = (s or "").strip().lower()
    return (s.replace("ã","a").replace("á","a").replace("â","a")
             .replace("é","e").replace("ê","e")
             .replace("í","i")
             .replace("ó","o").replace("ô","o")
             .replace("ú","u"))

def parse_multilabel(series, core_classes):
    CORE = set(core_classes)
    DELIMS = ["|",";",","]
    out = []
    for val in series.astype(str).tolist():
        s = val
        for d in DELIMS: s = s.replace(d,"|")
        labs_raw = [p.strip() for p in s.split("|") if p.strip()]
        labs = []
        for lab in labs_raw:
            tok = normalize_token(lab)
            if tok in ("nao","não","desconhecido"):
                continue
            if lab in CORE:
                labs.append(lab)
        out.append(labs)
    return out

def main():
    p = argparse.ArgumentParser(description="Gera Resultado_Heuristica_Tunada e Resultado (inferência softmax, colunas alinhadas).")
    p.add_argument("--input", default=r"c:\\SourceCode\\qip\\saida_modelo\\banco_dados_vt_full.xlsx", help="Caminho do .xlsx de entrada (com TDados e Pontuação/_Tunada).")
    p.add_argument("--output", default=None, help="Arquivo de saída (por padrão, sobrescreve o input).")
    p.add_argument("--sheet-dados", default="DATA_UNUSED")
    p.add_argument("--sheet-pontos", default="Pontuação")
    p.add_argument("--sheet-pontos-tunada", default="Pontuação_Tunada")
    p.add_argument("--sheet-res-tun", default="Resultado_Heuristica_Tunada")
    p.add_argument("--sheet-res-all", default="Resultado")
    p.add_argument("--linha-inicio-pontos", type=int, default=3)
    p.add_argument("--col-alvo", default="Alvo")
    p.add_argument("--prefer-tunada", action="store_true", default=True)
    p.add_argument("--detect-classes", action="store_true", default=True)
    args = p.parse_args()

    INPUT = args.input
    OUTPUT = args.output or INPUT
    ABA_DADOS = args.sheet_dados
    ABA_PONTOS = args.sheet_pontos
    ABA_PONTOS_TUNADA = args.sheet_pontos_tunada
    ABA_RES_TUN = args.sheet_res_tun
    ABA_RES_ALL = args.sheet_res_all
    LINHA0 = args.linha_inicio_pontos
    COL_ALVO = args.col_alvo

    xl = pd.ExcelFile(INPUT)
    use_tunada = args.prefer_tunada and (ABA_PONTOS_TUNADA in xl.sheet_names)
    aba_pontos_usada = ABA_PONTOS_TUNADA if use_tunada else ABA_PONTOS

    # --- Leitura das abas ---
    df_dados_full = pd.read_excel(INPUT, sheet_name=ABA_DADOS)
    df_pont = pd.read_excel(INPUT, sheet_name=aba_pontos_usada)

    # Features candidatas em TDados: a partir da coluna B
    cols_tdados = df_dados_full.columns[1:]

    # Interseção ESTRITA das colunas entre Pontuação e TDados (ordem = TDados)
    cols_comuns = [c for c in cols_tdados if c in df_pont.columns]
    if len(cols_comuns) == 0:
        raise ValueError(f"Nenhuma coluna em comum entre '{ABA_DADOS}' e '{aba_pontos_usada}'.")

    # --- Detecta dinamicamente o número de classes (K) ---
    r0 = LINHA0 - 2
    df_feat_block = df_pont[cols_comuns].apply(pd.to_numeric, errors="coerce")

    def linha_vazia(idx):
        if idx not in df_feat_block.index:
            return True
        row = df_feat_block.loc[idx]
        all_nan_or_zero = bool(((row.isna()) | (np.isclose(row.fillna(0.0), 0.0))).all())
        if "Tipo de Transtorno" in df_pont.columns:
            nome_ok = isinstance(df_pont.at[idx, "Tipo de Transtorno"], str) and df_pont.at[idx, "Tipo de Transtorno"].strip() != ""
        else:
            nome_ok = True
        return all_nan_or_zero and (not nome_ok)

    indices = []
    i = r0
    while i in df_pont.index:
        if args.detect_classes and linha_vazia(i):
            break
        indices.append(i)
        i += 1
    if not indices:
        raise ValueError(f"Não encontrei linhas de classes a partir da linha {LINHA0} em '{aba_pontos_usada}'.")
    linhas_modelos = df_pont.index.intersection(indices)
    K = len(linhas_modelos)

    # --- Matriz de pesos W (apenas colunas comuns) ---
    W_block = df_pont.loc[linhas_modelos, cols_comuns]
    W0_sheet = W_block.apply(pd.to_numeric, errors="coerce").fillna(0.0).values.T  # (m_features x K)

    # --- Classes ---
    if "Tipo de Transtorno" in df_pont.columns:
        class_core = df_pont.loc[linhas_modelos, "Tipo de Transtorno"].astype(str).tolist()
    else:
        class_core = [f"Classe_{j+1}" for j in range(K)]

    # --- Monta X apenas com colunas comuns (ordem igual à de W0_sheet) ---
    # Garantimos a MESMA ordem de cols_comuns tanto em W quanto em X.
    X_all_full = df_dados_full[cols_comuns].apply(pd.to_numeric, errors="coerce").fillna(0.0).values
    X_all_full = np.clip(np.nan_to_num(X_all_full, nan=0.0, neginf=0.0, posinf=1.0), 0.0, 1.0)

    # --- Filtragem para Resultado_Heuristica_Tunada (linhas com algum rótulo do core) ---
    if COL_ALVO in df_dados_full.columns:
        y_lists_all = parse_multilabel(df_dados_full[COL_ALVO], class_core)
        keep_nonempty = [len(l)>0 for l in y_lists_all]
    else:
        y_lists_all = [[] for _ in range(len(df_dados_full))]
        keep_nonempty = [True]*len(df_dados_full)

    df_dados_filtrado = df_dados_full.loc[keep_nonempty].reset_index(drop=True)
    X_all = X_all_full[keep_nonempty]

    # ---------- "Regra de ouro": elimina features com todos os pesos==0 ----------
    mask_feat_all_zero = np.all(np.isclose(W0_sheet, 0.0, atol=1e-12), axis=1)
    keep_feat = ~mask_feat_all_zero

    W_eff = W0_sheet[keep_feat, :]
    # clip para estabilidade apenas onde não é zero
    W_eff = np.where(W_eff != 0.0, np.clip(W_eff, 1e-6, 1.0), 0.0)

    X_keep_full = X_all_full[:, keep_feat]
    X_keep = X_all[:, keep_feat]

    # ---------- Forward (sem bias) ----------
    def forward_no_bias(W, X):
        Z = X @ W
        return softmax_rows(Z)

    P_filtrado = forward_no_bias(W_eff, X_keep)      # Resultado_Heuristica_Tunada
    P_full     = forward_no_bias(W_eff, X_keep_full) # Resultado

    # ---------- Monta Resultado_Heuristica_Tunada ----------
    df_res = df_dados_filtrado[[df_dados_filtrado.columns[0]]].copy()
    if COL_ALVO in df_dados_filtrado.columns:
        df_res[COL_ALVO] = df_dados_filtrado[COL_ALVO]
    for j, name in enumerate(class_core):
        df_res[f"p_{name}"] = P_filtrado[:, j]
    order_all = np.argsort(-P_filtrado, axis=1)
    tops_rec = []
    for i in range(P_filtrado.shape[0]):
        rec = {}
        for t in range(min(3, P_filtrado.shape[1])):
            c = order_all[i, t]
            rec[f"top{t+1}_classe"] = class_core[c]
            rec[f"top{t+1}_prob"]   = float(P_filtrado[i, c])
        tops_rec.append(rec)
    df_res = pd.concat([df_res, pd.DataFrame(tops_rec)], axis=1)

    # ---------- Monta Resultado (todas as linhas) ----------
    df_resultado = df_dados_full[[df_dados_full.columns[0]]].copy()
    if COL_ALVO in df_dados_full.columns:
        df_resultado[COL_ALVO] = df_dados_full[COL_ALVO]
    for j, name in enumerate(class_core):
        df_resultado[f"p_{name}"] = P_full[:, j]
    order_full = np.argsort(-P_full, axis=1)
    tops_full = []
    for i in range(P_full.shape[0]):
        rec = {}
        for t in range(min(3, P_full.shape[1])):
            c = order_full[i, t]
            rec[f"top{t+1}_classe"] = class_core[c]
            rec[f"top{t+1}_prob"]   = float(P_full[i, c])
        tops_full.append(rec)
    df_resultado = pd.concat([df_resultado, pd.DataFrame(tops_full)], axis=1)

    # ---------- Grava no arquivo ----------
    saved_path = OUTPUT
    try:
        with pd.ExcelWriter(OUTPUT, engine="openpyxl", mode=("a" if os.path.exists(OUTPUT) else "w"),
                            if_sheet_exists="replace") as w:
            df_res.to_excel(w, sheet_name=ABA_RES_TUN, index=False)
            df_resultado.to_excel(w, sheet_name=ABA_RES_ALL, index=False)
    except PermissionError:
        carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
        alt = OUTPUT.replace(".xlsx", f"_{carimbo}.xlsx")
        with pd.ExcelWriter(alt, engine="openpyxl", mode="w") as w:
            df_res.to_excel(w, sheet_name=ABA_RES_TUN, index=False)
            df_resultado.to_excel(w, sheet_name=ABA_RES_ALL, index=False)
        saved_path = alt

    meta = {
        "used_sheet_pontos": aba_pontos_usada,
        "detected_classes": int(K),
        "features_in_common": len(cols_comuns),
        "dropped_zero_weight_features": int(np.sum(mask_feat_all_zero)),
        "resultado_tunada_rows": int(df_res.shape[0]),
        "resultado_all_rows": int(df_resultado.shape[0]),
    }
    print("✅ Abas geradas:", ABA_RES_TUN, ABA_RES_ALL)
    print("💾 Arquivo salvo em:", saved_path)
    print("__META__=" + json.dumps(meta, ensure_ascii=False))

if __name__ == "__main__":
    main()
