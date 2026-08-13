from pathlib import Path
import math
import re

import pandas as pd


# ============================================================
# CAMINHO DA PLANILHA
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent

PLANILHA = BASE_DIR / "planilhas" / "VENDAS X PRODUTO.xlsx"


# ============================================================
# VARIÁVEL GLOBAL
# ============================================================

df = None


# ============================================================
# CONVERTER NÚMERO
# ============================================================

def converter_numero(valor):

    if valor is None:
        return 0.0

    try:
        if pd.isna(valor):
            return 0.0
    except Exception:
        pass

    if isinstance(valor, (int, float)):

        try:
            if not math.isfinite(float(valor)):
                return 0.0

            return float(valor)

        except Exception:
            return 0.0

    texto = str(valor).strip()

    if not texto:
        return 0.0

    if texto.lower() in [
        "nan",
        "none",
        "null",
        "nat"
    ]:
        return 0.0

    texto = (
        texto
        .replace("R$", "")
        .replace(" ", "")
        .strip()
    )

    # Exemplo:
    # 18.381,02 -> 18381.02

    if "," in texto and "." in texto:

        texto = (
            texto
            .replace(".", "")
            .replace(",", ".")
        )

    # Exemplo:
    # 18381,02 -> 18381.02

    elif "," in texto:

        texto = texto.replace(",", ".")

    try:

        numero = float(texto)

        if not math.isfinite(numero):
            return 0.0

        return numero

    except (ValueError, TypeError):

        return 0.0


# ============================================================
# LIMPAR COLUNAS
# ============================================================

def limpar_colunas(dataframe):

    dataframe = dataframe.copy()

    novas_colunas = []

    for coluna in dataframe.columns:

        nome = str(coluna).strip()

        nome = re.sub(
            r"\s+",
            " ",
            nome
        )

        novas_colunas.append(nome)

    dataframe.columns = novas_colunas

    return dataframe


# ============================================================
# ENCONTRAR COLUNA
# ============================================================

def encontrar_coluna(
    dataframe,
    palavras
):

    for coluna in dataframe.columns:

        nome = str(
            coluna
        ).lower().strip()

        for palavra in palavras:

            if palavra.lower() in nome:

                return coluna

    return None


# ============================================================
# CARREGAR PLANILHA
# ============================================================

def carregar_planilha():

    global df

    if not PLANILHA.exists():

        raise FileNotFoundError(
            f"Planilha não encontrada: {PLANILHA}"
        )

    dataframe = pd.read_excel(
        PLANILHA,
        sheet_name=0
    )

    dataframe = limpar_colunas(
        dataframe
    )

    # Remove linhas totalmente vazias

    dataframe = dataframe.dropna(
        how="all"
    )

    # Limpa textos

    for coluna in dataframe.columns:

        if dataframe[coluna].dtype == "object":

            dataframe[coluna] = dataframe[
                coluna
            ].apply(

                lambda x:
                    str(x).strip()
                    if not pd.isna(x)
                    else ""

            )

    df = dataframe

    # Preparar JSON

    dados = dataframe.astype(
        object
    )

    dados = dados.where(
        pd.notna(dados),
        None
    )

    return dados.to_dict(
        orient="records"
    )


# ============================================================
# GARANTIR PLANILHA CARREGADA
# ============================================================

def garantir_planilha():

    global df

    if df is None or df.empty:

        carregar_planilha()

    return df


# ============================================================
# IDENTIFICAR COLUNAS
# ============================================================

def identificar_colunas(
    dataframe
):

    coluna_produto = encontrar_coluna(

        dataframe,

        [
            "produto",
            "descrição",
            "descricao",
            "item",
            "mercadoria",
            "nome"
        ]

    )

    coluna_volume = encontrar_coluna(

        dataframe,

        [
            "v.mês atual",
            "v.mes atual",
            "v mês atual",
            "v mes atual",
            "volume",
            "quantidade",
            "qtde",
            "qtd",
            "vendido",
            "vendas"
        ]

    )

    return (
        coluna_produto,
        coluna_volume
    )


