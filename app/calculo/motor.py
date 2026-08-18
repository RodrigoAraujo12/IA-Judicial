"""Orquestrador do calculo.

A ordem de execucao e o ponto central: adicionais habituais precisam ser apurados
ANTES das horas extras, porque majoram a base (Sumula 264 do TST). Rodar na ordem
errada subestima o pedido inteiro - e e o erro que uma planilha comum comete.

Cascata:
    1. insalubridade x periculosidade  (nao acumulam - vence a mais benefica)
    2. adicional noturno               (sobre a base ja majorada)
    3. demais verbas                   (sobre a base com todos os adicionais)
    4. rescisorias, multas e estabilidades
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.calculo.dinheiro import ZERO, brl, d, fmt
from app.calculo.periodo import Periodo, periodo_apuracao
from app.calculo.verbas import COMPOEM_BASE, MODULOS, Contexto, Verba
from app.motor import Analise, data_ajuizamento
from app.schema import Catalogo

PARAMETROS = Path(__file__).parent / "parametros.yaml"


@lru_cache(maxsize=1)
def parametros() -> dict[str, Any]:
    with PARAMETROS.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class Calculo:
    disponivel: bool = False
    motivo: str = ""
    periodo: Periodo | None = None
    houve_corte_quinquenal: bool = False
    remuneracao: Decimal = ZERO
    verbas: list[Verba] = field(default_factory=list)
    pendentes: list[Verba] = field(default_factory=list)
    observacoes: list[str] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return brl(sum((v.total for v in self.verbas if not v.alternativa), ZERO))

    @property
    def total_principal(self) -> Decimal:
        return brl(sum((v.principal for v in self.verbas if not v.alternativa), ZERO))

    @property
    def total_reflexos(self) -> Decimal:
        return brl(sum((v.total_reflexos for v in self.verbas if not v.alternativa), ZERO))


def _data(respostas: dict[str, Any], campo: str) -> date | None:
    v = respostas.get(campo)
    if isinstance(v, date):
        return v
    if isinstance(v, str) and v.strip():
        try:
            return date.fromisoformat(v.strip())
        except ValueError:
            return None
    return None


def calcular(
    catalogo: Catalogo,
    respostas: dict[str, Any],
    analise: Analise,
    hoje: date | None = None,
) -> Calculo:
    admissao = _data(respostas, "data_admissao")
    saida = _data(respostas, "data_saida")
    salario = respostas.get("salario_base")

    faltam = [
        rotulo
        for rotulo, valor in (
            ("data de admissao", admissao),
            ("data de saida", saida),
            ("salario base", salario),
        )
        if not valor
    ]
    if faltam:
        return Calculo(motivo="Informar " + ", ".join(faltam) + " para apurar valores.")

    ajuizamento = data_ajuizamento(respostas, hoje)
    periodo, houve_corte = periodo_apuracao(admissao, saida, ajuizamento)
    if not periodo.valido:
        return Calculo(motivo="Periodo integralmente alcancado pela prescricao quinquenal.")

    par = parametros()
    jornada = respostas.get("jornada_contratual") or "44h"
    divisor = par["divisores"].get(jornada, 220)

    ctx = Contexto(
        respostas=respostas,
        parametros=par,
        admissao=admissao,
        saida=saida,
        ajuizamento=ajuizamento,
        salario_base=d(salario),
        periodo=periodo,
        houve_corte_quinquenal=houve_corte,
        divisor=divisor,
    )

    calculo = Calculo(disponivel=True, periodo=periodo, houve_corte_quinquenal=houve_corte)
    if houve_corte:
        calculo.observacoes.append(
            f"Corte quinquenal aplicado: apuracao limitada a {periodo}. "
            "Parcelas anteriores nao foram computadas."
        )

    # Quais verbas apurar: apenas pedidos confirmados com modulo de calculo.
    a_calcular = [
        av.pedido.calculo
        for av in analise.cabiveis
        if av.pedido.calculo and av.pedido.calculo in MODULOS
    ]

    def executar(nome: str) -> Verba:
        return MODULOS[nome](ctx)

    # --- 1. insalubridade x periculosidade: nao acumulam (art. 193, par. 2o)
    concorrentes = [n for n in ("insalubridade", "periculosidade") if n in a_calcular]
    resultados = [executar(n) for n in concorrentes]
    calculaveis = [v for v in resultados if v.calculavel]
    if len(calculaveis) > 1:
        vencedora = max(calculaveis, key=lambda v: v.total)
        for v in calculaveis:
            if v is not vencedora:
                v.alternativa = True
                v.observacoes.append(
                    "Nao acumula com o adicional mais benefico (art. 193, par. 2o, da CLT). "
                    "Pedir em carater alternativo/sucessivo."
                )
        ctx.adicionais_habituais += vencedora.mensal
    elif calculaveis:
        ctx.adicionais_habituais += calculaveis[0].mensal

    for v in resultados:
        (calculo.verbas if v.calculavel else calculo.pendentes).append(v)

    # --- 2. adicional noturno: integra o salario para todos os efeitos (Sumula 60, I)
    if "adicional_noturno" in a_calcular:
        v = executar("adicional_noturno")
        if v.calculavel:
            ctx.adicionais_habituais += v.mensal
            calculo.verbas.append(v)
        else:
            calculo.pendentes.append(v)

    if ctx.adicionais_habituais > ZERO:
        calculo.observacoes.append(
            f"Base majorada em {fmt(ctx.adicionais_habituais)}/mes pelos adicionais habituais "
            f"(Sumula 264 do TST): remuneracao de {fmt(ctx.remuneracao)}."
        )

    # --- 3. demais verbas, ja sobre a base majorada
    for nome in a_calcular:
        if nome in COMPOEM_BASE:
            continue
        v = executar(nome)
        (calculo.verbas if v.calculavel else calculo.pendentes).append(v)

    calculo.remuneracao = ctx.remuneracao
    calculo.observacoes.append(
        "Apurado sobre o ultimo salario informado. A evolucao salarial real exige a ficha "
        "financeira - conferir antes de protocolar."
    )
    calculo.observacoes.append(
        "NAO inclui correcao monetaria, juros, INSS nem IRRF. Valores nominais, "
        "para dimensionar o pedido (art. 840, par. 1o, da CLT)."
    )
    return calculo
