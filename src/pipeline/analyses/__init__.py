"""Análises A1–A4 da N2 (seção 6), uma por arquivo, como aggregation pipelines do MongoDB."""
from . import a1_meta_realizado, a2_pracas, a3_venda_casada, a4_margem_subcategoria

TODAS = (
    ("A1 – Meta × realizado", a1_meta_realizado),
    ("A2 – Ranking de praças", a2_pracas),
    ("A3 – Venda casada", a3_venda_casada),
    ("A4 – Margem por subcategoria", a4_margem_subcategoria),
)
