"""O parser do Planalto fora da CLT: CF, ADCT, Codigo Civil e leis esparsas.

    python testar_leis.py

O parser nasceu para a CLT, e cada lei nova trouxe uma forma que a CLT nao tem.
Todas quebravam em silencio - dispositivo sumido ou fundido com outro, nunca
erro na tela:

- **"Art. 1.228"**, com ponto de milhar. Lido como "1", o Codigo Civil parecia
  regredir mil artigos e o guarda de norma estranha descartava do art. 1.000 em
  diante: 948 de 2.046 artigos.
- **"Art. 5o -A."**, na Lei 6.019. O espaco antes do hifen fazia o art. 5o-A
  virar redacao nova do art. 5o. Aceitar o espaco sem criterio, porem, le o
  "Art. 11 -O direito de acao" da CLT como art. 11-O - e apaga a prescricao.
- **Alinea de inciso.** A alinea ia sempre para o caput. O ADCT, art. 10, II,
  'b' (estabilidade da gestante) nao existia no indice, e no art. 589 da CLT a
  alinea 'a' do inciso I e a do inciso II viravam a mesma URN.
- **"§ 6º-A"** era lido como § 6º. O § 3º-A do art. 832 da CLT passava por
  redacao nova do § 3º, que aparecia revogado desde 2018 estando em vigor.
- **Texto sem marcador depois de outra redacao** caia no piso da obra. O art.
  9o-C da Lei 8.036, criado em 2018, aparecia valendo desde 1990.
"""

from datetime import date
from pathlib import Path

from app.corpus import planalto
from app.corpus.busca import _como_referencia
from app.corpus.planalto import Trecho
from app.corpus.refs import interpretar

falhas = []


def conferir(rotulo: str, obtido, esperado) -> None:
    ok = obtido == esperado
    print(f"  {'ok ' if ok else 'ERRO'} {rotulo}")
    if not ok:
        falhas.append(f"{rotulo}: esperado {esperado!r}, obtido {obtido!r}")


def pagina(*paragrafos: str) -> bytes:
    return "".join(f"<p>{p}</p>" for p in paragrafos).encode("cp1252")


def ler(obra: str, *paragrafos: str, sigla: str | None = None) -> dict[str, Trecho]:
    return {t.urn: t for t in planalto.dispositivos(pagina(*paragrafos), obra, sigla=sigla)}


# --- 1. numeracao de artigo -------------------------------------------------

print("numeracao de artigo")

cc = ler(
    "cc",
    "Art. 999. O texto do artigo novecentos e noventa e nove.",
    "Art. 1.000. O texto do artigo mil, que o Codigo escreve com ponto.",
    "Art. 1.228. O proprietario tem a faculdade de usar, gozar e dispor da coisa.",
    sigla="CC",
)
conferir("artigo mil nao regride para o art. 1", "cc/art-1000" in cc, True)
conferir("nem e descartado como norma estranha", "cc/art-1228" in cc, True)
conferir("o rotulo leva o ponto de milhar", cc["cc/art-1228"].rotulo, "CC, art. 1.228")

lei = ler(
    "lei-6019-1974",
    "Art. 5o Empresa tomadora de servicos e a pessoa juridica que contrata.",
    "Art. 5o -A. Contratante e a pessoa fisica ou juridica que celebra contrato.",
)
conferir("'Art. 5o -A.' e o art. 5o-A", "lei-6019-1974/art-5-A" in lei, True)
conferir("e o art. 5o continua la", "lei-6019-1974/art-5" in lei, True)

clt = ler(
    "clt",
    "Art. 11 -O direito de acao quanto a creditos resultantes das relacoes de trabalho.",
    "Art. 58 - A duracao normal do trabalho nao excedera de 8 horas diarias.",
)
conferir("'Art. 11 -O direito' e o art. 11, nao o 11-O", sorted(clt), ["clt/art-11", "clt/art-58"])


# --- 2. cada subdivisao pendura na mais proxima acima -----------------------

