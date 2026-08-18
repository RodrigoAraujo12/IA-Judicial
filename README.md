# Triagem trabalhista

Entrevista guiada para atendimento de reclamante, com mapeamento automático de
pedidos cabíveis, verificações de risco e conferência de prescrição.

**A triagem não usa IA.** É um motor de regras sobre um catálogo em YAML. Isso é
deliberado: esta é a camada que não pode alucinar e que ninguém copia. A IA entra
na camada de cima — o índice do corpus normativo e, depois, a redação da peça.

## Rodar

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\uvicorn app.main:app --reload
```

Abre em <http://127.0.0.1:8000>. Testes rápidos, sem servidor:

```
python testar.py           # triagem
python testar_refs.py      # referências do catálogo -> dispositivos
python testar_corpus.py    # esquema do corpus: vigência e busca lexical
```

## O que faz

- **Entrevista** com perguntas que aparecem conforme as respostas anteriores.
- **Painel vivo** classificando cada pedido em três estados:
  - *cabível* — os requisitos estão confirmados;
  - *a investigar* — falta uma resposta para decidir, **e o sistema diz qual**;
  - *afastado* — alguma condição foi negada.
- **Prescrição** bienal e quinquenal, contadas da data do ajuizamento quando a
  ação já existe — usar hoje num processo antigo encolheria o período apurável.
- **Corte da Reforma** (11/11/2017): pedidos com regra e natureza jurídica
  distintas são marcados para formulação cindida por período.
- **Verificações do polo ativo** — ressalva de valores estimativos, justiça
  gratuita, sucumbência, art. 844 §2º, competência, quesitos periciais.
- **Lista de documentos a solicitar**, montada a partir dos pedidos em jogo.
- **Relatório** imprimível, e casos salvos em SQLite.

O terceiro estado é o coração da triagem. Sem ele o sistema descartaria pedidos
em silêncio só porque uma pergunta ainda não foi feita — que é exatamente o erro
que ele existe para evitar.

## Estrutura

```
app/
  schema.py              contratos de dados (pydantic)
  motor.py               avaliação de três estados, prescrição, regimes
  persistencia.py        SQLite — casos, a fonte da verdade
  main.py                FastAPI
  catalogo/
    loader.py            carga + validação cruzada dos YAML
    entrevista.yaml      roteiro de perguntas (41)
    armadilhas.yaml      verificações que não são pedidos (9)
    pedidos/*.yaml       o catálogo — 21 pedidos
  corpus/
    refs.py              referência do catálogo -> dispositivo endereçável
    banco.py             índice normativo em SQLite: vigência, FTS5, vetores
  templates/             Jinja2
  static/                CSS e JS (sem dependência externa, sem CDN)
dados/casos.db           criado no primeiro salvamento
dados/corpus.db          índice do corpus — reconstruível e descartável
```

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

## O corpus normativo

Os 73 `fundamentos` do catálogo já formam um grafo de citações: 68 referências
distintas, tipadas, ligando cada pedido às normas que o sustentam. O índice se
apoia nisso em vez de começar cego.

**Três vias de recuperação.** A ordem importa:

0. **Lookup determinístico.** `fundamento.ref` → dispositivo. Não é busca, é
   *join*, e cobre o uso mais frequente: conferir a norma que o relatório citou.
   [`app/corpus/refs.py`](app/corpus/refs.py) resolve as 68 referências do
   catálogo em 105 dispositivos, incluindo faixas (`arts. 223-A a 223-G`),
   listas (`par. 3o e par. 4o`) e cadeias (`art. 10, II, 'b'`).
1. **Esparsa (BM25/FTS5).** Consulta jurídica é cheia de token exato — "Súmula
   437", "art. 384". Vetor denso troca número; BM25 não.
2. **Densa (BGE-M3, 1024d).** Para a pergunta em linguagem de cliente.

Fusão por RRF. Reranking só se a precisão não bastar — o próprio BGE-M3 devolve
vetores ColBERT, o que evita carregar um segundo modelo.

**Vigência é por dispositivo, não por obra.** O art. 71 §4º tem uma redação até
10/11/2017 e outra depois — a Reforma mudou a regra *e* a natureza jurídica. Um
índice que guarda só a redação atual responde a pergunta errada num contrato de
2016, com a mesma cara de quem acerta. Por isso a chave em
[`app/corpus/banco.py`](app/corpus/banco.py) é `(urn, vigencia_inicio)` e toda
consulta passa por uma data do caso.

**Nada é citável sem procedência.** Cada dispositivo aponta para uma fonte com
URL, data de captura e sha256. Citação que não se rastreia até lá não entra na
peça.

## Estado

Triagem completa. Em andamento e a fazer:

| | | |
|---|---|---|
| **Corpus** | em andamento | CLT, CF, súmulas e OJs do TST, NRs. Parser de referências e esquema prontos; falta a ingestão. |
| **Peças** | a fazer | Modelos de peça por preenchimento de slots, com citação obrigatória, validador de citações e exportação em DOCX. |
| **Processo parado** | a fazer | Consultor de próxima medida para processo que anda devagar há anos. |
| **Jurisprudência** | a decidir | Acórdãos, em fase própria: muda a escala e exige rastrear superação de tese, não vigência. |

## Limites conhecidos

- O conteúdo jurídico do catálogo é um **ponto de partida** e precisa ser
  revisado por quem vai usar. Referências marcadas `controverso: true` são as que
  eu deliberadamente não afirmei.
- **O sistema não apura valores.** A indicação exigida pelo art. 840 §1º vem de
  fora — do contador, do calculista ou do PJe-Calc.
- Duas referências estão classificadas de forma imprecisa no catálogo e o
  `testar_refs.py` as aponta: `IN 41/2018 do TST` está como `tipo: lei` (é
  instrução normativa) e `ADI 5766` como `tipo: tema_stf` (é ação direta). Nenhuma
  quebra nada hoje; ambas quebrariam o validador de citações.
- `mostrar_se_pedido` e o segundo passe do motor continuam de pé, mas **hoje sem
  nenhum usuário** — eram o mecanismo das perguntas de quantificação. Ficaram
  porque a redação da peça precisa do mesmo padrão: detalhe que só faz sentido
  perguntar depois que o pedido se confirma.

## O que saiu, e por quê

Havia uma calculadora de 16 verbas com memória linha a linha. Foi removida em
18/08/2026, a pedido de quem usa o sistema: apuração de valor é trabalho de
perito e calculista, não de quem redige a inicial.

A decisão tem um custo conhecido — o art. 840 §1º exige valor por pedido, e agora
esse número vem de fora. Em troca, sai do projeto a camada de maior risco: as
fórmulas de reflexo nunca foram conferidas contra fonte autoritativa, e um valor
errado saía com a mesma aparência de certeza que um valor certo.

O histórico está em git, no commit anterior a esta remoção.
