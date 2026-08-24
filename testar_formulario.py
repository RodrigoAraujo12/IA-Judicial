"""Conversao dos campos do formulario para o dicionario do motor.

    python testar_formulario.py

O caso que motivou este arquivo: `_moeda("3.500")` devolvia 3.5. Sem virgula nao
ha decimal para desempatar o ponto, e a leitura antiga o tomava por separador
decimal - R$ 3.500 virava R$ 3,50 e ia para casos.db assim, sem erro nenhum na
tela. Numero errado que nao reclama e a falha que este projeto mais teme, entao
ela ganhou teste proprio.

O segundo bloco cuida do que importa tanto quanto: campo em branco tem de ficar
AUSENTE do dicionario, nunca virar zero ou False. E o que alimenta o terceiro
estado do motor.
"""

from starlette.datastructures import FormData

from app.main import _moeda, parse_respostas

falhas = []


def conferir(rotulo: str, obtido, esperado) -> None:
    ok = obtido == esperado
    if not ok:
        falhas.append(f"{rotulo}: esperado {esperado!r}, obtido {obtido!r}")
    print(f"  {'ok ' if ok else 'ERRO'}  {rotulo:24} -> {obtido!r}")


print("moeda: separador de milhar sem centavos")
for bruto, esperado in [
    ("3.500", 3500.0),
    ("1.200", 1200.0),
    ("10.000", 10000.0),
    ("1.234.567", 1234567.0),
    ("R$ 2.000", 2000.0),
]:
    conferir(repr(bruto), _moeda(bruto), esperado)

print("\nmoeda: formas que ja funcionavam, e que nao podem regredir")
for bruto, esperado in [
    ("3.500,00", 3500.0),
    ("3500.00", 3500.0),
    ("1500,50", 1500.5),
    ("2000", 2000.0),
    ("R$ 1.234,56", 1234.56),
]:
    conferir(repr(bruto), _moeda(bruto), esperado)

print("\nmoeda: decimal de verdade continua decimal")
for bruto, esperado in [
    ("3.5", 3.5),
    ("0.75", 0.75),
    ("3.50", 3.5),
]:
    conferir(repr(bruto), _moeda(bruto), esperado)

print("\nmoeda: o que nao da para ler vira None, nao zero")
for bruto in ["", "   ", "R$", "abc", "1.2.3", "3.500.00"]:
    conferir(repr(bruto), _moeda(bruto), None)

print("\nformulario: em branco fica AUSENTE (terceiro estado)")
form = FormData(
    [
        ("salario_base", "3.500"),
        ("funcao", "  Auxiliar de producao  "),
        ("data_admissao", ""),
        ("registro_ctps", "sim"),
        ("empresa_mais_20_empregados", ""),
        ("horas_extras_pagas", "nao"),
        ("justa_causa_demora", "45"),
        ("agente_nocivo", "ruido"),
        ("agente_nocivo", "calor"),
    ]
)
r = parse_respostas(form)
conferir("salario_base", r.get("salario_base"), 3500.0)
conferir("funcao aparada", r.get("funcao"), "Auxiliar de producao")
conferir("registro_ctps", r.get("registro_ctps"), True)
conferir("horas_extras_pagas", r.get("horas_extras_pagas"), False)
conferir("justa_causa_demora int", r.get("justa_causa_demora"), 45)
conferir("agente_nocivo", r.get("agente_nocivo"), ["ruido", "calor"])
conferir("data_admissao ausente", "data_admissao" in r, False)
conferir("empresa_20 ausente", "empresa_mais_20_empregados" in r, False)

if falhas:
    print(f"\n{len(falhas)} FALHA(S):")
    for f in falhas:
        print(f"  - {f}")
    raise SystemExit(1)
print("\ntudo certo")