print("\nhierarquia de subdivisoes")

adct = ler(
    "adct",
    "Art. 10. Ate que seja promulgada a lei complementar a que se refere o art. 7o:",
    "I - fica limitada a protecao nele referida ao aumento da porcentagem;",
    "II - fica vedada a dispensa arbitraria ou sem justa causa:",
    "a) do empregado eleito para cargo de direcao de comissoes internas;",
    "b) da empregada gestante, desde a confirmacao da gravidez ate cinco meses.",
    "§ 1º Ate que a lei venha a disciplinar o disposto no art. 7o, XIX.",
    sigla="ADCT",
)
conferir("alinea de inciso vai para o inciso", "adct/art-10/inc-II/al-b" in adct, True)
conferir(
    "e o rotulo diz o caminho inteiro",
    adct["adct/art-10/inc-II/al-b"].rotulo,
    "ADCT, art. 10, II, alínea 'b'",
)
conferir("paragrafo seguinte volta ao artigo", "adct/art-10/par-1" in adct, True)

clt = ler(
    "clt",
    "Art. 482 - Constituem justa causa para rescisao do contrato pelo empregador:",
    "a) ato de improbidade praticado pelo empregado;",
)
conferir("CLT antiga: alinea direto no caput", "clt/art-482/al-a" in clt, True)

clt = ler(
    "clt",
    "Art. 589. Da importancia da arrecadacao da contribuicao sindical serao feitos os creditos:",
    "I - para os empregadores, na forma seguinte:",
    "a) 5% (cinco por cento) para a confederacao correspondente;",
    "II - para os trabalhadores, na forma seguinte:",
    "a) 5% (cinco por cento) para a confederacao correspondente;",
)
conferir(
    "alineas 'a' de incisos diferentes sao dispositivos diferentes",
    sorted(u for u in clt if "/al-" in u),
    ["clt/art-589/inc-I/al-a", "clt/art-589/inc-II/al-a"],
)

clt = ler(
    "clt",
    "Art. 430. Na hipotese de os Servicos Nacionais nao oferecerem cursos suficientes:",
    "§ 6º Os entes qualificados em formacao tecnico-profissional deverao:",
    "III - cumprir os requisitos de qualidade da formacao profissional.",
    sigla="CLT",
)
conferir(
    "inciso de paragrafo e citado com o paragrafo",
    clt["clt/art-430/par-6/inc-III"].rotulo,
    "CLT, art. 430, § 6º, III",
)


# --- 3. paragrafo com sufixo de letra ---------------------------------------

print("\nparagrafo com sufixo")

adct = ler(
    "adct",
    "Art. 107. Ficam estabelecidos, para cada exercicio, limites individualizados.",
    "§ 6º Nao se incluem na base de calculo e nos limites estabelecidos neste artigo.",
    "§ 6º-A Nao se incluem no limite estabelecido no inciso I do caput deste artigo.",
    "§ 1o -A. O limite fixado neste artigo nao se aplica quando o contratante for.",
    "§ 1º - O disposto neste artigo aplica-se, igualmente, a quem trabalhe.",
    "§ 11. O pagamento de restos a pagar inscritos ate o fim do exercicio.",
    "§ 11-B O saldo remanescente sera apurado ao fim de cada exercicio fiscal.",
    sigla="ADCT",
)
conferir(
    "cada paragrafo com sufixo e proprio",
    sorted(adct),
    sorted(
        [
            "adct/art-107",
            "adct/art-107/par-6",
            "adct/art-107/par-6-A",
            "adct/art-107/par-1-A",
            "adct/art-107/par-1",
            "adct/art-107/par-11",
            "adct/art-107/par-11-B",
        ]
    ),
)
conferir("'§ 1º - O disposto' e o § 1º, estilo antigo", "adct/art-107/par-1" in adct, True)
conferir("ordinal ate o nono", adct["adct/art-107/par-6-A"].rotulo, "ADCT, art. 107, § 6º-A")
conferir("cardinal do decimo em diante", adct["adct/art-107/par-11-B"].rotulo, "ADCT, art. 107, § 11-B")


