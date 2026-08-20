"""Ingestao de normas publicadas no Planalto.

O HTML do Planalto e legado - FrontPage 6.0, cp1252, decadas de edicoes manuais -
mas carrega tres coisas que valem ouro e que nenhuma outra fonte da de graca:

**Ancoras que marcam cada dispositivo.** `<a name="art71">`, `<a name="art71§4">`.
Um ponto no fim marca redacao sucessiva: `art71§4` e a redacao anterior,
`art71§4.` e a que a substituiu.

**`<strike>` marca texto superado.** E o sinal de vigencia encerrada, escrito no
proprio documento.

**A autoria da alteracao vem inline.** "(Redacao dada pela Lei no 13.467, de 2017)"
diz quem mudou e quando.

Uma decisao de parsing importa mais que as outras: **a ancora localiza, o texto
classifica.** A ancora `art223a` designa o art. 223-A, nao a alinea "a" do art.
223 - e nao ha como saber isso pela ancora. O texto, esse, sempre se identifica:
"Art. 223-A.", "§ 4o", "I -", "a)". Confiar na ancora para classificar erra em
silencio; confiar no texto erra alto, e erro alto se conserta.
"""

from __future__ import annotations

import html
import re
import ssl
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.schema import REFORMA

CACHE = Path(__file__).parent.parent.parent / "dados" / "fontes"

# Vigencia da CLT (Decreto-Lei 5.452/1943, art. 2o do decreto). Serve de piso
# quando o dispositivo nao traz marcador de alteracao: e o texto original.
VIGENCIA_CLT = date(1943, 11, 10)

URL_CLT = "https://www.planalto.gov.br/ccivil_03/decreto-lei/del5452.htm"
# Onde a Consolidacao comeca, depois do decreto-lei que a aprovou.
INICIO_CLT = r"^CONSOLIDA[CÇ][AÃ]O DAS LEIS DO TRABALHO"

# So <p>. Tentar incluir <h1-h6> parece atraente - ha 1 artigo perdido num <h4> -
# mas headings envolvem <p> neste documento, e a alternacao passa a casar o
# heading inteiro como um bloco unico, fundindo dezenas de dispositivos em um so.
# Custo de incluir: 34 dispositivos do catalogo somem. Beneficio: 1. Fica <p>.
_BLOCO = re.compile(r"<p\b[^>]*>(.*?)</p>", re.I | re.S)
_ANCORA = re.compile(r'<a\s+name="([^"]+)"', re.I)
_TAG = re.compile(r"<[^>]+>")
_ESPACO = re.compile(r"\s+")

# Marcadores de alteracao, na forma em que o Planalto os escreve. Captura tambem
# o TIPO da norma - "Decreto-Lei no 229" nao e "Lei 229", e chamar assim produz
# uma citacao que nao existe.
#
# A especie precisa aceitar letra acentuada. Com apenas [A-Za-zç] o "o" de "Medida
# Provisoria" nao casa, e os 560 marcadores de MP da CLT ficam sem norma
# reconhecida - o que joga a redacao no piso de 1943 e faz texto de MP aparecer
# como redacao original da Consolidacao.
_ESPECIE = r"[A-Za-zÀ-ÖØ-öø-ÿ\-\s]"
_NORMA = r"\bpel[ao]s?\s+(" + _ESPECIE + r"{3,40}?)\s*n?[ºo°.\s]*([\d.]+)([^)]*?)\)"
_MARCADOR = re.compile(
    r"\(\s*(?:Reda[cç][aã]o dada|Inclu[ií]d[oa]|Renumerad[oa])[^)]*?" + _NORMA, re.I
)
_REVOGACAO = re.compile(r"\(\s*Revogad[oa]\b[^)]*?" + _NORMA, re.I)
_DATA_LEI = re.compile(r"de\s*(?:(\d{1,2})[./](\d{1,2})[./])?(\d{4})", re.I)

