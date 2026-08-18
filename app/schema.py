"""Contratos de dados do catalogo.

Tudo que vem dos YAML passa por aqui. Se um YAML estiver malformado, o erro
aparece na carga (loader.py), nao no meio de um atendimento.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

# 11/11/2017 - vigencia da Lei 13.467/2017 (Reforma Trabalhista).
# Serve de corte para toda regra que mudou de regime.
REFORMA = date(2017, 11, 11)

Operador = Literal[
    "verdadeiro",
    "falso",
    "igual",
    "diferente",
    "em",
    "maior",
    "menor",
    "preenchido",
]


class Condicao(BaseModel):
    """Uma clausula sobre uma resposta da entrevista."""

    campo: str
    op: Operador = "verdadeiro"
    valor: Any = None


class Fundamento(BaseModel):
    tipo: Literal["cf", "clt", "lei", "sumula_tst", "oj_tst", "nr", "tema_stf", "sv_stf"]
    ref: str
    nota: str | None = None
    # Marca tese em disputa: o relatorio destaca em vez de afirmar.
    controverso: bool = False


class Requisito(BaseModel):
    descricao: str
    prova: list[str] = Field(default_factory=list)


class VariacaoTemporal(BaseModel):
    """Regra que muda conforme o periodo do contrato."""

    regime: Literal["pre_reforma", "pos_reforma"]
    regra: str


class Pedido(BaseModel):
    id: str
    nome: str
    grupo: str
    resumo: str = ""
    # Lista de grupos de condicoes. Dentro do grupo vale E, entre grupos vale OU.
    quando: list[list[Condicao]] = Field(default_factory=list)
    requisitos: list[Requisito] = Field(default_factory=list)
    fundamentos: list[Fundamento] = Field(default_factory=list)
    provas: list[str] = Field(default_factory=list)
    reflexos: list[str] = Field(default_factory=list)
    variacao_temporal: list[VariacaoTemporal] = Field(default_factory=list)
    alertas: list[str] = Field(default_factory=list)
    # Qual data define o regime aplicavel. "contrato" olha todo o periodo
    # (tempus regit actum, parcela a parcela); "rescisao" olha so a data de saida,
    # porque o fato gerador e a propria extincao.
    marco_temporal: Literal["contrato", "rescisao"] = "contrato"
    # True quando a regra muda de tal forma que o pedido precisa ser formulado
    # em separado por periodo. `variacao_temporal` sozinha e apenas informativa.
    cindir: bool = False
    # id do modulo da calculadora (Fase 2). None = ainda sem calculo.
    calculo: str | None = None


class Armadilha(BaseModel):
    """Verificacao do polo ativo que nao e pedido, mas custa dinheiro se faltar."""

    id: str
    titulo: str
    descricao: str
    fundamentos: list[Fundamento] = Field(default_factory=list)
    # Quando vazio, a armadilha vale para todo caso.
    quando: list[list[Condicao]] = Field(default_factory=list)
    gravidade: Literal["critica", "alta", "media"] = "alta"


class Opcao(BaseModel):
    valor: str
    rotulo: str


class Pergunta(BaseModel):
    id: str
    secao: str
    texto: str
    tipo: Literal["bool", "escolha", "multipla", "texto", "numero", "data", "moeda"]
    opcoes: list[Opcao] = Field(default_factory=list)
    ajuda: str | None = None
    mostrar_se: list[list[Condicao]] = Field(default_factory=list)
    # Pergunta de quantificacao: so aparece se algum destes pedidos estiver em
    # jogo. Avaliada num segundo passe, depois que os pedidos ja foram triados -
    # por isso nunca pode ser referenciada no `quando` de um pedido.
    mostrar_se_pedido: list[str] = Field(default_factory=list)
    obrigatoria: bool = False
    sufixo: str | None = None


class Secao(BaseModel):
    id: str
    titulo: str
    ordem: int


class Entrevista(BaseModel):
    secoes: list[Secao]
    perguntas: list[Pergunta]


class Catalogo(BaseModel):
    pedidos: list[Pedido]
    armadilhas: list[Armadilha]
    entrevista: Entrevista

    def pedido(self, pedido_id: str) -> Pedido | None:
        return next((p for p in self.pedidos if p.id == pedido_id), None)
