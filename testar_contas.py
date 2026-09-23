"""Login e isolamento entre escritorios - o que o servico nao pode errar.

    python testar_contas.py

Roda num diretorio temporario: nao encosta em dados/contas.db nem nos casos reais.

A assercao que importa e a do bloco 3: o escritorio B nao ve, nao abre e nao
sobrescreve o caso do escritorio A, nem sabendo o numero dele. Tudo mais - senha,
sessao, bloqueio - existe para que essa continue verdadeira.
"""

import re
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path

try:
    from starlette.testclient import TestClient
except RuntimeError:  # o TestClient exige httpx, que esta no requirements.txt
    raise SystemExit("falta o httpx: pip install -r requirements.txt")

from app import contas, persistencia
from app.main import app

falhas = []


def conferir(rotulo: str, obtido, esperado) -> None:
    ok = obtido == esperado
    print(f"  {'ok ' if ok else 'ERRO'} {rotulo}")
    if not ok:
        falhas.append(f"{rotulo}: esperado {esperado!r}, obtido {obtido!r}")


def cliente(**kw) -> TestClient:
    return TestClient(app, follow_redirects=False, **kw)


def ids_na_lista(html: str) -> set[int]:
    return {int(n) for n in re.findall(r'href="/caso/(\d+)"', html)}


