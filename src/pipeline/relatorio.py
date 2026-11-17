"""Gera output/relatorio_qualidade.md: o que a validação encontrou, o que foi descartado e por quê,
o que a transformação corrigiu e o que foi marcado (sem remover)."""
from __future__ import annotations

from . import config

DESTINO = config.OUTPUT / "relatorio_qualidade.md"


def escrever(val: dict, trans: dict | None = None) -> None:
    config.OUTPUT.mkdir(parents=True, exist_ok=True)
    L = ["# Relatório de qualidade da carga", "",
         f"Gerado pelo pipeline em {val['executado_em']}. Regras V1–V9 e T1–T12: ver `docs/RASTREABILIDADE.md`.", "",
         "## 1. Linhas por arquivo", "",
         "| Arquivo | Lidas | Rejeitadas/descartadas | Aprovadas |", "|---|---:|---:|---:|"]
    for nome, lidas in val["lidas"].items():
        aprov = val["aprovadas"][nome]
        L.append(f"| {nome} | {lidas} | {lidas - aprov} | {aprov} |")

    L += ["", "## 2. O que foi descartado e por quê", ""]
    if val["rejeicoes"]:
        L += ["| Arquivo | Regra | Motivo | Linhas |", "|---|---|---|---:|"]
        for r in val["rejeicoes"]:
            L.append(f"| {r['arquivo']} | {r['regra']} | {r['motivo']} | {r['linhas']} |")
        L += ["", "Cada linha descartada, com o número da linha no arquivo original, está em `output/rejeitados/`."]
    else:
        L.append("Nenhuma linha descartada.")

    L += ["", "## 3. O que foi corrigido (transformação)", ""]
    if trans:
        L.append(f"- **T1** – espaços removidos nas pontas: {trans['T1_campos_aparados']} campo(s) "
                 "(no dataset atual, o estado `\"Kerala \"`).")
        L.append(f"- **T5** – par cidade × estado corrigido em {len(trans['T5_corrigidos'])} pedido(s):")
        L += [f"  - {c}" for c in trans["T5_corrigidos"]] or ["  - nenhum"]
        L.append("  - Premissa: Delhi não fica em Madhya Pradesh. Chandigarh mantido em Punjab e Haryana "
                 "(capital dos dois estados).")
    else:
        L.append(f"Transformação ainda não executada. A validação (V9) encontrou {val['a_corrigir_t5']} "
                 "pedido(s) que a T5 vai corrigir.")

    L += ["", "## 4. O que foi marcado, sem remover (T9, decisão D4)", ""]
    if trans:
        t9 = trans["T9"]
        L += [f"- Limite de valor atípico (Q3 + 1,5 × IQR): Q1 = {t9['q1']:.2f}, Q3 = {t9['q3']:.2f}, "
              f"limite = **{t9['limite_atipico']}**.",
              f"- `flags.valor_atipico`: {t9['valor_atipico']} itens.",
              f"- `flags.prejuizo` (lucro < 0): {t9['prejuizo']} itens.",
              f"- `flags.prejuizo_maior_que_venda` (lucro < −valor): {t9['prejuizo_maior_que_venda']} itens "
              "(possível devolução ou erro de digitação; mantidos e marcados para revisão)."]
    else:
        L.append("Transformação ainda não executada.")

    L += ["", "## 5. Alertas", ""]
    L += [f"- {a}" for a in val["alertas"]] or ["Nenhum."]
    DESTINO.write_text("\n".join(L) + "\n", encoding="utf-8")
