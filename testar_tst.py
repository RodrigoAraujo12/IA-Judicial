"""Sumulas e OJs do TST: parsing do Livro e vigencia dos verbetes.

    python testar_tst.py     (exige `python -m app.corpus.indexar tst`)

O que este arquivo defende, em ordem de importancia:

**Sumula cancelada nao some: fecha janela.** A 437 foi cancelada pela Reforma. Um
caso de 2016 tem de continuar encontrando-a, e um caso de hoje tem de receber a
explicacao de que ela caiu - nao uma lista vazia. E a mesma regra da CLT, aplicada
a jurisprudencia.

**A data do cabecalho muda de sentido com o status.** "(nova redacao) - Res.
185/2012" abre vigencia; "(cancelada) - Res. 121/2003" encerra. Ler as duas como
inicio poe a sumula nascendo no dia em que morreu.

**O corte do indice remissivo.** O Livro repete cada verbete no indice tematico,
sem texto. Se o corte falhar para um lado entram 4.700 fantasmas; para o outro,
zero verbetes. Os dois ja aconteceram.
"""

import sys
from datetime import date

from app.corpus import banco, busca, tst

falhas: list[str] = []


def conferir(rotulo: str, obtido, esperado) -> None:
    ok = obtido == esperado
    if not ok:
        falhas.append(f"{rotulo}: esperado {esperado!r}, obtido {obtido!r}")
    marca = "ok " if ok else "ERRO"
    texto = f"  {marca}  {rotulo}"
    if not ok:
        texto += f"  -> {obtido!r}"
    sys.stdout.write(texto.encode("ascii", "replace").decode() + "\n")


con = banco.conectar()
if not con.execute("SELECT 1 FROM dispositivos WHERE obra = 'sumula-tst' LIMIT 1").fetchone():
    raise SystemExit("corpus sem as sumulas. Rode: python -m app.corpus.indexar tst")

print("extensao do que foi ingerido")
for obra, minimo in [("sumula-tst", 400), ("oj-sdi1-tst", 300),
                     ("oj-sdi2-tst", 120), ("oj-sdi1-trans-tst", 60)]:
    n = con.execute("SELECT COUNT(*) FROM dispositivos WHERE obra = ?", (obra,)).fetchone()[0]
    conferir(f"{obra} tem ao menos {minimo}", n >= minimo, True)

# O indice remissivo repete cada verbete como remissao sem texto. Verbete de duas
# palavras e sinal de que o corte falhou.
curtos = con.execute(
    "SELECT COUNT(*) FROM dispositivos WHERE obra LIKE '%tst' AND LENGTH(texto) < 40"
).fetchone()[0]
conferir("nenhum verbete truncado (indice remissivo cortado)", curtos, 0)

print("\nSumula 437 - cancelada pela Reforma, e a data do caso decide")
achou_2016 = busca.por_referencia(con, "sumula_tst", "Sumula 437", date(2016, 5, 1))
conferir("responde para caso de 2016", len(achou_2016), 1)
if achou_2016:
    conferir("com o texto do verbete", "intervalo intrajornada" in achou_2016[0].texto.lower(), True)
    conferir("janela fecha em 10/11/2017", achou_2016[0].vigencia_fim, "2017-11-10")

hoje = busca.buscar(con, "Sumula 437", date(2026, 1, 1))
conferir("nao responde hoje", len(hoje.achados), 0)
conferir("e diz por que, em vez de calar", bool(hoje.aviso and "vigor" in hoje.aviso), True)

print("\nverbete vigente responde normalmente")
r331 = busca.por_referencia(con, "sumula_tst", "Sumula 331", None)
conferir("Sumula 331 vigente hoje", len(r331), 1)
if r331:
    conferir("texto transcrito", "empresa interposta" in r331[0].texto.lower(), True)
    conferir("sem fim de vigencia", r331[0].vigencia_fim, None)

print("\nOJ da SBDI-I resolve pela referencia do catalogo")
oj = busca.por_referencia(con, "oj_tst", "OJ 355 da SDI-1", date(2016, 5, 1))
conferir("OJ 355 responde para 2016", len(oj), 1)
if oj:
    conferir("rotulo nomeia a subsecao", "SBDI-I" in oj[0].rotulo, True)

print("\na data do cabecalho nao vira inicio quando o status e cancelamento")
s2 = con.execute(
    "SELECT vigencia_inicio, vigencia_fim FROM dispositivos WHERE urn = 'sumula-tst/2'"
).fetchone()
if s2 is None:
    conferir("Sumula 2 ingerida", False, True)
else:
    conferir("Sumula 2 comeca no piso, nao na Res. que a cancelou",
             s2["vigencia_inicio"], tst.PISO.isoformat())
    conferir("e termina na vespera da Res. 121/2003", s2["vigencia_fim"], "2003-11-20")

print("\nbusca livre alcanca a jurisprudencia")
livre = busca.buscar(con, "terceirizacao responsabilidade subsidiaria do tomador", limite=10)
urns = [a.urn for a in livre.achados]
conferir("Sumula 331 aparece na busca livre", "sumula-tst/331" in urns, True)

print("\nnada de TST entrou como vigente sem texto")
vazios = con.execute(
    """SELECT COUNT(*) FROM dispositivos
        WHERE obra LIKE '%tst' AND revogado = 0 AND TRIM(texto) = ''"""
).fetchone()[0]
conferir("nenhum verbete vigente sem texto", vazios, 0)

con.close()

if falhas:
    print(f"\n{len(falhas)} FALHA(S):")
    for f in falhas:
        print(f"  - {f}")
    raise SystemExit(1)
print("\nsumulas e OJs ok")
