"""Ingestao do corpus normativo.

    python -m app.corpus.indexar              # todas as obras do Planalto em OBRAS
    python -m app.corpus.indexar clt cf adct  # so as escolhidas
    python -m app.corpus.indexar tst          # sumulas e OJs, do Livro do TST
    python -m app.corpus.indexar trt13        # sumulas do TRT-13, do site do NUGEP
    python -m app.corpus.indexar vetores      # Via 2: vetores densos (BGE-M3)
    python -m app.corpus.indexar clt --rebaixar   # rebaixa a captura do site

Grava em dados/corpus.db. O banco e indice: apagar e reconstruir e operacao
normal, nao acidente.

Ao fim, imprime a unica metrica que decide se a ingestao presta: **quantos dos
dispositivos citados pelo catalogo ficaram enderecaveis**. Um parser que reconhece
5.000 artigos e perde o art. 71 par. 4o nao serve para este projeto.
"""

from __future__ import annotations

import sys
import time
from datetime import date

from app.catalogo.loader import carregar
from app.corpus import banco, planalto, trt13, tst
from app.corpus.banco import Dispositivo
from app.corpus.refs import interpretar

# O `piso` e a data em que o texto original passou a valer, e cada um foi lido na
# propria pagina: o DOU do rodape ("Este texto nao substitui o publicado no DOU
# de...") mais o artigo de vigencia da lei. Onde os dois divergem, manda o artigo:
# o Codigo Civil saiu no DOU de 11.1.2002 e so vigorou um ano depois (art. 2.044),
# e a Lei 6.019 teve sessenta dias de vacatio (art. 20).
#
# So as obras que o catalogo cita. Cada lei nova e densidade a mais competindo na
# busca livre - o TST custou 8 consultas em acerto@1 -, entao lei que nenhum
# pedido usa entra quando houver pedido que a use.
_CF = "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm"
OBRAS = {
    "clt": {
        "url": planalto.URL_CLT,
        "arquivo": "clt-planalto.html",
        "inicio": planalto.INICIO_CLT,
        "piso": planalto.VIGENCIA_CLT,
        "nome": "Consolidacao das Leis do Trabalho",
        "sigla": "CLT",
    },
    # O ADCT mora no fim da pagina da CF, com numeracao propria que recomeca no
    # art. 1o. Na passada da CF o guarda de regressao o descarta como norma
    # estranha; aqui ele vira obra sua, a partir do titulo em caixa alta. O
    # `(?-i:...)` e necessario porque o cabecalho da pagina tem um link "Ato das
    # Disposicoes..." em caixa mista, e casar ali comecaria o ADCT no art. 1o da CF.
    "cf": {
        "url": _CF,
        "arquivo": "cf-planalto.html",
        "inicio": None,
        "piso": date(1988, 10, 5),
        "nome": "Constituicao Federal",
        "sigla": "CF",
    },
    "adct": {
        "url": _CF,
        "arquivo": "cf-planalto.html",
        "inicio": r"(?-i:^ATO DAS DISPOSI[CÇ][OÕ]ES CONSTITUCIONAIS TRANSIT)",
        "piso": date(1988, 10, 5),
        "nome": "Ato das Disposicoes Constitucionais Transitorias",
        "sigla": "ADCT",
    },
    "cc": {
        "url": "https://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm",
        "arquivo": "cc-planalto.html",
        "inicio": None,
        "piso": date(2003, 1, 11),
        "nome": "Codigo Civil (Lei 10.406/2002)",
        "sigla": "CC",
    },
    "lei-6019-1974": {
        "url": "https://www.planalto.gov.br/ccivil_03/leis/l6019.htm",
        "arquivo": "lei-6019-1974.html",
        "inicio": None,
        "piso": date(1974, 3, 5),
        "nome": "Lei 6.019/1974 (trabalho temporario e terceirizacao)",
        "sigla": "Lei 6.019/1974",
    },
    "lei-7998-1990": {
        "url": "https://www.planalto.gov.br/ccivil_03/leis/l7998.htm",
        "arquivo": "lei-7998-1990.html",
        "inicio": None,
        "piso": date(1990, 1, 12),
        "nome": "Lei 7.998/1990 (seguro-desemprego)",
        "sigla": "Lei 7.998/1990",
    },
    "lei-8036-1990": {
        "url": "https://www.planalto.gov.br/ccivil_03/leis/l8036consol.htm",
        "arquivo": "lei-8036-1990.html",
        "inicio": None,
        "piso": date(1990, 5, 14),
        "nome": "Lei 8.036/1990 (FGTS)",
        "sigla": "Lei 8.036/1990",
    },
    "lei-8213-1991": {
        "url": "https://www.planalto.gov.br/ccivil_03/leis/l8213cons.htm",
        "arquivo": "lei-8213-1991.html",
        "inicio": None,
        "piso": date(1991, 7, 25),
        "nome": "Lei 8.213/1991 (planos de beneficios da Previdencia)",
        "sigla": "Lei 8.213/1991",
    },
    "lei-12506-2011": {
        "url": "https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2011/lei/l12506.htm",
        "arquivo": "lei-12506-2011.html",
        "inicio": None,
        "piso": date(2011, 10, 13),
        "nome": "Lei 12.506/2011 (aviso previo proporcional)",
        "sigla": "Lei 12.506/2011",
    },
}


