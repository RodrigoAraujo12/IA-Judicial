"""Compara as vias de recuperacao contra um gabarito.

    python -m app.corpus.indexar clt
    python -m app.corpus.indexar vetores
    python testar_vias.py

As consultas sao escritas como **a advogada** escreve, nao como o cliente fala.
Isso nao e detalhe: quem digita no sistema conhece o vocabulario da lei, e avaliar
com relato de leigo mede uma habilidade que ninguem vai usar. A traducao do relato
para categoria juridica ja acontece antes, na entrevista.

O gabarito foi conferido dispositivo a dispositivo contra o texto ingerido.
"""

import sys
from datetime import date

from app.corpus import banco, busca

sys.stdout.reconfigure(encoding="utf-8")

# (consulta, urn que deveria aparecer)
CASOS = [
    ("intervalo intrajornada natureza indenizatoria",    "clt/art-71/par-4"),
    ("dispensa imotivada aviso previo",                  "clt/art-487"),
    ("atividades perigosas adicional de trinta por cento", "clt/art-193"),
    ("grupo economico responsabilidade solidaria",       "clt/art-2/par-2"),
    ("honorarios de sucumbencia advogado",               "clt/art-791-A"),
    ("acrescimo de horas extras limite diario",          "clt/art-59"),
    ("justa causa ato de improbidade",                   "clt/art-482"),
    ("trabalho noturno hora reduzida",                   "clt/art-73"),
    ("equiparacao salarial identidade de funcao",        "clt/art-461"),
    ("ausencia do reclamante arquivamento custas",       "clt/art-844/par-2"),
    ("peticao inicial pedido certo determinado",         "clt/art-840/par-1"),
    ("prescricao dos creditos trabalhistas",             "clt/art-11"),
    ("dano extrapatrimonial esfera moral",               "clt/art-223-B"),
    ("fornecimento gratuito de equipamento de protecao", "clt/art-166"),
    ("multa por atraso no pagamento das verbas rescisorias", "clt/art-477/par-8"),
]

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


def posicao(achados, alvo: str) -> int | None:
    """Acerta quem devolve o dispositivo OU um subordinado dele.

    Exigir a URN exata mede a coisa errada. Para "justa causa ato de improbidade"
    a melhor resposta e a alinea 'a' do art. 482 - literalmente "ato de
    improbidade" -, nao o caput; para "hora noturna reduzida" e o par. 1o do art.
    73, nao o artigo. Cobrar o caput reprovava o sistema justamente quando ele
    respondia com mais precisao do que se pediu.
    """
    for i, a in enumerate(achados):
        if a.urn == alvo or a.urn.startswith(alvo + "/"):
            return i + 1
    return None


def marca(p: int | None) -> str:
    return f"#{p}" if p else "--"


placar = {"lexical": 0, "densa": 0, "hibrida": 0}
reciproco = {"lexical": 0.0, "densa": 0.0, "hibrida": 0.0}

print(f"  {'consulta':<50} {'lex':>5} {'den':>5} {'hib':>5}")
print(f"  {'-' * 50} {'-' * 5} {'-' * 5} {'-' * 5}")

for consulta, esperado in CASOS:
    lex = busca.lexical(con, consulta, hoje, 20)
    den = busca.densa(con, consulta, hoje, 20) if tem_vetores else []
    hib = busca.rrf([lex, den], limite=20) if den else lex

    ps = {"lexical": posicao(lex[:K], esperado),
          "densa": posicao(den[:K], esperado) if den else None,
          "hibrida": posicao(hib[:K], esperado)}
    for via, p in ps.items():
        if p:
            placar[via] += 1
            reciproco[via] += 1 / p

    print(f"  {consulta[:48]:<50} {marca(ps['lexical']):>5} "
          f"{marca(ps['densa']):>5} {marca(ps['hibrida']):>5}")

n = len(CASOS)
print(f"\n  {'via':<10} {'acerto@' + str(K):<10} {'MRR':<8}")
for via in ("lexical", "densa", "hibrida"):
    if via == "densa" and not tem_vetores:
        continue
    print(f"  {via:<10} {placar[via]}/{n:<9} {reciproco[via]/n:.3f}")

if completo and placar["hibrida"] < max(placar["lexical"], placar["densa"]):
    print("\n  ATENCAO: a fusao ficou ABAIXO da melhor via isolada.")
    print("  RRF deveria somar acertos, nao perder. Investigar antes de manter.")
elif not completo and tem_vetores:
    print("\n  (rode de novo quando a indexacao terminar - os numeros acima nao valem)")

con.close()
