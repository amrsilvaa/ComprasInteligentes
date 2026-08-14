import logging
from typing import List, Dict, Any
import os
from pathlib import Path
import requests
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)

SANKHYA_URL = os.getenv("SANKHYA_URL", "").rstrip("/")
SANKHYA_USUARIO = os.getenv("SANKHYA_USUARIO", "")
SANKHYA_SENHA = os.getenv("SANKHYA_SENHA", "")


class SankhyaAPIService:

    @staticmethod
    def _coerce_number(value: Any) -> float:
        if value is None or value == "":
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace(".", "").replace(",", "."))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _first_value(item: Dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in item:
                return item[key]
            lower_key = key.lower()
            if lower_key in item:
                return item[lower_key]
            upper_key = key.upper()
            if upper_key in item:
                return item[upper_key]
        return None

    @classmethod
    def _normalizar_produto(cls, item: Dict[str, Any]) -> Dict[str, Any]:
        codigo = cls._first_value(item, "CODPROD", "codigo", "codprod")
        descricao = cls._first_value(item, "DESCRPROD", "descricao", "descrprod")
        unidade = cls._first_value(item, "UNIDADEMEDIDA", "unidade", "codvol", "CODVOL")
        estoque = cls._first_value(item, "ESTOQUE", "DISPONIVEL", "SALDO", "estoque")
        estoque_minimo = cls._first_value(item, "ESTOQUE_MINIMO", "ESTMIN", "estoque_minimo")
        venda_15d = cls._first_value(item, "VENDAS_15D", "vendas_15d")
        venda_mes_anterior = cls._first_value(item, "VENDAS_MES_ANTERIOR", "vendas_mes_anterior")
        custo = cls._first_value(item, "PRECO_CUSTO", "CUSTO_UNITARIO", "custo")
        preco_venda = cls._first_value(item, "PRECO_VENDA", "preco_venda")

        estoque_valor = cls._coerce_number(estoque)
        estoque_minimo_valor = cls._coerce_number(estoque_minimo)
        venda_15d_valor = cls._coerce_number(venda_15d)
        venda_mes_anterior_valor = cls._coerce_number(venda_mes_anterior)
        custo_valor = cls._coerce_number(custo)
        preco_venda_valor = cls._coerce_number(preco_venda)
        
        sugestao = max(0.0, venda_15d_valor - estoque_valor)

        produto = {
            "codigo": codigo,
            "descricao": descricao,
            "unidade": unidade if unidade else "UN",
            "estoque": estoque_valor,
            "estoque_disponivel": estoque_valor,
            "estoque_minimo": estoque_minimo_valor,
            "venda_15d": venda_15d_valor,
            "venda_mes_anterior": venda_mes_anterior_valor,
            "custo": custo_valor,
            "preco_venda": preco_venda_valor,
            "sugestao_compra": sugestao,
            "status": "REPOR" if sugestao > 0 else "OK",
        }

        return produto

    def __init__(self):
        self.base_url = SANKHYA_URL
        self.usuario = SANKHYA_USUARIO
        self.senha = SANKHYA_SENHA
        self.session = requests.Session()
        self.jsessionid = None

    def login(self) -> bool:
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
        logger.info("=== INICIANDO carregar_dados_estoque_vendas ===")
        if not self.jsessionid and not self.login():
            raise Exception("Não foi possível autenticar na API do Sankhya.")

        query_url = f"{self.base_url}/service.sbr?serviceName=DbExplorerSP.executeQuery&outputType=json&mgeSession={self.jsessionid}"

        # SQL Direta e Otimizada baseada na query do seu Gadget do Sankhya
        sql_query = """
        SELECT 
            PRO.CODPROD,
            PRO.DESCRPROD,
            PRO.CODVOL AS UNIDADEMEDIDA,
            ISNULL(EST.ESTOQUE, 0) - ISNULL(EST.RESERVADO, 0) AS ESTOQUE,
            ISNULL(EST.ESTMIN, 0) AS ESTOQUE_MINIMO,
            ISNULL(V15.QTD, 0) AS VENDAS_15D,
            ISNULL(VMA.QTD, 0) AS VENDAS_MES_ANTERIOR,
            ISNULL(CUS.CUSREP, 0) AS PRECO_CUSTO,
            ISNULL(EXC.VLRVENDA, 0) AS PRECO_VENDA
        FROM TGFPRO PRO

        INNER JOIN (
            SELECT 
                CODPROD,
                SUM(ESTOQUE) AS ESTOQUE,
                SUM(RESERVADO) AS RESERVADO,
                MAX(ESTMIN) AS ESTMIN
            FROM TGFEST
            WHERE TIPO = 'P'
            GROUP BY CODPROD
        ) EST ON EST.CODPROD = PRO.CODPROD

        LEFT JOIN (
            SELECT ITE.CODPROD, SUM(ITE.QTDNEG) AS QTD
            FROM TGFCAB CAB
            INNER JOIN TGFITE ITE ON CAB.NUNOTA = ITE.NUNOTA
            WHERE CAB.DTNEG >= DATEADD(day, -15, CAST(GETDATE() AS DATE))
              AND CAB.STATUSNOTA = 'L'
            GROUP BY ITE.CODPROD
        ) V15 ON V15.CODPROD = PRO.CODPROD

        LEFT JOIN (
            SELECT ITE.CODPROD, SUM(ITE.QTDNEG) AS QTD
            FROM TGFCAB CAB
            INNER JOIN TGFITE ITE ON CAB.NUNOTA = ITE.NUNOTA
            WHERE CAB.DTNEG >= DATEADD(month, DATEDIFF(month, 0, GETDATE()) - 1, 0)
              AND CAB.DTNEG < DATEADD(month, DATEDIFF(month, 0, GETDATE()), 0)
              AND CAB.STATUSNOTA = 'L'
            GROUP BY ITE.CODPROD
        ) VMA ON VMA.CODPROD = PRO.CODPROD

        LEFT JOIN (
            SELECT CODPROD, CUSREP
            FROM (
                SELECT CODPROD, CUSREP, ROW_NUMBER() OVER (PARTITION BY CODPROD ORDER BY DTATUAL DESC) AS RN
                FROM TGFCUS
            ) CUSTO_TEMP WHERE RN = 1
        ) CUS ON CUS.CODPROD = PRO.CODPROD

        LEFT JOIN (
            SELECT CODPROD, VLRVENDA
            FROM (
                SELECT E.CODPROD, E.VLRVENDA, ROW_NUMBER() OVER (PARTITION BY E.CODPROD ORDER BY E.NUTAB DESC) AS RN
                FROM TGFEXC E
            ) TAB_TEMP WHERE RN = 1
        ) EXC ON EXC.CODPROD = PRO.CODPROD

        WHERE PRO.ATIVO = 'S'
          AND RTRIM(LTRIM(PRO.USOCOM)) = 'R'
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
                status_msg = data.get("statusMessage", "Erro na consulta Sankhya")
                logger.error(f"Erro Sankhya API: {status_msg}")
                return []

            response_body = data.get("responseBody", {})
            
            fields = []
            if isinstance(response_body, dict):
                fields_meta = response_body.get("fieldsMetadata", [])
                if isinstance(fields_meta, list):
                    for field in fields_meta:
                        if isinstance(field, dict):
                            fields.append(field.get("name"))
                        elif isinstance(field, str):
                            fields.append(field)
            
            rows = []
            if isinstance(response_body, dict):
                rows_obj = response_body.get("rows", [])
                if isinstance(rows_obj, list):
                    rows = rows_obj
            elif isinstance(response_body, list):
                rows = response_body
            
            produtos = []
            
            for row in rows:
                item = {}
                if isinstance(row, dict):
                    values = row.get("localFields", {}).get("localField", [])
                    if isinstance(values, dict):
                        values = [values]
                    for idx, field_name in enumerate(fields):
                        if field_name is None or idx >= len(values):
                            continue
                        val_obj = values[idx]
                        val = val_obj.get("$") if isinstance(val_obj, dict) else val_obj
                        item[field_name] = val
                
                elif isinstance(row, list):
                    for idx, field_name in enumerate(fields):
                        if field_name is None or idx >= len(row):
                            continue
                        val = row[idx]
                        item[field_name] = val
                
                if item:
                    produtos.append(self._normalizar_produto(item))
            
            logger.info(f"Sucesso! Total de produtos de revenda retornados: {len(produtos)}")
            return produtos

        except Exception as e:
            logger.error(f"Erro ao consultar estoque/vendas via API Sankhya: {str(e)}")
            raise e


def buscar_dados_estoque_vendas() -> List[Dict[str, Any]]:
    service = SankhyaAPIService()
    return service.carregar_dados_estoque_vendas()