def _texto_indexado(rotulo: str, texto: str, caput: str | None) -> str:
    """O que vai para o BM25 e para o vetor, distinto do que se cita.

    Um paragrafo solto perde o assunto: "§ 4o A nao concessao ou a concessao
    parcial..." nao diz de que artigo fala nem que o tema e intervalo. Sem o caput
    junto, esse dispositivo some tanto da busca lexical quanto da densa - e ele e
    justamente um dos mais pedidos.
    """
    partes = [rotulo]
    # O rotulo exibido usa "§ 4º", que e como advogado escreve. Mas o escritorio
    # digita "par. 4" tanto quanto, e "§" nao e tokenizavel pelo FTS5. As duas
    # formas entram no indice para que a busca nao dependa do teclado.
    if "§" in rotulo:
        partes.append(rotulo.replace("§", "paragrafo par."))
    if caput:
        partes.append(caput[:240])
    partes.append(texto)
    return " ".join(partes)


def indexar(chave: str, rebaixar: bool = False) -> None:
    obra = OBRAS[chave]
    print(f"{obra['nome']}")

    bruto = planalto.baixar(obra["url"], obra["arquivo"], forcar=rebaixar)
    print(f"  fonte: {len(bruto):,} bytes")

    trechos = planalto.dispositivos(bruto, chave, inicio=obra["inicio"], sigla=obra["sigla"])
    resolvidos = planalto.com_vigencia(trechos, obra["piso"])

    # MP que caducou sem estar na tabela entraria como alteracao definitiva, e seu
    # texto ficaria valendo para sempre. E o erro que a tabela existe para evitar,
    # entao ele e dito em voz alta.
    if desconhecidas := planalto.mps_sem_tabela(bruto):
        print("  MP COM VIGENCIA ENCERRADA FORA DA TABELA CADUCIDADE:")
        for mp in sorted(desconhecidas):
            print(f"    {mp} - datas nao conhecidas; o texto dela pode ficar vigente")
    print(f"  reconhecidos: {len(trechos)} dispositivos em {len({t.urn for t in trechos})} URNs")

    # Caput de cada artigo, para dar contexto aos subordinados no indice.
    caputs = {t.urn: t.texto for t in trechos if t.especie == "artigo"}

    registros = []
    for t, inicio, fim, revogado in resolvidos:
        raiz = t.urn.split("/")[0] + "/" + t.urn.split("/")[1]
        caput = caputs.get(raiz) if t.especie != "artigo" else None
        registros.append(
            Dispositivo(
                urn=t.urn,
                obra=chave,
                especie=t.especie,
                rotulo=t.rotulo,
                texto=t.texto,
                texto_indexado=_texto_indexado(t.rotulo, t.texto, caput),
                pai=t.pai,
                ordem=t.ordem,
                vigencia_inicio=inicio.isoformat(),
                vigencia_fim=fim.isoformat() if fim else None,
                revogado=revogado,
                alterado_por=t.alterado_por,
            )
        )

    con = banco.conectar()
    # O vetor sobrevive a reingestao quando o texto que o gerou nao mudou. Sem
    # isto, reindexar a obra zera todos os vetores pelo cascade - e a busca passa
    # a responder so pela via lexical, sem dizer que emagreceu.
    # O denominador conta VETORES; `guardados` conta textos distintos, e os dois
    # numeros diferem - redacoes com o mesmo texto indexado compartilham vetor.
    # Relatar "de len(guardados)" daria um "5747 de 5341" sem sentido.
    tinham_vetor = int(
        con.execute(
            """SELECT COUNT(*) FROM vetores v
                 JOIN dispositivos d ON d.id = v.dispositivo_id
                WHERE d.obra = ?""",
            (chave,),
        ).fetchone()[0]
    )
    guardados = banco.vetores_guardados(con, chave)
    con.execute("DELETE FROM dispositivos WHERE obra = ?", (chave,))
    fonte_id = banco.registrar_fonte(con, chave, obra["url"], bruto)
    banco.gravar(con, registros, fonte_id)
    recolocados, sem_vetor = banco.restaurar_vetores(con, chave, guardados)
    con.commit()

    print(f"  gravados: {len(registros)} redacoes")
    if recolocados:
        print(f"  vetores preservados: {recolocados} de {tinham_vetor}")
    if sem_vetor:
        print(f"  sem vetor: {sem_vetor} redacoes - para a busca densa, rode:")
        print("    python -m app.corpus.indexar vetores")
    print(f"  estatisticas: {banco.estatisticas(con)}")
    conferir_catalogo(con, chave)
    con.close()


