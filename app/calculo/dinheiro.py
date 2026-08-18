"""Aritmetica monetaria.

Decimal, nunca float. Calculo trabalhista soma centenas de parcelas ao longo de
anos; erro de arredondamento binario aparece no total e destroi a credibilidade
da memoria de calculo na primeira conferencia da parte contraria.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

CENTAVO = Decimal("0.01")
ZERO = Decimal("0.00")


def d(valor: Any) -> Decimal:
    """Converte para Decimal sem passar por float."""
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, float):
        return Decimal(str(valor))
    if valor is None or valor == "":
        return ZERO
    return Decimal(str(valor))


def brl(valor: Any) -> Decimal:
    """Arredonda para centavos, meio-para-cima (convencao brasileira)."""
    return d(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def pct(valor: Any, percentual: Any) -> Decimal:
    return brl(d(valor) * d(percentual) / Decimal(100))


def fmt(valor: Any) -> str:
    """1234.5 -> '1.234,50'"""
    v = brl(valor)
    negativo = v < 0
    inteiro, _, centavos = f"{abs(v):.2f}".partition(".")
    grupos = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    grupos.insert(0, inteiro)
    return ("-" if negativo else "") + ".".join(grupos) + "," + centavos
