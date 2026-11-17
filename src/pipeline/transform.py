"""Etapa 3 – Transform: regras T1–T12 da N2 (seção 5.4). Saída em Parquet (camada prata).

Entrada: data/processed/_validado/*.parquet (linhas aprovadas na validação, ainda como texto).
Saída:   data/processed/pedidos.parquet, itens.parquet, metas.parquet e _carga.json.
A montagem do documento do MongoDB (T12) também fica aqui, para a regra ficar num lugar só.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from . import config
from .referencias import CORRECOES_CIDADE_ESTADO
from .validate import PASTA_VALIDADO

log = logging.getLogger("transform")
CENTAVO = Decimal("0.01")


def _dec(texto: str) -> Decimal:
    return Decimal(texto).quantize(CENTAVO, rounding=ROUND_HALF_UP)


# ------------------------------------------------------------------------------------------- regras

def t1_remover_espacos(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """T1 – remove espaços nas pontas de todos os campos texto (ex.: "Kerala " em 16 pedidos)."""
    df = df.copy()
    alterados = 0
    for col in df.columns:
        if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
            limpo = df[col].astype(str).str.strip()
            alterados += int((limpo != df[col].astype(str)).sum())
            df[col] = limpo
    return df, alterados


RENOMEAR = {
    "pedidos": {"Order ID": "order_id", "Order Date": "data_texto", "CustomerName": "cliente_nome",
                "State": "estado", "City": "cidade"},
    "itens": {"Order ID": "order_id", "Amount": "valor", "Profit": "lucro", "Quantity": "quantidade",
              "Category": "categoria", "Sub-Category": "subcategoria"},
    "metas": {"Month of Order Date": "mes_texto", "Category": "categoria", "Target": "valor_alvo"},
}


def t2_renomear(df: pd.DataFrame, tabela: str) -> pd.DataFrame:
    """T2 – renomeia as colunas para snake_case em português (sem espaço nem hífen)."""
    return df.rename(columns=RENOMEAR[tabela])


def t3_converter_data(texto: pd.Series) -> pd.Series:
    """T3 – converte Order Date com formato explícito dd-mm-aaaa.

    Formato explícito porque 193 das 500 datas têm dia ≤ 12: "01-04-2018" seria lido como 4 de janeiro
    por um parser que adivinha o formato. Aqui é sempre 1º de abril.
    """
    return pd.to_datetime(texto, format="%d-%m-%Y", errors="raise")


def t4_competencia(datas: pd.Series) -> tuple[pd.Series, pd.Series]:
    """T4 – deriva competencia (AAAA-MM) e mes_fiscal (abril = 1 … março = 12, ano fiscal indiano)."""
    competencia = datas.dt.strftime("%Y-%m")
    mes_fiscal = ((datas.dt.month - 4) % 12 + 1).astype(int)
    return competencia, mes_fiscal


def t5_corrigir_cidade_estado(pedidos: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """T5 – corrige pares cidade × estado conhecidos (Delhi/Madhya Pradesh → Delhi/Delhi).

    Chandigarh fica nos dois estados (Punjab e Haryana) porque é capital dos dois: não é erro.
    """
    pedidos = pedidos.copy()
    corrigidos = []
    for (cidade, estado), (nova_cidade, novo_estado) in CORRECOES_CIDADE_ESTADO.items():
        alvo = (pedidos["cidade"] == cidade) & (pedidos["estado"] == estado)
        for oid in pedidos.loc[alvo, "order_id"]:
            corrigidos.append(f"{oid}: {cidade}/{estado} → {nova_cidade}/{novo_estado}")
        pedidos.loc[alvo, ["cidade", "estado"]] = [nova_cidade, novo_estado]
    return pedidos, corrigidos


def t6_tipar(itens: pd.DataFrame, metas: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """T6 – valor, lucro e valor_alvo viram Decimal (decimal128 no Mongo); quantidade vira inteiro.

    Dinheiro em double geraria centavos fantasmas na soma, e a conciliação (OE1) exige igualdade exata.
    """
    itens, metas = itens.copy(), metas.copy()
    itens["valor"] = itens["valor"].map(_dec)
    itens["lucro"] = itens["lucro"].map(_dec)
    itens["quantidade"] = itens["quantidade"].astype(int)
    metas["valor_alvo"] = metas["valor_alvo"].map(_dec)
    return itens, metas


def t7_posicao(itens: pd.DataFrame) -> pd.Series:
    """T7 – numera os itens: posicao = ordem do item dentro do pedido, na ordem do arquivo.

    O dataset não tem ID de item e 432 linhas repetem pedido + subcategoria, então a chave do item
    é order_id + posicao.
    """
    ordenado = itens.sort_values("_linha")
    return (ordenado.groupby("order_id").cumcount() + 1).reindex(itens.index).astype(int)


def t8_preco_unitario(itens: pd.DataFrame) -> pd.Series:
    """T8 – preco_unitario = valor ÷ quantidade, com 2 casas."""
    return pd.Series([(v / q).quantize(CENTAVO, rounding=ROUND_HALF_UP)
                      for v, q in zip(itens["valor"], itens["quantidade"])], index=itens.index)


def t9_flags(itens: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """T9 – marca (não remove) prejuízo, valor atípico pelo IQR e prejuízo maior que a venda (decisão D4).

    Limite atípico = Q3 + 1,5 × IQR do valor, calculado sobre todos os itens desta carga.
    """
    itens = itens.copy()
    valores = itens["valor"].astype(float)
    q1, q3 = valores.quantile(0.25), valores.quantile(0.75)
    limite = Decimal(str(q3 + 1.5 * (q3 - q1))).quantize(CENTAVO)
    itens["flag_prejuizo"] = itens["lucro"].map(lambda x: x < 0)
    itens["flag_valor_atipico"] = itens["valor"].map(lambda x: x > limite)
    itens["flag_prejuizo_maior_que_venda"] = [lc < -vl for vl, lc in zip(itens["valor"], itens["lucro"])]
    info = {"q1": float(q1), "q3": float(q3), "limite_atipico": str(limite),
            "prejuizo": int(itens["flag_prejuizo"].sum()),
            "valor_atipico": int(itens["flag_valor_atipico"].sum()),
            "prejuizo_maior_que_venda": int(itens["flag_prejuizo_maior_que_venda"].sum())}
    return itens, info


def t10_pseudonimizar(nome: str, chave: bytes) -> str:
    """T10 – cliente_ref = HMAC-SHA256(chave, nome normalizado), 16 hex. O nome não segue adiante.

    HMAC com chave, e não SHA-256 puro: com só 332 nomes, um hash sem chave seria revertido
    testando uma lista de nomes comuns. O mesmo nome gera sempre o mesmo código (carga idempotente).
    """
    return hmac.new(chave, nome.strip().casefold().encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def t11_meta(metas: pd.DataFrame) -> pd.DataFrame:
    """T11 – "Apr-18" → competencia "2018-04", mes_fiscal e _id = "2018-04#Categoria"."""
    metas = metas.copy()
    mes = pd.to_datetime(metas["mes_texto"], format="%b-%y")
    metas["competencia"], metas["mes_fiscal"] = t4_competencia(mes)
    metas["meta_id"] = metas["competencia"] + "#" + metas["categoria"]
    return metas[["meta_id", "competencia", "mes_fiscal", "categoria", "valor_alvo"]]


def t12_totais(pedidos: pd.DataFrame, itens: pd.DataFrame) -> pd.DataFrame:
    """T12 – calcula os totais do pedido. Categorias em ordem alfabética para que
    "Clothing + Electronics" seja sempre a mesma combinação na análise A3."""
    g = itens.groupby("order_id")
    tot = pd.DataFrame({
        "total_valor": g["valor"].apply(lambda s: sum(s, Decimal("0"))),
        "total_lucro": g["lucro"].apply(lambda s: sum(s, Decimal("0"))),
        "qtd_itens": g.size().astype(int),
        "qtd_unidades": g["quantidade"].sum().astype(int),
        "categorias": g["categoria"].apply(lambda s: sorted(set(s))),
    })
    tot["margem_pct"] = [round(float(lc / vl * 100), 2) for vl, lc in zip(tot["total_valor"], tot["total_lucro"])]
    tot["item_unico"] = tot["qtd_itens"] == 1
    return pedidos.merge(tot, left_on="order_id", right_index=True, how="inner")


# ------------------------------------------------------------------------------- montagem (T12)

def montar_documento_pedido(p: dict, itens: list[dict], carga: dict) -> dict:
    """T12 – monta o agregado do pedido no formato da N2 (seção 4.2): itens embutidos + totais."""
    from bson.decimal128 import Decimal128

    return {
        "_id": p["order_id"],
        "data_pedido": pd.Timestamp(p["data_pedido"]).to_pydatetime(),
        "competencia": p["competencia"],
        "mes_fiscal": int(p["mes_fiscal"]),
        "cliente_ref": p["cliente_ref"],
        "praca": {"cidade": p["cidade"], "estado": p["estado"]},
        "itens": [{
            "posicao": int(i["posicao"]), "categoria": i["categoria"], "subcategoria": i["subcategoria"],
            "quantidade": int(i["quantidade"]),
            "valor": Decimal128(i["valor"]), "lucro": Decimal128(i["lucro"]),
            "preco_unitario": Decimal128(i["preco_unitario"]),
            "flags": {"prejuizo": bool(i["flag_prejuizo"]), "valor_atipico": bool(i["flag_valor_atipico"]),
                      "prejuizo_maior_que_venda": bool(i["flag_prejuizo_maior_que_venda"])},
        } for i in sorted(itens, key=lambda x: x["posicao"])],
        "totais": {
            "valor": Decimal128(p["total_valor"]), "lucro": Decimal128(p["total_lucro"]),
            "margem_pct": float(p["margem_pct"]), "qtd_itens": int(p["qtd_itens"]),
            "qtd_unidades": int(p["qtd_unidades"]), "categorias": list(p["categorias"]),
            "item_unico": bool(p["item_unico"]),
        },
        # sem data de execução de propósito: o documento só muda se o dado mudar (idempotência)
        "_carga": {"sha256_origem": carga["sha256_origem"], "versao_pipeline": carga["versao_pipeline"]},
    }


def montar_documento_meta(m: dict) -> dict:
    from bson.decimal128 import Decimal128

    return {"_id": m["meta_id"], "competencia": m["competencia"], "mes_fiscal": int(m["mes_fiscal"]),
            "categoria": m["categoria"], "valor_alvo": Decimal128(m["valor_alvo"])}


# ------------------------------------------------------------------------------------ orquestração

def transformar(chave_hmac: bytes) -> dict:
    pedidos = pd.read_parquet(PASTA_VALIDADO / "pedidos.parquet")
    itens = pd.read_parquet(PASTA_VALIDADO / "itens.parquet")
    metas = pd.read_parquet(PASTA_VALIDADO / "metas.parquet")
    stats: dict = {}

    pedidos, n1p = t1_remover_espacos(pedidos)
    itens, n1i = t1_remover_espacos(itens)
    metas, n1m = t1_remover_espacos(metas)
    stats["T1_campos_aparados"] = n1p + n1i + n1m
    log.info("T1 – espaços removidos nas pontas: %d campo(s)", stats["T1_campos_aparados"])

    pedidos, itens, metas = t2_renomear(pedidos, "pedidos"), t2_renomear(itens, "itens"), t2_renomear(metas, "metas")
    log.info("T2 – colunas renomeadas para snake_case")

    pedidos["data_pedido"] = t3_converter_data(pedidos["data_texto"])
    log.info("T3 – parse de data dd-mm-aaaa: %d datas convertidas (%s a %s)", len(pedidos),
             pedidos["data_pedido"].min().date(), pedidos["data_pedido"].max().date())

    pedidos["competencia"], pedidos["mes_fiscal"] = t4_competencia(pedidos["data_pedido"])
    log.info("T4 – competência e mês fiscal derivados (%d competências)", pedidos["competencia"].nunique())

    pedidos, corrigidos = t5_corrigir_cidade_estado(pedidos)
    stats["T5_corrigidos"] = corrigidos
    log.info("T5 – cidade × estado corrigido em %d pedido(s): %s", len(corrigidos), "; ".join(corrigidos))

    itens, metas = t6_tipar(itens, metas)
    log.info("T6 – valores tipados como Decimal; quantidade como inteiro")

    itens["posicao"] = t7_posicao(itens)
    log.info("T7 – posição numerada em %d itens (máx. %d por pedido)", len(itens), itens["posicao"].max())

    itens["preco_unitario"] = t8_preco_unitario(itens)
    log.info("T8 – preço unitário calculado (%s a %s)", itens["preco_unitario"].min(), itens["preco_unitario"].max())

    itens, stats["T9"] = t9_flags(itens)
    log.info("T9 – flags: limite atípico (Q3 + 1,5×IQR) = %s; prejuízo=%d, atípico=%d, prejuízo>venda=%d",
             stats["T9"]["limite_atipico"], stats["T9"]["prejuizo"], stats["T9"]["valor_atipico"],
             stats["T9"]["prejuizo_maior_que_venda"])

    pedidos["cliente_ref"] = pedidos["cliente_nome"].map(lambda n: t10_pseudonimizar(n, chave_hmac))
    stats["T10_clientes_distintos"] = int(pedidos["cliente_ref"].nunique())
    pedidos = pedidos.drop(columns=["cliente_nome"])
    log.info("T10 – cliente pseudonimizado com HMAC-SHA256 (%d códigos distintos); nome descartado",
             stats["T10_clientes_distintos"])

    metas = t11_meta(metas)
    log.info("T11 – %d metas com competência e _id mês#categoria", len(metas))

    pedidos = t12_totais(pedidos, itens)
    log.info("T12 – totais calculados para %d pedidos (soma de valor = %s)", len(pedidos),
             sum(pedidos["total_valor"], Decimal("0")))

    pedidos = pedidos[["order_id", "data_pedido", "competencia", "mes_fiscal", "cliente_ref", "cidade", "estado",
                       "total_valor", "total_lucro", "margem_pct", "qtd_itens", "qtd_unidades", "categorias",
                       "item_unico"]]
    itens = itens[["order_id", "posicao", "categoria", "subcategoria", "quantidade", "valor", "lucro",
                   "preco_unitario", "flag_prejuizo", "flag_valor_atipico", "flag_prejuizo_maior_que_venda"]]

    config.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    pedidos.to_parquet(config.DATA_PROCESSED / "pedidos.parquet", index=False)
    itens.to_parquet(config.DATA_PROCESSED / "itens.parquet", index=False)
    metas.to_parquet(config.DATA_PROCESSED / "metas.parquet", index=False)

    origem = (config.DATA_RAW / config.ARQ_PEDIDOS).read_bytes() + (config.DATA_RAW / config.ARQ_ITENS).read_bytes()
    carga = {"sha256_origem": hashlib.sha256(origem).hexdigest()[:12], "versao_pipeline": config.VERSAO_PIPELINE,
             "limite_atipico": stats["T9"]["limite_atipico"]}
    (config.DATA_PROCESSED / "_carga.json").write_text(json.dumps(carga, indent=2), encoding="utf-8")
    log.info("Parquet gravado em %s: pedidos=%d, itens=%d, metas=%d", config.DATA_PROCESSED,
             len(pedidos), len(itens), len(metas))
    stats.update({"pedidos": len(pedidos), "itens": len(itens), "metas": len(metas)})
    return stats
