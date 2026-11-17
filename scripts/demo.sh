#!/usr/bin/env bash
# Demonstração guiada do pipeline (Linux/macOS/Git Bash).
# Uso, na raiz do projeto:  bash scripts/demo.sh
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONIOENCODING=utf-8
PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python
[ -x .venv/Scripts/python.exe ] && PY=.venv/Scripts/python.exe

passo() {
  printf '\n%s\n  %s\n%s\n' "$(printf '=%.0s' {1..72})" "$1" "$(printf '=%.0s' {1..72})"
  read -r -p "  [Enter para executar] " _
}

[ -f .env ] || { cp .env.example .env; echo ".env criado a partir do .env.example"; }

passo "1/9  Subir a infraestrutura (docker compose: MongoDB 7 + mongo-express em http://localhost:8081)"
docker compose up -d --wait
docker compose ps

passo "2/9  Começar do zero: apagar o banco 'ecommerce' (só o banco desta demo)"
$PY scripts/inspecionar.py limpar

passo "3/9  EXTRACT – kagglehub → data/raw/ + manifesto (hash, bytes, linhas)"
$PY src/main.py --step extract

passo "4/9  VALIDATE – regras V1–V9; rejeitados em output/rejeitados/"
$PY src/main.py --step validate

passo "5/9  TRANSFORM – regras T1–T12; Parquet em data/processed/"
$PY src/main.py --step transform
head -n 30 output/relatorio_qualidade.md

passo "6/9  LOAD – validador \$jsonSchema, upsert em lotes, índices e conciliação"
$PY src/main.py --step load
$PY scripts/inspecionar.py contar

passo "7/9  Um pedido completo no MongoDB (B-25608)"
$PY scripts/inspecionar.py pedido B-25608
echo "No navegador: http://localhost:8081 (mongo-express)"

passo "8/9  IDEMPOTÊNCIA – rodar a carga de novo: 0 inseridos, 0 modificados, contagem igual"
$PY src/main.py --step load
$PY scripts/inspecionar.py contar

passo "9/9  ANALYZE – aggregations A1–A4 → coleções analytics_* + CSV e PNG em output/"
$PY src/main.py --step analyze
ls -l output
