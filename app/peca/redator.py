"""Minuta da inicial, montada a partir do que a triagem ja decidiu.

**O redator nao decide nada.** Quais pedidos cabem, quais se cindem por periodo,
o que prescreveu e qual redacao da lei valia na data do caso - tudo isso ja foi
resolvido pelo motor de regras e pelo corpus. Aqui so se da forma.

Isso e o que torna a minuta auditavel. Nao ha modelo de linguagem no caminho,
entao o texto e funcao determinista das respostas: mesmo caso, mesma minuta,
sempre. Divergencia se explica lendo o template, nao reexecutando um modelo. E
nenhuma citacao pode ser inventada, porque nenhuma citacao e escrita aqui - todas
vem do catalogo, resolvidas contra o corpus pela data do caso.

Duas coisas que ele deliberadamente NAO faz, por decisao de quem usa o sistema:

**Nao apura valor.** O art. 840 par. 1o exige valor por pedido, e esse numero vem
do contador ou do PJe-Calc. A minuta sai sem a coluna - e sem lacunas de valor,
que e o ponto: lacuna que ninguem preenche vira peca protocolada com "[VALOR]"
dentro dela.

**Nao inclui pedido em estado "a investigar".** Eles saem numa lista propria, ao
fim, com a pergunta que destrancaria cada um. Achatar o terceiro estado dentro do
corpo da peca desfaria justamente o que a triagem construiu.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date

from app.motor import Analise, PedidoAvaliado, Prescricao, Respostas, data_ajuizamento
from app.schema import REFORMA, Armadilha, Catalogo, Pedido, VariacaoTemporal

# Ultimo dia do regime anterior. Citar a redacao pre-Reforma pedindo a lei "em
# 11/11/2017" devolveria a redacao nova - a vespera e a unica data que responde
# pelo regime que se quer citar.
VESPERA_REFORMA = date.fromordinal(REFORMA.toordinal() - 1)

# Os oito campos que compoem a qualificacao do reclamante, na ordem em que a peca
# os escreve. O texto ao redor e formula forense; o que vem da entrevista e so o
# valor. `funcao` entra como profissao, que e onde a peca a pede.
_QUALIFICACAO = [
    ("reclamante_nacionalidade", "{}"),
    ("reclamante_estado_civil", "{}"),
    ("funcao", "{}"),
    ("reclamante_rg", "portador do RG nº {}"),
    ("reclamante_cpf", "inscrito no CPF sob o nº {}"),
    ("reclamante_ctps", "CTPS nº {}"),
    ("reclamante_pis", "PIS/PASEP nº {}"),
    ("reclamante_endereco", "residente e domiciliado em {}"),
]

# Cada bloco de fato vira uma secao com titulo proprio. O texto da pergunta serve
# para perguntar, nao para intitular: "Descreva os episodios de assedio" e um
# comando ao entrevistador, e nao um titulo de peca.
_TITULO_FATO = {
    "narrativa_fatos": "Do contrato de trabalho e de sua execução",
    "fatos_jornada": "Da jornada efetivamente cumprida",
    "fatos_assedio": "Do assédio moral",
    "fatos_acidente": "Do acidente de trabalho",
    "fatos_justa_causa": "Da justa causa e de sua reversão",
    "fatos_rescisao_indireta": "Da falta patronal",
    "fatos_paradigma": "Da equiparação salarial",
    "fatos_desvio": "Do desvio de função",
}

REGIME_ROTULO = {
    "pre_reforma": "até 10/11/2017",
    "pos_reforma": "a partir de 11/11/2017",
}


@dataclass
class Citacao:
    """Um fundamento do catalogo, resolvido contra o corpus quando possivel."""

    ref: str
    nota: str | None = None
    controverso: bool = False
    # Preenchidos so quando o corpus tem a obra. Sumula do TST e CF ainda nao
    # foram ingeridas: a citacao sai pelo rotulo, sem o texto, que e honesto -
    # melhor citar sem transcrever do que transcrever de memoria.
    rotulo: str | None = None
    texto: str | None = None
    vigencia: str | None = None


@dataclass
class Bloco:
    """Um pedido cabivel, com o que sustenta o direito nele."""

    pedido: Pedido
    regimes: list[str] = field(default_factory=list)
    cindir: bool = False
    citacoes: list[Citacao] = field(default_factory=list)
    variacoes: list[VariacaoTemporal] = field(default_factory=list)


@dataclass
class Pendencia:
    """Pedido que a triagem nao confirmou, e a pergunta que o destrancaria."""

    pedido: Pedido
    faltam: list[str] = field(default_factory=list)


@dataclass
class Minuta:
    juizo: str
    reclamante: str
    reclamada: str
    fatos: list[tuple[str, str]] = field(default_factory=list)
    fundamentacao: list[Bloco] = field(default_factory=list)
    pedidos: list[str] = field(default_factory=list)
    requerimentos: list[Armadilha] = field(default_factory=list)
    nao_incluidos: list[Pendencia] = field(default_factory=list)
    # Campos de qualificacao e de fato ainda em branco. A minuta sai mesmo assim
    # - peca incompleta que se ve e melhor que peca que espera perfeicao para
    # existir -, mas diz o que falta antes do protocolo.
    lacunas: list[str] = field(default_factory=list)
    prescricao: Prescricao | None = None
    atravessa_reforma: bool = False


def _rotulo(catalogo: Catalogo, campo: str, valor) -> str:
    """Resolve o rotulo de uma pergunta de escolha. 'casado' -> 'Casado(a)'."""
    p = next((q for q in catalogo.entrevista.perguntas if q.id == campo), None)
    if p is None or p.tipo != "escolha":
        return str(valor)
    return next((o.rotulo for o in p.opcoes if o.valor == valor), str(valor))


def qualificar_reclamante(catalogo: Catalogo, respostas: Respostas) -> str:
    nome = (respostas.get("reclamante_nome") or "").strip()
    partes = []
    for campo, forma in _QUALIFICACAO:
        v = respostas.get(campo)
        if v not in (None, "", []):
            partes.append(forma.format(_rotulo(catalogo, campo, v)).strip())
    # Sem nome a qualificacao nao pode simplesmente comecar pelo campo seguinte:
    # "Auxiliar de producao, brasileiro, ..." se le como se a profissao fosse o
    # nome. A falta precisa aparecer como falta.
    if not nome:
        return f"[RECLAMANTE NÃO QUALIFICADO], {', '.join(partes)}" if partes else ""
    corpo = ", ".join(partes)
    return f"{nome.upper()}, {corpo}" if corpo else nome.upper()


def qualificar_reclamada(respostas: Respostas) -> str:
    razao = (respostas.get("reclamada_razao_social") or "").strip()
    partes = []
    if cnpj := respostas.get("reclamada_cnpj"):
        partes.append(f"inscrita no CNPJ sob o nº {cnpj}")
    if end := respostas.get("reclamada_endereco"):
        partes.append(f"com endereço em {end}")
    if not razao and not partes:
        return ""
    corpo = ", ".join(["pessoa jurídica de direito privado", *partes])
    return f"{razao.upper()}, {corpo}" if razao else corpo


def lacunas(catalogo: Catalogo, respostas: Respostas, analise: Analise) -> list[str]:
    """Campos visiveis, ainda em branco, que a peca vai precisar.

    Mesma regra que o relatorio aplica hoje dentro do template
    (`relatorio.html`). Ela deveria morar num lugar so - hoje esta nos dois.
    """
    fora = []
    for p in catalogo.entrevista.perguntas:
        if p.secao not in ("qualificacao", "fatos"):
            continue
        if p.id not in analise.visiveis or p.vazio_e_resposta:
            continue
        if not respostas.get(p.id):
            fora.append(p.texto)
    return fora


def _datas_de_citacao(
    av: PedidoAvaliado, respostas: Respostas, hoje: date | None
) -> list[date]:
    """Em que data(s) a lei deve ser lida para ESTE pedido.

    Pedido que atravessa a Reforma se cita nas duas pontas: e o mesmo motivo pelo
    qual ele se cinde no pedido. Citar so a redacao de hoje num contrato de 2016
    e o erro que o eixo de vigencia existe para impedir.
    """
    fim = data_ajuizamento(respostas, hoje)
    datas = []
    if "pre_reforma" in av.regimes:
        datas.append(VESPERA_REFORMA)
    if "pos_reforma" in av.regimes or not av.regimes:
        datas.append(fim)
    return datas or [fim]


def _citacoes(
    av: PedidoAvaliado,
    respostas: Respostas,
    con: sqlite3.Connection | None,
    hoje: date | None,
) -> list[Citacao]:
    from app.corpus import busca

    datas = _datas_de_citacao(av, respostas, hoje)
    saida: list[Citacao] = []
    for f in av.pedido.fundamentos:
        if con is None:
            saida.append(Citacao(ref=f.ref, nota=f.nota, controverso=f.controverso))
            continue
        # Um dispositivo pode ter a mesma redacao nas duas pontas; nesse caso ele
        # se cita uma vez so. A chave e (urn, inicio de vigencia), que e a mesma
        # do corpus - duas redacoes distintas do art. 71 par. 4o sao duas
        # citacoes, e a mesma redacao lida em duas datas e uma.
        vistos = set()
        achou = False
        for quando in datas:
            for a in busca.por_referencia(con, f.tipo, f.ref, quando):
                chave = (a.urn, a.vigencia_inicio)
                if chave in vistos:
                    continue
                vistos.add(chave)
                achou = True
                ate = a.vigencia_fim or "hoje"
                saida.append(
                    Citacao(
                        ref=f.ref,
                        nota=f.nota,
                        controverso=f.controverso,
                        rotulo=a.rotulo,
                        texto=a.texto,
                        vigencia=f"{a.vigencia_inicio} a {ate}",
                    )
                )
        if not achou:
            # Obra fora do corpus (sumula, CF) ou dispositivo nao vigente na data.
            saida.append(Citacao(ref=f.ref, nota=f.nota, controverso=f.controverso))
    return saida


def _texto_do_pedido(av: PedidoAvaliado) -> list[str]:
    """O pedido como ele entra na lista final, cindido quando a regra exige."""
    if not av.cindir or len(av.regimes) < 2:
        return [av.pedido.nome]
    return [f"{av.pedido.nome} ({REGIME_ROTULO[r]})" for r in av.regimes]


def montar(
    catalogo: Catalogo,
    respostas: Respostas,
    analise: Analise,
    con: sqlite3.Connection | None = None,
    hoje: date | None = None,
) -> Minuta:
    """Monta a minuta. `con` ausente significa corpus nao ingerido: as citacoes
    saem pelo rotulo do catalogo, sem transcricao."""
    local = (respostas.get("local_prestacao") or "").strip()
    juizo = (
        f"UMA DAS VARAS DO TRABALHO DE {local.upper()}"
        if local
        else "UMA DAS VARAS DO TRABALHO"
    )

    fatos = []
    for campo, titulo in _TITULO_FATO.items():
        texto = (respostas.get(campo) or "").strip()
        if texto:
            fatos.append((titulo, texto))

    fundamentacao = [
        Bloco(
            pedido=av.pedido,
            regimes=av.regimes,
            cindir=av.cindir,
            citacoes=_citacoes(av, respostas, con, hoje),
            variacoes=[v for v in av.pedido.variacao_temporal if v.regime in av.regimes],
        )
        for av in analise.cabiveis
    ]

    pedidos = [nome for av in analise.cabiveis for nome in _texto_do_pedido(av)]

    perguntas = {p.id: p.texto for p in catalogo.entrevista.perguntas}
    nao_incluidos = [
        Pendencia(
            pedido=av.pedido,
            faltam=[perguntas.get(c, c) for c in av.faltam],
        )
        for av in analise.possiveis
    ]

    return Minuta(
        juizo=juizo,
        reclamante=qualificar_reclamante(catalogo, respostas),
        reclamada=qualificar_reclamada(respostas),
        fatos=fatos,
        fundamentacao=fundamentacao,
        pedidos=pedidos,
        requerimentos=analise.armadilhas,
        nao_incluidos=nao_incluidos,
        lacunas=lacunas(catalogo, respostas, analise),
        prescricao=analise.prescricao,
        atravessa_reforma=analise.atravessa_reforma,
    )
