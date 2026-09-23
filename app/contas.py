"""Escritorios, usuarios e sessoes - o que o sistema precisa para virar servico.

    python -m app.contas criar-escritorio "Silva & Souza Advogados"
    python -m app.contas criar-usuario 1 ana@silvasouza.adv.br "Ana Silva"
    python -m app.contas listar
    python -m app.contas redefinir-senha ana@silvasouza.adv.br
    python -m app.contas desativar ana@silvasouza.adv.br
    python -m app.contas acessos                        # as ultimas 50 acoes
    python -m app.contas acessos ana@silvasouza.adv.br  # so as dela
    python -m app.contas acessos caso:7                 # quem abriu o caso 7
    python -m app.contas acessos caso:7@1               # ... no escritorio 1
    python -m app.contas importar-casos 1 /tmp/casos.db # casos de uma instalacao local

**Dois modos, escolhidos por variavel de ambiente, nunca por deducao.**

- `TRIAGEM_MODO=local` (o padrao) e o produto de hoje: sem login, um
  `dados/casos.db` so, e o servidor so atende a propria maquina.
- `TRIAGEM_MODO=servico` exige login em toda rota, e cada escritorio tem o seu
  arquivo de casos: `dados/escritorios/<id>/casos.db`.

O modo nao e inferido da existencia de `contas.db` de proposito. Inferencia erra
em silencio: um arquivo apagado por engano desligaria o login de um servidor na
internet, com dado de saude de cliente atras. Variavel esquecida tambem erra, e
por isso o modo local recusa quem nao for a propria maquina - o esquecimento
aparece como 403 na primeira requisicao, e nao como sistema aberto.

**Um arquivo de casos por escritorio.** O erro que o servico nao pode cometer e um
escritorio ver o cliente de outro. Num banco unico com coluna de escritorio, basta
uma consulta que esqueca o filtro. Aqui o caminho do arquivo sai da sessao - de um
inteiro gravado em `contas.db`, nunca de algo que o navegador mande -, e o banco de
outro escritorio nao esta aberto para ser consultado. Encerrar um contrato e
apagar uma pasta, que e o que a LGPD pede ao operador no fim do tratamento.

**Senha com scrypt da biblioteca padrao.** Nenhuma dependencia nova, e o scrypt e
lento de proposito: vazar `contas.db` nao entrega as senhas.

**A sessao guarda o hash do token, nao o token.** Quem copia o banco nao herda as
sessoes abertas.

**O registro de acesso responde "quem abriu qual caso, e quando".** E o que a
LGPD cobra do operador (art. 37) e o que se consulta depois de um incidente. Ele
guarda o e-mail como COPIA, para sobreviver ao usuario desativado, e tem prazo -
`RETENCAO` -, porque quem abriu o que tambem e dado pessoal. Fica em `contas.db`,
e nao no arquivo do escritorio: o rastro nao pode morar no mesmo lugar que a
coisa cujo acesso ele registra, ou apagar a pasta apaga a prova.
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import hmac
import os
import secrets
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

MODO = os.environ.get("TRIAGEM_MODO", "local").strip().lower()
if MODO not in ("local", "servico"):
    # Valor desconhecido nao vira "local" por omissao: seria desligar o login de
    # um servidor por causa de um erro de digitacao.
    raise SystemExit(f"TRIAGEM_MODO invalido: {MODO!r}. Use 'local' ou 'servico'.")

# Contas e casos: o que precisa de backup, e nada mais. Num servidor mora fora da
# pasta do codigo (TRIAGEM_DADOS=/var/lib/triagem), onde atualizar o codigo nao
# encosta nela. O corpus e o modelo ficam em `dados/` e `modelos/` de qualquer
# jeito - sao reconstruiveis e nao entram no backup.
DADOS = Path(os.environ.get("TRIAGEM_DADOS") or Path(__file__).parent.parent / "dados")

# Um expediente. Sessao que dura semanas e sessao que alguem esquece aberta no
# computador da recepcao.
DURACAO = timedelta(hours=12)
SENHA_MINIMA = 10
# Dez erros em quinze minutos travam o e-mail por quinze minutos. Nao impede quem
# tenta devagar, mas tira do alcance quem tenta um dicionario.
TENTATIVAS = 10
JANELA = timedelta(minutes=15)

# Por quanto tempo o registro de acesso e guardado. Precisa ser maior que o
# intervalo entre um incidente e a descoberta dele, que costuma ser de meses -
# registro que expira antes disso nao responde nada. Tambem nao e para sempre:
# quem abriu qual caso e, ele proprio, dado pessoal, e guardar sem prazo
# contraria a minimizacao do art. 6o, III, da LGPD.
RETENCAO = timedelta(days=180)

# scrypt: N=2^14, r=8, p=1 e o minimo recomendado para login interativo, e leva
# ~50 ms aqui. O custo vai gravado junto do hash, para poder subir depois sem
# invalidar as senhas antigas.
_N, _R, _P = 2**14, 8, 1

ESQUEMA = """
CREATE TABLE IF NOT EXISTS escritorios (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nome       TEXT NOT NULL,
    criado_em  TEXT NOT NULL,
    ativo      INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS usuarios (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    escritorio_id  INTEGER NOT NULL REFERENCES escritorios(id),
    email          TEXT NOT NULL UNIQUE COLLATE NOCASE,
    nome           TEXT NOT NULL,
    senha          TEXT NOT NULL,
    criado_em      TEXT NOT NULL,
    ativo          INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS sessoes (
    token_hash  TEXT PRIMARY KEY,
    usuario_id  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    criada_em   TEXT NOT NULL,
    expira_em   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tentativas (
    email  TEXT NOT NULL COLLATE NOCASE,
    em     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tentativas ON tentativas(email, em);

-- Quem abriu qual caso, e quando. Ver "registro de acesso", abaixo.
--
-- `email` e `escritorio` sao COPIAS, nao referencias, e nao ha chave estrangeira
-- nenhuma aqui. E deliberado: o rastro tem de continuar legivel depois que o
-- usuario for desativado e o escritorio encerrado - que e justamente quando
-- alguem vai perguntar o que aconteceu. Uma FK com CASCADE apagaria a resposta
-- junto com a pergunta.
CREATE TABLE IF NOT EXISTS acessos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    em            TEXT NOT NULL,
    acao          TEXT NOT NULL,
    email         TEXT NOT NULL,
    escritorio_id INTEGER,
    caso_id       INTEGER,
    ip            TEXT
);
CREATE INDEX IF NOT EXISTS idx_acessos_em    ON acessos(em DESC);
CREATE INDEX IF NOT EXISTS idx_acessos_email ON acessos(email, em DESC);
CREATE INDEX IF NOT EXISTS idx_acessos_caso  ON acessos(caso_id, em DESC);
"""


@dataclass(frozen=True)
class Usuario:
    id: int
    nome: str
    email: str
    escritorio_id: int
    escritorio: str


def conectar() -> sqlite3.Connection:
    DADOS.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DADOS / "contas.db")
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(ESQUEMA)
    return con


def banco_de_casos(escritorio_id: int) -> Path:
    """O arquivo de casos do escritorio. So recebe inteiro vindo da sessao."""
    return DADOS / "escritorios" / str(int(escritorio_id)) / "casos.db"


def _agora() -> datetime:
    return datetime.now().replace(microsecond=0)


# --- senha --------------------------------------------------------------------


def hash_senha(senha: str) -> str:
    sal = secrets.token_bytes(16)
    chave = hashlib.scrypt(senha.encode(), salt=sal, n=_N, r=_R, p=_P, dklen=32)
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f"scrypt${_N}${_R}${_P}${b64(sal)}${b64(chave)}"


def senha_confere(senha: str, guardado: str) -> bool:
    try:
        _, n, r, p, sal, chave = guardado.split("$")
        calculada = hashlib.scrypt(
            senha.encode(), salt=base64.b64decode(sal), n=int(n), r=int(r), p=int(p), dklen=32
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calculada, base64.b64decode(chave))


# Hash de uma senha qualquer, para gastar o mesmo tempo quando o e-mail nao existe.
# Sem isso a resposta rapida denuncia quais e-mails tem conta.
_HASH_FICTICIO = hash_senha(secrets.token_urlsafe(16))


def _exigir_senha_boa(senha: str) -> None:
    if len(senha) < SENHA_MINIMA:
        raise ValueError(f"a senha precisa de pelo menos {SENHA_MINIMA} caracteres")


# --- cadastro -----------------------------------------------------------------


def criar_escritorio(nome: str) -> int:
    nome = nome.strip()
    if not nome:
        raise ValueError("o escritorio precisa de um nome")
    with closing(conectar()) as con, con:
        cur = con.execute(
            "INSERT INTO escritorios (nome, criado_em) VALUES (?, ?)",
            (nome, _agora().isoformat()),
        )
        escritorio_id = int(cur.lastrowid)
    banco_de_casos(escritorio_id).parent.mkdir(parents=True, exist_ok=True)
    return escritorio_id


def criar_usuario(escritorio_id: int, email: str, nome: str, senha: str) -> int:
    _exigir_senha_boa(senha)
    email, nome = email.strip(), nome.strip()
    if "@" not in email or not nome:
        raise ValueError("e-mail e nome sao obrigatorios")
    with closing(conectar()) as con, con:
        if con.execute("SELECT 1 FROM escritorios WHERE id = ?", (escritorio_id,)).fetchone() is None:
            raise ValueError(f"escritorio {escritorio_id} nao existe")
        cur = con.execute(
            """INSERT INTO usuarios (escritorio_id, email, nome, senha, criado_em)
               VALUES (?, ?, ?, ?, ?)""",
            (escritorio_id, email, nome, hash_senha(senha), _agora().isoformat()),
        )
        return int(cur.lastrowid)


def redefinir_senha(email: str, senha: str) -> None:
    _exigir_senha_boa(senha)
    with closing(conectar()) as con, con:
        linha = con.execute("SELECT id FROM usuarios WHERE email = ?", (email,)).fetchone()
        if linha is None:
            raise ValueError(f"usuario {email} nao existe")
        con.execute("UPDATE usuarios SET senha = ? WHERE id = ?", (hash_senha(senha), linha["id"]))
        # Senha nova derruba as sessoes abertas: e para isso que se troca senha.
        con.execute("DELETE FROM sessoes WHERE usuario_id = ?", (linha["id"],))


def trocar_senha(email: str, atual: str, nova: str) -> bool:
    """O proprio usuario troca a senha. False quando a senha atual nao confere.

    Diferente de `redefinir_senha`, que e do administrador e nao pergunta nada:
    aqui a senha atual e exigida. Sem isso, um computador deixado aberto na
    recepcao viraria uma conta tomada - quem passasse trocaria a senha e o dono
    perderia o acesso.

    Derruba TODAS as sessoes, inclusive a de quem trocou. Trocar senha e o que se
    faz quando se desconfia que alguem entrou; manter aberta a sessao de quem
    talvez seja o invasor esvaziaria o gesto. O preco e entrar de novo.
    """
    _exigir_senha_boa(nova)
    with closing(conectar()) as con, con:
        linha = con.execute(
            "SELECT id, senha FROM usuarios WHERE email = ? AND ativo = 1", (email,)
        ).fetchone()
        if linha is None or not senha_confere(atual, linha["senha"]):
            return False
        con.execute("UPDATE usuarios SET senha = ? WHERE id = ?", (hash_senha(nova), linha["id"]))
        con.execute("DELETE FROM sessoes WHERE usuario_id = ?", (linha["id"],))
        return True


def desativar(email: str) -> None:
    with closing(conectar()) as con, con:
        linha = con.execute("SELECT id FROM usuarios WHERE email = ?", (email,)).fetchone()
        if linha is None:
            raise ValueError(f"usuario {email} nao existe")
        con.execute("UPDATE usuarios SET ativo = 0 WHERE id = ?", (linha["id"],))
        con.execute("DELETE FROM sessoes WHERE usuario_id = ?", (linha["id"],))


# --- entrada e sessao ---------------------------------------------------------


def bloqueado(email: str) -> bool:
    desde = (_agora() - JANELA).isoformat()
    with closing(conectar()) as con:
        n = con.execute(
            "SELECT COUNT(*) FROM tentativas WHERE email = ? AND em > ?", (email.strip(), desde)
        ).fetchone()[0]
    return n >= TENTATIVAS


def entrar(email: str, senha: str) -> str | None:
    """Confere a senha e abre uma sessao. Devolve o token, ou None.

    None nao diz se o erro foi o e-mail ou a senha - dizer seria confirmar a
    terceiros quais e-mails tem conta. Usuario ou escritorio desativado tambem
    e None.
    """
    email = email.strip()
    with closing(conectar()) as con, con:
        linha = con.execute(
            """SELECT u.id, u.senha FROM usuarios u
                 JOIN escritorios e ON e.id = u.escritorio_id
                WHERE u.email = ? AND u.ativo = 1 AND e.ativo = 1""",
            (email,),
        ).fetchone()
        if linha is None:
            senha_confere(senha, _HASH_FICTICIO)
            con.execute("INSERT INTO tentativas (email, em) VALUES (?, ?)", (email, _agora().isoformat()))
            return None
        if not senha_confere(senha, linha["senha"]):
            con.execute("INSERT INTO tentativas (email, em) VALUES (?, ?)", (email, _agora().isoformat()))
            return None

        con.execute("DELETE FROM tentativas WHERE email = ?", (email,))
        con.execute("DELETE FROM sessoes WHERE expira_em < ?", (_agora().isoformat(),))
        # O registro de acesso tem prazo, e o login e a hora barata de cobra-lo:
        # acontece poucas vezes ao dia, ja esta numa transacao de escrita, e nao
        # exige tarefa agendada nenhuma para lembrar disso.
        con.execute("DELETE FROM acessos WHERE em < ?", ((_agora() - RETENCAO).isoformat(),))
        token = secrets.token_urlsafe(32)
        con.execute(
            "INSERT INTO sessoes (token_hash, usuario_id, criada_em, expira_em) VALUES (?, ?, ?, ?)",
            (_hash_token(token), linha["id"], _agora().isoformat(), (_agora() + DURACAO).isoformat()),
        )
        return token


def sessao(token: str) -> Usuario | None:
    """O usuario dono do token, se a sessao existe, nao expirou e ninguem foi desativado."""
    with closing(conectar()) as con:
        linha = con.execute(
            """SELECT u.id, u.nome, u.email, u.escritorio_id, e.nome AS escritorio
                 FROM sessoes s
                 JOIN usuarios u ON u.id = s.usuario_id
                 JOIN escritorios e ON e.id = u.escritorio_id
                WHERE s.token_hash = ? AND s.expira_em > ? AND u.ativo = 1 AND e.ativo = 1""",
            (_hash_token(token), _agora().isoformat()),
        ).fetchone()
    return Usuario(**dict(linha)) if linha else None


def sair(token: str) -> None:
    with closing(conectar()) as con, con:
        con.execute("DELETE FROM sessoes WHERE token_hash = ?", (_hash_token(token),))


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# --- registro de acesso -------------------------------------------------------


def registrar(
    acao: str,
    usuario: Usuario | None = None,
    *,
    email: str = "",
    caso_id: int | None = None,
    ip: str | None = None,
) -> None:
    """Anota uma acao sobre dado de cliente. So no modo servico.

    **No modo local nao registra**, e nao e esquecimento: sem login nao ha "quem",
    e uma linha dizendo "alguem nesta maquina abriu o caso 7" nao responde a
    pergunta que o registro existe para responder. O registro nasce com o
    servico, porque e ali que escritorio e operador sao pessoas diferentes.

    **Falha aqui nao derruba o atendimento.** Um disco cheio nao pode impedir uma
    advogada de abrir o caso dela no meio de uma audiencia. Mas tambem nao pode
    passar calado: a falha vai para o log do servidor, onde o monitoramento a ve.
    """
    if MODO != "servico":
        return
    if usuario is not None:
        email = usuario.email
        escritorio_id = usuario.escritorio_id
    else:
        escritorio_id = None
    try:
        with closing(conectar()) as con, con:
            con.execute(
                "INSERT INTO acessos (em, acao, email, escritorio_id, caso_id, ip)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (_agora().isoformat(), acao, email, escritorio_id, caso_id, ip),
            )
    except sqlite3.Error as erro:  # noqa: BLE001 - a acao do usuario segue, o aviso nao
        print(f"AVISO: registro de acesso falhou ({acao}): {erro}", file=sys.stderr)


def acessos(
    limite: int = 50,
    email: str | None = None,
    caso_id: int | None = None,
    escritorio_id: int | None = None,
) -> list[dict[str, Any]]:
    """As ultimas acoes registradas, da mais recente para a mais antiga.

    **O numero do caso so identifica um caso junto com o escritorio.** Cada
    arquivo numera do 1, entao existe um caso nº 7 em cada escritorio, e filtrar
    so por `caso_id` traz os dois. E consequencia direta de um arquivo por
    escritorio - a mesma escolha que impede um de ver o outro. Quem investiga um
    caso especifico passa os dois; quem varre por numero ve a coluna do
    escritorio e sabe separar.
    """
    onde, params = [], []
    if email:
        onde.append("email = ?")
        params.append(email.strip())
    if caso_id is not None:
        onde.append("caso_id = ?")
        params.append(caso_id)
    if escritorio_id is not None:
        onde.append("escritorio_id = ?")
        params.append(escritorio_id)
    filtro = f" WHERE {' AND '.join(onde)}" if onde else ""
    with closing(conectar()) as con:
        linhas = con.execute(
            f"SELECT * FROM acessos{filtro} ORDER BY em DESC, id DESC LIMIT ?",
            (*params, int(limite)),
        ).fetchall()
    return [dict(l) for l in linhas]


def limpar_acessos(agora: datetime | None = None) -> int:
    """Descarta o que passou de `RETENCAO`. Devolve quantas linhas sairam."""
    corte = ((agora or _agora()) - RETENCAO).isoformat()
    with closing(conectar()) as con, con:
        return int(con.execute("DELETE FROM acessos WHERE em < ?", (corte,)).rowcount)


# --- linha de comando ---------------------------------------------------------


def _pedir_senha() -> str:
    senha = getpass.getpass(f"senha (minimo {SENHA_MINIMA} caracteres): ")
    if senha != getpass.getpass("repita: "):
        raise SystemExit("as senhas nao conferem")
    return senha


def main(args: list[str]) -> None:
    comando, *resto = args or ["ajuda"]
    try:
        if comando == "criar-escritorio" and len(resto) == 1:
            print(f"escritorio #{criar_escritorio(resto[0])} criado")
        elif comando == "criar-usuario" and len(resto) == 3:
            escritorio_id, email, nome = resto
            uid = criar_usuario(int(escritorio_id), email, nome, _pedir_senha())
            print(f"usuario #{uid} criado no escritorio #{escritorio_id}")
        elif comando == "redefinir-senha" and len(resto) == 1:
            redefinir_senha(resto[0], _pedir_senha())
            print("senha trocada; as sessoes abertas foram encerradas")
        elif comando == "desativar" and len(resto) == 1:
            desativar(resto[0])
            print("usuario desativado; as sessoes abertas foram encerradas")
        elif comando == "acessos" and len(resto) <= 1:
            alvo = resto[0] if resto else ""
            if alvo.startswith("caso:"):
                # "caso:7" ou "caso:7@1" - o numero sozinho existe em todos os
                # escritorios, entao sem o "@" a saida traz todos eles.
                numero, _, escritorio = alvo[5:].partition("@")
                linhas = acessos(
                    caso_id=int(numero), escritorio_id=int(escritorio) if escritorio else None
                )
                if not escritorio and len({a["escritorio_id"] for a in linhas}) > 1:
                    print(
                        f"aviso: ha um caso #{numero} em mais de um escritorio. "
                        f"Use 'caso:{numero}@<escritorio>' para separar.\n"
                    )
            else:
                linhas = acessos(email=alvo or None)
            if MODO != "servico":
                print("(modo local: nada e registrado - ver `registrar` em app/contas.py)\n")
            for a in linhas:
                onde = f"esc #{a['escritorio_id']}" if a["escritorio_id"] else ""
                caso = f"caso #{a['caso_id']}" if a["caso_id"] is not None else ""
                print(
                    f"{a['em']}  {a['acao']:<16} {a['email']:<32} "
                    f"{onde:<8} {caso:<10} {a['ip'] or ''}"
                )
            if not linhas:
                print("nenhum acesso registrado com esse filtro")
        elif comando == "importar-casos" and len(resto) == 2:
            from app import persistencia

            escritorio_id, arquivo = int(resto[0]), Path(resto[1])
            with closing(conectar()) as con:
                linha = con.execute(
                    "SELECT nome FROM escritorios WHERE id = ?", (escritorio_id,)
                ).fetchone()
            if linha is None:
                raise ValueError(f"escritorio {escritorio_id} nao existe")
            r = persistencia.importar(arquivo, banco_de_casos(escritorio_id))
            print(f"{r['importados']} casos importados para #{escritorio_id} {linha['nome']}")
            if r["iguais"]:
                print(
                    f"AVISO: {r['iguais']} deles ja existiam la, iguais no nome e nas "
                    "respostas. Foram importados assim mesmo - a importacao nunca decide "
                    "por voce. Se rodou duas vezes sem querer, apague as copias pela tela."
                )
        elif comando == "listar":
            with closing(conectar()) as con:
                for e in con.execute("SELECT * FROM escritorios ORDER BY id"):
                    print(f"#{e['id']} {e['nome']}{'' if e['ativo'] else '  (inativo)'}")
                    for u in con.execute(
                        "SELECT * FROM usuarios WHERE escritorio_id = ? ORDER BY id", (e["id"],)
                    ):
                        print(f"    {u['email']:40} {u['nome']}{'' if u['ativo'] else '  (inativo)'}")
        else:
            print(__doc__.split("\n\n")[1])
            raise SystemExit(1)
    except (ValueError, sqlite3.IntegrityError) as erro:
        raise SystemExit(f"erro: {erro}") from erro


if __name__ == "__main__":
    main(sys.argv[1:])
