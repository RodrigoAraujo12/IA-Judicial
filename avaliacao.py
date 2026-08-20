"""Gabarito de recuperacao: consultas e o dispositivo que deveria responder.

Separado de `testar_vias.py` porque duas coisas diferentes leem daqui: o teste,
que da um placar rapido, e `analisar_rerank.py`, que precisa das mesmas consultas
com outra profundidade. Gabarito duplicado e gabarito que diverge.

Dois grupos, e a distincao importa mais que o total:

**Grupo A - vocabulario da lei.** A advogada digita o termo tecnico e ele esta no
texto do dispositivo. E a distribuicao real de uso: quem opera o sistema conhece a
nomenclatura, e a traducao do relato do cliente para categoria juridica ja
aconteceu antes, na entrevista.

**Grupo B - termo forense ausente da lei.** "Rescisao indireta" nao aparece no
art. 483; a CLT escreve "considerar rescindido o contrato". "Hipersuficiente" nao
esta no art. 444. "Pejotizacao" nao esta no art. 442-B. Aqui o BM25 fica sem
ancora, e quem sustenta o acerto e a via densa. E o grupo que diz se falta rerank.

O gabarito foi conferido dispositivo a dispositivo contra o texto ingerido: toda
URN daqui existe e esta vigente hoje no corpus.

Uma consulta ficou de fora de proposito: "insalubridade prorrogacao de jornada
licenca previa", que deveria cair no art. 60. O art. 60 nao esta enderecavel no
corpus - a fonte do Planalto transcreve, dentro do titulo da Justica do Trabalho,
um "Art. 60" do Decreto-Lei 9.797/1946 sobre Tribunais Regionais, e o parser o le
como redacao nova do art. 60 da CLT. Isso e falha de ingestao, nao de ranqueamento;
mede-la aqui misturaria os dois diagnosticos.
"""

