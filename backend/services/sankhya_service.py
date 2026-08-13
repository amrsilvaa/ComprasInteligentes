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
    """Consulta de alta performance trazendo Custo de Reposição, Custo Gerencial, Preço de Venda e Cálculo de Preço por KG."""
    try:
        jsessionid, base_endpoint = autenticar_sankhya()
        cookies = {"JSESSIONID": jsessionid}

        url_dbexp = f"{base_endpoint}/service.sbr?serviceName=DbExplorerSP.executeQuery&outputType=json&mgeSessionHandle={jsessionid}"
        
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
            ),
            VendasMesAnterior AS (
                SELECT 
                    i.CODPROD,
                    ISNULL(SUM(CASE WHEN c.TIPMOV = 'V' THEN i.QTDNEG WHEN c.TIPMOV = 'D' THEN -i.QTDNEG ELSE 0 END), 0) AS VENDA_MES_ANT
                FROM TGFITE i
                INNER JOIN TGFCAB c ON c.NUNOTA = i.NUNOTA
                WHERE c.STATUSNOTA = 'L'
                  AND c.TIPMOV IN ('V', 'D')
                  AND c.DTNEG >= DATEADD(month, DATEDIFF(month, 0, GETDATE()) - 1, 0)
                  AND c.DTNEG < DATEADD(month, DATEDIFF(month, 0, GETDATE()), 0)
                GROUP BY i.CODPROD
            )
            SELECT 
                p.CODPROD, 
                p.DESCRPROD, 
                ISNULL(p.CODVOL, 'UN') AS UNIDADE,
                ISNULL(MAX(p.PESOLIQUIDO), 0) AS PESOLIQUIDO,
                ISNULL(MAX(p.PESOBRUTO), 0) AS PESOBRUTO,
                ISNULL(SUM(e.ESTOQUE - e.RESERVADO), 0) AS ESTOQUE,
                ISNULL(MAX(e.ESTMIN), 0) AS ESTMIN,
                ISNULL(v15.VENDA_15, 0) AS VENDA_15,
                CASE 
                    WHEN ISNULL(MAX(e.ESTMIN), 0) > 0 THEN 
                        CASE WHEN (ISNULL(MAX(e.ESTMIN), 0) - ISNULL(SUM(e.ESTOQUE - e.RESERVADO), 0)) > 0 
                             THEN (ISNULL(MAX(e.ESTMIN), 0) - ISNULL(SUM(e.ESTOQUE - e.RESERVADO), 0))
                             ELSE 0 END
                    ELSE 
                        CASE WHEN (ISNULL(v15.VENDA_15, 0) - ISNULL(SUM(e.ESTOQUE - e.RESERVADO), 0)) > 0 
                             THEN (ISNULL(v15.VENDA_15, 0) - ISNULL(SUM(e.ESTOQUE - e.RESERVADO), 0))
                             ELSE 0 END
                END AS SUGESTAO_COMPRA,
                ISNULL(vma.VENDA_MES_ANT, 0) AS VENDA_MES_ANT,
                ISNULL(MAX(c.CUSREP), 0) AS CUSTO_REPOSICAO,
                ISNULL(MAX(c.CUSGER), 0) AS CUSTO_GERENCIAL,
                ISNULL(MAX(prc.VLRVENDA), 0) AS PRECO_VENDA
            LEFT JOIN TGFPRO p
            LEFT JOIN TGFEST e ON p.CODPROD = e.CODPROD
            LEFT JOIN Vendas15 v15 ON p.CODPROD = v15.CODPROD
            LEFT JOIN VendasMesAnterior vma ON p.CODPROD = vma.CODPROD
            LEFT JOIN TGFCUS c ON p.CODPROD = c.CODPROD AND c.CODEMP = 1 AND c.DTATUAL = (SELECT MAX(c2.DTATUAL) FROM TGFCUS c2 WHERE c2.CODPROD = p.CODPROD AND c2.CODEMP = 1)
            LEFT JOIN TGFEXC prc ON p.CODPROD = prc.CODPROD AND prc.NUTAB = 604
            WHERE ISNULL(p.ATIVO, 'S') = 'S'
              AND ISNULL(p.USOPROD, '') <> 'C'
            GROUP BY p.CODPROD, p.DESCRPROD, p.CODVOL, v15.VENDA_15, vma.VENDA_MES_ANT
            ORDER BY SUGESTAO_COMPRA DESC, v15.VENDA_15 DESC, p.DESCRPROD ASC
        """

        payload_dbexp = {"requestBody": {"sql": sql_query}}
        resp_dbexp = requests.post(url_dbexp, json=payload_dbexp, cookies=cookies, timeout=30)
        data_dbexp = resp_dbexp.json()

        response_body = data_dbexp.get("responseBody", {})
        if "rows" in response_body and response_body["rows"]:
            produtos = []
            for linha in response_body["rows"]:
                unidade = linha[2] if len(linha) > 2 and linha[2] else "UN"
                peso_liq = float(linha[3]) if len(linha) > 3 and linha[3] is not None else 0.0
                peso_bruto = float(linha[4]) if len(linha) > 4 and linha[4] is not None else 0.0
                
                custo_rep = float(linha[10]) if len(linha) > 10 and linha[10] is not None else 0.0
                custo_ger = float(linha[11]) if len(linha) > 11 and linha[11] is not None else 0.0
                custo_principal = custo_rep if custo_rep > 0 else custo_ger
                
                preco_venda = float(linha[12]) if len(linha) > 12 and linha[12] is not None else 0.0

                # Identifica o peso unitario da embalagem (ex: 20kg na caixa de frango)
                peso_unitario = peso_liq if peso_liq > 0 else peso_bruto

                # Se for caixa/fardo e tiver peso cadastrado, calcula os valores por KG
                if unidade != "KG" and peso_unitario > 0:
                    preco_kg = preco_venda / peso_unitario
                    custo_kg = custo_principal / peso_unitario
                else:
                    preco_kg = preco_venda
                    custo_kg = custo_principal

                produtos.append({
                    "codigo": linha[0],
                    "descricao": linha[1],
                    "unidade": unidade,
                    "peso_unitario": peso_unitario,
                    "estoque": float(linha[5]) if len(linha) > 5 and linha[5] is not None else 0.0,
                    "estoque_minimo": float(linha[6]) if len(linha) > 6 and linha[6] is not None else 0.0,
                    "venda_15d": float(linha[7]) if len(linha) > 7 and linha[7] is not None else 0.0,
                    "sugestao_compra": float(linha[8]) if len(linha) > 8 and linha[8] is not None else 0.0,
                    "venda_mes_anterior": float(linha[9]) if len(linha) > 9 and linha[9] is not None else 0.0,
                    "custo": custo_principal,
                    "custo_kg": round(custo_kg, 2),
                    "custo_reposicao": custo_rep,
                    "custo_gerencial": custo_ger,
                    "preco_venda": preco_venda,
                    "preco_kg": round(preco_kg, 2)
                })
            return produtos

        print(f"[RESPOSTA SANKHYA SEM ROWS]: {data_dbexp}")
        return []

    except Exception as e:
        print(f"[ERRO SANKHYA_SERVICE]: {str(e)}")
        return []
