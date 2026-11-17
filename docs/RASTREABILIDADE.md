# Rastreabilidade N2 → N3

Cada item especificado na N2 aponta para o código que o implementa e para o modo de demonstrar.
Os números da coluna "como demonstrar" são os que o pipeline imprime no dataset real.
Desvios em relação à N2 estão em [`N3/desvios_da_N2.md`](N3/desvios_da_N2.md).

Atalhos usados abaixo: `main` = `python src/main.py --step <etapa>`, `insp` = `python scripts/inspecionar.py`.

## Camadas e etapas (N2 seção 5.1, Figura 2)

| Item da N2 | Implementação | Como demonstrar |
|---|---|---|
| Camada raw (bronze): CSVs sem alteração + manifesto | [`extract.py` → `extrair()`](../src/pipeline/extract.py#L40) | `main extract` → `data/raw/manifesto.json` |
| Extração por kagglehub com fallback manual (5.2) | [`extract.py` → `_baixar_kaggle()`, `extrair()`](../src/pipeline/extract.py#L32) | log "kagglehub baixou…"; com `EXTRACT_MODE=local` usa só `data/raw/` |
| SHA-256, bytes e linhas por arquivo (5.2) | [`extract.py` → `_sha256()`, `_linhas_de_dados()`](../src/pipeline/extract.py#L21) | log: `List of Orders.csv sha256=abe7bf6c8aa7… bytes=23615 linhas=560` |
| Camada processed (prata) em Parquet (5.4) | [`transform.py` → `transformar()`](../src/pipeline/transform.py#L211) | `data/processed/pedidos.parquet`, `itens.parquet`, `metas.parquet` |
| Rejeitados + relatório de qualidade (5.3) | [`validate.py` → `salvar()`](../src/pipeline/validate.py#L169), [`relatorio.py`](../src/pipeline/relatorio.py#L10) | `output/rejeitados/*.csv`, `output/relatorio_qualidade.md` |
| Camada analytics (ouro) com `$out` (6) | [`analyses/comum.py` → `rodar()`](../src/pipeline/analyses/comum.py#L29) + `{"$out": …}` em cada análise | `insp contar` → coleções `analytics_*` |
| Resumo da execução | [`main.py` → `imprimir_resumo()`](../src/main.py) | final de `main all` |

## Regras de validação (N2 Tabela 4)

| Regra | Implementação | Resultado no dataset real |
|---|---|---|
| V1 linha toda vazia | [`v1_linhas_vazias()`](../src/pipeline/validate.py#L51), aplicada em [`validar()` L124](../src/pipeline/validate.py#L124) | 60 linhas descartadas de List of Orders |
| V2 Order ID no padrão e único | [`v2_order_id_invalido()`](../src/pipeline/validate.py#L57) | 0 rejeitados |
| V3 data dd-mm-aaaa válida | [`v3_data_invalida()`](../src/pipeline/validate.py#L65) | 0 rejeitados |
| V4 item órfão | [`validar()` L144](../src/pipeline/validate.py#L144) | 0 rejeitados |
| V5 pedido sem item | [`validar()` L149](../src/pipeline/validate.py#L149) | 0 rejeitados |
| V6 Amount > 0, Quantity ≥ 1, Profit numérico | [`v6_numero_invalido()`](../src/pipeline/validate.py#L71) | 0 rejeitados |
| V7 categoria e subcategoria coerentes | [`v7_categoria_invalida()`](../src/pipeline/validate.py#L80) + [`referencias.py`](../src/pipeline/referencias.py) | 0 rejeitados |
| V8 meta válida e única | [`v8_meta_invalida()`](../src/pipeline/validate.py#L90) | 0 rejeitadas (36 = 12 × 3) |
| V9 cidade × estado contra referência | [`v9_cidade_estado()`](../src/pipeline/validate.py#L100) + [`referencias.py`](../src/pipeline/referencias.py) | 3 pedidos a corrigir pela T5, 0 desconhecidos |

Testes: [`tests/test_validate.py`](../tests/test_validate.py).

## Regras de transformação (N2 Tabela 5)

| Regra | Implementação | Resultado no dataset real |
|---|---|---|
| T1 remover espaços | [`t1_remover_espacos()`](../src/pipeline/transform.py#L31) | 16 campos (`"Kerala "`) |
| T2 renomear colunas | [`RENOMEAR` / `t2_renomear()`](../src/pipeline/transform.py#L43) | colunas em snake_case |
| T3 data com formato explícito | [`t3_converter_data()`](../src/pipeline/transform.py#L57) | 500 datas, 01/04/2018 a 31/03/2019 |
| T4 competência e mês fiscal | [`t4_competencia()`](../src/pipeline/transform.py#L66) | 12 competências; abril = 1 |
| T5 corrigir cidade × estado | [`t5_corrigir_cidade_estado()`](../src/pipeline/transform.py#L73) | B-25905, B-25909, B-25913 → Delhi/Delhi |
| T6 Decimal e inteiro | [`t6_tipar()`](../src/pipeline/transform.py#L88) | `decimal128` no Mongo; soma exata 431.502,00 |
| T7 posição do item | [`t7_posicao()`](../src/pipeline/transform.py#L101) | máx. 12 itens por pedido |
| T8 preço unitário | [`t8_preco_unitario()`](../src/pipeline/transform.py#L111) | 2,33 a 872,60 |
| T9 flags (D4) | [`t9_flags()`](../src/pipeline/transform.py#L117) | limite 737,50; 155 atípicos, 503 prejuízo, 14 prejuízo > venda |
| T10 HMAC do cliente (D5) | [`t10_pseudonimizar()`](../src/pipeline/transform.py#L136) | 332 `cliente_ref`; nome descartado |
| T11 meta → competência e `_id` | [`t11_meta()`](../src/pipeline/transform.py#L145) | 36 metas, `_id` `2018-04#Furniture` |
| T12 totais e montagem do agregado | [`t12_totais()`](../src/pipeline/transform.py#L154), [`montar_documento_pedido()`](../src/pipeline/transform.py#L172) | `insp pedido B-25608` = exemplo da N2 seção 4.2 |

Testes: [`tests/test_transform.py`](../tests/test_transform.py).

## Carga (N2 seção 5.5)

| Item da N2 | Implementação | Como demonstrar |
|---|---|---|
| Validador `$jsonSchema` antes dos dados (9.3) | [`SCHEMA_PEDIDOS`, `SCHEMA_METAS`](../src/pipeline/load.py#L25), [`garantir_colecao()`](../src/pipeline/load.py#L70) | inserir documento inválido → erro 121 "Document failed validation" |
| Upsert idempotente, `_id` = chave natural | [`upsert_em_lotes()`](../src/pipeline/load.py#L81) | `main load` 2× → 2ª vez: inseridos=0, modificados=0, iguais=500 |
| Lotes configuráveis, `ordered=False` | [`upsert_em_lotes()` L94](../src/pipeline/load.py#L94) + `BATCH_SIZE` no `.env` | log: 5 lotes de 100 |
| Documento sem data de execução | [`montar_documento_pedido()` L198](../src/pipeline/transform.py#L198) | `_carga` só tem `sha256_origem` e `versao_pipeline` |
| Índices (9.2) | [`INDICES_PEDIDOS`](../src/pipeline/load.py#L57), criados em [`carregar()`](../src/pipeline/load.py#L147) | `idx_competencia`, `idx_praca`, `idx_itens_subcategoria` |
| Conciliação (OE1) | [`conciliar()`](../src/pipeline/load.py#L124) | "conciliação OK: pedidos 500/500, metas 36/36, soma 431502.00" |

Testes: [`tests/test_load.py`](../tests/test_load.py) (idempotência e atualização sem duplicar).

## Modelo de agregados (N2 seção 9)

| Item da N2 | Implementação | Como demonstrar |
|---|---|---|
| `pedidos` com `itens[]`, `praca`, `totais`, `_carga` embutidos | [`montar_documento_pedido()`](../src/pipeline/transform.py#L172) | http://localhost:8081 → pedidos → B-25608 |
| `metas_mensais` separada, `_id` = `AAAA-MM#Categoria` | [`montar_documento_meta()`](../src/pipeline/transform.py#L202) | `metas_mensais` → `2018-04#Furniture` |
| Sem coleção `clientes` (D3, D5) | — (decisão de não criar) | `insp contar` lista só pedidos, metas e analytics |

## Análises (N2 seção 6)

| Análise | Implementação | Resultado (= prévia do profiling da N2) |
|---|---|---|
| A1 meta × realizado (`$unwind`, `$group`, `$lookup`) | [`a1_meta_realizado.py`](../src/pipeline/analyses/a1_meta_realizado.py#L14) | 36 linhas, 16 metas batidas, 5 com lucro negativo |
| A2 ranking de praças (`$group` por subdocumento) | [`a2_pracas.py`](../src/pipeline/analyses/a2_pracas.py#L14) | 25 praças, Indore 76 pedidos, 6 praças com prejuízo |
| A3 venda casada (`$unionWith`) | [`a3_venda_casada.py`](../src/pipeline/analyses/a3_venda_casada.py#L15) | 235 pedidos de 1 item; ticket 267,58 × 1.391,02 |
| A4 margem por subcategoria | [`a4_margem_subcategoria.py`](../src/pipeline/analyses/a4_margem_subcategoria.py#L14) | 17 subcategorias; Tables −17,74% |
| Exportação CSV + PNG | [`analyses/comum.py`](../src/pipeline/analyses/comum.py#L48) | `output/a1_*.png` … `a4_*.png` e CSVs |

## Objetivos específicos (N2 seção 2)

| Objetivo | Verificação | Resultado |
|---|---|---|
| OE1 carga completa e conciliada | `conciliar()` | 500 pedidos, 1.500 itens, 36 metas, soma 431.502,00 = CSV |
| OE2 idempotência | 2ª execução de `main load` + `test_load.py` | 0 inseridos, 0 modificados |
| OE3 rastreabilidade da qualidade | `output/relatorio_qualidade.md` + `output/rejeitados/` | 60 descartadas (V1), 3 corrigidas (T5), 16 aparadas (T1) |
| OE4 análises no banco | `analyses/*.py` terminam em `$out` | resultados iguais à prévia do profiling |

## Infraestrutura e ferramentas (N2 seção 7)

| Item da N2 | Implementação |
|---|---|
| Docker Compose com MongoDB 7 + mongo-express | [`docker-compose.yml`](../docker-compose.yml) (volume e healthcheck) |
| Python + pandas + pyarrow + pymongo + kagglehub + matplotlib + pytest + python-dotenv | [`requirements.txt`](../requirements.txt), [`config.py`](../src/pipeline/config.py) + `.env` |
| Execução por etapa (papel do orquestrador na N3) | [`src/main.py`](../src/main.py) `--step` |
