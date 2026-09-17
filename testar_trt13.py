"""Sumulas do TRT-13: parsing das paginas do NUGEP e vigencia dos verbetes.

    python testar_trt13.py     (a segunda metade exige `python -m app.corpus.indexar trt13`)

O que este arquivo defende:

**A data certa e a ultima da linha, e nem toda data e de vigencia.** "Acordao
disponibilizado em 22.10.2015. Sumula disponibilizada em 20, 21 e 22 de outubro
de 2015" abre em 22.10.2015. "..., e em 07, 08 e 11.03.2019, por mera
formalidade" NAO move nada. Numero de processo ("0038800-03.2009.5.13.0000")
nao e data.

**Cancelada fecha janela; revisada nao move o inicio.** A Sumula 7 caiu em
03.03.2021 e um caso de 2016 continua encontrando-a. A Sumula 22 foi revisada por
IAC em 2026 com o mesmo texto - um caso de 2020 continua encontrando-a.

**Sumula de outro tribunal nao entra no caso.** Um caso da Paraiba ve a Sumula 9
do TRT-13; um de Pernambuco, nao.
"""

import sys
from datetime import date

from app.corpus import banco, busca, trt13
from app.corpus.refs import interpretar
from app import jurisdicao

sys.stdout.reconfigure(encoding="utf-8")
falhas: list[str] = []


def conferir(rotulo: str, obtido, esperado) -> None:
    ok = obtido == esperado
    print(f"  {'ok  ' if ok else 'ERRO'} {rotulo}")
    if not ok:
        falhas.append(f"{rotulo}: esperado {esperado!r}, obtido {obtido!r}")


# --- 1. datas ---------------------------------------------------------------

print("a ultima data da linha")

conferir("tres dias de publicacao: vale o ultimo",
         trt13.ultima_data("disponibilizada no DEJT, em 28, 29 e 30.06.2010."), date(2010, 6, 30))
conferir("'1º, 02 e 03.03.2021' le o ordinal",
         trt13.ultima_data("no DEJT nos dias 1º, 02 e 03.03.2021."), date(2021, 3, 3))
conferir("mes por extenso",
         trt13.ultima_data("em 20, 21 e 22 de outubro de 2015 (Protocolo n.º 24.894/2015)."), date(2015, 10, 22))
conferir("a data do acordao, que vem antes, nao vale",
         trt13.ultima_data("Acórdão disponibilizado no DEJT, em 19.10.2015. Súmula disponibilizada no DEJT, "
                           "em 20, 21 e 22 de outubro de 2015."), date(2015, 10, 22))
conferir("republicacao por mera formalidade e ignorada",
         trt13.ultima_data("Súmula disponibilizada no DEJT, em 20, 21 e 22.06.2016 (Protocolo n.º 10.448/2016), "
                           "e em 07, 08 e 11.03.2019, por mera formalidade (Protocolo n.º 2.831/2019)."),
         date(2016, 6, 22))
conferir("numero de processo nao e data",
         trt13.ultima_data("Incidente de Uniformização de Jurisprudência n.º 0038800-03.2009.5.13.0000."), None)
# Tag inline vira NADA, entao "1<span>9.12.2017" chega aqui como "19.12.2017". O
# que sobra picotado e a quebra de BLOCO no meio da data - "20.09." numa linha e
# "2016" na seguinte -, e ai o espaco entre as partes tem de ser tolerado.
conferir("data emendada depois das tags le inteira",
         trt13.ultima_data("Súmula disponibilizada no DEJT em 19.12.2017, 09 e 10.01.2018"), date(2018, 1, 10))
conferir("data partida por quebra de bloco tambem",
         trt13.ultima_data("Súmula disponibilizada no DEJT, em 16, 19 e 20.09. 2016 (Protocolo n.º 000-15.999/2016)."),
         date(2016, 9, 20))
conferir("barra tambem serve", trt13.ultima_data("publicado em 16/07/2025."), date(2025, 7, 16))


# --- 2. vigencia por status -------------------------------------------------

print("\nvigencia por evento do historico")

