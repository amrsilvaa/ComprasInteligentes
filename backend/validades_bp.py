from flask import Blueprint, render_template, jsonify, request
import logging

# Importação correta da função atualizada no serviço do Sankhya
from backend.services.sankhya_service import buscar_dados_estoque_vendas

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
        # Executa a consulta chamando o módulo correto que já possui a query interna
        registros = buscar_dados_estoque_vendas() or []

        produtos_formatados = []

        for row in registros:
            if not isinstance(row, dict):
                continue

            # Tratamento de campos vazios ou nulos (garantindo que exiba "-" no frontend)
            separador_val = str(row.get('separador') or '-').strip()
            if not separador_val or separador_val.upper() in ['NONE', 'NULL', '']:
                separador_val = '-'

            complemento_val = str(row.get('complemento') or '-').strip()
            if not complemento_val or complemento_val.upper() in ['NONE', 'NULL', '']:
                complemento_val = '-'
                
            ean_val = str(row.get('ean') or '-').strip()
            if not ean_val or ean_val.upper() in ['NONE', 'NULL', '']:
                ean_val = '-'

            # Montagem do objeto final com as chaves esperadas pelo JavaScript/HTML
            produtos_formatados.append({
                "codigo": str(row.get('codigo') or '0'),
                "ean": ean_val,
                "complemento": complemento_val,
                "descricao": str(row.get('descricao') or '').strip(),
                "separador": separador_val,
                "estoque": float(row.get('estoque') or 0.0),
                "reservado": float(row.get('reservado') or row.get('RESERVADO') or 0.0)
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