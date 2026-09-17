"""Entrevista guiada e triagem de pedidos.

Roda local, sem IA. Sobe com:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.datastructures import FormData

from app import jurisdicao, persistencia
from app.catalogo.loader import carregar
from app.corpus import banco as corpus_banco
from app.corpus import busca as corpus_busca
from app.peca import redator
from app.motor import analisar
from app.schema import Catalogo

BASE = Path(__file__).parent

app = FastAPI(title="Triagem trabalhista")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")
# "TRT da 13ª Região (PB)" e escrito num lugar so, e os templates chamam de la.
templates.env.globals["rotulo_trt"] = jurisdicao.rotulo

# Estoura na subida se algum YAML estiver quebrado ou inconsistente.
CATALOGO: Catalogo = carregar()
PERGUNTAS_POR_ID = {p.id: p for p in CATALOGO.entrevista.perguntas}


# Salario redondo se digita sem centavos: "3.500". Ali o ponto e separador de
# MILHAR, e le-lo como decimal transformava R$ 3.500 em R$ 3,50 - erro de tres
# ordens de grandeza, gravado em casos.db sem nenhum sinal de que algo deu errado.
# Sem centavos nao ha virgula para desempatar, entao quem desempata e o formato:
# grupos de exatamente tres digitos depois de cada ponto so existem em milhar.
_MILHAR = re.compile(r"^\d{1,3}(?:\.\d{3})+$")


def _moeda(bruto: str) -> float | None:
    """Converte o campo de moeda. Devolve None quando nao da para ter certeza.

    None e resposta legitima aqui: o campo em branco - ou ilegivel - alimenta o
    terceiro estado do motor. Chutar um numero e que nao e opcao.
    """
    limpo = bruto.strip().replace("R$", "").replace(" ", "")
    if not limpo:
        return None

    if "," in limpo:
        # Formato do pais: ponto e milhar, virgula e decimal. "3.500,00" -> 3500.0
        limpo = limpo.replace(".", "").replace(",", ".")
    elif _MILHAR.match(limpo):
        # "3.500", "10.000", "1.234.567": so milhar. Note que "3.5" e "3.50" NAO
        # casam - tres digitos e a exigencia - e seguem sendo decimais.
        limpo = limpo.replace(".", "")

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


@app.post("/peca", response_class=HTMLResponse)
async def peca(request: Request):
    """Minuta da inicial. Mesmas respostas do relatorio, outra forma.

    O corpus e opcional aqui: sem ele a minuta sai com as referencias do
    catalogo, so que sem transcricao. Peca que cita sem transcrever e util; peca
    que transcreve de memoria, nao.
    """
    respostas = parse_respostas(await request.form())
    contexto = _contexto(respostas)
    con = corpus_banco.conectar() if corpus_banco.BANCO.exists() else None
    try:
        contexto["m"] = redator.montar(CATALOGO, respostas, contexto["analise"], con)
    finally:
        if con is not None:
            con.close()
    contexto["rotulo_regime"] = redator.REGIME_ROTULO
    return templates.TemplateResponse(request, "peca.html", contexto)


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
def caso_abrir(request: Request, caso_id: int):
    dados = persistencia.carregar(caso_id)
    if dados is None:
        return RedirectResponse("/casos", status_code=303)
    nome, respostas = dados
    return templates.TemplateResponse(request, "entrevista.html", _contexto(respostas, caso_id, nome))


@app.get("/casos", response_class=HTMLResponse)
def casos(request: Request):
    return templates.TemplateResponse(request, "casos.html", {"casos": persistencia.listar()})


# --- corpus normativo -------------------------------------------------------


@app.get("/corpus", response_class=HTMLResponse)
def corpus(request: Request, q: str = "", em: str = "", trt: str = ""):
    """Consulta ao corpus. GET com query string para o resultado ser linkavel.

    Sincrono de proposito, e nao por esquecimento. A busca hibrida leva 118 ms
    medidos - 68 deles embutindo a consulta no BGE-M3 - e nada disso e await:
    dentro de um `async def` esse tempo todo trava o event loop. Como `def`, o
    FastAPI executa no threadpool e o painel da entrevista, que faz POST em
    /analise 180 ms depois de cada tecla, nao fica na fila atras da busca.

    `em` e a data em que a norma deve estar vigente. Nunca some do formulario: uma
    busca juridica sem data responde para o presente e cala sobre o resto, que e o
    erro que este indice existe para nao cometer.

    `trt` e o tribunal regional cujas obras entram junto das nacionais. Aqui nao
    ha caso, entao ele e escolhido a mao - e o padrao e nenhum: consulta livre
    sem tribunal ve so o que vale para o pais inteiro. Os 24 tribunais aparecem
    sempre, mesmo os que ainda nao tem obra no indice: escolher um desses devolve
    so as nacionais e DIZ isso, em vez de esconder o tribunal da lista. "todos" e
    pesquisa comparada - como os outros regionais tratam a materia - e por isso
    existe aqui e nao no caso, onde sumula de outro tribunal nao e resposta.
    """
    disponivel = corpus_banco.BANCO.exists()
    try:
        quando = date.fromisoformat(em) if em else date.today()
    except ValueError:
        quando = date.today()
    todos = trt == "todos"
    trt_escolhido = int(trt) if trt.isdigit() and int(trt) in jurisdicao.ABRANGENCIA else None

    contexto: dict[str, Any] = {
        "disponivel": disponivel,
        "consulta": q,
        "quando": quando.isoformat(),
        "trt": "todos" if todos else trt_escolhido,
        "tribunais": sorted(jurisdicao.ABRANGENCIA),
        "com_obra": [],
        "resultado": None,
        "estatisticas": {},
    }

    if disponivel:
        con = corpus_banco.conectar()
        try:
            contexto["estatisticas"] = corpus_banco.estatisticas(con)
            todas = corpus_banco.obras(con)
            contexto["com_obra"] = jurisdicao.trts_no_corpus(todas)
            if q.strip():
                obras = None if todos else jurisdicao.obras_para(todas, trt_escolhido)
                contexto["resultado"] = corpus_busca.buscar(con, q, quando, limite=20, obras=obras)
        finally:
            con.close()

    return templates.TemplateResponse(request, "corpus.html", contexto)
