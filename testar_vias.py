"""Compara as vias de recuperacao contra o gabarito de `avaliacao.py`.

    python -m app.corpus.indexar clt
    python -m app.corpus.indexar vetores
    python testar_vias.py

Placar rapido, por consulta. Para decidir se falta um reranqueador - que e outra
pergunta, e depende de recall em lote profundo, nao de acerto@5 - use
`analisar_rerank.py`.

As consultas e o gabarito moram em `avaliacao.py`, junto com o criterio de acerto.

**O placar e medido sobre as obras NACIONAIS.** O gabarito tem resposta na CLT e
foi calibrado antes de existir obra regional; medir com as sumulas de um TRT no
lote mudaria a regua sem mudar a busca. O efeito do tribunal aparece a parte, como
comparacao: quantas consultas mudam de posicao quando o caso e daquele TRT.
"""

import sys
from datetime import date

from app import jurisdicao
from app.corpus import banco, busca
from avaliacao import CASOS, posicao

sys.stdout.reconfigure(encoding="utf-8")

if not banco.BANCO.exists():
    print("corpus vazio. Rode:  python -m app.corpus.indexar clt")
    raise SystemExit(1)

con = banco.conectar()
est = banco.estatisticas(con)
tem_vetores = est["com_vetor"] > 0
# Indexacao parcial e pior que nenhuma para efeito de medicao: a via densa so
# alcanca o que ja tem vetor, entao ela "erra" dispositivos que nem foram vistos,
# e a fusao herda esse buraco. Medir nesse estado produz um numero que parece
# resultado e nao e.
completo = est["com_vetor"] >= est["redacoes"]
if not tem_vetores:
    print("AVISO: nenhum vetor no indice. So a via lexical sera medida.")
    print("       Rode:  python -m app.corpus.indexar vetores\n")
elif not completo:
    pct = 100 * est["com_vetor"] / est["redacoes"]
    print(f"AVISO: indexacao INCOMPLETA ({est['com_vetor']}/{est['redacoes']}, {pct:.0f}%).")
    print("       Os numeros da via densa e da fusao NAO valem ainda.\n")

hoje = date.today()
K = 5

TODAS = banco.obras(con)
NACIONAIS = jurisdicao.obras_para(TODAS, None)
REGIONAIS = jurisdicao.trts_no_corpus(TODAS)

# Controle do filtro de obras, em dois regimes:
#  - corpus SEM obra regional: filtrar por "so nacionais" tem de devolver
#    EXATAMENTE o que a busca sem filtro devolve, consulta a consulta;
#  - corpus COM obra regional: nenhum resultado filtrado pode trazer obra fora do
#    conjunto permitido - nem a de outro tribunal, nem regional numa consulta
#    sem tribunal.
# Nos dois, se um ponto se mover o filtro vazou - e esse e o tipo de regressao
# que o placar sozinho esconderia dentro do ruido.
controle = {"n": 0, "ok": 0}
# Efeito de cada tribunal sobre o gabarito: consultas em que o top-5 muda.
efeito = {t: {"muda": 0, "regional_no_topo": 0} for t in REGIONAIS}


def marca(p: int | None) -> str:
    return f"#{p}" if p else "--"


placar = {"lexical": 0, "densa": 0, "hibrida": 0}
reciproco = {"lexical": 0.0, "densa": 0.0, "hibrida": 0.0}
# O grupo B (termo forense que nao esta no texto da lei) e onde a via densa
# deveria ganhar da lexical. Somado ao total ele desaparece, entao sai separado.
por_grupo: dict[str, dict[str, int]] = {
    "A": {"n": 0, "hibrida": 0}, "B": {"n": 0, "hibrida": 0}
}

print(f"  {'':1} {'consulta':<50} {'lex':>5} {'den':>5} {'hib':>5}")
print(f"  {'':1} {'-' * 50} {'-' * 5} {'-' * 5} {'-' * 5}")


def vias(obras):
    lex = busca.lexical(con, consulta, hoje, 20, obras)
    den = busca.densa(con, consulta, hoje, 20, obras) if tem_vetores else []
    hib = busca.rrf([lex, den], limite=20) if den else lex
    return lex, den, hib


for consulta, esperado, grupo in CASOS:
    lex, den, hib = vias(NACIONAIS)

    controle["n"] += 1
    if not REGIONAIS:
        lex0, den0, _ = vias(None)
        if [a.urn for a in lex0] == [a.urn for a in lex] and [a.urn for a in den0] == [a.urn for a in den]:
            controle["ok"] += 1
    else:
        vazou = any(a.obra not in NACIONAIS for a in lex + den)
        for t in REGIONAIS:
            permitidas = jurisdicao.obras_para(TODAS, t)
            lex_t, den_t, hib_t = vias(permitidas)
            vazou |= any(a.obra not in permitidas for a in lex_t + den_t)
            if [a.urn for a in hib_t[:K]] != [a.urn for a in hib[:K]]:
                efeito[t]["muda"] += 1
            if hib_t and jurisdicao.trt_da_obra(hib_t[0].obra) == t:
                efeito[t]["regional_no_topo"] += 1
        if not vazou:
            controle["ok"] += 1

    ps = {"lexical": posicao(lex[:K], esperado),
          "densa": posicao(den[:K], esperado) if den else None,
          "hibrida": posicao(hib[:K], esperado)}
    for via, p in ps.items():
        if p:
            placar[via] += 1
            reciproco[via] += 1 / p

    por_grupo[grupo]["n"] += 1
    if ps["hibrida"]:
        por_grupo[grupo]["hibrida"] += 1

    print(f"  {grupo} {consulta[:48]:<50} {marca(ps['lexical']):>5} "
          f"{marca(ps['densa']):>5} {marca(ps['hibrida']):>5}")

n = len(CASOS)
print(f"\n  {'via':<10} {'acerto@' + str(K):<10} {'MRR':<8}   (obras nacionais)")
for via in ("lexical", "densa", "hibrida"):
    if via == "densa" and not tem_vetores:
        continue
    print(f"  {via:<10} {placar[via]}/{n:<9} {reciproco[via]/n:.3f}")

print(f"\n  fusao por grupo:")
for g, rotulo in (("A", "vocabulario da lei"), ("B", "termo forense fora da lei")):
    d = por_grupo[g]
    print(f"    {g} ({rotulo:<26}) {d['hibrida']}/{d['n']}")

if REGIONAIS:
    print(f"\n  controle do filtro de obras: {controle['ok']}/{controle['n']} consultas sem obra fora do permitido")
    for t in REGIONAIS:
        e = efeito[t]
        print(f"  com o TRT-{t} no caso: top-{K} muda em {e['muda']}/{n} consultas; "
              f"verbete do TRT em #1 em {e['regional_no_topo']}")
else:
    print(f"\n  controle do filtro de obras: {controle['ok']}/{controle['n']} consultas identicas com 'so nacionais'")
if controle["ok"] < controle["n"]:
    print("  ATENCAO: o filtro por obra vazou. Investigar antes de manter.")

if completo and placar["hibrida"] < max(placar["lexical"], placar["densa"]):
    print("\n  ATENCAO: a fusao ficou ABAIXO da melhor via isolada.")
    print("  RRF deveria somar acertos, nao perder. Investigar antes de manter.")
elif not completo and tem_vetores:
    print("\n  (rode de novo quando a indexacao terminar - os numeros acima nao valem)")

con.close()
