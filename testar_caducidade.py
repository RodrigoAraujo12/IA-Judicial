"""Caducidade de medida provisoria, e o tachado que a fonte escreve de dois jeitos.

    python testar_caducidade.py

O caso de teste e o art. 223-C, que a Reforma criou, a MP 808/2017 reescreveu e
que voltou ao texto da Reforma quando a MP caducou. Sao tres redacoes em cinco
meses, e a terceira nao e nova: e a primeira que RETORNA.

Isso quebra a sucessao por ordem de documento, que assume que cada redacao
comeca onde a seguinte termina. O bloco que retorna carrega o marcador da lei
que o criou - 11/11/2017 - e ler essa data como inicio poria a Reforma valendo
durante o periodo em que a MP estava em vigor.

O teste tambem tranca a deteccao de tachado. Antes ela olhava so a tag <strike>
e marcava o bloco inteiro como superado se ela aparecesse em qualquer lugar. O
HTML do Planalto e malformado o bastante para que isso apague lei vigente.
"""

from datetime import date
from pathlib import Path

from app.corpus import planalto
from app.corpus.planalto import Trecho

falhas = []


def conferir(rotulo: str, obtido, esperado) -> None:
    ok = obtido == esperado
    print(f"  {'ok ' if ok else 'ERRO'} {rotulo}")
    if not ok:
        falhas.append(f"{rotulo}: esperado {esperado!r}, obtido {obtido!r}")


# --- 1. o marcador reconhece medida provisoria ------------------------------

print("marcador de norma alteradora")

lei, data, revog = planalto._marcador("(Redação dada pela Lei nº 13.467, de 2017)")
conferir("lei ordinaria", (lei, revog), ("Lei 13.467/2017", False))

lei, data, revog = planalto._marcador(
    "(Redação dada pela Medida Provisória nº 808, de 2017)"
)
conferir("medida provisoria e reconhecida", lei, "Medida Provisória 808/2017")
# Sem a data de publicacao a MP entraria em 1o de janeiro - dez meses antes de
# existir. O marcador so escreve o ano.
conferir("com a data de publicacao, nao 1o de janeiro", data, date(2017, 11, 14))

lei, _, revog = planalto._marcador("(Revogado pelo Decreto-lei nº 229, de 28.2.1967)")
conferir("decreto-lei nao vira 'lei'", lei, "Decreto-Lei 229/1967")
conferir("revogacao e lida como revogacao", revog, True)


# --- 2. tachado: onde o risco comeca, nao quanto ele cobre ------------------

print("\ndeteccao de tachado")

RISCADO_INTEIRO = "<strike>Art. 223-C. A etnia, a idade, a nacionalidade.</strike>"
conferir(
    "dispositivo riscado do rotulo em diante",
    planalto._superado(RISCADO_INTEIRO, planalto._texto_limpo(RISCADO_INTEIRO)),
    True,
)

# So o CSS, sem a tag. Sao 80 blocos da CLT, que a deteccao antiga perdia.
CSS = (
    '<span style="color: black; text-decoration:line-through">Art. 223-C. A honra, '
    "a imagem, a intimidade.</span>"
)
conferir(
    "line-through no CSS conta como tachado",
    planalto._superado(CSS, planalto._texto_limpo(CSS)),
    True,
)

# O art. 12 esta em vigor. O <strike> que ele carrega e de um titulo que vazou
# para dentro do <p> por HTML malformado.
VAZAMENTO = (
    "Art. 12 - Os preceitos concernentes ao regime de seguro social são objeto "
    "de lei especial.<b><strike>Armazenamento em meio eletrônico</strike></b>"
)
conferir(
    "titulo tachado que vazou nao revoga o artigo",
    planalto._superado(VAZAMENTO, planalto._texto_limpo(VAZAMENTO)),
    False,
)

