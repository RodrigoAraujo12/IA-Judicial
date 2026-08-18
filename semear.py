"""Carrega tres casos de exemplo no banco, para conferir o sistema funcionando.

    python semear.py

Depois abra http://127.0.0.1:8000/casos e clique em cada um. Os casos sao
ficticios e foram desenhados para exercitar partes diferentes do motor - o que
cada um testa esta em EXEMPLOS.md.
"""

from app import persistencia

# --- 1. Marcio: o caso completo, ainda a ajuizar ----------------------------
# Caso denso: aciona insalubridade e periculosidade ao mesmo tempo, que nao se
# acumulam (art. 193, par. 2o), e ponto britanico, que aciona a Sumula 338.
MARCIO = {
    "data_admissao": "2019-03-15",
    "data_saida": "2026-04-30",
    "funcao": "Auxiliar de producao",
    "salario_base": 2400.0,
    "local_prestacao": "Contagem/MG",
    "registro_ctps": True,
    "empresa_mais_20_empregados": True,
    "empresa_ativa": True,
    "jornada_contratual": "44h",
    "horas_extras_habituais": True,
    "horas_extras_pagas": False,
    "controle_ponto": "sim_britanico",
    "intervalo_gozado": "parcial",
    "interjornada_violada": False,
    "trabalho_noturno": True,
    "exposicao_agente_nocivo": True,
    "agente_nocivo": ["ruido"],
    "epi_fornecido": "sim_sem_fiscalizacao",
    "adicional_insalubridade_pago": False,
    "exposicao_perigo": True,
    "tipo_perigo": ["inflamaveis"],
    "adicional_periculosidade_pago": False,
    "transferencia": False,
    "desvio_ou_acumulo": "nenhum",
    "paradigma_existe": False,
    "modalidade_saida": "sem_justa_causa",
    "verbas_pagas": "parcial",
    "prazo_10_dias_cumprido": False,
    "fgts_depositado": "parcial",
    "multa_40_paga": False,
    "guias_seguro_desemprego": False,
    "assedio_moral": False,
    "afastamento_acidentario": False,
    "doenca_ocupacional": False,
    "gestante_na_dispensa": False,
    "hipossuficiente": True,
}

# --- 2. Regina: pejotizacao, com lacunas de proposito -----------------------
# Metade das perguntas em branco para ver a coluna "a investigar" dizendo
# exatamente o que falta perguntar ao cliente.
REGINA = {
    "data_admissao": "2022-06-01",
    "data_saida": "2026-02-20",
    "funcao": "Consultora de vendas",
    "salario_base": 3200.0,
    "local_prestacao": "Sao Paulo/SP",
    "registro_ctps": False,
    "vinculo_negado": True,
    "empresa_ativa": True,
    "jornada_contratual": "44h",
    "horas_extras_habituais": True,
    "horas_extras_pagas": False,
    "controle_ponto": "nao_havia",
    "modalidade_saida": "sem_formalizacao",
    "verbas_pagas": "nenhuma",
    "hipossuficiente": True,
}

# --- 3. Joao: processo ja ajuizado em 2019 ----------------------------------
# Unico jeito de ver a cisao pela Reforma: acao ajuizada antes de o corte
# quinquenal engolir todo o periodo anterior a 11/11/2017.
JOAO = {
    "data_admissao": "2015-02-01",
    "data_saida": "2019-09-30",
    "data_ajuizamento": "2019-10-15",
    "funcao": "Operador de empilhadeira",
    "salario_base": 2400.0,
    "local_prestacao": "Guarulhos/SP",
    "registro_ctps": True,
    "empresa_mais_20_empregados": True,
    "empresa_ativa": True,
    "jornada_contratual": "44h",
    "horas_extras_habituais": True,
    "horas_extras_pagas": False,
    "controle_ponto": "sim_britanico",
    "intervalo_gozado": "parcial",
    "trabalho_noturno": False,
    "exposicao_agente_nocivo": False,
    "exposicao_perigo": False,
    "transferencia": False,
    "desvio_ou_acumulo": "nenhum",
    "paradigma_existe": False,
    "modalidade_saida": "sem_justa_causa",
    "verbas_pagas": "parcial",
    "prazo_10_dias_cumprido": False,
    "fgts_depositado": "integral",
    "multa_40_paga": True,
    "guias_seguro_desemprego": True,
    "assedio_moral": False,
    "afastamento_acidentario": False,
    "doenca_ocupacional": False,
    "gestante_na_dispensa": False,
    "hipossuficiente": True,
}

CASOS = [
    ("1. Marcio - caso completo (adicionais alternativos, Sumula 338)", MARCIO),
    ("2. Regina - pejotizacao com lacunas (coluna 'a investigar')", REGINA),
    ("3. Joao - ajuizado em 2019 (cisao pela Reforma)", JOAO),
]

if __name__ == "__main__":
    existentes = {c["nome"] for c in persistencia.listar(200)}
    for nome, respostas in CASOS:
        if nome in existentes:
            print(f"ja existe, pulando: {nome}")
            continue
        caso_id = persistencia.salvar(nome, respostas)
        print(f"criado #{caso_id}: {nome}")
    print("\nAbra http://127.0.0.1:8000/casos")
