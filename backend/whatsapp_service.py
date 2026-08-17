import os
import requests

# Número configurado para receber os alertas de compras
WHATSAPP_DESTINATARIO = os.getenv("WHATSAPP_DESTINATARIO", "5533999317139")

# URL da sua API de WhatsApp (Z-API, Evolution API, etc.)
WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL", "https://api.z-api.io/instances/SUA_INSTANCIA/token/SEU_TOKEN/send-text")

def enviar_alerta_compras(produtos_repor):
    """
    Monta uma mensagem formatada e envia o resumo de compras no WhatsApp.
    """
    if not produtos_repor:
        return {"sucesso": False, "mensagem": "Nenhum produto com necessidade de reposição no momento."}

    total_itens = len(produtos_repor)
    custo_total = sum(
        float(p.get("sugestao_compra", 0)) * float(p.get("custo_un", p.get("custo", 0))) 
        for p in produtos_repor
    )

    # Montagem do texto do alerta
    mensagem = f"🚨 *ALERTA DE COMPRAS INTELIGENTES* 🚨\n\n"
    mensagem += f"Atenção! Identificados *{total_itens} itens* no ponto de reposição.\n"
    mensagem += f"💰 *Estimativa Total de Investimento:* R$ {custo_total:,.2f}\n\n"
    mensagem += "*Resumo dos itens principais:*\n"

    # Lista os 10 primeiros produtos
    for p in produtos_repor[:10]:
        cod = p.get("codigo") or p.get("codprod", "-")
        desc = p.get("descricao") or p.get("produto", "-")
        sug = p.get("sugestao_compra", 0)
        mensagem += f"• [{cod}] {desc} -> *Comprar: {sug}*\n"

    if total_itens > 10:
        mensagem += f"\n... e mais {total_itens - 10} produtos na lista."

    mensagem += "\n\n📊 Acesse o painel para visualizar/exportar a planilha completa!"

    payload = {
        "phone": WHATSAPP_DESTINATARIO,
        "message": mensagem
    }

    try:
        response = requests.post(WHATSAPP_API_URL, json=payload, timeout=10)
        return {"sucesso": response.status_code == 200, "status": response.status_code}
    except Exception as e:
        return {"sucesso": False, "erro": str(e)}