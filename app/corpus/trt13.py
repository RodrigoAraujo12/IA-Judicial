"""Ingestao das Sumulas do TRT da 13a Regiao (Paraiba).

Primeira obra REGIONAL do corpus. Vale para caso cujo TRT e o 13 - ver
`app/jurisdicao.py` - e para nenhum outro; o sufixo `-trt13` no nome da obra e o
que o filtro da busca le.

**A fonte e o site do Tribunal, pagina a pagina.** O NUGEP publica um indice com
um link por sumula e o texto de cada uma numa pagina propria (Plone). Nao ha
arquivo consolidado como o Livro do TST, entao a captura sao 46 requisicoes: o
indice mais 45 verbetes. Todas ficam em `dados/fontes/trt13/`, e o registro de
fonte leva o sha256 da concatenacao - mudou UMA pagina, o hash acusa.

**O site recusa cliente que nao pareca navegador.** Com `User-Agent: Mozilla/5.0`
seco a resposta e 403; com a assinatura completa de um Chrome, 200. Nao e
contorno de bloqueio a robo, e cabecalho que o servidor exige para servir uma
pagina publica.

**O HTML vem picotado.** O texto foi colado do Word e chega em spans que partem
palavra e data ao meio: "1<span>9.12.2017", "0<span>1</span>.201<span>8". Por
isso tag inline vira NADA (e nao espaco) e so tag de bloco vira quebra de linha.
Sem isso "19.12.2017" vira "1 9.12.2017" e a data some.

**Vigencia vem do bloco "Historico", e cada evento tem um sentido.**

- "Redacao original: ... disponibilizada no DEJT em 28, 29 e 30.06.2010" abre a
  janela. A data que vale e a ULTIMA da linha: a publicacao no diario se completa
  no ultimo dia, e a data do acordao, que vem antes, nao e a da sumula.
- "Redacao alterada" e "Inclusao do item II" substituem o inicio: o texto que a
  pagina mostra e o novo, e a fonte nao guarda o antigo. Uma redacao por verbete,
  como no TST - o esquema aceita o historico depois, sem migracao.
- "Sumula cancelada: ... DEJT em 28.04.2017" FECHA a janela na vespera. Cancelada
  nao vira `revogado`: um caso de 2016 continua encontrando a Sumula 7, que e
  o mesmo motivo pelo qual a CLT tem vigencia por dispositivo. So cai em
  `revogado` o cancelamento sem data legivel.
- "Revisao: IAC ... Tema 10" NAO move o inicio. A revisao fixa tese sobre a
  materia, mas o texto do verbete continua o original - mover a vigencia para
  2026 esconderia a sumula de todo caso anterior, e o texto que ele veria e o
  mesmo. A tese fica fora do `texto`: e acordao, nao verbete.
- "..., e em 07, 08 e 11.03.2019, por mera formalidade" e republicacao. Se a
  ultima data da linha fosse essa, tres sumulas de 2016 nasceriam em 2019 e um
  caso de 2017 nao as encontraria. O trecho e descartado antes de ler a data.

**O titulo (ementa em caixa alta) nao entra no `texto`.** Entra so no indexado,
pela mesma razao do TST: e ementa da publicacao, nao parte do verbete, e uma peca
que o transcrevesse citaria o Tribunal dizendo o que ele nao disse.
"""

from __future__ import annotations

import html
import re
import ssl
import time
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta

from app.corpus.planalto import CACHE

URL_INDICE = "https://www.trt13.jus.br/institucional/nugep/sumulas"
PASTA = "trt13"
OBRA = "sumula-trt13"
ROTULO = "Sumula {n} do TRT-13"

# O que o servidor exige para responder 200. Ver docstring.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)

# Piso para verbete sem data legivel. A Sumula 1 e de dezembro de 2003 (RA
# 223/2003); nada aqui e anterior a isso, e o piso so precisa ficar antes de
# qualquer caso que o sistema va ver.
PISO = date(2003, 1, 1)


@dataclass
class Verbete:
    numero: int
    titulo: str
    status: str            # "vigente", "alterada", "revisada", "cancelada"
    texto: str
    historico: str
    vigencia_inicio: date
    vigencia_fim: date | None
    revogado: bool
    # O evento que fecha ou substitui a redacao, para `alterado_por`.
    cabecalho: str

    @property
    def urn(self) -> str:
        return f"{OBRA}/{self.numero}"

    @property
    def rotulo(self) -> str:
        return ROTULO.format(n=self.numero)


# --- captura ----------------------------------------------------------------


def _baixar_pagina(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=120) as r:
        return r.read()


