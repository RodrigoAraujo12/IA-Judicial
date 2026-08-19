"""Os dois blocos que faltavam para a peticao inicial existir.

    python testar_inicial.py

A estrutura da inicial veio de quem escreve peca: qualificacao das partes,
historia dos fatos, fundamentacao e pedido. Fundamentacao e pedido o sistema ja
produzia; os dois primeiros nao eram sequer perguntados.

O que se afere aqui:

  1. a qualificacao NAO mexe na triagem. Se mexer, um CPF digitado muda quais
     pedidos cabem - e ninguem repara ate perder a verba;
  2. o detalhe de fato so e pedido DEPOIS que o pedido correspondente se
     confirma, e nunca antes;
  3. a narrativa atravessa inteira: campo -> parse -> banco -> relatorio, com as
     quebras de linha preservadas. A advogada separa episodios por linha, e
     juntar tudo num paragrafo apaga a separacao.
"""

import sys

from fastapi.testclient import TestClient

from app.catalogo.loader import carregar
from app.main import app, parse_respostas
from app.motor import analisar
from starlette.datastructures import FormData

sys.stdout.reconfigure(encoding="utf-8")

catalogo = carregar()
cliente = TestClient(app)
falhas: list[str] = []


def conferir(rotulo: str, obtido, esperado) -> None:
    ok = obtido == esperado
    print(f"  {'ok  ' if ok else 'ERRO'} {rotulo}")
    if not ok:
        falhas.append(f"{rotulo}: esperado {esperado!r}, obtido {obtido!r}")


def visiveis(respostas: dict) -> set[str]:
    return analisar(catalogo, respostas).visiveis


def cabiveis(respostas: dict) -> set[str]:
    return {av.pedido.id for av in analisar(catalogo, respostas).cabiveis}


# Caso minimo que confirma dano moral por assedio.
CASO = {
    "data_admissao": "2021-03-01",
    "data_saida": "2023-08-10",
    "funcao": "auxiliar de producao",
    "local_prestacao": "Bayeux",
    "salario_base": 1800.0,
    "registro_ctps": True,
    "modalidade_saida": "sem_justa_causa",
    "assedio_moral": True,
    "hipossuficiente": True,
}

QUALIFICACAO = {
    "reclamante_nome": "Fulano de Tal",
    "reclamante_nacionalidade": "brasileiro",
    "reclamante_estado_civil": "uniao_estavel",
    "reclamante_cpf": "000.000.000-00",
    "reclamante_endereco": "Rua Exemplo, 123\nJoao Pessoa/PB, CEP 58000-000",
    "reclamada_razao_social": "Empresa Exemplo Ltda.",
    "reclamada_cnpj": "00.000.000/0001-00",
    "reclamada_endereco": "Av. Exemplo, 1000, Joao Pessoa/PB",
}

NARRATIVA = (
    "15/03/2022, no refeitorio: o supervisor gritou diante de dez colegas.\n"
    "02/05/2022, na expedicao: repetiu a cobranca em voz alta.\n"
    "Presenciaram Maria e Pedro nas duas ocasioes."
)

print("qualificacao nao interfere na triagem")
sem = cabiveis(CASO)
com = cabiveis({**CASO, **QUALIFICACAO})
conferir("os mesmos pedidos com e sem qualificacao", com, sem)
conferir("dano moral entre eles", "dano_moral" in sem, True)

print("\ndetalhe de fato so aparece depois do pedido")
vazio = visiveis({})
conferir("narrativa livre aparece desde o inicio", "narrativa_fatos" in vazio, True)
conferir("detalhe do assedio nao aparece sem caso", "fatos_assedio" in vazio, False)
conferir("detalhe do acidente nao aparece sem caso", "fatos_acidente" in vazio, False)
conferir("qualificacao aparece desde o inicio", "reclamante_cpf" in vazio, True)

