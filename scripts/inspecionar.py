"""Consultas rápidas para a demonstração.

Uso:
  python scripts/inspecionar.py contar            → documentos por coleção
  python scripts/inspecionar.py pedido B-25608    → um pedido completo (Extended JSON)
  python scripts/inspecionar.py limpar            → apaga o banco do pipeline (para a demo começar do zero)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from bson import json_util
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
db = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"), serverSelectionTimeoutMS=5000)[
    os.getenv("MONGO_DB", "ecommerce")]

if len(sys.argv) < 2 or sys.argv[1] == "contar":
    for nome in sorted(db.list_collection_names(filter={"name": {"$not": {"$regex": "^system[.]"}}})):
        print(f"{nome:<32} {db[nome].count_documents({}):>5} documentos")
elif sys.argv[1] == "pedido":
    oid = sys.argv[2] if len(sys.argv) > 2 else "B-25608"
    doc = db.pedidos.find_one({"_id": oid})
    print(json_util.dumps(doc, indent=2, ensure_ascii=False, json_options=json_util.RELAXED_JSON_OPTIONS)
          if doc else f"pedido {oid} não encontrado")
elif sys.argv[1] == "limpar":
    db.client.drop_database(db.name)
    print(f"banco {db.name} apagado")
else:
    sys.exit(__doc__)