# ============================================================
# PRODUTOS MAIS VENDIDOS
# ============================================================

def produtos_mais_vendidos():

    dataframe = garantir_planilha()

    coluna_produto = "PRODUTO"

    coluna_volume = "V.MÊS ATUAL"

    # Verificar PRODUTO

    if coluna_produto not in dataframe.columns:

        raise ValueError(

            "Coluna PRODUTO não encontrada. "
            f"Colunas disponíveis: "
            f"{list(dataframe.columns)}"

        )

    # Verificar V.MÊS ATUAL

    if coluna_volume not in dataframe.columns:

        raise ValueError(

            "Coluna V.MÊS ATUAL não encontrada. "
            f"Colunas disponíveis: "
            f"{list(dataframe.columns)}"

        )

    dados = dataframe[
        [
            coluna_produto,
            coluna_volume
        ]
    ].copy()

    # Produto

    dados[
        coluna_produto
    ] = (

        dados[
            coluna_produto
        ]
        .fillna("")
        .astype(str)
        .str.strip()

    )

    # Volume

    dados[
        coluna_volume
    ] = dados[
        coluna_volume
    ].apply(
        converter_numero
    )

    # Remover produtos sem nome

    dados = dados[
        dados[
            coluna_produto
        ] != ""
    ]

    # Somar produtos repetidos

    dados = (

        dados
        .groupby(
            coluna_produto,
            as_index=False
        )[coluna_volume]
        .sum()

    )

    # Ordenar

    dados = dados.sort_values(

        by=coluna_volume,

        ascending=False

    )

    # Padronizar nomes

    dados.columns = [
        "produto",
        "volume"
    ]

    # Garantir números válidos

    dados["volume"] = (

        pd.to_numeric(
            dados["volume"],
            errors="coerce"
        )
        .fillna(0.0)

    )

    dados["volume"] = dados[
        "volume"
    ].apply(

        lambda x:
            float(x)
            if math.isfinite(float(x))
            else 0.0

    )

    return dados.to_dict(
        orient="records"
    )


# ============================================================
# RESUMO DAS VENDAS
# ============================================================

def resumo_vendas():

    ranking = produtos_mais_vendidos()

    total_produtos = len(
        ranking
    )

    total_vendas = sum(

        float(
            item.get(
                "volume",
                0
            ) or 0
        )

        for item in ranking

    )

    if ranking:

        produto_mais_vendido = (
            ranking[0]["produto"]
        )

        quantidade_mais_vendida = float(
            ranking[0]["volume"] or 0
        )

    else:

        produto_mais_vendido = ""

        quantidade_mais_vendida = 0.0

    return {

        "total_produtos":
            total_produtos,

        "total_vendas":
            total_vendas,

        "produto_mais_vendido":
            produto_mais_vendido,

        "quantidade_mais_vendida":
            quantidade_mais_vendida

    }


# ============================================================
# LIMPAR VALOR PARA JSON
# ============================================================

def limpar_valor_json(valor):

    if valor is None:

        return None

    # Verifica NaN / NaT

    try:

        if pd.isna(valor):

            return None

    except Exception:

        pass

    # Números

    if isinstance(
        valor,
        (int, float)
    ):

        try:

            numero = float(valor)

            if not math.isfinite(
                numero
            ):

                return None

            return numero

        except Exception:

            return None

    return valor


# ============================================================
# ANÁLISE DE ESTOQUE
# ============================================================

