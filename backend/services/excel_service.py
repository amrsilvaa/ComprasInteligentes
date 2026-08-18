import io
from typing import List, Dict, Any
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side


def gerar_excel_validades(produtos: List[Dict[str, Any]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Consulta Validades"

    # Cabeçalhos do relatório
    headers = [
        "Código", "EAN", "Complemento", "Descrição", "Separador",
        "Estoque_Sistema", "Reservado", "Disponível_Sistema", "Total_Coletado", "Divergência",
        "Qtd_1", "Data_1", "Qtd_2", "Data_2", "Qtd_3", "Data_3"
    ]
    ws.append(headers)

    # Definição de Cores
    fill_header = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")  # Azul Escuro
    font_header = Font(color="FFFFFF", bold=True, size=11)

    fill_coleta1 = PatternFill(start_color="D9EAD3", end_color="D9EAD3", fill_type="solid")  # Verde Claro
    fill_coleta2 = PatternFill(start_color="C9DAF8", end_color="C9DAF8", fill_type="solid")  # Azul Claro
    fill_coleta3 = PatternFill(start_color="FCE5CD", end_color="FCE5CD", fill_type="solid")  # Laranja Claro

    font_bold = Font(bold=True)
    font_divergencia = Font(bold=True, color="9C0006")
    fill_divergencia = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

    thin_border = Side(style='thin', color='D9D9D9')
    border = Border(left=thin_border, right=thin_border, top=thin_border, bottom=thin_border)

    # Estiliza o cabeçalho
    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = fill_header
        cell.font = font_header
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Preenche as linhas de dados
    for row_idx, p in enumerate(produtos, start=2):
        coletas = p.get("coletas", [])
        
        qtd_1 = coletas[0].get("qtd", "") if len(coletas) > 0 else p.get("qtd_1", "")
        data_1 = coletas[0].get("data", "") if len(coletas) > 0 else p.get("data_1", "")
        
        qtd_2 = coletas[1].get("qtd", "") if len(coletas) > 1 else p.get("qtd_2", "")
        data_2 = coletas[1].get("data", "") if len(coletas) > 1 else p.get("data_2", "")

        qtd_3 = coletas[2].get("qtd", "") if len(coletas) > 2 else p.get("qtd_3", "")
        data_3 = coletas[2].get("data", "") if len(coletas) > 2 else p.get("data_3", "")

        estoque_sistema = float(p.get("estoque", 0.0))
        reservado = float(p.get("reservado", 0.0))
        disponivel_sistema = float(p.get("disponivel", estoque_sistema - reservado))

        # Soma apenas valores coletados válidos
        coletados_list = []
        for q in [qtd_1, qtd_2, qtd_3]:
            try:
                if q is not None and str(q).strip() != "":
                    coletados_list.append(float(str(q).replace(',', '.')))
            except ValueError:
                pass

        total_coletado = sum(coletados_list)
        
        # Divergência Real: Contagem Física vs Estoque Total no Sistema
        divergencia = total_coletado - estoque_sistema

        ean_val = str(p.get("ean", "")).strip()

        linha_dados = [
            p.get("cod", ""),
            ean_val,
            p.get("complemento", ""),
            p.get("desc", ""),
            p.get("separador", ""),
            estoque_sistema,
            reservado,
            disponivel_sistema,
            total_coletado,
            divergencia,
            qtd_1, data_1,
            qtd_2, data_2,
            qtd_3, data_3
        ]

        ws.append(linha_dados)

        # Força o campo EAN como Texto puro no Excel para evitar notação científica (7,89808E+12)
        cell_ean = ws.cell(row=row_idx, column=2)
        cell_ean.data_type = 's'
        cell_ean.number_format = '@'

        # Aplica cores distintas e negrito nas colunas de coleta
        for col_i in [11, 12]:  # Qtd_1, Data_1
            c = ws.cell(row=row_idx, column=col_i)
            c.fill = fill_coleta1
            c.font = font_bold

        for col_i in [13, 14]:  # Qtd_2, Data_2
            c = ws.cell(row=row_idx, column=col_i)
            c.fill = fill_coleta2
            c.font = font_bold

        for col_i in [15, 16]:  # Qtd_3, Data_3
            c = ws.cell(row=row_idx, column=col_i)
            c.fill = fill_coleta3
            c.font = font_bold

        # Destaque em vermelho caso exista divergência física real
        cell_div = ws.cell(row=row_idx, column=10)
        if divergencia != 0:
            cell_div.fill = fill_divergencia
            cell_div.font = font_divergencia

        # Aplicação de bordas
        for col_num in range(1, len(headers) + 1):
            ws.cell(row=row_idx, column=col_num).border = border

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()