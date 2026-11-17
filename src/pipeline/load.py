"""Etapa 4 – Load: Parquet (prata) → MongoDB, de forma idempotente (N2, seção 5.5).

- coleções criadas com validador $jsonSchema ANTES dos dados (N2 9.3);
- bulk_write com UpdateOne(upsert=True) e _id = chave natural, em lotes de BATCH_SIZE;
- índices da N2 (9.2) criados depois da carga;
- conciliação: contagem e soma de valor no banco contra o Parquet.
"""
from __future__ import annotations

import json
import logging
from decimal import Decimal

import pandas as pd
from pymongo import MongoClient, UpdateOne
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import BulkWriteError, CollectionInvalid

from . import config
from .transform import montar_documento_meta, montar_documento_pedido

log = logging.getLogger("load")

SCHEMA_PEDIDOS = {
    "bsonType": "object",
    "required": ["_id", "data_pedido", "competencia", "mes_fiscal", "praca", "itens", "totais"],
    "properties": {
        "_id": {"bsonType": "string", "pattern": "^B-[0-9]{5}$"},
        "data_pedido": {"bsonType": "date"},
        "competencia": {"bsonType": "string", "pattern": "^[0-9]{4}-[0-9]{2}$"},
        "mes_fiscal": {"bsonType": "int", "minimum": 1, "maximum": 12},
        "praca": {"bsonType": "object", "required": ["cidade", "estado"]},
        "itens": {"bsonType": "array", "minItems": 1, "items": {
            "bsonType": "object",
            "required": ["posicao", "categoria", "subcategoria", "quantidade", "valor", "lucro", "flags"],
            "properties": {
                "categoria": {"enum": ["Clothing", "Electronics", "Furniture"]},
                "quantidade": {"bsonType": "int", "minimum": 1},
                "valor": {"bsonType": "decimal"},
                "lucro": {"bsonType": "decimal"},
            }}},
        "totais": {"bsonType": "object", "required": ["valor", "lucro", "qtd_itens", "categorias", "item_unico"]},
    },
}

SCHEMA_METAS = {
    "bsonType": "object",
    "required": ["_id", "competencia", "mes_fiscal", "categoria", "valor_alvo"],
    "properties": {
        "_id": {"bsonType": "string", "pattern": "^[0-9]{4}-[0-9]{2}#(Clothing|Electronics|Furniture)$"},
        "valor_alvo": {"bsonType": "decimal"},
    },
}

# N2 9.2: o _id já é indexado; nenhum índice extra em metas_mensais porque o $lookup da A1 usa o _id
INDICES_PEDIDOS = [
    ([("competencia", 1)], "idx_competencia"),                           # A1: fechar o mês da reunião
    ([("praca.estado", 1), ("praca.cidade", 1)], "idx_praca"),          # A2/A3: abrir um estado ou uma praça
    ([("itens.subcategoria", 1)], "idx_itens_subcategoria"),            # A4: multikey (um valor por item)
]


def conectar(uri: str, db: str) -> Database:
    cliente = MongoClient(uri, serverSelectionTimeoutMS=5000)
    cliente.admin.command("ping")  # falha cedo e com mensagem clara se o Mongo não estiver no ar
    return cliente[db]


def garantir_colecao(db: Database, nome: str, schema: dict) -> Collection:
    """Cria a coleção com o validador; se já existe, atualiza o validador (collMod). Idempotente."""
    try:
        db.create_collection(nome, validator={"$jsonSchema": schema}, validationAction="error")
        log.info("coleção %s criada com validador $jsonSchema", nome)
    except CollectionInvalid:
        db.command("collMod", nome, validator={"$jsonSchema": schema}, validationAction="error")
        log.info("coleção %s já existia; validador $jsonSchema reaplicado", nome)
    return db[nome]


