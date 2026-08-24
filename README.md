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

**O vetor precisa ver o dispositivo inteiro.** O orçamento de tokens da
embedding era 128, e isso truncava **900 das 5.748 redações** — 15,7% do corpus.
O corte não era aleatório: caía nos parágrafos. `texto_indexado` antepõe o rótulo,
a variante sem "§" e o caput ao texto do dispositivo, e nos subordinados esse
prefixo consumia o orçamento antes de o texto começar. No art. 71 §4º o prefixo
levava 91 dos 128 tokens, e o vetor **nunca via** "de natureza indenizatória" —
exatamente o termo pelo qual esse dispositivo é procurado.

O corpus inteiro cabe em 256 (mediana 83 tokens, p90 140, máximo 255). Subir o
teto custou 5 minutos de máquina, não uma reingestão: para texto que não estoura
128, o vetor nos dois orçamentos é bit a bit o mesmo — conferido, diferença máxima
`0.0` —, então só as 900 truncadas precisaram voltar ao modelo. O que mudou nas
72 consultas do gabarito:

| via | acerto@1 | acerto@5 | MRR | recall@50 |
|---|---|---|---|---|
| densa em 128 | 49/72 | 55/72 | 0,714 | 69/72 |
| densa em 256 | 50/72 | 57/72 | 0,738 | 71/72 |
| fusão em 128 | 53/72 | 65/72 | 0,808 | 72/72 |
| **fusão em 256** | **54/72** | **67/72** | **0,822** | **72/72** |

A via lexical não se moveu — 50/72 e 0,768 antes e depois —, o que é o controle:
a mudança ficou onde deveria. Casos individuais: o art. 71 §4º saiu de #7 para #1
na via densa, e o art. 469 §3º ("transferência, adicional de 25%") de #253 para
#18.

O `maxlen` fica gravado junto de cada vetor. Sem isso, mexer nessa constante não
refazia nada e os vetores do orçamento antigo continuavam no banco com cara de
saudáveis — a busca degradaria em silêncio, que é o modo de falha que este
projeto recusa. Com a coluna, `indexar vetores` sabe sozinho quais refazer.

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

**Súmula do TST tem vigência, e por isso entra no mesmo eixo da lei.** A Súmula
437 foi cancelada por perda de eficácia em 11.11.2017; a Súmula 450, pela decisão
da ADPF 501, em 14.08.2022. Um índice que guarde só "está cancelada" responde
errado a um caso de 2016 — a súmula valia, e a peça daquele período tem de
citá-la. Por isso o cancelamento vira **janela**, não sinalizador:
`vigencia_fim = 10.11.2017`. Só cai em `revogado` o cancelamento sem data legível
na fonte, e no Livro atual não há nenhum.

A fonte é o **Livro de Súmulas, OJs e PNs**, a publicação consolidada do próprio
Tribunal ([`app/corpus/tst.py`](app/corpus/tst.py)). A página `/sumulas` do site
não serve: é um SPA em React que entrega 1 KB de HTML e um `<div>` vazio. O Livro
sai em PDF e em RTF, e o RTF ganhou — PDF exigiria biblioteca de extração e
devolveria texto por coordenada, e coordenada não distingue título de corpo. O RTF
traz a quebra de parágrafo explícita, que é o que separa uma súmula da seguinte, e
lê-se com o `re` da biblioteca padrão. **Nenhuma dependência nova.**

Entram 1.056 verbetes: 463 súmulas (1 a 463, **sem uma lacuna na faixa**), 359 OJs
da SBDI-I, 156 da SBDI-II e 78 da SBDI-I Transitória. Ficam de fora SDC e
Precedentes Normativos, que só servem a dissídio coletivo.

Duas armadilhas do formato, ambas encontradas quebrando:

- **A mesma data significa o oposto conforme o status.** Em `(nova redação) - Res.
  185/2012` ela abre a vigência; em `(cancelada) - Res. 121/2003` ela a encerra.
  Ler as duas como início punha a súmula nascendo no dia em que morreu, com
  vigência aberta dali em diante.
- **O índice remissivo repete cada verbete sem texto.** Cortá-lo cedo demais
  ingere 4.700 fantasmas; tarde demais, zero verbetes — e este segundo aconteceu,
  porque a linha do sumário (`Índice Remissivo   H - 1 – 193`) casava o mesmo
  padrão do cabeçalho real.

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

| via | só CLT | | | com TST | | |
|---|---|---|---|---|---|---|
| | acerto@1 | acerto@5 | MRR | acerto@1 | acerto@5 | MRR |
| lexical | 50/72 | 63/72 | 0,768 | 42/72 | 59/72 | 0,671 |
| densa | 50/72 | 57/72 | 0,738 | 42/72 | 54/72 | 0,660 |
| **fusão RRF** | **54/72** | **67/72** | **0,822** | **47/72** | **62/72** | **0,739** |

**Os números caíram quando as súmulas entraram, e a queda precisa de leitura.** O
gabarito tem resposta **na CLT** por construção — foi escrito quando o corpus era
só a CLT. Com 1.056 verbetes do TST no índice, uma consulta pode agora ser
respondida por quem o gabarito não previa.

Das 25 consultas em que o alvo não é mais o primeiro, **16 têm um verbete do TST
no topo**. Olhando uma a uma, elas se dividem em dois grupos que não podem ser
somados:

