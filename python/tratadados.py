import re
import numpy as np
import pandas as pd
import unicodedata
from sklearn.preprocessing import OneHotEncoder
from openpyxl import load_workbook
from openpyxl.comments import Comment

# Funções de conversão
def remover_acentos_e_transformar_minusculo(texto):
    # Transforma o texto em minúsculas
    texto = texto.lower()
    # Normaliza a string para remover acentos
    texto_sem_acentos = unicodedata.normalize('NFD', texto)
    texto_sem_acentos = texto_sem_acentos.encode('ascii', 'ignore').decode('utf-8')
    return texto_sem_acentos

def str_null(df: pd.DataFrame, column: str) -> pd.DataFrame:
    cols_tela = [col for col in df.columns if col.startswith(column) and col not in [f'{column}_part_1'] ]    
    for column_name in cols_tela:
        df[column_name] = df[column_name].apply(lambda x: 1 if isinstance(x, str) else 0)        
    return df

def yes_no(df: pd.DataFrame, column: str) -> pd.DataFrame:
    cols_tela = [col for col in df.columns if col.startswith(column) and col not in [f'{column}_part_1'] ]    
    for column_name in cols_tela:
        df[column_name] = df[column_name].map({'Não': 0, 'Sim': 1, ' Não': 0, ' Sim': 1}).astype('int')
    return df

# Função para:
#   * remover espaços vazios antes e depois do ; e do |
#   * Dividir as colunas que têm valores separados por ; e por |
def split_columns(df):    
    columns_to_drop = []
    for col in df.columns:
        if df[col].dtype == 'object':
            # Remove espaços antes e depois de ; ou | usando regex
            df[col] = df[col].str.replace(r'\s*([;|])\s*', r'\1', regex=True)
            # Verifica se a coluna contém ; ou | e divide
            # Se a coluna contém ; ou |, divide em várias colunas
            if df[col].str.contains(';|\|').any():
                split_df = df[col].str.split(r';|\|', expand=True)
                split_df.columns = [f'{col}_part_{i+1}' for i in range(split_df.shape[1])]
                df = pd.concat([df, split_df], axis=1)
                columns_to_drop.append(col)
    df = df.drop(columns=columns_to_drop)
    return df


if __name__ == '__main__':
    # Caminho para o arquivo xlsx local
    file_path = './banco_dados.xlsx'
    # Carregar o DataFrame
    df_inicial = pd.read_excel(file_path, sheet_name='BDados')
    # Realizando várias substituições em todas as colunas do DataFrame
    df_replace = df_inicial.replace({
        "other;": "",   # Remove "other;"
        "Sucess;": "",  # Remove "Sucess;"
        "Sucess": ""    # Remove "Sucess"
    }, regex=True)