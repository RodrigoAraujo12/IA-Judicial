# Entregar o sistema para quem vai usar

Este documento existe porque a decisão de como empacotar o sistema foi tomada
numa conversa que não sobrevive à troca de máquina. O que está aqui é o
raciocínio, não só o passo a passo — a intenção é que daqui a três meses ainda dê
para entender **por que** foi assim e não de outro jeito.

## O ponto de partida

O sistema roda em `127.0.0.1` e guarda tudo em SQLite local. Não há servidor,
não há nuvem, não há conta de usuário. Isso não é limitação: a entrevista coleta
nome, CPF, salário e dado de saúde — dado pessoal sensível pela LGPD, art. 11 —
e a forma mais barata de proteger isso é ele nunca sair da máquina.

**Depois de instalado, o sistema não precisa de internet.** Isto foi verificado,
não presumido: fora de `app/corpus/planalto.py` (ingestão da CLT) e
`app/corpus/baixar_modelo.py` (download do BGE-M3), não existe uma única chamada
de rede no código, e os templates não carregam nada de CDN. A busca por
referência, a busca por palavra, a busca por sentido, a triagem e a minuta rodam
todas offline.

## Três formas de entregar, da mais simples à mais completa

### 1. Git + o corpus por fora

Ela clona do GitHub e recebe `dados/corpus.db` (33 MB) separado — pen drive,
WeTransfer, o que for. O corpus está no `.gitignore` de propósito: é índice
reconstruível, não código, e 33 MB por commit poluiria o histórico para sempre.

Serve quando ela é técnica ou quando você vai dar suporte de perto. Exige Python
instalado.

### 2. Pasta + os dois `.bat`

`instalar.bat` (uma vez) e `abrir.bat` (uso diário). Já existem e foram testados
numa cópia limpa. Exige Python instalado na máquina dela, e conexão para baixar
as dependências (~170 MB) e, se quiser, o modelo (2,2 GB).

**Armadilha conhecida:** a pasta precisa ficar num caminho curto — `C:\triagem`
ou a Área de Trabalho. O Windows corta caminhos acima de 260 caracteres e a
instalação morre no meio do `pip`, com um erro que não diz isso. Aconteceu no
teste.

### 3. Pacote offline com Python embutido — o alvo

Uma pasta que contém **tudo**, inclusive o próprio Python. Ela não instala nada,
não precisa de administrador, não mexe em PATH e não precisa de internet nem uma
vez. Copia a pasta, clica no `abrir.bat`, usa.

| | |
|---|---|
| Python embutido | ~11 MB |
| Dependências já instaladas | ~169 MB |
| Código + `corpus.db` | ~34 MB |
| Modelo BGE-M3 | ~2,2 GB |
| **Total** | **~2,4 GB** |

## Por que Python embutido e não um `.exe`

A alternativa óbvia seria empacotar com PyInstaller e entregar um executável. Foi
descartada por quatro motivos, e vale registrar para não se reabrir a discussão
sem os fatos:

- **Antivírus.** Executável gerado por PyInstaller é padrão conhecido de falso
  positivo. Num escritório de advocacia, um alerta de vírus mata a adoção.
- **SmartScreen.** Executável não assinado dispara "aplicativo não reconhecido".
  Assinatura de código custa dinheiro e renovação anual.
- **Manutenção.** Corrigir uma vírgula obrigaria a reempacotar e reenviar
  centenas de megabytes. Com Python embutido, o conserto é trocar **um arquivo**
  e mandar por WhatsApp.
- **Não resolve o que pesa.** Os 2,2 GB do modelo continuariam do lado de fora.

O Python embutido é uma distribuição oficial da própria python.org: uma pasta com
`python.exe` que não escreve no registro, não pede administrador e não conflita
com nenhum Python já instalado.

**Ressalva:** o `onnxruntime` depende do runtime do Visual C++, que quase toda
máquina Windows tem, mas não é garantido numa instalação muito limpa. Se faltar,
o sintoma é a busca por sentido falhar — e só ela. Entrevista, minuta, busca por
referência e busca por palavra continuam funcionando, porque a busca degrada para
lexical em vez de quebrar (`app/corpus/busca.py`).

## Como o pacote offline foi montado

Feito e testado em 20/08/2026. A receita, para poder refazer:

1. Baixar `python-3.13.11-embed-amd64.zip` de python.org (10,4 MB) e extrair em
   `triagem/python/`. **A versão precisa bater com a do `.venv`** — os pacotes
   vêm compilados para uma versão específica (`cp313`), e trocar a minor version
   quebra tudo.
2. Reescrever `python/python313._pth` para incluir `Lib\site-packages` e
   descomentar `import site`. Sem isso o Python embutido **ignora** o que o pip
   instalar, e nenhum pacote é encontrado — é o passo que todo mundo esquece.
3. `python\python.exe get-pip.py`, depois
   `python\python.exe -m pip install -r requirements.txt`.
