# Triagem trabalhista — Fases 1 e 2

Entrevista guiada para atendimento de reclamante, com mapeamento automático de
pedidos cabíveis, verificações de risco, conferência de prescrição e **apuração
de valores com memória de cálculo**.

**Não usa IA.** É um motor de regras sobre um catálogo em YAML, mais uma
calculadora determinística em `Decimal`. Isso é deliberado: esta é a camada que
não pode alucinar e que ninguém copia.

## Rodar

```
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Abre em <http://127.0.0.1:8000>. Testes rápidos, sem servidor:

```
python testar.py           # triagem
python testar_calculo.py   # calculadora, com dois cenários
```

## O que faz

- **Entrevista** com perguntas que aparecem conforme as respostas anteriores.
- **Painel vivo** classificando cada pedido em três estados:
  - *cabível* — os requisitos estão confirmados;
  - *a investigar* — falta uma resposta para decidir, **e o sistema diz qual**;
  - *afastado* — alguma condição foi negada.
- **Prescrição** bienal e quinquenal. O corte quinquenal não é aviso na tela:
  ele **limita os meses que entram na conta**.
- **Corte da Reforma** (11/11/2017): pedidos com regra e natureza jurídica
  distintas são apurados de forma cindida por período.
- **Cálculo** de 16 verbas com reflexos, e **memória linha a linha** com a
  fórmula de cada operação.
- **Verificações do polo ativo** — ressalva de valores estimativos, justiça
  gratuita, sucumbência, art. 844 §2º, competência, quesitos periciais.
- **Relatório** imprimível, e casos salvos em SQLite.

O terceiro estado é o coração da triagem. Sem ele o sistema descartaria pedidos
em silêncio só porque uma pergunta ainda não foi feita — que é exatamente o erro
que ele existe para evitar.

## A calculadora

Três decisões estruturais:

**`Decimal`, nunca `float`.** O cálculo soma centenas de parcelas ao longo de
anos; erro de arredondamento binário aparece no total e destrói a credibilidade
da memória na primeira conferência da parte contrária.

**A ordem de execução importa.** Adicionais habituais precisam ser apurados
*antes* das horas extras, porque majoram a base (Súmula 264 do TST). A cascata
está em [`app/calculo/motor.py`](app/calculo/motor.py):

1. insalubridade × periculosidade — não acumulam (art. 193 §2º); vence a mais
   benéfica e a outra fica marcada como alternativa, fora do total;
2. adicional noturno, sobre a base já majorada;
3. demais verbas, sobre a base com todos os adicionais;
4. rescisórias, multas e estabilidades.

**Se um número não pode ser explicado linha a linha, ele não entra no pedido.**
Toda operação vira uma linha da memória com a fórmula em texto. É por isso que a
calculadora é determinística e não sai de modelo de linguagem.

### Parâmetros que você mantém

[`app/calculo/parametros.yaml`](app/calculo/parametros.yaml) guarda salário
mínimo por competência, divisores e percentuais. **Esses valores não são
afirmados pelo sistema** — você confere e mantém. Se a apuração passar da última
competência da tabela, a calculadora avisa em vez de usar valor defasado em
silêncio.

## Estrutura

```
app/
  schema.py              contratos de dados (pydantic)
  motor.py               avaliação de três estados, prescrição, regimes
  persistencia.py        SQLite — fonte da verdade
  main.py                FastAPI
  catalogo/
    loader.py            carga + validação cruzada dos YAML
    entrevista.yaml      roteiro de perguntas (57)
    armadilhas.yaml      verificações que não são pedidos (9)
    pedidos/*.yaml       o catálogo — 21 pedidos
  calculo/
    dinheiro.py          aritmética Decimal e formatação BRL
    periodo.py           corte quinquenal, cisão pela Reforma, competências
    verbas.py            16 módulos de cálculo, um por verba
    motor.py             orquestrador — a cascata
    parametros.yaml      valores que você mantém
  templates/             Jinja2
  static/                CSS e JS (sem dependência externa, sem CDN)
dados/casos.db           criado no primeiro salvamento
```

## Duas passadas na entrevista

A triagem responde **se** o pedido cabe; a quantificação apura **quanto**. As
perguntas de quantificação (`mostrar_se_pedido`) só aparecem depois que o pedido
correspondente é confirmado — por isso são avaliadas num segundo passe.

O loader recusa o catálogo se um pedido usar uma pergunta de quantificação no
seu `quando`: isso criaria dependência circular, já que a triagem passaria a
depender do próprio resultado.

## Como editar o catálogo

É onde mora o valor. Todo pedido vive num YAML e é validado na subida do
servidor — se um campo de `quando` apontar para pergunta inexistente, o app não
sobe, em vez de desligar um pedido em silêncio.

Campos de `Pedido` que merecem atenção:

| Campo | Para quê |
|---|---|
| `quando` | Grupos de condições. Dentro do grupo vale **E**, entre grupos vale **OU**. |
| `marco_temporal` | `contrato` (padrão) ou `rescisao`. Define qual data escolhe o regime da Reforma. Multa do art. 477 é `rescisao`: o fato gerador é a extinção. |
| `cindir` | `true` só quando a regra muda a ponto de exigir pedidos separados por período (ex.: intervalo intrajornada). `variacao_temporal` sozinha é informativa. |
| `controverso` | Em `fundamentos`, marca tese em disputa. O relatório imprime "conferir no índice" em vez de afirmar. |

## Estado

Fases 1 e 2 completas. Próximas:

3. Corpus (CLT, súmulas e OJs do TST, NRs) em SQLite + Qdrant embutido, com
   BGE-M3 (denso + esparso) e fusão RRF.
4. Geração da inicial por preenchimento de slots, com citação obrigatória,
   validador de citações e exportação em DOCX.
5. Cartão de ponto (OCR + tabulação).
6. Consultor de próxima medida para processo parado.

## ⚠ As fórmulas de cálculo ainda NÃO foram validadas

As 16 fórmulas em [`app/calculo/verbas.py`](app/calculo/verbas.py) foram escritas
sem conferência contra fonte autoritativa. Os **parâmetros legais** (divisor 220,
adicional de 50%, noturno de 20%, periculosidade de 30%, FGTS 8% + 40%, aviso da
Lei 12.506/2011) são texto de lei e têm confiança alta. As **fórmulas de reflexo**
não têm.

Pontos já identificados como provavelmente incorretos:

| Ponto | Problema |
|---|---|
| FGTS sobre férias indenizadas | `reflexos_sobre()` aplica 8% sobre o conjunto, mas férias indenizadas e o terço ficam fora da base (art. 15 §6º da Lei 8.036/90 c/c art. 28 §9º da Lei 8.212/91) |
| Média dos reflexos de horas extras | A Súmula 347 do TST manda usar **média física** (número de horas); o código usa média por valor |
| RSR e o sábado | Só domingos entram como repouso; em semana de 5 dias o sábado costuma entrar também |
| Avos de férias | Apurados pelo ano civil da saída, e não pelo período aquisitivo contado do aniversário de admissão |

**Referência para validar:** Manual de Cálculos da Justiça do Trabalho (CSJT) e,
melhor ainda, comparação linha a linha contra a saída do **PJe-Calc** num caso
conhecido.

Até isso ser feito, a calculadora serve para **dimensionar ordem de grandeza e
não esquecer verba** — não para fixar o valor do art. 840 §1º em peça.

## Limites conhecidos

- O conteúdo jurídico do catálogo é um **ponto de partida** e precisa ser
  revisado por quem vai usar. Referências marcadas `controverso: true` são as que
  eu deliberadamente não afirmei.
- **O cálculo usa o último salário informado** para todo o período. A evolução
  salarial real exige a ficha financeira — entra com a leitura de contracheques.
- **Não há correção monetária, juros, INSS nem IRRF.** Os valores são nominais,
  para dimensionar o pedido do art. 840 §1º. A discussão de correção (ADCs 58 e
  59) precisa entrar antes de usar em liquidação.
- **RSR considera apenas domingos.** Feriados variam por município e norma
  coletiva, então o valor apurado é um piso.
- Avos de 13º e férias são apurados pelo ano civil da saída; período aquisitivo
  com marco distinto exige ajuste manual.
- As horas extras vêm de estimativa do cliente. A apuração definitiva sai da
  tabulação dos cartões de ponto (fase 5).
