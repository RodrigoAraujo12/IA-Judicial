"""Ingestao do corpus normativo.

    python -m app.corpus.indexar clt
    python -m app.corpus.indexar clt --rebaixar   # rebaixa a captura do site

Grava em dados/corpus.db. O banco e indice: apagar e reconstruir e operacao
normal, nao acidente.

Ao fim, imprime a unica metrica que decide se a ingestao presta: **quantos dos
dispositivos citados pelo catalogo ficaram enderecaveis**. Um parser que reconhece
5.000 artigos e perde o art. 71 par. 4o nao serve para este projeto.
"""

from __future__ import annotations

import sys
from datetime import date

from app.catalogo.loader import carregar
from app.corpus import banco, planalto
from app.corpus.banco import Dispositivo
from app.corpus.refs import interpretar

OBRAS = {
    "clt": {
        "url": planalto.URL_CLT,
        "arquivo": "clt-planalto.html",
        "inicio": planalto.INICIO_CLT,
        "piso": planalto.VIGENCIA_CLT,
        "nome": "Consolidacao das Leis do Trabalho",
    },
}


def _texto_indexado(rotulo: str, texto: str, caput: str | None) -> str:
    """O que vai para o BM25 e para o vetor, distinto do que se cita.

    Um paragrafo solto perde o assunto: "§ 4o A nao concessao ou a concessao
    parcial..." nao diz de que artigo fala nem que o tema e intervalo. Sem o caput
    junto, esse dispositivo some tanto da busca lexical quanto da densa - e ele e
    justamente um dos mais pedidos.
    """
    partes = [rotulo]
    if caput:
        partes.append(caput[:240])
    partes.append(texto)
    return " ".join(partes)


def indexar(chave: str, rebaixar: bool = False) -> None:
    obra = OBRAS[chave]
    print(f"{obra['nome']}")

    bruto = planalto.baixar(obra["url"], obra["arquivo"], forcar=rebaixar)
    print(f"  fonte: {len(bruto):,} bytes")

    trechos = planalto.dispositivos(bruto, chave, inicio=obra["inicio"])
    resolvidos = planalto.com_vigencia(trechos, obra["piso"])
    print(f"  reconhecidos: {len(trechos)} dispositivos em {len({t.urn for t in trechos})} URNs")

    # Caput de cada artigo, para dar contexto aos subordinados no indice.
    caputs = {t.urn: t.texto for t in trechos if t.especie == "artigo"}

    registros = []
    for t, inicio, fim, revogado in resolvidos:
        raiz = t.urn.split("/")[0] + "/" + t.urn.split("/")[1]
        caput = caputs.get(raiz) if t.especie != "artigo" else None
        registros.append(
            Dispositivo(
                urn=t.urn,
                obra=chave,
                especie=t.especie,
                rotulo=t.rotulo,
                texto=t.texto,
                texto_indexado=_texto_indexado(t.rotulo, t.texto, caput),
                pai=t.pai,
                ordem=t.ordem,
                vigencia_inicio=inicio.isoformat(),
                vigencia_fim=fim.isoformat() if fim else None,
                revogado=revogado,
                alterado_por=t.alterado_por,
            )
        )

    con = banco.conectar()
    con.execute("DELETE FROM dispositivos WHERE obra = ?", (chave,))
    fonte_id = banco.registrar_fonte(con, chave, obra["url"], bruto)
    banco.gravar(con, registros, fonte_id)
    con.commit()

    print(f"  gravados: {len(registros)} redacoes")
    print(f"  estatisticas: {banco.estatisticas(con)}")
    conferir_catalogo(con, chave)
    con.close()


def conferir_catalogo(con, chave: str) -> None:
    """A metrica que decide: o catalogo consegue encontrar o que cita?"""
    catalogo = carregar()
    exigidos: dict[str, list[str]] = {}
    for item in list(catalogo.pedidos) + list(catalogo.armadilhas):
        origem = getattr(item, "nome", None) or item.titulo
        for f in item.fundamentos:
            r = interpretar(f.tipo, f.ref)
            if r.obra == chave:
                for urn in r.urns:
                    exigidos.setdefault(urn, []).append(origem)

    # Dois diagnosticos opostos que nao podem aparecer misturados:
    #   ausente  -> o parser perdeu o dispositivo. Bug meu, corrige-se em codigo.
    #   revogado -> o catalogo cita norma que nao existe mais. Bug juridico,
    #               corrige-se no YAML, e e informacao util para quem redige.
    hoje = date.today()
    ausentes, revogados = [], []
    for urn in exigidos:
        if banco.vigente_em(con, urn, hoje) is not None:
            continue
        (revogados if banco.redacoes(con, urn) else ausentes).append(urn)

    total = len(exigidos)
    vivos = total - len(ausentes) - len(revogados)
    print(f"\n  catalogo -> corpus: {vivos} de {total} dispositivos citados estao vigentes hoje")

    if ausentes:
        print("  AUSENTES DO CORPUS (falha de ingestao):")
        for urn in sorted(ausentes):
            print(f"    {urn}  <- {', '.join(sorted(set(exigidos[urn])))}")

    if revogados:
        print("  NO CORPUS, MAS NAO VIGENTES (o catalogo cita norma revogada):")
        for urn in sorted(revogados):
            ultima = banco.redacoes(con, urn)[-1]
            quando = ultima["vigencia_fim"] or "data nao legivel na fonte"
            por = ultima["alterado_por"] or "?"
            print(f"    {urn} ate {quando} ({por})  <- {', '.join(sorted(set(exigidos[urn])))}")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    rebaixar = "--rebaixar" in sys.argv
    alvos = args or list(OBRAS)
    for chave in alvos:
        if chave not in OBRAS:
            print(f"obra desconhecida: {chave}. Disponiveis: {', '.join(OBRAS)}")
            raise SystemExit(1)
        indexar(chave, rebaixar)


if __name__ == "__main__":
    main()
