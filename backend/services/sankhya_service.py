import logging
from typing import List, Dict, Any
import os
from pathlib import Path
import requests
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo backend/.env ou do Render
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)

# Credenciais da API Web do Sankhya
SANKHYA_URL = os.getenv("SANKHYA_URL", "").rstrip("/")
SANKHYA_USUARIO = os.getenv("SANKHYA_USUARIO", "")
SANKHYA_SENHA = os.getenv("SANKHYA_SENHA", "")


class SankhyaAPIService:
    """
    Serviço para autenticação e consulta de dados via API REST do Sankhya (MGE).
    """

    def __init__(self):
        self.base_url = SANKHYA_URL
        self.usuario = SANKHYA_USUARIO
        self.senha = SANKHYA_SENHA
        self.session = requests.Session()
        self.jsessionid = None

    def login(self) -> bool:
        """
        Realiza login na API do Sankhya MGE e recupera a JSESSIONID.
        """
        login_url = f"{self.base_url}/service.sbr?serviceName=MobileLoginSP.login&outputType=json"
        
        payload = {
            "serviceName": "MobileLoginSP.login",
            "requestBody": {
                "NOMUSU": {"$": self.usuario},
                "INTERNO": {"$": self.senha}
            }
        }

        try:
            response = self.session.post(login_url, json=payload, timeout=15)
            response.raise_for_status()
            data = response.json()

            status = data.get("status")
            if status == "1":
                self.jsessionid = data.get("responseBody", {}).get("jsessionid", {}).get("$")
                logger.info("Login no Sankhya realizado com sucesso!")
                return True
            else:
                status_msg = data.get("statusMessage", "Erro de autenticação")
                logger.error(f"Falha no login Sankhya: {status_msg}")
                return False

        except Exception as e:
            logger.error(f"Erro ao conectar na API do Sankhya: {str(e)}")
            return False

    def carregar_dados_estoque_vendas(self) -> List[Dict[str, Any]]:
        """
        Executa a consulta de estoque e vendas via serviço de consulta (DbExplorerSP.executeQuery).
        """
        if not self.jsessionid and not self.login():
            raise Exception("Não foi possível autenticar na API do Sankhya.")

        query_url = f"{self.base_url}/service.sbr?serviceName=DbExplorerSP.executeQuery&outputType=json&mgeSession={self.jsessionid}"

        sql_query = """
        WITH Vendas15D AS (
            SELECT 
                ITE.CODPROD,
                SUM(ITE.QTDNEG) AS QTD_VENDIDA_15D
            FROM TGFCAB CAB
            INNER JOIN TGFITE ITE ON CAB.NUNOTA = ITE.NUNOTA
            INNER JOIN TGFTOP TOP ON CAB.CODTIPOPER = TOP.CODTIPOPER AND CAB.DHTIPOPER = TOP.DHALTER
            WHERE CAB.DTNEG >= DATEADD(day, -15, CAST(GETDATE() AS DATE))
              AND CAB.STATUSNOTA = 'L'
              AND TOP.GHOST = 'N'
              AND TOP.BONIFICACAO = 'N'
              AND TOP.DTPRESO = 'N'
              AND TOP.ATUALEST = 'B'
            GROUP BY ITE.CODPROD
        ),
        VendasMesAnt AS (
            SELECT 
                ITE.CODPROD,
                SUM(ITE.QTDNEG) AS QTD_VENDIDA_MES_ANT
            FROM TGFCAB CAB
            INNER JOIN TGFITE ITE ON CAB.NUNOTA = ITE.NUNOTA
            INNER JOIN TGFTOP TOP ON CAB.CODTIPOPER = TOP.CODTIPOPER AND CAB.DHTIPOPER = TOP.DHALTER
            WHERE CAB.DTNEG >= DATEADD(month, DATEDIFF(month, 0, GETDATE()) - 1, 0)
              AND CAB.DTNEG < DATEADD(month, DATEDIFF(month, 0, GETDATE()), 0)
              AND CAB.STATUSNOTA = 'L'
              AND TOP.GHOST = 'N'
              AND TOP.BONIFICACAO = 'N'
              AND TOP.DTPRESO = 'N'
              AND TOP.ATUALEST = 'B'
            GROUP BY ITE.CODPROD
        )
        SELECT 
            PRO.CODPROD,
            PRO.DESCRPROD,
            PRO.CODVOL AS UNIDADEMEDIDA,
            ISNULL(EST.ESTOQUE, 0) AS ESTOQUE_ATUAL,
            ISNULL(EST.ESTMIN, 0) AS ESTOQUE_MINIMO,
            ISNULL(V15.QTD_VENDIDA_15D, 0) AS VENDAS_15D,
            ISNULL(VMA.QTD_VENDIDA_MES_ANT, 0) AS VENDAS_MES_ANTERIOR,
            ISNULL(CUS.CUSSEMICMS, 0) AS CUSTO_UNITARIO,
            ISNULL(EXC.VLRVENDA, 0) AS PRECO_VENDA
        FROM TGFPRO PRO
        LEFT JOIN TGFEST EST ON PRO.CODPROD = EST.CODPROD AND EST.CODEMP = 1 AND EST.CODLOCAL = 0
        LEFT JOIN Vendas15D V15 ON PRO.CODPROD = V15.CODPROD
        LEFT JOIN VendasMesAnt VMA ON PRO.CODPROD = VMA.CODPROD
        LEFT JOIN TGFCUS CUS ON PRO.CODPROD = CUS.CODPROD AND CUS.CODEMP = 1 AND CUS.DTATUAL = (
            SELECT MAX(DTATUAL) FROM TGFCUS WHERE CODPROD = PRO.CODPROD AND CODEMP = 1
        )
        LEFT JOIN TGFEXC EXC ON PRO.CODPROD = EXC.CODPROD AND EXC.NUTAB = 1
        WHERE PRO.ATIVO = 'S'
          AND (ISNULL(EST.ESTOQUE, 0) > 0 OR ISNULL(V15.QTD_VENDIDA_15D, 0) > 0)
        ORDER BY PRO.DESCRPROD
        """

        payload = {
            "serviceName": "DbExplorerSP.executeQuery",
            "requestBody": {
                "sql": sql_query
            }
        }

        try:
            response = self.session.post(query_url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "1":
                status_msg = data.get("statusMessage", "Erro ao executar consulta SQL na API Sankhya")
                logger.error(f"Erro Sankhya API: {status_msg}")
                return []

            response_body = data.get("responseBody", {})
            fields = [field.get("name") for field in response_body.get("fields", {}).get("field", [])]
            rows = response_body.get("rows", {}).get("row", [])

            produtos = []
            for row in rows:
                values = row.get("localFields", {}).get("localField", [])
                item = {}
                for idx, field_name in enumerate(fields):
                    item[field_name] = values[idx].get("$") if idx < len(values) else None
                produtos.append(item)

            return produtos

        except Exception as e:
            logger.error(f"Erro ao consultar estoque/vendas via API Sankhya: {str(e)}")
            raise e


def buscar_dados_estoque_vendas() -> List[Dict[str, Any]]:
    """
    Função principal chamada pelo FastAPI (app.py).
    """
    service = SankhyaAPIService()
    return service.carregar_dados_estoque_vendas()