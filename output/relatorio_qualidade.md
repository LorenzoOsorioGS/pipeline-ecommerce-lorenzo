# Relatório de qualidade da carga

Gerado pelo pipeline em 2026-11-17T16:18:17. Regras V1–V9 e T1–T12: ver `docs/RASTREABILIDADE.md`.

## 1. Linhas por arquivo

| Arquivo | Lidas | Rejeitadas/descartadas | Aprovadas |
|---|---:|---:|---:|
| List of Orders.csv | 560 | 60 | 500 |
| Order Details.csv | 1500 | 0 | 1500 |
| Sales target.csv | 36 | 0 | 36 |

## 2. O que foi descartado e por quê

| Arquivo | Regra | Motivo | Linhas |
|---|---|---|---:|
| List of Orders.csv | V1 | linha com todos os campos vazios | 60 |

Cada linha descartada, com o número da linha no arquivo original, está em `output/rejeitados/`.

## 3. O que foi corrigido (transformação)

- **T1** – espaços removidos nas pontas: 16 campo(s) (no dataset atual, o estado `"Kerala "`).
- **T5** – par cidade × estado corrigido em 3 pedido(s):
  - B-25905: Delhi/Madhya Pradesh → Delhi/Delhi
  - B-25909: Delhi/Madhya Pradesh → Delhi/Delhi
  - B-25913: Delhi/Madhya Pradesh → Delhi/Delhi
  - Premissa: Delhi não fica em Madhya Pradesh. Chandigarh mantido em Punjab e Haryana (capital dos dois estados).

## 4. O que foi marcado, sem remover (T9, decisão D4)

- Limite de valor atípico (Q3 + 1,5 × IQR): Q1 = 45.00, Q3 = 322.00, limite = **737.50**.
- `flags.valor_atipico`: 155 itens.
- `flags.prejuizo` (lucro < 0): 503 itens.
- `flags.prejuizo_maior_que_venda` (lucro < −valor): 14 itens (possível devolução ou erro de digitação; mantidos e marcados para revisão).

## 5. Alertas

Nenhum.