# Medida provisoria que caducou nao e o mesmo que norma revogada, e a diferenca
# muda a resposta. Revogacao poe um texto novo no lugar do antigo. Caducidade
# apenas encerra a eficacia da MP - e o texto ANTERIOR volta a valer, sem que
# nenhuma norma nova seja publicada. Um indice que trata as duas do mesmo jeito
# serve texto de MP caduca como se fosse a lei de hoje.
#
# O Planalto marca esses blocos com "(Vigencia encerrada)" e um link para o Ato
# Declaratorio do Congresso. As datas abaixo foram lidas desses atos e das
# proprias MPs, nao inferidas:
#
#   MP 808/2017  DOU 14/11/2017  encerrada 23/04/2018  (ADC 22/2018)
#   MP 873/2019  DOU 01/03/2019  encerrada 28/06/2019  (ADC 43/2019)
#   MP 905/2019  DOU 12/11/2019  encerrada 18/08/2020  (ADC 127/2020)
#   MP 955/2020  DOU 20/04/2020  encerrada 17/08/2020  (ADC 113/2020)
#
# As demais MPs citadas pela CLT nao entram aqui porque nao caducaram: 1.107,
# 1.108 e 1.116 viraram lei, e 2.164, 2.180 e 2.226 seguem em vigor por forca do
# art. 2o da EC 32/2001. Se aparecer "(Vigencia encerrada)" de uma MP fora desta
# tabela, a ingestao avisa em vez de adivinhar.
CADUCIDADE = {
    "808": (date(2017, 11, 14), date(2018, 4, 23)),
    "873": (date(2019, 3, 1), date(2019, 6, 28)),
    "905": (date(2019, 11, 12), date(2020, 8, 18)),
    "955": (date(2020, 4, 20), date(2020, 8, 17)),
}
_VIG_ENCERRADA = re.compile(r"Vig[eê]ncia\s+encerrada", re.I)
_E_MP = re.compile(r"^Medida\s+Provis", re.I)

# Tachado vem de duas formas neste documento: a tag <strike> e o CSS
# "text-decoration:line-through". So a tag nao basta - 80 blocos usam apenas o
# CSS. Mas a presenca do sinal tambem nao basta, por dois motivos:
#
#   O HTML e malformado e um <strike> de titulo vaza para dentro do <p> seguinte.
#   O art. 12 carrega "Armazenamento em meio eletronico" tachado e esta vigente.
#
#   O Planalto risca palavras isoladas declaradas inconstitucionais dentro de
#   artigo em vigor - art. 790-B e o art. 791-A par. 4o, pela ADI 5766.
#
# O criterio que separa os casos e posicional, nao quantitativo: o Planalto risca
# o dispositivo A PARTIR DO ROTULO. Se o trecho tachado comeca igual ao bloco, o
# dispositivo foi superado; se o risco comeca no meio, e outra coisa.
_STRIKE_TAG = re.compile(r"<(strike|s)\b[^>]*>(.*?)</\1>", re.I | re.S)
_STRIKE_CSS = re.compile(r"<span[^>]*line-through[^>]*>(.*?)</span>", re.I | re.S)
_PREFIXO = 15

# "Art[. .]189": tolera pontuacao repetida ANTES do numero porque a fonte tem erro
# de digitacao - o art. 189 vigente, que define insalubridade, esta escrito
# "Art. . 189" no Planalto. "Arts." nao casa de proposito: e referencia cruzada.
#
# O sufixo de letra exige o hifen COLADO no numero, e isso nao e frescura: a CLT
# antiga escreve "Art. 58 - A duracao normal do trabalho...". Aceitar espaco antes
# do hifen le esse artigo como "art. 58-A" e apaga o art. 58 - junto com todos os
# outros no formato antigo, que sao a maioria da Consolidacao.
_ARTIGO = re.compile(r"^Art[.\s]*(\d+)(?:[-–—]\s*([A-Z])\b)?\s*[-.–]?", re.I)
_PAR_UNICO = re.compile(r"^Par[aá]grafo\s+[uú]nico", re.I)
_PARAGRAFO = re.compile(r"^§\s*(\d+)")
_INCISO = re.compile(r"^([IVXLC]{1,7})\s*[-–.)]")
_ALINEA = re.compile(r"^([a-z])\s*\)")


