# Triagem trabalhista

Entrevista guiada para atendimento de reclamante, com mapeamento automático de
pedidos cabíveis, verificações de risco e conferência de prescrição.

**A triagem não usa IA.** É um motor de regras sobre um catálogo em YAML. Isso é
deliberado: esta é a camada que não pode alucinar e que ninguém copia. A IA entra
na camada de cima — o índice do corpus normativo e, depois, a redação da peça.

## Instalar na máquina de quem vai usar

Dois cliques, sem terminal e **sem VS Code** — ele é editor de código, não é
preciso para rodar. Basta o Python instalado (3.10 ou superior, de
[python.org](https://www.python.org/downloads/), marcando *"Add Python to PATH"*).

1. `instalar.bat` — uma vez só. Cria o ambiente, instala as dependências
   (~170 MB) e pergunta se quer baixar o modelo de busca por sentido (2,2 GB).
2. `abrir.bat` — no uso diário. Sobe o servidor e abre o navegador.

**Ponha a pasta num caminho curto** (`C:\triagem`, ou a Área de Trabalho). O
Windows corta caminhos acima de 260 caracteres e a instalação falha no meio, com
erro que não diz isso.

O que copiar junto:

| | |
|---|---|
| código | 321 KB |
| `dados/corpus.db` | 33 MB — não está no git, vai por fora |
| `modelos/` | 2,2 GB — opcional; o `instalar.bat` baixa se preferir |
| `dados/casos.db` | **nunca** — é dado de cliente |
| `.venv/` | não; o `instalar.bat` cria o dela |

Sem o modelo o sistema funciona: a consulta por referência e a busca por palavra
ficam inteiras, e o acerto@5 cai de 65/72 para 63/72 no conjunto de avaliação. Sem o
`corpus.db` a entrevista e a minuta ainda funcionam — as citações saem pelo
rótulo, sem transcrição.

## Rodar (desenvolvimento)

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --reload --reload-dir app
```

`--reload-dir app` limita o watcher ao código. Sem ele o reloader vigia também
`dados/`, que guarda a captura da CLT (3,5 MB) e o índice. Se o `--reload` der
problema no seu terminal, tire-o: ele só recarrega o servidor quando o código
muda, e não é necessário para usar o sistema.

Abre em <http://127.0.0.1:8000>. Três telas: a **entrevista** (`/`), a
**consulta à lei** (`/corpus`), que precisa do corpus montado, e a **minuta da
inicial** (`/peca`), gerada a partir das respostas da entrevista.

Testes rápidos, sem servidor:

```
python testar.py           # triagem
python testar_refs.py      # referências do catálogo -> dispositivos
python testar_corpus.py    # esquema do corpus: vigência e busca lexical
python testar_busca.py     # recuperação na CLT (exige o corpus ingerido)
python testar_caducidade.py # MP que caducou, e o texto anterior que volta
python testar_norma_estranha.py # norma de terceiro transcrita no meio da pagina
python testar_inicial.py   # qualificação e história dos fatos, ponta a ponta
python testar_peca.py      # a minuta: cisão, terceiro estado, ausência de valor
python testar_vias.py      # placar das vias sobre as 72 consultas de avaliacao.py
python analisar_rerank.py  # a folga que um reranqueador teria (exige vetores)
```

Para montar o corpus, uma vez só (leva menos de um minuto):

```
python -m app.corpus.indexar clt
```

Em <http://127.0.0.1:8000/corpus> a consulta aceita tanto referência
(`art. 71 §4º`, `arts. 58 e 59`, `art. 223-A`) quanto pergunta em linguagem
corrente — e sempre com a data em que a norma deve estar vigente.

## O que faz

- **Entrevista** com perguntas que aparecem conforme as respostas anteriores.
- **Qualificação das partes e história dos fatos** — os dois blocos que a peça
  exige e que sim/não nenhum entrega. O detalhe de fato (episódios de assédio,
  jornada real, nome do paradigma) só é perguntado **depois** que o pedido
  correspondente se confirma na triagem.
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
    entrevista.yaml      roteiro de perguntas (79, em 10 secoes)
    armadilhas.yaml      verificações que não são pedidos (12)
    pedidos/*.yaml       o catálogo — 26 pedidos
  corpus/
    refs.py              referência do catálogo -> dispositivo endereçável
    banco.py             índice normativo em SQLite: vigência, FTS5, vetores
    planalto.py          ingestão do HTML do Planalto
    indexar.py           CLI de ingestão, com conferência contra o catálogo
    busca.py             as vias de recuperação e a fusão RRF
  peca/
    redator.py           minuta da inicial — só dá forma, não decide
  templates/             Jinja2 — entrevista, relatório, casos, corpus e minuta
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

Os 92 `fundamentos` do catálogo já formam um grafo de citações: 82 referências
distintas, tipadas, ligando cada pedido às normas que o sustentam. O índice se
apoia nisso em vez de começar cego.

**Três vias de recuperação.** A ordem importa:

0. **Lookup determinístico.** `fundamento.ref` → dispositivo. Não é busca, é
   *join*, e cobre o uso mais frequente: conferir a norma que o relatório citou.
   [`app/corpus/refs.py`](app/corpus/refs.py) resolve as 82 referências do
   catálogo em 117 dispositivos, incluindo faixas (`arts. 223-A a 223-G`),
   listas (`par. 3o e par. 4o`) e cadeias (`art. 10, II, 'b'`).
1. **Esparsa (BM25/FTS5).** Consulta jurídica é cheia de token exato — "Súmula
   437", "art. 384". Vetor denso troca número; BM25 não.
2. **Densa (BGE-M3, 1024d).** Para quando o vocabulário da consulta não é o da
   lei — "dispensa imotivada" onde o art. 487 escreve "sem justo motivo".

Fusão por RRF, sem reranqueador — e isso foi **medido**, não presumido. Ver
[Sobre reranking](#sobre-reranking).

Consulta que *é* uma referência ("art. 384") não vai para o BM25: ali o token
"art" casa com o corpus inteiro e o resultado é ruído. Ela é roteada para a Via 0.

E quando a norma existe mas não vale na data pedida, a busca **diz isso** em vez
de devolver lista vazia ou, pior, dez artigos que nada têm a ver:

```
CLT, art. 384 nao estava em vigor em 2026-08-18: vigorou ate 2017-11-10
(Lei 13.467/2017).
```

**Vigência é por dispositivo, não por obra.** O art. 71 §4º tem uma redação até
10/11/2017 e outra depois — a Reforma mudou a regra *e* a natureza jurídica. Um
índice que guarda só a redação atual responde a pergunta errada num contrato de
2016, com a mesma cara de quem acerta. Por isso a chave em
[`app/corpus/banco.py`](app/corpus/banco.py) é `(urn, vigencia_inicio)` e toda
consulta passa por uma data do caso.

**Medida provisória que caduca não é norma revogada.** Revogação põe texto novo
no lugar do antigo. Caducidade apenas encerra a eficácia da MP — e o texto
anterior **volta**, sem que nenhuma norma nova seja publicada. O art. 223-C tem
três redações em cinco meses por causa disso:

```
11/11/2017 a 13/11/2017   texto da Reforma
14/11/2017 a 23/04/2018   texto da MP 808/2017
24/04/2018 até hoje       texto da Reforma, que retornou
```

A terceira não é redação nova, e é aí que a sucessão por ordem de documento
quebra: o bloco que retorna carrega o marcador da lei que o criou (11/11/2017), e
ler essa data como início poria a Reforma valendo durante a vigência da MP.

Quatro MPs caducaram sobre a CLT — 808/2017, 873/2019, 905/2019 e 955/2020. As
datas de publicação e de encerramento estão em `CADUCIDADE`, em
[`app/corpus/planalto.py`](app/corpus/planalto.py), e foram lidas dos Atos
Declaratórios do Congresso, não inferidas. Se a fonte trouxer "(Vigência
encerrada)" de uma MP fora dessa tabela, a ingestão avisa em vez de adivinhar.

**Nada é citável sem procedência.** Cada dispositivo aponta para uma fonte com
URL, data de captura e sha256. Citação que não se rastreia até lá não entra na
peça.

## Sobre reranking

A pergunta reaparece sempre: falta um reranqueador? Aqui a resposta é **não** — e
foi medida, não deduzida do que costuma valer em outros sistemas.

**Reranqueador não busca; ele reordena o que a busca já trouxe.** Isso confina o
ganho possível a um intervalo que dá para calcular antes de baixar modelo nenhum:

```
teto  = recall@50    o alvo está em algum lugar do lote de candidatos
piso  = acerto@5     o alvo já aparece nos cinco que a tela mostra
folga = teto - piso  o máximo que um reranqueador PERFEITO consertaria
```

[`analisar_rerank.py`](analisar_rerank.py) imprime essa conta sobre as 72
consultas de [`avaliacao.py`](avaliacao.py), divididas em dois grupos: **A**, em
que a advogada digita o termo que está no texto da lei, e **B**, em que digita o
termo forense que a lei não usa — "rescisão indireta" para o art. 483,
"hipersuficiente" para o art. 444, "pejotização" para o art. 442-B.

| via | acerto@1 | acerto@5 | MRR | recall@50 |
|---|---|---|---|---|
| lexical | 50/72 | 63/72 | 0,768 | 70/72 |
| densa | 49/72 | 55/72 | 0,714 | 69/72 |
| **fusão RRF** | **53/72** | **65/72** | **0,808** | **72/72** |

**Recall@50 é 72/72.** Quando a resposta está na CLT, a busca a encontra sempre; o
que falha é a ordem. Sobra uma folga de 7 consultas — e é só isso que um
reranqueador poderia disputar.

### O que aconteceu com reranqueadores reais

Dois foram postos no caminho e medidos sobre o mesmo gabarito, reordenando os 15
melhores candidatos da fusão:

| | tamanho | acerto@1 | acerto@5 | grupo B | latência |
|---|---|---|---|---|---|
| fusão RRF (hoje) | — | 53/72 | 65/72 | 16/20 | 63 ms |
| mmarco-mMiniLMv2 int8 | 119 MB | 50/72 | 64/72 | 13/20 | 141 ms |
| bge-reranker-base | 1,1 GB | 51/72 | 68/72 | 17/20 | 565 ms |

O modelo pequeno **piora**: nenhuma configuração testada superou a fusão em
acerto@5, e todas derrubaram o grupo B, que era justamente o alvo. A explicação é
de domínio — mMARCO é ranqueamento de passagem web, e dispositivo de CLT tem 176
caracteres na mediana, 15% deles abaixo de 80. "i) abandono de emprego;" não é
uma passagem.

O modelo grande ganha 3 consultas em acerto@5 e perde 2 em acerto@1. Com n=72, um
erro-padrão vale ~2,5 consultas: **o ganho está dentro do ruído**, e custa 1,1 GB
num pacote que já pesa 1,4 GB, mais 9× de latência por consulta.

### O que valeu mais que o reranqueador

Ajustar **uma constante**. O `k` do RRF estava em 60, valor herdado de avaliação
TREC, onde se fundem dezenas de sistemas parecidos. Aqui são duas listas, de
forças bem diferentes: com k=60 a curva achata, 1/(60+1) e 1/(60+10) quase
empatam, e a fusão vira média de opinião. Chegava a ficar **abaixo da via lexical
sozinha** no primeiro resultado.

| | acerto@1 | acerto@5 | MRR |
|---|---|---|---|
| k=60 (antes) | 47/72 | 63/72 | 0,760 |
| k=5 (agora) | 53/72 | 65/72 | 0,808 |

Seis consultas em acerto@1, de graça, sem modelo novo — mais do que qualquer
reranqueador testado entregou. O intervalo k=1..20 é um platô; o que importava era
não estar em 60.

**Quando reabrir a discussão.** Hoje o corpus é só a CLT. Quando entrarem CF,
súmulas do TST, OJs e NRs, o lote de candidatos passa a misturar obras e a chance
de o topo vir sujo cresce — aí a folga aumenta e a conta muda. O caminho a medir
primeiro é `bge-reranker-v2-m3`, da mesma família do modelo de embeddings já
usado; o obstáculo é tamanho: 2,3 GB, sem ONNX oficial publicado.

Uma ressalva sobre o gabarito: as 72 consultas têm resposta **na CLT** por
construção. Recall@50 de 100% quer dizer "quando a resposta está no corpus, a
busca acha" — não "o sistema responde tudo". Pergunta sobre FGTS, terceirização ou
súmula não tem onde cair, porque essas obras ainda não foram ingeridas.

## A minuta da inicial

`/peca` monta a peça a partir das mesmas respostas que alimentam o relatório.
**Não há modelo de linguagem no caminho** — o texto é função determinista das
respostas, então o mesmo caso produz sempre a mesma minuta, e qualquer
divergência se explica lendo o template em vez de reexecutar um modelo.

O redator ([`app/peca/redator.py`](app/peca/redator.py)) **não decide nada**.
Quais pedidos cabem, quais se cindem por período e qual redação da lei valia na
data do caso já foram resolvidos pelo motor e pelo corpus. Aqui só se dá forma —
e é isso que mantém a auditoria onde ela já estava.

O efeito aparece no pedido que atravessa a Reforma. Ele vira dois no texto, e a
*mesma* referência do catálogo resolve em duas redações distintas:

```
Intervalo intrajornada suprimido (até 10/11/2017)
   CLT, art. 71, § 4º   1994-07-27 a 2017-11-10
   "...ficará obrigado a remunerar o período correspondente..."
Intervalo intrajornada suprimido (a partir de 11/11/2017)
   CLT, art. 71, § 4º   2017-11-11 a hoje
   "...de natureza indenizatória, apenas do período suprimido..."
```

Três decisões que valem mais que o código:

- **A minuta não apura valor.** Nem número, nem lacuna `[VALOR]` — lacuna que
  ninguém preenche vira peça protocolada com o marcador dentro. O art. 840 §1º
  continua exigindo o valor; ele vem do contador ou do PJe-Calc.
- **Pedido "a investigar" não entra no corpo**, e também não some: sai numa lista
  própria, ao fim, com a pergunta que o destrancaria. Achatar o terceiro estado
  dentro da peça desfaria o que a triagem construiu.
- **A narrativa dos fatos entra literal.** Reescrever fato dito pelo cliente vira
  alegação que ele não fez.

Obra que ainda não está no corpus — súmulas do TST, CF — é citada pelo rótulo,
sem transcrição. Citar sem transcrever é útil; transcrever de memória, não.

## Estado

Triagem completa. Em andamento e a fazer:

| | | |
|---|---|---|
| **Corpus** | CLT pronta | 3.663 dispositivos, 5.752 redações, com eixo de vigência. Faltam CF, súmulas e OJs do TST, NRs, súmulas do TRT-13. |
| **Via densa** | pronta | BGE-M3 em ONNX na CPU. Fusão RRF acerta 65 de 72 no conjunto de avaliação, com recall@50 de 72/72. Reranking foi medido e reprovado - ver [Sobre reranking](#sobre-reranking). |
| **Inicial** | minuta pronta | Os quatro blocos — qualificação, fatos, fundamentação, pedidos — saem como peça em `/peca`, montada por template. Sem modelo de linguagem: o texto é função determinista das respostas. |
| **Recurso, embargos, contrarrazões** | a fazer | Partem de um **documento** (sentença, acórdão, recurso da outra parte), não da entrevista. Exigem uma camada de leitura que não existe. |
| **Processo parado** | a fazer | Consultor de próxima medida para processo que anda devagar há anos. |
| **Jurisprudência** | a decidir | Uso principal é **citar na peça**, o que torna o validador de citações obrigatório. Uso secundário é aferir viabilidade. Muda a escala e exige rastrear superação de tese, não vigência. |

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
- **O catálogo cita um artigo revogado.** `Verbas rescisórias` aponta para
  `arts. 129 a 147`, e o art. 141 foi revogado pela Lei 13.874/2019. A ingestão
  acusa isso a cada execução. É correção de YAML, não de código.
- **As datas de vigência são aproximadas, exceto a da Reforma e as das quatro MPs
  que caducaram.** O marcador do Planalto traz a data de *publicação* da norma
  alteradora, que só coincide com a vigência quando não há vacatio legis. Para
  11/11/2017 e para as MPs da tabela `CADUCIDADE` as datas são exatas, porque vêm
  de fonte própria.
- **A vigência escalonada da MP 905/2019 não está modelada.** Ela entrou em vigor
  em 90 dias para os arts. 161, 634 e 634-A, e na publicação para o resto; o
  índice usa a publicação para todos. O catálogo não cita nenhum dos três, então
  isso só afeta busca livre nesses artigos.
- **194 dispositivos têm janelas de vigência que se sobrepõem**, 38 deles em datas
  a partir de 2010. A causa é outra: quando o Planalto repete um texto sem
  marcador legível, a redação cai no piso de 1943 e passa a cobrir período que não
  lhe pertence. Nenhum deles é citado pelo catálogo — a Via 0 está limpa —, mas a
  busca livre pode devolver duas redações para a mesma data.
- 1.258 redações ficaram marcadas como revogadas sem data legível na fonte. Elas
  nunca são servidas como vigentes — na dúvida o índice cala, em vez de afirmar.
- A qualificação é a única parte do sistema que **não influencia nada**. É de
  propósito, e há teste que tranca isso: se um CPF digitado passar a mudar quais
  pedidos cabem, `testar_inicial.py` quebra.

## O que saiu, e por quê

Havia uma calculadora de 16 verbas com memória linha a linha. Foi removida em
18/08/2026, a pedido de quem usa o sistema: apuração de valor é trabalho de
perito e calculista, não de quem redige a inicial.

A decisão tem um custo conhecido — o art. 840 §1º exige valor por pedido, e agora
esse número vem de fora. Em troca, sai do projeto a camada de maior risco: as
fórmulas de reflexo nunca foram conferidas contra fonte autoritativa, e um valor
errado saía com a mesma aparência de certeza que um valor certo.

O histórico está em git, no commit anterior a esta remoção.
