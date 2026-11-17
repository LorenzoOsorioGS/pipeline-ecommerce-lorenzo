"""Regras de validação V1–V9 com casos sintéticos no formato dos CSVs reais."""
import pandas as pd

from pipeline import validate as V


def _df(**colunas):
    df = pd.DataFrame(colunas, dtype=str)
    df["_linha"] = df.index + 2
    return df


def test_v1_detecta_linha_toda_vazia():
    df = _df(a=["B-1", "", " "], b=["x", "", ""])
    assert list(V.v1_linhas_vazias(df)) == [False, True, True]


def test_v2_padrao_e_duplicidade():
    pedidos = _df(**{"Order ID": ["B-25601", "B-25601", "X-1", ""]})
    fora, dup = V.v2_order_id_invalido(pedidos)
    assert list(fora) == [False, False, True, True]
    assert list(dup) == [False, True, False, False]


def test_v3_data_invalida():
    pedidos = _df(**{"Order Date": ["01-04-2018", "31-02-2019", "2018-04-01"]})
    assert list(V.v3_data_invalida(pedidos)) == [False, True, True]


def test_v6_valores():
    itens = _df(Amount=["10.00", "0", "x", "5"], Profit=["-3", "1", "1", "abc"], Quantity=["2", "1", "1", "1"])
    assert list(V.v6_numero_invalido(itens)) == [False, True, True, True]


def test_v7_subcategoria_tem_que_pertencer_a_categoria():
    itens = _df(Category=["Furniture", "Furniture", "Toys"], **{"Sub-Category": ["Tables", "Saree", "Tables"]})
    assert list(V.v7_categoria_invalida(itens)) == [False, True, True]


def test_v8_meta_invalida_e_duplicada():
    metas = _df(**{"Month of Order Date": ["Apr-18", "Apr-18", "Abr-18"], "Category": ["Furniture"] * 3,
                   "Target": ["10400.00", "10400.00", "1"]})
    ruim, dup = V.v8_meta_invalida(metas)
    assert list(ruim) == [False, False, True]
    assert list(dup) == [False, True, False]


def test_v9_delhi_corrigivel_e_par_desconhecido_alerta():
    pedidos = _df(City=["Delhi", "Chandigarh", "Atlantis"], State=["Madhya Pradesh", "Haryana", "Goa"])
    corrigivel, desconhecido = V.v9_cidade_estado(pedidos)
    assert list(corrigivel) == [True, False, False]
    assert list(desconhecido) == [False, False, True]