@dataclass
class Bloco:
    """Um paragrafo do HTML, ja limpo e classificado."""

    ancoras: list[str]
    texto: str
    superado: bool
    alterado_por: str | None
    # Data que o marcador carrega. O TIPO do marcador diz o que ela significa:
    # "Incluido/Redacao dada" -> a redacao COMECA ali; "Revogado" -> ela TERMINA.
    # Ler so a data e perder a metade que importa.
    vigencia: date | None
    revogado_em: date | None
    # Dia em que a MP perdeu eficacia. Distinto de `revogado_em`: aqui nao ha
    # norma nova, e a redacao anterior volta no dia seguinte.
    caducou_em: date | None = None


# --- captura ----------------------------------------------------------------


def baixar(url: str, nome: str, forcar: bool = False) -> bytes:
    """Baixa e guarda em dados/fontes/. Reusa o arquivo local se ja existir.

    A captura fica em disco de proposito: reingerir nao deve depender de o site
    estar no ar, e o sha256 do que foi efetivamente lido e o que vai para o
    registro de fonte.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    destino = CACHE / nome
    if destino.exists() and not forcar:
        return destino.read_bytes()

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=120) as r:
        bruto = r.read()
    destino.write_bytes(bruto)
    return bruto


# --- limpeza ----------------------------------------------------------------


def _texto_limpo(fragmento: str) -> str:
    texto = _TAG.sub(" ", fragmento)
    texto = html.unescape(texto).replace("\xa0", " ")
    # O Planalto escreve ordinal como "4<u><sup>o</sup></u>": depois de tirar as
    # tags sobra "4 o". Reune antes que o classificador leia "4" e "o" separados.
    texto = re.sub(r"(?<=\d)\s+([oºa°ª])\b", r"\1", texto)
    texto = _ESPACO.sub(" ", texto).strip()
    # "Art. . 189" e erro de digitacao do site, nao do legislador. Normalizar o
    # rotulo nao e editar a lei - o texto do dispositivo segue intocado.
    return re.sub(r"^(Art\.)\s*\.\s*", r"\1 ", texto)


def _marcador(fragmento: str) -> tuple[str | None, date | None, bool]:
    """Extrai (lei, data, e_revogacao) do marcador do Planalto.

    "(Revogado pela Lei no 13.467, de 2017)" e "(Incluido pela Lei no 8.923, de
    27.7.1994)" trazem datas com sentidos OPOSTOS: a primeira encerra a vigencia,
    a segunda a inicia. Tratar as duas como inicio faz o indice servir texto
    revogado como se fosse a lei de hoje.
    """
    # A revogacao e procurada primeiro, e por regex propria. Dois motivos:
    #
    # 1. Um bloco pode ter varios marcadores - o art. 141 traz "(Redacao dada pelo
    #    Decreto-lei 1.535)" e depois "(Revogado pela Lei 13.874)". Ficar com o
    #    primeiro mantem no indice, como vigente, um artigo que nao existe mais.
    # 2. A fonte tem parenteses sem fechar. Nesse mesmo art. 141 falta o ")" do
    #    primeiro marcador, entao uma varredura generica casa do "(" dele ate o
    #    ")" da revogacao, e a revogacao vira texto interno de outro marcador.
    #    Ancorar em "(Revogad" contorna o parenteses quebrado.
    revogacao = True
    m = _REVOGACAO.search(fragmento)
    if m is None:
        revogacao = False
        m = _MARCADOR.search(fragmento)
    if m is None:
        return None, None, False

    especie, numero, resto = m.group(1), m.group(2), m.group(3)

    especie = _ESPACO.sub(" ", especie).strip().title()
    numero = numero.rstrip(".")
    norma = f"{especie} {numero}"

    # A Reforma e o unico marco que o sistema inteiro ja conhece por data exata.
    # Para as demais normas, o marcador traz a data de PUBLICACAO, que so coincide
    # com a vigencia quando nao ha vacatio - por isso a data e aproximada, e o
    # README diz isso.
    if numero.replace(".", "") == "13467":
        return "Lei 13.467/2017", REFORMA, revogacao

    # MP que caducou tem data de publicacao conhecida. O marcador so escreve o ano
    # ("de 2017"), e cair no default de 1o de janeiro colocaria em vigor, desde
    # janeiro, texto que so passou a existir em novembro.
    if _E_MP.match(especie) and numero in CADUCIDADE:
        return f"{norma}/{CADUCIDADE[numero][0].year}", CADUCIDADE[numero][0], revogacao

    d = _DATA_LEI.search(resto)
    if not d:
        return norma, None, revogacao
    dia, mes, ano = d.groups()
    try:
        return f"{norma}/{ano}", date(int(ano), int(mes or 1), int(dia or 1)), revogacao
    except ValueError:
        return f"{norma}/{ano}", None, revogacao


def _superado(fragmento: str, texto: str) -> bool:
    """O tachado cobre o dispositivo, ou so um pedaco solto?

    Ver o comentario de _STRIKE_TAG: a resposta esta em ONDE o risco comeca, nao
    em quanto ele cobre.
    """
    n = min(_PREFIXO, len(texto))
    if n < 6:
        return False
    riscados = [_texto_limpo(m.group(2)) for m in _STRIKE_TAG.finditer(fragmento)]
    riscados += [_texto_limpo(m.group(1)) for m in _STRIKE_CSS.finditer(fragmento)]
    return any(r[:n] == texto[:n] for r in riscados)


def blocos(bruto: bytes) -> list[Bloco]:
    """Quebra o HTML em paragrafos limpos, na ordem do documento."""
    fonte = bruto.decode("cp1252", errors="replace")
    saida = []
    for m in _BLOCO.finditer(fonte):
        fragmento = m.group(1)
        texto = _texto_limpo(fragmento)
        if not texto:
            continue
        lei, data, revogacao = _marcador(fragmento)
        # "(Vigencia encerrada)" so vale como caducidade quando o bloco de fato
        # traz a redacao da MP. O mesmo aviso aparece solto em blocos vizinhos.
        caducou = None
        if _VIG_ENCERRADA.search(fragmento) and lei:
            numero = lei.split("/")[0].rsplit(" ", 1)[-1]
            if _E_MP.match(lei) and numero in CADUCIDADE:
                caducou = CADUCIDADE[numero][1]
        saida.append(
            Bloco(
                ancoras=_ANCORA.findall(fragmento),
                texto=texto,
                superado=_superado(fragmento, texto),
                alterado_por=lei,
                vigencia=None if revogacao else data,
                revogado_em=data if revogacao else None,
                caducou_em=caducou,
            )
        )
    return saida


def mps_sem_tabela(bruto: bytes) -> set[str]:
    """MPs com "(Vigencia encerrada)" que a tabela CADUCIDADE nao conhece.

    Silenciar isso seria repetir o erro que este modulo acabou de corrigir: a MP
    entraria como alteracao comum, sem fim de vigencia, e seu texto ficaria
    valendo para sempre. A ingestao prefere avisar.
    """
    # A chave e o numero, nao o rotulo: o mesmo bloco pode sair como "Medida
    # Provisoria 905" ou "Medida Provisoria 905/2019", conforme o marcador traga
    # ou nao o ano, e avisar duas vezes da mesma MP so atrapalha quem le.
    fora = set()
    for bloco in blocos(bruto):
        if not _VIG_ENCERRADA.search(bloco.texto) or not bloco.alterado_por:
            continue
        if not _E_MP.match(bloco.alterado_por):
            continue
        numero = bloco.alterado_por.split("/")[0].rsplit(" ", 1)[-1]
        if numero not in CADUCIDADE:
            fora.add(numero)
    return {f"Medida Provisória {n}" for n in fora}


# --- classificacao ----------------------------------------------------------


@dataclass
class Trecho:
    """Um dispositivo reconhecido, ja com URN e procedencia."""

    urn: str
    especie: str
    rotulo: str
    texto: str
    pai: str | None
    ordem: int
    superado: bool
    alterado_por: str | None
    vigencia: date | None
    revogado_em: date | None
    caducou_em: date | None = None


def _sem_marcador(texto: str) -> str:
    """Tira do texto os parenteses de "(Redacao dada...)" e "(Vide...)".

    Eles sao metadado do Planalto, nao texto de lei. Deixar dentro polui o indice
    e faz a busca casar a nota editorial em vez do dispositivo.
    """
    limpo = re.sub(
        r"\((?:Reda[cç][aã]o|Inclu[ií]d|Revogad|Renumerad|Vide|Vig[eê]ncia|Vetado)"
        r"[^)]*\)",
        "",
        texto,
        flags=re.I,
    )
    return _ESPACO.sub(" ", limpo).strip()


def dispositivos(bruto: bytes, obra: str, inicio: str | None = None) -> list[Trecho]:
    """Percorre o documento montando URNs a partir do contexto corrente.

    `inicio` e um padrao que marca onde a norma comeca de fato. A pagina da CLT
    traz antes o decreto-lei que a aprovou, e esse decreto tem os proprios arts.
    1o e 2o - "Fica aprovada a Consolidacao" e "entrara em vigor em 10 de novembro
    de 1943". Sem o corte, eles colidem com os arts. 1o e 2o da CLT (conceito de
    empregador), e a colisao cai justamente sobre os artigos que fundam o vinculo.
    """
    trechos: list[Trecho] = []
    artigo: str | None = None
    sub: str | None = None  # paragrafo ou inciso corrente, para pendurar alinea
    ordem = 0
    comecou = inicio is None
    padrao_inicio = re.compile(inicio, re.I) if inicio else None

    for bloco in blocos(bruto):
        texto = _sem_marcador(bloco.texto)
        if len(texto) < 8:
            continue

        if not comecou:
            comecou = bool(padrao_inicio.search(texto))
            continue

        especie = rotulo = None
        urn = pai = None
        corte = 0  # onde termina o identificador ("Art. 71 -", "§ 4o", "I -")

        if m := _ARTIGO.match(texto):
            corte = m.end()
            numero = m.group(1) + (f"-{m.group(2)}" if m.group(2) else "")
            artigo, sub = numero, None
            urn = f"{obra}/art-{numero}"
            especie, rotulo, pai = "artigo", f"art. {numero}", None

        elif artigo and (m := _PAR_UNICO.match(texto)):
            corte = m.end()
            sub = "par-unico"
            urn = f"{obra}/art-{artigo}/par-unico"
            especie, rotulo = "paragrafo", f"art. {artigo}, parágrafo único"
            pai = f"{obra}/art-{artigo}"

        elif artigo and (m := _PARAGRAFO.match(texto)):
            corte = m.end()
            sub = f"par-{m.group(1)}"
            urn = f"{obra}/art-{artigo}/{sub}"
            especie, rotulo = "paragrafo", f"art. {artigo}, § {m.group(1)}º"
            pai = f"{obra}/art-{artigo}"

        elif artigo and (m := _INCISO.match(texto)):
            corte = m.end()
            romano = m.group(1).upper()
            base = f"{obra}/art-{artigo}"
            # Inciso pendura no paragrafo corrente quando ha um; senao, no caput.
            if sub and sub.startswith("par-"):
                base = f"{base}/{sub}"
            urn = f"{base}/inc-{romano}"
            especie, rotulo = "inciso", f"art. {artigo}, {romano}"
            pai = base

        elif artigo and (m := _ALINEA.match(texto)):
            corte = m.end()
            letra = m.group(1)
            base = f"{obra}/art-{artigo}"
            if sub:
                base = f"{base}/{sub}"
            urn = f"{base}/al-{letra}"
            especie, rotulo = "alinea", f"art. {artigo}, alínea '{letra}'"
            pai = base

        if not urn:
            continue

        # "Art. 235-H. ." e "Art. 390-A. ." aparecem no documento: o identificador
        # ficou num bloco e o texto foi para outro. Indexar a casca poluiria a
        # busca com dispositivos sem conteudo, que casam qualquer consulta.
        #
        # A medida e o que sobra DEPOIS do identificador, nunca o tamanho do
        # rotulo: rotulo e texto de exibicao, e mudar "par. 4o" para "§ 4o"
        # mexeria no criterio de descarte sem ninguem perceber.
        if len(texto[corte:].strip(" .-–")) < 12:
            continue

        ordem += 1
        trechos.append(
            Trecho(
                urn=urn,
                especie=especie,
                rotulo=f"{obra.upper()}, {rotulo}",
                texto=texto,
                pai=pai,
                ordem=ordem,
                superado=bloco.superado,
                alterado_por=bloco.alterado_por,
                vigencia=bloco.vigencia,
                revogado_em=bloco.revogado_em,
                caducou_em=bloco.caducou_em,
            )
        )

    return trechos


def com_vigencia(
    trechos: list[Trecho], piso: date
) -> list[tuple[Trecho, date, date | None, bool]]:
    """Resolve a janela de vigencia de cada redacao.

    Um dispositivo aparece varias vezes no documento: a redacao antiga vem
    tachada, a nova logo abaixo. A ordem no documento e cronologica - o Planalto
    sempre imprime a superada antes da vigente.

    Devolve (trecho, inicio, fim, revogado). `revogado` cobre o caso em que o
    texto esta tachado e nao ha sucessora nem data legivel: sabe-se que saiu da
    lei, nao se sabe quando. Servir esse texto como vigente seria o pior erro que
    o indice pode cometer, entao ele fica marcado e a consulta o exclui.

    A caducidade de medida provisoria quebra a sucessao simples. O art. 223-C tem
    tres blocos: o texto da Reforma, o da MP 808 e de novo o da Reforma. O
    terceiro nao e redacao nova - e a mesma de antes, que VOLTA quando a MP perde
    eficacia. Por isso a data que o marcador dele carrega (11/11/2017, quando a
    Reforma entrou) nao serve de inicio: o inicio e o dia seguinte ao fim da MP.
    """
    por_urn: dict[str, list[Trecho]] = {}
    for t in trechos:
        por_urn.setdefault(t.urn, []).append(t)

    resolvidos = []
    for redacoes in por_urn.values():
        for i, t in enumerate(redacoes):
            inicio = t.vigencia or piso
            # Texto que volta depois da caducidade recomeca no dia seguinte, e nao
            # na data em que valeu pela primeira vez.
            if i and redacoes[i - 1].caducou_em:
                inicio = date.fromordinal(redacoes[i - 1].caducou_em.toordinal() + 1)

            fim: date | None = None
            revogado = False

            if t.caducou_em:
                # A MP vale ate o dia declarado pelo ato do Congresso, inclusive.
                fim = t.caducou_em
            elif t.revogado_em:
                # "(Revogado pela Lei X, de DATA)": a data encerra a vigencia.
                fim = date.fromordinal(t.revogado_em.toordinal() - 1)
            elif i + 1 < len(redacoes):
                proxima = redacoes[i + 1]
                if proxima.vigencia and proxima.vigencia > inicio:
                    fim = date.fromordinal(proxima.vigencia.toordinal() - 1)
                elif t.superado:
                    # Superada por uma redacao sem data legivel, ou por uma cuja
                    # data e anterior a esta - o que acontece quando a sucessora e
                    # um texto que retorna. A sucessora responde pelo presente;
                    # esta nao pode responder por nada.
                    revogado = True
            elif t.superado:
                revogado = True

            resolvidos.append((t, inicio, fim, revogado))
    return resolvidos