def indexar_tst(rebaixar: bool = False) -> None:
    """Sumulas e OJs do TST, do Livro consolidado.

    Uma passada grava as QUATRO colecoes de uma vez, porque elas vem do mesmo
    arquivo: separa-las em quatro comandos faria quatro downloads do mesmo RTF de
    23 MB e quatro registros de fonte para um sha256 so.
    """
    print("Sumulas e Orientacoes Jurisprudenciais do TST")
    bruto = planalto.baixar(tst.URL_LIVRO, tst.ARQUIVO, forcar=rebaixar)
    print(f"  fonte: {len(bruto):,} bytes")

    achados = tst.verbetes(bruto)
    if not achados:
        # Zero verbetes nao e "o Livro esta vazio": e o parser cego. Ja aconteceu
        # uma vez, quando o corte do indice remissivo casou a linha do sumario.
        raise SystemExit("  NENHUM verbete reconhecido - o parser quebrou, nao o Livro.")

    registros = [
        Dispositivo(
            urn=v.urn,
            obra=v.obra,
            especie="sumula" if v.obra == "sumula-tst" else "oj",
            rotulo=v.rotulo,
            texto=v.texto,
            # O titulo entra so no indexado, nunca no `texto`: ele e ementa da
            # publicacao, nao parte do verbete, e uma peca que o transcrevesse
            # como se fosse citaria o TST dizendo o que o TST nao disse.
            texto_indexado=f"{v.rotulo} {v.titulo} {v.texto}",
            pai=None,
            ordem=int(v.numero),
            vigencia_inicio=v.vigencia_inicio.isoformat(),
            vigencia_fim=v.vigencia_fim.isoformat() if v.vigencia_fim else None,
            revogado=v.revogado,
            alterado_por=v.cabecalho[:200] or None,
        )
        for v in achados
    ]

    por_obra: dict[str, int] = {}
    for r in registros:
        por_obra[r.obra] = por_obra.get(r.obra, 0) + 1

    con = banco.conectar()
    guardados = {}
    tinham_vetor = 0
    for obra in por_obra:
        tinham_vetor += int(
            con.execute(
                """SELECT COUNT(*) FROM vetores v
                     JOIN dispositivos d ON d.id = v.dispositivo_id
                    WHERE d.obra = ?""",
                (obra,),
            ).fetchone()[0]
        )
        guardados |= banco.vetores_guardados(con, obra)
        con.execute("DELETE FROM dispositivos WHERE obra = ?", (obra,))

    fonte_id = banco.registrar_fonte(con, "tst", tst.URL_LIVRO, bruto)
    banco.gravar(con, registros, fonte_id)

    recolocados = sem_vetor = 0
    for obra in por_obra:
        a, b = banco.restaurar_vetores(con, obra, guardados)
        recolocados += a
        sem_vetor += b
    con.commit()

    for obra, n in sorted(por_obra.items()):
        vig = sum(1 for r in registros if r.obra == obra and not r.vigencia_fim and not r.revogado)
        print(f"  {obra:22} {n:4} verbetes, {vig} vigentes hoje")
    print(f"  gravados: {len(registros)} verbetes")
    if recolocados:
        print(f"  vetores preservados: {recolocados} de {tinham_vetor}")
    if sem_vetor:
        print(f"  sem vetor: {sem_vetor} verbetes - para a busca densa, rode:")
        print("    python -m app.corpus.indexar vetores")

    # Lacuna nao e prova de bug: o Livro nao reimprime verbete cancelado ha
    # decadas. E sinal - colecao que perdeu metade da faixa perdeu por parsing.
    for obra, faltando in sorted(tst.lacunas(achados).items()):
        if faltando:
            amostra = ", ".join(str(n) for n in faltando[:10])
            resto = f" (+{len(faltando) - 10})" if len(faltando) > 10 else ""
            print(f"  {obra}: {len(faltando)} numeros ausentes na faixa - {amostra}{resto}")

    print(f"  estatisticas: {banco.estatisticas(con)}")
    for obra in sorted(por_obra):
        conferir_catalogo(con, obra)
    con.close()