# --- 4. texto sem marcador nao cai no piso ---------------------------------


def trecho(texto: str, vigencia: date | None, superado: bool = False) -> Trecho:
    return Trecho(
        urn="lei-8036-1990/art-9-C", especie="artigo", rotulo="art. 9-C", texto=texto,
        pai=None, ordem=0, superado=superado, alterado_por=None, vigencia=vigencia,
        revogado_em=None,
    )


print("\nvigencia de redacao sem marcador")

resolvidos = planalto.com_vigencia(
    [
        trecho("Art. 9o-C redacao incluida em 2018", date(2018, 1, 1), superado=True),
        trecho("Art. 9o-C a mesma redacao, repetida sem marcador", None),
    ],
    piso=date(1990, 5, 14),
)
conferir(
    "a redacao repetida comeca com a anterior, nao no piso da lei",
    resolvidos[1][1],
    date(2018, 1, 1),
)


# --- 5. referencia na consulta livre ----------------------------------------

print("\nreferencia com a obra na consulta")

for consulta, urn in [
    ("art. 7º, XXIX da CF", "cf/art-7/inc-XXIX"),
    ("CF, art. 7º, XXIX", "cf/art-7/inc-XXIX"),
    ("art. 10, II, b do ADCT", "adct/art-10/inc-II/al-b"),
    ("art. 118 da Lei 8.213/91", "lei-8213-1991/art-118"),
    ("art. 1.228 do Código Civil", "cc/art-1228"),
    ("art. 71 §4º", "clt/art-71/par-4"),
    ("CLT, art. 482, i", "clt/art-482/al-i"),
]:
    conferir(f"{consulta!r}", interpretar(*_como_referencia(consulta)).urns, [urn])


# --- 6. o corpus real, se estiver ingerido ---------------------------------

if Path("dados/corpus.db").exists():
    from app.corpus import banco, busca

    con = banco.conectar()
    if "cf" not in banco.obras(con):
        print("\n(CF nao ingerida - rode: python -m app.corpus.indexar cf adct cc ...)")
    else:
        print("\ncorpus ingerido")

        def em(urn: str, d: str):
            return banco.vigente_em(con, urn, date.fromisoformat(d))

        hoje = str(date.today())
        gestante = em("adct/art-10/inc-II/al-b", hoje)
        conferir("ADCT, art. 10, II, 'b' e a gestante", bool(gestante) and "gestante" in gestante["texto"], True)
        conferir("CC, art. 1.228 esta no indice", bool(em("cc/art-1228", hoje)), True)
        conferir("CLT, art. 832, § 3º vigente hoje", bool(em("clt/art-832/par-3", hoje)), True)
        conferir("CLT, art. 879, § 1º vigente hoje", bool(em("clt/art-879/par-1", hoje)), True)
        conferir("Lei 8.036, art. 9o-C nao existe em 2010", em("lei-8036-1990/art-9-C", "2010-01-01"), None)

        # A MP 739 reescreveu o art. 62 da Lei 8.213 e caducou em 04/11/2016; o
        # texto anterior volta no dia seguinte.
        durante = em("lei-8213-1991/art-62", "2016-09-01")
        depois = em("lei-8213-1991/art-62", "2016-11-10")
        conferir("em 09/2016 vale a MP 739", (durante["alterado_por"] or "").startswith("Medida Provisória 739"), True)
        conferir("em 11/2016 a MP ja caducou", (depois["alterado_por"] or "").startswith("Medida Provisória 739"), False)

        r = busca.buscar(con, "art. 7º, XXIX da CF")
        conferir("a consulta livre acha a CF", [a.urn for a in r.achados], ["cf/art-7/inc-XXIX"])
    con.close()

if falhas:
    print("\nFALHOU")
    for f in falhas:
        print("  " + f)
    raise SystemExit(1)
print("\nleis fora da CLT ok")