- **O gabarito ficou estreito.** "abandono de emprego após trinta dias de falta"
  devolve a Súmula 32 — *"presume-se o abandono se o trabalhador não retornar no
  prazo de 30 dias"* — em vez da alínea `i` do art. 482, que só diz "abandono de
  emprego". A súmula é a resposta melhor. Idem "perda da gratificação após dez
  anos" → Súmula 372, e "sobreaviso" → Súmula 428.
- **Degradação real.** "rescisão indireta do contrato de trabalho" traz a Súmula
  69 em #1 — que fala de rescisão e revelia, nada a ver — e empurra o art. 483
  para #47. "grupo econômico responsabilidade solidária" traz a OJ 411, que diz o
  **oposto** do perguntado.

As duas vias caíram na mesma proporção (lexical −8, densa −8), o que **descarta** a
hipótese mais óbvia: não é o título em caixa alta da súmula inflando o BM25, senão
a via densa teria ficado de pé. É competição por densidade de corpus.

Corrigir isso pelo gabarito seria ajustar a régua ao resultado. O gabarito precisa
ser reescrito — decidindo, verbete a verbete, qual autoridade responde cada
consulta —, e isso é juízo jurídico, não ajuste de código.

**Recall@50 é 71/72**, contra 72/72 antes. Uma consulta saiu do lote.

### O que aconteceu com reranqueadores reais

Dois foram postos no caminho e medidos sobre o mesmo gabarito, reordenando os 15
melhores candidatos da fusão:

| | tamanho | acerto@1 | acerto@5 | grupo B | latência |
|---|---|---|---|---|---|
| fusão RRF (só CLT) | — | 54/72 | 67/72 | 17/20 | 63 ms |
| mmarco-mMiniLMv2 int8 | 119 MB | 50/72 | 64/72 | 13/20 | 141 ms |
| bge-reranker-base | 1,1 GB | 51/72 | 68/72 | 17/20 | 565 ms |

As três linhas são do corpus **só com a CLT** — as de reranqueador, ainda por
cima, sobre os vetores truncados em 128 tokens. Nenhuma foi refeita depois da
ingestão do TST, e refazê-las só faz sentido depois que o gabarito for reescrito
para o corpus atual. A comparação portanto
**subestima** a fusão de hoje, e o modelo grande, que já empatava dentro do ruído,
agora empata com 1,1 GB de desvantagem.

O modelo pequeno **piora**: nenhuma configuração testada superou a fusão em
acerto@5, e todas derrubaram o grupo B, que era justamente o alvo. A explicação é
de domínio — mMARCO é ranqueamento de passagem web, e dispositivo de CLT tem 176
caracteres na mediana, 15% deles abaixo de 80. "i) abandono de emprego;" não é
uma passagem.

O modelo grande ganha 3 consultas em acerto@5 e perde 2 em acerto@1. Com n=72, um
erro-padrão vale ~2,5 consultas: **o ganho está dentro do ruído**, e custa 1,1 GB
num pacote que já pesa 1,4 GB, mais 9× de latência por consulta.

### O que valeu mais que o reranqueador

Duas constantes. Nenhum modelo novo.

A primeira foi o orçamento de tokens da embedding, de 128 para 256 — está contada
acima, em "o vetor precisa ver o dispositivo inteiro": +2 consultas em acerto@5 na
fusão, por 5 minutos de reembutição.

A segunda é o `k` do RRF, que estava em 60, valor herdado de avaliação
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

Somadas, as duas constantes valem +7 em acerto@1 e +4 em acerto@5 sobre o ponto de
partida — enquanto o reranqueador de 1,1 GB entregava +3 em acerto@5 e **−2** em
acerto@1. É o argumento inteiro desta seção numa linha: antes de acrescentar um
modelo, medir o que os que já estão lá não estão conseguindo ver.

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

Obra que ainda não está no corpus — CF, leis esparsas, NRs — é citada pelo rótulo,
sem transcrição. Citar sem transcrever é útil; transcrever de memória, não. CLT,
súmulas e OJs do TST já entram transcritas.

## Estado

Triagem completa. Em andamento e a fazer:

| | | |
|---|---|---|
| **Corpus** | CLT e TST prontas | 4.716 dispositivos, 6.804 redações, com eixo de vigência. CLT do Planalto; súmulas e OJs (SBDI-I, SBDI-I Transitória, SBDI-II) do Livro consolidado do TST. Faltam CF, leis esparsas, NRs, súmulas do TRT-13. |
| **Via densa** | pronta | BGE-M3 em ONNX, CPU por padrão e GPU quando houver (5x na consulta, 17x na indexação). Fusão RRF acerta 62 de 72 no conjunto de avaliação, com recall@50 de 71/72. Reranking foi medido e reprovado - ver [Sobre reranking](#sobre-reranking). |
| **Inicial** | minuta pronta | Os quatro blocos — qualificação, fatos, fundamentação, pedidos — saem como peça em `/peca`, montada por template. Sem modelo de linguagem: o texto é função determinista das respostas. |
| **Recurso, embargos, contrarrazões** | a fazer | Partem de um **documento** (sentença, acórdão, recurso da outra parte), não da entrevista. Exigem uma camada de leitura que não existe. |
| **Processo parado** | a fazer | Consultor de próxima medida para processo que anda devagar há anos. |
| **Gabarito de avaliação** | a refazer | As 72 consultas têm resposta na CLT por construção, e o corpus agora tem súmulas. Metade das quedas de acerto@1 é o gabarito ficando estreito, metade é degradação real - e só juízo jurídico separa as duas. |
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
