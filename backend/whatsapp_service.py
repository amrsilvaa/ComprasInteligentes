import os
import logging
import requests

logger = logging.getLogger(__name__)

# Número configurado para receber os alertas de compras
WHATSAPP_DESTINATARIO = os.getenv("WHATSAPP_DESTINATARIO", "5533999317139")

# URL da sua API de WhatsApp (Z-API, Evolution API, etc.)
WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL", "https://api.z-api.io/instances/SUA_INSTANCIA/token/SEU_TOKEN/send-text")


def enviar_alerta_compras(dados_produtos):
    """
    Filtra os produtos que precisam de reposição, monta uma mensagem formatada
    e envia o resumo de compras via WhatsApp.
    """
    if not dados_produtos:
        return {"sucesso": False, "mensagem": "Nenhum dado de produto recebido."}

    # 1. Filtra apenas os produtos com necessidade de reposição
    produtos_repor = []
    for p in dados_produtos:
        status = str(p.get("STATUS", p.get("status", ""))).upper()
        try:
            sugestao = float(p.get("SUGESTAO", p.get("sugestao_compra", p.get("SUGESTAO_COMPRA", 0))) or 0)
        except (ValueError, TypeError):
            sugestao = 0

        if status == "REPOR" or sugestao > 0:
            produtos_repor.append(p)

    if not produtos_repor:
        return {"sucesso": False, "mensagem": "Nenhum produto com necessidade de reposição no momento."}

    total_itens = len(produtos_repor)
    custo_total = 0.0

    # 2. Cálculo do investimento total previsto
    for p in produtos_repor:
        try:
            sug = float(p.get("SUGESTAO", p.get("sugestao_compra", p.get("SUGESTAO_COMPRA", 0))) or 0)
            custo = float(p.get("CUSTO", p.get("custo_un", p.get("custo", p.get("VLRUNIT", 0)))) or 0)
            custo_total += sug * custo
        except (ValueError, TypeError):
            continue

    # Formatação de moeda no padrão brasileiro (1.234,56)
    custo_formatado = f"{custo_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    # 3. Montagem da mensagem formatada para WhatsApp
    mensagem = f"🚨 *ALERTA DE COMPRAS INTELIGENTES* 🚨\n\n"
    mensagem += f"Atenção! Identificados *{total_itens} itens* no ponto de reposição.\n"
    mensagem += f"💰 *Estimativa Total de Investimento:* R$ {custo_formatado}\n\n"
    mensagem += "*Resumo dos itens principais:*\n"

    # Lista os 10 primeiros produtos
    for p in produtos_repor[:10]:
        cod = p.get("CODPROD") or p.get("codigo") or p.get("codprod", "-")
        desc = p.get("DESCRPROD") or p.get("descricao") or p.get("produto", "-")
        sug = p.get("SUGESTAO") or p.get("sugestao_compra") or p.get("SUGESTAO_COMPRA", 0)
        mensagem += f"• [{cod}] {desc} -> *Comprar: {sug}*\n"

    if total_itens > 10:
        mensagem += f"\n... e mais {total_itens - 10} produtos na lista."

    mensagem += "\n\n📊 Acesse o painel para visualizar/exportar a planilha completa!"

    payload = {
        "phone": WHATSAPP_DESTINATARIO,
        "message": mensagem
    }

    headers = {
        "Content-Type": "application/json"
    }

    # Adiciona Client-Token caso utilizado pelo Z-API
    client_token = os.getenv("WHATSAPP_CLIENT_TOKEN")
    if client_token:
        headers["Client-Token"] = client_token

    try:
        response = requests.post(WHATSAPP_API_URL, json=payload, headers=headers, timeout=15)
        res_data = {}
        try:
            res_data = response.json()
        except Exception:
            res_data = {"text": response.text}

        return {
            "sucesso": response.status_code in [200, 201],
            "status": response.status_code,
            "resposta": res_data
        }
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem via WhatsApp: {e}")
        return {"sucesso": False, "erro": str(e)}