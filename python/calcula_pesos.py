import pandas as pd

# ================== CONFIG ==================
ARQUIVO = r"c:\SourceCode\qip\python\banco_dados.xlsx"
ABA_DADOS = "TDados"
ABA_PONTOS = "Pontuação"
ABA_SAIDA = "Resultado"

COLUNA_TAM = 11           # número de modelos
LINHA_INICIO_PONTOS = 3   # começa na linha 3 do Excel, termina na 13
# ============================================

# 1) Ler planilhas
df_dados = pd.read_excel(ARQUIVO, sheet_name=ABA_DADOS)
df_pont  = pd.read_excel(ARQUIVO, sheet_name=ABA_PONTOS)

# 2) Matriz X: TDados da coluna B em diante (numérico)
cols_dados = df_dados.columns[1:]  # ignora a primeira (A)
if len(cols_dados) == 0:
    raise ValueError("TDados não possui colunas a partir da coluna B.")

X = (df_dados[cols_dados]
     .apply(pd.to_numeric, errors="coerce")
     .fillna(0.0)
     .values)  # (n, m)

n, m = X.shape
print(f"[INFO] TDados: {n} linhas x {m} colunas (B em diante)")
print(f"[INFO] Esperando {COLUNA_TAM} modelos nas linhas {LINHA_INICIO_PONTOS}..{LINHA_INICIO_PONTOS+COLUNA_TAM-1} de 'Pontuação'.")

# 3) Selecionar as K linhas (HORIZONTAL) na aba Pontuação
#    Excel linha 3 -> índice 1 no pandas (porque linha 1 é header; linha 2 vira índice 0)
r0 = LINHA_INICIO_PONTOS - 2  # <--- CORREÇÃO AQUI
linhas_modelos = df_pont.index[r0 : r0 + COLUNA_TAM]
if len(linhas_modelos) != COLUNA_TAM:
    raise ValueError(f"Aba 'Pontuação' não tem {COLUNA_TAM} linhas a partir da linha {LINHA_INICIO_PONTOS}.")

# Checar se todas colunas de TDados existem em Pontuação
faltantes = [c for c in cols_dados if c not in df_pont.columns]
if faltantes:
    raise ValueError(
        "Algumas colunas de TDados não existem na aba 'Pontuação': "
        f"{faltantes[:10]}{'...' if len(faltantes) > 10 else ''}"
    )

# 3.2) Bloco de pesos (K x m) nas MESMAS colunas de TDados
W_block = df_pont.loc[linhas_modelos, cols_dados]
W = (W_block.apply(pd.to_numeric, errors="coerce").fillna(0.0).values.T)  # -> (m, K)

if W.shape != (m, COLUNA_TAM):
    raise ValueError(f"Dimensão inesperada de W: {W.shape}, esperado ({m}, {COLUNA_TAM}).")

# 3.3) Nomes das K saídas
if "Tipo de Transtorno" in df_pont.columns:
    out_cols = df_pont.loc[linhas_modelos, "Tipo de Transtorno"].astype(str).tolist()
else:
    out_cols = [f"Resultado_{i+1}" for i in range(COLUNA_TAM)]

# 4) Cálculo: (n x m) @ (m x K) -> (n x K)
S = X @ W

# 5) Saída (preserva a coluna A como identificador)
df_saida = pd.DataFrame(S, columns=out_cols)
id_col = df_dados.columns[0]
df_saida.insert(0, id_col, df_dados[id_col])

# 6) Gravar
with pd.ExcelWriter(ARQUIVO, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
    df_saida.to_excel(writer, sheet_name=ABA_SAIDA, index=False)

print(f"✅ '{ABA_SAIDA}' criada/atualizada: {df_saida.shape[0]} linhas × {COLUNA_TAM} colunas.")