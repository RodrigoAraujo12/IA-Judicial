"""Periodo de apuracao: corte quinquenal, cisao pela Reforma e contagem de meses.

Aqui mora a decisao que mais afeta o valor final: o que se apura e o que ja
prescreveu. O corte quinquenal nao e aviso na tela - ele LIMITA os meses que
entram na conta.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.calculo.dinheiro import d
from app.schema import REFORMA


@dataclass(frozen=True)
class Periodo:
    inicio: date
    fim: date

    @property
    def valido(self) -> bool:
        return self.inicio <= self.fim

    def competencias(self) -> list[tuple[int, int]]:
        """(ano, mes) de cada competencia tocada pelo periodo."""
        if not self.valido:
            return []
        saida, ano, mes = [], self.inicio.year, self.inicio.month
        while (ano, mes) <= (self.fim.year, self.fim.month):
            saida.append((ano, mes))
            mes += 1
            if mes > 12:
                ano, mes = ano + 1, 1
        return saida

    def dias_na_competencia(self, ano: int, mes: int) -> int:
        """Dias do mes efetivamente dentro do periodo."""
        ultimo = calendar.monthrange(ano, mes)[1]
        ini = max(self.inicio, date(ano, mes, 1))
        fim = min(self.fim, date(ano, mes, ultimo))
        return max(0, (fim - ini).days + 1)

    @property
    def meses(self) -> Decimal:
        """Meses fracionados, para medias."""
        if not self.valido:
            return d(0)
        total = sum(
            d(self.dias_na_competencia(a, m)) / d(calendar.monthrange(a, m)[1])
            for a, m in self.competencias()
        )
        return d(total)

    @property
    def avos(self) -> int:
        """Meses com 15 dias ou mais, para 13o e ferias proporcionais."""
        return sum(1 for a, m in self.competencias() if self.dias_na_competencia(a, m) >= 15)

    def __str__(self) -> str:
        return f"{self.inicio.strftime('%d/%m/%Y')} a {self.fim.strftime('%d/%m/%Y')}"


def somar_anos(base: date, anos: int) -> date:
    try:
        return base.replace(year=base.year + anos)
    except ValueError:  # 29/02
        return base.replace(year=base.year + anos, day=28)


def periodo_apuracao(admissao: date, saida: date, ajuizamento: date) -> tuple[Periodo, bool]:
    """Periodo efetivamente apuravel apos o corte quinquenal.

    Retorna tambem se houve corte, para que a memoria de calculo registre.
    """
    corte = somar_anos(ajuizamento, -5)
    inicio = max(admissao, corte)
    return Periodo(inicio, saida), inicio > admissao


def cindir_por_regime(periodo: Periodo) -> dict[str, Periodo]:
    """Divide o periodo no marco de 11/11/2017.

    Retorna so os regimes que efetivamente incidem.
    """
    saida: dict[str, Periodo] = {}
    if periodo.inicio < REFORMA:
        saida["pre_reforma"] = Periodo(periodo.inicio, min(periodo.fim, REFORMA.replace(day=10)))
    if periodo.fim >= REFORMA:
        saida["pos_reforma"] = Periodo(max(periodo.inicio, REFORMA), periodo.fim)
    return {k: v for k, v in saida.items() if v.valido}


def domingos_e_uteis(ano: int, mes: int) -> tuple[int, int]:
    """(domingos, dias uteis) do mes.

    Base do RSR. Feriados nao entram: variam por municipio e por norma coletiva.
    O resultado e, portanto, um PISO - conferir o calendario local e acrescentar.
    """
    total = calendar.monthrange(ano, mes)[1]
    domingos = sum(1 for dia in range(1, total + 1) if date(ano, mes, dia).weekday() == 6)
    return domingos, total - domingos
