"""Visualizador SOMENTE LEITURA do MongoDB no navegador (http://localhost:8081).

Existe só para máquinas sem Docker, onde o mongo-express do docker-compose não roda.
Com Docker, use o mongo-express (mesma porta). Ver docs/N3/desvios_da_N2.md.
Uso: python scripts/visualizar.py
"""
from __future__ import annotations

import html
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote

from bson import json_util
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
DB = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))[os.getenv("MONGO_DB", "ecommerce")]
CSS = ("body{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#fcfcfb;color:#0b0b0b}"
       "a{color:#2a78d6}pre{background:#f2f2f0;padding:12px;border-radius:6px;font-size:13px;overflow:auto}"
       "td,th{padding:4px 12px;text-align:left;border-bottom:1px solid #e4e3df}small{color:#52514e}")


def pagina(titulo: str, corpo: str) -> bytes:
    return (f"<!doctype html><meta charset='utf-8'><title>{html.escape(titulo)}</title><style>{CSS}</style>"
            f"<p><a href='/'>banco {DB.name}</a> <small>(somente leitura)</small></p>{corpo}").encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        partes = [unquote(p) for p in self.path.strip("/").split("/") if p]
        if not partes:
            linhas = "".join(f"<tr><td><a href='/{quote(c)}'>{c}</a></td><td>{DB[c].estimated_document_count()}</td></tr>"
                             for c in sorted(DB.list_collection_names()))
            corpo = f"<h2>Coleções</h2><table><tr><th>coleção</th><th>documentos</th></tr>{linhas}</table>"
        elif len(partes) == 1:
            col = DB[partes[0]]
            docs = list(col.find().limit(50))
            itens = "".join(
                f"<li><a href='/{quote(partes[0])}/{quote(str(d['_id']))}'>{html.escape(str(d['_id']))}</a></li>"
                if not partes[0].startswith("analytics") else
                f"<li><pre>{html.escape(json_util.dumps(d, json_options=json_util.RELAXED_JSON_OPTIONS))}</pre></li>"
                for d in docs)
            corpo = (f"<h2>{html.escape(partes[0])}</h2><p>{col.estimated_document_count()} documentos "
                     f"(mostrando até 50)</p><ul>{itens}</ul>")
        else:
            doc = DB[partes[0]].find_one({"_id": partes[1]})
            texto = json_util.dumps(doc, indent=2, ensure_ascii=False, json_options=json_util.RELAXED_JSON_OPTIONS)
            corpo = f"<h2>{html.escape(partes[0])} / {html.escape(partes[1])}</h2><pre>{html.escape(texto)}</pre>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(pagina(" / ".join(partes) or "MongoDB", corpo))

    def log_message(self, *args):  # silencia o log de cada requisição
        pass


if __name__ == "__main__":
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8081
    print(f"Visualizador somente leitura em http://localhost:{porta}  (Ctrl+C para parar)")
    ThreadingHTTPServer(("127.0.0.1", porta), Handler).serve_forever()
