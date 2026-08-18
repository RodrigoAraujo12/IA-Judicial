"""Persistencia local em SQLite.

Fonte da verdade do sistema. Quando o indice vetorial entrar (fase 3), ele sera
apenas indice - reconstruivel a partir daqui e descartavel a qualquer momento.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

BANCO = Path(__file__).parent.parent / "dados" / "casos.db"

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


def conectar() -> sqlite3.Connection:
    BANCO.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(BANCO)
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    return con


def salvar(nome: str, respostas: dict[str, Any], caso_id: int | None = None) -> int:
    agora = datetime.now().isoformat(timespec="seconds")
    dados = json.dumps(respostas, ensure_ascii=False, default=str)
    with conectar() as con:
        if caso_id:
            con.execute(
                "UPDATE casos SET nome = ?, respostas = ?, atualizado_em = ? WHERE id = ?",
                (nome, dados, agora, caso_id),
            )
            return caso_id
        cur = con.execute(
            "INSERT INTO casos (nome, criado_em, atualizado_em, respostas) VALUES (?, ?, ?, ?)",
            (nome, agora, agora, dados),
        )
        return int(cur.lastrowid)


def carregar(caso_id: int) -> tuple[str, dict[str, Any]] | None:
    with conectar() as con:
        linha = con.execute("SELECT nome, respostas FROM casos WHERE id = ?", (caso_id,)).fetchone()
    if linha is None:
        return None
    return linha["nome"], json.loads(linha["respostas"])


def listar(limite: int = 50) -> list[dict[str, Any]]:
    with conectar() as con:
        linhas = con.execute(
            "SELECT id, nome, atualizado_em FROM casos ORDER BY atualizado_em DESC LIMIT ?",
            (limite,),
        ).fetchall()
    return [dict(linha) for linha in linhas]


def excluir(caso_id: int) -> None:
    with conectar() as con:
        con.execute("DELETE FROM casos WHERE id = ?", (caso_id,))