def analise_estoque():

    dataframe = garantir_planilha()

    # ========================================================
    # COLUNAS DA SUA PLANILHA
    # ========================================================

    coluna_produto = "PRODUTO"

    coluna_unidade = "UNIDADE"

    coluna_estoque = "ESTOQUE"

    coluna_separado = "SEPARADO"

    coluna_vendas = "V.MÊS ATUAL"
    colunas_necessarias = [

        coluna_produto,

        coluna_unidade,

        coluna_estoque,

        coluna_separado,

        coluna_vendas




    ]  




    # ========================================================
    # VERIFICAR COLUNAS
    # ========================================================

    faltando = [

        coluna

        for coluna in colunas_necessarias

        if coluna not in dataframe.columns

    ]

    if faltando:

        raise ValueError(

            f"Colunas não encontradas: "
            f"{faltando}. "

            f"Colunas disponíveis: "
            f"{list(dataframe.columns)}"

        )

    # ========================================================
    # SELECIONAR DADOS
    # ========================================================

    dados = dataframe[
        colunas_necessarias
    ].copy()

    # ========================================================
    # LIMPAR PRODUTO
    # ========================================================

    dados[
        coluna_produto
    ] = (

        dados[
            coluna_produto
        ]
        .fillna("")
        .astype(str)
        .str.strip()

    )

    # ========================================================
    # UNIDADE
    # ========================================================

    dados[
        coluna_unidade
    ] = (
        dados[
            coluna_unidade
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # ========================================================
    # CONVERTER NÚMEROS
    # ========================================================

    dados[
        coluna_estoque
    ] = dados[
        coluna_estoque
    ].apply(
        converter_numero
    )

    dados[
        coluna_separado
    ] = dados[
        coluna_separado
    ].apply(
        converter_numero
    )

    dados[
        coluna_vendas
    ] = dados[
        coluna_vendas
    ].apply(
        converter_numero
    )

    # ========================================================
    # EVITAR NEGATIVOS
    # ========================================================

    dados[
        coluna_estoque
    ] = dados[
        coluna_estoque
    ].clip(
        lower=0
    )

    dados[
        coluna_separado
    ] = dados[
        coluna_separado
    ].clip(
        lower=0
    )

    dados[
        coluna_vendas
    ] = dados[
        coluna_vendas
    ].clip(
        lower=0
    )

    # ========================================================
    # ESTOQUE DISPONÍVEL
    # ========================================================

    dados[
        "ESTOQUE_DISPONIVEL"
    ] = (

        dados[
            coluna_estoque
        ]

        -

        dados[
            coluna_separado
        ]

    ).clip(
        lower=0
    )

    # ========================================================
    # MÉDIA DIÁRIA
    # ========================================================

    # Considerando 30 dias

    dados[
        "MEDIA_DIARIA"
    ] = (

        dados[
            coluna_vendas
        ] / 30

    )

    # ========================================================
    # DIAS DE ESTOQUE
    # ========================================================

    def calcular_dias(
        linha
    ):

        media = float(
            linha[
                "MEDIA_DIARIA"
            ]
        )

        estoque = float(
            linha[
                "ESTOQUE_DISPONIVEL"
            ]
        )

        # Sem venda:
        # não existe cobertura calculável

        if media <= 0:

            return None

        return (
            estoque / media
        )

    dados[
        "DIAS_ESTOQUE"
    ] = dados.apply(

        calcular_dias,

        axis=1

    )

    # ========================================================
    # META DE ESTOQUE
    # ========================================================

    META_DIAS = 15

    dados[
        "ESTOQUE_META"
    ] = (

        dados[
            "MEDIA_DIARIA"
        ]

        *

        META_DIAS

    )

    # ========================================================
    # SUGESTÃO DE COMPRA
    # ========================================================

    def calcular_compra(
        linha
    ):

        media = float(
            linha[
                "MEDIA_DIARIA"
            ]
        )

        estoque = float(
            linha[
                "ESTOQUE_DISPONIVEL"
            ]
        )

        if media <= 0:

            return 0.0

        meta = (
            media *
            META_DIAS
        )

        necessidade = (
            meta -
            estoque
        )

        if necessidade <= 0:

            return 0.0

        # Arredondar para cima

        return float(
            math.ceil(
                necessidade
            )
        )

    dados[
        "SUGESTAO_COMPRA"
    ] = dados.apply(

        calcular_compra,

        axis=1

    )

    # ========================================================
    # STATUS
    # ========================================================

    def calcular_status(
        linha
    ):

        vendas = float(
            linha[
                coluna_vendas
            ]
        )

        estoque = float(
            linha[
                "ESTOQUE_DISPONIVEL"
            ]
        )

        # Produto sem venda

        if vendas <= 0:

            if estoque > 0:

                return "Estoque parado"

            return "Sem venda"

        # Sem estoque

        if estoque <= 0:

            return "Comprar urgente"

        dias = linha[
            "DIAS_ESTOQUE"
        ]

        if dias is None:

            return "Sem venda"

        # Menos de 3 dias

        if dias < 3:

            return "Comprar urgente"

        # Até 7 dias

        if dias <= 7:

            return "Comprar"

        return "Estoque suficiente"

    dados[
        "STATUS"
    ] = dados.apply(

        calcular_status,

        axis=1

    )

    # ========================================================
    # PRIORIDADE
    # ========================================================

    prioridades = {

        "Comprar urgente": 1,

        "Comprar": 2,

        "Estoque parado": 3,

        "Estoque suficiente": 4,

        "Sem venda": 5

    }

    dados[
        "PRIORIDADE"
    ] = (

        dados[
            "STATUS"
        ]
        .map(prioridades)
        .fillna(99)
        .astype(int)

    )

    # ========================================================
    # PERCENTUAL DA META
    # ========================================================

    def calcular_percentual(
        linha
    ):

        meta = float(
            linha[
                "ESTOQUE_META"
            ]
        )

        estoque = float(
            linha[
                "ESTOQUE_DISPONIVEL"
            ]
        )

        if meta <= 0:

            return 0.0

        return (
            estoque /
            meta *
            100
        )

    dados[
        "PERCENTUAL_META"
    ] = dados.apply(

        calcular_percentual,

        axis=1

    )

    # ========================================================
    # RESULTADO
    # ========================================================

    resultado = dados[

        [

            coluna_produto,

            coluna_unidade,

            coluna_estoque,

            coluna_separado,

            "ESTOQUE_DISPONIVEL",

            coluna_vendas,

            "MEDIA_DIARIA",

            "DIAS_ESTOQUE",

            "ESTOQUE_META",

            "SUGESTAO_COMPRA",

            "PERCENTUAL_META",

            "STATUS",

            "PRIORIDADE"

        ]

    ].copy()

    # ========================================================
    # NOMES PARA O FRONTEND
    # ========================================================

    resultado.columns = [

        "produto",

        "unidade",

        "estoque",

        "separado",

        "estoque_disponivel",

        "vendas_mes",

        "media_diaria",

        "dias_estoque",

        "estoque_meta",

        "sugestao_compra",

        "percentual_meta",

        "status",

        "prioridade"

    ]

    # ========================================================
    # REMOVER PRODUTOS SEM NOME
    # ========================================================

    resultado = resultado[
        resultado[
            "produto"
        ] != ""
    ]

    # ========================================================
    # ORDENAR
    # ========================================================

    resultado = resultado.sort_values(

        by=[

            "prioridade",

            "sugestao_compra",

            "vendas_mes"

        ],

        ascending=[

            True,

            False,

            False

        ]

    )

    # ========================================================
    # LIMPAR TODOS OS NaN / INF
    # ========================================================

    for coluna in resultado.columns:

        resultado[
            coluna
        ] = resultado[
            coluna
        ].apply(
            limpar_valor_json
        )

    # ========================================================
    # ARREDONDAR
    # ========================================================

    colunas_2_casas = [

        "estoque",

        "separado",

        "estoque_disponivel",

        "vendas_mes",

        "media_diaria",

        "estoque_meta",

        "sugestao_compra",

        "percentual_meta"

    ]

    for coluna in colunas_2_casas:

        resultado[
            coluna
        ] = resultado[
            coluna
        ].apply(

            lambda valor:

                round(
                    float(valor),
                    2
                )

                if valor is not None

                else None

        )

    # ========================================================
    # DIAS DE ESTOQUE
    # ========================================================

    resultado[
        "dias_estoque"
    ] = resultado[
        "dias_estoque"
    ].apply(

        lambda valor:

            round(
                float(valor),
                1
            )

            if valor is not None

            else None

    )

    # ========================================================
    # LIMPEZA FINAL
    # ========================================================

    for coluna in resultado.columns:

        resultado[
            coluna
        ] = resultado[
            coluna
        ].apply(
            limpar_valor_json
        )

    # ========================================================
    # RETORNAR JSON
    # ========================================================

    return resultado.to_dict(
        orient="records"
    )


# ============================================================
# RESUMO DO ESTOQUE
# ============================================================

def resumo_estoque():

    dados = analise_estoque()

    total_produtos = len(
        dados
    )

    comprar_urgente = sum(

        1

        for item in dados

        if item[
            "status"
        ] == "Comprar urgente"

    )

    comprar = sum(

        1

        for item in dados

        if item[
            "status"
        ] == "Comprar"

    )

    estoque_parado = sum(

        1

        for item in dados

        if item[
            "status"
        ] == "Estoque parado"

    )

    estoque_suficiente = sum(

        1

        for item in dados

        if item[
            "status"
        ] == "Estoque suficiente"

    )

    sem_venda = sum(

        1

        for item in dados

        if item[
            "status"
        ] == "Sem venda"

    )

    quantidade_sugerida = sum(

        float(
            item.get(
                "sugestao_compra",
                0
            ) or 0
        )

        for item in dados

    )

    return {

        "total_produtos":
            total_produtos,

        "comprar_urgente":
            comprar_urgente,

        "comprar":
            comprar,

        "estoque_parado":
            estoque_parado,

        "estoque_suficiente":
            estoque_suficiente,

        "sem_venda":
            sem_venda,

        "quantidade_sugerida_compra":
            round(
                quantidade_sugerida,
                2
            )

    }


# ============================================================
# O QUE COMPRAR
# ============================================================

def o_que_comprar():

    dados = analise_estoque()

    resultado = [

        item

        for item in dados

        if item[
            "status"
        ] in [

            "Comprar urgente",

            "Comprar"

        ]

        and float(
            item.get(
                "sugestao_compra",
                0
            ) or 0
        ) > 0

    ]

    return resultado


# ============================================================
# TESTE
# ============================================================

if __name__ == "__main__":

    print("=" * 70)

    print(
        "COMPRAS INTELIGENTES"
    )

    print("=" * 70)

    print()

    print(
        "Planilha:"
    )

    print(
        PLANILHA
    )

    print()

    print(
        "Existe:",
        PLANILHA.exists()
    )

    print()

    dataframe = garantir_planilha()

    print(
        "TOTAL DE LINHAS:",
        len(dataframe)
    )

    print()

    print(
        "COLUNAS:"
    )

    print(
        dataframe.columns.tolist()
    )

    print()

    print(
        "TOP 10 PRODUTOS:"
    )

    ranking = produtos_mais_vendidos()

    for numero, item in enumerate(

        ranking[:10],

        start=1

    ):

        print(

            f"{numero:02d} - "
            f"{item['produto']} | "
            f"{item['volume']:.2f}"

        )

    print()

    print(
        "RESUMO:"
    )

    print(
        resumo_vendas()
    )

    print()

    print(
        "RESUMO ESTOQUE:"
    )

    print(
        resumo_estoque()
    )

    print()

    print(
        "TOP 10 O QUE COMPRAR:"
    )

    compras = o_que_comprar()

    for numero, item in enumerate(

        compras[:10],

        start=1

    ):

        print(

            f"{numero:02d} - "
            f"{item['produto']} | "
            f"Unidade: {item['unidade']} | "
            f"Status: {item['status']} | "
            f"Estoque: {item['estoque_disponivel']} | "
            f"Venda/mês: {item['vendas_mes']} | "
            f"Comprar: {item['sugestao_compra']}"

        )

    print()

    print(
        "TESTE FINALIZADO"
    )
