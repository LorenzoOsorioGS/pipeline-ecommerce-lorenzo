"""A1 – Meta × realizado por categoria e mês.

Pergunta de negócio: em quais meses cada categoria bateu a meta, e com que lucro?
Coleções: pedidos (competencia, itens.categoria, itens.valor, itens.lucro) + metas_mensais (_id, valor_alvo).
Esperado (profiling da N2): 36 linhas, 16 metas batidas; Electronics 128,1% no ano, Clothing 79,9%,
Furniture 95,7%; 5 metas batidas com lucro negativo.
"""
from __future__ import annotations

from .comum import AZUL, CINZA, TINTA_2, estilo_eixo, exportar_csv, figura, rodar, salvar_png

SAIDA = "analytics_meta_realizado"

PIPELINE = [
    # 1 documento por item: a meta é por categoria, e um pedido pode ter itens de várias categorias
    {"$unwind": "$itens"},
    # soma o realizado do mês × categoria; $addToSet conta cada pedido uma vez só
    {"$group": {
        "_id": {"competencia": "$competencia", "categoria": "$itens.categoria"},
        "realizado": {"$sum": "$itens.valor"},
        "lucro": {"$sum": "$itens.lucro"},
        "pedidos": {"$addToSet": "$_id"},
    }},
    # monta a mesma chave usada como _id em metas_mensais ("2018-04#Furniture")
    {"$addFields": {"chave_meta": {"$concat": ["$_id.competencia", "#", "$_id.categoria"]}}},
    # $lookup = JOIN do MongoDB; como compara com o _id da meta, usa o índice que o _id já tem
    {"$lookup": {"from": "metas_mensais", "localField": "chave_meta", "foreignField": "_id", "as": "meta"}},
    {"$unwind": "$meta"},  # o $lookup devolve uma lista; aqui ela tem exatamente 1 meta
    {"$project": {
        "_id": 0,
        "competencia": "$_id.competencia",
        "categoria": "$_id.categoria",
        "valor_alvo": "$meta.valor_alvo",
        "realizado": 1,
        "lucro": 1,
        "qtd_pedidos": {"$size": "$pedidos"},
        "atingimento_pct": {"$round": [{"$toDouble": {
            "$multiply": [{"$divide": ["$realizado", "$meta.valor_alvo"]}, 100]}}, 1]},
        "bateu": {"$gte": ["$realizado", "$meta.valor_alvo"]},
    }},
    {"$sort": {"categoria": 1, "competencia": 1}},
    {"$out": SAIDA},  # substitui a coleção ouro inteira: nunca sobra resultado de execução anterior
]


def executar(db) -> dict:
    df = rodar(db, PIPELINE, SAIDA).sort_values(["categoria", "competencia"])
    csv = exportar_csv(df[["competencia", "categoria", "valor_alvo", "realizado", "atingimento_pct", "bateu",
                           "lucro", "qtd_pedidos"]], "a1_meta_realizado")

    fig, eixos = figura(10, 6.5)
    fig.clf()
    cats = sorted(df["categoria"].unique())
    for n, cat in enumerate(cats, start=1):
        ax = fig.add_subplot(len(cats), 1, n)
        parte = df[df["categoria"] == cat]
        cores = [AZUL if b else CINZA for b in parte["bateu"]]
        ax.bar(parte["competencia"], parte["atingimento_pct"], color=cores, width=0.7)
        ax.axhline(100, color=TINTA_2, linewidth=1, linestyle="--")
        ano = parte["realizado"].sum() / parte["valor_alvo"].sum() * 100
        ax.set_title(f"{cat}: {int(parte['bateu'].sum())} de 12 metas batidas · "
                     f"{ano:.1f}% da meta anual".replace(".", ","),
                     loc="left", fontsize=10)
        ax.set_ylabel("% da meta")
        ax.set_ylim(0, max(220, parte["atingimento_pct"].max() + 15))
        estilo_eixo(ax, "y")
        if n < len(cats):
            ax.set_xticklabels([])
        else:
            ax.tick_params(axis="x", rotation=45)
    fig.suptitle("A1 – Atingimento da meta por mês (azul = meta batida; linha tracejada = 100%)",
                 x=0.01, ha="left", fontweight="bold")
    png = salvar_png(fig, "a1_meta_realizado")

    return {"linhas": len(df), "metas_batidas": int(df["bateu"].sum()),
            "batidas_com_prejuizo": int((df["bateu"] & (df["lucro"] < 0)).sum()), "csv": csv, "png": png}
