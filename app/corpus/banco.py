"""Indice do corpus normativo em SQLite.

Arquivo SEPARADO de dados/casos.db, e a separacao e proposital: casos.db guarda
dado de cliente e e a fonte da verdade; corpus.db e indice - reconstruivel a
partir das fontes publicas e descartavel a qualquer momento. Ciclos de vida
diferentes, backups diferentes, riscos de LGPD diferentes.

Tres decisoes de esquema:

**Vigencia por dispositivo, nao por obra.** O art. 71 par. 4o tem uma redacao ate
10/11/2017 e outra depois. Um indice que guarda so a redacao atual responde a
pergunta errada num contrato de 2016 - com a mesma cara de quem acerta. Por isso
a chave e (urn, vigencia_inicio) e toda consulta passa por uma data.

**Fonte com hash e data de captura.** O projeto ja recusa numero que nao se
explica linha a linha. O analogo aqui: citacao que nao se rastreia ate uma URL e
uma data de captura nao entra na peca.

**`texto` e `texto_indexado` sao coisas distintas.** `texto` e o dispositivo
literal, que e o que se cita. `texto_indexado` acrescenta rotulo e caminho
hierarquico, que e o que se busca - sem isso o par. 4o solto perde o "art. 71" e
some tanto do BM25 quanto do vetor denso.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

BANCO = Path(__file__).parent.parent.parent / "dados" / "corpus.db"

ESQUEMA = """
PRAGMA journal_mode = WAL;

-- De onde veio cada texto. Sem isso a citacao nao e auditavel.
CREATE TABLE IF NOT EXISTS fontes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    obra         TEXT NOT NULL,
    url          TEXT NOT NULL,
    capturado_em TEXT NOT NULL,
    sha256       TEXT NOT NULL,
    bytes        INTEGER NOT NULL,
    UNIQUE (obra, sha256)
);

-- Um dispositivo numa dada redacao. A mesma urn aparece varias vezes quando o
-- texto mudou: e assim que o corte da Reforma vira consulta em vez de aviso.
CREATE TABLE IF NOT EXISTS dispositivos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    urn             TEXT NOT NULL,
    obra            TEXT NOT NULL,
    especie         TEXT NOT NULL,
    rotulo          TEXT NOT NULL,
    texto           TEXT NOT NULL,
    texto_indexado  TEXT NOT NULL,
    pai             TEXT,
    ordem           INTEGER NOT NULL,
    vigencia_inicio TEXT NOT NULL,
    vigencia_fim    TEXT,
    alterado_por    TEXT,
    fonte_id        INTEGER NOT NULL REFERENCES fontes(id),
    UNIQUE (urn, vigencia_inicio)
);

CREATE INDEX IF NOT EXISTS idx_disp_urn   ON dispositivos(urn);
CREATE INDEX IF NOT EXISTS idx_disp_obra  ON dispositivos(obra, ordem);
CREATE INDEX IF NOT EXISTS idx_disp_pai   ON dispositivos(pai);

-- Via 1 (esparsa). remove_diacritics 2 porque o catalogo e as consultas do
-- escritorio sao escritos sem acento: "extraordinaria" tem de casar
-- "extraordinaria" com acento.
CREATE VIRTUAL TABLE IF NOT EXISTS dispositivos_fts USING fts5(
    rotulo,
    texto_indexado,
    content = 'dispositivos',
    content_rowid = 'id',
    tokenize = "unicode61 remove_diacritics 2"
);

CREATE TRIGGER IF NOT EXISTS disp_ai AFTER INSERT ON dispositivos BEGIN
    INSERT INTO dispositivos_fts(rowid, rotulo, texto_indexado)
    VALUES (new.id, new.rotulo, new.texto_indexado);
END;
CREATE TRIGGER IF NOT EXISTS disp_ad AFTER DELETE ON dispositivos BEGIN
    INSERT INTO dispositivos_fts(dispositivos_fts, rowid, rotulo, texto_indexado)
    VALUES ('delete', old.id, old.rotulo, old.texto_indexado);
END;
CREATE TRIGGER IF NOT EXISTS disp_au AFTER UPDATE ON dispositivos BEGIN
    INSERT INTO dispositivos_fts(dispositivos_fts, rowid, rotulo, texto_indexado)
    VALUES ('delete', old.id, old.rotulo, old.texto_indexado);
    INSERT INTO dispositivos_fts(rowid, rotulo, texto_indexado)
    VALUES (new.id, new.rotulo, new.texto_indexado);
