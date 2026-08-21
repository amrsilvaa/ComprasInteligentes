from flask import Blueprint, jsonify, request, Response
from backend.services.excel_service import gerar_excel_validades

validades_bp = Blueprint('validades_bp', __name__)

# Exemplo de mock de dados ou integração com banco/ERP
# Substitua pela sua consulta real ao banco de dados se necessário
PRODUTOS_MOCK = [
    {
        "cod": "1001",
        "ean": "7898080000012",
        "complemento": "CX C/ 24",
        "desc": "PRODUTO EXEMPLO A",
        "separador": "JOAO",
        "fornecedor": "FORNECEDOR ALFA",
        "estoque": 100.0,
        "reservado": 10.0,
        "disponivel": 90.0,
        "coletas": [
            {"qtd": 50, "data": "2026-10-15"},
            {"qtd": 40, "data": "2026-12-01"}
        ]
    },
    {
        "cod": "1002",
        "ean": "7898080000029",
        "complemento": "UNIDADE",
        "desc": "PRODUTO EXEMPLO B",
        "separador": "MARIA",
        "fornecedor": "FORNECEDOR BETA",
        "estoque": 50.0,
        "reservado": 5.0,
        "disponivel": 45.0,
        "coletas": []
    }
]


@validades_bp.route('/api/validades', methods=['GET'])
def listar_validades():
    """
    Retorna a lista de produtos para a tela frontend (JSON).
    Suporta busca por termo ou separador.
    """
    try:
        busca = request.args.get('busca', '').lower().strip()
        separador = request.args.get('separador', '').strip()

        produtos_filtrados = PRODUTOS_MOCK

        if busca:
            produtos_filtrados = [
                p for p in produtos_filtrados
                if busca in str(p.get('cod', '')).lower()
                or busca in str(p.get('desc', '')).lower()
                or busca in str(p.get('fornecedor', '')).lower()
                or busca in str(p.get('ean', '')).lower()
            ]

        if separador:
            produtos_filtrados = [
                p for p in produtos_filtrados
                if p.get('separador') == separador
            ]

        return jsonify({"status": "sucesso", "data": produtos_filtrados}), 200

    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@validades_bp.route('/api/validades/excel', methods=['POST', 'GET'])
def download_excel_validades():
    """
    Gera e envia o arquivo Excel com 2 abas (Dados do Estoque e Coleta/Lotes).
    Aceita payload JSON no POST ou usa a lista completa no GET.
    """
    try:
        if request.method == 'POST' and request.is_json:
            dados = request.get_json()
            produtos = dados.get('produtos', PRODUTOS_MOCK)
        else:
            produtos = PRODUTOS_MOCK

        excel_bytes = gerar_excel_validades(produtos)

        return Response(
            excel_bytes,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=coleta_validades_completo.xlsx"
            }
        )
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500