ORIGINAL = "Redação original: Resolução Administrativa n.º 223/2003, disponibilizada no DJ em 07.12.2003, 10.12.2003 e 11.12.2003."
inicio, fim, rev, _ = trt13.vigencia("vigente", ORIGINAL)
conferir("original abre em 11.12.2003", (inicio, fim, rev), (date(2003, 12, 11), None, False))

inicio, fim, rev, cab = trt13.vigencia(
    "cancelada", ORIGINAL + " Súmula cancelada: Resolução Administrativa n.º 42/2017. Disponibilizada no DEJT em 28.04.2017.")
conferir("cancelada fecha na vespera", (inicio, fim, rev), (date(2003, 12, 11), date(2017, 4, 27), False))
conferir("e o cabecalho diz quem cancelou", cab.startswith("Súmula cancelada"), True)

inicio, fim, rev, _ = trt13.vigencia("cancelada", ORIGINAL)
conferir("cancelada sem data legivel vira revogado", rev, True)

inicio, fim, rev, _ = trt13.vigencia(
    "alterada", ORIGINAL + " Redação alterada: Resolução Administrativa n.º 176/2012, disponibilizada no DEJT, em 07.01.2013.")
conferir("alterada substitui o inicio", (inicio, fim), (date(2013, 1, 7), None))

inicio, fim, rev, _ = trt13.vigencia(
    "alterada", ORIGINAL + " Inclusão do item II: IUJ n.º 1311000-26.2017.5.13.0000. Súmula disponibilizada no DEJT, em 10, 11 e 12.07.2018.")
conferir("inclusao de item tambem", inicio, date(2018, 7, 12))

inicio, fim, rev, _ = trt13.vigencia(
    "revisada",
    "Redação original: IUJ n.º 0130129-86.2015.5.13.0000. Súmula disponibilizada no DEJT, em 20, 21 e 22 de outubro de 2015. "
    "Revisão : Incidente de Assunção de Competência nº 0001360-64.2024.5.13.0026 (Tema 10). Acórdão publicado no DEJT, em 21.01.2026. "
    "Tese jurídica fixada: \"1. No período anterior a 11/11/2017, incide a prescrição parcial\".")
conferir("revisada NAO move o inicio", (inicio, fim, rev), (date(2015, 10, 22), None, False))


# --- 3. a pagina inteira ----------------------------------------------------

print("\nde pagina a verbete")

PAGINA = """<html><body>
<h1 class="documentFirstHeading">SÚMULA N.º 42 (alterada)</h1>
<div class="documentDescription description">CEF. SUPERVISOR. CARGO COM FIDÚCIA.</div>
<div id="content-core"><div id="parent-fieldname-text">
<p>O supervisor <span>centralizador</span> exerce cargo de <b>fidúcia</b> intermediária.</p>
<p><em><strong>Precedentes:</strong></em></p>
<p>RO-0000823-55.2016.5.13.0024 (DEJT 05.12.2017), Relator Fulano.</p>
<p><i><b>Histórico:</b></i></p>
<p>Redação original: IUJ n.º 1331100-02.2017.5.13.0000. Súmula disponibilizada no DE<span>N</span>JT em 1<span>9.12.2017</span>, 09 e 10<span>.0</span>1<span>.201</span>8.</p>
<p>Redação alterada: RA n.º 1/2019, disponibilizada no DEJT em 05.02.2019.</p>
</div></div>
<div id="viewlet-below-content"></div></body></html>"""

v = trt13.verbete(PAGINA)
conferir("numero", v.numero, 42)
conferir("status", v.status, "alterada")
conferir("titulo vem da descricao", v.titulo, "CEF. SUPERVISOR. CARGO COM FIDÚCIA.")
conferir("tag inline nao parte palavra", v.texto, "O supervisor centralizador exerce cargo de fidúcia intermediária.")
conferir("precedentes ficam fora do texto", "Relator" in v.texto, False)
conferir("historico fica fora do texto", "Redação" in v.texto, False)
conferir("inicio e o da alteracao", v.vigencia_inicio, date(2019, 2, 5))
conferir("urn e rotulo", (v.urn, v.rotulo), ("sumula-trt13/42", "Sumula 42 do TRT-13"))


