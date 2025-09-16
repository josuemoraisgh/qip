# -*- coding: utf-8 -*-
"""
Transforma valores para [-1,1] com y = 2x - 1:
- Ignora colunas 100% zero (NaN conta como 0 para essa checagem)
- Nas demais colunas, substitui NaN por 0 e aplica a conta
- Só modifica as LINHAS 3 a 13 (1-based) — o restante permanece igual
- Resultado vai para a aba 'Pontuação_new_range' no MESMO arquivo

Requisitos:
    pip install pandas openpyxl numpy
"""

from pathlib import Path
import pandas as pd
import numpy as np

def transformar_pontuacao_no_mesmo_arquivo(
    caminho_arquivo: str | Path,
    aba_origem: str = "Pontuação",
    aba_destino: str = "Pontuação_new_range",
    linha_inicio: int = 3,
    linha_fim: int = 14,
) -> None:
    """
    linha_inicio e linha_fim são 1-based (a primeira linha é 1).
    A transformação é aplicada apenas entre essas linhas, inclusive.
    """
    caminho_arquivo = Path(caminho_arquivo)
    if not caminho_arquivo.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_arquivo}")

    # Lê a aba de origem
    df = pd.read_excel(caminho_arquivo, sheet_name=aba_origem)

    # Cópia de trabalho/saída
    df_out = df.copy()

    # Converte limites de linha para índices 0-based do pandas
    # iloc usa fim exclusivo, então usamos end = linha_fim (sem -1)
    start = max(linha_inicio-2, 0)
    end = min(linha_fim-1, len(df_out))

    if start >= end:
        raise ValueError(
            f"Intervalo de linhas inválido: {linha_inicio}..{linha_fim} "
            f"para {len(df_out)} linhas."
        )

    # Index slice (rótulos) correspondente ao recorte de linhas
    target_index = df_out.index[start:end]

    for col in df_out.columns:
        # Série numérica auxiliar para checagens/cálculo (sem alterar o original ainda)
        s_num = pd.to_numeric(df_out[col], errors="coerce")

        # Ignora colunas 100% zero (NaN tratados como 0)
        if s_num.fillna(0).eq(0).all():
            continue

        # Pega apenas o trecho de linhas solicitado
        sub = s_num.loc[target_index]

        # Substitui NaN por 0 apenas no trecho alvo
        sub = sub.fillna(0)

        # Aplica transformação no trecho alvo
        transformed = 2.0 * sub - 1.0

        # Escreve de volta SÓ nas linhas alvo, preservando o resto da coluna
        df_out.loc[target_index, col] = transformed

    # Grava no MESMO arquivo (mantém outras abas; substitui a de destino se existir)
    with pd.ExcelWriter(
        caminho_arquivo,
        engine="openpyxl",
        mode="a",
        if_sheet_exists="replace",  # pandas >= 1.4
    ) as writer:
        df_out.to_excel(writer, sheet_name=aba_destino, index=False)

    print(
        f"Aba '{aba_destino}' atualizada em: {caminho_arquivo} "
        f"(linhas {linha_inicio}..{linha_fim})"
    )


if __name__ == "__main__":
    # Exemplo de uso: aplica nas linhas 3..14
    transformar_pontuacao_no_mesmo_arquivo(r"C:\SourceCode\qip\python\banco_dados.xlsx")