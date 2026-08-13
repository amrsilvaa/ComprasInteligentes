import cx_Oracle
import logging
from typing import List, Dict, Any
from backend.config import settings

logger = logging.getLogger(__name__)

class SankhyaService:
    def __init__(self):
        self.dsn = cx_Oracle.makedsn(
            settings.SANKHYA_HOST,
            settings.SANKHYA_PORT,
            service_name=settings.SANKHYA_SERVICE_NAME
        )
        self.user = settings.SANKHYA_USER
        self.password = settings.SANKHYA_PASSWORD

    def _get_connection(self):
        return cx_Oracle.connect(
            user=self.user,
            password=self.password,
            dsn=self.dsn
        )

    def get_sugestao_compras(self) -> List[Dict[str, Any]]:
        query = """
        WITH 
        Vendas15Dias AS (
            SELECT 
                ite.CODPROD,
                ISNULL(SUM(ite.QTDNEG), 0) AS QTD_15D
            FROM TGFITE ite WITH (NOLOCK)
            INNER JOIN TGFCAB cab WITH (NOLOCK) ON cab.NUNOTA = ite.NUNOTA
            WHERE cab.DTNEG >= GETDATE() - 15
              AND cab.STATUSNOTA = 'L'
              AND cab.CODEMP = 1
            GROUP BY ite.CODPROD
        ),
        VendasMesAnterior AS (
            SELECT 
                ite.CODPROD,
                ISNULL(SUM(ite.QTDNEG), 0) AS QTD_MES_ANT
            FROM TGFITE ite WITH (NOLOCK)
            INNER JOIN TGFCAB cab WITH (NOLOCK) ON cab.NUNOTA = ite.NUNOTA
            WHERE cab.DTNEG >= DATEADD(month, -1, DATEADD(month, DATEDIFF(month, 0, GETDATE()), 0))
              AND cab.DTNEG < DATEADD(month, DATEDIFF(month, 0, GETDATE()), 0)
              AND cab.STATUSNOTA = 'L'
              AND cab.CODEMP = 1
            GROUP BY ite.CODPROD
        ),
        EstoqueTotal AS (
            SELECT 
                e.CODPROD,
                ISNULL(SUM(
                    CASE 
                        WHEN (e.ESTOQUE - e.RESERVADO) < 0 THEN 0 
                        ELSE (e.ESTOQUE - e.RESERVADO) 
                    END
                ), 0) AS ESTOQUE,
                ISNULL(MAX(e.ESTMIN), 0) AS ESTMIN
            FROM TGFEST e WITH (NOLOCK)
            WHERE e.CODEMP = 1
            GROUP BY e.CODPROD
        )
        SELECT 
            p.CODPROD AS CODIGO,
            p.DESCRPROD AS DESCRICAO,
            p.COMPLPROD,
            p.CODVOL AS UNID,
            ISNULL(e.ESTOQUE, 0) AS ESTOQUE,
            ISNULL(e.ESTMIN, 0) AS ESTMIN,
            ISNULL(v15.QTD_15D, 0) AS VENDAS_15D,
            ISNULL(vma.QTD_MES_ANT, 0) AS VENDAS_MES_ANT,
            ISNULL(cus.CUSSEMICM, 0) AS CUSTO_UN,
            ISNULL(exc.VLRVENDA, 0) AS PRECO_VENDA
        FROM TGFPRO p WITH (NOLOCK)
        LEFT JOIN EstoqueTotal e ON e.CODPROD = p.CODPROD
        LEFT JOIN Vendas15Dias v15 ON v15.CODPROD = p.CODPROD
        LEFT JOIN VendasMesAnterior vma ON vma.CODPROD = p.CODPROD
        LEFT JOIN TGFCUS cus WITH (NOLOCK) ON cus.CODPROD = p.CODPROD AND cus.CODEMP = 1
        LEFT JOIN TGFEXC exc WITH (NOLOCK) ON exc.CODPROD = p.CODPROD AND exc.NUTAB = 1
        WHERE p.ATIVO = 'S'
          AND (ISNULL(v15.QTD_15D, 0) > 0 OR ISNULL(e.ESTOQUE, 0) > 0)
        ORDER BY VENDAS_15D DESC
        """

        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(query)
            
            columns = [col[0].lower() for col in cursor.description]
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                item = dict(zip(columns, row))
                
                vendas_15d = item.get('vendas_15d', 0)
                estoque = item.get('estoque', 0)
                sugestao = max(0, vendas_15d - estoque)
                
                item['sugestao_compra'] = sugestao
                item['status'] = 'REPOR' if sugestao > 0 else 'OK'
                
                result.append(item)
                
            cursor.close()
            conn.close()
            return result
            
        except Exception as e:
            logger.error(f"Erro ao buscar dados do Sankhya: {str(e)}")
            raise e