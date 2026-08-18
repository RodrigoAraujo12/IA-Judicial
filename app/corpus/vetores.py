"""Via 2 - recuperacao densa com BGE-M3.

Roda em ONNX na CPU, de proposito. A alternativa seria PyTorch, que traz 2,5 GB
de dependencia e um caminho feliz que exige CUDA - e a maquina deste projeto tem
Intel Arc, nao NVIDIA. Com ONNX o mesmo codigo roda em qualquer computador, sem
placa, sem driver e sem configuracao. Os numeros medidos nesta maquina:

    carregar o modelo    1,8 s   (uma vez, no arranque)
    embutir a consulta    62 ms  (por busca)
    varrer o indice        1 ms  (por busca)
    indexar o corpus     ~25 min (uma vez; o resultado e um arquivo copiavel)

A indexacao nao precisa acontecer na maquina de quem usa: corpus.db e um arquivo.
Indexa-se uma vez, entrega-se pronto.

**O modelo devolve so o vetor denso, e isso e suficiente aqui.** O BGE-M3 tem
tambem uma cabeca esparsa e uma ColBERT, que o export ONNX oficial nao expoe. A
esparsa seria redundante: o BM25 do FTS5 ja faz esse papel, filtrado por vigencia
e sem custo de modelo. A ColBERT entraria como reranqueador, se a precisao pedir.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np

MODELO = Path(__file__).parent.parent.parent / "modelos" / "bge-m3"
NOME = "bge-m3"
DIM = 1024

# Medido nesta maquina: lote 8 e maxlen 128 sao o melhor ponto. Lotes maiores
# ficam MAIS lentos por item - o gargalo e banda de memoria, nao paralelismo.
LOTE = 8
MAXLEN = 128


class ModeloAusente(RuntimeError):
    pass


@dataclass
class Codificador:
    """Sessao ONNX + tokenizador, carregados sob demanda."""

    _sess: object | None = None
    _tok: object | None = None

    def _carregar(self) -> None:
        if self._sess is not None:
            return
        if not (MODELO / "model.onnx").exists():
            raise ModeloAusente(
                f"modelo nao encontrado em {MODELO}. "
                "Rode: python -m app.corpus.baixar_modelo"
            )
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self._tok = Tokenizer.from_file(str(MODELO / "tokenizer.json"))
        self._sess = ort.InferenceSession(
            str(MODELO / "model.onnx"), providers=["CPUExecutionProvider"]
        )

    def codificar(self, textos: list[str], maxlen: int = MAXLEN) -> np.ndarray:
        """Devolve os vetores densos, ja normalizados (uma linha por texto).

        `sentence_embedding` do export e o token CLS normalizado, que e exatamente
        a definicao do denso do BGE-M3 - conferido contra 1_Pooling/config.json.
        """
        self._carregar()
        self._tok.enable_truncation(maxlen)
        if len(textos) > 1:
            self._tok.enable_padding()
        else:
            self._tok.no_padding()

        enc = self._tok.encode_batch(textos)
        saida = self._sess.run(
            ["sentence_embedding"],
            {
                "input_ids": np.array([e.ids for e in enc], dtype=np.int64),
                "attention_mask": np.array([e.attention_mask for e in enc], dtype=np.int64),
            },
        )[0]
        return saida.astype(np.float32)


_codificador = Codificador()


def codificar(textos: list[str], maxlen: int = MAXLEN) -> np.ndarray:
    return _codificador.codificar(textos, maxlen)


# --- indexacao --------------------------------------------------------------


def indexar(con: sqlite3.Connection, progresso: bool = True) -> int:
    """Calcula e grava o vetor de cada redacao ainda sem vetor.

    Inclui redacoes revogadas e superadas de proposito: um caso de 2016 precisa
    achar a lei de 2016. O filtro de vigencia acontece na CONSULTA, nunca aqui -
    apagar a historia do indice seria irreversivel, filtrar e barato.
    """
    pendentes = con.execute(
        """SELECT d.id, d.texto_indexado FROM dispositivos d
           LEFT JOIN vetores v ON v.dispositivo_id = d.id AND v.modelo = ?
           WHERE v.dispositivo_id IS NULL
           ORDER BY d.id""",
        (NOME,),
    ).fetchall()
    if not pendentes:
        return 0

    inicio = time.time()
    feitos = 0
    for i in range(0, len(pendentes), LOTE):
        bloco = pendentes[i : i + LOTE]
        vetores = codificar([l["texto_indexado"] for l in bloco])
        con.executemany(
            "INSERT OR REPLACE INTO vetores (dispositivo_id, modelo, dim, denso) VALUES (?, ?, ?, ?)",
            [(l["id"], NOME, DIM, v.tobytes()) for l, v in zip(bloco, vetores)],
        )
        feitos += len(bloco)
        if progresso and feitos % 200 < LOTE:
            passou = time.time() - inicio
            resta = (len(pendentes) - feitos) / max(feitos / passou, 1e-9)
            print(
                f"  {feitos}/{len(pendentes)}  ({feitos/passou:.1f}/s, "
                f"faltam ~{resta/60:.0f} min)",
                flush=True,
            )
            con.commit()
    con.commit()
    return feitos


# --- consulta ---------------------------------------------------------------


@dataclass
class Matriz:
    """Os vetores do corpus em memoria, prontos para o produto escalar.

    23 MB para o corpus inteiro. Carregar tudo e mais simples e mais rapido que
    qualquer indice aproximado nesta escala - a varredura exaustiva leva 1 ms.
    """

    ids: np.ndarray
    vetores: np.ndarray


def carregar_matriz(con: sqlite3.Connection) -> Matriz | None:
    linhas = con.execute(
        "SELECT dispositivo_id, denso FROM vetores WHERE modelo = ? ORDER BY dispositivo_id",
        (NOME,),
    ).fetchall()
    if not linhas:
        return None
    ids = np.array([l["dispositivo_id"] for l in linhas], dtype=np.int64)
    vetores = np.frombuffer(b"".join(l["denso"] for l in linhas), dtype=np.float32)
    return Matriz(ids=ids, vetores=vetores.reshape(len(ids), DIM))


def buscar(
    con: sqlite3.Connection,
    matriz: Matriz,
    consulta: str,
    quando: date | None = None,
    limite: int = 10,
) -> list[tuple[int, float]]:
    """Devolve (dispositivo_id, similaridade) dos mais proximos, ja filtrados.

    O filtro de vigencia vem ANTES do corte em `limite`: filtrar depois devolveria
    menos resultados que o pedido sempre que houvesse redacao antiga no topo, e o
    buraco apareceria como "a busca nao achou".
    """
    q = codificar([consulta])[0]
    sims = matriz.vetores @ q

    ref = (quando or date.today()).isoformat()
    validos = {
        int(r["id"])
        for r in con.execute(
            """SELECT id FROM dispositivos
               WHERE revogado = 0 AND vigencia_inicio <= ?
                 AND (vigencia_fim IS NULL OR vigencia_fim >= ?)""",
            (ref, ref),
        )
    }

    ordem = np.argsort(-sims)
    saida: list[tuple[int, float]] = []
    for i in ordem:
        did = int(matriz.ids[i])
        if did in validos:
            saida.append((did, float(sims[i])))
            if len(saida) == limite:
                break
    return saida
