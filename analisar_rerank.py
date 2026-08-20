"""Mede se falta um reranqueador - e nao se um reranqueador seria bonito.

    python analisar_rerank.py

Reranqueador nao busca: ele **reordena** o que a busca ja trouxe. Isso limita o
que ele pode fazer, e o limite e mensuravel. Se o dispositivo certo nao esta no
lote de candidatos, nenhum modelo de reordenacao vai inventa-lo; se ele ja esta em
primeiro, nao ha o que ganhar. O ganho possivel mora inteiro num unico intervalo:

    teto  = recall@P   (o alvo esta em algum lugar do lote de P candidatos)
    piso  = acerto@5   (o alvo ja aparece nos 5 que a tela mostra)
    folga = teto - piso

`folga` e o numero maximo de consultas que um reranqueador PERFEITO consertaria.
Se der zero, a discussao acabou: nao ha o que reordenar. Se der pouco, o custo -
um segundo modelo, mais RAM, mais latencia por consulta - precisa caber nesse
pouco. Sem essa conta, adotar rerank e comprar reforco para um flanco que talvez
nem esteja sob ataque.

A saida separa os casos em tres, porque exigem decisoes diferentes:

  RECUPERAVEL  alvo entre a posicao 6 e P  -> so aqui rerank ajuda
  FORA DO LOTE alvo nem aparece em P       -> problema de recuperacao, nao de ordem
  NO TOPO      alvo em 1..5                -> nada a fazer
"""

import sys
from datetime import date

from app.corpus import banco, busca
from avaliacao import CASOS, posicao

sys.stdout.reconfigure(encoding="utf-8")

K = 5              # o que a tela mostra
POOLS = (20, 50)   # profundidades de lote que um reranqueador consumiria

if not banco.BANCO.exists():
    print("corpus vazio. Rode:  python -m app.corpus.indexar clt")
    raise SystemExit(1)

con = banco.conectar()
est = banco.estatisticas(con)
if est["com_vetor"] < est["redacoes"]:
    print(f"AVISO: indexacao incompleta ({est['com_vetor']}/{est['redacoes']}).")
    print("       Os numeros da via densa e da fusao nao valem. Rode:")
    print("       python -m app.corpus.indexar vetores\n")

hoje = date.today()
FUNDO = max(POOLS)

# Uma passada so; tudo o mais e leitura destes registros.
registros = []
for consulta, alvo, grupo in CASOS:
    lex = busca.lexical(con, consulta, hoje, FUNDO)
    den = busca.densa(con, consulta, hoje, FUNDO)
    hib = busca.rrf([lex, den], limite=FUNDO) if den else lex
    registros.append({
        "consulta": consulta, "alvo": alvo, "grupo": grupo,
        "lex": posicao(lex, alvo), "den": posicao(den, alvo),
        "hib": posicao(hib, alvo),
    })


def dentro(p, n):
    return p is not None and p <= n


def placar(regs, via):
    n = len(regs)
    if not n:
        return None
    ps = [r[via] for r in regs]
    return {
        "n": n,
        "a1": sum(1 for p in ps if dentro(p, 1)),
        "a5": sum(1 for p in ps if dentro(p, K)),
        "mrr": sum(1 / p for p in ps if dentro(p, K)) / n,
        **{f"r{P}": sum(1 for p in ps if dentro(p, P)) for P in POOLS},
    }


NOMES = {"lex": "lexical", "den": "densa", "hib": "hibrida (RRF)"}

print("=" * 74)
print(f"  {len(CASOS)} consultas   corpus: {est['dispositivos']} dispositivos, "
      f"{est['redacoes']} redacoes")
print("=" * 74)

for rotulo, regs in (("TUDO", registros),
                     ("GRUPO A - vocabulario da lei", [r for r in registros if r["grupo"] == "A"]),
                     ("GRUPO B - termo forense fora da lei", [r for r in registros if r["grupo"] == "B"])):
    print(f"\n{rotulo}  (n={len(regs)})")
    cab = f"  {'via':<14} {'acerto@1':>9} {'acerto@5':>9} {'MRR@5':>7}"
    for P in POOLS:
        cab += f" {'recall@' + str(P):>10}"
    print(cab)
    print("  " + "-" * (len(cab) - 2))
    for via in ("lex", "den", "hib"):
        e = placar(regs, via)
        linha = (f"  {NOMES[via]:<14} {e['a1']:>4}/{e['n']:<4} {e['a5']:>4}/{e['n']:<4} "
                 f"{e['mrr']:>7.3f}")
        for P in POOLS:
            linha += f" {e['r' + str(P)]:>5}/{e['n']:<4}"
        print(linha)

print("\n" + "=" * 74)
print("  TETO DO RERANK - o que um reranqueador PERFEITO ganharia sobre a fusao")
print("=" * 74)

e = placar(registros, "hib")
n = e["n"]
for P in POOLS:
    folga = e[f"r{P}"] - e["a5"]
    print(f"\n  lote de {P:>2} candidatos:  teto {e[f'r{P}']}/{n}  -  piso {e['a5']}/{n}"
          f"  =  folga de {folga} consulta(s)")
    if folga == 0:
        print("     Nada a reordenar: tudo o que a fusao alcanca ja esta nos 5 primeiros.")
    else:
        print(f"     Ganho maximo teorico: +{100 * folga / n:.1f} ponto(s) de acerto@5.")

P = POOLS[0]
recuperaveis = [r for r in registros if not dentro(r["hib"], K) and dentro(r["hib"], P)]
fora = [r for r in registros if not dentro(r["hib"], FUNDO)]

print(f"\n  RECUPERAVEIS por rerank (alvo entre {K + 1} e {P}): {len(recuperaveis)}")
for r in recuperaveis:
    print(f"    #{r['hib']:<3} [{r['grupo']}] {r['consulta'][:46]:<48} -> {r['alvo']}")

print(f"\n  FORA DO LOTE de {FUNDO} (rerank nao alcanca): {len(fora)}")
for r in fora:
    print(f"    [{r['grupo']}] {r['consulta'][:46]:<48} -> {r['alvo']}"
          f"   (lex {r['lex']}, den {r['den']})")

# A fusao nao pode ficar abaixo da melhor via isolada: RRF existe para somar
# acertos. Se ficar, o problema esta na fusao, e trocar de reranqueador nao
# conserta o que a etapa anterior estragou.
mlex, mden, mhib = (placar(registros, v)["a5"] for v in ("lex", "den", "hib"))
if mhib < max(mlex, mden):
    print(f"\n  ATENCAO: fusao ({mhib}) abaixo da melhor via isolada "
          f"(lexical {mlex}, densa {mden}). Investigar a fusao antes do rerank.")

con.close()
