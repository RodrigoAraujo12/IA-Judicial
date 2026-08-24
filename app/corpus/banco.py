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
    -- Texto que saiu da lei sem que a fonte diga quando. Nunca e servido como
    -- vigente: e melhor nao achar a norma do que achar a revogada achando que
    -- vale. A redacao continua no banco para consulta historica explicita.
    revogado        INTEGER NOT NULL DEFAULT 0,
    alterado_por    TEXT,
    fonte_id        INTEGER NOT NULL REFERENCES fontes(id),
    -- `ordem` entra na chave porque duas redacoes podem cair na mesma data de
    -- inicio quando a fonte nao data a mais antiga. Sem ela, uma sobrescreve a
    -- outra em silencio - e no corpus da CLT isso apagava 956 redacoes.
    UNIQUE (urn, vigencia_inicio, ordem)
);

CREATE INDEX IF NOT EXISTS idx_disp_urn   ON dispositivos(urn);
CREATE INDEX IF NOT EXISTS idx_disp_obra  ON dispositivos(obra, ordem);
CREATE INDEX IF NOT EXISTS idx_disp_pai   ON dispositivos(pai);
-- NAO criar indice sobre (revogado, vigencia_inicio, vigencia_fim). Ja foi
-- tentado, medido e revertido.
--
-- O ganho pretendido era pequeno e real: a via densa monta o conjunto de ids
-- vigentes a cada consulta, e um indice de cobertura levava esse passo de 4,1 ms
-- para 1,3 ms. O custo foi de outra ordem. Com o indice disponivel, o planejador
-- passa a dirigir a consulta LEXICAL por ele - percorre os 2.652 dispositivos
-- vigentes e sonda o FTS uma vez para cada - em vez de partir do MATCH e buscar
-- cada acerto pela chave primaria:
--
--   sem indice   SCAN dispositivos_fts / SEARCH d USING INTEGER PRIMARY KEY    1 ms
--   com indice   SEARCH d USING INDEX / SCAN dispositivos_fts VIRTUAL TABLE  198 ms
--
-- 2,8 ms comprados por 197. Indice que existe e indice que o planejador pode
-- escolher, e aqui a escolha errada e 200 vezes pior que o problema.

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
--
-- `maxlen` guarda o orcamento de tokens com que o vetor foi produzido, porque o
-- vetor nao e funcao so do texto e do modelo: e funcao tambem do quanto do texto
-- o modelo chegou a ver. Sem essa coluna, baixar ou subir MAXLEN deixa no banco
-- vetores de dois regimes diferentes com a mesma cara, e a busca degrada em
-- silencio - que e o modo de falha que este projeto recusa. Com ela, `indexar()`
-- sabe sozinho quais refazer.
CREATE TABLE IF NOT EXISTS vetores (
    dispositivo_id INTEGER NOT NULL REFERENCES dispositivos(id) ON DELETE CASCADE,
    modelo         TEXT NOT NULL,
    dim            INTEGER NOT NULL,
    maxlen         INTEGER,
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
    revogado: bool = False
    alterado_por: str | None = None
    id: int | None = None


def conectar(caminho: Path | None = None) -> sqlite3.Connection:
    destino = caminho or BANCO
    destino.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(destino)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    # `INSERT OR REPLACE` em `dispositivos` apaga a linha em conflito, e sem isto
    # o gatilho AFTER DELETE do FTS nao dispara: a entrada velha fica no indice
    # apontando para um rowid cujo texto ja e outro. O `integrity-check` do FTS5
    # externo nao acusa, porque so confere consistencia interna - o fantasma so
    # aparece como resultado errado no meio de um atendimento.
    con.execute("PRAGMA recursive_triggers = ON")
    con.executescript(ESQUEMA)
    _migrar(con)
    return con


def carimbo(con: sqlite3.Connection) -> tuple | None:
    """Estado dos arquivos por tras da conexao. Muda quando o banco muda.

    Serve a quem guarda em memoria algo derivado do banco - a matriz de vetores,
    as estatisticas - e precisa saber quando reler. A ingestao roda em OUTRO
    processo, entao cache que so se desfaz no arranque envelhece calado.

    Olha corpus.db E corpus.db-wal: em WAL a escrita recente vive no -wal e so
    aparece no arquivo principal no checkpoint. Olhar so um perde metade.
    """
    principal = None
    for _, nome, arquivo in con.execute("PRAGMA database_list"):
        if nome == "main" and arquivo:
            principal = Path(arquivo)
    if principal is None:
        return None

    marcas = []
    for caminho in (principal, principal.with_name(principal.name + "-wal")):
        try:
            st = caminho.stat()
            marcas.append((str(caminho), st.st_mtime_ns, st.st_size))
        except OSError:
            marcas.append((str(caminho), None, None))
    return tuple(marcas)


def _migrar(con: sqlite3.Connection) -> None:
    """Alteracoes de esquema que `CREATE TABLE IF NOT EXISTS` nao alcanca."""
    colunas = {c["name"] for c in con.execute("PRAGMA table_info(vetores)")}
    if "maxlen" not in colunas:
        con.execute("ALTER TABLE vetores ADD COLUMN maxlen INTEGER")
        con.commit()


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
            vigencia_inicio, vigencia_fim, revogado, alterado_por, fonte_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                d.urn, d.obra, d.especie, d.rotulo, d.texto, d.texto_indexado,
                d.pai, d.ordem, d.vigencia_inicio, d.vigencia_fim, int(d.revogado),
                d.alterado_por, fonte_id,
            )
            for d in dispositivos
        ],
    )
    return len(dispositivos)