END;

-- Via 2 (densa) e os pesos lexicais do BGE-M3. `denso` e float32 cru; `esparso`
-- e JSON {token: peso}. Tabela a parte para que trocar de modelo de embedding
-- seja um DELETE, e nao uma reingestao do corpus inteiro.
CREATE TABLE IF NOT EXISTS vetores (
    dispositivo_id INTEGER NOT NULL REFERENCES dispositivos(id) ON DELETE CASCADE,
    modelo         TEXT NOT NULL,
    dim            INTEGER NOT NULL,
    denso          BLOB NOT NULL,
    esparso        TEXT,
    PRIMARY KEY (dispositivo_id, modelo)
);
"""


@dataclass
class Dispositivo:
    urn: str
    obra: str
    especie: str
    rotulo: str
    texto: str
    texto_indexado: str
    ordem: int
    vigencia_inicio: str
    pai: str | None = None
    vigencia_fim: str | None = None
    alterado_por: str | None = None
    id: int | None = None


def conectar(caminho: Path | None = None) -> sqlite3.Connection:
    destino = caminho or BANCO
    destino.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(destino)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(ESQUEMA)
    return con


def registrar_fonte(con: sqlite3.Connection, obra: str, url: str, bruto: bytes) -> int:
    """Grava a captura. Reingerir o mesmo conteudo devolve a fonte existente."""
    sha = hashlib.sha256(bruto).hexdigest()
    linha = con.execute(
        "SELECT id FROM fontes WHERE obra = ? AND sha256 = ?", (obra, sha)
    ).fetchone()
    if linha:
        return int(linha["id"])
    cur = con.execute(
        "INSERT INTO fontes (obra, url, capturado_em, sha256, bytes) VALUES (?, ?, ?, ?, ?)",
        (obra, url, datetime.now().isoformat(timespec="seconds"), sha, len(bruto)),
    )
    return int(cur.lastrowid)


def gravar(con: sqlite3.Connection, dispositivos: list[Dispositivo], fonte_id: int) -> int:
    con.executemany(
        """INSERT OR REPLACE INTO dispositivos
           (urn, obra, especie, rotulo, texto, texto_indexado, pai, ordem,
            vigencia_inicio, vigencia_fim, alterado_por, fonte_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                d.urn, d.obra, d.especie, d.rotulo, d.texto, d.texto_indexado,
                d.pai, d.ordem, d.vigencia_inicio, d.vigencia_fim, d.alterado_por,
                fonte_id,
            )
            for d in dispositivos
        ],
    )
    return len(dispositivos)


def vigente_em(
    con: sqlite3.Connection, urn: str, quando: date | None = None
) -> sqlite3.Row | None:
    """A redacao de `urn` em vigor na data dada.

    `quando` e obrigatoriamente uma data do CASO, nunca hoje por conveniencia:
    verba de 2016 se rege pela redacao de 2016.
    """
    ref = (quando or date.today()).isoformat()
    return con.execute(
        """SELECT * FROM dispositivos
           WHERE urn = ?
             AND vigencia_inicio <= ?
             AND (vigencia_fim IS NULL OR vigencia_fim >= ?)
           ORDER BY vigencia_inicio DESC LIMIT 1""",
        (urn, ref, ref),
    ).fetchone()


def redacoes(con: sqlite3.Connection, urn: str) -> list[sqlite3.Row]:
    """Todas as redacoes ja tidas por um dispositivo, da mais antiga para a atual."""
    return con.execute(
        "SELECT * FROM dispositivos WHERE urn = ? ORDER BY vigencia_inicio", (urn,)
    ).fetchall()


def estatisticas(con: sqlite3.Connection) -> dict[str, int]:
    def um(sql: str) -> int:
        return int(con.execute(sql).fetchone()[0])

    return {
        "obras": um("SELECT COUNT(DISTINCT obra) FROM dispositivos"),
        "dispositivos": um("SELECT COUNT(DISTINCT urn) FROM dispositivos"),
        "redacoes": um("SELECT COUNT(*) FROM dispositivos"),
        "com_vetor": um("SELECT COUNT(*) FROM vetores"),
        "fontes": um("SELECT COUNT(*) FROM fontes"),
    }
