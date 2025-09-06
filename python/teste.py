# -*- coding: utf-8 -*-
import os, shutil, tempfile
from datetime import datetime
import numpy as np
import pandas as pd

# ================== CONFIG ==================
ARQUIVO = r"c:\SourceCode\qip\python\banco_dados.xlsx"
ABA_DADOS = "TDados"
ABA_PONTOS = "Pontuação"
LINHA_INICIO_PONTOS = 3   # linhas 3..13 em "Pontuação"
COLUNA_TAM = 11           # número de classes
NORMAL_LABEL = "Sem Transtorno"

ABA_SAIDA_LINHAS   = "Linhas_SemRotulo"           # novas abas de diagnóstico
ABA_SAIDA_TOKENS   = "Resumo_Tokens_Desconhecidos"
ABA_SAIDA_STATUS   = "Resumo_Status_Alvo"
# ============================================

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
        with pd.ExcelWriter(tmpfile, engine="openpyxl", mode="w"):
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
    s = (s
         .replace("ã","a").replace("á","a").replace("â","a")
         .replace("é","e").replace("ê","e")
         .replace("í","i").replace("î","i")
         .replace("ó","o").replace("ô","o")
         .replace("ú","u").replace("û","u")
    )
    return s

def parse_multilabel_like_pipeline(series, class_names, normal_label=NORMAL_LABEL):
    """
    Replica a lógica do seu script atual:
    - divide Alvo por | ; , (sem normalização de classe, só mapeia 'não/nao' -> normal_label)
    - mantém o rótulo ORIGINAL apenas se for exatamente igual a alguma classe conhecida
    - ignora tokens desconhecidos
    Retorna: lista de listas (rótulos reconhecidos por linha) e lista de tokens por linha.
    """
    KNOWN = set(class_names) | {normal_label}
    DELIMS = ["|",";",","]
    rec_labels = []
    rec_tokens = []
    for val in series.astype(str).tolist():
        s = val
        for d in DELIMS:
            s = s.replace(d, "|")
        parts = [p.strip() for p in s.split("|") if p.strip()]
        labs = []
        toks = []
        for raw in parts:
            toks.append(raw)
            tok_norm = normalize_token(raw)
            if tok_norm == "nao":          # 'não'/'nao' -> normal
                labs.append(normal_label)
            else:
                # Mantém o ORIGINAL se for exatamente igual a alguma classe conhecida
                if raw in KNOWN:
                    labs.append(raw)
        rec_labels.append(labs)
        rec_tokens.append(toks)
    return rec_labels, rec_tokens

