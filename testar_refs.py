"""Cobertura do interpretador de referencias contra o catalogo real.

    python testar_refs.py

Nao ha corpus ainda: o que se mede aqui e se toda `ref` escrita no catalogo
consegue virar dispositivo enderecavel. Referencia que nao resolve e citacao que
o validador da fase 4 nao vai conseguir conferir - some do indice em silencio,
que e exatamente o modo de falha que o projeto inteiro existe para evitar.
"""

from collections import Counter

from app.catalogo.loader import carregar
from app.corpus.refs import interpretar

catalogo = carregar()

fundamentos = [
    (origem, f)
    for origem, lista in (
        [(f"pedido {p.id}", p.fundamentos) for p in catalogo.pedidos]
        + [(f"armadilha {a.id}", a.fundamentos) for a in catalogo.armadilhas]
    )
    for f in lista
]

distintas: dict[tuple[str, str], list[str]] = {}
for origem, f in fundamentos:
    distintas.setdefault((f.tipo, f.ref), []).append(origem)

print(f"{len(fundamentos)} fundamentos, {len(distintas)} referencias distintas\n")

falhas: list[tuple[str, str, list[str]]] = []
observacoes: list[tuple[str, str]] = []
por_obra: Counter[str] = Counter()
total_urns = 0

for (tipo, ref), origens in sorted(distintas.items()):
    r = interpretar(tipo, ref)
    if not r.resolvido:
        falhas.append((tipo, ref, origens))
        continue

    total_urns += len(r.urns)
    por_obra[r.obra or "?"] += 1
    if r.observacao:
        observacoes.append((ref, r.observacao))

    amostra = ", ".join(r.urns[:3])
    if len(r.urns) > 3:
        amostra += f", ... (+{len(r.urns) - 3})"
    marca = " [+paragrafos]" if r.inclui_paragrafos else ""
    print(f"  {ref:<38} -> {amostra}{marca}")

print(f"\n{total_urns} dispositivos enderecados por {len(distintas) - len(falhas)} referencias")
print("obras: " + ", ".join(f"{o} ({n})" for o, n in por_obra.most_common()))

if observacoes:
    print("\nDIVERGENCIAS DE TIPO (o catalogo classificou de um jeito, a ref diz outro)")
    for ref, nota in observacoes:
        print(f"  {ref}: {nota}")

if falhas:
    print(f"\nNAO RESOLVIDAS ({len(falhas)})")
    for tipo, ref, origens in falhas:
        print(f"  [{tipo}] {ref}  <- {', '.join(sorted(set(origens)))}")
    raise SystemExit(1)

print("\ntodas as referencias do catalogo resolvem")
