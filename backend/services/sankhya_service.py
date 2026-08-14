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
        unidade = cls._first_value(item, "UNIDADEMEDIDA", "unidade", "codvol")
        estoque = cls._first_value(item, "ESTOQUE_DISPONIVEL", "SALDO", "DISPONIVEL", "ESTOQUE", "estoque")
        estoque_minimo = cls._first_value(item, "ESTOQUE_MINIMO", "estoque_minimo", "ESTMIN")
        venda_15d = cls._first_value(item, "VENDAS_15D", "vendas_15d", "QTD_VENDIDA_15D")
        venda_mes_anterior = cls._first_value(item, "VENDAS_MES_ANTERIOR", "vendas_mes_anterior", "QTD_VENDIDA_MES_ANT")
        custo = cls._first_value(item, "CUSTO_UNITARIO", "custo_unitario", "CUSREP", "PRECO_CUSTO")
        preco_venda = cls._first_value(item, "PRECO_VENDA", "preco_venda", "VLRVENDA")

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
            "unidade": unidade,
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

        for key, value in item.items():
            produto[key] = value

        for key in list(produto.keys()):
            if isinstance(key, str):
                produto[key.lower()] = produto[key]
                produto[key.upper()] = produto[key]

        return produto

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
        logger.info("=== INICIANDO carregar_dados_estoque_vendas ===")
        if not self.jsessionid and not self.login():
            raise Exception("Não foi possível autenticar na API do Sankhya.")

        query_url = f"{self.base_url}/service.sbr?serviceName=DbExplorerSP.executeQuery&outputType=json&mgeSession={self.jsessionid}"

        # Consulta SQL com Custo de Reposição (CUSREP) e Preço de Venda Ordenado por NUTAB
        sql_query = """
        WITH Vendas15D AS (
            SELECT 
                ITE.CODPROD,
                SUM(ITE.QTDNEG) AS QTD_VENDIDA_15D
            FROM TGFCAB CAB
            INNER JOIN TGFITE ITE ON CAB.NUNOTA = ITE.NUNOTA
            WHERE CAB.DTNEG >= DATEADD(day, -15, CAST(GETDATE() AS DATE))
              AND CAB.STATUSNOTA = 'L'
            GROUP BY ITE.CODPROD
        ),
        VendasMesAnt AS (
            SELECT 
                ITE.CODPROD,
                SUM(ITE.QTDNEG) AS QTD_VENDIDA_MES_ANT
            FROM TGFCAB CAB
            INNER JOIN TGFITE ITE ON CAB.NUNOTA = ITE.NUNOTA
            WHERE CAB.DTNEG >= DATEADD(month, DATEDIFF(month, 0, GETDATE()) - 1, 0)
              AND CAB.DTNEG < DATEADD(month, DATEDIFF(month, 0, GETDATE()), 0)
              AND CAB.STATUSNOTA = 'L'
            GROUP BY ITE.CODPROD
        ),
        EstoqueSum AS (
            SELECT 
                CODPROD,
                SUM(ESTOQUE - ISNULL(RESERVADO, 0)) AS ESTOQUE_DISPONIVEL,
                SUM(ESTOQUE) AS ESTOQUE_ATUAL,
                MAX(ESTMIN) AS ESTOQUE_MINIMO
            FROM TGFEST
            WHERE TIPO = 'P'
            GROUP BY CODPROD
        ),
        CustoReposicao AS (
            SELECT CODPROD, CUSREP
            FROM (
                SELECT CODPROD, CUSREP, ROW_NUMBER() OVER (PARTITION BY CODPROD ORDER BY DTATUAL DESC) AS RN
                FROM TGFCUS
            ) CUSTO_TEMP WHERE RN = 1
        ),
        PrecoVenda AS (
            SELECT CODPROD, VLRVENDA
            FROM (
                SELECT 
                    E.CODPROD, 
                    E.VLRVENDA,
                    ROW_NUMBER() OVER (PARTITION BY E.CODPROD ORDER BY E.NUTAB DESC) AS RN
                FROM TGFEXC E
            ) TAB_TEMP WHERE RN = 1
        )
        SELECT 
            PRO.CODPROD,
            PRO.DESCRPROD,
            PRO.CODVOL AS UNIDADEMEDIDA,
            ISNULL(EST.ESTOQUE_DISPONIVEL, 0) AS ESTOQUE_DISPONIVEL,
            ISNULL(EST.ESTOQUE_DISPONIVEL, 0) AS SALDO,
            ISNULL(EST.ESTOQUE_ATUAL, 0) AS ESTOQUE_ATUAL,
            ISNULL(EST.ESTOQUE_MINIMO, 0) AS ESTOQUE_MINIMO,
            ISNULL(V15.QTD_VENDIDA_15D, 0) AS VENDAS_15D,
            ISNULL(VMA.QTD_VENDIDA_MES_ANT, 0) AS VENDAS_MES_ANTERIOR,
            ISNULL(CUS.CUSREP, 0) AS CUSTO_UNITARIO,
            ISNULL(EXC.VLRVENDA, 0) AS PRECO_VENDA
        FROM TGFPRO PRO
        LEFT JOIN EstoqueSum EST ON PRO.CODPROD = EST.CODPROD
        LEFT JOIN Vendas15D V15 ON PRO.CODPROD = V15.CODPROD
        LEFT JOIN VendasMesAnt VMA ON PRO.CODPROD = VMA.CODPROD
        LEFT JOIN CustoReposicao CUS ON PRO.CODPROD = CUS.CODPROD
        LEFT JOIN PrecoVenda EXC ON PRO.CODPROD = EXC.CODPROD
        WHERE PRO.ATIVO = 'S'
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
                        item[field_name.upper()] = val
                        item[field_name.lower()] = val
                
                elif isinstance(row, list):
                    for idx, field_name in enumerate(fields):
                        if field_name is None or idx >= len(row):
                            continue
                        val = row[idx]
                        item[field_name] = val
                        item[field_name.upper()] = val
                        item[field_name.lower()] = val
                
                if item:
                    produtos.append(self._normalizar_produto(item))
            
            # Filtra produtos para exibir na lista
            produtos_com_estoque = [p for p in produtos if p.get("estoque", 0) > 0 or p.get("venda_15d", 0) > 0]
            logger.info(f"Carregados {len(produtos_com_estoque)} de {len(produtos)} produtos.")
            return produtos_com_estoque

        except Exception as e:
            logger.error(f"Erro ao consultar estoque/vendas via API Sankhya: {str(e)}")
            raise e


def buscar_dados_estoque_vendas() -> List[Dict[str, Any]]:
    """
    Função principal chamada pelo FastAPI (app.py).
    """
    service = SankhyaAPIService()
    return service.carregar_dados_estoque_vendas()