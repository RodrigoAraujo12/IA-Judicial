"""Carga e validacao do catalogo.

Todo YAML e validado no import. Erro de catalogo estoura na subida do servidor,
nunca no meio de um atendimento.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from app.schema import Armadilha, Catalogo, Entrevista, Pedido

BASE = Path(__file__).parent
PEDIDOS_DIR = BASE / "pedidos"


def _ler(caminho: Path):
    with caminho.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def carregar() -> Catalogo:
    pedidos: list[Pedido] = []
    for arquivo in sorted(PEDIDOS_DIR.glob("*.yaml")):
        bruto = _ler(arquivo) or []
        for item in bruto:
            try:
                pedidos.append(Pedido.model_validate(item))
            except Exception as exc:  # noqa: BLE001 - queremos o nome do arquivo no erro
                raise ValueError(f"{arquivo.name}: pedido invalido -> {exc}") from exc

    ids = [p.id for p in pedidos]
    duplicados = {i for i in ids if ids.count(i) > 1}
    if duplicados:
        raise ValueError(f"ids de pedido duplicados: {sorted(duplicados)}")

    armadilhas = [Armadilha.model_validate(a) for a in _ler(BASE / "armadilhas.yaml") or []]
    entrevista = Entrevista.model_validate(_ler(BASE / "entrevista.yaml"))

    catalogo = Catalogo(pedidos=pedidos, armadilhas=armadilhas, entrevista=entrevista)
    _conferir_campos(catalogo)
    return catalogo


def _conferir_campos(catalogo: Catalogo) -> None:
    """Toda condicao precisa apontar para uma pergunta que existe.

    Sem isso, um campo renomeado no YAML da entrevista silenciosamente desliga um
    pedido inteiro - e ninguem percebe ate perder a verba.
    """
    conhecidos = {p.id for p in catalogo.entrevista.perguntas}
    problemas: list[str] = []

    def checar(origem: str, grupos):
        for grupo in grupos:
            for cond in grupo:
                if cond.campo not in conhecidos:
                    problemas.append(f"{origem} referencia campo inexistente '{cond.campo}'")

    for pedido in catalogo.pedidos:
        checar(f"pedido '{pedido.id}'", pedido.quando)
    for armadilha in catalogo.armadilhas:
        checar(f"armadilha '{armadilha.id}'", armadilha.quando)
    for pergunta in catalogo.entrevista.perguntas:
        checar(f"pergunta '{pergunta.id}'", pergunta.mostrar_se)

    ids_pedido = {p.id for p in catalogo.pedidos}
    pos_triagem = {p.id for p in catalogo.entrevista.perguntas if p.mostrar_se_pedido}

    for pergunta in catalogo.entrevista.perguntas:
        for pid in pergunta.mostrar_se_pedido:
            if pid not in ids_pedido:
                problemas.append(f"pergunta '{pergunta.id}' referencia pedido inexistente '{pid}'")

    # Pergunta de segundo passe e avaliada DEPOIS da triagem. Se um pedido a usasse
    # em `quando`, a triagem dependeria do proprio resultado.
    for pedido in catalogo.pedidos:
        for grupo in pedido.quando:
            for cond in grupo:
                if cond.campo in pos_triagem:
                    problemas.append(
                        f"pedido '{pedido.id}' usa '{cond.campo}' em `quando`, mas essa pergunta "
                        "so aparece apos a triagem (dependencia circular)"
                    )

    if problemas:
        raise ValueError("catalogo inconsistente:\n  - " + "\n  - ".join(problemas))
