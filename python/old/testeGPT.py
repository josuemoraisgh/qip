import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score

# 1. Ler o arquivo original
df = pd.read_excel('./python/banco_dados - Copia.xlsx')

# 2. Detectar colunas por instrumento usando palavras-chave
instr_mapping = {
    'Depressão': ('PHQ', 9, 27, 10),
    'Ansiedade': ('GAD', 7, 21, 10),
    'TDAH': ('ASRS', 6, 24, 14),
    'TEPT': ('PCL', 20, 80, 33),
    'Bipolar': ('MDQ', 13, 13, 7),
    'TOC': ('OCI', 18, 72, 21),
    'Alimentar': ('EAT', 26, 78, 20),
    'Alimentar_EDDS': ('EDDS', 22, 22*4, 16.5),
    'Borderline': ('MSI', 10, 10, 7),
    'Ciclotimia': ('DCS', 16, 16*4, None),
    'Psicótico': ('PQB', 21, 21, 7),
}

detected = {}
for name, (key, count, max_score, cutoff) in instr_mapping.items():
    cols = [c for c in df.columns if key in c]
    if len(cols) >= count:
        detected[name] = {'cols': cols[:count], 'max': max_score, 'cut': cutoff}
    else:
        print(f"[AVISO] Encontradas {len(cols)} colunas com '{key}' para o instrumento {name}. Esperado: {count}.")

# 3. Cálculo de escores, normalização e probabilidades
for name, info in detected.items():
    cols = info['cols']
    df[name + '_score'] = df[cols].sum(axis=1, skipna=True)
    df[name + '_norm'] = df[name + '_score'] / info['max']
    if info['cut']:
        df['Prob_' + name] = (df[name + '_score'] / info['cut']).clip(upper=1)
    else:
        df['Prob_' + name] = df[name + '_norm']

# 4. Montar string com todas as probabilidades
prob_cols = [c for c in df.columns if c.startswith('Prob_')]
df['Todas_Probabilidades'] = df[prob_cols].apply(
    lambda r: '; '.join([f"{c.replace('Prob_','')}: {r[c]:.2f}" for c in prob_cols]), axis=1)

# 5. Matriz de pesos (correlação absoluta entre resposta e probabilidade)
pesos = {}
all_question_cols = [c for info in detected.values() for c in info['cols']]
for q in all_question_cols:
    pesos[q] = {name: abs(df[q].corr(df['Prob_' + name])) for name in detected}
df_pesos = pd.DataFrame(pesos).T
df_pesos = df_pesos.div(df_pesos.max(axis=0), axis=1).fillna(0)

# 6. Validação estatística
df_valid = []
# Converter coluna de diagnóstico em múltiplas colunas binárias
dx = pd.get_dummies(df['Diagnóstico'], prefix='DX')
for name in detected:
    col_dx = 'DX_' + name
    if col_dx in dx:
        y_true = dx[col_dx]
        y_score = df['Prob_' + name]
        auc = roc_auc_score(y_true, y_score)
        y_pred = (y_score >= 0.5).astype(int)
        prec = precision_score(y_true, y_pred)
        rec = recall_score(y_true, y_pred)
        f1 = f1_score(y_true, y_pred)
        spec = recall_score(y_true, y_pred, pos_label=0)
        df_valid.append({
            'Transtorno': name,
            'Sensibilidade': rec,
            'Especificidade': spec,
            'Precisão': prec,
            'F1-Score': f1,
            'AUC': auc
        })
df_valid = pd.DataFrame(df_valid)

# 7. Documentação & log
log = [
    {'Etapa':'Leitura','Status':'OK', 'Detalhes':f"{len(df)} linhas importadas"},
    {'Etapa':'Mapeamento', 'Status':'OK', 'Detalhes':", ".join([f"{n}: {len(info['cols'])}" for n,info in detected.items()])},
    {'Etapa':'Cálculos', 'Status':'OK', 'Detalhes':'Scores e probabilidades geradas'},
    {'Etapa':'Pesos', 'Status':'OK', 'Detalhes':f"Matriz com {df_pesos.shape[0]} perguntas"},
    {'Etapa':'Validação', 'Status':'OK', 'Detalhes':f"{df_valid.shape[0]} transtornos avaliados"},
    {'Etapa':'Exportação','Status':'OK','Detalhes':'Arquivo gerado: resultado_analysis.xlsx'},
]
df_log = pd.DataFrame(log)

# 8. Exportar para Excel
with pd.ExcelWriter('resultado_analysis.xlsx', engine='openpyxl') as writer:
    df.to_excel(writer, sheet_name='Base+Probabilidades', index=False)
    df_pesos.to_excel(writer, sheet_name='Matriz de Pesos', index=True)
    df_valid.to_excel(writer, sheet_name='Validação', index=False)
    df_log.to_excel(writer, sheet_name='Metodologia & Log', index=False)

print("Análise concluída. Arquivo salvo como 'resultado_analysis.xlsx'")
