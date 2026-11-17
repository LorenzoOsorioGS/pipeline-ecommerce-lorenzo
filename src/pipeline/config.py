"""Configuração central: caminhos, variáveis do .env e logging."""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]
load_dotenv(RAIZ / ".env")

DATA_RAW = RAIZ / "data" / "raw"
DATA_PROCESSED = RAIZ / "data" / "processed"
OUTPUT = RAIZ / "output"
REJEITADOS = OUTPUT / "rejeitados"

DATASET_KAGGLE = "benroshan/ecommerce-data"
ARQ_PEDIDOS = "List of Orders.csv"
ARQ_ITENS = "Order Details.csv"
ARQ_METAS = "Sales target.csv"
ARQUIVOS = (ARQ_PEDIDOS, ARQ_ITENS, ARQ_METAS)

VERSAO_PIPELINE = "1.0"


@dataclass(frozen=True)
class Config:
    mongo_uri: str
    mongo_db: str
    batch_size: int
    hmac_key: bytes
    extract_mode: str
    log_level: str


def carregar() -> Config:
    chave = os.getenv("HMAC_KEY", "")
    if not chave:
        raise RuntimeError("HMAC_KEY não definida no .env (copie o .env.example e troque a chave).")
    return Config(
        mongo_uri=os.getenv("MONGO_URI", "mongodb://localhost:27017"),
        mongo_db=os.getenv("MONGO_DB", "ecommerce"),
        batch_size=int(os.getenv("BATCH_SIZE", "100")),
        hmac_key=chave.encode("utf-8"),
        extract_mode=os.getenv("EXTRACT_MODE", "auto").lower(),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )


def configurar_logging(nivel: str = "INFO") -> None:
    logging.basicConfig(
        stream=sys.stdout,  # stdout: no PowerShell 5.1, stderr de programa externo aparece como "erro"
        level=getattr(logging, nivel, logging.INFO),
        format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    for ruidoso in ("pymongo", "matplotlib", "urllib3", "kagglehub", "PIL"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)
