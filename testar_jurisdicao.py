"""Competencia territorial e o filtro de obras por tribunal.

    python testar_jurisdicao.py

Duas coisas que este teste tranca.

**O TRT e derivado, nunca escolhido.** A UF da prestacao decide o tribunal; Sao
Paulo precisa de uma segunda resposta; sem UF o resultado e None - o terceiro
estado, e nao o tribunal da advogada por padrao.

**Sumula de outro tribunal nao entra no caso.** Num corpus de fixture com CLT,
uma sumula da 13a Regiao e uma da 6a, a busca de um caso da Paraiba ve a CLT e a
sua sumula, e so. Sem filtro ve tudo, que e o comportamento anterior e o que o
controle em `testar_vias.py` compara contra o corpus real.
"""

import sys
import tempfile
from datetime import date
from pathlib import Path

from app import jurisdicao
from app.corpus import banco, busca
from app.corpus.banco import Dispositivo
from app.motor import analisar
from app.catalogo.loader import carregar

sys.stdout.reconfigure(encoding="utf-8")
falhas: list[str] = []


def conferir(rotulo: str, obtido, esperado) -> None:
    ok = obtido == esperado
    print(f"  {'ok  ' if ok else 'ERRO'} {rotulo}")
    if not ok:
        falhas.append(f"{rotulo}: esperado {esperado!r}, obtido {obtido!r}")


# --- 1. de UF a TRT ---------------------------------------------------------

print("de UF a TRT")

conferir("Paraiba e a 13a Regiao", jurisdicao.trt_do_caso({"uf_prestacao": "PB"}), 13)
conferir("Pernambuco e a 6a", jurisdicao.trt_do_caso({"uf_prestacao": "PE"}), 6)
conferir("Amapa divide a 8a com o Para", jurisdicao.trt_do_caso({"uf_prestacao": "AP"}), 8)
conferir("minusculas nao atrapalham", jurisdicao.trt_do_caso({"uf_prestacao": "pb"}), 13)
conferir("sem UF nao ha tribunal", jurisdicao.trt_do_caso({}), None)
conferir("UF desconhecida nao vira tribunal", jurisdicao.trt_do_caso({"uf_prestacao": "XX"}), None)

conferir("SP metropolitana e a 2a",
         jurisdicao.trt_do_caso({"uf_prestacao": "SP", "regiao_sp": "metropolitana"}), 2)
conferir("SP interior e a 15a",
         jurisdicao.trt_do_caso({"uf_prestacao": "SP", "regiao_sp": "interior"}), 15)
conferir("SP sem a segunda resposta fica indefinido",
         jurisdicao.trt_do_caso({"uf_prestacao": "SP"}), None)

conferir("todas as 27 UFs resolvem", len(jurisdicao.UFS), 27)
for uf in jurisdicao.UFS:
    r = {"uf_prestacao": uf, "regiao_sp": "interior"}
    if jurisdicao.trt_do_caso(r) is None:
        falhas.append(f"UF {uf} sem tribunal")
conferir("os 24 tribunais tem rotulo", sorted(jurisdicao.ABRANGENCIA), list(range(1, 25)))
conferir("rotulo diz quem o tribunal cobre", jurisdicao.rotulo(8), "TRT da 8ª Região (PA e AP)")
conferir("rotulo de None e None", jurisdicao.rotulo(None), None)

# O catalogo tem as duas perguntas e a segunda so aparece em SP.
catalogo = carregar()
ids = {p.id for p in catalogo.entrevista.perguntas}
conferir("a entrevista pergunta a UF", "uf_prestacao" in ids, True)
conferir("e a regiao de SP", "regiao_sp" in ids, True)
opcoes = {o.valor for p in catalogo.entrevista.perguntas if p.id == "uf_prestacao" for o in p.opcoes}
conferir("as opcoes da UF sao as do mapa", opcoes, set(jurisdicao.UFS))

pb = analisar(catalogo, {"uf_prestacao": "PB"})
conferir("o motor carrega o TRT na analise", pb.trt, 13)
conferir("a regiao de SP nao aparece para a Paraiba", "regiao_sp" in pb.visiveis, False)
sp = analisar(catalogo, {"uf_prestacao": "SP"})
conferir("e aparece para Sao Paulo", "regiao_sp" in sp.visiveis, True)
conferir("Sao Paulo sem regiao fica sem tribunal", sp.trt, None)


# --- 2. obras nacionais e regionais ------------------------------------------

print("\nobras por tribunal")

conferir("clt e nacional", jurisdicao.trt_da_obra("clt"), None)
conferir("sumula-tst e nacional", jurisdicao.trt_da_obra("sumula-tst"), None)
conferir("sumula-trt13 e da 13a", jurisdicao.trt_da_obra("sumula-trt13"), 13)
conferir("oj-trt2 e da 2a", jurisdicao.trt_da_obra("oj-trt2"), 2)

