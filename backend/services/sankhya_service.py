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
    """Consulta trazendo Custo de Reposição real e Saldo de Estoque idêntico ao Sankhya."""
    try:
        jsessionid, base_endpoint = autenticar_sankhya()
        cookies = {"JSESSIONID": jsessionid}

        url_dbexp = f"{base_endpoint}/service.sbr?serviceName=DbExplorerSP.executeQuery&outputType=json&mgeSessionHandle={jsessionid}"
        
        sql_query = """
            WITH Vendas15 AS (
                SELECT 
                    i.CODPROD,
                    ISNULL(SUM(CASE WHEN c.TIPMOV = 'V' THEN i.QTDNEG WHEN c.TIPMOV = 'D' THEN -i.QTDNEG ELSE 0 END), 0) AS VENDA_15
                FROM TGFITE i WITH (NOLOCK)
                INNER JOIN TGFCAB c WITH (NOLOCK) ON c.NUNOTA = i.NUNOTA
                WHERE c.STATUSNOTA = 'L'
                  AND c.TIPMOV IN ('V', 'D')
                  AND c.DTNEG >= DATEADD(day, -15, GETDATE())
                GROUP BY i.CODPROD
            ),
            VendasMesAnterior AS (
                SELECT 
                    i.CODPROD,
                    ISNULL(SUM(CASE WHEN c.TIPMOV = 'V' THEN i.QTDNEG WHEN c.TIPMOV = 'D' THEN -i.QTDNEG ELSE 0 END), 0) AS VENDA_MES_ANT
                FROM TGFITE i WITH (NOLOCK)
                INNER JOIN TGFCAB c WITH (NOLOCK) ON c.NUNOTA = i.NUNOTA
                WHERE c.STATUSNOTA = 'L'
                  AND c.TIPMOV IN ('V', 'D')
                  AND c.DTNEG >= DATEADD(month, DATEDIFF(month, 0, GETDATE()) - 1, 0)
                  AND c.DTNEG < DATEADD(month, DATEDIFF(month, 0, GETDATE()), 0)
                GROUP BY i.CODPROD
            ),
          EstoqueTotal AS (
    SELECT 
        CODPROD,
        ISNULL(SUM(ESTOQUE - RESERVADO), 0) AS ESTOQUE,
        ISNULL(MAX(ESTMIN), 0) AS ESTMIN
    FROM TGFEST WITH (NOLOCK)
    WHERE CODEMP = 1 
      AND CODLOCAL <> 0  -- Ignora o estoque do Local 0 (Remessas / Fiscal)
    GROUP BY CODPROD
),
            UltimoCusto AS (
                SELECT 
                    CODPROD,
                    CUSREP,
                    CUSGER,
                    ROW_NUMBER() OVER (PARTITION BY CODPROD ORDER BY DTATUAL DESC, CUSREP DESC) AS RN
                FROM TGFCUS WITH (NOLOCK)
                WHERE CODEMP = 1 AND (CUSREP > 0 OR CUSGER > 0)
            )
            SELECT 
                p.CODPROD, 
                p.DESCRPROD, 
                ISNULL(p.CODVOL, 'UN') AS UNIDADE,
                ISNULL(p.PESOBRUTO, 0) AS PESO,
                ISNULL(e.ESTOQUE, 0) AS ESTOQUE,
                ISNULL(e.ESTMIN, 0) AS ESTMIN,
                ISNULL(v15.VENDA_15, 0) AS VENDA_15,
                CASE 
                    WHEN ISNULL(e.ESTMIN, 0) > 0 THEN 
                        CASE WHEN (ISNULL(e.ESTMIN, 0) - ISNULL(e.ESTOQUE, 0)) > 0 
                             THEN (ISNULL(e.ESTMIN, 0) - ISNULL(e.ESTOQUE, 0))
                             ELSE 0 END
                    ELSE 
                        CASE WHEN (ISNULL(v15.VENDA_15, 0) - ISNULL(e.ESTOQUE, 0)) > 0 
                             THEN (ISNULL(v15.VENDA_15, 0) - ISNULL(e.ESTOQUE, 0))
                             ELSE 0 END
                END AS SUGESTAO_COMPRA,
                ISNULL(vma.VENDA_MES_ANT, 0) AS VENDA_MES_ANT,
                ISNULL(c.CUSREP, 0) AS CUSTO_REPOSICAO,
                ISNULL(c.CUSGER, 0) AS CUSTO_GERENCIAL,
                ISNULL(prc.VLRVENDA, 0) AS PRECO_VENDA
            FROM TGFPRO p WITH (NOLOCK)
            LEFT JOIN EstoqueTotal e ON p.CODPROD = e.CODPROD
            LEFT JOIN Vendas15 v15 ON p.CODPROD = v15.CODPROD
            LEFT JOIN VendasMesAnterior vma ON p.CODPROD = vma.CODPROD
            LEFT JOIN UltimoCusto c ON p.CODPROD = c.CODPROD AND c.RN = 1
            LEFT JOIN TGFEXC prc WITH (NOLOCK) ON p.CODPROD = prc.CODPROD AND prc.NUTAB = 604
            WHERE ISNULL(p.ATIVO, 'S') = 'S'
              AND ISNULL(p.USOPROD, '') <> 'C'
            ORDER BY SUGESTAO_COMPRA DESC, v15.VENDA_15 DESC, p.DESCRPROD ASC
        """

        payload_dbexp = {"requestBody": {"sql": sql_query}}
        resp_dbexp = requests.post(url_dbexp, json=payload_dbexp, cookies=cookies, timeout=30)
        data_dbexp = resp_dbexp.json()

        response_body = data_dbexp.get("responseBody", {})
        if "rows" in response_body and response_body["rows"]:
            produtos = []
            for linha in response_body["rows"]:
                codigo = linha[0]
                descricao = linha[1]
                unidade = linha[2] if linha[2] else "UN"
                peso = float(linha[3]) if linha[3] is not None else 0.0
                estoque = float(linha[4]) if linha[4] is not None else 0.0
                estoque_min = float(linha[5]) if linha[5] is not None else 0.0
                venda_15 = float(linha[6]) if linha[6] is not None else 0.0
                sugestao = float(linha[7]) if linha[7] is not None else 0.0
                venda_ma = float(linha[8]) if linha[8] is not None else 0.0
                custo_rep = float(linha[9]) if linha[9] is not None else 0.0
                custo_ger = float(linha[10]) if linha[10] is not None else 0.0
                preco_venda = float(linha[11]) if linha[11] is not None else 0.0

                custo_principal = custo_rep if custo_rep > 0 else custo_ger

                if unidade != "KG" and peso > 0:
                    preco_kg = preco_venda / peso
                    custo_kg = custo_principal / peso
                else:
                    preco_kg = preco_venda
                    custo_kg = custo_principal

                produtos.append({
                    "codigo": codigo,
                    "descricao": descricao,
                    "unidade": unidade,
                    "peso_unitario": peso,
                    "estoque": estoque,
                    "estoque_minimo": estoque_min,
                    "venda_15d": venda_15,
                    "sugestao_compra": sugestao,
                    "venda_mes_anterior": venda_ma,
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