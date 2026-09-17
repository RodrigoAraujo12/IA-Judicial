"""Competencia territorial: de onde o servico foi prestado ao TRT que julga.

A advogada NAO escolhe o tribunal. Ela responde onde o servico era prestado, e o
sistema deriva o TRT - porque e isso que o art. 651 da CLT manda olhar, e nao o
foro da contratacao nem o da sede da empresa. Deixar escolher a mao abriria a
porta exatamente para o erro que o artigo existe para evitar. O que ela ve e o
resultado, ao lado da resposta, para conferir.

O mapa e por UF, com uma excecao. Vinte e cinco unidades tem um tribunal so, ou
dividem um com a vizinha. Sao Paulo tem dois: a capital, a Grande Sao Paulo e a
Baixada Santista sao a 2a Regiao; o interior e a 15a. So ali o sistema precisa de
uma segunda resposta, e so ali ela e perguntada.

O mesmo modulo diz que obras do corpus valem para um TRT. A convencao e o sufixo
`-trtNN` no nome da obra: `sumula-trt13`, `oj-trt13`. Obra sem esse sufixo e
nacional e vale para todo caso. Isso e o que mantem uma sumula da 6a Regiao fora
de um caso da Paraiba - regra juridica, e tambem o que preserva o ranking, que
degrada quando o lote de candidatos cresce com verbete que nao se aplica.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

# UF -> numero do TRT. Sao Paulo esta fora de proposito: depende do municipio.
TRT_POR_UF: dict[str, int] = {
    "RJ": 1,
    "MG": 3,
    "RS": 4,
    "BA": 5,
    "PE": 6,
    "CE": 7,
    "PA": 8, "AP": 8,
    "PR": 9,
    "DF": 10, "TO": 10,
    "AM": 11, "RR": 11,
    "SC": 12,
    "PB": 13,
    "RO": 14, "AC": 14,
    "MA": 16,
    "ES": 17,
    "GO": 18,
    "AL": 19,
    "SE": 20,
    "RN": 21,
    "PI": 22,
    "MT": 23,
    "MS": 24,
}

# As duas metades de Sao Paulo, pelos valores da pergunta `regiao_sp`.
TRT_SP: dict[str, int] = {
    "metropolitana": 2,   # capital, Grande Sao Paulo e Baixada Santista
    "interior": 15,
}

# Quem cada tribunal cobre, para o rotulo. A UF sozinha nao basta: "TRT da 8a
# Regiao" sem "(PA e AP)" faz a advogada do Amapa achar que caiu no lugar errado.
ABRANGENCIA: dict[int, str] = {
    1: "RJ", 2: "SP, capital e regiao metropolitana", 3: "MG", 4: "RS", 5: "BA",
    6: "PE", 7: "CE", 8: "PA e AP", 9: "PR", 10: "DF e TO", 11: "AM e RR",
    12: "SC", 13: "PB", 14: "RO e AC", 15: "SP, interior", 16: "MA", 17: "ES",
    18: "GO", 19: "AL", 20: "SE", 21: "RN", 22: "PI", 23: "MT", 24: "MS",
}

UFS: list[str] = sorted(TRT_POR_UF) + ["SP"]
UFS.sort()

_SUFIXO_REGIONAL = re.compile(r"-trt(\d{1,2})$")


def trt_do_caso(respostas: dict[str, Any]) -> int | None:
    """O TRT competente para o caso, ou None quando as respostas nao bastam.

    None e resposta legitima, no mesmo espirito do terceiro estado do motor: sem
    a UF nao se deriva tribunal, e chutar o da advogada seria errar em silencio
    no caso em que ela atende alguem que trabalhou noutro estado.
    """
    uf = str(respostas.get("uf_prestacao") or "").strip().upper()
    if not uf:
        return None
    if uf == "SP":
        return TRT_SP.get(str(respostas.get("regiao_sp") or "").strip())
    return TRT_POR_UF.get(uf)


def rotulo(trt: int | None) -> str | None:
    if trt is None:
        return None
    return f"TRT da {trt}ª Região ({ABRANGENCIA[trt]})"


def trt_da_obra(obra: str) -> int | None:
    """`sumula-trt13` -> 13. Obra nacional -> None."""
    m = _SUFIXO_REGIONAL.search(obra)
    return int(m.group(1)) if m else None


def obras_para(todas: Iterable[str], trt: int | None) -> set[str]:
    """As obras que um caso daquele TRT pode consultar: nacionais mais as dele.

    Com `trt=None` sobram so as nacionais. Nao existe "todas as regionais" de
    proposito: consulta sem tribunal e consulta sem caso, e verbete regional fora
    do seu tribunal nao e resposta para ninguem.
    """
    return {o for o in todas if (t := trt_da_obra(o)) is None or t == trt}


def trts_no_corpus(todas: Iterable[str]) -> list[int]:
    """Quais tribunais regionais ja tem obra ingerida."""
    return sorted({t for o in todas if (t := trt_da_obra(o)) is not None})