# O Planalto risca as palavras derrubadas pela ADI 5766 dentro de artigo vigente.
# Marcar o art. 790-B como superado o tiraria de todas as consultas.
PARCIAL = (
    "Art. 790-B. A responsabilidade pelo pagamento dos honorários periciais é da "
    "parte sucumbente, <strike>ainda que beneficiária da justiça gratuita.</strike>"
)
conferir(
    "palavra inconstitucional riscada nao revoga o artigo",
    planalto._superado(PARCIAL, planalto._texto_limpo(PARCIAL)),
    False,
)


# --- 3. a linha do tempo do texto que retorna -------------------------------

print("\nvigencia com caducidade (art. 223-C)")

REFORMA = date(2017, 11, 11)
MP_INICIO, MP_FIM = planalto.CADUCIDADE["808"]


def bloco(texto: str, vig: date | None, caducou: date | None, superado: bool) -> Trecho:
    return Trecho(
        urn="clt/art-223-C",
        especie="artigo",
        rotulo="CLT, art. 223-C",
        texto=texto,
        pai=None,
        ordem=1,
        superado=superado,
        alterado_por=None,
        vigencia=vig,
        revogado_em=None,
        caducou_em=caducou,
    )


# A ordem e a do documento, que e cronologica. O terceiro bloco repete o texto do
# primeiro e carrega o mesmo marcador - e por isso que a data dele engana.
resolvido = planalto.com_vigencia(
    [
        bloco("texto da Reforma", REFORMA, None, superado=True),
        bloco("texto da MP 808", MP_INICIO, MP_FIM, superado=True),
        bloco("texto da Reforma", REFORMA, None, superado=False),
    ],
    piso=date(1943, 11, 10),
)
janelas = [(i, f, rev) for _, i, f, rev in resolvido]

conferir(
    "a Reforma vale ate a vespera da MP",
    janelas[0][:2],
    (REFORMA, date(2017, 11, 13)),
)
conferir("a MP vale da publicacao ate o ato do Congresso", janelas[1][:2], (MP_INICIO, MP_FIM))
conferir(
    "o texto que retorna comeca no dia seguinte a caducidade",
    janelas[2][:2],
    (date(2018, 4, 24), None),
)
conferir("nenhuma das tres fica sem data", [j[2] for j in janelas], [False, False, False])

# A prova de que nao ha buraco nem sobreposicao: as janelas se encaixam.
conferir(
    "as janelas cobrem o periodo sem se sobrepor",
    all(janelas[k][1] and janelas[k][1] < janelas[k + 1][0] for k in range(2)),
    True,
)


# --- 4. o corpus real, se estiver ingerido ---------------------------------

if Path("dados/corpus.db").exists():
    from app.corpus import banco

    print("\ncorpus ingerido: art. 223-C ao longo do tempo")
    con = banco.conectar()

    def em(d: str):
        return banco.vigente_em(con, "clt/art-223-C", date.fromisoformat(d))

    # Antes da Reforma o artigo NAO EXISTE. Devolver texto aqui e o erro que este
    # eixo existe para impedir - e era o que acontecia.
    conferir("em 2016 o artigo ainda nao existe", em("2016-05-10"), None)
    conferir("em 12/11/2017 vale a Reforma", "A honra" in em("2017-11-12")["texto"], True)
    conferir("em 01/12/2017 vale a MP 808", "A etnia" in em("2017-12-01")["texto"], True)
    conferir("em 01/06/2018 a Reforma ja voltou", "A honra" in em("2018-06-01")["texto"], True)
    conferir("hoje vale a Reforma", "A honra" in em(str(date.today()))["texto"], True)
    conferir("uma unica redacao vigente por data", len(banco.redacoes(con, "clt/art-223-C")), 3)
    con.close()
else:
    print("\n(corpus nao ingerido - rode: python -m app.corpus.indexar clt)")

if falhas:
    print("\nFALHOU")
    for f in falhas:
        print("  " + f)
    raise SystemExit(1)
print("\ncaducidade de MP ok")