# --- 4. referencia ----------------------------------------------------------

print("\nreferencia a sumula regional")

conferir("'Sumula 7 do TRT-13' resolve", interpretar("sumula_trt", "Sumula 7 do TRT-13").urns, ["sumula-trt13/7"])
conferir("'Sumula 9 do TRT da 13a Regiao' tambem",
         interpretar("sumula_trt", "Sumula 9 do TRT da 13a Regiao").urns, ["sumula-trt13/9"])
conferir("outro tribunal e outra obra", interpretar("sumula_trt", "Sumula 9 do TRT-6").obra, "sumula-trt6")
conferir("a busca reconhece o tipo pela forma", busca._tipo_provavel("Sumula 7 do TRT-13"), "sumula_trt")
conferir("e sem tribunal continua TST", busca._tipo_provavel("Sumula 437"), "sumula_tst")


# --- 5. contra o corpus -----------------------------------------------------

con = banco.conectar()
if not con.execute("SELECT 1 FROM dispositivos WHERE obra = 'sumula-trt13' LIMIT 1").fetchone():
    print("\n(TRT-13 nao ingerido - rode: python -m app.corpus.indexar trt13)")
else:
    print("\no que foi ingerido")
    linhas = con.execute(
        "SELECT ordem, texto, vigencia_fim, revogado FROM dispositivos WHERE obra = 'sumula-trt13' ORDER BY ordem"
    ).fetchall()
    conferir("45 verbetes", len(linhas), 45)
    conferir("sem lacuna na faixa", [l["ordem"] for l in linhas], list(range(1, 46)))
    conferir("35 vigentes hoje (28 nunca alteradas, 5 alteradas, 2 revisadas)",
             sum(1 for l in linhas if not l["vigencia_fim"] and not l["revogado"]), 35)
    conferir("10 canceladas, todas com janela e nenhuma revogada",
             (sum(1 for l in linhas if l["vigencia_fim"]), sum(1 for l in linhas if l["revogado"])), (10, 0))
    conferir("nenhum verbete sem texto", all(len(l["texto"]) > 40 for l in linhas), True)

    print("\nSumula 7 - cancelada em 2021, e a data do caso decide")
    em_2016 = busca.por_referencia(con, "sumula_trt", "Sumula 7 do TRT-13", date(2016, 5, 1))
    conferir("responde para caso de 2016", [a.urn for a in em_2016], ["sumula-trt13/7"])
    hoje = busca.buscar(con, "Sumula 7 do TRT-13", date(2026, 9, 17))
    conferir("hoje nao responde", hoje.achados, [])
    conferir("e diz ate quando valeu", "2021-03-02" in (hoje.aviso or ""), True)

    print("\nSumula 22 - revisada em 2026, texto original continua valendo")
    em_2020 = busca.por_referencia(con, "sumula_trt", "Sumula 22 do TRT-13", date(2020, 1, 1))
    conferir("caso de 2020 encontra", len(em_2020), 1)

    print("\nsumula regional so entra no caso do seu tribunal")
    todas = banco.obras(con)
    conferir("o corpus tem o TRT-13 e so ele", jurisdicao.trts_no_corpus(todas), [13])
    consulta = "grupo economico relacao de coordenacao"
    pb = busca.lexical(con, consulta, date(2026, 9, 17), 10, jurisdicao.obras_para(todas, 13))
    conferir("caso da Paraiba ve a Sumula 9 do TRT-13", "sumula-trt13/9" in [a.urn for a in pb], True)
    pe = busca.buscar(con, consulta, date(2026, 9, 17), 20, jurisdicao.obras_para(todas, 6))
    conferir("caso de Pernambuco nao ve", any(a.obra == "sumula-trt13" for a in pe.achados), False)
    nac = busca.buscar(con, consulta, date(2026, 9, 17), 20, jurisdicao.obras_para(todas, None))
    conferir("consulta sem tribunal nao ve", any(a.obra == "sumula-trt13" for a in nac.achados), False)

con.close()

if falhas:
    print("\nFALHOU")
    for f in falhas:
        print("  " + f)
    raise SystemExit(1)
print("\nsumulas do TRT-13 ok")
