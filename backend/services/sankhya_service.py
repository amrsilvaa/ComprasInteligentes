import logging
from typing import List, Dict, Any
import os
from pathlib import Path
import requests
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
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
    def _normalizar_produto(cls, item: Dict[str, Any], mapa_fornecedores: dict) -> Dict[str, Any]:
        codigo = cls._first_value(item, "CODPROD", "codigo", "codprod", "cod")
        descricao = cls._first_value(item, "DESCRPROD", "descricao", "descrprod", "desc")
        unidade = cls._first_value(item, "UNIDADEMEDIDA", "unidade", "codvol", "CODVOL")
        ean = cls._first_value(item, "EAN", "CODBARRA", "ean", "codbarra")
        complemento = cls._first_value(item, "COMPLEMENTO", "COMPLDESC", "complemento", "compldesc")
        separador = cls._first_value(item, "SEPARADOR", "CODAREASEP", "separador", "codareasep")
        
        # 🔥 CORREÇÃO: Pega o código do fornecedor e busca o nome
        cod_fornecedor = cls._first_value(item, "CODPARCFORN")
        
        fornecedor = ""
        if cod_fornecedor:
            cod_str = str(cod_fornecedor).strip()
            # Busca no mapa de fornecedores carregado
            if cod_str in mapa_fornecedores:
                fornecedor = mapa_fornecedores[cod_str]
            else:
                # Tenta buscar com pontos (ex: 4.0)
                cod_sem_ponto = cod_str.replace(".", "")
                if cod_sem_ponto in mapa_fornecedores:
                    fornecedor = mapa_fornecedores[cod_sem_ponto]
                elif cod_str in mapa_fornecedores:
                    fornecedor = mapa_fornecedores[cod_str]
                else:
                    # Log para debug
                    logger.debug(f"Fornecedor não encontrado: {cod_str}")
                    fornecedor = f"Forn: {cod_str}"

        estoque_bruto = cls._first_value(item, "ESTOQUE", "estoque")
        reservado = cls._first_value(item, "RESERVADO", "reservado")
        disponivel = cls._first_value(item, "DISPONIVEL", "disponivel")

        venda_15d = cls._first_value(item, "VENDAS_15D", "vendas_15d", "venda_15d")
        venda_mes_anterior = cls._first_value(item, "VENDAS_MES_ANTERIOR", "vendas_mes_anterior", "venda_mes_anterior")
        custo = cls._first_value(item, "PRECO_CUSTO", "CUSTO_UNITARIO", "custo", "CUSREP")
        preco_venda = cls._first_value(item, "PRECO_VENDA", "preco_venda", "VLRVENDA")

        estoque_valor = cls._coerce_number(estoque_bruto)
        reservado_valor = cls._coerce_number(reservado)
        
        if disponivel is not None and str(disponivel).strip() != "":
            disponivel_valor = cls._coerce_number(disponivel)
        else:
            disponivel_valor = estoque_valor - reservado_valor

        venda_15d_valor = cls._coerce_number(venda_15d)
        venda_mes_anterior_valor = cls._coerce_number(venda_mes_anterior)
        custo_valor = cls._coerce_number(custo)
        preco_venda_valor = cls._coerce_number(preco_venda)

        ean_str = ""
        if ean is not None and str(ean).strip() != "":
            ean_raw = str(ean).strip()
            if "E+" in ean_raw.upper() or "E-" in ean_raw.upper():
                try:
                    ean_str = f"{int(float(ean_raw))}"
                except ValueError:
                    ean_str = ean_raw
            else:
                ean_str = ean_raw.split(".")[0] if "." in ean_raw else ean_raw

        sugestao = max(0.0, venda_15d_valor - disponivel_valor)
        status = "REPOR" if sugestao > 0 else "OK"

        return {
            "codigo": codigo,
            "ean": ean_str,
            "complemento": complemento if complemento is not None else "",
            "descricao": descricao,
            "separador": separador if separador is not None else "",
            "fornecedor": fornecedor,  # 🔥 Nome do fornecedor
            "estoque": estoque_valor,
            "reservado": reservado_valor,
            "disponivel": disponivel_valor,
            "cod": codigo,
            "desc": descricao,
            "unidade": unidade if unidade else "UN",
            "estoque_disponivel": disponivel_valor,
            "estoque_minimo": 0.0,
            "venda_15d": venda_15d_valor,
            "vendas_15d": venda_15d_valor,
            "venda_mes_anterior": venda_mes_anterior_valor,
            "vendas_mes_ant": venda_mes_anterior_valor,
            "custo": custo_valor,
            "custo_un": custo_valor,
            "preco_venda": preco_venda_valor,
            "sugestao_compra": sugestao,
            "status": status,
            "CODIGO": codigo,
            "DESCRICAO": descricao,
            "SEPARADOR": separador if separador is not None else "",
            "ESTOQUE": estoque_valor,
            "RESERVADO": reservado_valor,
        }

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

            if data.get("status") == "1":
                self.jsessionid = data.get("responseBody", {}).get("jsessionid", {}).get("$")
                logger.info("Login no Sankhya realizado com sucesso!")
                return True
            else:
                logger.error(f"Falha no login Sankhya: {data.get('statusMessage')}")
                return False
        except Exception as e:
            logger.error(f"Erro ao conectar na API do Sankhya: {str(e)}")
            return False

    def carregar_fornecedores(self) -> dict:
        """Carrega todos os fornecedores ativos do Sankhya"""
        if not self.jsessionid and not self.login():
            logger.error("Não foi possível autenticar para carregar fornecedores.")
            return {}

        query_url = f"{self.base_url}/service.sbr?serviceName=DbExplorerSP.executeQuery&outputType=json&mgeSession={self.jsessionid}"
        
        # 🔥 CORREÇÃO: Busca apenas fornecedores ATIVOS
        sql_parceiros = "SELECT CODPARC, NOMEPARC, RAZAOSOCIAL FROM TGFPAR WHERE FORNECEDOR = 'S' AND ATIVO = 'S'"
        
        try:
            response = self.session.post(query_url, json={"serviceName": "DbExplorerSP.executeQuery", "requestBody": {"sql": sql_parceiros}}, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != "1":
                logger.warning("Erro ao carregar lista de fornecedores.")
                return {}

            response_body = data.get("responseBody", {})
            fields = [f.get("name") if isinstance(f, dict) else f for f in response_body.get("fieldsMetadata", [])]
            rows = response_body.get("rows", [])

            mapa = {}
            for row in rows:
                item = {}
                values = row.get("localFields", {}).get("localField", []) if isinstance(row, dict) else row
                if isinstance(values, dict):
                    values = [values]
                for idx, field_name in enumerate(fields):
                    if field_name and idx < len(values):
                        val_obj = values[idx]
                        item[field_name] = val_obj.get("$") if isinstance(val_obj, dict) else val_obj
                
                codpar = item.get("CODPARC")
                nomeparc = item.get("NOMEPARC")
                razaosocial = item.get("RAZAOSOCIAL")
                nome = nomeparc or razaosocial
                
                if codpar and nome:
                    cod_str = str(codpar).strip()
                    # 🔥 Adiciona com e sem ponto para garantir matching
                    mapa[cod_str] = nome.strip()
                    if "." in cod_str:
                        mapa[cod_str.replace(".", "")] = nome.strip()
            
            logger.info(f"Carregados {len(mapa)} fornecedores com sucesso.")
            return mapa
            
        except Exception as e:
            logger.error(f"Erro ao carregar fornecedores: {e}")
            return {}

    def carregar_dados_estoque_vendas(self) -> List[Dict[str, Any]]:
        if not self.jsessionid and not self.login():
            raise Exception("Não foi possível autenticar na API do Sankhya.")

        query_url = f"{self.base_url}/service.sbr?serviceName=DbExplorerSP.executeQuery&outputType=json&mgeSession={self.jsessionid}"

        sql_query = """
        WITH V15 AS (
            SELECT 
                ITE.CODPROD,
                SUM(ITE.QTDNEG) AS QTD
            FROM TGFCAB CAB
            INNER JOIN TGFITE ITE ON CAB.NUNOTA = ITE.NUNOTA
            WHERE CAB.DTNEG >= DATEADD(day, -15, CAST(GETDATE() AS DATE))
              AND CAB.STATUSNOTA = 'L'
              AND CAB.TIPMOV = 'V'
            GROUP BY ITE.CODPROD
        ),
        VMA AS (
            SELECT 
                ITE.CODPROD,
                SUM(ITE.QTDNEG) AS QTD
            FROM TGFCAB CAB
            INNER JOIN TGFITE ITE ON CAB.NUNOTA = ITE.NUNOTA
            WHERE CAB.DTNEG >= DATEADD(month, DATEDIFF(month, 0, GETDATE()) - 1, 0)
              AND CAB.DTNEG < DATEADD(month, DATEDIFF(month, 0, GETDATE()), 0)
              AND CAB.STATUSNOTA = 'L'
              AND CAB.TIPMOV = 'V'
            GROUP BY ITE.CODPROD
        ),
        BAR AS (
            SELECT 
                CODPROD,
                MAX(CODBARRA) AS CODBARRA
            FROM TGFBAR
            GROUP BY CODPROD
        )
        SELECT 
            PRO.CODPROD,
            BAR.CODBARRA AS EAN,
            PRO.COMPLDESC AS COMPLEMENTO,
            PRO.DESCRPROD, 
            ISNULL(VEN.APELIDO, PRO.AD_CODVEND) AS SEPARADOR,
            PRO.CODPARCFORN,  -- 🔥 Código do fornecedor
            PRO.CODVOL AS UNIDADEMEDIDA,
            ISNULL(EST.ESTOQUE, 0) AS ESTOQUE,
            ISNULL(EST.RESERVADO, 0) AS RESERVADO,
            (ISNULL(EST.ESTOQUE, 0) - ISNULL(EST.RESERVADO, 0)) AS DISPONIVEL,
            ISNULL(V15.QTD, 0) AS VENDAS_15D,
            ISNULL(VMA.QTD, 0) AS VENDAS_MES_ANTERIOR,
            ISNULL(CUS.CUSREP, 0) AS PRECO_CUSTO,
            ISNULL(EXC.VLRVENDA, 0) AS PRECO_VENDA
        FROM TGFPRO PRO

        LEFT JOIN BAR ON BAR.CODPROD = PRO.CODPROD
        LEFT JOIN TGFVEN VEN ON VEN.CODVEND = PRO.AD_CODVEND
        LEFT JOIN (
            SELECT 
                CODPROD,
                SUM(ESTOQUE) AS ESTOQUE,
                SUM(RESERVADO) AS RESERVADO
            FROM TGFEST
            WHERE TIPO = 'P'
            GROUP BY CODPROD
        ) EST ON EST.CODPROD = PRO.CODPROD

        LEFT JOIN V15 ON V15.CODPROD = PRO.CODPROD
        LEFT JOIN VMA ON VMA.CODPROD = PRO.CODPROD

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
                SELECT 
                    E.CODPROD, 
                    E.VLRVENDA,
                    ROW_NUMBER() OVER (PARTITION BY E.CODPROD ORDER BY E.NUTAB DESC) AS RN
                FROM TGFEXC E
            ) TAB_TEMP WHERE RN = 1
        ) EXC ON EXC.CODPROD = PRO.CODPROD

        WHERE PRO.ATIVO = 'S'
          AND PRO.USOPROD = 'R'
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
                logger.warning(f"Sessão ou resposta inválida da API Sankhya ({data.get('status')}): {data.get('statusMessage')}. Tentando reautenticar...")
                if self.login():
                    query_url = f"{self.base_url}/service.sbr?serviceName=DbExplorerSP.executeQuery&outputType=json&mgeSession={self.jsessionid}"
                    response = self.session.post(query_url, json=payload, timeout=30)
                    response.raise_for_status()
                    data = response.json()
                    if data.get("status") != "1":
                        logger.error(f"Erro Sankhya API após reautenticação: {data.get('statusMessage')}")
                        return []
                else:
                    return []

            response_body = data.get("responseBody", {})
            fields = [f.get("name") if isinstance(f, dict) else f for f in response_body.get("fieldsMetadata", [])]
            rows = response_body.get("rows", [])

            produtos = []
            
            # 🔥 Carrega fornecedores uma única vez
            mapa_fornecedores = self.carregar_fornecedores()
            logger.info(f"Mapa de fornecedores carregado: {len(mapa_fornecedores)} registros")

            for row in rows:
                item = {}
                values = row.get("localFields", {}).get("localField", []) if isinstance(row, dict) else row
                if isinstance(values, dict):
                    values = [values]
                for idx, field_name in enumerate(fields):
                    if field_name and idx < len(values):
                        val_obj = values[idx]
                        item[field_name] = val_obj.get("$") if isinstance(val_obj, dict) else val_obj
                if item:
                    produto = self._normalizar_produto(item, mapa_fornecedores)
                    # 🔥 Log para debug (apenas os primeiros 5 produtos)
                    if len(produtos) < 5:
                        logger.info(f"Produto: {produto.get('codigo')} - Fornecedor: {produto.get('fornecedor')}")
                    produtos.append(produto)

            logger.info(f"Retornados {len(produtos)} produtos de revenda do Sankhya com sucesso.")
            return produtos

        except Exception as e:
            logger.error(f"Erro ao consultar estoque via API Sankhya: {str(e)}")
            raise e


def buscar_dados_estoque_vendas() -> List[Dict[str, Any]]:
    service = SankhyaAPIService()
    return service.carregar_dados_estoque_vendas()