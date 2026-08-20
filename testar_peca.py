"""Minuta da inicial: o que entra, o que fica de fora, e o que nunca aparece.

    python testar_peca.py

Tres coisas que este teste existe para trancar.

**A cisao chega ao texto.** Contrato que atravessa a Reforma nao gera um pedido
de intervalo intrajornada, gera dois - e cada um cita a redacao que valia no seu
periodo. Se um dia a minuta passar a citar so a redacao de hoje, o pedido de 2016
sai com a lei errada e com a mesma cara de quem acertou.

**O terceiro estado sobrevive.** Pedido "a investigar" nao entra no corpo da peca
nem some: sai numa lista propria, com a pergunta que o destrancaria. Achatar isso
desfaz o que a triagem construiu.

**Nenhum valor aparece.** A calculadora foi removida de proposito, e a minuta nao
pode reintroduzir valor por outra porta - nem como numero, nem como lacuna
"[VALOR]" que alguem protocola sem preencher.
"""

from datetime import date

from app.catalogo.loader import carregar
from app.motor import analisar
from app.peca import redator

falhas = []


def conferir(rotulo: str, obtido, esperado) -> None:
    ok = obtido == esperado
    print(f"  {'ok ' if ok else 'ERRO'} {rotulo}")
    if not ok:
        falhas.append(f"{rotulo}: esperado {esperado!r}, obtido {obtido!r}")


CATALOGO = carregar()

# Contrato de 2015 a 2019: atravessa a Reforma, que e o caso interessante.
ATRAVESSA = {
    "data_admissao": "2015-02-02",
    "data_saida": "2019-03-29",
    "data_ajuizamento": "2019-06-10",
    "funcao": "Operador de empilhadeira",
    "salario_base": 2100.0,
    "local_prestacao": "Joao Pessoa/PB",
    "registro_ctps": True,
    "jornada_contratual": "44h",
    "intervalo_gozado": "parcial",
    "reclamante_nome": "Joao da Silva Sauro",
    "reclamante_nacionalidade": "brasileiro",
    "reclamante_estado_civil": "solteiro",
    "reclamante_cpf": "111.222.333-44",
    "reclamada_razao_social": "Transportadora Exemplo Ltda.",
    "reclamada_cnpj": "99.888.777/0001-66",
    "narrativa_fatos": "Primeira linha do relato.\n\nSegunda linha, apos quebra.",
}


def montar(respostas, con=None):
    return redator.montar(CATALOGO, respostas, analisar(CATALOGO, respostas), con)


# --- 1. qualificacao --------------------------------------------------------

print("qualificacao das partes")

m = montar(ATRAVESSA)
conferir("o nome sai em caixa alta", m.reclamante.startswith("JOAO DA SILVA SAURO,"), True)
conferir("o CPF entra com a formula forense", "inscrito no CPF sob o nº 111.222.333-44" in m.reclamante, True)
# O estado civil e `escolha`: o que vai para a peca e o rotulo, nao o codigo.
conferir("estado civil sai por extenso", "solteiro" in m.reclamante.lower(), True)
conferir("a reclamada e qualificada como pessoa juridica", "pessoa jurídica de direito privado" in m.reclamada, True)

# Sem nome, a peca nao pode comecar pela profissao como se fosse o nome.
sem_nome = montar({**ATRAVESSA, "reclamante_nome": ""})
conferir("falta de nome aparece como falta", sem_nome.reclamante.startswith("[RECLAMANTE NÃO QUALIFICADO]"), True)

conferir("o juizo vem do local da prestacao", "JOAO PESSOA/PB" in m.juizo, True)


# --- 2. fatos ---------------------------------------------------------------

print("\nhistoria dos fatos")

titulo, texto = m.fatos[0]
conferir("o bloco recebe titulo de peca, nao o texto da pergunta", titulo, "Do contrato de trabalho e de sua execução")
# A narrativa e do cliente. Reescrever vira alegacao que ele nao fez.
conferir("a narrativa entra literal", texto, ATRAVESSA["narrativa_fatos"])


# --- 3. a cisao chega ao texto ---------------------------------------------

print("\ncisao pela Reforma")

conferir("o caso atravessa a Reforma", m.atravessa_reforma, True)

intervalo = [p for p in m.pedidos if p.startswith("Intervalo intrajornada")]
conferir("o pedido cindido vira dois", len(intervalo), 2)
conferir("um por periodo", sorted(intervalo), [
    "Intervalo intrajornada suprimido (a partir de 11/11/2017)",
    "Intervalo intrajornada suprimido (até 10/11/2017)",
])

conferir(
    "a vespera da Reforma e o ultimo dia do regime anterior",
    redator.VESPERA_REFORMA,
    date(2017, 11, 10),
)


# --- 4. o terceiro estado -------------------------------------------------

print("\npedido a investigar")

# Sem responder se havia registro em CTPS, o vinculo fica indefinido.
indefinido = {k: v for k, v in ATRAVESSA.items() if k != "registro_ctps"}
mi = montar(indefinido)
nomes_pedidos = set(mi.pedidos)
pendentes = {d.pedido.nome for d in mi.nao_incluidos}

conferir("ha pedido em estado indefinido", bool(pendentes), True)
conferir("nenhum pendente vazou para os pedidos", nomes_pedidos & pendentes, set())
conferir(
    "cada pendente diz o que falta, em texto de pergunta",
    all(d.faltam and not any(f.islower() and "_" in f for f in d.faltam) for d in mi.nao_incluidos),
    True,
)


# --- 5. nenhum valor --------------------------------------------------------

print("\nausencia de valor")

corpo = " ".join(
    [m.reclamante, m.reclamada, *m.pedidos, *(t for _, t in m.fatos)]
)
for proibido in ["[VALOR", "R$", "valor da causa"]:
    conferir(f"a minuta nao escreve {proibido!r}", proibido.lower() in corpo.lower(), False)


# --- 6. citacao pelo corpus, quando ele existe ------------------------------

from pathlib import Path

if Path("dados/corpus.db").exists():
    from app.corpus import banco

    print("\ncitacoes resolvidas contra o corpus")
    con = banco.conectar()
    mc = montar(ATRAVESSA, con)

    bloco = next(b for b in mc.fundamentacao if b.pedido.id == "intervalo_intrajornada")
    art71 = [c for c in bloco.citacoes if c.rotulo and "71" in c.rotulo]
    conferir("o art. 71 par. 4o e citado nas duas redacoes", len(art71), 2)
    janelas = sorted(c.vigencia for c in art71)
    conferir("uma redacao termina na vespera da Reforma", janelas[0].endswith("2017-11-10"), True)
    conferir("a outra comeca na Reforma", janelas[1].startswith("2017-11-11"), True)
    conferir(
        "as duas trazem texto diferente",
        art71[0].texto != art71[1].texto,
        True,
    )

    # Sumula do TST ainda nao esta no corpus. Citar sem transcrever e o certo;
    # transcrever de memoria seria inventar.
    sem_corpus = [c for c in bloco.citacoes if c.texto is None]
    conferir("obra fora do corpus cita sem transcrever", bool(sem_corpus), True)
    con.close()
else:
    print("\n(corpus nao ingerido - rode: python -m app.corpus.indexar clt)")

if falhas:
    print("\nFALHOU")
    for f in falhas:
        print("  " + f)
    raise SystemExit(1)
print("\nminuta da inicial ok")
