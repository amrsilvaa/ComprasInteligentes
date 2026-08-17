from flask import Blueprint, render_template, jsonify, request
import logging

# Importação correta com base na sua pasta backend/services/
from backend.services.sankhya_service import executar_query

validades_bp = Blueprint('validades', __name__)

@validades_bp.route('/validades')
def pagina_validades():
    """Renderiza a página principal do módulo de validades."""
    return render_template('validades.html')


@validades_bp.route('/api/validades', methods=['GET'])
def get_validades():
    """
    Retorna a lista de produtos com Código, EAN, Complemento, Descrição, Separador e Estoque.
    """
    try:
        query = """
            SELECT 
                P.CODPROD AS codigo,
                COALESCE(P.INTEGRAPROD, P.EAN, '-') AS ean,
                COALESCE(CAST(P.COMPLEMENTO AS VARCHAR), '-') AS complemento,
                COALESCE(P.DESCRPROD, '-') AS descricao,
                COALESCE(P.AD_SEPARADOR, P.SEPARADOR, '-') AS separador,
                COALESCE(E.ESTOQUE, 0) AS estoque
            FROM TGFPRO P
            LEFT JOIN TGFEST E ON P.CODPROD = E.CODPROD
            WHERE P.ATIVO = 'S'
            ORDER BY P.DESCRPROD ASC
        """

        # Executa a consulta chamando o módulo correto
        registros = executar_query(query) or []

        produtos_formatados = []

        for row in registros:
            if not isinstance(row, dict):
                continue

            separador_val = str(row.get('separador') or row.get('AD_SEPARADOR') or '-').strip()
            if not separador_val or separador_val.upper() in ['NONE', 'NULL']:
                separador_val = '-'

            complemento_val = str(row.get('complemento') or row.get('COMPLEMENTO') or '-').strip()
            if not complemento_val or complemento_val.upper() in ['NONE', 'NULL']:
                complemento_val = '-'

            produtos_formatados.append({
                "codigo": str(row.get('codigo') or row.get('CODPROD') or '0'),
                "ean": str(row.get('ean') or row.get('INTEGRAPROD') or '-').strip(),
                "complemento": complemento_val,
                "descricao": str(row.get('descricao') or row.get('DESCRPROD') or '').strip(),
                "separador": separador_val,
                "estoque": float(row.get('estoque') or row.get('ESTOQUE') or 0)
            })

        return jsonify({
            "status": "success",
            "total": len(produtos_formatados),
            "data": produtos_formatados
        }), 200

    except Exception as e:
        logging.error(f"Erro ao buscar validades: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Erro ao carregar dados de validades.",
            "details": str(e)
        }), 500