# href com aspas duplas OU simples: o indice usa as duas, e a regex que so lia
# uma delas perdia a Sumula 5 em silencio.
_LINK = re.compile(
    r"""<a\s+href=(["'])(?P<href>[^"']+)\1[^>]*class="state-published contenttype-document">"""
    r"""\s*<span>(?P<span>[^<]+)</span>""",
    re.S,
)


def links(indice: str) -> list[tuple[int, str]]:
    """(numero, url) de cada sumula listada no indice, em ordem de numero."""
    saida: dict[int, str] = {}
    for m in _LINK.finditer(indice):
        rotulo = html.unescape(m.group("span"))
        n = re.search(r"(\d+)", rotulo)
        if n:
            saida.setdefault(int(n.group(1)), m.group("href"))
    return sorted(saida.items())


def baixar(forcar: bool = False) -> dict[str, bytes]:
    """Indice mais uma pagina por sumula. Reusa o que ja esta em disco.

    Devolve {nome do arquivo: bytes}, com o indice em primeiro lugar e as sumulas
    em ordem de numero - a ordem importa porque o sha256 da fonte e o da
    concatenacao.
    """
    pasta = CACHE / PASTA
    pasta.mkdir(parents=True, exist_ok=True)

    indice_arq = pasta / "_indice.html"
    if indice_arq.exists() and not forcar:
        indice = indice_arq.read_bytes()
    else:
        indice = _baixar_pagina(URL_INDICE)
        indice_arq.write_bytes(indice)

    paginas: dict[str, bytes] = {"_indice.html": indice}
    for numero, url in links(indice.decode("utf-8", "replace")):
        nome = f"sumula-{numero:02d}.html"
        destino = pasta / nome
        if destino.exists() and not forcar:
            paginas[nome] = destino.read_bytes()
            continue
        paginas[nome] = _baixar_pagina(url)
        destino.write_bytes(paginas[nome])
        time.sleep(0.3)  # 45 paginas; nao ha pressa e o servidor e de um tribunal
    return paginas


# --- HTML -> texto ----------------------------------------------------------

_BLOCO = re.compile(r"</?(?:p|div|br|li|ul|ol|h[1-6]|tr|table)\b[^>]*>", re.I)
_TAG = re.compile(r"<[^>]+>")
_DIV = re.compile(r"</?div\b", re.I)


def _linhas(fragmento: str) -> list[str]:
    """Tag de bloco vira quebra; tag inline vira NADA. Ver docstring do modulo."""
    texto = _BLOCO.sub("\n", fragmento)
    texto = _TAG.sub("", texto)
    texto = html.unescape(texto).replace("\xa0", " ")
    linhas = [re.sub(r"\s+", " ", l).strip() for l in texto.split("\n")]
    return [l for l in linhas if l]


def _bloco(pagina: str, marcador: str) -> str | None:
    """O HTML de um <div id=...> do Plone, ate o proximo `</div>` de mesmo nivel."""
    i = pagina.find(marcador)
    if i < 0:
        return None
    i = pagina.find(">", i) + 1
    profundidade, j = 1, i
    while profundidade and (m := _DIV.search(pagina, j)):
        profundidade += -1 if pagina.startswith("</", m.start()) else 1
        j = m.end()
    return pagina[i : pagina.rfind("<", i, j)] if profundidade == 0 else pagina[i:]


# --- datas ------------------------------------------------------------------

_MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4, "maio": 5,
    "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
}
# "11.12.2003", "07/01/2013", e o que sobra de "1<span>9.12.2017": espacos
# opcionais entre as partes. O lookbehind evita casar dentro de numero de
# processo ("0000618-07.2017.5.13.0019" tem "07.2017" mas nao "dd.mm.aaaa").
_DATA_NUM = re.compile(r"(?<!\d)(\d{1,2})\s*[./]\s*(\d{1,2})\s*[./]\s*(\d{4})(?!\d)")
_DATA_EXT = re.compile(
    r"(?<!\d)(\d{1,2})\s+de\s+([a-zç]+)\s+de\s+(\d{4})(?!\d)", re.I
)
# Republicacao "por mera formalidade": nao e data de vigencia.
_REPUBLICACAO = re.compile(r",?\s*e\s+em\s.*?por\s+mera\s+formalidade[^.]*\.?", re.I | re.S)


def _valida(d: int, m: int, a: int) -> date | None:
    if a < 1990 or not 1 <= m <= 12:
        return None
    try:
        return date(a, m, d)
    except ValueError:
        return None


def ultima_data(texto: str) -> date | None:
    """A ultima data completa do trecho, ignorando republicacao por formalidade."""
    texto = _REPUBLICACAO.sub("", texto)
    achadas: list[tuple[int, date]] = []
    for m in _DATA_NUM.finditer(texto):
        if d := _valida(int(m.group(1)), int(m.group(2)), int(m.group(3))):
            achadas.append((m.start(), d))
    for m in _DATA_EXT.finditer(texto):
        mes = _MESES.get(m.group(2).lower())
        if mes and (d := _valida(int(m.group(1)), mes, int(m.group(3)))):
            achadas.append((m.start(), d))
    return max(achadas)[1] if achadas else None


