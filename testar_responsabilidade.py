"""Os quatro blocos que faltavam: quem paga, justa causa, salario a margem, ferias.

    python testar_responsabilidade.py

O caso de teste e o do roteiro que veio do escritorio: contrato sem registro no
inicio, dispensa por justa causa sem nenhuma advertencia anterior, empresa
esvaziada e outra empresa tocando o mesmo negocio.

Esses quatro blocos entraram porque um roteiro de entrevista escrito a mao
cobria coisas que o catalogo nao cobria. O mais consequente e o primeiro: sem
ele a peca sai perfeita, o pedido e julgado procedente, e a execucao morre num
CNPJ sem bens.
"""

from datetime import date

from app.catalogo.loader import carregar
from app.motor import analisar

falhas = []


def conferir(rotulo: str, obtido, esperado) -> None:
    ok = obtido == esperado
    print(f"  {'ok ' if ok else 'ERRO'} {rotulo}")
    if not ok:
        falhas.append(f"{rotulo}: esperado {esperado!r}, obtido {obtido!r}")


CATALOGO = carregar()

BASE = {
    "data_admissao": "2019-08-01",
    "data_saida": "2024-09-12",
    "data_ajuizamento": "2025-03-10",
    "funcao": "Retificador de motores",
    "salario_base": 2800.0,
    "local_prestacao": "Contagem/MG",
    "registro_ctps": False,
    "modalidade_saida": "justa_causa",
}


def analisar_com(**extra):
    return analisar(CATALOGO, {**BASE, **extra})


def cabiveis(a):
    return {p.pedido.id for p in a.cabiveis}


def pendentes(a):
    return {p.pedido.id for p in a.possiveis}


def armadilhas(a):
    return {x.id for x in a.armadilhas}


# --- 1. quem paga -----------------------------------------------------------

print("responsabilidade patrimonial")

# Sucessao: a nova empresa toca o mesmo negocio.
a = analisar_com(empresa_sucessora=True, empresa_ativa=False, patrimonio_esvaziado=True)
conferir("sucessora entra no polo passivo", "sucessao_empresarial" in cabiveis(a), True)
conferir(
    "patrimonio esvaziado aciona o alerta de execucao",
    "execucao_frustrada" in armadilhas(a),
    True,
)

# Grupo economico exige atuacao conjunta, e nao apenas socios comuns: e o que o
# art. 2o, par. 3o passou a exigir depois da Reforma.
so_socios = analisar_com(outras_empresas_grupo=True, grupo_atuacao_conjunta=False)
conferir("socios comuns, sozinhos, nao formam grupo", "grupo_economico" in cabiveis(so_socios), False)

integradas = analisar_com(outras_empresas_grupo=True, grupo_atuacao_conjunta=True)
conferir("atuacao conjunta forma grupo", "grupo_economico" in cabiveis(integradas), True)

# Sem resposta sobre a atuacao conjunta, o pedido nao pode ser descartado: ele
# fica no terceiro estado, com a pergunta nomeada.
indefinido = analisar_com(outras_empresas_grupo=True)
conferir("sem a resposta, o grupo fica a investigar", "grupo_economico" in pendentes(indefinido), True)
faltam = next(p.faltam for p in indefinido.possiveis if p.pedido.id == "grupo_economico")
conferir("e o sistema diz qual pergunta falta", "grupo_atuacao_conjunta" in faltam, True)

conferir(
    "tomador de servicos responde de forma subsidiaria",
    "responsabilidade_tomador" in cabiveis(analisar_com(prestava_para_tomador=True)),
    True,
)


# --- 2. justa causa: os requisitos agora sao perguntados --------------------

print("\nrequisitos da justa causa")

# O pedido de reversao ja cabia so pela modalidade de saida - isso nao muda.
conferir("reversao cabe pela propria justa causa", "reversao_justa_causa" in cabiveis(a), True)

sem_punicao = analisar_com(justa_causa_advertencias="nenhuma")
conferir(
    "ficha limpa aciona a tese de ausencia de gradacao",
    "justa_causa_sem_gradacao" in armadilhas(sem_punicao),
    True,
)