com_assedio = visiveis(CASO)
conferir("com dano moral confirmado, o detalhe aparece", "fatos_assedio" in com_assedio, True)
conferir("mas o do acidente continua fora", "fatos_acidente" in com_assedio, False)

# A regra do loader e estrutural, mas so falha na carga. Aqui ela vira medida:
# nenhuma resposta de fato pode ser condicao de pedido, senao a triagem passaria
# a depender de um campo que ela mesma libera.
pos_triagem = {p.id for p in catalogo.entrevista.perguntas if p.mostrar_se_pedido}
usados_em_quando = {
    c.campo for p in catalogo.pedidos for grupo in p.quando for c in grupo
}
conferir("nenhum campo pos-triagem alimenta `quando`", pos_triagem & usados_em_quando, set())
conferir("o mecanismo pos-triagem esta de fato em uso", len(pos_triagem) > 0, True)

print("\na narrativa atravessa o formulario inteira")
form = FormData([(k, str(v)) for k, v in QUALIFICACAO.items()] + [("narrativa_fatos", NARRATIVA)])
lidas = parse_respostas(form)
conferir("quebras de linha preservadas", lidas["narrativa_fatos"].count("\n"), 2)
conferir("endereco multilinha preservado", "\n" in lidas["reclamante_endereco"], True)
conferir("CPF chega inteiro", lidas["reclamante_cpf"], "000.000.000-00")

print("\nentrevista renderiza os campos novos")
html = cliente.get("/").text
conferir("textarea da narrativa presente", 'id="c-narrativa_fatos"' in html, True)
conferir("campo de CPF presente", 'name="reclamante_cpf"' in html, True)
conferir("secao da historia dos fatos no roteiro", 'href="#s-fatos"' in html, True)
conferir("secao da qualificacao no roteiro", 'href="#s-qualificacao"' in html, True)
conferir("detalhe do assedio vem oculto", 'data-id="fatos_assedio"' in html, True)

print("\nrelatorio mostra o material da inicial")
envio = {k: ("sim" if v is True else "nao" if v is False else str(v))
         for k, v in {**CASO, **QUALIFICACAO}.items()}
envio["narrativa_fatos"] = NARRATIVA
envio["fatos_assedio"] = NARRATIVA
rel = cliente.post("/relatorio", data=envio).text

conferir("as partes aparecem no cabecalho", "Empresa Exemplo Ltda." in rel, True)
conferir("estado civil sai por extenso, nao pelo codigo", "Em uniao estavel" in rel, True)
conferir("a narrativa sai no relatorio", "02/05/2022, na expedicao" in rel, True)
conferir("preservada em bloco de quebra de linha", 'class="narrativa"' in rel, True)

# O aviso do que falta e o ponto: um relatorio que cala sobre o campo vazio deixa
# a peca sair sem endereco de citacao, e o processo para na citacao frustrada.
conferir("aponta o que ainda falta", "ainda n&atilde;o tem o que precisa" in rel, True)
conferir("PIS em branco e cobrado", "PIS/PASEP" in rel, True)
# Em branco que E resposta nao pode virar cobranca eterna: nao ha outra empresa
# no polo passivo, e o relatorio nao deve insistir para sempre nisso.
conferir("polo passivo adicional vazio nao e cobrado",
         "Outras pessoas a incluir" in rel, False)
conferir("CPF preenchido nao e cobrado como falta",
         rel.count("reclamante_cpf"), 0)

completo = {**envio}
for p in catalogo.entrevista.perguntas:
    if p.secao in ("qualificacao", "fatos") and p.id not in completo and not p.vazio_e_resposta:
        completo[p.id] = "preenchido"
rel2 = cliente.post("/relatorio", data=completo).text
conferir("com tudo preenchido, o aviso some", "ainda n&atilde;o tem o que precisa" in rel2, False)

print()
if falhas:
    print("FALHOU")
    for f in falhas:
        print("  " + f)
    raise SystemExit(1)
print("qualificacao e historia dos fatos ok")
