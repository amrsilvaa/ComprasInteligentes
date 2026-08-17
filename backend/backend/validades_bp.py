import os
import io
import logging
import requests
import pandas as pd
from flask import Blueprint, request, jsonify, send_file, current_app
from backend.services.sankhya_service import buscar_dados_estoque_vendas

logger = logging.getLogger(__name__)

# Criação do Blueprint de Validades com o prefixo /api/validades
validades_bp = Blueprint("validades", __name__, url_prefix="/api/validades")


@validades_bp.route("/produtos", methods=["GET"])
def listar_produtos_validades():
    """
    Retorna a lista de produtos do Sankhya para a tela de Coleta de Validades.
    """
    try:
        dados = buscar_dados_estoque_vendas()
        return jsonify({"sucesso": True, "produtos": dados})
    except Exception as e:
        logger.error(f"Erro ao carregar produtos para validades: {e}")
        return jsonify({"sucesso": False, "erro": str(e)}), 500


@validades_bp.route("/exportar-excel", methods=["POST"])
def exportar_validades_excel():
    """
    Recebe os dados coletados com múltiplos lotes e gera a planilha Excel.
    """
    try:
        dados = request.json or []
        linhas = []

        for p in dados:
            cod = p.get("cod", "")
            desc = p.get("desc", "")
            ean = p.get("ean", "")
            for lote in p.get("lotes", []):
                qtd = lote.get("qtd")
                validade = lote.get("validade")
                if qtd or validade:
                    linhas.append({
                        "Código": cod,
                        "EAN": ean,
                        "Descrição do Produto": desc,
                        "Quantidade Coletada": qtd,
                        "Data de Validade": validade
                    })

        if not linhas:
            return jsonify({"error": "Nenhum lote com quantidade/validade preenchida."}), 400

        df = pd.DataFrame(linhas)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Coleta_Validades", index=False)
        output.seek(0)

        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="coleta_validades.xlsx"
        )
    except Exception as e:
        logger.error(f"Erro ao exportar Excel de validades: {e}")
        return jsonify({"error": str(e)}), 500


@validades_bp.route("/enviar-whatsapp", methods=["POST"])
def enviar_validades_whatsapp():
    """
    Envia o resumo de validades diretamente para o WhatsApp.
    """
    try:
        dados = request.json or []
        total_lotes = 0
        total_itens = 0
        resumo_produtos = []

        for p in dados:
            cod = p.get("cod", "")
            desc = p.get("desc", "")
            lotes = [l for l in p.get("lotes", []) if l.get("validade") or l.get("qtd")]

            if lotes:
                resumo_lotes_str = []
                for l in lotes:
                    qtd = l.get("qtd", 0) or 0
                    validade = l.get("validade", "S/D")
                    total_lotes += 1
                    try:
                        total_itens += int(qtd)
                    except ValueError:
                        pass
                    resumo_lotes_str.append(f"{qtd} un (Vence: {validade})")

                resumo_produtos.append(f"• [{cod}] {desc}\n   └ Lotes: {', '.join(resumo_lotes_str)}")

        if not resumo_produtos:
            return jsonify({"sucesso": False, "mensagem": "Nenhuma validade preenchida."})

        mensagem = f"📅 *RELATÓRIO DE COLETA DE VALIDADES* 📅\n\n"
        mensagem += f"✅ *Total de Lotes Mapeados:* {total_lotes}\n"
        mensagem += f"📦 *Total de Unidades Coletadas:* {total_itens}\n\n"
        mensagem += "*Resumo dos Produtos Coletados:*\n"
        mensagem += "\n".join(resumo_produtos[:15])

        if len(resumo_produtos) > 15:
            mensagem += f"\n\n... e mais {len(resumo_produtos) - 15} produtos na lista."

        api_url = os.getenv("WHATSAPP_API_URL")
        destinatario = os.getenv("WHATSAPP_DESTINATARIO", "5533999317139")

        payload = {"phone": destinatario, "message": mensagem}
        headers = {"Content-Type": "application/json"}
        client_token = os.getenv("WHATSAPP_CLIENT_TOKEN")
        if client_token:
            headers["Client-Token"] = client_token

        response = requests.post(api_url, json=payload, headers=headers, timeout=15)
        return jsonify({"sucesso": response.status_code in [200, 201], "status": response.status_code})

    except Exception as e:
        logger.error(f"Erro ao enviar WhatsApp de validades: {e}")
        return jsonify({"sucesso": False, "error": str(e)}), 500