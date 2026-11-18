"""A3 – Venda casada.

Pergunta de negócio: quanto do movimento sai com um item só, em que praças, e quais categorias já são
vendidas juntas? (Na ótica: o cliente que leva a armação e não leva a lente.)
Coleção: pedidos (praca, totais.item_unico, totais.categorias, totais.valor).
Esperado (profiling da N2): 235 pedidos de 1 item; ticket 267,58 contra 1.391,02 nos de 2+ itens;
combinação mais comum = Clothing sozinho (195), depois as três categorias juntas (76).
"""
from __future__ import annotations

from .comum import AZUL, TINTA_2, estilo_eixo, exportar_csv, figura, rodar, salvar_png

SAIDA = "analytics_venda_casada"

PIPELINE = [
    # visão 1 – por praça: quantos pedidos saem com 1 item só
    {"$group": {"_id": "$praca", "pedidos": {"$sum": 1},
                "pedidos_1_item": {"$sum": {"$cond": ["$totais.item_unico", 1, 0]}}}},
    {"$project": {"_id": 0, "tipo": "praca", "cidade": "$_id.cidade", "estado": "$_id.estado",
                  "pedidos": 1, "pedidos_1_item": 1,
                  "pct_1_item": {"$round": [{"$multiply": [{"$divide": ["$pedidos_1_item", "$pedidos"]}, 100]}, 1]}}},
    # $unionWith = UNION ALL do SQL: junta na mesma saída o resultado de outra pipeline
    # visão 2 – combinações de categoria; totais.categorias está em ordem alfabética (T12),
    # então ["Clothing","Electronics"] é sempre a mesma chave de agrupamento
    {"$unionWith": {"coll": "pedidos", "pipeline": [
        {"$group": {"_id": "$totais.categorias", "pedidos": {"$sum": 1}}},
        {"$project": {"_id": 0, "tipo": "combinacao", "categorias": "$_id", "pedidos": 1}},
    ]}},
    # visão 3 – perfil: ticket médio de quem leva 1 item contra quem leva 2 ou mais
    {"$unionWith": {"coll": "pedidos", "pipeline": [
        {"$group": {"_id": "$totais.item_unico", "pedidos": {"$sum": 1}, "ticket_medio": {"$avg": "$totais.valor"}}},
        {"$project": {"_id": 0, "tipo": "perfil", "item_unico": "$_id", "pedidos": 1, "ticket_medio": 1}},
    ]}},
    {"$out": SAIDA},
]


def executar(db) -> dict:
    df = rodar(db, PIPELINE, SAIDA)
    pracas = df[df["tipo"] == "praca"].sort_values(["pct_1_item", "cidade"], ascending=[False, True])
    combos = df[df["tipo"] == "combinacao"].copy()
    combos["categorias"] = combos["categorias"].map(lambda c: " + ".join(c))
    combos = combos.sort_values(["pedidos", "categorias"], ascending=[False, True])
    perfil = df[df["tipo"] == "perfil"].sort_values("item_unico", ascending=False)

    exportar_csv(pracas[["cidade", "estado", "pedidos", "pedidos_1_item", "pct_1_item"]], "a3_venda_casada_pracas")
    exportar_csv(combos[["categorias", "pedidos"]], "a3_venda_casada_combinacoes")
    csv = exportar_csv(perfil[["item_unico", "pedidos", "ticket_medio"]], "a3_venda_casada_perfil")

    total = int(pracas["pedidos"].sum())
    um_item = int(pracas["pedidos_1_item"].sum())
    geral = um_item / total * 100
    fig, ax = figura(9, 7.5)
    ordem = pracas.iloc[::-1]
    ax.barh([f"{c} / {e}" for c, e in zip(ordem["cidade"], ordem["estado"])], ordem["pct_1_item"],
            color=AZUL, height=0.7)
    ax.axvline(geral, color=TINTA_2, linestyle="--", linewidth=1)
    ax.text(geral + 0.8, -1.1, f"média da loja: {geral:.0f}%", fontsize=8, color=TINTA_2)
    ax.set_ylim(-1.6, len(ordem) - 0.4)
    t1 = perfil[perfil["item_unico"]]["ticket_medio"].iloc[0]
    t2 = perfil[~perfil["item_unico"].astype(bool)]["ticket_medio"].iloc[0]
    ax.set_xlabel("% dos pedidos da praça com um item só")
    ax.set_title(f"A3 – Pedidos de 1 item por praça · ticket 1 item = {t1:,.2f} × 2+ itens = {t2:,.2f}"
                 .replace(",", "X").replace(".", ",").replace("X", "."), loc="left", fontsize=10)
    ax.set_xlim(0, 100)
    estilo_eixo(ax, "x")
    png = salvar_png(fig, "a3_venda_casada")

    return {"pedidos_1_item": um_item, "pct_1_item": round(geral, 1), "ticket_1_item": round(t1, 2),
            "ticket_2_mais": round(t2, 2), "combinacao_mais_comum": f"{combos.iloc[0]['categorias']} "
            f"({int(combos.iloc[0]['pedidos'])})", "csv": csv, "png": png}
