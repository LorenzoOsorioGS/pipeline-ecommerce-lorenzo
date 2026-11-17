"""Idempotência da carga: rodar duas vezes não duplica nem altera nada.

Usa o MongoDB de verdade (docker-compose ou portátil) se ele responder; senão, usa mongomock.
"""
import os
from decimal import Decimal

import pytest
from bson.decimal128 import Decimal128

from pipeline.load import upsert_em_lotes


def _documentos(n=7, valor="10.00"):
    return [{"_id": f"B-{25600 + i}", "competencia": "2018-04",
             "itens": [{"posicao": 1, "valor": Decimal128(Decimal(valor))}]} for i in range(n)]


class _ColecaoMock:
    """Adaptador para o mongomock 4.3, que não aceita o parâmetro `sort` que o pymongo 4.20 passa no
    bulk_write. Executa cada UpdateOne do lote com update_one (que o mongomock suporta)."""

    def __init__(self, col):
        self._col, self.name = col, col.name

    def bulk_write(self, ops, ordered=True):  # noqa: ARG002
        r = {"upserted_count": 0, "matched_count": 0, "modified_count": 0}
        for op in ops:
            res = self._col.update_one(op._filter, op._doc, upsert=op._upsert)
            r["upserted_count"] += res.upserted_id is not None
            r["matched_count"] += res.matched_count
            r["modified_count"] += res.modified_count
        return type("Resultado", (), r)()

    def __getattr__(self, nome):
        return getattr(self._col, nome)


@pytest.fixture
def colecao():
    try:
        from pymongo import MongoClient
        cliente = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"), serverSelectionTimeoutMS=1500)
        cliente.admin.command("ping")
        db, real = cliente["ecommerce_teste"], True
    except Exception:  # noqa: BLE001
        import mongomock
        db, real = mongomock.MongoClient()["ecommerce_teste"], False
    db.drop_collection("pedidos")
    yield (db["pedidos"] if real else _ColecaoMock(db["pedidos"])), real
    db.drop_collection("pedidos")


def test_rodar_duas_vezes_nao_duplica(colecao):
    col, real = colecao
    primeira = upsert_em_lotes(col, _documentos(), tamanho_lote=3)  # 3 lotes: 3 + 3 + 1
    assert primeira["inseridos"] == 7 and col.count_documents({}) == 7

    segunda = upsert_em_lotes(col, _documentos(), tamanho_lote=3)
    assert segunda["inseridos"] == 0
    assert col.count_documents({}) == 7
    if real:  # o mongomock não reproduz a detecção de "update sem mudança"
        assert segunda["modificados"] == 0 and segunda["iguais"] == 7


def test_dado_alterado_atualiza_sem_duplicar(colecao):
    col, _ = colecao
    upsert_em_lotes(col, _documentos(), tamanho_lote=100)
    r = upsert_em_lotes(col, _documentos(valor="99.00"), tamanho_lote=100)
    assert r["inseridos"] == 0 and r["modificados"] == 7
    assert col.count_documents({}) == 7
    assert col.find_one({"_id": "B-25600"})["itens"][0]["valor"] == Decimal128("99.00")
