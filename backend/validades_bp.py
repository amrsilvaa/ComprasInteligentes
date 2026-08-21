from flask import Blueprint, jsonify, request, Response
from backend.services.excel_service import gerar_excel_validades
from backend.services.sankhya_service import buscar_dados_estoque_vendas

validades_bp = Blueprint('validades_bp', __name__)

@validades_bp.route('/api/validades', methods=['GET'])
def listar_validades():
    """
    Retorna os dados reais de produtos do Sankhya para a tela frontend.
    """
    try:
        produtos = buscar_dados_estoque_vendas() or []
        
        # Mapeia/normaliza as chaves para garantir integridade com o frontend
        normalizados = []
        for p in produtos:
            normalizados.append({
                "codigo": p.get("cod") or p.get("codigo") or "",
                "descricao": p.get("desc") or p.get("descricao") or "-",
                "ean": p.get("ean") or "",
                "complemento": p.get("complemento") or "",
                "separador": p.get("separador") or "-",
                "fornecedor": p.get("fornecedor") or p.get("fornecedor_nome") or "NÃO INFORMADO",
                "estoque": float(p.get("estoque") or p.get("estoque_sistema") or 0.0),
                "reservado": float(p.get("reservado") or p.get("separado") or 0.0),
                "disponivel": float(p.get("disponivel") or 0.0)
            })

        return jsonify({"status": "sucesso", "data": normalizados}), 200

    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@validades_bp.route('/api/validades/excel', methods=['POST', 'GET'])
def download_excel_validades():
    try:
        if request.method == 'POST' and request.is_json:
            dados = request.get_json()
            produtos = dados.get('produtos', [])
        else:
            produtos = buscar_dados_estoque_vendas() or []

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