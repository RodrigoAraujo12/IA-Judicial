"""Interpretacao das referencias do catalogo.

Cada `fundamento` do catalogo carrega uma `ref` escrita para humano ler:
"art. 71, par. 4o", "arts. 223-A a 223-G", "Sumula 437". Este modulo converte
essa string na lista de dispositivos que ela designa.

E a Via 0 da recuperacao: ligar pedido a norma nao e busca semantica, e join.
Quando o relatorio cita o art. 71 par. 4o, o texto exibido tem de ser o do art. 71
par. 4o - nao o que um vetor achou parecido.

O identificador canonico e uma URN legivel:

    clt/art-71/par-4          art. 71, par. 4o da CLT
    clt/art-456/par-unico     art. 456, paragrafo unico
    clt/art-791-A             art. 791-A (artigo com sufixo de letra)
    cf/art-7/inc-XXIX         art. 7o, XXIX da Constituicao
    adct/art-10/inc-II/al-b   ADCT, art. 10, II, 'b'
    sumula-tst/437            Sumula 437 do TST
    oj-sdi1-tst/355           OJ 355 da SDI-1
    lei-8213-1991/art-118     art. 118 da Lei 8.213/91

Legivel de proposito: essa string aparece em log, em teste e na peca. URN opaca
economiza bytes e custa a conferencia visual, que aqui vale mais.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Ordinal em ASCII, como o catalogo escreve: "2o", "9o", as vezes "2o" com simbolo.
_ORDINAL = re.compile(r"(?<=\d)[oº°]\b")
_ROMANO = re.compile(r"^[IVXLC]+$")
_ARTIGO = re.compile(r"^\d+(?:-[A-Za-z])?$")
# Marcador interno de faixa, escolhido por nao ocorrer em texto de lei.
_FAIXA = "→"


@dataclass
class Referencia:
    """Uma `ref` do catalogo, depois de interpretada."""

    tipo: str
    ref: str
    obra: str | None = None
    urns: list[str] = field(default_factory=list)
    # Artigo citado "e paragrafos": a expansao so acontece contra o corpus, que
    # e quem sabe quantos paragrafos o artigo tem.
    inclui_paragrafos: bool = False
    # Divergencia entre o `tipo` declarado e o que a `ref` de fato designa.
    observacao: str | None = None

    @property
    def resolvido(self) -> bool:
        return bool(self.urns)


# --- obras ------------------------------------------------------------------


def _ano_quatro_digitos(ano: str) -> str:
    """"90" -> "1990"; "2011" -> "2011".

    Nao ha norma trabalhista citavel anterior a 1930, entao o corte em 30 e seguro:
    o catalogo so usa dois digitos para leis do seculo passado.
    """
    if len(ano) == 4:
        return ano
    n = int(ano)
    return str(1900 + n) if n >= 30 else str(2000 + n)


def _obra_de_lei(ref: str) -> tuple[str | None, str, str | None]:
    """Identifica a obra numa ref de tipo `lei`. Devolve (obra, resto, observacao)."""
    if re.match(r"^c[oó]digo civil", ref, re.I):
        resto = re.sub(r"^c[oó]digo civil\s*,?\s*", "", ref, flags=re.I)
        return "cc", resto, None

    m = re.match(r"^lei\s+n?o?\.?\s*([\d.]+)\s*/\s*(\d{2,4})\s*,?\s*(.*)$", ref, re.I)
    if m:
        numero = m.group(1).replace(".", "")
        return f"lei-{numero}-{_ano_quatro_digitos(m.group(2))}", m.group(3), None

    m = re.match(r"^in\s+(\d+)\s*/\s*(\d{2,4})\s+do\s+tst\s*,?\s*(.*)$", ref, re.I)
    if m:
        obra = f"in-tst-{m.group(1)}-{_ano_quatro_digitos(m.group(2))}"
        nota = "instrucao normativa do TST, nao lei - considerar um `tipo` proprio"
        return obra, m.group(3), nota

    return None, ref, None


# --- dispositivos -----------------------------------------------------------


def _limpar(token: str) -> str:
    return _ORDINAL.sub("", token.strip().strip(".,;\"'")).strip()


def _expandir_faixa(inicio: str, fim: str) -> list[str] | None:
    """"129" a "147" -> 19 artigos. "223-A" a "223-G" -> 7 artigos."""
    if inicio.isdigit() and fim.isdigit():
        a, b = int(inicio), int(fim)
        return [str(n) for n in range(a, b + 1)] if a <= b else None

    ma = re.match(r"^(\d+)-([A-Za-z])$", inicio)
    mb = re.match(r"^(\d+)-([A-Za-z])$", fim)
    if ma and mb and ma.group(1) == mb.group(1):
        base, ini, term = ma.group(1), ma.group(2).upper(), mb.group(2).upper()
        if ini <= term:
            return [f"{base}-{chr(c)}" for c in range(ord(ini), ord(term) + 1)]
    return None


def _subdivisao(token: str) -> tuple[str, str] | None:
    """Classifica um token em (especie, fragmento de URN)."""
    t = _limpar(token)
    if not t:
        return None

    if re.match(r"^par[aá]grafo\s+[uú]nico$", t, re.I):
        return "par", "par-unico"
    m = re.match(r"^(?:par\.|par[aá]grafo|§)\s*(\d+)$", t, re.I)
    if m:
        return "par", f"par-{m.group(1)}"
    if _ROMANO.match(t):
        return "inc", f"inc-{t}"
    m = re.match(r"^(?:al[ií]nea\s+)?([a-z])$", t, re.I)
    if m:
        return "al", f"al-{m.group(1).lower()}"
    return None


def _artigos_e_subdivisoes(texto: str) -> tuple[list[str], list[tuple[str, str]], bool]:
    """Separa a lista de artigos das subdivisoes que os qualificam.

    A virgula e ambigua no catalogo: em "arts. 186, 927 e 950" ela separa artigos;
    em "art. 71, par. 4o" ela introduz uma subdivisao. Desempata pelo formato do
    token - numero cru e artigo, o resto e subdivisao - e pela ordem: depois que
    uma subdivisao aparece, numero solto qualifica ela, nao abre artigo novo.
    """
    inclui_paragrafos = False
    if re.search(r"\be\s+par[aá]grafos\b", texto, re.I):
        inclui_paragrafos = True
        texto = re.sub(r"\s*\be\s+par[aá]grafos\b", "", texto, flags=re.I)

    texto = re.sub(r"^arts?\.\s*", "", texto.strip(), flags=re.I)
    # Marca a faixa antes de fatiar, para "129 a 147" nao virar dois itens soltos.
    texto = re.sub(r"\s+a\s+(?=\d)", f" {_FAIXA} ", texto)
    tokens = [t for t in re.split(r",|\se\s", texto, flags=re.I) if t.strip()]

    artigos: list[str] = []
    subdivisoes: list[tuple[str, str]] = []

    for token in tokens:
        if _FAIXA in token:
            inicio, fim = (_limpar(p) for p in token.split(_FAIXA, 1))
            faixa = _expandir_faixa(inicio, fim)
            if faixa:
                artigos.extend(faixa)
            continue

        limpo = _limpar(token)
        if _ARTIGO.match(limpo) and not subdivisoes:
            artigos.append(limpo)
            continue

        sub = _subdivisao(limpo)
        if sub:
            subdivisoes.append(sub)

    return artigos, subdivisoes, inclui_paragrafos


def _montar(obra: str, artigos: list[str], subdivisoes: list[tuple[str, str]]) -> list[str]:
    """Combina artigos e subdivisoes em URNs.

    Subdivisoes da MESMA especie sao alternativas ("par. 3o e par. 4o" -> duas
    URNs); de especies DIFERENTES encadeiam ("II, 'b'" -> inc-II/al-b).
    """
    if not artigos:
        return [obra]

    caminhos: list[list[str]] = [[]]
    for especie in ("par", "inc", "al"):
        do_tipo = [frag for esp, frag in subdivisoes if esp == especie]
        if not do_tipo:
            continue
        caminhos = [caminho + [frag] for caminho in caminhos for frag in do_tipo]

    return [
        "/".join([obra, f"art-{artigo}", *caminho])
        for artigo in artigos
        for caminho in caminhos
    ]


# --- entrada ----------------------------------------------------------------


def interpretar(tipo: str, ref: str) -> Referencia:
    """Converte (tipo, ref) do catalogo na lista de dispositivos designados."""
    r = Referencia(tipo=tipo, ref=ref)
    texto = ref.strip()

    match tipo:
        case "sumula_tst":
            m = re.search(r"(\d+)", texto)
            if m:
                r.obra, r.urns = "sumula-tst", [f"sumula-tst/{m.group(1)}"]
            return r

        case "oj_tst":
            m = re.search(r"oj\s+(\d+)\s+da\s+sdi-?(\d)", texto, re.I)
            if m:
                r.obra = f"oj-sdi{m.group(2)}-tst"
                r.urns = [f"{r.obra}/{m.group(1)}"]
            return r

        case "sv_stf":
            m = re.search(r"(\d+)", texto)
            if m:
                r.obra, r.urns = "sv-stf", [f"sv-stf/{m.group(1)}"]
            return r

        case "tema_stf":
            m = re.search(r"tema\s+(\d+)", texto, re.I)
            if m:
                r.obra, r.urns = "tema-stf", [f"tema-stf/{m.group(1)}"]
                return r
            m = re.search(r"adi\s+(\d+)", texto, re.I)
            if m:
                r.obra, r.urns = "adi-stf", [f"adi-stf/{m.group(1)}"]
                r.observacao = (
                    "acao direta de inconstitucionalidade, nao tema de repercussao geral"
                )
            return r

        case "nr":
            m = re.search(r"nr-?\s*(\d+)", texto, re.I)
            if m:
                obra = f"nr-{int(m.group(1)):02d}"
                r.obra, r.urns = obra, [obra]
            return r

        case "clt":
            r.obra = "clt"

        case "cf":
            if re.match(r"^adct\b", texto, re.I):
                r.obra = "adct"
                texto = re.sub(r"^adct\s*,?\s*", "", texto, flags=re.I)
            else:
                r.obra = "cf"

        case "lei":
            r.obra, texto, r.observacao = _obra_de_lei(texto)
            if r.obra is None:
                return r

        case _:
            return r

    artigos, subdivisoes, r.inclui_paragrafos = _artigos_e_subdivisoes(texto)
    r.urns = _montar(r.obra, artigos, subdivisoes)
    return r
