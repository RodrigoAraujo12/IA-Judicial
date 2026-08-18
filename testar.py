"""Fumaca: carrega o catalogo e roda um caso real pelo motor.

    python testar.py
"""

from datetime import date

from app.catalogo.loader import carregar
from app.motor import analisar

catalogo = carregar()
print(f"catalogo ok: {len(catalogo.pedidos)} pedidos, "
      f"{len(catalogo.armadilhas)} armadilhas, "
      f"{len(catalogo.entrevista.perguntas)} perguntas\n")

# Contrato que atravessa a Reforma, com respostas parciais de proposito:
# o que sobrar em "a investigar" e o que o motor mandaria perguntar ao cliente.
caso = {
    "data_admissao": "2014-03-10",
    "data_saida": "2024-06-28",
    "funcao": "Auxiliar de producao",
    "salario_base": 2400.0,
    "local_prestacao": "Contagem/MG",
    "registro_ctps": True,
    "empresa_mais_20_empregados": True,
    "horas_extras_habituais": True,
    "horas_extras_pagas": False,
    "controle_ponto": "sim_britanico",
    "intervalo_gozado": "parcial",
    "trabalho_noturno": True,
    "exposicao_agente_nocivo": True,
    "agente_nocivo": ["ruido"],
    "epi_fornecido": "sim_sem_fiscalizacao",
    "adicional_insalubridade_pago": False,
    "modalidade_saida": "sem_justa_causa",
    "verbas_pagas": "parcial",
    "prazo_10_dias_cumprido": False,
    "multa_40_paga": False,
    "hipossuficiente": True,
}

a = analisar(catalogo, caso, hoje=date(2025, 8, 18))

print(f"atravessa a reforma: {a.atravessa_reforma}")
p = a.prescricao
print(f"bienal ate {p.prazo_bienal_ate} (vencida: {p.bienal_vencida}) | "
      f"corte quinquenal {p.corte_quinquenal} | perde periodo anterior: {p.perde_periodo_anterior}\n")

print(f"CABIVEIS ({len(a.cabiveis)})")
for av in a.cabiveis:
    marca = "  [cindir por periodo]" if av.cindir else ""
    print(f"  - {av.pedido.nome}{marca}")

print(f"\nA INVESTIGAR ({len(a.possiveis)})")
for av in a.possiveis:
    print(f"  - {av.pedido.nome}")
    print(f"      falta: {', '.join(av.faltam)}")

print(f"\nAFASTADOS ({len(a.afastados)}): {', '.join(av.pedido.id for av in a.afastados)}")
print(f"\nARMADILHAS ({len(a.armadilhas)})")
for arm in a.armadilhas:
    print(f"  [{arm.gravidade}] {arm.titulo}")

print(f"\nrespondidas {a.respondidas} de {a.total_visiveis} perguntas visiveis")
