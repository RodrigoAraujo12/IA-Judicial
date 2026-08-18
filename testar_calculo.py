"""Fumaca da calculadora: cascata, cisao pela Reforma e memoria de calculo.

    python testar_calculo.py
"""

from datetime import date

from app.calculo.dinheiro import fmt
from app.calculo.motor import calcular
from app.catalogo.loader import carregar
from app.motor import analisar

catalogo = carregar()

# Contrato de 2014 a 2024: atravessa a Reforma e sofre corte quinquenal.
caso = {
    "data_admissao": "2014-03-10",
    "data_saida": "2024-06-28",
    "funcao": "Auxiliar de producao",
    "salario_base": 2400.0,
    "local_prestacao": "Contagem/MG",
    "jornada_contratual": "44h",
    "registro_ctps": True,
    "empresa_mais_20_empregados": True,
    "horas_extras_habituais": True,
    "horas_extras_pagas": False,
    "controle_ponto": "sim_britanico",
    "intervalo_gozado": "parcial",
    "trabalho_noturno": True,
    "exposicao_agente_nocivo": True,
    "epi_fornecido": "sim_sem_fiscalizacao",
    "adicional_insalubridade_pago": False,
    "exposicao_perigo": True,
    "adicional_periculosidade_pago": False,
    "modalidade_saida": "sem_justa_causa",
    "verbas_pagas": "parcial",
    "prazo_10_dias_cumprido": False,
    "fgts_depositado": "parcial",
    "multa_40_paga": False,
    "hipossuficiente": True,
    # quantificacao
    "grau_insalubridade": "medio",
    "base_insalubridade": "salario_minimo",
    "he_horas_mes": 40,
    "he_adicional": 50,
    "noturno_horas_mes": 30,
    "intervalo_minutos_suprimidos": 30,
    "intervalo_dias_mes": 22,
    "saldo_salario_dias": 28,
    "ferias_vencidas": 1,
    "verbas_incontroversas": 3500.0,
}

analise = analisar(catalogo, caso, hoje=date(2025, 8, 18))
c = calcular(catalogo, caso, analise, hoje=date(2025, 8, 18))

print(f"periodo apurado: {c.periodo}  (corte quinquenal: {c.houve_corte_quinquenal})")
print(f"remuneracao base majorada: R$ {fmt(c.remuneracao)}\n")

print(f"{'VERBA':<42}{'PRINCIPAL':>14}{'REFLEXOS':>14}{'TOTAL':>14}")
print("-" * 84)
for v in c.verbas:
    marca = "  (alternativo)" if v.alternativa else ""
    print(f"{(v.nome + marca):<42}{fmt(v.principal):>14}{fmt(v.total_reflexos):>14}{fmt(v.total):>14}")
print("-" * 84)
print(f"{'TOTAL':<42}{fmt(c.total_principal):>14}{fmt(c.total_reflexos):>14}{fmt(c.total):>14}\n")

if c.pendentes:
    print("SEM VALOR (falta quantificar)")
    for v in c.pendentes:
        print(f"  - {v.nome}: {', '.join(v.faltam)}")
    print()

print("OBSERVACOES DO CALCULO")
for o in c.observacoes:
    print(f"  * {o}")

alvo = next((v for v in c.verbas if v.pedido_id == "intervalo_intrajornada"), None)
if alvo:
    print(f"\nMEMORIA - {alvo.nome}  (verba que se cinde na Reforma)")
    for l in alvo.memoria:
        print(f"  {l.descricao:<46} {l.formula:<52} {fmt(l.valor):>13}")
    for l in alvo.reflexos:
        print(f"  + {l.descricao:<44} {l.formula:<52} {fmt(l.valor):>13}")

he = next((v for v in c.verbas if v.pedido_id == "horas_extras"), None)
if he:
    print(f"\nMEMORIA - {he.nome}  (base majorada pela cascata)")
    for l in he.memoria:
        print(f"  {l.descricao:<46} {l.formula:<52} {fmt(l.valor):>13}")


# --- cenario 2: cisao pela Reforma efetivamente incidindo --------------------
# Ajuizado em 2019, o corte quinquenal recua a 2014 e o periodo pre-Reforma
# sobrevive. E aqui que a natureza juridica do intervalo muda no meio da conta.
print("\n" + "=" * 84)
print("CENARIO 2 - contrato 2015-2019, ajuizado em 2019 (cisao efetiva)")
print("=" * 84)

caso2 = dict(caso)
caso2.update({
    "data_admissao": "2015-02-01",
    "data_saida": "2019-09-30",
    "exposicao_perigo": False,
    "adicional_periculosidade_pago": True,
    "trabalho_noturno": False,
})
analise2 = analisar(catalogo, caso2, hoje=date(2019, 10, 15))
c2 = calcular(catalogo, caso2, analise2, hoje=date(2019, 10, 15))

print(f"periodo apurado: {c2.periodo}  (corte: {c2.houve_corte_quinquenal})")
alvo2 = next((v for v in c2.verbas if v.pedido_id == "intervalo_intrajornada"), None)
if alvo2:
    print(f"\nMEMORIA - {alvo2.nome}")
    for l in alvo2.memoria:
        print(f"  {l.descricao:<46} {l.formula:<52} {fmt(l.valor):>13}")
    print(f"  {'principal':<46} {'':<52} {fmt(alvo2.principal):>13}")
    for l in alvo2.reflexos:
        print(f"  + {l.descricao:<44} {l.formula:<52} {fmt(l.valor):>13}")
    print(f"  {'TOTAL':<46} {'':<52} {fmt(alvo2.total):>13}")
    for o in alvo2.observacoes:
        print(f"  * {o}")