TODAS = ["clt", "sumula-tst", "oj-sdi1-tst", "sumula-trt13", "sumula-trt6", "tese-trt6"]
conferir("caso da Paraiba ve nacionais e a 13a",
         jurisdicao.obras_para(TODAS, 13), {"clt", "sumula-tst", "oj-sdi1-tst", "sumula-trt13"})
conferir("sem tribunal ve so nacionais",
         jurisdicao.obras_para(TODAS, None), {"clt", "sumula-tst", "oj-sdi1-tst"})
conferir("tribunais presentes no corpus", jurisdicao.trts_no_corpus(TODAS), [6, 13])


# --- 3. o filtro chega a busca ----------------------------------------------

print("\nfiltro na busca lexical")

CAMINHO = Path(tempfile.gettempdir()) / "corpus_jurisdicao.db"
CAMINHO.unlink(missing_ok=True)
con = banco.conectar(CAMINHO)

TEXTO = "adicional de periculosidade base de calculo salario"
registros = []
for obra, urn, rotulo in [
    ("clt", "clt/art-193", "CLT, art. 193"),
    ("sumula-trt13", "sumula-trt13/7", "Sumula 7 do TRT-13"),
    ("sumula-trt6", "sumula-trt6/9", "Sumula 9 do TRT-6"),
]:
    fonte = banco.registrar_fonte(con, obra, f"https://exemplo/{obra}", obra.encode())
    banco.gravar(con, [Dispositivo(
        urn=urn, obra=obra, especie="artigo", rotulo=rotulo, texto=TEXTO,
        texto_indexado=f"{rotulo} {TEXTO}", pai=None, ordem=1,
        vigencia_inicio="2000-01-01", vigencia_fim=None,
    )], fonte)

hoje = date(2026, 9, 17)
todas = banco.obras(con)
conferir("o fixture tem as tres obras", todas, ["clt", "sumula-trt13", "sumula-trt6"])


def obras_de(achados) -> set[str]:
    return {a.obra for a in achados}


sem_filtro = busca.lexical(con, "periculosidade", hoje, 10)
conferir("sem filtro, a busca ve tudo", obras_de(sem_filtro), {"clt", "sumula-trt13", "sumula-trt6"})

paraiba = busca.lexical(con, "periculosidade", hoje, 10, jurisdicao.obras_para(todas, 13))
conferir("caso da Paraiba nao ve a sumula da 6a", obras_de(paraiba), {"clt", "sumula-trt13"})

pernambuco = busca.lexical(con, "periculosidade", hoje, 10, jurisdicao.obras_para(todas, 6))
conferir("caso de Pernambuco nao ve a da 13a", obras_de(pernambuco), {"clt", "sumula-trt6"})

nacional = busca.lexical(con, "periculosidade", hoje, 10, jurisdicao.obras_para(todas, None))
conferir("sem tribunal, so a CLT", obras_de(nacional), {"clt"})

vazio = busca.lexical(con, "periculosidade", hoje, 10, set())
conferir("conjunto vazio nao vira 'todas'", vazio, [])

# A via densa usa a mesma mascara. Sem o modelo nao se roda a via inteira, mas a
# mascara e testavel sozinha - e e ela que decide o que a densa pode devolver.
ids_pb = banco.ids_vigentes(con, hoje, jurisdicao.obras_para(todas, 13))
ids_tudo = banco.ids_vigentes(con, hoje)
conferir("a mascara da densa sem filtro cobre as tres redacoes", len(ids_tudo), 3)
conferir("e com filtro da Paraiba, duas", len(ids_pb), 2)
obras_pb = {r[0] for r in con.execute(
    f"SELECT obra FROM dispositivos WHERE id IN ({','.join('?' * len(ids_pb))})", sorted(ids_pb))}
conferir("as duas certas", obras_pb, {"clt", "sumula-trt13"})

# O ponto de entrada repassa o filtro para as vias de busca...
r = busca.buscar(con, "periculosidade", hoje, 10, jurisdicao.obras_para(todas, 13))
conferir("buscar() respeita o filtro", obras_de(r.achados), {"clt", "sumula-trt13"})
# ...e NAO para a via de referencia: pedir um artigo pelo numero e pedir aquele texto.
r = busca.buscar(con, "art. 193", hoje, 10, set())
conferir("a via de referencia ignora o filtro", [a.urn for a in r.achados], ["clt/art-193"])

con.close()
CAMINHO.unlink(missing_ok=True)

if falhas:
    print("\nFALHOU")
    for f in falhas:
        print("  " + f)
    raise SystemExit(1)
print("\njurisdicao ok")