def _impressao(texto: str) -> str:
    """Identidade do texto que virou vetor."""
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def vetores_guardados(con: sqlite3.Connection, obra: str) -> dict[tuple[str, str], tuple]:
    """Os vetores de uma obra, chaveados pelo TEXTO que os gerou.

    Reingerir uma obra e um DELETE seguido de INSERT, e o cascade desta tabela
    leva os vetores junto: 20 minutos de modelo perdidos em silencio, porque a
    busca degrada para lexical sem reclamar. Guardar antes e recolocar depois
    devolve os que continuam validos.

    A chave e o sha256 de `texto_indexado`, nao a urn. Duas razoes:

      A urn nao identifica uma linha. `clt/art-71/par-4` tem varias redacoes, e
      colar nelas o vetor de uma irma poe o vetor do texto de 2016 no texto de
      2017 - erro que ninguem ve, porque a busca segue devolvendo algo.

      O que o modelo embute e `texto_indexado`, e vetor e funcao pura do texto:
      mesmo texto e mesmo modelo dao o mesmo vetor. Se o texto mudou - ou se
      `_texto_indexado` passou a montar a string de outro jeito - o vetor TEM de
      ser refeito, e a troca de hash e o que manda refazer.
    """
    linhas = con.execute(
        """SELECT d.texto_indexado, v.modelo, v.dim, v.maxlen, v.denso, v.esparso
             FROM vetores v
             JOIN dispositivos d ON d.id = v.dispositivo_id
            WHERE d.obra = ?""",
        (obra,),
    )
    guardados: dict[tuple[str, str], tuple] = {}
    for linha in linhas:
        chave = (_impressao(linha["texto_indexado"]), linha["modelo"])
        guardados[chave] = (linha["dim"], linha["maxlen"], linha["denso"], linha["esparso"])
    return guardados


def restaurar_vetores(
    con: sqlite3.Connection, obra: str, guardados: dict[tuple[str, str], tuple]
) -> tuple[int, int]:
    """Recoloca os vetores guardados. Devolve (recolocados, redacoes sem vetor).

    Uma redacao pode receber o vetor de outra quando as duas tem o mesmo
    `texto_indexado` - e isso esta certo: texto igual, vetor igual.
    """
    novas = con.execute(
        "SELECT id, texto_indexado FROM dispositivos WHERE obra = ?", (obra,)
    ).fetchall()
    modelos = {modelo for _, modelo in guardados}

    linhas, servidas = [], set()
    for nova in novas:
        impressao = _impressao(nova["texto_indexado"])
        for modelo in modelos:
            achado = guardados.get((impressao, modelo))
            if achado is None:
                continue
            dim, maxlen, denso, esparso = achado
            linhas.append((nova["id"], modelo, dim, maxlen, denso, esparso))
            servidas.add(nova["id"])

    con.executemany(
        """INSERT OR REPLACE INTO vetores (dispositivo_id, modelo, dim, maxlen, denso, esparso)
           VALUES (?, ?, ?, ?, ?, ?)""",
        linhas,
    )
    return len(linhas), len(novas) - len(servidas)


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
             AND revogado = 0
             AND vigencia_inicio <= ?
             AND (vigencia_fim IS NULL OR vigencia_fim >= ?)
           ORDER BY vigencia_inicio DESC, ordem DESC LIMIT 1""",
        (urn, ref, ref),
    ).fetchone()


def redacoes(con: sqlite3.Connection, urn: str) -> list[sqlite3.Row]:
    """Todas as redacoes ja tidas por um dispositivo, da mais antiga para a atual."""
    return con.execute(
        "SELECT * FROM dispositivos WHERE urn = ? ORDER BY vigencia_inicio", (urn,)
    ).fetchall()


# Seis COUNTs, um deles COUNT(DISTINCT urn): 7,7 ms medidos, pagos a cada visita
# ao /corpus mesmo quando nao ha consulta nenhuma - era o maior custo da pagina
# vazia. So mudam em reingestao, entao valem cache carimbado.
_estatisticas: dict | None = None
_estatisticas_carimbo: object = object()


def estatisticas(con: sqlite3.Connection) -> dict[str, int]:
    global _estatisticas, _estatisticas_carimbo
    marca = carimbo(con)
    if _estatisticas is not None and marca is not None and marca == _estatisticas_carimbo:
        return _estatisticas

    def um(sql: str) -> int:
        return int(con.execute(sql).fetchone()[0])

    _estatisticas_carimbo = marca
    _estatisticas = {
        "obras": um("SELECT COUNT(DISTINCT obra) FROM dispositivos"),
        "dispositivos": um("SELECT COUNT(DISTINCT urn) FROM dispositivos"),
        "redacoes": um("SELECT COUNT(*) FROM dispositivos"),
        "revogados": um("SELECT COUNT(*) FROM dispositivos WHERE revogado = 1"),
        "com_vetor": um("SELECT COUNT(*) FROM vetores"),
        "fontes": um("SELECT COUNT(*) FROM fontes"),
    }
    return _estatisticas
