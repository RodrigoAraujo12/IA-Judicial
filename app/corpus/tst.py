"""Ingestao das Sumulas e Orientacoes Jurisprudenciais do TST.

A fonte e o **Livro de Sumulas, OJs e PNs**, a publicacao consolidada do proprio
Tribunal. Foi escolhida contra duas alternativas:

**Nao a pagina /sumulas do site.** E um SPA em React: o HTML servido tem 1 KB e um
`<div id="root">` vazio. Nao ha o que raspar sem um navegador, e por um dado que o
Tribunal ja publica inteiro num arquivo so.

**RTF, nao PDF.** O Livro sai nos dois formatos. O PDF tem 3,2 MB contra 23 MB do
RTF, mas exigiria uma biblioteca de extracao e devolveria texto por coordenada -
e coordenada nao distingue titulo de corpo. O RTF traz a quebra de paragrafo
explicita, que e justamente o que separa uma sumula da seguinte, e le-se com o
`re` da biblioteca padrao. Zero dependencia nova.

**O que entra.** Sumulas, OJs da SBDI-I, da SBDI-I Transitoria e da SBDI-II. Fica
de fora o que so serve a dissidio coletivo - SDC e Precedentes Normativos -, que
nao e o uso deste sistema. O Livro traz tudo isso na mesma estrutura, entao
incluir depois e acrescentar uma linha em COLECOES.

**Uma redacao por verbete, nao o historico.** O Livro transcreve a redacao atual e
depois um bloco "Historico:" que as vezes traz a anterior e as vezes so cita a
resolucao que a mudou. Reconstruir a sucessao a partir disso seria adivinhar, e o
esquema aceita o historico depois sem migracao - a chave ja e (urn,
vigencia_inicio).

**Sumula cancelada nao vira `revogado`, vira JANELA.** Este e o ponto que faz o
trabalho valer. A Sumula 437 foi cancelada por perda de eficacia a partir de
11.11.2017, e o Livro diz isso na propria linha do titulo. Grava-la com
`vigencia_fim = 10.11.2017` e o que permite a um caso de 2016 continuar
encontrando-a - que e a mesma razao pela qual a CLT tem vigencia por dispositivo.
Marcar `revogado` seria jogar fora a informacao que a fonte deu de graca. So cai
em `revogado` o cancelamento sem data legivel: saiu, nao se sabe quando, e servir
como vigente e o unico erro inaceitavel.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

# A URL e estavel; o "12" e a edicao. Quando o TST publicar a 13, o sha256 muda e
# o registro de fonte acusa - que e o mecanismo, nao um efeito colateral.
URL_LIVRO = "https://www.tst.jus.br/documents/d/guest/livrointernet-12-rtf"
ARQUIVO = "tst-livro.rtf"

# Prefixo do marcador no Livro -> obra, na forma que `refs.py` ja resolve.
COLECOES = {
    "SUM": "sumula-tst",
    "OJ-SDI1T": "oj-sdi1-trans-tst",
    "OJ-SDI1": "oj-sdi1-tst",
    "OJ-SDI2": "oj-sdi2-tst",
}

ROTULOS = {
    "sumula-tst": "Sumula {n} do TST",
    "oj-sdi1-tst": "OJ {n} da SBDI-I do TST",
    "oj-sdi1-trans-tst": "OJ Transitoria {n} da SBDI-I do TST",
    "oj-sdi2-tst": "OJ {n} da SBDI-II do TST",
}

# Onde o corpo acaba e comeca o indice tematico. Dali para baixo cada linha e uma
# REMISSAO - "SUM-437, I<tab>(cancelada)" -, com a mesma cara de um verbete e sem
# texto nenhum. Sem este corte, o parser ingere 4.700 fantasmas.
#
# O `$` no fim nao e enfeite. O sumario da frente tem a linha "Indice Remissivo
# H - 1 - 193", com a paginacao no fim, e ela casava tao bem quanto o cabecalho
# de verdade - cortando o Livro na linha 47 e produzindo ZERO verbetes. O
# cabecalho real esta sozinho na linha; a entrada do sumario, nunca.
FIM_DO_CORPO = re.compile(r"^[IÍ]NDICE\s+REMISSIVO\s*$", re.I)

# Piso de vigencia para verbete cuja resolucao a fonte nao data. Nao e uma
# afirmacao sobre quando a sumula nasceu: e o "antes de qualquer caso que este
# sistema vai ver", escolhido para nao excluir o verbete de nenhuma consulta. A
# Sumula 1 do TST e de 1963.
PISO = date(1963, 1, 1)


@dataclass
class Verbete:
    obra: str
    numero: str
    titulo: str
    texto: str
    cabecalho: str
    vigencia_inicio: date
    vigencia_fim: date | None
    revogado: bool

    @property
    def urn(self) -> str:
        return f"{self.obra}/{self.numero}"

    @property
    def rotulo(self) -> str:
        return ROTULOS[self.obra].format(n=self.numero)


# --- RTF --------------------------------------------------------------------

_DESTINO_IGNORADO = re.compile(r"\{\\\*")
_CONTROLE = re.compile(r"\\([a-zA-Z]+)(-?\d+)?[ ]?")
_HEX = re.compile(r"\\'([0-9a-fA-F]{2})")
_LITERAL = re.compile(r"\\([{}\\])")
# Grupos que sao metadado do documento, nao texto: tabela de fontes, estilos,
# cabecalho e rodape de pagina. Sem descarta-los, "Pagina 12 de 579" entra no
# meio do texto das sumulas.
_GRUPOS_META = {
    "fonttbl", "colortbl", "stylesheet", "info", "listtable",
    "listoverridetable", "rsidtbl", "pict", "header", "footer",
}


def rtf_texto(bruto: bytes) -> str:
    """Extrai o texto de um RTF. So o que este documento precisa, nada alem.

    Um parser de RTF completo e um projeto; este resolve o subconjunto que o
    Livro usa - grupos, palavras de controle, escapes hex em cp1252 e `\\uN` - e
    ignora o resto da especificacao.

    O detalhe que custou caro: **CRLF dentro do arquivo RTF nao e quebra de
    linha do texto.** E dobra de linha do proprio fonte, e o RTF a trata como
    espaco. Emiti-la como conteudo partia palavra ao meio no meio de uma sumula,
    e o estrago passava despercebido porque o texto continuava legivel.
    """
    s = bruto.decode("cp1252", "replace")
    saida: list[str] = []
    i, n = 0, len(s)
    profundidade = 0
    pular_ate = 0

    while i < n:
        c = s[i]
        if c == "{":
            profundidade += 1
            if not pular_ate and _DESTINO_IGNORADO.match(s, i):
                pular_ate = profundidade
            i += 1
            continue
        if c == "}":
            if pular_ate and profundidade == pular_ate:
                pular_ate = 0
            profundidade -= 1
            i += 1
            continue
        if c == "\r" or c == "\n":
            i += 1
            continue
        if c != "\\":
            if not pular_ate:
                saida.append(c)
            i += 1
            continue

        if m := _LITERAL.match(s, i):
            if not pular_ate:
                saida.append(m.group(1))
            i = m.end()
            continue
        if m := _HEX.match(s, i):
            if not pular_ate:
                saida.append(bytes([int(m.group(1), 16)]).decode("cp1252", "replace"))
            i = m.end()
            continue
        if m := _CONTROLE.match(s, i):
            palavra, arg = m.group(1), m.group(2)
            if not pular_ate:
                if palavra in ("par", "line", "sect", "row"):
                    saida.append("\n")
                elif palavra in ("tab", "cell"):
                    saida.append("\t")
                elif palavra == "u" and arg:
                    saida.append(chr(int(arg) % 65536))
                elif palavra in _GRUPOS_META:
                    pular_ate = profundidade
            i = m.end()
            continue
        i += 1

    return "".join(saida)


# --- estrutura do Livro -----------------------------------------------------

# "SUM-437", "OJ-SDI1-123", "OJ-SDI1-T-25". A ordem em COLECOES importa: o
# alternador tenta OJ-SDI1T antes de OJ-SDI1. O Livro escreve a Transitoria SEM
# hifen antes do T, e escrever "OJ-SDI1-T" aqui nao produzia colisao: produzia
# SILENCIO - as 79 OJs transitorias simplesmente nao casavam nada e sumiam.
_MARCADOR = re.compile(
    r"^(" + "|".join(re.escape(p) for p in COLECOES) + r")-(\d+)(?:\s*,\s*[IVX]+)?\s*(.*)$"
)

# "(cancelada por perda de eficacia a partir de 11.11.2017, pela Lei 13.467/2017)"
_CANCELADA_EM = re.compile(
    r"\(\s*cancelad[ao]\b[^)]*?\ba partir de\s+(\d{1,2})[./](\d{1,2})[./](\d{4})", re.I
)
_CANCELADA = re.compile(r"\(\s*(?:cancelad[ao]|convertid[ao] em)\b", re.I)

# "- Res. 185/2012, DEJT divulgado em 25, 26 e 27.09.2012". A data que vale e a
# PRIMEIRA completa da linha: as anteriores sao dias de divulgacao sem mes.
_DATA = re.compile(r"(\d{1,2})[./](\d{1,2})[./](\d{4})")

# O texto do verbete acaba onde comeca a nota de historico.
_HISTORICO = re.compile(r"^Hist[oó]rico\s*:?\s*$", re.I)


def _data(texto: str) -> date | None:
    if m := _DATA.search(texto):
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def _titulo(resto: str) -> str:
    """O titulo do verbete, sem o status nem a resolucao que o acompanham."""
    corte = re.split(r"\s*\(|\s+-\s+Res\.|\s+-\s+DJ|\s+-\s+DEJT", resto, maxsplit=1)[0]
    return corte.strip(" .-\t")


def verbetes(bruto: bytes) -> list[Verbete]:
    """Le o Livro e devolve um verbete por sumula/OJ, ja com a janela de vigencia."""
    linhas = [l.strip() for l in rtf_texto(bruto).split("\n")]
    linhas = [l for l in linhas if l]

    # Corta o indice remissivo antes de qualquer coisa.
    for i, linha in enumerate(linhas):
        if FIM_DO_CORPO.match(linha):
            linhas = linhas[:i]
            break

    achados: list[Verbete] = []
    atual: Verbete | None = None
    corpo: list[str] = []
    em_historico = False

    def fechar() -> None:
        if atual is not None:
            atual.texto = " ".join(corpo).strip()
            if atual.texto:
                achados.append(atual)

    for linha in linhas:
        m = _MARCADOR.match(linha.replace("\t", " "))
        if m:
            fechar()
            prefixo, numero, resto = m.group(1), m.group(2), m.group(3)
            obra = COLECOES[prefixo]

            # A MESMA data significa coisas opostas conforme o status, e ler so a
            # data e errar metade. Em "(nova redacao) - Res. 185/2012" ela abre a
            # redacao vigente; em "(cancelada) - Res. 121/2003" ela a ENCERRA.
            # Gravar as duas como inicio poe a sumula nascendo no dia em que
            # morreu - e, pior, com vigencia aberta a partir dali.
            data = _data(resto)
            inicio, fim, revogado = PISO, None, False

            if quando := _CANCELADA_EM.search(resto):
                # "cancelada por perda de eficacia a partir de 11.11.2017": a
                # fonte da o dia exato, e ele vira janela.
                encerrou = date(int(quando.group(3)), int(quando.group(2)), int(quando.group(1)))
                fim = date.fromordinal(encerrou.toordinal() - 1)
            elif _CANCELADA.search(resto):
                if data:
                    # Cancelamento datado pela resolucao que o publicou. O inicio
                    # fica no piso porque a fonte nao diz quando a sumula comecou
                    # - e um caso de 2002 continua encontrando a Sumula 2.
                    fim = date.fromordinal(data.toordinal() - 1)
                else:
                    # Saiu, nao se sabe quando. Servir como vigente e o unico erro
                    # inaceitavel, entao ela fica fora de toda consulta por data.
                    revogado = True
            elif data:
                # Verbete em vigor: a resolucao data a redacao que esta no Livro.
                # E um "pelo menos desde", nao a certidao de nascimento: para
                # "(mantida)" o texto costuma ser mais velho que a resolucao. Fica
                # o que a fonte afirma - inventar data anterior seria pior.
                inicio = data

            atual = Verbete(
                obra=obra,
                numero=numero,
                titulo=_titulo(resto),
                texto="",
                cabecalho=resto.strip(),
                vigencia_inicio=inicio,
                vigencia_fim=fim,
                revogado=revogado,
            )
            corpo, em_historico = [], False
            continue

        if atual is None:
            continue
        if _HISTORICO.match(linha):
            em_historico = True
            continue
        if not em_historico:
            corpo.append(linha)

    fechar()
    return achados


def lacunas(achados: list[Verbete]) -> dict[str, list[int]]:
    """Numeros ausentes dentro da faixa de cada colecao.

    O Livro nao imprime verbete cancelado ha muito tempo, entao lacuna nao e
    necessariamente falha de parsing. Serve de sinal: uma colecao que perdeu
    metade dos numeros perdeu por bug, nao por cancelamento.
    """
    por_obra: dict[str, set[int]] = {}
    for v in achados:
        por_obra.setdefault(v.obra, set()).add(int(v.numero))
    return {
        obra: [n for n in range(min(ns), max(ns) + 1) if n not in ns]
        for obra, ns in por_obra.items()
        if ns
    }
