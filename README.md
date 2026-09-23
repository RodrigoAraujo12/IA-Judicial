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
| `dados/corpus.db` | 97 MB — não está no git, vai por fora |
| `modelos/` | 2,2 GB — opcional; o `instalar.bat` baixa se preferir |
| `dados/casos.db` | **nunca** — é dado de cliente |
| `.venv/` | não; o `instalar.bat` cria o dela |

Sem o modelo o sistema funciona: a consulta por referência e a busca por palavra
ficam inteiras, e o acerto@5 cai de 62/72 para 58/72 no conjunto de avaliação. Sem o
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
python testar_jurisdicao.py # UF -> TRT, e sumula de outro tribunal fora do caso
python testar_trt13.py     # sumulas do TRT-13: datas do historico e janela de vigencia
python testar_leis.py      # CF, ADCT, Codigo Civil e leis esparsas: o parser fora da CLT
python analisar_rerank.py  # a folga que um reranqueador teria (exige vetores)
```

Para montar o corpus, uma vez só:

```
python -m app.corpus.indexar            # CLT, CF, ADCT, Codigo Civil e leis esparsas (~1 min)
python -m app.corpus.indexar tst trt13  # sumulas e OJs do TST, sumulas do TRT-13
python -m app.corpus.indexar vetores    # busca por sentido (~50 min em CPU, retomavel)
```

`dados/` não vai para o git. Cada máquina — e o servidor, quando houver — monta
o seu, ou recebe o `corpus.db` pronto.

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
  jurisdicao.py          do local da prestação ao TRT; que obras valem para o caso
  persistencia.py        SQLite — casos, a fonte da verdade
  main.py                FastAPI
  catalogo/
    loader.py            carga + validação cruzada dos YAML
    entrevista.yaml      roteiro de perguntas (81, em 10 secoes)
    armadilhas.yaml      verificações que não são pedidos (12)
    pedidos/*.yaml       o catálogo — 26 pedidos
  corpus/
    refs.py              referência do catálogo -> dispositivo endereçável
    banco.py             índice normativo em SQLite: vigência, FTS5, vetores
    planalto.py          ingestão do HTML do Planalto
    indexar.py           CLI de ingestão, com conferência contra o catálogo
    tst.py               súmulas e OJs do TST, do Livro consolidado (RTF)
    trt13.py             súmulas do TRT-13, página a página no site do NUGEP
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

### Além da CLT: CF, ADCT, Código Civil e leis esparsas

Entraram em 23/09/2026 as oito obras do Planalto que o catálogo cita: CF, ADCT,
Código Civil e as Leis 6.019/1974 (temporário e terceirização), 7.998/1990
(seguro-desemprego), 8.036/1990 (FGTS), 8.213/1991 (benefícios da Previdência) e
12.506/2011 (aviso prévio proporcional). Os 14 dispositivos que o catálogo cita
nelas estão endereçáveis e vigentes, e a minuta passou a transcrevê-los; as Leis
7.998 e 12.506 o catálogo cita por inteiro, e essas saem pelo nome.
**Só as obras citadas**: cada lei nova é densidade a mais competindo na busca
livre, e lei que nenhum pedido usa entra quando houver pedido que a use.

| obra | dispositivos | redações | revogadas sem data |
|---|---|---|---|
| CF | 2.645 | 3.089 | 118 |
| ADCT | 812 | 888 | 103 |
| Código Civil | 3.739 | 3.739 | 0 |
| Lei 8.213/1991 | 899 | 1.277 | 240 |
| Lei 8.036/1990 | 375 | 635 | 164 |
| Lei 7.998/1990 | 155 | 217 | 31 |
| Lei 6.019/1974 | 96 | 105 | 7 |
| Lei 12.506/2011 | 3 | 3 | 0 |

O piso de vigência de cada uma foi lido na própria página — o DOU do rodapé e o
artigo de vigência da lei —, não de memória. Onde divergem, manda o artigo: o
Código Civil saiu no DOU de 11/01/2002 e vigorou um ano depois (art. 2.044); a
Lei 6.019 teve sessenta dias de vacatio (art. 20).

O parser era o da CLT, e **cada lei trouxe uma forma que a CLT não tem**. Todas
quebravam em silêncio, e [`testar_leis.py`](testar_leis.py) tranca cada uma:

- **"Art. 1.228"**, com ponto de milhar. Lido como "1", o Código Civil parecia
  regredir mil artigos, e o guarda de norma estranha — o do art. 60 — descartava
  do art. 1.000 em diante: entravam 948 de 2.046 artigos.
- **"Art. 5o -A."** (Lei 6.019), com espaço antes do hífen. Aceitar o espaço sem
  critério lê o "Art. 11 -O direito de ação" da CLT como art. 11-O e apaga a
  prescrição. Com espaço antes, o sufixo só vale seguido de ponto.
- **O ADCT** fica no fim da página da CF, com numeração que recomeça no art. 1º.
  Na passada da CF o guarda de regressão o descarta; na dele, vira obra própria.

E duas das formas **também estavam na CLT**, errando desde a primeira ingestão:

- **Alínea de inciso ia para o caput.** O ADCT, art. 10, II, "b" (estabilidade
  da gestante) não existia no índice. Na CLT, 211 redações de alínea, em 12
  artigos, tinham endereço errado — entre eles o art. 452-E (intermitente) e o
  484-A (distrato). No art. 589 a alínea "a" do inciso I e a do inciso II eram a
  mesma URN, lidas como redação uma da outra. Junto veio o rótulo: inciso de
  parágrafo saía citado como "art. 430, III", sem o § 6º.
- **"§ 3º-A" era lido como § 3º.** O parágrafo com sufixo virava redação nova do
  parágrafo sem, e o encerrava. O **art. 832, § 3º** (contribuição previdenciária
  na sentença) aparecia revogado desde 2018, e o **art. 879, § 1º** (a liquidação
  não modifica a sentença) desde 1999 — os dois em vigor.

**Cinco medidas provisórias caducas** vieram com as Leis 8.213 e 8.036 — 739/2016,
891/2019, 1.303/2025, 1.336/2026 e 1.355/2026. Foram para a tabela `CADUCIDADE`
pelo mesmo caminho das quatro da CLT: a página da MP dá o DOU, o Ato Declaratório
do Congresso dá o dia do encerramento, e as duas capturas ficam em
`dados/fontes/`. No art. 62 da Lei 8.213 o texto anterior volta em 05/11/2016, no
dia seguinte ao fim da MP 739.

Na consulta livre, a obra pode vir antes ou depois do artigo — "art. 7º, XXIX da
CF", "CF, art. 7º", "art. 118 da Lei 8.213/91", "art. 1.228 do CC", "art. 10,
II, b do ADCT". Antes, toda referência "art. N" era da CLT por falta de
alternativa; com a CF no índice, "art. 7º da CF" cairia no art. 7º da CLT.

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

**Quando entraram CF, ADCT, Código Civil e as leis esparsas** (23/09/2026), mais
10 mil redações passaram a competir. Medido consulta a consulta contra o banco de
antes, nas obras nacionais:

| | acerto@1 | acerto@5 | MRR |
|---|---|---|---|
| CLT + TST | 47/72 | 62/72 | 0,751 |
| + CF, ADCT, CC e 5 leis | 43/72 | 62/72 | 0,716 |

O acerto@5 não se moveu; o primeiro lugar, sim. Das 15 consultas que mudaram de
posição, só **4 têm uma obra nova no topo**, e de novo elas não se somam: "vedada
a dispensa do empregado sindicalizado" devolve o art. 8º, VIII, da CF, que é a
norma constitucional do tema (gabarito estreito); "juiz pode executar de ofício"
devolve o art. 249 do Código Civil, e "assédio... ofensa à honra" o art. 21 da
Lei 8.213 — ruído. As outras 11 perderam uma ou duas posições para o que já
estava lá, TST sobretudo: competição de densidade, como na entrada das súmulas.
Recall@50 foi a 70/72.

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

**Quando reabrir a discussão.** Este parágrafo dizia "quando entrarem CF,
súmulas e OJs, o lote passa a misturar obras e a folga aumenta". Entraram, e a
folga foi medida em 23/09/2026 com [`analisar_rerank.py`](analisar_rerank.py):
**4 consultas** num lote de 20 candidatos (+5,6 pontos de acerto@5 para um
reranqueador perfeito), 8 num lote de 50. Cresceu, mas continua pequena — e
ainda é medida por um gabarito que só tem resposta na CLT. A ordem certa é
reescrever o gabarito primeiro e medir depois. O caminho a medir primeiro é
`bge-reranker-v2-m3`, da mesma família do modelo de embeddings já usado; o
obstáculo é tamanho: 2,3 GB, sem ONNX oficial publicado.

Uma ressalva sobre o gabarito: as 72 consultas têm resposta **na CLT** por
construção. Recall@50 alto quer dizer "quando a resposta está na CLT, a busca
acha" — não "o sistema responde tudo". Pergunta sobre FGTS, terceirização ou
estabilidade da gestante agora tem onde cair, mas o gabarito não tem como dizer
se caiu no lugar certo.

## Competência: o TRT do caso

O direito do trabalho é federal, e por isso quase tudo que o corpus tem vale igual
em João Pessoa e em Campinas. O que muda de um estado para outro é a
jurisprudência do tribunal regional — e ela só pode entrar no índice se o sistema
souber, caso a caso, **qual** tribunal julga. É isso que
[`app/jurisdicao.py`](app/jurisdicao.py) responde.

**O tribunal é derivado, nunca escolhido.** A entrevista pergunta em que UF o
serviço era prestado, e o TRT sai daí, porque é isso que o art. 651 da CLT manda
olhar — não o foro da contratação nem o da sede da empresa. Deixar escolher o
tribunal à mão abriria a porta exatamente para o erro que o artigo existe para
evitar. O que a advogada vê é o resultado, no painel, no relatório e no quadro de
trabalho da minuta, para conferir.

**São Paulo é a única exceção.** Vinte e cinco unidades têm um tribunal só, ou
dividem um com a vizinha (PA e AP, DF e TO, AM e RR, RO e AC). São Paulo tem
dois: capital, Grande São Paulo e Baixada Santista são a 2ª Região; o interior é
a 15ª. Só ali aparece uma segunda pergunta, e só ali ela é feita.

**Sem UF não há tribunal.** É o terceiro estado do motor, de novo: o sistema não
assume o tribunal da advogada por padrão, porque ela pode atender alguém que
trabalhou noutro estado. A minuta diz que a competência não foi derivada e por quê.

**Obra regional tem sufixo, e o sufixo é o filtro.** A convenção é `-trtNN` no
nome da obra: `sumula-trt13`, `oj-trt13`. Obra sem sufixo é nacional e vale para
todo caso. As vias lexical e densa recebem o conjunto de obras que o caso pode
consultar — nacionais mais as do seu TRT — e é uma cláusula só, em
[`banco.filtro_obras`](app/corpus/banco.py), que serve às duas. A via de
referência fica **fora** do filtro de propósito: quem digita "Súmula 12 do TRT-6"
num caso da Paraíba está pedindo aquele texto, e filtro que esconde resposta
exata é censura, não competência.

Isso não é só regra jurídica; é o que preserva o ranking. Quando o TST entrou, as
duas vias caíram 8 consultas em acerto@1 por competição de densidade — ver
[Sobre reranking](#sobre-reranking). Súmulas de 24 tribunais no mesmo lote fariam
o mesmo, multiplicado. Com o filtro, um caso da Paraíba disputa contra a CLT, o
TST e a 13ª Região, e só.

**O controle.** Enquanto o corpus só tem obras nacionais, filtrar por "só
nacionais" tem de devolver exatamente o que a busca sem filtro devolve, consulta a
consulta, nas duas vias. `testar_vias.py` confere isso sobre as 72 consultas do
gabarito e imprime o resultado ao lado do placar: 72/72 idênticas. Se um dia esse
número se mover num corpus sem obra regional, o filtro vazou.

Na consulta livre em `/corpus` não há caso, então ali o tribunal é escolhido num
seletor — com "só normas nacionais" como padrão, e listando apenas os TRTs que já
têm obra no índice.

### A primeira obra regional: as súmulas do TRT-13

Entram 45 verbetes, a faixa inteira de 1 a 45, em
[`app/corpus/trt13.py`](app/corpus/trt13.py). Hoje 35 valem: 28 nunca alteradas,
5 alteradas e 2 revisadas. As 10 canceladas ficam no índice com **janela**, não
como revogadas — a Súmula 7 caiu em 03.03.2021, e um caso de 2016 continua
encontrando-a, pela mesma razão que o art. 71 §4º tem duas redações.

A fonte é diferente da do TST, e pior. Não há arquivo consolidado: o NUGEP publica
um índice com um link por súmula e o texto de cada uma numa página própria. São
46 requisições, todas guardadas em `dados/fontes/trt13/`, e o registro de fonte
leva o sha256 da concatenação. O servidor recusa cliente que não pareça
navegador: `User-Agent: Mozilla/5.0` seco recebe 403; a assinatura completa de um
Chrome, 200.

O HTML foi colado do Word e chega picotado em spans que partem palavra e data ao
meio — `1<span>9.12.2017`, `0<span>1</span>.201<span>8`. Por isso tag inline vira
**nada**, e não espaço, e só tag de bloco vira quebra de linha. Sem isso a data
vira "1 9.12.2017" e a súmula nasce no piso.

A vigência sai do bloco "Histórico", e cada evento tem um sentido:

- **"Redação original: ... DEJT em 28, 29 e 30.06.2010"** abre a janela. Vale a
  **última** data da linha: a publicação se completa no último dia, e a data do
  acórdão, que vem antes, não é a da súmula.
- **"Redação alterada"** e **"Inclusão do item II"** substituem o início. O texto
  da página é o novo; a fonte não guarda o antigo. Uma redação por verbete, como
  no TST.
- **"Súmula cancelada: ... DEJT em 28.04.2017"** fecha a janela na véspera. Só
  cai em `revogado` o cancelamento sem data legível, e não há nenhum.
- **"Revisão: IAC ... Tema 10"** não move o início. A revisão fixa tese sobre a
  matéria, mas o verbete continua com o texto original — mover a vigência para
  2026 esconderia a súmula de todo caso anterior, e o texto que ele veria é o
  mesmo. A tese fica fora do `texto`: é acórdão, não verbete.
- **"..., e em 07, 08 e 11.03.2019, por mera formalidade"** é republicação e é
  descartada antes de ler a data. Sem isso três súmulas de 2016 nasceriam em 2019.

O efeito no gabarito é medido, não presumido. O placar continua sendo tirado
sobre as obras nacionais — o gabarito tem resposta na CLT e foi calibrado antes de
existir obra regional —, e `testar_vias.py` imprime ao lado em quantas das 72
consultas o top-5 muda quando o caso é da 13ª Região:

| | só CLT e TST | com CF, CC e leis |
|---|---|---|
| top-5 muda | 7 de 72 consultas | 3 de 72 |
| verbete do TRT-13 em #1 | 0 | 1 |
| obra fora do permitido | 0 de 72, em todas as vias | 0 de 72 |

Com CLT e TST, sete consultas ganhavam uma súmula regional entre as cinco
primeiras sem que nenhuma tomasse o topo: a súmula entra como complemento, não
como competidora — o oposto do que aconteceu quando o TST entrou sem filtro.
Com as leis nacionais no índice, a súmula regional disputa lugar com mais gente
e aparece em menos consultas. A que tomou o topo é
"grupo econômico responsabilidade solidária", onde a Súmula 9 do TRT-13 (que
define grupo econômico) passa à frente da OJ 411 do TST, que diz o oposto do
perguntado. Aqui o topo melhorou. É esse número que reabre a discussão de
reranking, se um dia ele crescer.

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

Obra que ainda não está no corpus — NRs, decisões do STF — é citada pelo rótulo,
sem transcrição. Citar sem transcrever é útil; transcrever de memória, não. CLT,
CF, ADCT, Código Civil, as leis esparsas que o catálogo cita e as súmulas e OJs
do TST já entram transcritas. Lei citada por inteiro, sem artigo ("Lei
12.506/2011"), também sai pelo rótulo: não se transcreve uma lei na peça.

## Estado

Triagem completa. Em andamento e a fazer:

| | | |
|---|---|---|
| **Corpus** | tudo o que o catálogo cita, menos NR e STF | 13.591 dispositivos, 16.799 redações, com eixo de vigência, em 14 obras. Do Planalto: CLT, CF, ADCT, Código Civil e Leis 6.019, 7.998, 8.036, 8.213 e 12.506 — ver [Além da CLT](#além-da-clt-cf-adct-código-civil-e-leis-esparsas). Súmulas e OJs (SBDI-I, SBDI-I Transitória, SBDI-II) do Livro consolidado do TST; súmulas do TRT-13 do site do NUGEP. Faltam NRs e decisões do STF. |
| **Regional** | TRT-13 pronto | O caso deriva o TRT do local da prestação e a busca só vê as obras dele — ver [Competência](#competência-o-trt-do-caso). Súmulas do TRT-13 ingeridas: 45 verbetes, 35 vigentes, 10 com janela de cancelamento. Outros tribunais entram um a um, quando houver caso deles. |
| **Via densa** | pronta | BGE-M3 em ONNX, CPU por padrão e GPU quando houver (5x na consulta, 17x na indexação). Fusão RRF acerta 62 de 72 no conjunto de avaliação, com recall@50 de 70/72. Reranking foi medido e reprovado - ver [Sobre reranking](#sobre-reranking). |
| **Inicial** | minuta pronta | Os quatro blocos — qualificação, fatos, fundamentação, pedidos — saem como peça em `/peca`, montada por template. Sem modelo de linguagem: o texto é função determinista das respostas. |
| **Recurso, embargos, contrarrazões** | a fazer | Partem de um **documento** (sentença, acórdão, recurso da outra parte), não da entrevista. Exigem uma camada de leitura que não existe. |
| **Processo parado** | a fazer | Consultor de próxima medida para processo que anda devagar há anos. |
| **Gabarito de avaliação** | a refazer | As 72 consultas têm resposta na CLT por construção, e o corpus agora tem súmulas. Metade das quedas de acerto@1 é o gabarito ficando estreito, metade é degradação real - e só juízo jurídico separa as duas. |
| **Jurisprudência** | a decidir | Uso principal é **citar na peça**, o que torna o validador de citações obrigatório. Uso secundário é aferir viabilidade. Muda a escala e exige rastrear superação de tese, não vigência. |
| **Serviço para escritórios** | a fazer | Login, um escritório por conta, corpus compartilhado e somente leitura, casos de cada um. Reabre a premissa local do `ENTREGA.md` — ver [Rumo](#rumo-um-serviço-para-escritórios). |

## Rumo: um serviço para escritórios

Tudo acima descreve um sistema que roda na máquina de uma advogada. A direção,
registrada em 17/09/2026, é outra: **um serviço para escritórios trabalhistas de
todo o país.** Cada escritório entra com login e vê só os seus casos; o corpus é
um só, compartilhado e somente leitura. Nada disso está feito — esta seção existe
para que a intenção sobreviva à conversa em que foi dita, e para registrar o que
ela reabre antes que alguém comece pelo lugar errado.

**A divisão certa já existe, por outro motivo.** `corpus.db` e `casos.db` são
arquivos separados desde o início, e a separação foi justificada em
[`banco.py`](app/corpus/banco.py) por ciclos de vida, backups e riscos de LGPD
diferentes. É exatamente a linha que o serviço precisa: o corpus vira o que é
comum a todos e ninguém escreve; os casos viram o que é de cada um. Quem for
desenhar o serviço não parte de um monólito a fatiar — parte de dois bancos que
já não se misturam.

**O que não existe.** Não há login, sessão nem cookie em
[`main.py`](app/main.py). A tabela `casos` tem `id`, `nome`, datas e `respostas`
— nenhuma coluna diz de quem é o caso, porque até hoje a resposta era "de quem
está sentado na máquina". Os dois caminhos de banco são constantes de módulo
([`persistencia.py`](app/persistencia.py), [`banco.py`](app/corpus/banco.py)):
um processo, um arquivo. E o servidor escuta em `127.0.0.1` de propósito.

**O que a mudança reabre, e que não é código.**

- *A premissa do `ENTREGA.md`.* O documento inteiro se apoia em "o dado nunca sai
  da máquina" como a forma mais barata de cumprir o art. 11 da LGPD. No serviço o
  dado sai. O escritório passa a ser controlador e o serviço, operador (art. 5º,
  VI e VII; art. 39), o que pede contrato entre os dois, hospedagem que respeite o
  art. 33 e um plano para o dado de saúde que a entrevista coleta. Isso não é
  detalhe de implantação; é o que decide se o serviço pode existir.
- *"Outros tribunais entram um a um, quando houver caso deles."* Essa regra da
  tabela acima é regra de produto local. Com escritórios do país inteiro, os 24
  TRTs deixam de ser sob demanda e viram pré-requisito — e o TRT-13 custou um
  módulo de 351 linhas contra o site do NUGEP daquele tribunal; os outros 23 têm
  os seus. É a maior conta de conteúdo do serviço, e a que menos depende de
  decisão técnica.
- *O modelo.* O BGE-M3 foi tratado como opcional porque a máquina da advogada
  podia não comportar 2,2 GB. Num servidor ele sempre cabe; o que passa a
  importar é quantas consultas ao mesmo tempo uma sessão ONNX aguenta. A
  degradação para lexical continua como rede de segurança, não como modo normal.

**O que fica em aberto, de propósito.** Um `casos.db` por escritório — que
preserva o isolamento por arquivo e o modelo de "fonte da verdade" de hoje — ou um
banco só com coluna de escritório. Onde hospedar. Se a instalação local continua
como segundo produto (as três formas do `ENTREGA.md` seguem válidas para quem
preferir). Nenhuma dessas tem resposta óbvia, e este README registra a intenção,
não o projeto.

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
- **51 dispositivos têm janelas de vigência que se sobrepõem**, 24 deles em datas
  a partir de 2010 — 30 na CLT, 11 na Lei 8.213, o resto espalhado. Eram 194 só
  na CLT: quando o Planalto repete um texto sem marcador legível, a redação caía
  no piso da obra (1943, na CLT) e passava a cobrir período que não lhe pertence.
  Desde 23/09/2026 ela começa, no mínimo, junto da redação anterior — a ordem do
  documento é cronológica. O que sobra são casos em que a fonte traz datas
  contraditórias entre si. Nenhum é citado pelo catálogo, mas a busca livre pode
  devolver duas redações para a mesma data.
- 1.914 redações ficaram marcadas como revogadas sem data legível na fonte (1.251
  na CLT). Elas nunca são servidas como vigentes — na dúvida o índice cala, em
  vez de afirmar. Isso inclui texto histórico que deveria ter janela: as alíneas
  do art. 702 da CLT valeram de 1943 a 1946, mas a sucessora foi reescrita em
  outra estrutura (alínea de inciso), e sem sucessora no mesmo endereço não há
  de onde tirar a data de fim.
- **Emenda constitucional entra no ano, não no dia.** O marcador da CF escreve
  "(Redação dada pela Emenda Constitucional nº 72, de 2013)", sem dia, e a
  redação nova passa a valer em 1º de janeiro — três meses antes da EC 72. É a
  mesma aproximação das leis que alteram a CLT; só a Reforma e as MPs da tabela
  `CADUCIDADE` têm data exata.
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