# --- historico --------------------------------------------------------------

_EVENTO = re.compile(
    r"(?P<original>Reda[cç][aã]o\s+original)"
    r"|(?P<alterada>Reda[cç][aã]o\s+alterada|Inclus[aã]o\s+do\s+item)"
    r"|(?P<cancelada>S[uú]mula\s+cancelada)"
    r"|(?P<revisao>Revis[aã]o\s*:)"
    r"|(?P<tese>Tese\s+jur[ií]dica)",
    re.I,
)


def eventos(historico: str) -> list[tuple[str, str]]:
    """Quebra o bloco "Historico" em (tipo, trecho), na ordem em que aparecem."""
    marcas = list(_EVENTO.finditer(historico))
    saida = []
    for i, m in enumerate(marcas):
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(historico)
        saida.append((m.lastgroup or "", historico[m.start():fim].strip()))
    return saida


def vigencia(status: str, historico: str) -> tuple[date, date | None, bool, str]:
    """(inicio, fim, revogado, cabecalho) a partir do status e do historico."""
    inicio, fim, revogado, cabecalho = PISO, None, False, ""
    original = alterada = cancelada = None
    for tipo, trecho in eventos(historico):
        if tipo == "original" and original is None:
            original = trecho
        elif tipo == "alterada":
            alterada = trecho          # a ultima alteracao e a redacao exibida
        elif tipo == "cancelada":
            cancelada = trecho

    if alterada and (d := ultima_data(alterada)):
        inicio, cabecalho = d, alterada
    elif original and (d := ultima_data(original)):
        inicio = d

    if status == "cancelada" or cancelada:
        d = ultima_data(cancelada) if cancelada else None
        if d:
            fim, cabecalho = d - timedelta(days=1), cancelada or ""
        else:
            revogado = True
    return inicio, fim, revogado, cabecalho


# --- pagina -> verbete ------------------------------------------------------

_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)
_NUMERO = re.compile(r"S[UÚ]MULA\s+N[.º°o\s]*(\d+)", re.I)
_STATUS = re.compile(r"\((cancelada|alterada|revisada)\)", re.I)
_CORTE = re.compile(r"^(Precedentes?|Hist[oó]rico)\b", re.I)
_HISTORICO = re.compile(r"^Hist[oó]rico\b", re.I)


def verbete(pagina: str) -> Verbete | None:
    h1 = _H1.search(pagina)
    if not h1:
        return None
    cabeca = " ".join(_linhas(h1.group(1)))
    n = _NUMERO.search(cabeca)
    if not n:
        return None
    numero = int(n.group(1))
    st = _STATUS.search(cabeca)
    status = st.group(1).lower() if st else "vigente"

    desc = _bloco(pagina, 'class="documentDescription')
    titulo = " ".join(_linhas(desc)) if desc else ""

    corpo = _bloco(pagina, 'id="parent-fieldname-text"')
    if corpo is None:
        return None
    linhas = _linhas(corpo)

    texto: list[str] = []
    historico: list[str] = []
    em_historico = fechado = False
    for l in linhas:
        if _HISTORICO.match(l):
            em_historico = True
        elif em_historico:
            historico.append(l)
        elif _CORTE.match(l):
            # "Precedentes:" encerra o verbete. O que vem dali ate "Historico" e
            # lista de acordaos: nao e texto de sumula nem data de vigencia.
            fechado = True
        elif not fechado:
            texto.append(l)

    hist = " ".join(historico)
    inicio, fim, revogado, cabecalho = vigencia(status, hist)
    return Verbete(
        numero=numero,
        titulo=titulo,
        status=status,
        texto=" ".join(texto).strip(),
        historico=hist,
        vigencia_inicio=inicio,
        vigencia_fim=fim,
        revogado=revogado,
        cabecalho=cabecalho,
    )


def verbetes(paginas: dict[str, bytes]) -> list[Verbete]:
    """Um verbete por pagina de sumula, em ordem de numero. Sem texto, fora."""
    saida = []
    for nome, bruto in paginas.items():
        if nome.startswith("_"):
            continue
        v = verbete(bruto.decode("utf-8", "replace"))
        if v is not None and v.texto:
            saida.append(v)
    return sorted(saida, key=lambda v: v.numero)


def lacunas(achados: list[Verbete]) -> list[int]:
    numeros = {v.numero for v in achados}
    if not numeros:
        return []
    return [n for n in range(1, max(numeros) + 1) if n not in numeros]