com_punicao = analisar_com(justa_causa_advertencias="escritas")
conferir(
    "havendo advertencia escrita, a tese nao e oferecida",
    "justa_causa_sem_gradacao" in armadilhas(com_punicao),
    False,
)

bis = analisar_com(justa_causa_mesmo_fato_punido=True)
conferir("fato ja punido aciona o non bis in idem", "justa_causa_bis_in_idem" in armadilhas(bis), True)

# As teses de justa causa sao fundamentacao, nao pedido ao juizo: nao podem sair
# impressas como requerimento da peca.
tese = next(x for x in sem_punicao.armadilhas if x.id == "justa_causa_sem_gradacao")
conferir("a tese nao e requerimento da peca", tese.requerimento, False)
gratuita = next(x for x in a.armadilhas if x.id == "justica_gratuita")
conferir("justica gratuita e requerimento da peca", gratuita.requerimento, True)


# --- 3. salario pago a margem ----------------------------------------------

print("\nparcelas pagas a margem do contracheque")

fora = analisar_com(salario_por_fora=True)
conferir("pagamento por fora gera pedido de integracao", "integracao_parcelas" in cabiveis(fora), True)

premio = analisar_com(parcelas_variaveis=["premio"], parcelas_no_contracheque=False)
conferir("parcela habitual fora da folha tambem gera", "integracao_parcelas" in cabiveis(premio), True)

na_folha = analisar_com(parcelas_variaveis=["premio"], parcelas_no_contracheque=True)
conferir("parcela lancada em folha nao gera o pedido", "integracao_parcelas" in cabiveis(na_folha), False)

pedido = CATALOGO.pedido("integracao_parcelas")
conferir(
    "o pedido avisa que muda a base dos demais",
    any("BASE" in x for x in pedido.alertas),
    True,
)
conferir("e traz a variacao da Reforma", len(pedido.variacao_temporal), 2)


# --- 4. ferias --------------------------------------------------------------

print("\nferias")

conferir(
    "nunca gozadas geram dobra",
    "ferias_em_dobro" in cabiveis(analisar_com(ferias_gozadas="nenhuma")),
    True,
)
conferir(
    "pagamento fora do prazo gera dobra",
    "ferias_em_dobro" in cabiveis(analisar_com(ferias_gozadas="todas", ferias_pagas_no_prazo=False)),
    True,
)
conferir(
    "trabalho durante as ferias gera dobra",
    "ferias_em_dobro"
    in cabiveis(analisar_com(ferias_gozadas="todas", ferias_pagas_no_prazo=True, trabalhou_durante_ferias=True)),
    True,
)
conferir(
    "ferias regulares nao geram pedido",
    "ferias_em_dobro"
    in cabiveis(
        analisar_com(ferias_gozadas="todas", ferias_pagas_no_prazo=True, trabalhou_durante_ferias=False)
    ),
    False,
)

# A Sumula 450 sustenta uma das tres hipoteses e teve a validade questionada. O
# catalogo nao pode afirma-la como se fosse pacifica.
ferias = CATALOGO.pedido("ferias_em_dobro")
sum450 = next(f for f in ferias.fundamentos if "450" in f.ref)
conferir("a Sumula 450 sai marcada como controversa", sum450.controverso, True)
arts = {f.ref for f in ferias.fundamentos}
conferir("e o art. 137 sustenta a hipotese que nao depende dela", "art. 137" in arts, True)


# --- 5. tudo junto, no caso do roteiro -------------------------------------

print("\no caso completo")

completo = analisar_com(
    empresa_sucessora=True,
    empresa_ativa=False,
    patrimonio_esvaziado=True,
    justa_causa_advertencias="nenhuma",
    salario_por_fora=True,
    ferias_gozadas="algumas",
    ferias_pagas_no_prazo=False,
)
esperados = {"sucessao_empresarial", "integracao_parcelas", "ferias_em_dobro", "reversao_justa_causa"}
conferir("os quatro blocos aparecem juntos", esperados <= cabiveis(completo), True)
conferir(
    "e nenhum deles ficou no terceiro estado por falta de pergunta",
    esperados & pendentes(completo),
    set(),
)

if falhas:
    print("\nFALHOU")
    for f in falhas:
        print("  " + f)
    raise SystemExit(1)
print("\nresponsabilidade, justa causa, salario e ferias ok")
