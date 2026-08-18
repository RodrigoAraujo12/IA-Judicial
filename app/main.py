"""Entrevista guiada e triagem de pedidos.

Roda local, sem IA. Sobe com:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.datastructures import FormData

from app import persistencia
from app.catalogo.loader import carregar
from app.motor import analisar
from app.schema import Catalogo

BASE = Path(__file__).parent

app = FastAPI(title="Triagem trabalhista")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")

# Estoura na subida se algum YAML estiver quebrado ou inconsistente.
CATALOGO: Catalogo = carregar()
PERGUNTAS_POR_ID = {p.id: p for p in CATALOGO.entrevista.perguntas}


def _moeda(bruto: str) -> float | None:
    limpo = bruto.strip().replace("R$", "").replace(" ", "")
    if not limpo:
        return None
    # aceita 3.500,00 e 3500.00
    if "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    try:
        return float(limpo)
    except ValueError:
        return None


def parse_respostas(form: FormData) -> dict[str, Any]:
    """Converte o form para o dicionario de respostas do motor.

    Campo nao respondido fica AUSENTE do dicionario - e o que alimenta o terceiro
    estado do motor. Nunca preencher com False por omissao.
    """
    respostas: dict[str, Any] = {}
    for pergunta in CATALOGO.entrevista.perguntas:
        if pergunta.tipo == "multipla":
            marcados = [v for v in form.getlist(pergunta.id) if v]
            if marcados:
                respostas[pergunta.id] = marcados
            continue

        bruto = form.get(pergunta.id)
        if not isinstance(bruto, str) or not bruto.strip():
            continue
        bruto = bruto.strip()

        match pergunta.tipo:
            case "bool":
                if bruto in ("sim", "nao"):
                    respostas[pergunta.id] = bruto == "sim"
            case "moeda":
                valor = _moeda(bruto)
                if valor is not None:
                    respostas[pergunta.id] = valor
            case "numero":
                try:
                    valor = float(bruto.replace(",", "."))
                    # Inteiro vira int para o relatorio nao imprimir "40.0h".
                    respostas[pergunta.id] = int(valor) if valor.is_integer() else valor
                except ValueError:
                    pass
            case _:
                respostas[pergunta.id] = bruto
    return respostas


def _contexto(respostas: dict[str, Any], caso_id: int | None = None, nome: str = "") -> dict[str, Any]:
    analise = analisar(CATALOGO, respostas)
    return {
        "catalogo": CATALOGO,
        "respostas": respostas,
        "perguntas_por_id": PERGUNTAS_POR_ID,
        "analise": analise,
        "visiveis": analise.visiveis,
        "caso_id": caso_id,
        "caso_nome": nome,
        # O JS reavalia a visibilidade simples sem ida ao servidor; as perguntas
        # que dependem da triagem vem prontas do servidor.
        "regras_visibilidade": json.dumps(
            {
                p.id: [[c.model_dump() for c in grupo] for grupo in p.mostrar_se]
                for p in CATALOGO.entrevista.perguntas
                if p.mostrar_se
            },
            ensure_ascii=False,
        ),
        "tipos": json.dumps({p.id: p.tipo for p in CATALOGO.entrevista.perguntas}),
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "entrevista.html", _contexto({}))


@app.post("/analise", response_class=HTMLResponse)
async def analise(request: Request):
    """Painel lateral vivo. Recalculado no servidor a cada alteracao do formulario."""
    respostas = parse_respostas(await request.form())
    return templates.TemplateResponse(request, "_analise.html", _contexto(respostas))


@app.post("/relatorio", response_class=HTMLResponse)
async def relatorio(request: Request):
    respostas = parse_respostas(await request.form())
    return templates.TemplateResponse(request, "relatorio.html", _contexto(respostas))


# --- casos ------------------------------------------------------------------


@app.post("/caso/salvar")
async def caso_salvar(request: Request):
    form = await request.form()
    respostas = parse_respostas(form)
    nome = str(form.get("caso_nome") or "").strip() or "Caso sem nome"
    bruto = str(form.get("caso_id") or "").strip()
    caso_id = persistencia.salvar(nome, respostas, int(bruto) if bruto.isdigit() else None)
    return JSONResponse({"id": caso_id, "nome": nome})


@app.get("/caso/{caso_id}", response_class=HTMLResponse)
async def caso_abrir(request: Request, caso_id: int):
    dados = persistencia.carregar(caso_id)
    if dados is None:
        return RedirectResponse("/casos", status_code=303)
    nome, respostas = dados
    return templates.TemplateResponse(request, "entrevista.html", _contexto(respostas, caso_id, nome))


@app.get("/casos", response_class=HTMLResponse)
async def casos(request: Request):
    return templates.TemplateResponse(request, "casos.html", {"casos": persistencia.listar()})
