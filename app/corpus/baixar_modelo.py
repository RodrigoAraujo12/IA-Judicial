"""Baixa o BGE-M3 em ONNX (export oficial da BAAI).

    python -m app.corpus.baixar_modelo

Sao 2,2 GB, uma vez. Fica em modelos/bge-m3/, que esta no .gitignore: peso de
modelo nao vai para o repositorio.
"""

from __future__ import annotations

import ssl
import time
import urllib.request
from pathlib import Path

BASE = "https://huggingface.co/BAAI/bge-m3/resolve/main/"
DESTINO = Path(__file__).parent.parent.parent / "modelos" / "bge-m3"
ARQUIVOS = [
    "onnx/config.json",
    "onnx/tokenizer_config.json",
    "onnx/special_tokens_map.json",
    "onnx/tokenizer.json",
    "onnx/model.onnx",
    "onnx/model.onnx_data",
]


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    ctx = ssl.create_default_context()
    for alvo in ARQUIVOS:
        saida = DESTINO / Path(alvo).name
        if saida.exists() and saida.stat().st_size > 0:
            print(f"ja existe: {saida.name} ({saida.stat().st_size/1024/1024:.1f} MB)")
            continue
        req = urllib.request.Request(BASE + alvo, headers={"User-Agent": "Mozilla/5.0"})
        t0 = time.time()
        with urllib.request.urlopen(req, context=ctx, timeout=180) as r, saida.open("wb") as f:
            lido = 0
            while bloco := r.read(1 << 20):
                f.write(bloco)
                lido += len(bloco)
        print(f"ok: {saida.name} ({lido/1024/1024:.1f} MB em {time.time()-t0:.0f}s)")
    print(f"modelo em {DESTINO}")


if __name__ == "__main__":
    main()
