# Decisões da N2: o que escolhi, por que e o que descartei

Este arquivo é a base da minha defesa. Cada decisão tem o número que a sustenta, tirado de [`profiling.md`](profiling.md).

---

## D0. Dados da capa

- **Decisão:** Centro Universitário CESUSC (UniCESUSC), Florianópolis; disciplina "Desenvolvimento com Linguagens Disruptivas I"; professor Flaris Roland Feller; Equipe10.
- **Motivo:** é o que consta na versão entregue anteriormente e no sistema da faculdade.

---

## D1. Cenário: gerente comercial que fecha o mês por praça

- **Decisão:** o usuário dos dados é o gerente comercial da loja online. Todo início de mês ele faz a reunião de resultados e precisa responder três coisas: cada categoria bateu a meta? Quais praças (cidades) estão puxando ou segurando o resultado? Estamos vendendo só um item por cliente quando dava para vender mais?
- **Motivo:** é a rotina que eu vivo no varejo de ótica: meta mensal por categoria (armação, lente, solar), acompanhamento de ticket médio e venda casada (cliente que leva a armação sem a lente é venda perdida). Os dados sustentam o cenário: só 16 de 36 metas foram batidas, 235 dos 500 pedidos (47%) têm um item só e o ticket médio é 863 contra mediana 416,50.
- **Adaptação honesta:** o dataset não tem campo de vendedor nem de loja. Usei a **cidade de entrega como "praça"**, que é o papel que a loja física teria no meu dia a dia. São 24 cidades, e Indore (76 pedidos) e Mumbai (68) concentram 28,8% dos pedidos.
- **Alternativas descartadas:**
  - *Controle de margem (analista de rentabilidade):* os números são fortes (164 pedidos fecham no prejuízo, Tables com margem de −17,7%), mas o foco seria só custo. A margem não sumiu: entrou como uma das análises do gerente (ver D2).
  - *Expansão regional (logística):* o dataset não tem frete, prazo nem custo de entrega. Metade da análise viraria suposição, o que contradiz a regra de só citar número real.

---

## D2. Perguntas de negócio: as 4 análises do gerente

- **Decisão:** a reunião mensal do gerente usa quatro análises, nesta ordem:
  1. **A1 – Meta × realizado:** atingimento (%) por categoria e mês. Electronics fechou o ano em 128,1%, Clothing em 79,9% e Furniture em 95,7%.
  2. **A2 – Ranking de praças:** pedidos, faturamento, ticket médio e lucro por cidade. Indore lidera com 76 pedidos; Jaipur (−753) e Ahmedabad (−880) vendem e dão prejuízo.
  3. **A3 – Venda casada:** percentual de pedidos com um item só, por praça e por categoria, e quais pares de categoria saem juntos. Hoje 235 de 500 pedidos têm um item; 207 misturam categorias.
  4. **A4 – Margem por subcategoria:** onde a venda vira prejuízo. Tables tem −17,74%, Electronic Games −3,16% e Saree tem o maior faturamento de Clothing (53.511) com margem de 0,66%.
- **Motivo:** é a sequência de uma reunião de resultados real: primeiro "batemos a meta?", depois "onde?", depois "como vender mais por cliente?" e por fim "estamos vendendo com lucro?". A A4 entrou porque bater meta com prejuízo não é resultado bom, e o dado mostra isso: Electronics bateu a meta de maio/2018 com 142,3% e lucro de −2.523.
- **Alternativa descartada:** *recompra por cliente.* Os nomes não identificam pessoas (43 nomes aparecem em mais de uma cidade, e não há sobrenome nem ID), então qualquer número de recompra seria enganoso. Também descartei *previsão de vendas*: 12 meses de histórico não bastam para um modelo sério.

---

## D3. Modelagem: pedido com itens embutidos, meta separada, resultado na camada analítica

- **Decisão:** três grupos de coleções no MongoDB:
  - `pedidos`: um documento por pedido, `_id` = Order ID, com os itens embutidos em `itens[]`, a praça em `praca{cidade, estado}` e os totais em `totais{}`;
  - `metas_mensais`: um documento por mês × categoria (36), `_id` = `"AAAA-MM#Categoria"`;
  - `analytics_*`: uma coleção por análise (A1 a A4), recriada a cada execução pelo próprio MongoDB com `$out`, que substitui a coleção inteira de uma vez e não deixa sobra de execução anterior. É a camada "ouro".
