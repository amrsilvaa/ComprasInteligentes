import pymssql
import logging
from typing import List, Dict, Any
import sys
import os

# Resolvendo caminhos para importação do config
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(BASE_DIR)

for path in [BASE_DIR, ROOT_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    import config  # type: ignore
    settings = config.settings
except ModuleNotFoundError:
    import backend.config as config  # type: ignore
    settings = config.settings

logger = logging.getLogger(__name__)


def buscar_dados_estoque_vendas() -> List[Dict[str, Any]]:
    """
    Conecta ao banco SQL Server do Sankhya e busca dados de estoque e vendas.
    """
    try:
        conn = pymssql.connect(
            server=settings.SANKHYA_HOST,
            user=settings.SANKHYA_USER,
            password=settings.SANKHYA_PASSWORD,
            database=settings.SANKHYA_DATABASE,
            port=settings.SANKHYA_PORT
        )
        
        cursor = conn.cursor(as_dict=True)
        
        query = """
        WITH Vendas15D AS (
            -- Vendas dos últimos 15 dias (exclui devoluções e transferências)
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
              AND TOP.ATUALEST = 'B' -- Baixa estoque (Vendas efetivas)
            GROUP BY ITE.CODPROD
        ),
        VendasMesAnt AS (
            -- Vendas do mês anterior completo
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
        ORDER BY PRO.DESCRPROD;
        """
        
        cursor.execute(query)
        result = cursor.fetchall()
        
        cursor.close()
        conn.close()
        return result

    except Exception as e:
        logger.error(f"Erro ao buscar dados do Sankhya: {str(e)}")
        raise e