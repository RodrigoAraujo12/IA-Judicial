"""Persistencia dos casos em SQLite.

Fonte da verdade do sistema. O indice do corpus e apenas indice - reconstruivel e
descartavel a qualquer momento; os casos, nao.

Toda funcao recebe o arquivo em que vai operar. No modo local e `BANCO`, o mesmo
de sempre; no servico e o arquivo do escritorio de quem esta logado, que
`app.contas.banco_de_casos` deriva da sessao. Nao ha arquivo padrao escondido
aqui dentro de proposito: uma chamada que esquecesse de passar o escritorio
gravaria o caso no banco errado sem erro nenhum.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

# Mesma pasta de `app.contas.DADOS`: TRIAGEM_DADOS quando definida, `dados/` senao.
BANCO = Path(os.environ.get("TRIAGEM_DADOS") or Path(__file__).parent.parent / "dados") / "casos.db"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS casos (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    nome         TEXT NOT NULL,
    criado_em    TEXT NOT NULL,
    atualizado_em TEXT NOT NULL,
    respostas    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_casos_atualizado ON casos(atualizado_em DESC);
"""


# `with sqlite3.connect(...)` commita a transacao e NAO fecha a conexao - e o
# engano mais comum da API. Cada salvar/carregar/listar deixava um handle aberto
# ate o coletor passar; num app que grava a cada alteracao do formulario, isso
# acumula. `closing` por fora e o que de fato fecha.
def conectar(banco: Path) -> sqlite3.Connection:
    banco.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(banco)
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    return con


def salvar(banco: Path, nome: str, respostas: dict[str, Any], caso_id: int | None = None) -> int:
    agora = datetime.now().isoformat(timespec="seconds")
    dados = json.dumps(respostas, ensure_ascii=False, default=str)
    with closing(conectar(banco)) as con, con:
        if caso_id:
            cur = con.execute(
                "UPDATE casos SET nome = ?, respostas = ?, atualizado_em = ? WHERE id = ?",
                (nome, dados, agora, caso_id),
            )
            if cur.rowcount:
                return caso_id
            # Id que nao existe neste banco nao e "atualizar nada" em silencio: o
            # caso vira um novo. Acontece quando a sessao troca de escritorio com
            # uma entrevista aberta na tela - o id era do banco do outro.
        cur = con.execute(
            "INSERT INTO casos (nome, criado_em, atualizado_em, respostas) VALUES (?, ?, ?, ?)",
            (nome, agora, agora, dados),
        )
        return int(cur.lastrowid)


def carregar(banco: Path, caso_id: int) -> tuple[str, dict[str, Any]] | None:
    with closing(conectar(banco)) as con, con:
        linha = con.execute("SELECT nome, respostas FROM casos WHERE id = ?", (caso_id,)).fetchone()
    if linha is None:
        return None
    return linha["nome"], json.loads(linha["respostas"])


def listar(banco: Path, limite: int = 50) -> list[dict[str, Any]]:
    with closing(conectar(banco)) as con, con:
        linhas = con.execute(
            "SELECT id, nome, atualizado_em FROM casos ORDER BY atualizado_em DESC LIMIT ?",
            (limite,),
        ).fetchall()
    return [dict(linha) for linha in linhas]


def importar(origem: Path, destino: Path) -> dict[str, int]:
    """Copia os casos de um arquivo para outro. Nunca sobrescreve nada.

    O caminho de quem usava o sistema na propria maquina e passa a usar o
    servico. Todo caso importado **nasce com numero novo** no destino: os dois
    arquivos numeram do 1, entao o caso nº 3 de um nao e o nº 3 do outro, e
    reaproveitar o numero sobrescreveria trabalho alheio em silencio.

    A origem e aberta SOMENTE LEITURA. Importar nao pode estragar o arquivo de
    quem esta importando - e ele costuma ser a unica copia.

    `iguais` conta os casos que ja existiam no destino com o mesmo nome e as
    mesmas respostas. Eles sao importados assim mesmo, porque a regra e nunca
    decidir por quem importa; o numero serve para avisar quem rodou o comando
    duas vezes sem querer.
    """
    if not origem.exists():
        raise FileNotFoundError(f"nao existe: {origem}")

    con_o = sqlite3.connect(f"file:{origem.as_posix()}?mode=ro", uri=True)
    con_o.row_factory = sqlite3.Row
    try:
        tem = con_o.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'casos'"
        ).fetchone()
        if tem is None:
            # Apontar para corpus.db ou contas.db por engano e o erro facil de
            # cometer: sao todos .db, na mesma pasta. Dizer isso e melhor que
            # importar zero caso e parecer que nao havia nenhum.
            raise ValueError(f"{origem.name} nao e um banco de casos (nao tem a tabela `casos`)")
        vindos = con_o.execute(
            "SELECT nome, criado_em, atualizado_em, respostas FROM casos ORDER BY id"
        ).fetchall()
    finally:
        con_o.close()

    with closing(conectar(destino)) as con, con:
        ja_la = {
            (l["nome"], l["respostas"])
            for l in con.execute("SELECT nome, respostas FROM casos")
        }
        iguais = 0
        for c in vindos:
            if (c["nome"], c["respostas"]) in ja_la:
                iguais += 1
            con.execute(
                """INSERT INTO casos (nome, criado_em, atualizado_em, respostas)
                   VALUES (?, ?, ?, ?)""",
                (c["nome"], c["criado_em"], c["atualizado_em"], c["respostas"]),
            )
    return {"importados": len(vindos), "iguais": iguais}


def excluir(banco: Path, caso_id: int) -> None:
    with closing(conectar(banco)) as con, con:
        con.execute("DELETE FROM casos WHERE id = ?", (caso_id,))
