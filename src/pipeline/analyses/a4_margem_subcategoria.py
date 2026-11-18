"""A4 – Margem por subcategoria.

Pergunta de negócio: quais produtos vendem com prejuízo, mesmo quando a categoria bate a meta?
Coleção: pedidos (itens.categoria, itens.subcategoria, itens.valor, itens.lucro, itens.flags.prejuizo).
Esperado (profiling da N2): 17 subcategorias; piores margens Tables (−17,74%) e Electronic Games (−3,16%);
Saree fatura 53.511 com margem de 0,66%; melhor margem T-shirt (20,32%).
"""
from __future__ import annotations

from .comum import AZUL, TINTA_2, VERMELHO, estilo_eixo, exportar_csv, figura, rodar, salvar_png

SAIDA = "analytics_margem_subcategoria"

PIPELINE = [
    {"$unwind": "$itens"},  # a margem é do produto, então a unidade de análise é o item
    {"$group": {
        "_id": {"categoria": "$itens.categoria", "subcategoria": "$itens.subcategoria"},
        "itens": {"$sum": 1},
        "faturamento": {"$sum": "$itens.valor"},
        "lucro": {"$sum": "$itens.lucro"},
        # a flag T9 já vem marcada no documento: aqui só se conta
        "itens_com_prejuizo": {"$sum": {"$cond": ["$itens.flags.prejuizo", 1, 0]}},
    }},
    {"$project": {
        "_id": 0,
        "categoria": "$_id.categoria",
        "subcategoria": "$_id.subcategoria",
        "itens": 1, "faturamento": 1, "lucro": 1, "itens_com_prejuizo": 1,
        "margem_pct": {"$round": [{"$toDouble": {"$multiply": [{"$divide": ["$lucro", "$faturamento"]}, 100]}}, 2]},
    }},
    {"$sort": {"margem_pct": 1}},
    {"$out": SAIDA},
]


def executar(db) -> dict:
    df = rodar(db, PIPELINE, SAIDA).sort_values(["margem_pct", "subcategoria"])
    csv = exportar_csv(df[["categoria", "subcategoria", "itens", "faturamento", "lucro", "margem_pct",
                           "itens_com_prejuizo"]], "a4_margem_subcategoria")

    fig, ax = figura(9, 6.5)
    ordem = df.iloc[::-1]
    rotulos = [f"{s} ({c})" for s, c in zip(ordem["subcategoria"], ordem["categoria"])]
    cores = [VERMELHO if m < 0 else AZUL for m in ordem["margem_pct"]]
    ax.barh(rotulos, ordem["margem_pct"], color=cores, height=0.7)
    ax.axvline(0, color=TINTA_2, linewidth=1)
    for y, m in enumerate(ordem["margem_pct"]):
        ax.text(m + (0.4 if m >= 0 else -0.4), y, f"{m:.1f}%".replace(".", ","), va="center",
                ha="left" if m >= 0 else "right", fontsize=7.5, color=TINTA_2)
    ax.invert_yaxis()
    ax.set_xlabel("Margem (lucro ÷ faturamento, %)")
    ax.set_title("A4 – Margem por subcategoria no ano (vermelho = prejuízo)", loc="left")
    ax.set_xlim(min(-22, ordem["margem_pct"].min() - 4), ordem["margem_pct"].max() + 4)
    estilo_eixo(ax, "x")
    png = salvar_png(fig, "a4_margem_subcategoria")

    pior = df.iloc[0]
    return {"subcategorias": len(df), "pior": f"{pior['subcategoria']} ({pior['margem_pct']:.2f}%)",
            "com_margem_negativa": int((df["margem_pct"] < 0).sum()), "csv": csv, "png": png}
