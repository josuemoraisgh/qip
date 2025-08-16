# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
from openpyxl import load_workbook
from pandas.api.types import is_numeric_dtype

# ============ PARÂMETROS ============
in_path   = './python/banco_dados.xlsx'                 # entrada
sheet_in  = "Resultado"                        # aba com os resultados
out_path  = './python/banco_dados.xlsx'     # saída (cópia com nova aba)
K         = 4                                  # <= número máximo de casos por linha (pode alterar)
strict_gt = True                               # True -> usa ">" (garante ≤ K); False -> usa ">=" (pode gerar > K em empates)
# ====================================

sheet_out = f"binario_max{K}"

# 1) Lê a aba
df = pd.read_excel(in_path, sheet_name=sheet_in)

# 2) Detecta colunas numéricas (transtornos)
#    Converte tudo para numérico (coerce) e mantém colunas com >=80% de números.
tmp = df.apply(pd.to_numeric, errors="coerce")
num_ratio = tmp.notna().mean()
numeric_cols = [c for c in df.columns if num_ratio.get(c, 0) >= 0.8]
if not numeric_cols:
    numeric_cols = [c for c in df.columns if is_numeric_dtype(df[c])]

if not numeric_cols:
    raise ValueError("Nenhuma coluna numérica de transtorno foi detectada.")

vals = tmp[numeric_cols].to_numpy(dtype=float)

# 3) (K+1)-ésimo maior da linha (ignorando NaN)
def kth_largest_or_neg_inf(row: np.ndarray, k: int):
    """
    Retorna o (k)-ésimo maior valor de 'row' (k=1 => maior, k=2 => 2º maior, ...),
    ignorando NaNs. Se a linha tiver menos de k valores válidos, retorna -inf
    para não restringir por essa linha.
    """
    row = row[~np.isnan(row)]
    if row.size < k:
        return -np.inf
    # np.partition com índice negativo: posição -k contém o k-ésimo maior
    return np.partition(row, -k)[-k]

k_plus_1 = K + 1
kplus1_per_row = np.apply_along_axis(kth_largest_or_neg_inf, 1, vals, k=k_plus_1)

# 4) Cutoff = máximo dos (K+1)-ésimos maiores ao longo de todas as linhas
#    (menor cutoff global que ainda garante ≤ K por linha com comparação estrita)
finite_mask = np.isfinite(kplus1_per_row)
cutoff = np.max(kplus1_per_row[finite_mask]) if np.any(finite_mask) else float("inf")

# 5) Binarização
if strict_gt:
    # garante ≤ K por linha, mesmo em empates
    binary_df = (tmp[numeric_cols] > cutoff).astype(int)
else:
    # pode gerar > K em caso de empates com o próprio cutoff
    binary_df = (tmp[numeric_cols] >= cutoff).astype(int)

# 6) Mantém colunas não numéricas no início (referência) e depois as binárias
non_numeric_cols = [c for c in df.columns if c not in numeric_cols]
combined = pd.concat([df[non_numeric_cols], binary_df], axis=1)

# 7) Checagem rápida
max_ones_per_row = int(binary_df.sum(axis=1).max()) if not binary_df.empty else 0

# 8) Salva uma CÓPIA do arquivo com a nova aba
wb = load_workbook(in_path)
wb.save(out_path)
with pd.ExcelWriter(out_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
    combined.to_excel(writer, index=False, sheet_name=sheet_out)

# 9) Prints informativos
comp = ">" if strict_gt else ">="
print(f"[OK] Colunas de transtornos ({len(numeric_cols)}): {numeric_cols}")
print(f"[OK] K = {K} (máximo de {K} casos por linha)")
print(f"[OK] Cutoff (baseado no (K+1)-ésimo maior por linha) = {cutoff:.6f}")
print(f"[OK] Binarização usando '{comp} cutoff'")
print(f"[OK] Máximo de 1s por linha: {max_ones_per_row} (esperado ≤ {K} com comparação estrita)")
print(f"[OK] Nova aba '{sheet_out}' criada em '{out_path}'")
