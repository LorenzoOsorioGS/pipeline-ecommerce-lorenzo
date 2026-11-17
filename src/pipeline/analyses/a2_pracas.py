"""A2 – Ranking de praças.

Pergunta de negócio: quais praças (cidade + estado) puxam e quais seguram o resultado?
Coleção: só pedidos (praca, totais.valor, totais.lucro, cliente_ref) – sem $unwind, porque os totais
já estão calculados no documento (T12).
Esperado (profiling da N2): 25 praças; Indore lidera com 76 pedidos e 79.069; 6 praças com lucro negativo.
"""
from __future__ import annotations

from .comum import AZUL, TINTA_2, VERMELHO, estilo_eixo, exportar_csv, figura, rodar, salvar_png

SAIDA = "analytics_pracas"

PIPELINE = [
    # agrupar pelo subdocumento inteiro: {cidade, estado} separa Chandigarh/Punjab de Chandigarh/Haryana
    {"$group": {
        "_id": "$praca",
        "pedidos": {"$sum": 1},
        "faturamento": {"$sum": "$totais.valor"},
        "lucro": {"$sum": "$totais.lucro"},
        "clientes": {"$addToSet": "$cliente_ref"},  # aproximado: o nome não identifica pessoa (D5)
    }},
    {"$project": {
        "_id": 0,
        "cidade": "$_id.cidade",
        "estado": "$_id.estado",
        "pedidos": 1,
        "faturamento": 1,
        "lucro": 1,
        "ticket_medio": {"$round": [{"$toDouble": {"$divide": ["$faturamento", "$pedidos"]}}, 2]},
        "clientes_distintos": {"$size": "$clientes"},
    }},
    {"$sort": {"faturamento": -1}},
    {"$out": SAIDA},
]


def executar(db) -> dict:
    df = rodar(db, PIPELINE, SAIDA).sort_values("faturamento", ascending=False)
    csv = exportar_csv(df[["cidade", "estado", "pedidos", "faturamento", "lucro", "ticket_medio",
                           "clientes_distintos"]], "a2_pracas")

    fig, ax = figura(9, 7.5)
    ordem = df.sort_values("faturamento")
    rotulos = [f"{c} / {e}" for c, e in zip(ordem["cidade"], ordem["estado"])]
    cores = [VERMELHO if lc < 0 else AZUL for lc in ordem["lucro"]]
    ax.barh(rotulos, ordem["faturamento"], color=cores, height=0.7)
    for y, (fat, ped) in enumerate(zip(ordem["faturamento"], ordem["pedidos"])):
        ax.text(fat + 600, y, f"{ped} ped.", va="center", fontsize=7.5, color=TINTA_2)
    ax.xaxis.set_major_formatter(lambda x, _: f"{x:,.0f}".replace(",", "."))
    ax.set_xlabel("Faturamento no ano fiscal")
    ax.set_title("A2 – Faturamento por praça (vermelho = lucro anual negativo)", loc="left")
    ax.set_xlim(0, ordem["faturamento"].max() * 1.12)
    estilo_eixo(ax, "x")
    png = salvar_png(fig, "a2_pracas")

    return {"pracas": len(df), "lider": f"{df.iloc[0]['cidade']} ({int(df.iloc[0]['pedidos'])} pedidos)",
            "pracas_com_prejuizo": int((df["lucro"] < 0).sum()), "csv": csv, "png": png}
