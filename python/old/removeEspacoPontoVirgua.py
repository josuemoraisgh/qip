import openpyxl

arquivo = './python/banco_dados.xlsx'
sheet_name = 'BDados'

wb = openpyxl.load_workbook(arquivo)
ws = wb[sheet_name]

for row in ws.iter_rows(min_row=2):  # Percorre todas as linhas (exceto o cabeçalho)
    for celula in row:  # Percorre todas as colunas da linha
        if celula.value and isinstance(celula.value, str) and ';' in celula.value:
            valor = celula.value
            idx = valor.find(';')
            if idx > 0 and valor[idx-1] == ' ':
                valor = valor[:idx-1] + valor[idx:]
            celula.value = valor

wb.save(arquivo)
print("Arquivo salvo com sucesso!")