def indexar_trt13(rebaixar: bool = False) -> None:
    """Sumulas do TRT-13, uma pagina por verbete no site do NUGEP.

    Primeira obra regional. O que ela testa, alem do parser, e o filtro por
    tribunal: depois desta ingestao um caso da Paraiba passa a ver 45 verbetes
    que um caso de Pernambuco nao ve.
    """
    print("Sumulas do TRT da 13a Regiao")
    paginas = trt13.baixar(forcar=rebaixar)
    bruto = b"".join(paginas.values())
    print(f"  fonte: {len(paginas) - 1} paginas de sumula mais o indice, {len(bruto):,} bytes")

    achados = trt13.verbetes(paginas)
    if not achados:
        raise SystemExit("  NENHUM verbete reconhecido - o parser quebrou, nao o site.")

    registros = [
        Dispositivo(
            urn=v.urn,
            obra=trt13.OBRA,
            especie="sumula",
            rotulo=v.rotulo,
            texto=v.texto,
            # Titulo so no indexado, pela mesma razao do TST: e ementa, nao verbete.
            texto_indexado=f"{v.rotulo} {v.titulo} {v.texto}",
            pai=None,
            ordem=v.numero,
            vigencia_inicio=v.vigencia_inicio.isoformat(),
            vigencia_fim=v.vigencia_fim.isoformat() if v.vigencia_fim else None,
            revogado=v.revogado,
            alterado_por=v.cabecalho[:200] or None,
        )
        for v in achados
    ]

    con = banco.conectar()
    tinham_vetor = int(
        con.execute(
            """SELECT COUNT(*) FROM vetores v
                 JOIN dispositivos d ON d.id = v.dispositivo_id
                WHERE d.obra = ?""",
            (trt13.OBRA,),
        ).fetchone()[0]
    )
    guardados = banco.vetores_guardados(con, trt13.OBRA)
    con.execute("DELETE FROM dispositivos WHERE obra = ?", (trt13.OBRA,))
    fonte_id = banco.registrar_fonte(con, trt13.OBRA, trt13.URL_INDICE, bruto)
    banco.gravar(con, registros, fonte_id)
    recolocados, sem_vetor = banco.restaurar_vetores(con, trt13.OBRA, guardados)
    con.commit()

    por_status: dict[str, int] = {}
    for v in achados:
        por_status[v.status] = por_status.get(v.status, 0) + 1
    vigentes = sum(1 for r in registros if not r.vigencia_fim and not r.revogado)
    print(f"  {trt13.OBRA}: {len(registros)} verbetes, {vigentes} vigentes hoje")
    print("  por status: " + ", ".join(f"{k} {n}" for k, n in sorted(por_status.items())))
    sem_data = [v.numero for v in achados if v.vigencia_inicio == trt13.PISO]
    if sem_data:
        print(f"  no piso por falta de data legivel: {sem_data}")
    if faltando := trt13.lacunas(achados):
        print(f"  numeros ausentes na faixa: {faltando}")
    if recolocados:
        print(f"  vetores preservados: {recolocados} de {tinham_vetor}")
    if sem_vetor:
        print(f"  sem vetor: {sem_vetor} verbetes - para a busca densa, rode:")
        print("    python -m app.corpus.indexar vetores")
    print(f"  estatisticas: {banco.estatisticas(con)}")
    conferir_catalogo(con, trt13.OBRA)
    con.close()


