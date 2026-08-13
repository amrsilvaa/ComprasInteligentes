import os
import sys
import logging
from typing import List, Dict, Any

# Ajusta caminhos no sys.path para garantir importações corretas no Render e ambiente local
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(BASE_DIR)

for path in [BASE_DIR, ROOT_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    from backend.config import settings  # type: ignore
except ImportError:
    import config  # type: ignore
    settings = config.settings

logger = logging.getLogger(__name__)


class ExcelService:
    def __init__(self):
        pass

    def processar_dados(self, dados: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Processa e formata dados de produtos e vendas caso seja necessário.
        """
        if not dados:
            return []

        resultado = []
        for item in dados:
            vendas_15d = item.get('vendas_15d', 0) or 0
            estoque = item.get('estoque', 0) or 0
            sugestao = max(0, vendas_15d - estoque)

            item_processado = {
                **item,
                'sugestao_compra': sugestao,
                'status': 'REPOR' if sugestao > 0 else 'OK'
            }
            resultado.append(item_processado)

        return resultado