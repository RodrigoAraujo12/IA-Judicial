"""Escritorios, usuarios e sessoes - o que o sistema precisa para virar servico.

    python -m app.contas criar-escritorio "Silva & Souza Advogados"
    python -m app.contas criar-usuario 1 ana@silvasouza.adv.br "Ana Silva"
    python -m app.contas listar
    python -m app.contas redefinir-senha ana@silvasouza.adv.br
    python -m app.contas desativar ana@silvasouza.adv.br

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
