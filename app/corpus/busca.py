"""Recuperacao no corpus.

Duas vias funcionam hoje; a terceira entra com o BGE-M3.

**Via 0 - lookup.** `clt/art-71/par-4` mais uma data devolve o dispositivo. Nao e
busca, e join: precisao total, sem modelo no caminho. Cobre o uso mais frequente
do escritorio, que e conferir a norma que o relatorio ja citou.

**Via 1 - lexical (BM25 via FTS5).** Consulta juridica e cheia de token exato:
"Sumula 437", "art. 384", "intrajornada". Vetor denso troca numero; BM25 nao.

**Via 2 - densa (BGE-M3).** Para a pergunta em linguagem de cliente, onde nenhuma
palavra da consulta aparece no texto da lei. Ainda nao implementada.

Toda consulta leva uma DATA. Nao ha busca "no corpus" em abstrato: ha busca no
corpus como ele estava quando o fato aconteceu. O default e hoje por conveniencia
de teste, nunca por conveniencia de caso.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import date

from app.corpus import banco
from app.corpus.refs import interpretar


@dataclass
class Achado:
    urn: str
    rotulo: str
    texto: str
    obra: str
    via: str
    score: float
    vigencia_inicio: str
    vigencia_fim: str | None
    alterado_por: str | None


def _achado(linha: sqlite3.Row, via: str, score: float) -> Achado:
    return Achado(
        urn=linha["urn"],
        rotulo=linha["rotulo"],
        texto=linha["texto"],
        obra=linha["obra"],
        via=via,
        score=score,
        vigencia_inicio=linha["vigencia_inicio"],
        vigencia_fim=linha["vigencia_fim"],
        alterado_por=linha["alterado_por"],
    )


def por_referencia(
    con: sqlite3.Connection, tipo: str, ref: str, quando: date | None = None
) -> list[Achado]:
    """Via 0. Recebe a `ref` como o catalogo a escreve e devolve os dispositivos."""
    r = interpretar(tipo, ref)
    achados = []
    for urn in r.urns:
        linha = banco.vigente_em(con, urn, quando)
        if linha is not None:
            achados.append(_achado(linha, "referencia", 1.0))
    return achados


# FTS5 trata varios caracteres como sintaxe. Consulta digitada por advogado tem
# ponto, virgula, parenteses e "§" o tempo todo - sem limpar, a busca explode em
# erro de sintaxe no meio do atendimento.
_RUIDO = re.compile(r'[^\w\sÀ-ÿ]', re.UNICODE)


def _consulta_fts(texto: str) -> str:
    termos = [t for t in _RUIDO.sub(" ", texto).split() if len(t) > 1]
    return " OR ".join(f'"{t}"' for t in termos)


def lexical(
    con: sqlite3.Connection, consulta: str, quando: date | None = None, limite: int = 10
) -> list[Achado]:
    """Via 1. BM25 sobre `texto_indexado`, ja filtrado por vigencia."""
    expressao = _consulta_fts(consulta)
    if not expressao:
        return []

    ref = (quando or date.today()).isoformat()
    linhas = con.execute(
        """SELECT d.*, bm25(dispositivos_fts, 3.0, 1.0) AS score
           FROM dispositivos_fts
           JOIN dispositivos d ON d.id = dispositivos_fts.rowid
           WHERE dispositivos_fts MATCH ?
             AND d.revogado = 0
             AND d.vigencia_inicio <= ?
             AND (d.vigencia_fim IS NULL OR d.vigencia_fim >= ?)
           ORDER BY score
           LIMIT ?""",
        (expressao, ref, ref, limite),
    ).fetchall()
    # bm25() do SQLite e tanto menor quanto melhor; inverte para o score subir.
    return [_achado(l, "lexical", -l["score"]) for l in linhas]


# Consulta que JA e uma referencia: "art. 384", "Sumula 437", "art. 71 par. 4o".
# Sem esse desvio ela cai no BM25, onde o token "art" casa com o corpus inteiro e
# o resultado e ruido - foi o que aconteceu no primeiro teste com "art. 384".
_E_REFERENCIA = re.compile(
    r"^\s*(?:arts?\.?\s*\d|s[uú]mula\s*(?:vinculante\s*)?\d|oj\s*\d|nr-?\s*\d)",
    re.I,
)


def _tipo_provavel(consulta: str) -> str:
    baixa = consulta.lower()
    if baixa.lstrip().startswith("s") and "vinculante" in baixa:
        return "sv_stf"
    if "sumula" in baixa or "súmula" in baixa:
        return "sumula_tst"
    if baixa.lstrip().startswith("oj"):
        return "oj_tst"
    if baixa.lstrip().startswith("nr"):
        return "nr"
    return "clt"


@dataclass
class Resultado:
    achados: list[Achado]
    via: str
    # Por que a resposta esta vazia, quando esta. "Nao achei" e "achei, mas foi
    # revogado" sao respostas opostas para quem redige uma peca, e um buscador que
    # devolve lista vazia nos dois casos empurra a diferenca para o advogado.
    aviso: str | None = None


# A matriz de vetores custa 23 MB e uma leitura do banco. Carrega uma vez por
# processo; o indice so muda por reingestao, que reinicia o servidor de todo jeito.
_matriz = None
_matriz_tentada = False


def _obter_matriz(con: sqlite3.Connection):
    global _matriz, _matriz_tentada
    if not _matriz_tentada:
        _matriz_tentada = True
        try:
            from app.corpus import vetores

            _matriz = vetores.carregar_matriz(con)
        except Exception:
            _matriz = None
    return _matriz


def densa(
    con: sqlite3.Connection, consulta: str, quando: date | None = None, limite: int = 10
) -> list[Achado]:
    """Via 2. Similaridade de cosseno sobre os vetores do BGE-M3.

    Devolve lista vazia quando o corpus ainda nao foi vetorizado - a busca degrada
    para lexical em vez de quebrar, que e o comportamento certo numa maquina onde
    o modelo nao coube.
    """
    matriz = _obter_matriz(con)
    if matriz is None:
        return []

    from app.corpus import vetores

    try:
        pares = vetores.buscar(con, matriz, consulta, quando, limite)
    except vetores.ModeloAusente:
        # A matriz veio do corpus.db, mas embutir a CONSULTA exige o modelo. Sao
        # duas faltas diferentes, e so a primeira estava tratada: quem recebe o
        # corpus.db pronto tem os vetores e nao tem os 2,2 GB, e cairia em erro
        # 500 a cada busca em linguagem corrente. Aqui a busca vira lexical, que
        # e o que a maquina dela consegue fazer.
        return []
    if not pares:
        return []

    por_id = {
        l["id"]: l
        for l in con.execute(
            f"SELECT * FROM dispositivos WHERE id IN ({','.join('?' * len(pares))})",
            [i for i, _ in pares],
        )
    }
    return [_achado(por_id[i], "densa", s) for i, s in pares if i in por_id]


def buscar(
    con: sqlite3.Connection, consulta: str, quando: date | None = None, limite: int = 10
) -> Resultado:
    """Ponto de entrada. Escolhe a via pela forma da consulta.

    Referencia vai para o lookup; pergunta em linguagem natural vai para as vias
    de busca. Quando a densa entrar, esta funcao passa a fundir as duas por RRF -
    a de referencia continua fora da fusao, porque ela nao e palpite ranqueado e
    sim resposta exata.
    """
    if _E_REFERENCIA.match(consulta):
        r = interpretar(_tipo_provavel(consulta), consulta)
        achados = [
            _achado(linha, "referencia", 1.0)
            for urn in r.urns
            if (linha := banco.vigente_em(con, urn, quando)) is not None
        ]
        if achados:
            return Resultado(achados[:limite], "referencia")

        # A referencia existe no corpus, mas nao naquela data. Cair no BM25 aqui
        # seria o pior comportamento possivel: a consulta "art. 384" devolveria
        # dez artigos que nada tem a ver, e o silencio sobre a revogacao passaria
        # por resultado. Melhor dizer que a norma saiu, e quando.
        for urn in r.urns:
            historico = banco.redacoes(con, urn)
            if historico:
                ultima = historico[-1]
                ate = ultima["vigencia_fim"] or "data que a fonte nao registra"
                por = ultima["alterado_por"] or "norma nao identificada na fonte"
                return Resultado(
                    [],
                    "referencia",
                    f"{ultima['rotulo']} nao estava em vigor em "
                    f"{(quando or date.today()).isoformat()}: vigorou ate {ate} ({por}).",
                )

        return Resultado([], "referencia", f"referencia nao encontrada no corpus: {consulta}")

    # As duas vias de busca correm sobre o mesmo filtro de vigencia e sao fundidas
    # por posicao. Cada uma erra de um jeito proprio: a lexical nao sabe que
    # "dispensa imotivada" e "despedida sem justa causa" sao a mesma coisa; a densa
    # troca numero de artigo. RRF aproveita o acerto de qualquer uma das duas sem
    # precisar que os scores sejam comparaveis - e nao sao.
    lex = lexical(con, consulta, quando, max(limite, 20))
    den = densa(con, consulta, quando, max(limite, 20))
    if not den:
        return Resultado(lex[:limite], "lexical")
    return Resultado(rrf([lex, den], limite=limite), "hibrida")


def rrf(listas: list[list[Achado]], k: int = 5, limite: int = 10) -> list[Achado]:
    """Reciprocal Rank Fusion.

    Funde rankings sem precisar que os scores sejam comparaveis entre si - e o
    ponto, porque BM25 e similaridade de cosseno vivem em escalas diferentes e
    normalizar uma na outra e chute. RRF so olha POSICAO.

    **Sobre o k.** Ele decide o quanto a primeira posicao vale mais que a decima.
    k grande achata a curva: com k=60, 1/(60+1) e 1/(60+10) quase empatam, e a
    fusao vira media de opiniao em vez de ordenacao. k pequeno mantem o topo
    ingreme, e quem acertou em primeiro leva a consulta.

    O 60 herdado da literatura foi medido e reprovado aqui. Ele vem de avaliacao
    TREC, onde se fundem dezenas de sistemas de qualidade parecida; aqui sao duas
    listas so, de forcas bem diferentes, sobre um corpus de 5.752 redacoes. Com
    k=60 a fusao chegava a ficar ABAIXO da via lexical sozinha no primeiro
    resultado - a densa arrastava para baixo respostas que o BM25 ja tinha posto
    em #1. Caso concreto: "abandono de emprego apos trinta dias de falta" tem a
    alinea 'i' do art. 482 em #1 no lexical, e a fusao a empurrava para #5,
    porque "trinta dias" puxava os incisos de ferias do art. 130.

    Medido em `analisar_rerank.py` sobre as 72 consultas de `avaliacao.py`:

        k=60 (antes)  acerto@1 47/72   acerto@5 63/72   MRR 0,760
        k=5  (agora)  acerto@1 53/72   acerto@5 65/72   MRR 0,808

    O intervalo k=1..20 e um plato: os numeros mal se mexem la dentro. A escolha
    do 5 nao e ajuste fino em cima do gabarito, e o meio de uma regiao estavel -
    o que importa e nao estar em 60.
    """
    pontos: dict[str, float] = {}
    melhor: dict[str, Achado] = {}
    for lista in listas:
        for posicao, achado in enumerate(lista):
            pontos[achado.urn] = pontos.get(achado.urn, 0.0) + 1.0 / (k + posicao + 1)
            melhor.setdefault(achado.urn, achado)

    ordenados = sorted(pontos.items(), key=lambda kv: kv[1], reverse=True)
    saida = []
    for urn, ponto in ordenados[:limite]:
        a = melhor[urn]
        saida.append(
            Achado(
                urn=a.urn, rotulo=a.rotulo, texto=a.texto, obra=a.obra,
                via="fusao", score=ponto, vigencia_inicio=a.vigencia_inicio,
                vigencia_fim=a.vigencia_fim, alterado_por=a.alterado_por,
            )
        )
    return saida
