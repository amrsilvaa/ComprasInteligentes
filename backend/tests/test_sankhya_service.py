from backend.services.sankhya_service import SankhyaAPIService


def test_normaliza_dados_de_saldo_do_sankhya():
    payload = {
        "CODPROD": 101,
        "DESCRPROD": "Produto Teste",
        "ESTOQUE": 120,
        "RESERVADO": 30,
        "DISPONIVEL": 90,
        "VENDAS_15D": 50,
        "ESTOQUE_MINIMO": 20,
    }

    item = SankhyaAPIService._normalizar_produto(payload)

    assert item["codigo"] == 101
    assert item["descricao"] == "Produto Teste"
    assert item["estoque"] == 90
    assert item["estoque_disponivel"] == 90
    assert item["estoque_minimo"] == 20
    assert item["sugestao_compra"] == 0
