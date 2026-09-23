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

    # --- 5. registro de acesso ---------------------------------------------------

    # Tudo o que este bloco confere ja aconteceu acima: os logins, os casos
    # salvos, o caso aberto, a lista, a saida e as dez senhas erradas. O registro
    # e lido depois do fato, que e exatamente como ele sera usado.
    print("\nregistro de acesso")
    tudo = contas.acessos(limite=500)
    acoes = {a["acao"] for a in tudo}
    conferir("registrou entrada, criacao, abertura, listagem e saida",
             {"entrou", "criou", "abriu", "listou", "saiu"} <= acoes, True)
    conferir("e registrou as tentativas recusadas", "entrada-negada" in acoes, True)

    # Uma tentativa, uma linha - nem zero nem duas. Medido sobre um e-mail que
    # ainda nao apareceu, para o numero nao depender do que os blocos acima
    # fizeram. E-mail que nem existe conta igual: e assim que se ve alguem
    # varrendo enderecos.
    antes_negadas = len(contas.acessos(limite=500))
    for senha in ("chute-um-um-um", "chute-dois-dois", "chute-tres-tres"):
        anonimo.post("/login", data={"email": "fantasma@x.adv.br", "senha": senha})
    novas = contas.acessos(limite=500, email="fantasma@x.adv.br")
    conferir("tres tentativas, tres linhas", len(novas), 3)
    conferir("e nada alem delas foi registrado",
             len(contas.acessos(limite=500)) - antes_negadas, 3)
    conferir("e-mail que nem existe tambem deixa rastro",
             {a["acao"] for a in novas}, {"entrada-negada"})

    # A ana ficou bloqueada no bloco 4. Tentativa barrada pelo bloqueio tambem e
    # tentativa: sem esta linha, o registro pararia de contar justamente quando o
    # ataque esta no auge.
    antes = len(contas.acessos(limite=500, email="ana@a.adv.br"))
    anonimo.post("/login", data={"email": "ana@a.adv.br", "senha": "senha-da-ana-123"})
    conferir("recusa por bloqueio tambem e registrada",
             len(contas.acessos(limite=500, email="ana@a.adv.br")), antes + 1)

    # Nascer e mudar sao eventos diferentes para quem le o registro depois.
    # Usuario proprio: a Ana ficou bloqueada e a Bia, desativada, nos blocos acima.
    contas.criar_usuario(a, "caio@a.adv.br", "Caio", "senha-do-caio-123")
    novo = cliente()
    novo.post("/login", data={"email": "caio@a.adv.br", "senha": "senha-do-caio-123"})
    id_novo = novo.post("/caso/salvar", data={"caso_nome": "Caso que nasce"}).json()["id"]
    novo.post("/caso/salvar", data={"caso_nome": "Caso que muda", "caso_id": str(id_novo)})
    conferir("o mesmo caso sai como criou e depois salvou",
             [x["acao"] for x in contas.acessos(caso_id=id_novo, escritorio_id=a)],
             ["salvou", "criou"])

    # O numero do caso so identifica um caso JUNTO com o escritorio: cada arquivo
    # numera do 1. Quem investigar sem o escritorio recebe os dois, e tem de ver
    # isso, nao descobrir depois.
    escritorios_do_numero = {x["escritorio_id"] for x in contas.acessos(limite=500, caso_id=id_novo)}
    conferir("o mesmo numero existe em mais de um escritorio", escritorios_do_numero, {a, b})
    conferir("e o filtro por escritorio separa",
             {x["escritorio_id"] for x in contas.acessos(limite=500, caso_id=id_novo, escritorio_id=a)},
             {a})

    conferir("o caso aberto ficou pelo numero", bool(contas.acessos(caso_id=id_a)), True)
    conferir("a entrada tambem carrega o escritorio",
             {x["escritorio_id"] for x in contas.acessos(limite=500, email="caio@a.adv.br")
              if x["acao"] == "entrou"}, {a})
    conferir("o filtro por e-mail so traz o dele",
             {a["email"] for a in contas.acessos(limite=500, email="bia@b.adv.br")},
             {"bia@b.adv.br"})

    # A acao de cada uma fica com o escritorio dela: sem isso o registro nao
    # responde "quem, de qual escritorio, abriu o caso".
    de_bia = [a for a in contas.acessos(limite=500, email="bia@b.adv.br") if a["escritorio_id"]]
    conferir("cada acao carrega o escritorio de quem a fez",
             {a["escritorio_id"] for a in de_bia}, {b})
    # A entrada-negada acontece antes de existir sessao: nao ha escritorio ainda.
    negadas = [a for a in tudo if a["acao"] == "entrada-negada"]
    conferir("tentativa recusada nao inventa escritorio",
             {a["escritorio_id"] for a in negadas}, {None})

    conferir("o mais recente vem primeiro", tudo == sorted(tudo, key=lambda a: (a["em"], a["id"]), reverse=True), True)

    # O rastro nao pode morrer com o usuario: e depois de desativar alguem que se
    # vai perguntar o que essa pessoa andou abrindo. A Bia foi desativada no
    # bloco 4, e as linhas dela continuam la.
    conferir("usuario desativado nao apaga o rastro dele",
             bool(contas.acessos(limite=500, email="bia@b.adv.br")), True)

    # Prazo: o que passou da retencao sai, o resto fica.
    with contas.closing(contas.conectar()) as con, con:
        con.execute(
            "INSERT INTO acessos (em, acao, email, escritorio_id, caso_id, ip) VALUES (?, ?, ?, ?, ?, ?)",
            ((contas._agora() - contas.RETENCAO - timedelta(days=1)).isoformat(),
             "abriu", "antiga@a.adv.br", a, 1, "127.0.0.1"),
        )
    conferir("a linha velha entrou", bool(contas.acessos(limite=500, email="antiga@a.adv.br")), True)
    antes = len(contas.acessos(limite=500))
    saiu = contas.limpar_acessos()
    conferir("a limpeza tira so a velha", (saiu, len(contas.acessos(limite=500))), (1, antes - 1))
    conferir("e ela nao esta mais la", contas.acessos(limite=500, email="antiga@a.adv.br"), [])

    # --- 6. trocar a propria senha ----------------------------------------------

    print("\ntrocar a propria senha")

    # O Caio, do bloco anterior, esta logado. Uma segunda sessao dele, aberta
    # noutro aparelho, serve para ver se a troca derruba as duas.
    outro = cliente()
    outro.post("/login", data={"email": "caio@a.adv.br", "senha": "senha-do-caio-123"})
    conferir("o Caio tem duas sessoes abertas", outro.get("/").status_code, 200)

    conferir("sem sessao, /conta vai para o login", anonimo.get("/conta").status_code, 303)
    r = novo.get("/conta")
    conferir("logado, a tela abre", (r.status_code, "Trocar a senha" in r.text), (200, True))

    def trocar(**campos):
        return novo.post("/conta/senha", data={"atual": "senha-do-caio-123",
                                               "nova": "nova-senha-do-caio",
                                               "repetida": "nova-senha-do-caio", **campos})

    r = trocar(atual="senha-errada-errada")
    conferir("senha atual errada e recusada", (r.status_code, "não confere" in r.text), (400, True))
    r = trocar(repetida="outra-coisa-qualquer")
    conferir("as duas novas precisam bater", (r.status_code, "não são iguais" in r.text), (400, True))
    r = trocar(nova="curta", repetida="curta")
    conferir("senha curta e recusada", (r.status_code, "pelo menos" in r.text), (400, True))
    r = trocar(nova="senha-do-caio-123", repetida="senha-do-caio-123")
    conferir("senha nova igual a atual e recusada", (r.status_code, "igual" in r.text), (400, True))

    # Nenhuma das recusas pode ter trocado a senha pelo caminho.
    conferir("depois das recusas, a senha antiga ainda vale",
             contas.entrar("caio@a.adv.br", "senha-do-caio-123") is not None, True)

    r = trocar()
    conferir("a troca boa redireciona para o login",
             (r.status_code, r.headers.get("location")), (303, "/login"))
    conferir("a senha nova vale", contas.entrar("caio@a.adv.br", "nova-senha-do-caio") is not None, True)
    conferir("a antiga nao vale mais", contas.entrar("caio@a.adv.br", "senha-do-caio-123"), None)

    # Trocar senha e o que se faz quando se desconfia que alguem entrou. Manter
    # aberta a sessao do possivel invasor esvaziaria o gesto.
    conferir("a sessao de quem trocou cai", novo.get("/").status_code, 303)
    conferir("e a do outro aparelho tambem", outro.get("/").status_code, 303)

    acoes_caio = [x["acao"] for x in contas.acessos(limite=500, email="caio@a.adv.br")]
    conferir("a troca ficou registrada", "trocou-senha" in acoes_caio, True)
    conferir("a tentativa com senha errada tambem", "troca-de-senha-negada" in acoes_caio, True)

    # --- 7. importar casos de uma instalacao local ------------------------------

    print("\nimportar casos de uma instalacao local")

    # O arquivo de quem usava o sistema na propria maquina.
    local_db = temp / "vindo-de-casa.db"
    persistencia.salvar(local_db, "Cliente da maquina dela", {"funcao": "Pedreiro"})
    persistencia.salvar(local_db, "Outro cliente", {"funcao": "Vendedora"})

    destino = contas.banco_de_casos(a)
    antes = len(persistencia.listar(destino))
    r = persistencia.importar(local_db, destino)
    conferir("importa os dois", r, {"importados": 2, "iguais": 0})
    nomes = {c["nome"] for c in persistencia.listar(destino)}
    conferir("os dois chegaram", {"Cliente da maquina dela", "Outro cliente"} <= nomes, True)
    conferir("e nada do que ja estava la sumiu", len(persistencia.listar(destino)), antes + 2)

    # O numero e novo no destino: os dois arquivos numeram do 1, e reaproveitar o
    # numero sobrescreveria trabalho alheio.
    importado = next(c for c in persistencia.listar(destino) if c["nome"] == "Outro cliente")
    conferir("o caso ganhou numero novo", importado["id"] > antes, True)
    conferir("e o caso que ja existia continua o mesmo",
             persistencia.carregar(destino, id_a)[0], "Cliente da Ana")

    # Rodar duas vezes duplica - e a regra e nunca decidir por quem importa -,
    # mas o comando AVISA, que e o que separa o acidente do silencio.
    r = persistencia.importar(local_db, destino)
    conferir("a segunda vez avisa que ja estavam la", r, {"importados": 2, "iguais": 2})

    # A origem e aberta somente leitura: costuma ser a unica copia de quem importa.
    conferir("a origem fica intacta", len(persistencia.listar(local_db)), 2)

    # Apontar para contas.db ou corpus.db por engano e o erro facil: sao todos
    # .db, na mesma pasta.
    try:
        persistencia.importar(contas.DADOS / "contas.db", destino)
        conferir("arquivo que nao e de casos e recusado", False, True)
    except ValueError as erro:
        conferir("arquivo que nao e de casos e recusado", "nao e um banco de casos" in str(erro), True)
    try:
        persistencia.importar(temp / "nao-existe.db", destino)
        conferir("arquivo inexistente e recusado", False, True)
    except FileNotFoundError:
        conferir("arquivo inexistente e recusado", True, True)

    # E o escritorio B continua sem ver nada disso.
    conferir("o outro escritorio nao recebeu nada",
             any(c["nome"] == "Outro cliente" for c in persistencia.listar(contas.banco_de_casos(b))),
             False)

    # --- 8. modo local ----------------------------------------------------------

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

    # Sem login nao ha "quem": uma linha dizendo "alguem nesta maquina abriu o
    # caso 7" nao responde a pergunta que o registro existe para responder.
    quantas = len(contas.acessos(limite=500))
    local.get("/casos")
    local.get(f"/caso/{id_l}")
    local.post("/caso/salvar", data={"caso_nome": "Outro caso local"})
    conferir("no modo local nada e registrado", len(contas.acessos(limite=500)), quantas)
finally:
    contas.DADOS, contas.MODO, persistencia.BANCO = dados_originais, modo_original, banco_original
    shutil.rmtree(temp, ignore_errors=True)

if falhas:
    print("\nFALHOU")
    for f in falhas:
        print("  " + f)
    raise SystemExit(1)
print("\nlogin e isolamento ok")