def conferir_catalogo(con, chave: str) -> None:
    """A metrica que decide: o catalogo consegue encontrar o que cita?"""
    catalogo = carregar()
    exigidos: dict[str, list[str]] = {}
    for item in list(catalogo.pedidos) + list(catalogo.armadilhas):
        origem = getattr(item, "nome", None) or item.titulo
        for f in item.fundamentos:
            r = interpretar(f.tipo, f.ref)
            if r.obra == chave:
                for urn in r.urns:
                    exigidos.setdefault(urn, []).append(origem)

    # Dois diagnosticos opostos que nao podem aparecer misturados:
    #   ausente  -> o parser perdeu o dispositivo. Bug meu, corrige-se em codigo.
    #   revogado -> o catalogo cita norma que nao existe mais. Bug juridico,
    #               corrige-se no YAML, e e informacao util para quem redige.
    hoje = date.today()
    ausentes, revogados = [], []
    # "Lei 12.506/2011" sem artigo e citacao da lei inteira: a URN e a propria
    # obra, e nao ha dispositivo com esse endereco para achar. Obra ingerida e
    # citacao atendida - a peca a cita pelo nome, sem transcrever a lei toda.
    exigidos.pop(chave, None)
    for urn in exigidos:
        if banco.vigente_em(con, urn, hoje) is not None:
            continue
        (revogados if banco.redacoes(con, urn) else ausentes).append(urn)

    total = len(exigidos)
    if not total:
        # Obra que o catalogo nao cita. Imprimir "0 de 0" so enche a saida de
        # linha sem informacao, e a ingestao do TST chama isto quatro vezes.
        return
    vivos = total - len(ausentes) - len(revogados)
    print(f"\n  {chave}: {vivos} de {total} dispositivos citados pelo catalogo vigentes hoje")

    if ausentes:
        print("  AUSENTES DO CORPUS (falha de ingestao):")
        for urn in sorted(ausentes):
            print(f"    {urn}  <- {', '.join(sorted(set(exigidos[urn])))}")

    if revogados:
        print("  NO CORPUS, MAS NAO VIGENTES (o catalogo cita norma revogada):")
        for urn in sorted(revogados):
            ultima = banco.redacoes(con, urn)[-1]
            quando = ultima["vigencia_fim"] or "data nao legivel na fonte"
            por = ultima["alterado_por"] or "?"
            print(f"    {urn} ate {quando} ({por})  <- {', '.join(sorted(set(exigidos[urn])))}")


def indexar_vetores() -> None:
    """Via 2: calcula o vetor denso de cada redacao. Retomavel.

    So processa o que ainda nao tem vetor, entao interromper e rodar de novo
    continua de onde parou - o que importa numa etapa de ~25 minutos.
    """
    from app.corpus import vetores

    con = banco.conectar()
    try:
        inicio = time.time()
        feitos = vetores.indexar(con)
        # Em que hardware isto correu. A diferenca entre CPU e GPU aqui e de 41
        # minutos para 2, entao vale dizer em voz alta qual dos dois foi.
        if vetores.PROVEDOR:
            print(f"  provider: {vetores.PROVEDOR}")
        if feitos:
            print(f"  {feitos} vetores em {(time.time() - inicio) / 60:.1f} min")
        else:
            print("  nada pendente: todos os dispositivos ja tem vetor")
        print(f"  estatisticas: {banco.estatisticas(con)}")
    except vetores.ModeloAusente as erro:
        print(f"  {erro}")
        raise SystemExit(1) from erro
    finally:
        con.close()


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    rebaixar = "--rebaixar" in sys.argv

    if "tst" in args:
        indexar_tst(rebaixar)
        args = [a for a in args if a != "tst"]
        if not args:
            return

    if "trt13" in args:
        indexar_trt13(rebaixar)
        args = [a for a in args if a != "trt13"]
        if not args:
            return

    if "vetores" in args:
        print("Vetores densos (BGE-M3)")
        indexar_vetores()
        args = [a for a in args if a != "vetores"]
        if not args:
            return

    for chave in args or list(OBRAS):
        if chave not in OBRAS:
            print(f"obra desconhecida: {chave}. Disponiveis: {', '.join(OBRAS)}, tst, trt13, vetores")
            raise SystemExit(1)
        indexar(chave, rebaixar)


if __name__ == "__main__":
    main()
