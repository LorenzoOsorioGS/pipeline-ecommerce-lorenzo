# Roteiro da apresentação da N3 (10 minutos)

Antes de começar: MongoDB no ar (`scripts\mongo_local.ps1` ou `docker compose up -d`), terminal na raiz do projeto, navegador em http://localhost:8081, VS Code aberto.

| Tempo | O que mostrar | O que dizer |
|---|---|---|
| 0:00–1:00 | README (topo + diagrama) | "Implementei o pipeline da minha N2: o gerente comercial que fecha o mês por praça. Cinco etapas, cada regra da N2 com código próprio." |
| 1:00–2:00 | `docs/RASTREABILIDADE.md` | "Cada regra da especificação (V1–V9, T1–T12, coleções, índices, análises) tem uma linha apontando para a função que a implementa. O que mudou está em `desvios_da_N2.md`, com o motivo." |
| 2:00–2:45 | `scripts\demo.ps1`, passos 1–3 (sobe o banco, limpa, EXTRACT) | "O kagglehub baixa o dataset e o manifesto guarda o hash de cada arquivo. Se o Kaggle cair, uso o CSV manual." |
| 2:45–3:45 | passo 4 (VALIDATE) + `output/relatorio_qualidade.md` | "60 linhas vazias descartadas pela V1. Nada some em silêncio: cada linha descartada está em `output/rejeitados/` com o motivo." |
| 3:45–5:00 | passo 5 (TRANSFORM) + `transform.py` (abrir `t3_converter_data` e `t10_pseudonimizar`) | "A T3 usa formato explícito porque 193 datas têm dia ≤ 12. A T5 corrige Delhi. A T9 marca 155 atípicos sem remover. A T10 troca o nome por HMAC com chave secreta." |
| 5:00–6:00 | passo 6 (LOAD) + `upsert_em_lotes` | "Validador `$jsonSchema` antes, upsert em lotes de 100, índices depois e conciliação: 431.502 no banco igual ao CSV." |
| 6:00–6:45 | passo 7 + navegador `pedidos/B-25608` | "Esse é o agregado: os itens dentro do pedido, as flags, os totais. O Tables tem prejuízo maior que a venda." |
| 6:45–7:30 | passo 8 (IDEMPOTÊNCIA) | "Rodei a carga de novo: 0 inseridos, 0 modificados, contagem igual. O `_id` é o Order ID e o documento não guarda data de execução." |
| 7:30–9:00 | passo 9 (ANALYZE) + `a1_meta_realizado.py` + gráficos A1 e A3 | "A A1 é `$unwind`, `$group`, `$lookup` na meta pelo `_id`, e `$out`. Resultado: 16 de 36 metas batidas, 5 com prejuízo. Na A3, 47% dos pedidos saem com um item só, com ticket de 267 contra 1.391." |
| 9:00–9:30 | `python -m pytest -q` | "20 testes: datas reais, regras, HMAC e idempotência." |
| 9:30–10:00 | README, "Limitações e evolução" | "86 KB não são Big Data. O desenho escala: Kafka, Spark e Airflow entram sem mudar as regras nem o modelo." |

Se o tempo apertar, pule o pytest e mostre só o gráfico da A1.
