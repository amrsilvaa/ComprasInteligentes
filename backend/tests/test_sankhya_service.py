from services.sankhya_service import SankhyaAPIService


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

    # ✅ Passando mapa de fornecedores vazio
    item = SankhyaAPIService._normalizar_produto(payload, {})

    assert item["codigo"] == 101
    assert item["descricao"] == "Produto Teste"
    assert item["estoque"] == 120  # Estoque bruto
    assert item["estoque_disponivel"] == 90  # Disponível = estoque - reservado
    assert item["estoque_minimo"] == 0.0  # Valor padrão
    assert item["sugestao_compra"] == 0  # 50 - 90 = 0 (não pode ser negativo)