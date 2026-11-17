"""CLI do pipeline.

Uso:  python src/main.py --step extract|validate|transform|load|analyze|all
Cada etapa lê a saída da anterior em disco (data/raw → data/processed → MongoDB),
então dá para rodar uma etapa sozinha durante a demonstração.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time

from pipeline import config, extract, load, relatorio, transform, validate
from pipeline.analyses import TODAS

log = logging.getLogger("main")
ETAPAS = ("extract", "validate", "transform", "load", "analyze")


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline E-Commerce Data → MongoDB (N3)")
    parser.add_argument("--step", choices=(*ETAPAS, "all"), default="all")
    args = parser.parse_args()

    cfg = config.carregar()
    config.configurar_logging(cfg.log_level)
    etapas = ETAPAS if args.step == "all" else (args.step,)
    resumo: dict = {"tempos": {}}

    for etapa in etapas:
        log.info("==================== %s ====================", etapa.upper())
        ini = time.perf_counter()
        if etapa == "extract":
            resumo["extract"] = extract.extrair(cfg.extract_mode)
        elif etapa == "validate":
            v = validate.validar()
            resumo["validate"] = validate.salvar(v)
            relatorio.escrever(resumo["validate"])
        elif etapa == "transform":
            resumo["transform"] = transform.transformar(cfg.hmac_key)
            val = json.loads((validate.PASTA_VALIDADO / "validacao.json").read_text(encoding="utf-8"))
            relatorio.escrever(val, resumo["transform"])
            log.info("relatório de qualidade atualizado: %s", relatorio.DESTINO)
        elif etapa == "load":
            db = load.conectar(cfg.mongo_uri, cfg.mongo_db)
            resumo["load"] = load.carregar(db, cfg.batch_size)
        elif etapa == "analyze":
            db = load.conectar(cfg.mongo_uri, cfg.mongo_db)
            resumo["analyze"] = {}
            for nome, modulo in TODAS:
                r = modulo.executar(db)
                resumo["analyze"][nome] = r
                log.info("%s → %s | %s", nome, r["png"].name,
                         ", ".join(f"{k}={v}" for k, v in r.items() if k not in ("csv", "png")))
        resumo["tempos"][etapa] = time.perf_counter() - ini

    imprimir_resumo(resumo)
    conc = resumo.get("load", {}).get("conciliacao")
    return 1 if conc and not conc["ok"] else 0


def imprimir_resumo(r: dict) -> None:
    linhas = ["", "=" * 70, "RESUMO DA EXECUÇÃO", "=" * 70]
    if "extract" in r:
        linhas.append(f"Extração ({r['extract']['origem']}):")
        for nome, info in r["extract"]["arquivos"].items():
            linhas.append(f"  {nome:<20} {info['linhas']:>5} linhas  {info['bytes']:>6} bytes  "
                          f"sha256 {info['sha256'][:12]}…")
    if "validate" in r:
        v = r["validate"]
        linhas.append("Validação (lidas → aprovadas):")
        for nome, lidas in v["lidas"].items():
            linhas.append(f"  {nome:<20} {lidas:>5} → {v['aprovadas'][nome]:>5}")
        linhas.append("  Descartadas:" if v["rejeicoes"] else "  Descartadas: nenhuma")
        for rej in v["rejeicoes"]:
            linhas.append(f"    {rej['linhas']:>4} × {rej['regra']} – {rej['motivo']} ({rej['arquivo']})")
        for a in v["alertas"]:
            linhas.append(f"  Alerta: {a}")
    if "transform" in r:
        t = r["transform"]
        linhas += [f"Transformação: {t['pedidos']} pedidos, {t['itens']} itens, {t['metas']} metas em Parquet",
                   f"  T1 campos aparados: {t['T1_campos_aparados']} | T5 cidade×estado corrigidos: "
                   f"{len(t['T5_corrigidos'])}",
                   f"  T9 outliers marcados (valor > {t['T9']['limite_atipico']}): {t['T9']['valor_atipico']} | "
                   f"prejuízo: {t['T9']['prejuizo']} | prejuízo > venda: {t['T9']['prejuizo_maior_que_venda']}",
                   f"  T10 clientes pseudonimizados: {t['T10_clientes_distintos']} códigos"]
    if "load" in r:
        for col in ("pedidos", "metas_mensais"):
            c = r["load"][col]
            linhas.append(f"Carga {col:<14}: inseridos={c['inseridos']} atualizados={c['modificados']} "
                          f"iguais={c['iguais']} erros={len(c['erros'])}")
        c = r["load"]["conciliacao"]
        linhas.append(f"Conciliação: {'OK' if c['ok'] else 'FALHOU'} – pedidos {c['pedidos_banco']}, "
                      f"itens {c['itens_banco']}, metas {c['metas_banco']}, soma de valor {c['soma_valor_banco']}")
    if "analyze" in r:
        linhas.append("Análises (coleções analytics_* + CSV/PNG em output/):")
        for nome, a in r["analyze"].items():
            linhas.append(f"  {nome}: " + ", ".join(f"{k}={v}" for k, v in a.items() if k not in ("csv", "png")))
    linhas.append("Tempo por etapa: " + " | ".join(f"{k} {v:.2f}s" for k, v in r["tempos"].items()))
    linhas.append("=" * 70)
    for linha in linhas:
        log.info(linha)


if __name__ == "__main__":
    sys.exit(main())
