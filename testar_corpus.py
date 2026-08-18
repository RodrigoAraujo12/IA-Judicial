"""Esquema do corpus: vigencia por data e busca lexical.

    python testar_corpus.py

O caso de teste e o art. 71, par. 4o, da CLT, que e o pior caso do projeto: a
Reforma mudou a REGRA (periodo integral -> so o suprimido) e a NATUREZA
(salarial -> indenizatoria). Um indice sem eixo temporal devolve a redacao de
hoje para um contrato de 2016 e a peca sai errada sem nenhum sinal de erro.

Os textos abaixo sao FIXTURE, nao corpus: servem so para exercitar o esquema. A
ingestao real vem do Planalto, com URL, data de captura e sha256 - e so o que
passar por la pode ser citado.
"""

import tempfile
from datetime import date
from pathlib import Path

from app.corpus import banco
from app.corpus.banco import Dispositivo

CAMINHO = Path(tempfile.gettempdir()) / "corpus_teste.db"
CAMINHO.unlink(missing_ok=True)

con = banco.conectar(CAMINHO)
fonte = banco.registrar_fonte(
    con,
    obra="clt",
    url="https://www.planalto.gov.br/ccivil_03/decreto-lei/del5452.htm",
    bruto=b"fixture - nao e a captura real",
)

PRE = (
    "Quando o intervalo para repouso e alimentacao, previsto neste artigo, nao "
    "for concedido pelo empregador, este ficara obrigado a remunerar o periodo "
    "correspondente com um acrescimo de no minimo 50% sobre o valor da "
    "remuneracao da hora normal de trabalho."
)
POS = (
    "A nao concessao ou a concessao parcial do intervalo intrajornada minimo, "
    "para repouso e alimentacao, a empregados urbanos e rurais, implica o "
    "pagamento, de natureza indenizatoria, apenas do periodo suprimido, com "
    "acrescimo de 50% sobre o valor da remuneracao da hora normal de trabalho."
)

banco.gravar(
    con,
    [
        Dispositivo(
            urn="clt/art-71/par-4",
            obra="clt",
            especie="paragrafo",
            rotulo="CLT, art. 71, par. 4o",
            texto=PRE,
            texto_indexado=f"CLT art. 71 par. 4o intervalo intrajornada. {PRE}",
            pai="clt/art-71",
            ordem=71004,
            vigencia_inicio="1994-07-27",
            vigencia_fim="2017-11-10",
            alterado_por="Lei 8.923/1994",
        ),
        Dispositivo(
            urn="clt/art-71/par-4",
            obra="clt",
            especie="paragrafo",
            rotulo="CLT, art. 71, par. 4o",
            texto=POS,
            texto_indexado=f"CLT art. 71 par. 4o intervalo intrajornada. {POS}",
            pai="clt/art-71",
            ordem=71004,
            vigencia_inicio="2017-11-11",
            alterado_por="Lei 13.467/2017",
        ),
    ],
    fonte,
)
con.commit()

falhas = []


def conferir(rotulo: str, obtido, esperado) -> None:
    ok = obtido == esperado
    print(f"  {'ok ' if ok else 'ERRO'} {rotulo}")
    if not ok:
        falhas.append(f"{rotulo}: esperado {esperado!r}, obtido {obtido!r}")


print("vigencia do art. 71, par. 4o")
antes = banco.vigente_em(con, "clt/art-71/par-4", date(2016, 5, 1))
depois = banco.vigente_em(con, "clt/art-71/par-4", date(2020, 5, 1))
vespera = banco.vigente_em(con, "clt/art-71/par-4", date(2017, 11, 10))
estreia = banco.vigente_em(con, "clt/art-71/par-4", date(2017, 11, 11))

conferir("contrato de 2016 recebe a redacao anterior", antes["alterado_por"], "Lei 8.923/1994")
conferir("contrato de 2020 recebe a redacao da Reforma", depois["alterado_por"], "Lei 13.467/2017")
conferir("10/11/2017 ainda e regime anterior", vespera["alterado_por"], "Lei 8.923/1994")
conferir("11/11/2017 ja e regime novo", estreia["alterado_por"], "Lei 13.467/2017")
conferir("periodo integral so na redacao anterior", "periodo suprimido" in antes["texto"], False)
conferir("periodo suprimido so na redacao nova", "periodo suprimido" in depois["texto"], True)
conferir("duas redacoes registradas", len(banco.redacoes(con, "clt/art-71/par-4")), 2)

print("\nbusca lexical (Via 1)")
achados = con.execute(
    """SELECT d.urn, d.vigencia_inicio, bm25(dispositivos_fts) AS score
       FROM dispositivos_fts JOIN dispositivos d ON d.id = dispositivos_fts.rowid
       WHERE dispositivos_fts MATCH ? ORDER BY score""",
    ("intrajornada",),
).fetchall()
conferir("'intrajornada' acha as duas redacoes", len(achados), 2)

# O escritorio digita sem acento; o texto da lei tem acento. Sem remove_diacritics
# essa consulta volta vazia e a busca parece simplesmente nao funcionar.
com_acento = con.execute(
    "SELECT COUNT(*) FROM dispositivos_fts WHERE dispositivos_fts MATCH ?",
    ("indenizatória",),
).fetchone()[0]
conferir("consulta acentuada casa texto sem acento", com_acento, 1)

# Numero de artigo tem de ser recuperavel por token exato: e o caso de uso mais
# comum do escritorio, e o vetor denso e justamente ruim nisso.
por_numero = con.execute(
    "SELECT COUNT(*) FROM dispositivos_fts WHERE dispositivos_fts MATCH ?",
    ('"art. 71"',),
).fetchone()[0]
conferir("busca por 'art. 71' encontra o dispositivo", por_numero, 2)

print("\nestatisticas:", banco.estatisticas(con))
con.close()
CAMINHO.unlink(missing_ok=True)

if falhas:
    print("\nFALHOU")
    for f in falhas:
        print("  " + f)
    raise SystemExit(1)
print("\nesquema do corpus ok")