def upsert_em_lotes(colecao: Collection, documentos: list[dict], tamanho_lote: int) -> dict:
    """Grava com UpdateOne(filter={_id}, update={$set: resto}, upsert=True), em lotes.

    Por que upsert: se o _id não existe, insere; se existe e está igual, o MongoDB não altera nada;
    se mudou, atualiza. Rodar duas vezes termina com 0 inseridos e 0 modificados (idempotência).
    _id fica fora do $set porque é imutável.
    """
    res = {"inseridos": 0, "modificados": 0, "iguais": 0, "erros": []}
    for ini in range(0, len(documentos), tamanho_lote):
        lote = documentos[ini:ini + tamanho_lote]
        ops = [UpdateOne({"_id": d["_id"]}, {"$set": {k: v for k, v in d.items() if k != "_id"}}, upsert=True)
               for d in lote]
        try:
            r = colecao.bulk_write(ops, ordered=False)  # ordered=False: um documento recusado não trava o lote
            inseridos, casados, modificados = r.upserted_count, r.matched_count, r.modified_count
        except BulkWriteError as exc:
            det = exc.details
            inseridos, casados, modificados = det["nUpserted"], det["nMatched"], det["nModified"]
            for e in det["writeErrors"]:
                res["erros"].append({"_id": lote[e["index"]]["_id"], "erro": e["errmsg"][:300]})
        res["inseridos"] += inseridos
        res["modificados"] += modificados
        res["iguais"] += casados - modificados
        log.info("%s lote %d: %d documento(s) → inseridos=%d modificados=%d iguais=%d",
                 colecao.name, ini // tamanho_lote + 1, len(lote), inseridos, modificados, casados - modificados)
    for e in res["erros"]:
        log.error("%s recusado pelo validador: %s – %s", colecao.name, e["_id"], e["erro"])
    return res


def documentos_pedidos() -> list[dict]:
    pedidos = pd.read_parquet(config.DATA_PROCESSED / "pedidos.parquet")
    itens = pd.read_parquet(config.DATA_PROCESSED / "itens.parquet")
    carga = json.loads((config.DATA_PROCESSED / "_carga.json").read_text(encoding="utf-8"))
    por_pedido = {oid: grupo.to_dict("records") for oid, grupo in itens.groupby("order_id")}
    return [montar_documento_pedido(p, por_pedido[p["order_id"]], carga) for p in pedidos.to_dict("records")]


def documentos_metas() -> list[dict]:
    metas = pd.read_parquet(config.DATA_PROCESSED / "metas.parquet")
    return [montar_documento_meta(m) for m in metas.to_dict("records")]


def conciliar(db: Database) -> dict:
    """Confere o banco contra o Parquet: contagens e soma exata de valor (OE1)."""
    pedidos = pd.read_parquet(config.DATA_PROCESSED / "pedidos.parquet")
    metas = pd.read_parquet(config.DATA_PROCESSED / "metas.parquet")
    soma_parquet = sum(pedidos["total_valor"], Decimal("0"))
    agg = list(db.pedidos.aggregate([{"$group": {"_id": None, "soma": {"$sum": "$totais.valor"},
                                                 "itens": {"$sum": "$totais.qtd_itens"}}}]))
    soma_banco = agg[0]["soma"].to_decimal() if agg else Decimal("0")
    r = {
        "pedidos_banco": db.pedidos.count_documents({}), "pedidos_parquet": len(pedidos),
        "itens_banco": agg[0]["itens"] if agg else 0,
        "metas_banco": db.metas_mensais.count_documents({}), "metas_parquet": len(metas),
        "soma_valor_banco": str(soma_banco), "soma_valor_parquet": str(soma_parquet),
    }
    r["ok"] = (r["pedidos_banco"] == r["pedidos_parquet"] and r["metas_banco"] == r["metas_parquet"]
               and soma_banco == soma_parquet)
    (log.info if r["ok"] else log.error)(
        "conciliação %s: pedidos %d/%d, metas %d/%d, soma de valor banco=%s parquet=%s",
        "OK" if r["ok"] else "FALHOU", r["pedidos_banco"], r["pedidos_parquet"], r["metas_banco"],
        r["metas_parquet"], r["soma_valor_banco"], r["soma_valor_parquet"])
    return r


def carregar(db: Database, tamanho_lote: int) -> dict:
    pedidos = garantir_colecao(db, "pedidos", SCHEMA_PEDIDOS)
    metas = garantir_colecao(db, "metas_mensais", SCHEMA_METAS)

    r_pedidos = upsert_em_lotes(pedidos, documentos_pedidos(), tamanho_lote)
    r_metas = upsert_em_lotes(metas, documentos_metas(), tamanho_lote)

    for chaves, nome in INDICES_PEDIDOS:
        pedidos.create_index(chaves, name=nome)  # create_index não faz nada se o índice já existe
    log.info("índices garantidos em pedidos: %s", ", ".join(n for _, n in INDICES_PEDIDOS))

    return {"pedidos": r_pedidos, "metas_mensais": r_metas, "conciliacao": conciliar(db)}
