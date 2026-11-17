# 12 perguntas prováveis sobre o código

**1. O que acontece se eu rodar duas vezes?**
Nada muda. `upsert_em_lotes` usa `UpdateOne({_id}, {$set: …}, upsert=True)`. Na segunda vez todo `_id` já existe com o mesmo conteúdo: o MongoDB conta como "casado" e não modifica. O log mostra inseridos=0, modificados=0, iguais=500.

**2. Por que o documento não tem a data da carga?**
Se tivesse, o `$set` mudaria esse campo em toda execução e os 500 documentos contariam como "modificados". A prova de idempotência ficaria poluída. A data vai para o log e para o `manifesto.json`.

**3. Por que `_id` = Order ID e não ObjectId?**
O upsert precisa achar o documento anterior por uma chave estável. Um ObjectId novo a cada carga criaria 500 documentos duplicados por execução. O `_id` também já tem índice único sem custo extra.

**4. Por que `ordered=False` no `bulk_write`?**
Com `ordered=True`, o primeiro documento recusado pelo validador interromperia o resto do lote. Com `False`, os válidos entram e os erros vão para o log e para o resumo.

**5. Explique a A1 linha a linha.**
`$unwind` gera um documento por item. `$group` soma valor e lucro por competência × categoria, e o `$addToSet` conta cada pedido uma vez. `$addFields` monta a chave `2018-04#Furniture`. `$lookup` busca em `metas_mensais` pelo `_id`, usando o índice do `_id`. `$unwind` abre a lista de 1 meta. `$project` calcula `atingimento_pct` e `bateu`. `$out` grava em `analytics_meta_realizado`.

**6. Por que esses índices?**
`competencia` atende o filtro do mês na reunião (A1). `praca.estado + praca.cidade` serve para abrir uma praça ou um estado (A2/A3). `itens.subcategoria` é multikey (um valor por item) e lista os pedidos de uma subcategoria com prejuízo (A4). Em `metas_mensais` não criei índice extra: o `$lookup` usa o `_id`. Com 500 documentos o ganho de desempenho é pequeno; os índices são para os filtros do gerente e para o crescimento.

**7. Como você garante que um documento errado não entra?**
Em duas camadas. No Python, as regras V1–V9 rejeitam a linha antes. No banco, o `$jsonSchema` com `validationAction: "error"` recusa o documento (erro 121, "Document failed validation"). Testei inserindo um documento inválido.

**8. Por que `Decimal`/`decimal128` e não float?**
Ponto flutuante gera centavos fantasmas na soma, e a conciliação compara a soma do banco com a do Parquet por igualdade exata (431.502,00).

**9. Como funciona a T10? Dá para descobrir o nome?**
`hmac.new(chave, nome.casefold(), sha256)`, truncado em 16 caracteres hexadecimais. Sem a chave do `.env` não dá para refazer o cálculo. Com SHA-256 puro daria: são só 332 nomes, e bastaria testar uma lista de nomes comuns. O teste `test_t10_…` confere isso.

**10. Por que os campos aparecem em ordem alfabética no banco?**
Quando o upsert cria o documento a partir de um `$set`, o MongoDB grava os campos em ordem lexicográfica. Ordem de campo não tem significado; os valores são os do exemplo da N2. Está em `desvios_da_N2.md`.

**11. O que é o `$unionWith` da A3?**
É o `UNION ALL` do SQL: junta na mesma saída o resultado de outra pipeline sobre `pedidos`. Uso para gravar três visões numa coleção só: por praça, por combinação de categorias e por perfil (1 item × 2+ itens).

**12. Se o Kaggle mudar a ordem das linhas, quebra?**
A `posicao` dos itens (T7) pode mudar, porque vem da ordem do arquivo. Mas não duplica nada: o pedido inteiro é regravado pelo `_id`. O upsert atualiza o documento, e a contagem continua 500.
