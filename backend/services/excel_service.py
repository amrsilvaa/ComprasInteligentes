import io
from typing import List, Dict, Any
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side


def gerar_excel_validades(produtos: List[Dict[str, Any]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Consulta Validades"

    # Cabeçalhos
    headers = [
        "Código", "EAN", "Complemento", "Descrição", "Separador",
        "Estoque_Sistema", "Reservado", "Disponível_Sistema", "Total_Coletado", "Divergência",
        "Qtd_1", "Data_1", "Qtd_2", "Data_2", "Qtd_3", "Data_3"
    ]
    ws.append(headers)

    # Estilos de Cores para Cabeçalhos e Datas
    fill_header = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    font_header = Font(color="FFFFFF", bold=True)

    fill_coleta1 = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")  # Verde claro
    fill_coleta2 = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")  # Azul claro
    fill_coleta3 = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")  # Laranja claro

    font_data = Font(bold=True)
    thin_border = Side(style='thin', color='D9D9D9')
    border = Border(left=thin_border, right=thin_border, top=thin_border, bottom=thin_border)

    # Estiliza o cabeçalho
    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = fill_header
        cell.font = font_header
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Escreve as linhas de dados
    for row_idx, p in enumerate(produtos, start=2):
        coletas = p.get("coletas", [])
        
        qtd_1 = coletas[0].get("qtd", "") if len(coletas) > 0 else p.get("qtd_1", "")
        data_1 = coletas[0].get("data", "") if len(coletas) > 0 else p.get("data_1", "")
        
        qtd_2 = coletas[1].get("qtd", "") if len(coletas) > 1 else p.get("qtd_2", "")
        data_2 = coletas[1].get("data", "") if len(coletas) > 1 else p.get("data_2", "")

        qtd_3 = coletas[2].get("qtd", "") if len(coletas) > 2 else p.get("qtd_3", "")
        data_3 = coletas[2].get("data", "") if len(coletas) > 2 else p.get("data_3", "")

        estoque_total = p.get("estoque", 0.0)
        reservado = p.get("reservado", 0.0)
        disponivel = p.get("disponivel", estoque_total - reservado)

        # Cálculo do total coletado e divergência
        coletados_list = [float(q) for q in [qtd_1, qtd_2, qtd_3] if str(q).replace('.', '', 1).isdigit()]
        total_coletado = sum(coletados_list)
        divergencia = total_coletado - disponivel

        linha_dados = [
            p.get("cod", ""),
            str(p.get("ean", "")),
            p.get("complemento", ""),
            p.get("desc", ""),
            p.get("separador", ""),
            estoque_total,
            reservado,
            disponivel,
            total_coletado,
            divergencia,
            qtd_1, data_1,
            qtd_2, data_2,
            qtd_3, data_3
        ]

        ws.append(linha_dados)

        # Formatação das Células
        cell_ean = ws.cell(row=row_idx, column=2)
        cell_ean.number_format = '@'  # Força o Excel a tratar o EAN como Texto puro (impede 7,8949E+12)

        # Destaca Colunas de Coleta (Qtd_1, Data_1, Qtd_2, Data_2, Qtd_3, Data_3)
        ws.cell(row=row_idx, column=11).fill = fill_coleta1
        ws.cell(row=row_idx, column=12).fill = fill_coleta1
        ws.cell(row=row_idx, column=11).font = font_data
        ws.cell(row=row_idx, column=12).font = font_data

        ws.cell(row=row_idx, column=13).fill = fill_coleta2
        ws.cell(row=row_idx, column=14).fill = fill_coleta2
        ws.cell(row=row_idx, column=13).font = font_data
        ws.cell(row=row_idx, column=14).font = font_data

        ws.cell(row=row_idx, column=15).fill = fill_coleta3
        ws.cell(row=row_idx, column=16).fill = fill_coleta3
        ws.cell(row=row_idx, column=15).font = font_data
        ws.cell(row=row_idx, column=16).font = font_data

        # Bordas leves
        for col_num in range(1, len(headers) + 1):
            ws.cell(row=row_idx, column=col_num).border = border

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()