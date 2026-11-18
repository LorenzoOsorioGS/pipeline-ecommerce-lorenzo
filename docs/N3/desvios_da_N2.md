# Desvios da N3 em relação à N2

A regra foi: a N2 vence. Onde a implementação precisou ser diferente, o desvio está aqui, com o motivo.
Nenhuma regra V/T, coleção, índice ou análise da N2 foi retirada.

**Atualização de 18/11/2026:** a N2 foi revisada para descrever o que a N3 implementou. Os itens abaixo já constam nela e ficam aqui como registro do que mudou e do motivo.

## 1. MongoDB sem Docker na máquina do autor (infraestrutura)

- **N2:** Docker Compose sobe MongoDB 7 e mongo-express.
- **N3:** o `docker-compose.yml` está no repositório como especificado (MongoDB 7.0 + mongo-express 1.0.2, volume e healthcheck). Na máquina em que desenvolvi e apresento não há Docker nem WSL, e instalar exigiria administrador e reinício no dia da entrega. Por isso criei `scripts/mongo_local.ps1`, que sobe o **MongoDB 7.0.25 oficial em versão portátil** (zip da MongoDB, SHA-256 conferido) nas mesmas porta e URI. O código do pipeline é o mesmo nos dois casos: só muda quem sobe o banco.
- **Consequência honesta:** o caminho `docker compose up -d` não foi executado por mim. O arquivo segue a documentação oficial das imagens, mas não foi testado nesta máquina.

## 2. Visualizador no lugar do mongo-express quando não há Docker

- **N2:** mongo-express para ver os documentos no navegador.
- **N3:** com Docker, continua o mongo-express (`http://localhost:8081`). Sem Docker, tentei instalar o mongo-express 1.0.2 via npm e a instalação falha: ele depende de um pacote baixado direto do GitHub, que o npm 11 desta máquina não conseguiu resolver. A versão 0.54 instala, mas traz um driver MongoDB 2.2, incompatível com o MongoDB 7. Por isso escrevi `scripts/visualizar.py`, um visualizador **somente leitura** na mesma porta 8081, que lista as coleções e mostra cada documento em Extended JSON.

## 3. Ajustes de apresentação nas aggregations

- **N2:** esboços das pipelines A1–A4 (seção 6).
- **N3:** as pipelines são as mesmas, com três ajustes que não mudam o resultado:
  - `$project` com `_id: 0` e os campos do grupo "achatados" (`competencia`, `categoria`, `cidade`…), para a coleção ouro e o CSV ficarem legíveis;
  - `$toDouble` + `$round` nos percentuais (`atingimento_pct`, `ticket_medio`, `margem_pct`). Divisão de `decimal128` devolve `decimal128` com 34 dígitos, e para percentual isso só atrapalha a leitura;
  - na A3, uma terceira visão no `$unionWith` (perfil 1 item × 2+ itens, com ticket médio). O número já estava no texto da N2 (267,58 × 1.391,02) e agora sai do banco.

## 4. Ordem dos campos no documento

- **N2:** o exemplo da seção 4.2 mostra os campos na ordem `_id`, `data_pedido`, `competencia`…
- **N3:** no banco, os campos de primeiro nível aparecem em ordem alfabética (`_id`, `_carga`, `cliente_ref`…). É comportamento do MongoDB: quando o upsert cria o documento a partir de um `$set`, ele grava os campos em ordem lexicográfica. Ordem de campo não tem significado num documento, e os valores são idênticos aos do exemplo. Mantive `UpdateOne` + `$set` porque é o que a N2 e o enunciado especificam para a carga idempotente. `ReplaceOne` preservaria a ordem, mas mudaria a operação especificada.

## 5. Staging da validação

- **N2:** a validação aprova ou rejeita e a transformação segue.
- **N3:** para cada etapa rodar sozinha (`--step transform` sem refazer a validação), as linhas aprovadas são gravadas em `data/processed/_validado/` antes da transformação. É um detalhe de execução, não uma camada nova: a camada prata continua sendo `data/processed/*.parquet`.

## 6. Logs do banco

- **N2 original:** previa o log do pipeline, sem log das consultas do banco.
- **N3:** o `scripts/mongo_local.ps1` sobe o MongoDB com o profiler ligado (`--profile 2 --slowms 0`) e grava `logs/mongod.log`. O `scripts/consultas_log.py` resume esse arquivo em `logs/consultas.log`. A pasta `logs/` fica fora do Git. O profiler cria a coleção `system.profile`, que o `inspecionar.py` e o visualizador não listam.
- **Limite:** vale para o MongoDB portátil. O `docker-compose.yml` não foi alterado.
