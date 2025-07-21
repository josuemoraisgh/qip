import openpyxl

arquivo = './python/banco_dados.xlsx'
colunas = ['AR', 'BX', 'BY']  # Altere para as colunas desejadas (pode adicionar mais)
sheet_name = 'BDados'

wb = openpyxl.load_workbook(arquivo)
ws = wb[sheet_name]

for coluna in colunas:
    col_idx = openpyxl.utils.column_index_from_string(coluna)
    for row in ws.iter_rows(
        min_row=2,
        min_col=col_idx,
        max_col=col_idx
    ):
        celula = row[0]
        if celula.value and isinstance(celula.value, str) and ';' in celula.value:
            valor = celula.value

            # Agora troca os ; (exceto o primeiro) por | da coluna selecionada
            partes = valor.split(';', 1)
            if len(partes) > 1:
                partes[1] = partes[1].replace(';', '|')
                valor = partes[0] + ';' + partes[1]

            celula.value = valor

wb.save(arquivo)
print("Arquivo salvo com sucesso!")