- **Motivo (padrão de acesso):** as quatro análises leem o pedido inteiro. A2 e A3 usam só os totais e a lista de categorias do pedido, então não precisam de `$lookup` nem de `$unwind`. A1 e A4 abrem os itens com `$unwind`, mas os itens já estão dentro do documento lido. O documento é pequeno: no máximo 12 itens, média 3. Os itens não têm ID próprio no dataset e só existem dentro do pedido, então são parte do agregado, não uma entidade independente.
- **Por que a meta fica separada:** ela não pertence a nenhum pedido. É uma regra do mês × categoria que o gerente define antes de o mês acontecer. Embutir a meta em cada pedido repetiria o mesmo número em dezenas de documentos (Clothing de março/2019 tem 54 pedidos) e obrigaria a atualizar todos se a meta mudasse.
- **Por que o resultado (realizado, atingimento) não fica dentro da meta:** o resultado é derivado e muda sempre que um pedido entra. Guardei-o nas coleções `analytics_*`, que são recalculadas, e não no documento de origem. Assim, `pedidos` e `metas_mensais` guardam só fatos, e um recálculo nunca corrompe a origem.
- **Por que não há coleção `clientes`:** o nome não identifica uma pessoa (D5) e nenhuma das quatro análises parte do cliente.
- **Alternativas descartadas:**
  - *itens em coleção própria com referência (`order_id`):* toda análise viraria `$lookup`, que é uma junção relacional feita no banco de documentos. Faria sentido se um pedido pudesse ter milhares de itens (limite de 16 MB por documento) ou se o item fosse alterado sozinho. Nenhum dos dois acontece aqui.
  - *fato mensal pré-agregado (mês × praça × categoria):* responde A1, A2 e A4 rápido, mas apaga o pedido. A A3 (venda casada) precisa saber quais categorias saíram **no mesmo pedido**, e isso se perde na agregação.

---

## D4. Outliers e lucro negativo: manter e marcar

- **Decisão:** nenhum item é removido por ser outlier ou por ter prejuízo. Cada item recebe marcas (`flags`):
  - `prejuizo`: `Profit < 0` (503 itens, 33,5%);
  - `valor_atipico`: `Amount` acima do limite superior do IQR, calculado sobre a própria carga (hoje 737,50; são 155 itens);
  - `prejuizo_maior_que_venda`: `Profit < −Amount` (14 itens), sinal de possível erro de digitação ou de devolução lançada como venda.
- **Motivo:** os 155 outliers de `Amount` somam 209.958 de 431.502, ou seja, 48,7% do faturamento. Removê-los faria toda meta parecer não batida. São vendas de ticket alto (Printers, Tables, Phones), não erro. O prejuízo também é informação de negócio: é exatamente o que a A4 quer mostrar ao gerente. Marcar permite as duas leituras ("com" e "sem" atípicos) com um filtro, sem perder dado.
- **Alternativas descartadas:**
  - *remover:* apaga metade da receita e esconde o problema de margem;
  - *limitar ao teto do IQR (winsorizar):* altera valores reais de venda. O realizado deixaria de bater com a soma do CSV e a comparação com a meta ficaria falsa;
  - *manter sem marcar:* funciona para as somas, mas obriga o analista a recalcular o IQR toda vez que quiser isolar casos atípicos.

---

## D5. LGPD: pseudonimizar o nome com HMAC-SHA256

- **Decisão:** o campo `CustomerName` não entra no MongoDB. No lugar dele vai `cliente_ref`, que é HMAC-SHA256(chave secreta, nome normalizado) truncado em 16 caracteres hexadecimais. A chave fica no `.env`, fora do Git.
- **Motivo:** nenhuma análise precisa do nome (princípio da necessidade, LGPD art. 6º, III). Mesmo um primeiro nome, combinado com cidade e data do pedido, pode ajudar a identificar alguém. Usei **HMAC com chave** e não um hash simples porque são só 332 nomes distintos: um SHA-256 puro seria revertido em segundos testando uma lista de nomes indianos comuns (ataque de dicionário). Com a chave secreta, quem só tem o banco não consegue refazer o hash. A mesma entrada gera sempre o mesmo `cliente_ref`, então a carga continua idempotente e ainda dá para contar clientes distintos por praça, com a ressalva dos homônimos.
- **Alternativas descartadas:**
  - *manter o nome:* expõe dado pessoal sem nenhuma análise que precise dele;
  - *SHA-256 sem chave:* parece seguro, mas não é, pelo tamanho do universo de nomes;
  - *descartar o campo:* seguro, mas perde a contagem aproximada de clientes distintos e impede, no futuro, ligar o pedido a um cadastro real de clientes, que a loja teria com ID próprio.

---

## D6. Nomes dos campos no MongoDB

- **Decisão:** nomes em português, no vocabulário do varejo: `competencia` (`AAAA-MM`) para o mês de referência, `praca` para a cidade + estado, `posicao` para a ordem do item no pedido, `valor_alvo` para a meta do mês e `totais` para os valores calculados do pedido. Os valores de `categoria` e `subcategoria` ficam em inglês, como na origem.
- **Motivo:** "competência" é como o varejo e a contabilidade chamam o mês ao qual uma venda pertence, e é o termo que uso no trabalho. Isso deixa as consultas legíveis para o gerente. As categorias ficam em inglês porque são a chave lógica com as metas: traduzir criaria um ponto de erro sem ganho.
- **Alternativas descartadas:** manter os nomes originais em inglês com espaço e hífen (`Order Date`, `Sub-Category`), que obrigam a usar aspas em toda consulta; e traduzir os valores de categoria, que quebraria a ligação com `Sales target.csv` se um dos lados fosse traduzido diferente.