4. Copiar o código, `dados/corpus.db` e `modelos/bge-m3`.
5. `Triagem trabalhista.bat` chama `python\python.exe -m uvicorn app.main:app`.

**Detalhe que custou um teste:** o `.bat` usa `%SystemRoot%\System32\timeout.exe`
com caminho completo, e não só `timeout`. Se houver outro `timeout` no PATH — o
do Git Bash, por exemplo — o comando curto pega o errado e a espera antes de
abrir o navegador não acontece.

### O que foi verificado, e não presumido

- Sobe com o Python embutido, sem tocar no Python do sistema — confirmado pela
  linha de comando do processo: `python\python.exe -m uvicorn`.
- `onnxruntime` importa e roda a partir do Python embutido. Era o risco maior.
- As três telas respondem HTTP 200.
- Busca por sentido funciona: "dispensa imotivada aviso prévio" devolve os
  arts. 490, 487 §1º e 489 — modelo e vetores operando dentro do pacote.
- Consulta por referência com data antiga devolve a redação certa: `art. 71 §4º`
  em 10/05/2016 traz o texto pré-Reforma.
- A minuta renderiza com os pedidos novos.
- **Nenhuma conexão externa.** `netstat` no processo mostra apenas `127.0.0.1`.

## O que nunca vai no pacote

- **`dados/casos.db`** — entrevistas reais, com dado pessoal sensível. Ela começa
  com o banco vazio, criado no primeiro salvamento. Mandar o seu seria vazamento.
- **`.venv/`** — ambiente da sua máquina, com caminhos absolutos seus.

## Estado do projeto nesta data

26 pedidos, 12 verificações, 79 perguntas em 10 seções. Corpus com 3.660
dispositivos e 5.748 redações da CLT, todas vetorizadas. Nove arquivos de teste,
todos passando.

**O `corpus.db` mudou** depois do conserto do art. 60 (abaixo). Quem já recebeu o
pacote está com a versão anterior: para atualizar, basta trocar esse arquivo — não
é preciso reenviar o modelo, que é a parte pesada.

O que foi feito por último, e que vale saber porque muda o comportamento:

- **Caducidade de medida provisória** entrou no eixo de vigência. Antes, texto de
  MP caduca aparecia como lei atual — o art. 223-C respondia para 2016, quando o
  artigo nem existia. Junto vieram dois consertos no parser: o regex que não
  aceitava letra acentuada (e por isso nunca reconhecia "Medida Provisória") e a
  detecção de tachado, que marcava lei vigente como revogada. 492 dispositivos
  voltaram ao índice.
- **Minuta da inicial** em `/peca`, montada por template, sem modelo de
  linguagem. Pedido que atravessa a Reforma sai cindido, cada parte citando a
  redação do seu período.
- **Quatro blocos novos no catálogo**, vindos da comparação com um roteiro de
  entrevista escrito à mão: responsabilidade patrimonial (grupo econômico,
  sucessão, tomador), requisitos da justa causa, parcelas pagas à margem do
  contracheque e férias em dobro.
- **Art. 60 voltou ao índice.** A página do Planalto transcreve, no meio do título
  da Justiça do Trabalho, um "Art. 60" do Decreto-Lei 9.797/1946 sobre Tribunais
  Regionais. O parser o lia como redação nova do art. 60 da CLT — que trata de
  prorrogação de jornada em atividade insalubre — e marcava o artigo verdadeiro
  como revogado desde 1946. Consulta a ele não devolvia nada. O conserto é um
  guarda contra regressão da numeração, em `planalto.py`.
- **Conjunto de avaliação foi de 15 para 72 consultas**, e a decisão sobre
  reranking passou a ter base. Resumo: não faz falta. O que fazia falta era o `k`
  da fusão RRF, que estava em 60 e foi para 5. Detalhe em `README.md`, seção
  "Sobre reranking".

## O que ficou pendente

- **Mapa probatório** — para cada fato controvertido, quem presenciou. Hoje o
  sistema lista provas por pedido, mas nunca pergunta quem viu o quê.
- **Perguntas de controle sobre fatos adversos** — *"se eu conversar amanhã com o
  advogado da empresa, o que ele vai dizer que você fez de errado?"*. Custa pouco
  e não existe equivalente no sistema.
- **Fecho da peça** — advogado, OAB, local e data. Não há cadastro de advogado,
  então a minuta termina nos requerimentos.
- **A regra de "o que ainda falta"** está duplicada: no template do relatório e
  em `redator.lacunas()`. Deveria convergir para um lugar só.
- **194 dispositivos com janelas de vigência sobrepostas**, 38 em datas recentes.
  Causa: texto que o Planalto repete sem marcador legível cai no piso de 1943.
  Nenhum é citado pelo catálogo, então a Via 0 está limpa; afeta só busca livre.
- **Triagem de viabilidade econômica** (aceitar ou não a causa) foi
  deliberadamente deixada de fora: é decisão de negócio, não análise jurídica, e
  misturar as duas estraga as duas.