temp = Path(tempfile.mkdtemp())
dados_originais, modo_original, banco_original = contas.DADOS, contas.MODO, persistencia.BANCO
try:
    contas.DADOS = temp
    persistencia.BANCO = temp / "casos-local.db"

    # --- 1. senha -------------------------------------------------------------

    print("senha")
    guardado = contas.hash_senha("cavalo-bateria-grampo")
    conferir("a senha certa confere", contas.senha_confere("cavalo-bateria-grampo", guardado), True)
    conferir("a errada nao", contas.senha_confere("cavalo-bateria-grampa", guardado), False)
    conferir("o hash nao contem a senha", "cavalo" in guardado, False)
    conferir("mesma senha, hash diferente (sal)", contas.hash_senha("cavalo-bateria-grampo") != guardado, True)
    try:
        contas.criar_usuario(1, "x@x.adv.br", "X", "curta")
        conferir("senha curta e recusada", False, True)
    except ValueError:
        conferir("senha curta e recusada", True, True)

    # --- 2. modo servico: sem sessao, nada ------------------------------------

    contas.MODO = "servico"
    a = contas.criar_escritorio("Escritorio A")
    b = contas.criar_escritorio("Escritorio B")
    contas.criar_usuario(a, "ana@a.adv.br", "Ana", "senha-da-ana-123")
    contas.criar_usuario(b, "bia@b.adv.br", "Bia", "senha-da-bia-123")

    print("\nsem sessao")
    anonimo = cliente()
    r = anonimo.get("/")
    conferir("GET / vai para o login", (r.status_code, r.headers.get("location", "")[:6]), (303, "/login"))
    r = anonimo.get("/corpus?q=art.%2071")
    conferir("e volta para onde ia, com a busca", "proximo=/corpus%3Fq%3D" in r.headers.get("location", ""), True)
    r = anonimo.post("/caso/salvar", data={"caso_nome": "intruso"})
    conferir("POST sem sessao e 401, nao redirect", r.status_code, 401)
    conferir("a tela de login abre", anonimo.get("/login").status_code, 200)
    conferir("o CSS abre sem login", anonimo.get("/static/app.css").status_code, 200)
    r = anonimo.get("/login?proximo=//site-estranho.com")
    conferir("proximo externo e descartado", 'value="//site-estranho.com"' in r.text, False)

    print("\nentrar")
    r = anonimo.post("/login", data={"email": "ana@a.adv.br", "senha": "errada-errada"})
    conferir("senha errada: 401 e mensagem generica", (r.status_code, "não conferem" in r.text), (401, True))
    r = anonimo.post("/login", data={"email": "ninguem@x.adv.br", "senha": "qualquer-coisa"})
    conferir("e-mail inexistente: a MESMA mensagem", "não conferem" in r.text, True)

    ana = cliente()
    r = ana.post("/login", data={"email": "ANA@a.adv.br", "senha": "senha-da-ana-123", "proximo": "/casos"})
    conferir("senha certa entra (e-mail sem diferenca de caixa)", (r.status_code, r.headers["location"]), (303, "/casos"))
    cookie = r.headers.get("set-cookie", "").lower()
    conferir("cookie HttpOnly e SameSite=Lax", "httponly" in cookie and "samesite=lax" in cookie, True)
    conferir("com sessao, a entrevista abre", ana.get("/").status_code, 200)
    conferir("e o cabecalho diz o escritorio", "Escritorio A" in ana.get("/").text, True)

    bia = cliente()
    bia.post("/login", data={"email": "bia@b.adv.br", "senha": "senha-da-bia-123"})

    # --- 3. isolamento ---------------------------------------------------------

    print("\nisolamento entre escritorios")
    id_a = ana.post("/caso/salvar", data={"caso_nome": "Cliente da Ana"}).json()["id"]
    id_b = bia.post("/caso/salvar", data={"caso_nome": "Cliente da Bia"}).json()["id"]

    conferir("cada escritorio tem o seu arquivo", contas.banco_de_casos(a) != contas.banco_de_casos(b), True)
    conferir("A lista so o caso de A", "Cliente da Bia" in ana.get("/casos").text, False)
    conferir("B lista so o caso de B", "Cliente da Ana" in bia.get("/casos").text, False)

    # Os dois bancos numeram do 1: o mesmo numero e um caso diferente em cada um.
    conferir("mesmo numero nos dois escritorios", id_a == id_b, True)
    r = bia.get(f"/caso/{id_a}")
    conferir(
        "B abrindo o numero do caso de A ve o SEU caso",
        ("Cliente da Ana" in r.text, "Cliente da Bia" in r.text),
        (False, True),
    )
    r = bia.get("/caso/999")
    conferir("numero que nao existe volta para a lista", (r.status_code, r.headers.get("location")), (303, "/casos"))

    # Salvar com o id de outro escritorio nao alcanca o banco dele.
    bia.post("/caso/salvar", data={"caso_nome": "Sobrescrito pela Bia", "caso_id": str(id_a)})
    conferir("B nao sobrescreve o caso de A", persistencia.carregar(contas.banco_de_casos(a), id_a)[0], "Cliente da Ana")
    bia.post("/caso/salvar", data={"caso_nome": "Id alheio", "caso_id": "57"})
    conferir(
        "id que nao existe no banco vira caso novo, nao update perdido",
        "Id alheio" in bia.get("/casos").text,
        True,
    )

    # --- 4. sessao --------------------------------------------------------------

    print("\nsessao")
    token = ana.cookies.get("sessao")
    conferir("o banco guarda o hash do token, nao o token", token in (contas.DADOS / "contas.db").read_bytes().decode("latin-1"), False)

    ana.post("/sair")
    conferir("depois de sair, o mesmo token nao vale", contas.sessao(token), None)

    contas.DURACAO, duracao = timedelta(seconds=-1), contas.DURACAO
    velho = cliente()
    velho.post("/login", data={"email": "ana@a.adv.br", "senha": "senha-da-ana-123"})
    contas.DURACAO = duracao
    conferir("sessao expirada nao entra", velho.get("/").status_code, 303)

    contas.desativar("bia@b.adv.br")
    conferir("usuario desativado perde a sessao aberta", bia.get("/").status_code, 303)

    print("\nbloqueio por tentativas")
    for _ in range(contas.TENTATIVAS):
        anonimo.post("/login", data={"email": "ana@a.adv.br", "senha": "chute-chute-chute"})
    r = anonimo.post("/login", data={"email": "ana@a.adv.br", "senha": "senha-da-ana-123"})
    conferir("depois de dez erros, nem a senha certa entra", "Muitas tentativas" in r.text, True)

    # --- 5. modo local ----------------------------------------------------------

    print("\nmodo local")
    contas.MODO = "local"
    local = cliente(client=("127.0.0.1", 50000))
    conferir("da propria maquina, sem login", local.get("/").status_code, 200)
    conferir("e sem caixa de conta no cabecalho", "Sair" in local.get("/").text, False)
    id_l = local.post("/caso/salvar", data={"caso_nome": "Caso local"}).json()["id"]
    conferir("grava no casos.db local", persistencia.carregar(persistencia.BANCO, id_l)[0], "Caso local")
    conferir("de outra maquina: 403", cliente(client=("192.168.0.10", 50000)).get("/").status_code, 403)
    r = local.get("/", headers={"X-Forwarded-For": "200.1.2.3"})
    conferir("atras de proxy (servidor esquecido em modo local): 403", r.status_code, 403)
finally:
    contas.DADOS, contas.MODO, persistencia.BANCO = dados_originais, modo_original, banco_original
    shutil.rmtree(temp, ignore_errors=True)

if falhas:
    print("\nFALHOU")
    for f in falhas:
        print("  " + f)
    raise SystemExit(1)
print("\nlogin e isolamento ok")
