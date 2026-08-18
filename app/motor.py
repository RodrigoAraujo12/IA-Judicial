"""Motor de avaliacao do caso.

Logica de tres estados, e essa e a decisao central do modulo: uma condicao pode
ser verdadeira, falsa ou DESCONHECIDA. Sem o terceiro estado o sistema descartaria
silenciosamente pedidos so porque uma pergunta ainda nao foi feita - exatamente o
erro que ele existe para evitar. Pedido em estado desconhecido vira "possivel",
com a lista do que falta perguntar ao cliente.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from app.schema import REFORMA, Armadilha, Catalogo, Condicao, Pedido

Status = Literal["cabivel", "possivel", "afastado"]

Respostas = dict[str, Any]


@dataclass
class PedidoAvaliado:
    pedido: Pedido
    status: Status
    faltam: list[str] = field(default_factory=list)
    # Regimes da Reforma que incidem sobre ESTE pedido.
    regimes: list[str] = field(default_factory=list)
    # True quando o pedido precisa ser formulado em separado por periodo.
    cindir: bool = False


@dataclass
class Prescricao:
    ajuizamento: date
    bienal_vencida: bool = False
    prazo_bienal_ate: date | None = None
    dias_para_bienal: int | None = None
    corte_quinquenal: date | None = None
    perde_periodo_anterior: bool = False


@dataclass
class Analise:
    cabiveis: list[PedidoAvaliado] = field(default_factory=list)
    possiveis: list[PedidoAvaliado] = field(default_factory=list)
    afastados: list[PedidoAvaliado] = field(default_factory=list)
    armadilhas: list[Armadilha] = field(default_factory=list)
    prescricao: Prescricao | None = None
    atravessa_reforma: bool = False
    respondidas: int = 0
    total_visiveis: int = 0
    visiveis: set[str] = field(default_factory=set)
    # Perguntas de quantificacao visiveis. Dependem do resultado da triagem, entao
    # so o servidor sabe quais sao - o JS as recebe prontas a cada atualizacao.
    visiveis_quant: list[str] = field(default_factory=list)


# --- avaliacao de condicoes -------------------------------------------------


def _valor(respostas: Respostas, campo: str) -> Any:
    v = respostas.get(campo)
    if v is None:
        return None
    if isinstance(v, str) and not v.strip():
        return None
    if isinstance(v, list) and not v:
        return None
    return v


def avaliar_condicao(cond: Condicao, respostas: Respostas) -> bool | None:
    """True, False ou None (ainda nao respondido)."""
    v = _valor(respostas, cond.campo)

    if cond.op == "preenchido":
        return v is not None
    if v is None:
        return None

    match cond.op:
        case "verdadeiro":
            return v is True
        case "falso":
            return v is False
        case "igual":
            return v == cond.valor
        case "diferente":
            return v != cond.valor
        case "em":
            alvo = cond.valor or []
            if isinstance(v, list):
                return any(x in alvo for x in v)
            return v in alvo
        case "maior":
            return _num(v) > _num(cond.valor)
        case "menor":
            return _num(v) < _num(cond.valor)
    return None


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def avaliar_grupos(grupos: list[list[Condicao]], respostas: Respostas) -> tuple[bool | None, list[str]]:
    """Dentro do grupo vale E, entre grupos vale OU.

    Retorna o resultado e os campos que faltam para decidir, quando indefinido.
    """
    if not grupos:
        return True, []

    resultados: list[bool | None] = []
    pendentes: list[str] = []

    for grupo in grupos:
        avaliadas = [(c, avaliar_condicao(c, respostas)) for c in grupo]
        if any(r is False for _, r in avaliadas):
            resultados.append(False)
        elif any(r is None for _, r in avaliadas):
            resultados.append(None)
            pendentes.extend(c.campo for c, r in avaliadas if r is None)
        else:
            resultados.append(True)

    if any(r is True for r in resultados):
        return True, []
    if any(r is None for r in resultados):
        # dedup preservando ordem
        return None, list(dict.fromkeys(pendentes))
    return False, []


# --- datas ------------------------------------------------------------------


def _somar_anos(d: date, anos: int) -> date:
    try:
        return d.replace(year=d.year + anos)
    except ValueError:  # 29/02
        return d.replace(year=d.year + anos, day=28)


def _data(respostas: Respostas, campo: str) -> date | None:
    v = respostas.get(campo)
    if isinstance(v, date):
        return v
    if isinstance(v, str) and v.strip():
        try:
            return date.fromisoformat(v.strip())
        except ValueError:
            return None
    return None


def data_ajuizamento(respostas: Respostas, hoje: date | None = None) -> date:
    """Data base da prescricao.

    Acao ja ajuizada conta da data do protocolo; acao a ajuizar, de hoje. Usar hoje
    num processo antigo encolheria o periodo apuravel indevidamente.
    """
    return _data(respostas, "data_ajuizamento") or hoje or date.today()


def avaliar_prescricao(respostas: Respostas, hoje: date | None = None) -> Prescricao | None:
    """Bienal (art. 7o, XXIX, da CF) e quinquenal."""
    saida = _data(respostas, "data_saida")
    if saida is None:
        return None

    ajuizamento = data_ajuizamento(respostas, hoje)
    p = Prescricao(ajuizamento=ajuizamento)

    p.prazo_bienal_ate = _somar_anos(saida, 2)
    p.bienal_vencida = ajuizamento > p.prazo_bienal_ate
    p.dias_para_bienal = (p.prazo_bienal_ate - ajuizamento).days

    p.corte_quinquenal = _somar_anos(ajuizamento, -5)
    admissao = _data(respostas, "data_admissao")
    if admissao is not None:
        p.perde_periodo_anterior = admissao < p.corte_quinquenal

    return p


def regimes_do_contrato(respostas: Respostas) -> list[str]:
    """Quais regimes da Reforma incidem ao longo do contrato."""
    admissao = _data(respostas, "data_admissao")
    saida = _data(respostas, "data_saida")
    if admissao is None and saida is None:
        return []

    inicio = admissao or saida
    fim = saida or date.today()

    regimes = []
    if inicio < REFORMA:
        regimes.append("pre_reforma")
    if fim >= REFORMA:
        regimes.append("pos_reforma")
    return regimes


def regime_da_rescisao(respostas: Respostas) -> list[str]:
    """Regime aplicavel quando o fato gerador e a propria extincao do contrato.

    Multa do art. 477, guias do seguro-desemprego e afins nao se cindem por
    periodo: valem pela regra vigente na data da saida.
    """
    saida = _data(respostas, "data_saida")
    if saida is None:
        return []
    return ["pos_reforma"] if saida >= REFORMA else ["pre_reforma"]


# --- analise ----------------------------------------------------------------


def analisar(catalogo: Catalogo, respostas: Respostas, hoje: date | None = None) -> Analise:
    analise = Analise()
    do_contrato = regimes_do_contrato(respostas)
    da_rescisao = regime_da_rescisao(respostas)
    analise.atravessa_reforma = len(do_contrato) > 1

    for pedido in catalogo.pedidos:
        resultado, faltam = avaliar_grupos(pedido.quando, respostas)
        vigentes = da_rescisao if pedido.marco_temporal == "rescisao" else do_contrato
        aplicaveis = [v.regime for v in pedido.variacao_temporal if v.regime in vigentes]
        avaliado = PedidoAvaliado(
            pedido=pedido,
            status="afastado",
            faltam=faltam,
            regimes=aplicaveis,
            cindir=pedido.cindir and len(aplicaveis) > 1,
        )

        if resultado is True:
            avaliado.status = "cabivel"
            analise.cabiveis.append(avaliado)
        elif resultado is None:
            avaliado.status = "possivel"
            analise.possiveis.append(avaliado)
        else:
            analise.afastados.append(avaliado)

    for armadilha in catalogo.armadilhas:
        resultado, _ = avaliar_grupos(armadilha.quando, respostas)
        # Armadilha aparece tambem no indefinido: o custo de mostrar a mais e zero,
        # o de esconder e perder a verba.
        if resultado is not False:
            analise.armadilhas.append(armadilha)

    analise.prescricao = avaliar_prescricao(respostas, hoje)

    # Segundo passe: perguntas de quantificacao dependem do resultado da triagem.
    # Nao ha circularidade porque as respostas de quantificacao nunca alimentam o
    # `quando` de um pedido - o loader recusa o catalogo se isso acontecer.
    # So pedidos CONFIRMADOS liberam quantificacao. Incluir os "a investigar" faria
    # a secao abrir inteira logo no comeco da entrevista, quando quase tudo ainda
    # esta indefinido - e o ruido apagaria o sinal.
    em_jogo = {av.pedido.id for av in analise.cabiveis}
    for p in catalogo.entrevista.perguntas:
        if p.mostrar_se_pedido:
            if any(pid in em_jogo for pid in p.mostrar_se_pedido):
                analise.visiveis.add(p.id)
                analise.visiveis_quant.append(p.id)
        elif avaliar_grupos(p.mostrar_se, respostas)[0] is not False:
            analise.visiveis.add(p.id)

    analise.total_visiveis = len(analise.visiveis)
    analise.respondidas = sum(
        1 for p in catalogo.entrevista.perguntas if _valor(respostas, p.id) is not None
    )
    return analise
