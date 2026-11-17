"""Etapa 2 – Validate: regras de qualidade V1–V9 da N2 (seção 5.3).

Linha reprovada não interrompe o pipeline: vai para output/rejeitados/<arquivo>.csv com a regra e o motivo.
As linhas aprovadas seguem, ainda como texto, para data/processed/_validado/ (entrada da transformação).
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import config
from .referencias import CATEGORIAS, CIDADE_ESTADO, CORRECOES_CIDADE_ESTADO, SUBCATEGORIAS

log = logging.getLogger("validate")
PASTA_VALIDADO = config.DATA_PROCESSED / "_validado"
PADRAO_ORDER_ID = re.compile(r"^B-\d{5}$")


@dataclass
class Validacao:
    pedidos: pd.DataFrame
    itens: pd.DataFrame
    metas: pd.DataFrame
    lidas: dict[str, int] = field(default_factory=dict)
    rejeitados: list[dict] = field(default_factory=list)
    alertas: list[str] = field(default_factory=list)
    a_corrigir_t5: int = 0

    def rejeitar(self, arquivo: str, df: pd.DataFrame, regra: str, motivo: str) -> None:
        for _, linha in df.iterrows():
            reg = {k: v for k, v in linha.items() if k != "_linha"}
            self.rejeitados.append({"arquivo": arquivo, "linha_no_arquivo": int(linha["_linha"]),
                                    "regra": regra, "motivo": motivo, "registro": reg})
        if len(df):
            log.info("%s – %s: %d linha(s) de %s", regra, motivo, len(df), arquivo)


def ler_csv(caminho: Path) -> pd.DataFrame:
    # tudo como texto: a validação decide o que é número/data, não o pandas
    df = pd.read_csv(caminho, dtype=str, keep_default_na=False)
    df["_linha"] = df.index + 2  # +1 do cabeçalho, +1 porque linha de arquivo começa em 1
    return df


def v1_linhas_vazias(df: pd.DataFrame) -> pd.Series:
    """V1 – linha com todos os campos vazios (ex.: ",,,," no fim de List of Orders)."""
    dados = df.drop(columns="_linha")
    return dados.apply(lambda c: c.str.strip() == "").all(axis=1)


def v2_order_id_invalido(pedidos: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """V2 – Order ID presente, no padrão B-NNNNN e único. Devolve (fora do padrão, duplicado)."""
    oid = pedidos["Order ID"].str.strip()
    fora = ~oid.str.match(PADRAO_ORDER_ID)
    dup = oid.duplicated(keep="first") & ~fora
    return fora, dup


def v3_data_invalida(pedidos: pd.DataFrame) -> pd.Series:
    """V3 – Order Date tem que ser uma data real no formato dd-mm-aaaa."""
    datas = pd.to_datetime(pedidos["Order Date"].str.strip(), format="%d-%m-%Y", errors="coerce")
    return datas.isna()


def v6_numero_invalido(itens: pd.DataFrame) -> pd.Series:
    """V6 – Amount > 0, Quantity inteiro ≥ 1 e Profit numérico."""
    amount = pd.to_numeric(itens["Amount"].str.strip(), errors="coerce")
    profit = pd.to_numeric(itens["Profit"].str.strip(), errors="coerce")
    qtd_txt = itens["Quantity"].str.strip()
    qtd_ok = qtd_txt.str.fullmatch(r"\d+") & (pd.to_numeric(qtd_txt, errors="coerce") >= 1)
    return amount.isna() | (amount <= 0) | profit.isna() | ~qtd_ok


def v7_categoria_invalida(df: pd.DataFrame, com_sub: bool = True) -> pd.Series:
    """V7 – categoria no domínio e subcategoria coerente com ela."""
    cat = df["Category"].str.strip()
    ruim = ~cat.isin(CATEGORIAS)
    if com_sub:
        sub = df["Sub-Category"].str.strip()
        ruim |= ~pd.Series([s in SUBCATEGORIAS.get(c, set()) for c, s in zip(cat, sub)], index=df.index)
    return ruim


def v8_meta_invalida(metas: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """V8 – mês Mmm-aa válido, Target > 0, categoria válida; mês × categoria único."""
    mes = pd.to_datetime(metas["Month of Order Date"].str.strip(), format="%b-%y", errors="coerce")
    alvo = pd.to_numeric(metas["Target"].str.strip(), errors="coerce")
    ruim = mes.isna() | alvo.isna() | (alvo <= 0) | v7_categoria_invalida(metas, com_sub=False)
    chave = metas["Month of Order Date"].str.strip() + "#" + metas["Category"].str.strip()
    dup = chave.duplicated(keep="first") & ~ruim
    return ruim, dup


def v9_cidade_estado(pedidos: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """V9 – par cidade × estado contra a tabela de referência.

    Devolve (corrigível pela T5, desconhecido). Nenhum dos dois é rejeitado: o primeiro é corrigido
    na transformação e o segundo gera alerta no relatório.
    """
    pares = list(zip(pedidos["City"].str.strip(), pedidos["State"].str.strip()))
    corrigivel = pd.Series([p in CORRECOES_CIDADE_ESTADO for p in pares], index=pedidos.index)
    desconhecido = pd.Series([p not in CIDADE_ESTADO and p not in CORRECOES_CIDADE_ESTADO for p in pares],
                             index=pedidos.index)
    return corrigivel, desconhecido


def validar(raw: Path = config.DATA_RAW) -> Validacao:
    pedidos = ler_csv(raw / config.ARQ_PEDIDOS)
    itens = ler_csv(raw / config.ARQ_ITENS)
    metas = ler_csv(raw / config.ARQ_METAS)
    v = Validacao(pedidos=pedidos, itens=itens, metas=metas,
                  lidas={config.ARQ_PEDIDOS: len(pedidos), config.ARQ_ITENS: len(itens), config.ARQ_METAS: len(metas)})

    # V1 nos três arquivos
    for nome, attr in ((config.ARQ_PEDIDOS, "pedidos"), (config.ARQ_ITENS, "itens"), (config.ARQ_METAS, "metas")):
        df = getattr(v, attr)
        vazias = v1_linhas_vazias(df)
        v.rejeitar(nome, df[vazias], "V1", "linha com todos os campos vazios")
        setattr(v, attr, df[~vazias])

    # pedidos: V2, V3
    fora, dup = v2_order_id_invalido(v.pedidos)
    v.rejeitar(config.ARQ_PEDIDOS, v.pedidos[fora], "V2", "Order ID ausente ou fora do padrão B-NNNNN")
    v.rejeitar(config.ARQ_PEDIDOS, v.pedidos[dup], "V2", "Order ID duplicado")
    v.pedidos = v.pedidos[~(fora | dup)]
    ruim = v3_data_invalida(v.pedidos)
    v.rejeitar(config.ARQ_PEDIDOS, v.pedidos[ruim], "V3", "Order Date inválida (esperado dd-mm-aaaa)")
    v.pedidos = v.pedidos[~ruim]

    # itens: V6, V7, V4
    ruim = v6_numero_invalido(v.itens)
    v.rejeitar(config.ARQ_ITENS, v.itens[ruim], "V6", "Amount/Quantity/Profit inválido")
    v.itens = v.itens[~ruim]
    ruim = v7_categoria_invalida(v.itens)
    v.rejeitar(config.ARQ_ITENS, v.itens[ruim], "V7", "categoria fora do domínio ou subcategoria incoerente")
    v.itens = v.itens[~ruim]
    orfao = ~v.itens["Order ID"].str.strip().isin(set(v.pedidos["Order ID"].str.strip()))
    v.rejeitar(config.ARQ_ITENS, v.itens[orfao], "V4", "item sem pedido correspondente (órfão)")
    v.itens = v.itens[~orfao]

    # V5 depois dos itens: um pedido cujos itens foram todos rejeitados também fica sem item
    sem_item = ~v.pedidos["Order ID"].str.strip().isin(set(v.itens["Order ID"].str.strip()))
    v.rejeitar(config.ARQ_PEDIDOS, v.pedidos[sem_item], "V5", "pedido sem nenhum item válido")
    v.pedidos = v.pedidos[~sem_item]

    # metas: V8
    ruim, dup = v8_meta_invalida(v.metas)
    v.rejeitar(config.ARQ_METAS, v.metas[ruim], "V8", "meta com mês, valor ou categoria inválidos")
    v.rejeitar(config.ARQ_METAS, v.metas[dup], "V8", "meta duplicada para o mesmo mês × categoria")
    v.metas = v.metas[~(ruim | dup)]

    # V9: não rejeita; conta o que a T5 vai corrigir e alerta o que é desconhecido
    corrigivel, desconhecido = v9_cidade_estado(v.pedidos)
    v.a_corrigir_t5 = int(corrigivel.sum())
    log.info("V9 – par cidade × estado: %d a corrigir pela T5, %d desconhecido(s)",
             v.a_corrigir_t5, int(desconhecido.sum()))
    for _, linha in v.pedidos[desconhecido].iterrows():
        v.alertas.append(f"V9: par desconhecido {linha['City'].strip()}/{linha['State'].strip()} "
                         f"no pedido {linha['Order ID']} (linha {linha['_linha']}); mantido como veio.")
    return v


def salvar(v: Validacao) -> dict:
    """Grava a saída da validação (staging), os rejeitados e as estatísticas usadas no relatório."""
    PASTA_VALIDADO.mkdir(parents=True, exist_ok=True)
    config.REJEITADOS.mkdir(parents=True, exist_ok=True)
    v.pedidos.to_parquet(PASTA_VALIDADO / "pedidos.parquet", index=False)
    v.itens.to_parquet(PASTA_VALIDADO / "itens.parquet", index=False)
    v.metas.to_parquet(PASTA_VALIDADO / "metas.parquet", index=False)

    rej = pd.DataFrame(v.rejeitados, columns=["arquivo", "linha_no_arquivo", "regra", "motivo", "registro"])
    for nome in config.ARQUIVOS:
        alvo = config.REJEITADOS / (Path(nome).stem.replace(" ", "_").lower() + ".csv")
        parte = rej[rej["arquivo"] == nome].copy()
        parte["registro"] = parte["registro"].map(lambda r: json.dumps(r, ensure_ascii=False))
        parte.drop(columns="arquivo").to_csv(alvo, index=False, encoding="utf-8")

    por_regra = rej.groupby(["arquivo", "regra", "motivo"]).size().reset_index(name="linhas") if len(rej) else rej
    stats = {
        "executado_em": datetime.now().isoformat(timespec="seconds"),
        "lidas": v.lidas,
        "aprovadas": {config.ARQ_PEDIDOS: len(v.pedidos), config.ARQ_ITENS: len(v.itens),
                      config.ARQ_METAS: len(v.metas)},
        "rejeicoes": por_regra.to_dict("records") if len(rej) else [],
        "alertas": v.alertas,
        "a_corrigir_t5": v.a_corrigir_t5,
    }
    (PASTA_VALIDADO / "validacao.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    return stats
