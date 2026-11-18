"""Resume o log do MongoDB (logs/mongod.log) em logs/consultas.log: uma linha por consulta.

O mongo_local.ps1 sobe o banco com o profiler ligado (--profile 2 --slowms 0), então toda operação
entra no mongod.log como "Slow query". Este script só lê esse arquivo e escreve um resumo legível.

Uso: .venv\\Scripts\\python.exe scripts\\consultas_log.py
"""
import json
from pathlib import Path

LOGS = Path(__file__).resolve().parent.parent / "logs"
ORIGEM, DESTINO = LOGS / "mongod.log", LOGS / "consultas.log"
OPERACOES = ("find", "aggregate", "count", "update", "insert", "delete", "createIndexes", "drop", "create", "collMod")

linhas = []
for bruta in ORIGEM.read_text(encoding="utf-8").splitlines():
    try:
        reg = json.loads(bruta)
    except ValueError:
        continue
    if reg.get("msg") != "Slow query":
        continue
    a = reg["attr"]
    if not a.get("ns", "").startswith("ecommerce."):
        continue
    cmd = a.get("command", {})
    op = next((k for k in cmd if k in OPERACOES), a.get("type", "?"))
    detalhe = cmd.get("filter") or cmd.get("pipeline") or cmd.get("query") or cmd.get("updates") or ""
    detalhe = json.dumps(detalhe, ensure_ascii=False, default=str)[:300]
    linhas.append(f"{reg['t']['$date'][:19]}  {a['ns']:<38} {op:<14} {a.get('durationMillis', 0):>4} ms  "
                  f"docs lidos={a.get('docsExamined', '-'):<5} plano={a.get('planSummary', '-'):<10} {detalhe}")

DESTINO.write_text("\n".join(linhas) + "\n", encoding="utf-8")
print(f"{len(linhas)} consulta(s) do banco ecommerce gravada(s) em {DESTINO}")
