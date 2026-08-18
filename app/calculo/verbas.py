"""Modulos de calculo, um por verba.

Cada modulo devolve o principal, os reflexos e a MEMORIA: uma linha por operacao,
com a formula em texto. Se um numero nao pode ser explicado linha a linha, ele nao
entra no pedido - e essa e a razao de a calculadora ser deterministica e nao sair
de modelo de linguagem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from app.calculo.dinheiro import ZERO, brl, d, fmt, pct
from app.calculo.periodo import Periodo, cindir_por_regime, domingos_e_uteis


@dataclass
class Linha:
    descricao: str
    formula: str
    valor: Decimal


@dataclass
class Verba:
    pedido_id: str
    nome: str
    principal: Decimal = ZERO
    reflexos: list[Linha] = field(default_factory=list)
    memoria: list[Linha] = field(default_factory=list)
    observacoes: list[str] = field(default_factory=list)
    faltam: list[str] = field(default_factory=list)
    # Valor MENSAL da parcela, quando ela integra a base das demais verbas
    # (Sumula 264 do TST). So os adicionais habituais preenchem este campo.
    mensal: Decimal = ZERO
    # Verba deferida em carater alternativo (ex.: insalubridade x periculosidade).
    alternativa: bool = False

    @property
    def total_reflexos(self) -> Decimal:
        return brl(sum((r.valor for r in self.reflexos), ZERO))

    @property
    def total(self) -> Decimal:
        return brl(self.principal + self.total_reflexos)

    @property
    def calculavel(self) -> bool:
        return not self.faltam


@dataclass
class Contexto:
    respostas: dict[str, Any]
    parametros: dict[str, Any]
    admissao: date
    saida: date
    ajuizamento: date
    salario_base: Decimal
    periodo: Periodo
    houve_corte_quinquenal: bool
    divisor: int
    # Preenchido em cascata pelo orquestrador: adicionais habituais que integram
    # a base das demais verbas (Sumula 264 do TST).
    adicionais_habituais: Decimal = ZERO

    @property
    def remuneracao(self) -> Decimal:
        return brl(self.salario_base + self.adicionais_habituais)

    @property
    def valor_hora(self) -> Decimal:
        return brl(self.remuneracao / d(self.divisor))

    @property
    def anos_completos(self) -> int:
        anos = self.saida.year - self.admissao.year
        if (self.saida.month, self.saida.day) < (self.admissao.month, self.admissao.day):
            anos -= 1
        return max(0, anos)

    @property
    def dias_aviso(self) -> int:
        """Lei 12.506/2011: 30 dias mais 3 por ano completo, limitado a 90."""
        return min(90, 30 + 3 * self.anos_completos)

    def num(self, campo: str, padrao: Any = None) -> Decimal | None:
        v = self.respostas.get(campo)
        if v is None or v == "":
            return d(padrao) if padrao is not None else None
        return d(v)


# --- utilitarios ------------------------------------------------------------


def _por_competencia(periodo: Periodo, valor_mes_cheio: Decimal) -> tuple[Decimal, list[Linha]]:
    """Rateia um valor mensal pelo periodo, proporcionalizando meses parciais."""
    import calendar

    total, linhas = ZERO, []
    for ano, mes in periodo.competencias():
        dias_mes = calendar.monthrange(ano, mes)[1]
        dias = periodo.dias_na_competencia(ano, mes)
        if dias == dias_mes:
            valor = brl(valor_mes_cheio)
        else:
            valor = brl(valor_mes_cheio * d(dias) / d(dias_mes))
        total += valor
    linhas.append(
        Linha(
            f"Total do periodo ({periodo.meses:.2f} meses)",
            f"{fmt(valor_mes_cheio)}/mes, com meses parciais proporcionalizados",
            brl(total),
        )
    )
    return brl(total), linhas


def _rsr(periodo: Periodo, valor_mes_cheio: Decimal) -> Decimal:
    """RSR sobre parcela variavel habitual (Sumula 172 do TST).

    (valor do mes / dias uteis) x domingos. Feriados nao entram - ver periodo.py.
    """
    import calendar

    total = ZERO
    for ano, mes in periodo.competencias():
        domingos, uteis = domingos_e_uteis(ano, mes)
        if uteis == 0:
            continue
        dias_mes = calendar.monthrange(ano, mes)[1]
        dias = periodo.dias_na_competencia(ano, mes)
        valor = valor_mes_cheio * d(dias) / d(dias_mes)
        total += valor / d(uteis) * d(domingos)
    return brl(total)


def reflexos_sobre(ctx: Contexto, base: Decimal, periodo: Periodo, com_aviso: bool = True) -> list[Linha]:
    """Reflexos padrao de parcela salarial habitual.

    Ordem importa: FGTS incide sobre o principal ja somado aos demais reflexos.
    """
    if base <= ZERO:
        return []
    meses = periodo.meses or d(1)
    linhas: list[Linha] = []

    decimo = brl(base / d(12))
    linhas.append(Linha("Reflexo em 13o salario", f"{fmt(base)} / 12", decimo))

    ferias = brl(base / d(12) * d(4) / d(3))
    linhas.append(Linha("Reflexo em ferias + 1/3", f"{fmt(base)} / 12 x 4/3", ferias))

    aviso = ZERO
    if com_aviso:
        media = brl(base / meses)
        aviso = brl(media * d(ctx.dias_aviso) / d(30))
        linhas.append(
            Linha("Reflexo em aviso previo", f"media {fmt(media)} x {ctx.dias_aviso}/30 dias", aviso)
        )

    base_fgts = brl(base + decimo + ferias + aviso)
    fgts = pct(base_fgts, ctx.parametros["fgts_percentual"])
    linhas.append(Linha("FGTS sobre o conjunto", f"8% de {fmt(base_fgts)}", fgts))

    multa = pct(fgts, ctx.parametros["fgts_multa_percentual"])
    linhas.append(Linha("Multa de 40% do FGTS", f"40% de {fmt(fgts)}", multa))
    return linhas


def _salario_minimo(ctx: Contexto, em: date) -> tuple[Decimal, bool]:
    """Valor vigente na competencia. O bool indica se a tabela ficou defasada."""
    tabela = ctx.parametros["salario_minimo"]
    vigente, defasado = None, True
    for faixa in tabela:
        if faixa["desde"] <= em:
            vigente = d(faixa["valor"])
    ultima = max(f["desde"] for f in tabela)
    defasado = em > ultima and em.year > ultima.year
    return (vigente or d(tabela[-1]["valor"])), defasado


# --- adicionais que compoem a base -----------------------------------------


def insalubridade(ctx: Contexto) -> Verba:
    v = Verba("insalubridade", "Adicional de insalubridade")
    grau = ctx.respostas.get("grau_insalubridade")
    if not grau:
        v.faltam.append("grau_insalubridade")
        return v

    percentual = d(ctx.parametros["graus_insalubridade"][grau])
    usar_minimo = ctx.respostas.get("base_insalubridade", "salario_minimo") == "salario_minimo"

    if usar_minimo:
        base, defasado = _salario_minimo(ctx, ctx.periodo.fim)
        v.memoria.append(Linha("Base adotada", f"salario minimo de {ctx.periodo.fim:%m/%Y}", base))
        if defasado:
            v.observacoes.append(
                "A tabela de salario minimo nao cobre toda a competencia apurada. "
                "Atualizar app/calculo/parametros.yaml antes de usar em peca."
            )
        v.observacoes.append(
            "Base de calculo em disputa (Sumula Vinculante 4 do STF x Sumula 228 do TST, "
            "suspensa). Adotado o salario minimo. Conferir a posicao do TRT competente."
        )
    else:
        base = ctx.salario_base
        v.memoria.append(Linha("Base adotada", "salario base contratual", base))
        v.observacoes.append("Base sobre o salario contratual: tese mais favoravel, porem controversa.")

    mensal = pct(base, percentual)
    v.memoria.append(Linha(f"Adicional grau {grau}", f"{percentual}% de {fmt(base)}", mensal))

    total, linhas = _por_competencia(ctx.periodo, mensal)
    v.memoria.extend(linhas)
    v.principal = total
    v.mensal = mensal
    v.reflexos = reflexos_sobre(ctx, total, ctx.periodo)
    return v


def periculosidade(ctx: Contexto) -> Verba:
    v = Verba("periculosidade", "Adicional de periculosidade")
    percentual = d(ctx.parametros["periculosidade_percentual"])
    # Art. 193: incide sobre o salario base, sem os acrescimos de outros adicionais.
    mensal = pct(ctx.salario_base, percentual)
    v.memoria.append(
        Linha("Adicional mensal", f"{percentual}% de {fmt(ctx.salario_base)} (salario base)", mensal)
    )
    total, linhas = _por_competencia(ctx.periodo, mensal)
    v.memoria.extend(linhas)
    v.principal = total
    v.mensal = mensal
    v.reflexos = reflexos_sobre(ctx, total, ctx.periodo)
    return v


def adicional_noturno(ctx: Contexto) -> Verba:
    v = Verba("adicional_noturno", "Adicional noturno e hora ficta")
    horas = ctx.num("noturno_horas_mes")
    if horas is None:
        v.faltam.append("noturno_horas_mes")
        return v

    percentual = d(ctx.parametros["adicional_noturno_percentual"])
    fator = d(ctx.parametros["fator_hora_noturna"])

    adicional_mes = brl(ctx.valor_hora * horas * percentual / d(100))
    v.memoria.append(
        Linha("Adicional de 20%", f"{fmt(ctx.valor_hora)}/h x {horas}h x 20%", adicional_mes)
    )

    # Hora ficta: 60/52,5 gera horas excedentes remuneradas como extras.
    horas_ficticias = brl(horas * (fator - d(1)))
    ficta_mes = brl(ctx.valor_hora * horas_ficticias * d("1.5"))
    v.memoria.append(
        Linha(
            "Horas da reducao ficta (52min30s)",
            f"{horas}h x 0,142857 = {horas_ficticias}h x {fmt(ctx.valor_hora)} x 1,5",
            ficta_mes,
        )
    )

    mensal = brl(adicional_mes + ficta_mes)
    total, linhas = _por_competencia(ctx.periodo, mensal)
    v.memoria.extend(linhas)
    v.principal = total
    v.mensal = mensal
    rsr = _rsr(ctx.periodo, mensal)
    v.reflexos.append(Linha("RSR (Sumula 172)", "sobre parcela variavel habitual", rsr))
    v.reflexos += reflexos_sobre(ctx, brl(total + rsr), ctx.periodo)
    return v


# --- verbas sobre a base majorada ------------------------------------------


def horas_extras(ctx: Contexto) -> Verba:
    v = Verba("horas_extras", "Horas extras e reflexos")
    horas = ctx.num("he_horas_mes")
    if horas is None:
        v.faltam.append("he_horas_mes")
        return v

    adicional = ctx.num("he_adicional", 50)
    valor_he = brl(ctx.valor_hora * (d(1) + adicional / d(100)))
    v.memoria.append(
        Linha(
            "Valor da hora extra",
            f"({fmt(ctx.remuneracao)} / {ctx.divisor}) x (1 + {adicional}%)",
            valor_he,
        )
    )
    if ctx.adicionais_habituais > ZERO:
        v.memoria.append(
            Linha(
                "Base majorada pelos adicionais habituais",
                f"salario {fmt(ctx.salario_base)} + adicionais {fmt(ctx.adicionais_habituais)} (Sumula 264)",
                ctx.remuneracao,
            )
        )

    mensal = brl(valor_he * horas)
    v.memoria.append(Linha("Horas extras por mes", f"{fmt(valor_he)} x {horas}h", mensal))

    total, linhas = _por_competencia(ctx.periodo, mensal)
    v.memoria.extend(linhas)
    v.principal = total

    rsr = _rsr(ctx.periodo, mensal)
    v.reflexos.append(Linha("RSR (Sumula 172)", "(HE do mes / dias uteis) x domingos", rsr))
    v.reflexos += reflexos_sobre(ctx, brl(total + rsr), ctx.periodo)
    v.observacoes.append(
        "RSR calculado sobre domingos. Feriados variam por municipio e norma coletiva - "
        "conferir o calendario local e acrescentar."
    )
    return v


def intervalo_intrajornada(ctx: Contexto) -> Verba:
    """Unica verba que se cinde: regra E natureza mudam em 11/11/2017."""
    v = Verba("intervalo_intrajornada", "Intervalo intrajornada suprimido")
    dias_mes = ctx.num("intervalo_dias_mes", 22)
    minutos = ctx.num("intervalo_minutos_suprimidos")
    if minutos is None:
        v.faltam.append("intervalo_minutos_suprimidos")
        return v

    regimes = cindir_por_regime(ctx.periodo)

    if "pre_reforma" in regimes:
        p = regimes["pre_reforma"]
        # Sumula 437: paga-se a hora INTEGRAL, com natureza salarial e reflexos.
        mensal = brl(ctx.valor_hora * d("1.5") * dias_mes)
        v.memoria.append(
            Linha(
                f"Ate 10/11/2017 ({p})",
                f"1h integral x 1,5 x {dias_mes} dias x {fmt(ctx.valor_hora)} (Sumula 437)",
                mensal,
            )
        )
        total_pre, linhas = _por_competencia(p, mensal)
        v.memoria.extend(linhas)
        v.principal += total_pre
        rsr = _rsr(p, mensal)
        v.reflexos.append(Linha("RSR sobre o periodo pre-Reforma", "natureza salarial", rsr))
        v.reflexos += reflexos_sobre(ctx, brl(total_pre + rsr), p)

    if "pos_reforma" in regimes:
        p = regimes["pos_reforma"]
        # Art. 71, par. 4o: so o periodo suprimido, natureza indenizatoria, sem reflexos.
        mensal = brl(ctx.valor_hora * (minutos / d(60)) * d("1.5") * dias_mes)
        v.memoria.append(
            Linha(
                f"A partir de 11/11/2017 ({p})",
                f"{minutos}min suprimidos x 1,5 x {dias_mes} dias x {fmt(ctx.valor_hora)}",
                mensal,
            )
        )
        total_pos, linhas = _por_competencia(p, mensal)
        v.memoria.extend(linhas)
        v.principal += total_pos
        v.observacoes.append(
            "Periodo pos-Reforma tem natureza INDENIZATORIA: nao gera reflexos "
            "(art. 71, par. 4o, da CLT)."
        )

    v.principal = brl(v.principal)
    return v


def intervalo_interjornada(ctx: Contexto) -> Verba:
    v = Verba("intervalo_interjornada", "Intervalo interjornada desrespeitado")
    horas = ctx.num("interjornada_horas_mes")
    if horas is None:
        v.faltam.append("interjornada_horas_mes")
        return v

    mensal = brl(ctx.valor_hora * d("1.5") * horas)
    v.memoria.append(
        Linha("Horas suprimidas por mes", f"{horas}h x 1,5 x {fmt(ctx.valor_hora)} (OJ 355)", mensal)
    )
    total, linhas = _por_competencia(ctx.periodo, mensal)
    v.memoria.extend(linhas)
    v.principal = total
    rsr = _rsr(ctx.periodo, mensal)
    v.reflexos.append(Linha("RSR", "sobre parcela variavel habitual", rsr))
    v.reflexos += reflexos_sobre(ctx, brl(total + rsr), ctx.periodo)
    v.observacoes.append("Conferir sobreposicao com horas extras para evitar bis in idem.")
    return v


def adicional_transferencia(ctx: Contexto) -> Verba:
    v = Verba("adicional_transferencia", "Adicional de transferencia")
    meses = ctx.num("transferencia_meses")
    if meses is None:
        v.faltam.append("transferencia_meses")
        return v

    percentual = d(ctx.parametros["adicional_transferencia_percentual"])
    mensal = pct(ctx.remuneracao, percentual)
    v.memoria.append(Linha("Adicional mensal", f"{percentual}% de {fmt(ctx.remuneracao)}", mensal))
    v.principal = brl(mensal * meses)
    v.memoria.append(Linha("Periodo da transferencia", f"{fmt(mensal)} x {meses} meses", v.principal))
    v.reflexos = reflexos_sobre(ctx, v.principal, ctx.periodo)
    return v


def equiparacao_salarial(ctx: Contexto) -> Verba:
    v = Verba("equiparacao_salarial", "Equiparacao salarial")
    paradigma = ctx.num("paradigma_salario")
    if paradigma is None:
        v.faltam.append("paradigma_salario")
        return v

    diferenca = brl(paradigma - ctx.salario_base)
    if diferenca <= ZERO:
        v.observacoes.append("Salario do paradigma nao supera o do reclamante: sem diferencas a apurar.")
        return v

    v.memoria.append(
        Linha("Diferenca mensal", f"{fmt(paradigma)} - {fmt(ctx.salario_base)}", diferenca)
    )
    total, linhas = _por_competencia(ctx.periodo, diferenca)
    v.memoria.extend(linhas)
    v.principal = total
    v.reflexos = reflexos_sobre(ctx, total, ctx.periodo)
    v.observacoes.append(
        "Apurado sobre a diferenca atual. A evolucao salarial de ambos exige a ficha "
        "financeira do reclamante e do paradigma."
    )
    return v


def desvio_acumulo_funcao(ctx: Contexto) -> Verba:
    v = Verba("desvio_acumulo_funcao", "Desvio ou acumulo de funcao")
    percentual = ctx.num("acumulo_percentual")
    if percentual is None:
        v.faltam.append("acumulo_percentual")
        return v

    mensal = pct(ctx.salario_base, percentual)
    v.memoria.append(Linha("Plus salarial mensal", f"{percentual}% de {fmt(ctx.salario_base)}", mensal))
    total, linhas = _por_competencia(ctx.periodo, mensal)
    v.memoria.extend(linhas)
    v.principal = total
    v.reflexos = reflexos_sobre(ctx, total, ctx.periodo)
    v.observacoes.append(
        "Percentual arbitrado, sem base legal expressa. A posicao varia entre TRTs - "
        "conferir o entendimento do tribunal competente."
    )
    return v


# --- rescisao e penalidades ------------------------------------------------


def verbas_rescisorias(ctx: Contexto) -> Verba:
    v = Verba("verbas_rescisorias", "Verbas rescisorias")
    remuneracao = ctx.remuneracao

    saldo_dias = ctx.num("saldo_salario_dias", ctx.saida.day)
    saldo = brl(remuneracao / d(30) * saldo_dias)
    v.memoria.append(Linha("Saldo de salario", f"{fmt(remuneracao)} / 30 x {saldo_dias} dias", saldo))

    aviso = brl(remuneracao / d(30) * d(ctx.dias_aviso))
    v.memoria.append(
        Linha(
            "Aviso previo indenizado",
            f"{fmt(remuneracao)} / 30 x {ctx.dias_aviso} dias (Lei 12.506/2011)",
            aviso,
        )
    )

    # Avos do ano da saida, com projecao do aviso previo.
    ano_saida = Periodo(date(ctx.saida.year, 1, 1), ctx.saida)
    avos_13 = min(12, max(ano_saida.avos, 1))
    decimo = brl(remuneracao / d(12) * d(avos_13))
    v.memoria.append(Linha("13o proporcional", f"{fmt(remuneracao)} / 12 x {avos_13}/12", decimo))

    ferias_venc = ctx.num("ferias_vencidas", 0)
    vencidas = brl(remuneracao * d(4) / d(3) * ferias_venc)
    if vencidas > ZERO:
        v.memoria.append(
            Linha("Ferias vencidas + 1/3", f"{fmt(remuneracao)} x 4/3 x {ferias_venc} periodo(s)", vencidas)
        )

    # Avos de ferias contam do ultimo periodo aquisitivo.
    avos_ferias = min(12, max(ano_saida.avos, 1))
    proporcionais = brl(remuneracao / d(12) * d(avos_ferias) * d(4) / d(3))
    v.memoria.append(
        Linha("Ferias proporcionais + 1/3", f"{fmt(remuneracao)} / 12 x {avos_ferias}/12 x 4/3", proporcionais)
    )

    v.principal = brl(saldo + aviso + decimo + vencidas + proporcionais)
    v.observacoes.append(
        "Avos apurados pelo ano civil da saida. Periodo aquisitivo de ferias com marco "
        "distinto exige ajuste manual."
    )
    v.observacoes.append(
        "Base inclui os adicionais habituais deferidos nesta acao "
        f"({fmt(ctx.adicionais_habituais)}/mes) - e o erro mais caro quando esquecido."
    )
    return v


def fgts_40(ctx: Contexto) -> Verba:
    v = Verba("fgts_40", "FGTS e multa de 40%")
    situacao = ctx.respostas.get("fgts_depositado")

    meses = ctx.periodo.meses
    # Base e o salario CONTRATUAL, nao a remuneracao majorada: o FGTS dos adicionais
    # deferidos nesta acao ja esta nos reflexos de cada um. Usar a base majorada aqui
    # contaria a mesma parcela duas vezes.
    deposito_mes = pct(ctx.salario_base, ctx.parametros["fgts_percentual"])
    v.memoria.append(
        Linha("Deposito mensal devido", f"8% de {fmt(ctx.salario_base)} (salario contratual)", deposito_mes)
    )

    if situacao in ("nenhum", "parcial", "nao_sabe"):
        devido = brl(deposito_mes * meses)
        v.memoria.append(
            Linha("Depositos do periodo imprescrito", f"{fmt(deposito_mes)} x {meses:.2f} meses", devido)
        )
        v.principal = devido
        v.observacoes.append(
            "Apurado como se NENHUM deposito tivesse sido feito. Abater o que constar do "
            "extrato analitico da Caixa - o onus de comprovar e do empregador (Sumula 461)."
        )
    else:
        v.observacoes.append("Depositos informados como regulares: apurada apenas a multa rescisoria.")

    saldo_estimado = brl(deposito_mes * meses)
    multa = pct(saldo_estimado, ctx.parametros["fgts_multa_percentual"])
    v.reflexos.append(Linha("Multa de 40%", f"40% sobre saldo estimado de {fmt(saldo_estimado)}", multa))
    v.observacoes.append(
        "Apurado sobre o salario contratual. O FGTS e a multa das verbas deferidas nesta "
        "acao estao nos reflexos de cada uma - somar aqui seria contar duas vezes."
    )
    return v


def multa_477(ctx: Contexto) -> Verba:
    v = Verba("multa_477", "Multa do art. 477, par. 8o, da CLT")
    v.principal = ctx.remuneracao
    v.memoria.append(
        Linha("Multa equivalente a um salario", f"remuneracao de {fmt(ctx.remuneracao)}", v.principal)
    )
    return v


def multa_467(ctx: Contexto) -> Verba:
    v = Verba("multa_467", "Multa do art. 467 da CLT")
    incontroversas = ctx.num("verbas_incontroversas")
    if incontroversas is None:
        v.faltam.append("verbas_incontroversas")
        return v
    v.principal = pct(incontroversas, ctx.parametros["multa_467_percentual"])
    v.memoria.append(Linha("Acrescimo de 50%", f"50% de {fmt(incontroversas)}", v.principal))
    v.observacoes.append(
        "Incide apenas sobre a parcela reconhecida como incontroversa. Se a defesa "
        "controverter integralmente, tende a ser afastada."
    )
    return v


def seguro_desemprego(ctx: Contexto) -> Verba:
    v = Verba("seguro_desemprego", "Indenizacao substitutiva do seguro-desemprego")
    parcelas = ctx.num("seguro_parcelas", 4)
    valor_parcela = ctx.num("seguro_valor_parcela")
    if valor_parcela is None:
        v.faltam.append("seguro_valor_parcela")
        return v
    v.principal = brl(valor_parcela * parcelas)
    v.memoria.append(
        Linha("Indenizacao substitutiva", f"{fmt(valor_parcela)} x {parcelas} parcelas (Sumula 389)", v.principal)
    )
    return v


def estabilidade_gestante(ctx: Contexto) -> Verba:
    v = Verba("estabilidade_gestante", "Estabilidade gestante")
    meses = ctx.num("estabilidade_meses_restantes")
    if meses is None:
        v.faltam.append("estabilidade_meses_restantes")
        return v
    v.principal = brl(ctx.remuneracao * meses)
    v.memoria.append(
        Linha("Salarios do periodo de garantia", f"{fmt(ctx.remuneracao)} x {meses} meses", v.principal)
    )
    v.reflexos = reflexos_sobre(ctx, v.principal, ctx.periodo, com_aviso=False)
    v.observacoes.append("Indenizacao substitutiva pressupoe periodo de estabilidade ja exaurido.")
    return v


def estabilidade_acidentaria(ctx: Contexto) -> Verba:
    v = Verba("estabilidade_acidentaria", "Estabilidade acidentaria")
    meses = ctx.num("estabilidade_meses_restantes", 12)
    v.principal = brl(ctx.remuneracao * meses)
    v.memoria.append(
        Linha(
            "Salarios do periodo de garantia",
            f"{fmt(ctx.remuneracao)} x {meses} meses (art. 118 da Lei 8.213/91)",
            v.principal,
        )
    )
    v.reflexos = reflexos_sobre(ctx, v.principal, ctx.periodo, com_aviso=False)
    return v


# Ordem de execucao: adicionais primeiro, porque majoram a base dos demais.
COMPOEM_BASE = ["insalubridade", "periculosidade", "adicional_noturno"]

MODULOS = {
    "insalubridade": insalubridade,
    "periculosidade": periculosidade,
    "adicional_noturno": adicional_noturno,
    "horas_extras": horas_extras,
    "intervalo_intrajornada": intervalo_intrajornada,
    "intervalo_interjornada": intervalo_interjornada,
    "adicional_transferencia": adicional_transferencia,
    "equiparacao_salarial": equiparacao_salarial,
    "desvio_acumulo_funcao": desvio_acumulo_funcao,
    "verbas_rescisorias": verbas_rescisorias,
    "fgts_40": fgts_40,
    "multa_477": multa_477,
    "multa_467": multa_467,
    "seguro_desemprego": seguro_desemprego,
    "estabilidade_gestante": estabilidade_gestante,
    "estabilidade_acidentaria": estabilidade_acidentaria,
}
