import pymssql
import logging
from typing import List, Dict, Any
import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env ou do próprio servidor (Render)
load_dotenv()

logger = logging.getLogger(__name__)

# Configurações do banco de dados (lidas diretamente do ambiente)
SANKHYA_HOST = os.getenv("SANKHYA_HOST")
SANKHYA_USER = os.getenv("SANKHYA_USER")
SANKHYA_PASSWORD = os.getenv("SANKHYA_PASSWORD")
SANKHYA_DATABASE = os.getenv("SANKHYA_DATABASE")
SANKHYA_PORT = int(os.getenv("SANKHYA_PORT", "1433"))


def buscar_dados_estoque_vendas() -> List[Dict[str, Any]]:
    """
    Conecta ao banco SQL Server do Sankhya e busca dados de estoque e vendas.
    """
    try:
        conn = pymssql.connect(
            server=SANKHYA_HOST,
            user=SANKHYA_USER,
            password=SANKHYA_PASSWORD,
            database=SANKHYA_DATABASE,
            port=SANKHYA_PORT
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