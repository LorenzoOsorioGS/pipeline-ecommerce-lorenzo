"""Peças comuns às análises: rodar a aggregation, ler o resultado da camada ouro e exportar CSV/PNG."""
from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # gera PNG sem abrir janela
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from bson.decimal128 import Decimal128  # noqa: E402
from pymongo.database import Database  # noqa: E402

from .. import config  # noqa: E402

log = logging.getLogger("analyze")

# paleta (referência de dataviz): uma cor de série, vermelho só para valor negativo, tinta neutra no texto
AZUL = "#2a78d6"
VERMELHO = "#e34948"
CINZA = "#b9b8b3"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
GRADE = "#e4e3df"
FUNDO = "#fcfcfb"


def rodar(db: Database, pipeline: list[dict], saida: str) -> pd.DataFrame:
    """Executa a aggregation em `pedidos` (que termina em $out) e lê de volta a coleção ouro."""
    db.pedidos.aggregate(pipeline)
    # o _id das coleções ouro é um ObjectId gerado pelo $out; não interessa ao gerente
    docs = list(db[saida].find({}, {"_id": 0}))
    log.info("%s: %d documento(s) gravado(s) pela aggregation", saida, len(docs))
    return pd.json_normalize([_para_python(d) for d in docs], sep="_")


def _para_python(valor):
    if isinstance(valor, Decimal128):
        return float(valor.to_decimal())
    if isinstance(valor, dict):
        return {k: _para_python(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_para_python(v) for v in valor]
    return valor


def exportar_csv(df: pd.DataFrame, nome: str) -> Path:
    config.OUTPUT.mkdir(parents=True, exist_ok=True)
    caminho = config.OUTPUT / f"{nome}.csv"
    df.to_csv(caminho, index=False, encoding="utf-8", float_format="%.2f")
    return caminho


def figura(largura: float = 9, altura: float = 5):
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": GRADE, "axes.labelcolor": TINTA_2,
        "xtick.color": TINTA_2, "ytick.color": TINTA_2, "axes.titlecolor": TINTA, "axes.titlesize": 11,
        "axes.titleweight": "bold", "figure.facecolor": FUNDO, "axes.facecolor": FUNDO,
    })
    return plt.subplots(figsize=(largura, altura))


def estilo_eixo(ax, grade_em: str = "x") -> None:
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.grid(axis=grade_em, color=GRADE, linewidth=0.8)
    ax.set_axisbelow(True)


def salvar_png(fig, nome: str) -> Path:
    caminho = config.OUTPUT / f"{nome}.png"
    fig.tight_layout()
    fig.savefig(caminho, dpi=150)
    plt.close(fig)
    return caminho