# (consulta, urn que deveria aparecer, grupo)
CASOS: list[tuple[str, str, str]] = [
    # -- Grupo A: o termo da consulta esta no texto da lei -------------------
    ("intervalo intrajornada natureza indenizatoria",        "clt/art-71/par-4",   "A"),
    ("dispensa imotivada aviso previo",                      "clt/art-487",        "A"),
    ("atividades perigosas adicional de trinta por cento",   "clt/art-193",        "A"),
    ("grupo economico responsabilidade solidaria",           "clt/art-2/par-2",    "A"),
    ("honorarios de sucumbencia advogado",                   "clt/art-791-A",      "A"),
    ("acrescimo de horas extras limite diario",              "clt/art-59",         "A"),
    ("justa causa ato de improbidade",                       "clt/art-482",        "A"),
    ("trabalho noturno hora reduzida",                       "clt/art-73",         "A"),
    ("equiparacao salarial identidade de funcao",            "clt/art-461",        "A"),
    ("ausencia do reclamante arquivamento custas",           "clt/art-844/par-2",  "A"),
    ("peticao inicial pedido certo determinado",             "clt/art-840/par-1",  "A"),
    ("prescricao dos creditos trabalhistas",                 "clt/art-11",         "A"),
    ("dano extrapatrimonial esfera moral",                   "clt/art-223-B",      "A"),
    ("fornecimento gratuito de equipamento de protecao",     "clt/art-166",        "A"),
    ("multa por atraso no pagamento das verbas rescisorias", "clt/art-477/par-8",  "A"),
    ("sucessao empresarial responsabilidade do sucessor",    "clt/art-448-A",      "A"),
    ("socio retirante responde subsidiariamente",            "clt/art-10-A",       "A"),
    ("jornada de doze horas por trinta e seis de descanso",  "clt/art-59-A",       "A"),
    ("regime de tempo parcial duracao semanal",              "clt/art-58-A",       "A"),
    ("tempo despendido da residencia ao trabalho conducao",  "clt/art-58/par-2",   "A"),
    ("atividade externa incompativel com fixacao de horario", "clt/art-62/inc-I",  "A"),
    ("periodo minimo de onze horas entre duas jornadas",     "clt/art-66",         "A"),
    ("registro de ponto estabelecimento com mais de vinte",  "clt/art-74/par-2",   "A"),
    ("periodo aquisitivo de ferias faltas injustificadas",   "clt/art-130",        "A"),
    ("ferias concedidas apos o prazo pagamento em dobro",    "clt/art-137",        "A"),
    ("conversao de um terco das ferias em abono pecuniario", "clt/art-143",        "A"),
    ("adicional de insalubridade grau maximo medio minimo",  "clt/art-192",        "A"),
    ("pericia para caracterizar insalubridade periculosidade", "clt/art-195",      "A"),
    ("duracao normal do trabalho dos bancarios",             "clt/art-224",        "A"),
    ("licenca maternidade de cento e vinte dias",            "clt/art-392",        "A"),
    ("contrato de aprendizagem inscricao em programa",       "clt/art-428",        "A"),
    ("contrato por prazo determinado nao podera exceder",    "clt/art-445",        "A"),
    ("integram o salario gratificacoes legais e comissoes",  "clt/art-457/par-1",  "A"),
    ("ajuda de custo e diarias nao integram a remuneracao",  "clt/art-457/par-2",  "A"),
    ("pagamento do salario ate o quinto dia util",           "clt/art-459",        "A"),
    ("vedado efetuar descontos nos salarios do empregado",   "clt/art-462",        "A"),
    ("verbas rescisorias incontroversas acrescimo de cinquenta", "clt/art-467",    "A"),
    ("alteracao das condicoes do contrato por mutuo consentimento", "clt/art-468", "A"),
    ("transferencia adicional de vinte e cinco por cento",   "clt/art-469/par-3",  "A"),
    ("faltas justificadas sem prejuizo do salario",          "clt/art-473",        "A"),
    ("extincao do contrato por acordo entre as partes",      "clt/art-484-A",      "A"),
    ("reducao de duas horas diarias no aviso previo",        "clt/art-488",        "A"),
    ("vedada a dispensa do empregado sindicalizado",         "clt/art-543/par-3",  "A"),
    ("convencao coletiva prevalece sobre a lei",             "clt/art-611-A",      "A"),
    ("objeto ilicito de convencao coletiva",                 "clt/art-611-B",      "A"),
    ("competencia pelo local da prestacao de servicos",      "clt/art-651",        "A"),
    ("prazos processuais contados em dias uteis",            "clt/art-775",        "A"),
    ("justica gratuita insuficiencia de recursos",           "clt/art-790/par-3",  "A"),
    ("honorarios periciais a cargo da parte sucumbente",     "clt/art-790-B",      "A"),
    ("onus da prova incumbe ao reclamante e ao reclamado",   "clt/art-818",        "A"),
    ("atualizacao dos creditos decorrentes de condenacao",   "clt/art-879/par-7",  "A"),
    ("deposito recursal para interposicao de recurso",       "clt/art-899",        "A"),

    # -- Grupo B: o termo forense NAO esta no texto da lei -------------------
    ("rescisao indireta do contrato de trabalho",            "clt/art-483",        "B"),
    ("sobreaviso escala de plantao",                         "clt/art-244/par-2",  "B"),
    ("empregado hipersuficiente pode negociar direto",       "clt/art-444/par-unico", "B"),
    ("pejotizacao contratacao de autonomo com exclusividade", "clt/art-442-B",     "B"),
    ("home office trabalho remoto",                          "clt/art-75-B",       "B"),
    ("demissao em massa sem negociacao com o sindicato",     "clt/art-477-A",      "B"),
    ("acumulo de funcao servico compativel com a condicao pessoal", "clt/art-456/par-unico", "B"),
    ("perda da gratificacao apos dez anos de funcao",        "clt/art-468/par-2",  "B"),
    ("abandono de emprego apos trinta dias de falta",        "clt/art-482/al-i",   "B"),
    ("desidia faltas repetidas e atrasos constantes",        "clt/art-482/al-e",   "B"),
    ("acordo extrajudicial homologado em juizo",             "clt/art-855-B",      "B"),
    ("litigancia de ma fe alterar a verdade dos fatos",      "clt/art-793-B",      "B"),
    ("transcendencia do recurso de revista",                 "clt/art-896-A",      "B"),
    ("embargos a execucao com o juizo garantido",            "clt/art-884",        "B"),
    ("juiz pode executar de oficio a sentenca",              "clt/art-878",        "B"),
    ("revelia e confissao pela ausencia da reclamada",       "clt/art-844",        "B"),
    ("trabalho intermitente com convocacao por periodos",    "clt/art-443/par-3",  "B"),
    ("contratacao por empresa de fachada para fraudar direitos", "clt/art-9",      "B"),
    ("banco de horas pactuado por acordo individual",        "clt/art-59/par-5",   "B"),
    ("assedio no ambiente de trabalho ofensa a honra",       "clt/art-223-C",      "B"),
]


def posicao(achados, alvo: str) -> int | None:
    """Acerta quem devolve o dispositivo OU um subordinado dele.

    Exigir a URN exata mede a coisa errada. Para "justa causa ato de improbidade"
    a melhor resposta e a alinea 'a' do art. 482 - literalmente "ato de
    improbidade" -, nao o caput; para "hora noturna reduzida" e o par. 1o do art.
    73, nao o artigo. Cobrar o caput reprovava o sistema justamente quando ele
    respondia com mais precisao do que se pediu.
    """
    for i, a in enumerate(achados):
        if a.urn == alvo or a.urn.startswith(alvo + "/"):
            return i + 1
    return None