def main():
    # Ler dados
    df_dados = pd.read_excel(ARQUIVO, sheet_name=ABA_DADOS)
    df_pont  = pd.read_excel(ARQUIVO, sheet_name=ABA_PONTOS)

    # Classes na "Pontuação" (linhas 3..13)
    r0 = LINHA_INICIO_PONTOS - 2  # pandas index
    linhas_modelos = df_pont.index[r0 : r0 + COLUNA_TAM]
    if len(linhas_modelos) != COLUNA_TAM:
        raise ValueError(f"Aba 'Pontuação' não tem {COLUNA_TAM} linhas a partir da linha {LINHA_INICIO_PONTOS}.")

    if "Tipo de Transtorno" in df_pont.columns:
        class_names = df_pont.loc[linhas_modelos, "Tipo de Transtorno"].astype(str).tolist()
    else:
        class_names = [f"Classe_{i+1}" for i in range(COLUNA_TAM)]

    # Identificar linhas reconhecidas vs não reconhecidas (REPLICA a lógica do treino antigo)
    alvo_col = "Alvo"
    if alvo_col not in df_dados.columns:
        raise ValueError("Coluna 'Alvo' não encontrada em TDados.")

    y_lists_all, tokens_all = parse_multilabel_like_pipeline(df_dados[alvo_col], class_names, normal_label=NORMAL_LABEL)

    has_any_label = np.array([len(l)>0 for l in y_lists_all], dtype=bool)  # tem alguma classe reconhecida (clinica ou 'Sem Transtorno')
    # Para referência: linhas usadas no treino (apenas classes clínicas, não 'Sem Transtorno' puro)
    has_clinical = np.array([any(lbl in class_names for lbl in labs) for labs in y_lists_all], dtype=bool)

    n_total = len(df_dados)
    n_any   = int(has_any_label.sum())
    n_none  = int((~has_any_label).sum())
    n_clin  = int(has_clinical.sum())

    print(f"[INFO] TDados total: {n_total}")
    print(f"[INFO] Linhas com ALGUM rótulo reconhecido (clinico ou '{NORMAL_LABEL}'): {n_any}")
    print(f"[INFO] Linhas SEM rótulo reconhecido (causaram a diferença): {n_none}")
    print(f"[INFO] Linhas com rótulo clínico (usáveis no treino): {n_clin}")

    # ---- montar DataFrame de linhas sem rótulo reconhecido
    id_col = df_dados.columns[0]
    idx_unk = np.where(~has_any_label)[0]
    def classify_motivo(alvo_raw: str) -> str:
        s = str(alvo_raw).strip()
        if s == "" or s.lower() in {"nan","none"}:
            return "Alvo vazio"
        # Ver se contém 'não/nao' escrito de forma irreconhecível (ex.: com espaços ou variações)
        s_norm = normalize_token(s)
        if "nao" in [normalize_token(p) for p in s.replace("|",";").replace(",",";").split(";")]:
            return "Contém 'não/nao' mas não isolado"
        return "Texto não mapeado a classes"

    linhas_sem_rotulo = []
    for i in idx_unk:
        alvo_raw = df_dados.loc[i, alvo_col]
        tokens = tokens_all[i]
        linhas_sem_rotulo.append({
            "idx0": i,
            "linha_excel": i + 2,      # 1 = cabeçalho; dados começam na 2
            "ID": df_dados.loc[i, id_col],
            "Alvo": alvo_raw,
            "tokens_extraidos": " | ".join(tokens) if tokens else "",
            "motivo": classify_motivo(alvo_raw),
        })
    df_sem = pd.DataFrame(linhas_sem_rotulo)

    # ---- resumo de tokens desconhecidos (contagem dos pedaços que NÃO viraram rótulo)
    KNOWN = set(class_names) | {NORMAL_LABEL}
    desconhecidos = []
    for toks, labs in zip(tokens_all, y_lists_all):
        # refaz mapeamento "rápido" para ver quem ficou de fora
        labs_set = set(labs)
        for raw in toks:
            tok_norm = normalize_token(raw)
            if tok_norm == "nao":
                mapped = NORMAL_LABEL
            else:
                mapped = raw if raw in KNOWN else None
            if mapped is None:
                desconhecidos.append(raw.strip())
    if len(desconhecidos) == 0:
        df_tokens = pd.DataFrame({"token_desconhecido": [], "freq": []})
    else:
        vc = pd.Series(desconhecidos).value_counts()
        df_tokens = vc.rename_axis("token_desconhecido").reset_index(name="freq")

    # ---- resumo de status (contagens)
    df_status = pd.DataFrame([
        {"chave": "total_linhas_TDados", "valor": n_total},
        {"chave": "linhas_com_algum_rotulo_reconhecido", "valor": n_any},
        {"chave": "linhas_sem_rotulo_reconhecido", "valor": n_none},
        {"chave": "linhas_com_rotulo_clinico_para_treino", "valor": n_clin},
    ])

    saved = save_preserving_sheets(
        ARQUIVO,
        [
            (df_sem,    ABA_SAIDA_LINHAS),
            (df_tokens, ABA_SAIDA_TOKENS),
            (df_status, ABA_SAIDA_STATUS),
        ]
    )
    print(f"✅ Abas criadas/atualizadas: {ABA_SAIDA_LINHAS} {ABA_SAIDA_TOKENS} {ABA_SAIDA_STATUS}")
    print(f"💾 Arquivo salvo em: {saved}")

if __name__ == "__main__":
    main()
