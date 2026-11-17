"""Regras de transformação T3–T12 com casos tirados dos dados reais."""
import hashlib
from decimal import Decimal

import pandas as pd
import pytest

from pipeline import transform as T


def test_t3_data_ambigua_e_lida_como_dia_mes_ano():
    # "01-04-2018" tem dia ≤ 12: um parser que adivinha leria 4 de janeiro
    datas = T.t3_converter_data(pd.Series(["01-04-2018", "31-03-2019", "08-04-2018", "12-11-2018"]))
    assert [d.strftime("%Y-%m-%d") for d in datas] == ["2018-04-01", "2019-03-31", "2018-04-08", "2018-11-12"]


def test_t3_rejeita_formato_errado():
    with pytest.raises(ValueError):
        T.t3_converter_data(pd.Series(["2018-04-01"]))


def test_t4_competencia_e_mes_fiscal_indiano():
    datas = pd.to_datetime(pd.Series(["2018-04-01", "2018-12-15", "2019-03-31"]))
    competencia, fiscal = T.t4_competencia(datas)
    assert list(competencia) == ["2018-04", "2018-12", "2019-03"]
    assert list(fiscal) == [1, 9, 12]  # abril = 1, março = 12


def test_t1_remove_espaco_de_kerala():
    df, n = T.t1_remover_espacos(pd.DataFrame({"State": ["Kerala ", "Goa"]}))
    assert list(df["State"]) == ["Kerala", "Goa"] and n == 1


def test_t5_corrige_delhi_e_mantem_chandigarh_nos_dois_estados():
    pedidos = pd.DataFrame({"order_id": ["B-1", "B-2", "B-3"], "cidade": ["Delhi", "Chandigarh", "Chandigarh"],
                            "estado": ["Madhya Pradesh", "Punjab", "Haryana"]})
    corrigido, log = T.t5_corrigir_cidade_estado(pedidos)
    assert list(corrigido["estado"]) == ["Delhi", "Punjab", "Haryana"]
    assert len(log) == 1


def test_t7_posicao_segue_a_ordem_do_arquivo_dentro_do_pedido():
    itens = pd.DataFrame({"order_id": ["B-2", "B-1", "B-1", "B-2"], "_linha": [4, 2, 3, 5]})
    assert list(T.t7_posicao(itens)) == [1, 1, 2, 2]


def test_t9_flags_com_o_pedido_real_b25608():
    itens = pd.DataFrame({
        "valor": [Decimal(v) for v in ("1364.00", "476.00", "257.00", "856.00")],
        "lucro": [Decimal(v) for v in ("-1864.00", "0.00", "23.00", "385.00")],
    })
    # com só 4 itens o IQR muda; o que importa aqui é a regra de cada flag
    marcados, info = T.t9_flags(itens)
    assert list(marcados["flag_prejuizo"]) == [True, False, False, False]  # lucro 0 não é prejuízo
    assert list(marcados["flag_prejuizo_maior_que_venda"]) == [True, False, False, False]
    assert info["prejuizo"] == 1


def test_t9_limite_iqr_no_conjunto_completo():
    # Q1 = 45 e Q3 = 322 no dataset real → limite 737,50 (profiling da N2)
    valores = [Decimal("45")] * 3 + [Decimal("322")] * 3
    serie = pd.DataFrame({"valor": valores, "lucro": [Decimal("1")] * 6})
    _, info = T.t9_flags(serie)
    assert info["limite_atipico"] == "737.50"


def test_t10_hmac_deterministico_depende_da_chave_e_nao_e_sha256_puro():
    a = T.t10_pseudonimizar("Aarushi", b"chave-1")
    assert a == T.t10_pseudonimizar("  aarushi ", b"chave-1")  # normaliza espaço e maiúsculas
    assert a != T.t10_pseudonimizar("Aarushi", b"chave-2")      # sem a chave não se refaz
    assert a != hashlib.sha256(b"aarushi").hexdigest()[:16]     # não é um hash simples
    assert len(a) == 16 and "Aarushi" not in a


def test_t11_mes_da_meta_vira_competencia_e_id():
    metas = pd.DataFrame({"mes_texto": ["Apr-18", "Mar-19"], "categoria": ["Furniture", "Clothing"],
                          "valor_alvo": [Decimal("10400.00"), Decimal("16000.00")]})
    r = T.t11_meta(metas)
    assert list(r["meta_id"]) == ["2018-04#Furniture", "2019-03#Clothing"]
    assert list(r["mes_fiscal"]) == [1, 12]


def test_t12_totais_e_documento_do_b25608():
    pedidos = pd.DataFrame({"order_id": ["B-25608"], "data_pedido": [pd.Timestamp("2018-04-08")],
                            "competencia": ["2018-04"], "mes_fiscal": [1], "cliente_ref": ["x"],
                            "cidade": ["Chennai"], "estado": ["Tamil Nadu"]})
    itens = pd.DataFrame({
        "order_id": ["B-25608"] * 4, "posicao": [1, 2, 3, 4],
        "categoria": ["Furniture", "Furniture", "Clothing", "Electronics"],
        "subcategoria": ["Tables", "Chairs", "Hankerchief", "Printers"], "quantidade": [5, 3, 5, 6],
        "valor": [Decimal(v) for v in ("1364.00", "476.00", "257.00", "856.00")],
        "lucro": [Decimal(v) for v in ("-1864.00", "0.00", "23.00", "385.00")],
    })
    p = T.t12_totais(pedidos, itens).iloc[0]
    assert p["total_valor"] == Decimal("2953.00") and p["total_lucro"] == Decimal("-1456.00")
    assert p["margem_pct"] == -49.31 and p["qtd_unidades"] == 19
    assert p["categorias"] == ["Clothing", "Electronics", "Furniture"]  # ordem alfabética
    assert not p["item_unico"]
