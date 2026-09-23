"""Via 2 - recuperacao densa com BGE-M3.

Roda em ONNX, de proposito. A alternativa seria PyTorch, que traz 2,5 GB de
dependencia e um caminho feliz que exige CUDA - e a maquina deste projeto tem
Intel Arc, nao NVIDIA. Com ONNX o mesmo codigo roda em qualquer computador, sem
placa, sem driver e sem configuracao.

**CPU e o chao, nao o teto.** `provedores()` pergunta ao ORT o que a maquina
oferece e usa o melhor que houver; onde nao houver nada, usa CPU e ninguem
percebe. Medido nesta maquina, na CLT inteira, com a Arc B580 via DirectML:

                          CPU        DirectML     razao
    carregar o modelo     1,5 s       2,5 s       ~igual  (uma vez, no arranque)
    embutir a consulta   61,5 ms     12,1 ms      5x melhor
    lote de 8 a 256 tok   3,48 s      0,20 s     17x melhor
    indexar o corpus     41,6 min     2,4 min    17x melhor

A primeira sessao DirectML da maquina custa ~15 s compilando shaders; o driver
os guarda e da segunda em diante sao 2,5 s. Nao ha contrapartida relevante.

O acelerador nao vem na instalacao padrao e nao deve vir: `onnxruntime-directml`
substitui a wheel `onnxruntime` em vez de somar a ela, e so serve ao Windows. Fica
como opcional documentado em requirements.txt, e o codigo funciona igual sem ele.

**Os vetores sao os mesmos nos dois caminhos**, e isso foi conferido antes de
deixar o provider variar: cosseno minimo 0,99999988 entre CPU e DirectML sobre 64
dispositivos, diferenca maxima de 1,2e-06 por componente, top-10 identico. Um
corpus indexado na GPU pode ser consultado na CPU, e vice-versa - o que importa
porque corpus.db e um arquivo que se copia entre maquinas.

A indexacao nao precisa acontecer na maquina de quem usa: corpus.db e um arquivo.
Indexa-se uma vez, entrega-se pronto.

**O modelo devolve so o vetor denso, e isso e suficiente aqui.** O BGE-M3 tem
tambem uma cabeca esparsa e uma ColBERT, que o export ONNX oficial nao expoe. A
esparsa seria redundante: o BM25 do FTS5 ja faz esse papel, filtrado por vigencia
e sem custo de modelo. A ColBERT entraria como reranqueador, se a precisao pedir.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np

from app.corpus import banco

MODELO = Path(__file__).parent.parent.parent / "modelos" / "bge-m3"
NOME = "bge-m3"
DIM = 1024

# Medido nesta maquina: lote 8 e o melhor ponto. Lotes maiores ficam MAIS lentos
# por item - o gargalo e banda de memoria, nao paralelismo.
LOTE = 8

# 256 porque e o teto do corpus, nao um numero redondo. Medido sobre as 5.748
# redacoes da CLT: mediana 83 tokens, p90 140, MAXIMO 255. Em 256 nenhuma redacao
# perde texto; em 128 perdiam 900 delas, 15,7% do corpus.
#
# E o corte nao era aleatorio: caia nos PARAGRAFOS. `_texto_indexado` antepoe
# rotulo, a variante "paragrafo par." e o caput ao texto do dispositivo, e nos
# subordinados esse prefixo consome o orcamento antes de o texto comecar. No art.
# 71 par. 4o o prefixo levava 91 dos 128 tokens, e o vetor nunca via "de natureza
# indenizatoria" - que e exatamente o termo pelo qual esse dispositivo e buscado.
#
# 13 dos 72 alvos de `avaliacao.py` estavam truncados, todos paragrafos. Reembuti-
# los em 256 melhorou a posicao na via densa de 8 deles, piorou 1: o art. 71 par.
# 4o saiu de #7 para #1, o art. 469 par. 3o de #253 para #18.
#
# Para texto que nao estoura 128, o vetor em 128 e em 256 e BIT A BIT o mesmo
# (conferido: diferenca maxima 0.0 sobre uma amostra). Por isso subir o teto so
# obriga a reembutir as que truncavam, e nao o corpus inteiro - e por isso o
# `maxlen` fica gravado junto do vetor, para que a proxima mudanca aqui saiba
# sozinha o que refazer.
#
# O "nenhuma perde texto" valia para a CLT. Remedido em 23/09/2026, com TST,
# TRT-13, CF, ADCT, Codigo Civil e as leis esparsas (16.799 redacoes): p99 200,
# e 53 passam de 256. As leis novas quase nao contribuem - 3 da CF, e o Codigo
# Civil nao passa de 189. Quem estoura sao as sumulas do TST, 38 de 463, porque
# o Livro traz a tese do IRR junto do verbete; uma chega a 1.220 tokens. Subir o
# teto e decisao em aberto: custa latencia na consulta e reembutir as 53.
MAXLEN = 256


class ModeloAusente(RuntimeError):
    pass


def modelo_presente() -> bool:
    """O modelo esta em disco? Barato de perguntar, e serve para decidir ANTES.

    Sem ele a via densa nao tem como embutir a consulta, e perguntar aqui evita
    carregar os 68 MB da matriz de vetores para descobrir isso depois - numa
    maquina de 1 GB essa diferenca decide se o servidor respira.
    """
    return (MODELO / "model.onnx").exists()


# Aceleradores por ordem de aposta. A CPU nao entra na lista porque nao e uma
# escolha: e o chao, e vai sempre no fim.
#
# Nomear um provider ausente NAO quebra - o ORT avisa e cai para CPU sozinho -
# mas o aviso sai em toda criacao de sessao, e a instalacao PADRAO deste projeto
# nao tem nenhum deles: a wheel `onnxruntime` baunilha traz so CPU. Sem perguntar
# antes, toda maquina limpa passaria a cuspir dois avisos por arranque sobre
# hardware que ninguem pediu. Perguntar custa uma chamada.
ACELERADORES = (
    "DmlExecutionProvider",       # DirectX 12: qualquer GPU no Windows, Intel inclusive
    "CUDAExecutionProvider",      # NVIDIA
    "ROCMExecutionProvider",      # AMD no Linux
    "OpenVINOExecutionProvider",  # runtime da Intel (CPU, iGPU, NPU)
    "CoreMLExecutionProvider",    # Apple
)

# Preenchido na primeira sessao. Quem indexa imprime; a interface pode mostrar.
PROVEDOR: str | None = None


def provedores() -> list[str]:
    """A lista de providers a pedir, ja intersectada com o que a maquina tem."""
    import onnxruntime as ort

    disponiveis = set(ort.get_available_providers())
    return [p for p in ACELERADORES if p in disponiveis] + ["CPUExecutionProvider"]


@dataclass
class Codificador:
    """Sessao ONNX + tokenizador, carregados sob demanda.

    O carregamento e protegido por lock porque as buscas agora correm no
    threadpool do FastAPI: sem ele, duas consultas simultaneas na primeira
    requisicao criariam duas sessoes - 2,2 GB de modelo cada, e numa GPU isso
    tambem duplica a VRAM ocupada.
    """

    _sess: object | None = None
    _tok: object | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def _carregar(self) -> None:
        if self._sess is not None:
            return
        with self._lock:
            if self._sess is not None:  # outra thread chegou primeiro
                return
            if not (MODELO / "model.onnx").exists():
                raise ModeloAusente(
                    f"modelo nao encontrado em {MODELO}. "
                    "Rode: python -m app.corpus.baixar_modelo"
                )
            import onnxruntime as ort
            from tokenizers import Tokenizer

            tok = Tokenizer.from_file(str(MODELO / "tokenizer.json"))
            pedidos = provedores()
            try:
                sess = ort.InferenceSession(str(MODELO / "model.onnx"), providers=pedidos)
            except Exception:
                # Provider presente que nao inicializa - driver velho, GPU ocupada,
                # VRAM insuficiente. Cair para CPU e o comportamento certo; cair
                # CALADO nao e. A busca continua respondendo, mais devagar, e quem
                # olhar PROVEDOR ve o que de fato aconteceu.
                if pedidos == ["CPUExecutionProvider"]:
                    raise
                sess = ort.InferenceSession(
                    str(MODELO / "model.onnx"), providers=["CPUExecutionProvider"]
                )

            global PROVEDOR
            PROVEDOR = sess.get_providers()[0]
            self._tok, self._sess = tok, sess

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
    # Pendente e tanto quem nunca teve vetor quanto quem tem um vetor produzido
    # com outro orcamento de tokens. O segundo caso e o que a coluna `maxlen`
    # existe para tornar visivel: sem ela, subir MAXLEN nao refazia nada e os
    # vetores truncados ficavam no banco parecendo saudaveis.
    pendentes = con.execute(
        """SELECT d.id, d.texto_indexado FROM dispositivos d
           LEFT JOIN vetores v ON v.dispositivo_id = d.id AND v.modelo = ?
           WHERE v.dispositivo_id IS NULL OR v.maxlen IS NOT ?
           ORDER BY d.id""",
        (NOME, MAXLEN),
    ).fetchall()
    if not pendentes:
        return 0

    inicio = time.time()
    feitos = 0
    for i in range(0, len(pendentes), LOTE):
        bloco = pendentes[i : i + LOTE]
        vetores = codificar([l["texto_indexado"] for l in bloco])
        con.executemany(
            """INSERT OR REPLACE INTO vetores (dispositivo_id, modelo, dim, maxlen, denso)
               VALUES (?, ?, ?, ?, ?)""",
            [(l["id"], NOME, DIM, MAXLEN, v.tobytes()) for l, v in zip(bloco, vetores)],
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
    obras: Iterable[str] | None = None,
) -> list[tuple[int, float]]:
    """Devolve (dispositivo_id, similaridade) dos mais proximos, ja filtrados.

    O filtro de vigencia e de obra vem ANTES do corte em `limite`: filtrar depois
    devolveria menos resultados que o pedido sempre que houvesse redacao antiga -
    ou sumula de outro tribunal - no topo, e o buraco apareceria como "a busca
    nao achou".
    """
    q = codificar([consulta])[0]
    sims = matriz.vetores @ q

    validos = banco.ids_vigentes(con, quando, obras)

    ordem = np.argsort(-sims)
    saida: list[tuple[int, float]] = []
    for i in ordem:
        did = int(matriz.ids[i])
        if did in validos:
            saida.append((did, float(sims[i])))
            if len(saida) == limite:
                break
    return saida
