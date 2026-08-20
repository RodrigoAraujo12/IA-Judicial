"""Norma de terceiro transcrita no meio da pagina, com numeracao propria.

    python testar_norma_estranha.py

O caso e o art. 60. A pagina da CLT no Planalto transcreve, dentro do titulo da
Justica do Trabalho, o texto do Decreto-Lei 9.797/1946 - que numera os proprios
artigos. Seu "Art. 60", sobre composicao dos Tribunais Regionais, aparece entre
os arts. 669 e 670 da CLT.

O parser lia esse bloco como redacao NOVA do art. 60 da CLT, que trata de outra
coisa inteiramente: prorrogacao de jornada em atividade insalubre, que so pode
acontecer mediante licenca previa. O efeito nao era um texto errado no lugar
certo - era o artigo verdadeiro marcado como revogado desde 1946 e sumido do
indice. Consulta a ele devolvia lista vazia, sem dizer por que.

O criterio do conserto e posicional, nao textual: a numeracao da CLT nesta fonte
e estritamente crescente - 1.853 marcadores de artigo, nenhuma regressao alem
desta. Entao regredir centenas de artigos nao e desordem, e outra norma.

Este teste tranca as duas pontas: o artigo certo volta, e os vizinhos que
cercam a intrusao continuam inteiros. A segunda parte importa tanto quanto a
primeira - um guarda que descartasse demais consertaria o art. 60 destruindo o
titulo da Justica do Trabalho.
"""

from pathlib import Path

from app.corpus import planalto

falhas = []


def conferir(rotulo: str, obtido, esperado) -> None:
    ok = obtido == esperado
    print(f"  {'ok ' if ok else 'ERRO'} {rotulo}")
    if not ok:
        falhas.append(f"{rotulo}: esperado {esperado!r}, obtido {obtido!r}")


FONTE = Path("dados/fontes/clt-planalto.html")
if not FONTE.exists():
    print("fonte nao capturada - rode: python -m app.corpus.indexar clt")
    raise SystemExit(0)

bruto = FONTE.read_bytes()
trechos = planalto.dispositivos(bruto, "clt", inicio=planalto.INICIO_CLT)
por_urn: dict[str, list] = {}
for t in trechos:
    por_urn.setdefault(t.urn, []).append(t)

print("o art. 60 da CLT e o dele mesmo")

art60 = por_urn.get("clt/art-60", [])
conferir("tem exatamente uma redacao", len(art60), 1)
if art60:
    texto = art60[0].texto
    conferir("fala de atividade insalubre", "insalubres" in texto, True)
    conferir("nao e o dos Tribunais Regionais", "Tribunais Regionais" in texto, False)

# Os paragrafos do artigo intruso viravam clt/art-60/par-1..3, pendurados num
# artigo que nada tem a ver com composicao de tribunal.
print("\nos paragrafos do intruso nao viraram paragrafos do art. 60")
for n in (1, 2, 3):
    conferir(f"art-60/par-{n} nao existe", f"clt/art-60/par-{n}" in por_urn, False)

print("\nos vizinhos da intrusao sobreviveram")
for urn in ("clt/art-669", "clt/art-670", "clt/art-671"):
    conferir(f"{urn} presente", urn in por_urn, True)
conferir(
    "art. 670 mantem as redacoes sucessivas",
    len(por_urn.get("clt/art-670", [])) >= 2,
    True,
)

# O guarda so pode disparar quando ha regressao GRANDE. Se disparasse em
# qualquer desordem, comeria dispositivo legitimo - e o sintoma seria uma queda
# silenciosa na contagem, que ninguem nota sem numero de referencia.
print("\no guarda nao comeu o corpus")
conferir("total de URNs preservado", len(por_urn) > 3600, True)
conferir("total de redacoes preservado", len(trechos) > 5700, True)

if falhas:
    print("\nFALHOU")
    for f in falhas:
        print("  " + f)
    raise SystemExit(1)
print("\nnorma estranha na pagina ok")
