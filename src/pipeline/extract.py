"""Etapa 1 – Extract: camada raw (bronze).

Baixa o dataset com kagglehub e copia os 3 CSVs, sem alteração, para data/raw/.
Se o kagglehub falhar (sem rede, sem credencial), usa os CSVs colocados à mão em data/raw/.
Grava data/raw/manifesto.json com SHA-256, tamanho e nº de linhas de cada arquivo.
"""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from . import config

log = logging.getLogger("extract")


def _sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def _linhas_de_dados(caminho: Path) -> int:
    # conta linhas físicas sem o cabeçalho; linhas vazias (",,,,") entram na conta de propósito:
    # quem descarta é a validação (V1), não a extração
    with caminho.open("r", encoding="utf-8", newline="") as f:
        return sum(1 for _ in f) - 1


def _baixar_kaggle() -> Path:
    import kagglehub  # import tardio: o modo "local" não precisa da biblioteca

    pasta = Path(kagglehub.dataset_download(config.DATASET_KAGGLE))
    log.info("kagglehub baixou/encontrou o dataset em %s", pasta)
    return pasta


def extrair(modo: str = "auto", destino: Path = config.DATA_RAW) -> dict:
    destino.mkdir(parents=True, exist_ok=True)
    origem = "manual (data/raw/)"

    if modo != "local":
        try:
            pasta = _baixar_kaggle()
            for nome in config.ARQUIVOS:
                shutil.copy2(pasta / nome, destino / nome)
            origem = f"kagglehub ({config.DATASET_KAGGLE})"
        except Exception as exc:  # noqa: BLE001 – qualquer falha do kagglehub cai no fallback
            log.warning("kagglehub falhou (%s: %s); usando os CSVs que já estão em %s",
                        exc.__class__.__name__, exc, destino)

    faltando = [n for n in config.ARQUIVOS if not (destino / n).exists()]
    if faltando:
        raise FileNotFoundError(
            f"Arquivos ausentes em {destino}: {faltando}. Baixe o zip em "
            f"https://www.kaggle.com/datasets/{config.DATASET_KAGGLE} e extraia nessa pasta.")

    manifesto = {
        "dataset": config.DATASET_KAGGLE,
        "origem": origem,
        "extraido_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "arquivos": {},
    }
    for nome in config.ARQUIVOS:
        caminho = destino / nome
        info = {"sha256": _sha256(caminho), "bytes": caminho.stat().st_size, "linhas": _linhas_de_dados(caminho)}
        manifesto["arquivos"][nome] = info
        log.info("%-20s sha256=%s… bytes=%d linhas=%d", nome, info["sha256"][:12], info["bytes"], info["linhas"])

    (destino / "manifesto.json").write_text(json.dumps(manifesto, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("manifesto gravado em %s (origem: %s)", destino / "manifesto.json", origem)
    return manifesto
