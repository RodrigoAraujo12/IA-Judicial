"""Vetor sobrevive a reingestao da obra - e nao troca de dono.

    python testar_vetores_preservados.py

Reingerir uma obra e `DELETE FROM dispositivos` seguido de INSERT. Como a tabela
`vetores` referencia dispositivos com ON DELETE CASCADE, o DELETE levava junto os
5.752 vetores da CLT. Aconteceu de verdade em 18/08: a vetorizacao terminou as
20:25 e uma reingestao as 23:25 zerou tudo. Ninguem percebeu porque a busca
degrada para lexical em silencio - `if not den: return Resultado(lex, "lexical")`.

O conserto guarda os vetores antes do DELETE e recoloca depois. A parte delicada
e a CHAVE de recolocacao. Por urn seria errado: `clt/art-71/par-4` tem uma
redacao de 2016 e outra de 2017, e um vetor colado por urn cairia na irma errada
- servindo o sentido do texto velho como se fosse o novo, sem erro visivel.

A chave e o sha256 de `texto_indexado`. Este teste tranca as duas pontas: o que
nao mudou mantem o SEU vetor, byte a byte, e o que mudou fica sem vetor em vez de
ficar com um vetor plausivel.
"""

import shutil
import tempfile
from pathlib import Path

from app.corpus import banco
from app.corpus.banco import Dispositivo

falhas = []


def conferir(rotulo: str, obtido, esperado) -> None:
    ok = obtido == esperado
    print(f"  {'ok ' if ok else 'ERRO'} {rotulo}")
    if not ok:
        falhas.append(f"{rotulo}: esperado {esperado!r}, obtido {obtido!r}")


def disp(urn: str, ordem: int, inicio: str, texto: str) -> Dispositivo:
    return Dispositivo(
        urn=urn,
        obra="clt",
        especie="artigo",
        rotulo=urn,
        texto=texto,
        texto_indexado=texto,
        pai=None,
        ordem=ordem,
        vigencia_inicio=inicio,
    )


def vetores_por_urn(con) -> dict[str, bytes]:
    linhas = con.execute(
        """SELECT d.urn, d.vigencia_inicio, v.denso
             FROM dispositivos d LEFT JOIN vetores v ON v.dispositivo_id = d.id"""
    )
    return {f"{l['urn']}@{l['vigencia_inicio']}": l["denso"] for l in linhas}


temp = Path(tempfile.mkdtemp())
try:
    con = banco.conectar(temp / "corpus.db")

    # --- primeira ingestao ---------------------------------------------------
    #
    # As duas redacoes do art. 71 par. 4o sao o coracao do teste: mesma urn,
    # textos diferentes, vetores diferentes.
    primeira = [
        disp("clt/art-1", 1, "2000-01-01", "alfa"),
        disp("clt/art-71/par-4", 10, "2016-01-01", "intervalo, redacao velha"),
        disp("clt/art-71/par-4", 11, "2017-11-11", "intervalo, redacao nova"),
        disp("clt/art-9", 2, "2000-01-01", "texto que vai mudar"),
        disp("clt/art-99", 3, "2000-01-01", "dispositivo que vai sumir"),
    ]
    fonte = banco.registrar_fonte(con, "clt", "http://exemplo/1", b"fonte-1")
    banco.gravar(con, primeira, fonte)

    # Vetor de mentira, um byte distinto por dispositivo: o teste compara
    # identidade, nao similaridade.
    for i, linha in enumerate(con.execute("SELECT id FROM dispositivos ORDER BY id").fetchall()):
        con.execute(
            "INSERT INTO vetores (dispositivo_id, modelo, dim, denso) VALUES (?, ?, ?, ?)",
            (linha["id"], "bge-m3", 4, bytes([i + 1]) * 16),
        )
    con.commit()
    antes = vetores_por_urn(con)
    conferir("cinco vetores gravados", con.execute("SELECT COUNT(*) FROM vetores").fetchone()[0], 5)

    # --- reingestao ----------------------------------------------------------
    #
    # art. 1 e as duas redacoes do 71 seguem iguais; o art. 9 mudou de texto; o
    # art. 99 sumiu da fonte; o art. 100 e novo.
    print("\nreingestao da obra")
    segunda = [
        disp("clt/art-1", 1, "2000-01-01", "alfa"),
        disp("clt/art-71/par-4", 10, "2016-01-01", "intervalo, redacao velha"),
        disp("clt/art-71/par-4", 11, "2017-11-11", "intervalo, redacao nova"),
        disp("clt/art-9", 2, "2000-01-01", "texto DEPOIS de mudar"),
        disp("clt/art-100", 4, "2000-01-01", "dispositivo novo"),
    ]
    guardados = banco.vetores_guardados(con, "clt")
    conferir("vetores guardados antes do DELETE", len(guardados), 5)

    con.execute("DELETE FROM dispositivos WHERE obra = ?", ("clt",))
    conferir("o cascade zerou a tabela", con.execute("SELECT COUNT(*) FROM vetores").fetchone()[0], 0)

    fonte = banco.registrar_fonte(con, "clt", "http://exemplo/2", b"fonte-2")
    banco.gravar(con, segunda, fonte)
    recolocados, sem_vetor = banco.restaurar_vetores(con, "clt", guardados)
    con.commit()

    conferir("recolocados", recolocados, 3)
    conferir("redacoes sem vetor", sem_vetor, 2)

    # --- o vetor certo no dispositivo certo ----------------------------------
    print("\ncada redacao ficou com o SEU vetor")
    depois = vetores_por_urn(con)
    for chave in ["clt/art-1@2000-01-01",
                  "clt/art-71/par-4@2016-01-01",
                  "clt/art-71/par-4@2017-11-11"]:
        conferir(f"{chave} manteve o vetor, byte a byte", depois[chave], antes[chave])

    conferir(
        "as duas redacoes do art. 71 nao trocaram de vetor",
        depois["clt/art-71/par-4@2016-01-01"] != depois["clt/art-71/par-4@2017-11-11"],
        True,
    )

    print("\ntexto novo nao herda vetor velho")
    conferir("art. 9, texto alterado, ficou SEM vetor", depois["clt/art-9@2000-01-01"], None)
    conferir("art. 100, dispositivo novo, ficou SEM vetor", depois["clt/art-100@2000-01-01"], None)
    conferir("art. 99 sumiu junto com a fonte", "clt/art-99@2000-01-01" in depois, False)

    con.close()
finally:
    shutil.rmtree(temp, ignore_errors=True)

if falhas:
    print("\nFALHOU")
    for f in falhas:
        print("  " + f)
    raise SystemExit(1)
print("\nvetores preservados ok")
