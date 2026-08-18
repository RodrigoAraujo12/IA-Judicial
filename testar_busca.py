"""Recuperacao no corpus da CLT.

    python -m app.corpus.indexar clt    # antes, para ter o que buscar
    python testar_busca.py

O que se afere aqui nao e "achou algo", e **achou a norma certa para a data
certa**. Um indice juridico que ignora o tempo responde com a mesma seguranca
para um contrato de 2016 e um de 2026 - e erra um dos dois.
"""

import sys
from datetime import date
from pathlib import Path

from app.corpus import banco, busca

sys.stdout.reconfigure(encoding="utf-8")

if not banco.BANCO.exists():
    print("corpus vazio. Rode primeiro:  python -m app.corpus.indexar clt")
    raise SystemExit(1)

con = banco.conectar()
falhas: list[str] = []


def conferir(rotulo: str, obtido, esperado) -> None:
    ok = obtido == esperado
    print(f"  {'ok  ' if ok else 'ERRO'} {rotulo}")
    if not ok:
        falhas.append(f"{rotulo}: esperado {esperado!r}, obtido {obtido!r}")


def urns(achados) -> list[str]:
    return [a.urn for a in achados]


print("Via 0 - referencia vira dispositivo")
r = busca.por_referencia(con, "clt", "art. 71, par. 4o")
conferir("art. 71 par. 4o resolve", urns(r), ["clt/art-71/par-4"])
conferir("devolve a redacao da Reforma", "período suprimido" in r[0].texto, True)

r = busca.por_referencia(con, "clt", "art. 844, par. 2o e par. 3o")
conferir("referencia com dois paragrafos devolve os dois", len(r), 2)

r = busca.por_referencia(con, "clt", "art. 71, par. 4o", date(2016, 5, 1))
conferir("mesma referencia em 2016 devolve a redacao anterior",
         "período correspondente" in r[0].texto, True)

print("\nVia 1 - consulta em linguagem de escritorio")
r = busca.lexical(con, "intervalo intrajornada suprimido", limite=3)
conferir("intervalo intrajornada acha o art. 71 par. 4o", "clt/art-71/par-4" in urns(r), True)

r = busca.lexical(con, "insalubridade agentes nocivos limites de tolerancia", limite=3)
conferir("insalubridade acha o art. 189", "clt/art-189" in urns(r), True)

r = busca.lexical(con, "ausencia do reclamante na audiencia", limite=3)
conferir("ausencia em audiencia acha o art. 844 par. 2o", "clt/art-844/par-2" in urns(r), True)

# O escritorio escreve sem acento; a lei tem acento. Sem remove_diacritics no
# tokenizer, esta consulta volta vazia e a busca "simplesmente nao funciona".
r = busca.lexical(con, "jornada extraordinaria", limite=5)
conferir("consulta sem acento casa texto acentuado", len(r) > 0, True)

print("\nRoteamento - referencia nao vai para o BM25")
r = busca.buscar(con, "art. 384", date(2016, 1, 1))
conferir("'art. 384' em 2016 devolve o proprio art. 384", urns(r.achados), ["clt/art-384"])

print("\nVigencia - a data do caso decide")
hoje = busca.buscar(con, "art. 384", date.today())
conferir("art. 384 nao devolve nada hoje", hoje.achados, [])
conferir("e explica por que, em vez de calar", "vigorou ate" in (hoje.aviso or ""), True)
conferir("o aviso nomeia a norma revogadora", "13.467" in (hoje.aviso or ""), True)

conferir("art. 141 responde para caso de 2016",
         urns(busca.buscar(con, "art. 141", date(2016, 1, 1)).achados), ["clt/art-141"])
r141 = busca.buscar(con, "art. 141", date.today())
conferir("art. 141 nao responde hoje", r141.achados, [])
conferir("e diz ate quando valeu", "2018-12-31" in (r141.aviso or ""), True)

antes = busca.lexical(con, "intervalo de quinze minutos mulher prorrogacao", date(2016, 3, 1), 1)
depois = busca.lexical(con, "intervalo de quinze minutos mulher prorrogacao", date(2026, 3, 1), 1)
conferir("busca livre em 2016 alcanca o art. 384", urns(antes), ["clt/art-384"])
conferir("a mesma busca em 2026 nao alcanca", "clt/art-384" in urns(depois), False)

print(f"\nestatisticas: {banco.estatisticas(con)}")
con.close()

if falhas:
    print("\nFALHOU")
    for f in falhas:
        print("  " + f)
    raise SystemExit(1)
print("\nrecuperacao ok")
