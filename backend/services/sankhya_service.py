import os
import requests
from dotenv import load_dotenv

load_dotenv()

SANKHYA_URL = os.getenv("SANKHYA_URL", "http://amorim.snk.ativy.com:40039/mge/")
SANKHYA_USUARIO = os.getenv("SANKHYA_USUARIO", "sup")
SANKHYA_SENHA = os.getenv("SANKHYA_SENHA", "@amor1m2026")


def autenticar_sankhya():
    """Realiza o login na API do Sankhya."""
    if not SANKHYA_URL:
        raise Exception("SANKHYA_URL não configurada.")

    url_base = SANKHYA_URL.rstrip("/")
    urls_para_testar = [
        f"{url_base}/service.sbr?serviceName=MobileLoginSP.login&outputType=json",
        f"{url_base[:-4]}/service.sbr?serviceName=MobileLoginSP.login&outputType=json" if url_base.endswith("/mge") else f"{url_base}/mge/service.sbr?serviceName=MobileLoginSP.login&outputType=json"
    ]

    payload = {
        "requestBody": {
            "NOMUSU": {"$": SANKHYA_USUARIO},
            "INTERNO": {"$": SANKHYA_SENHA}
        }
    }

    erros = []
    for url in urls_para_testar:
        try:
            response = requests.post(url, json=payload, timeout=15)
            data = response.json()
            if "responseBody" in data and "jsessionid" in data["responseBody"]:
                jsessionid = data["responseBody"]["jsessionid"]["$"]
                base_endpoint = url.rsplit("/service.sbr", 1)[0]
                return jsessionid, base_endpoint
            erros.append(f"[{url}]: {data.get('statusMessage') or str(data)}")
        except Exception as e:
            erros.append(f"[{url}]: {str(e)}")

    raise Exception(f"Falha de autenticação Sankhya: {' | '.join(erros)}")


def buscar_dados_estoque_vendas():
    """Consulta saldo real e vendas dos últimos 15 dias para calcular a compra."""
    try:
        jsessionid, base_endpoint = autenticar_sankhya()
        cookies = {"JSESSIONID": jsessionid}

        url_dbexp = f"{base_endpoint}/service.sbr?serviceName=DbExplorerSP.executeQuery&outputType=json&mgeSessionHandle={jsessionid}"
        
        # SQL com CTE para buscar histórico de vendas dos últimos 15 dias
        sql_query = """
            WITH Vendas15 AS (
                SELECT 
                    i.CODPROD,
                    ISNULL(SUM(CASE WHEN c.TIPMOV = 'V' THEN i.QTDNEG WHEN c.TIPMOV = 'D' THEN -i.QTDNEG ELSE 0 END), 0) AS VENDA_15
                FROM TGFITE i
                INNER JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
                WHERE c.STATUSNOTA = 'L'
                  AND c.TIPMOV IN ('V', 'D')
                  AND c.DTNEG >= DATEADD(day, -15, GETDATE())
                GROUP BY i.CODPROD
            )
            SELECT 
                p.CODPROD, 
                p.DESCRPROD, 
                ISNULL(p.CODVOL, 'UN') AS UNIDADE,
                ISNULL(SUM(e.ESTOQUE - e.RESERVADO), 0) AS ESTOQUE,
                ISNULL(MAX(e.ESTMIN), 0) AS ESTMIN,
                ISNULL(v.VENDA_15, 0) AS VENDA_15,
                CASE 
                    WHEN ISNULL(MAX(e.ESTMIN), 0) > 0 THEN 
                        CASE WHEN (ISNULL(MAX(e.ESTMIN), 0) - ISNULL(SUM(e.ESTOQUE - e.RESERVADO), 0)) > 0 
                             THEN (ISNULL(MAX(e.ESTMIN), 0) - ISNULL(SUM(e.ESTOQUE - e.RESERVADO), 0))
                             ELSE 0 END
                    ELSE 
                        CASE WHEN (ISNULL(v.VENDA_15, 0) - ISNULL(SUM(e.ESTOQUE - e.RESERVADO), 0)) > 0 
                             THEN (ISNULL(v.VENDA_15, 0) - ISNULL(SUM(e.ESTOQUE - e.RESERVADO), 0))
                             ELSE 0 END
                END AS SUGESTAO_COMPRA
            FROM TGFPRO p
            LEFT JOIN TGFEST e ON p.CODPROD = e.CODPROD
            LEFT JOIN Vendas15 v ON p.CODPROD = v.CODPROD
            WHERE ISNULL(p.ATIVO, 'S') = 'S'
              AND ISNULL(p.USOPROD, '') <> 'C'
            GROUP BY p.CODPROD, p.DESCRPROD, p.CODVOL, v.VENDA_15
            ORDER BY SUGESTAO_COMPRA DESC, v.VENDA_15 DESC, p.DESCRPROD ASC
        """

        payload_dbexp = {"requestBody": {"sql": sql_query}}
        resp_dbexp = requests.post(url_dbexp, json=payload_dbexp, cookies=cookies, timeout=30)
        data_dbexp = resp_dbexp.json()

        response_body = data_dbexp.get("responseBody", {})
        if "rows" in response_body and response_body["rows"]:
            produtos = []
            for linha in response_body["rows"]:
                produtos.append({
                    "codigo": linha[0],
                    "descricao": linha[1],
                    "unidade": linha[2] if len(linha) > 2 else "UN",
                    "estoque": float(linha[3]) if len(linha) > 3 and linha[3] is not None else 0.0,
                    "estoque_minimo": float(linha[4]) if len(linha) > 4 and linha[4] is not None else 0.0,
                    "venda_30d": float(linha[5]) if len(linha) > 5 and linha[5] is not None else 0.0,
                    "sugestao_compra": float(linha[6]) if len(linha) > 6 and linha[6] is not None else 0.0
                })
            return produtos

        return []

    except Exception as e:
        print(f"[ERRO SANKHYA_SERVICE]: {str(e)}")
        return [{"erro": True, "mensagem": str(e)}]