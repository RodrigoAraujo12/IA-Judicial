# Casos de exemplo

Três casos fictícios para conferir o sistema funcionando. Cada um exercita uma
parte diferente do motor.

```
python semear.py
uvicorn app.main:app --reload
```

Depois abra <http://127.0.0.1:8000/casos> e clique em cada um. Você pode alterar
qualquer resposta e ver o painel da direita recalcular na hora.

**O que interessa não é o sistema rodar — é você julgar se o resultado está
certo.** Abaixo vai o relato de cada cliente e o que conferir.

---

## 1. Márcio — o caso completo

> *"Trabalhei sete anos como auxiliar de produção numa fábrica em Contagem,
> registrado, ganhando R$ 2.400. A gente batia ponto, mas o horário era sempre o
> mesmo no cartão — entrava 7h e saía 17h, todo dia igual, mesmo quando eu ficava
> até 20h. Almoço eram uns 30 minutos, quando dava. Fazia turno da noite umas
> vezes por semana. O barulho no setor era muito alto e a gente mexia com
> solvente inflamável; davam protetor auricular mas ninguém conferia se usava nem
> trocava. Me mandaram embora em abril, pagaram uma parte só, fora do prazo, e
> não me deram as guias do seguro-desemprego."*

**Confira:**

- **Periculosidade venceu a insalubridade.** Ambos são cabíveis, mas não acumulam
  (art. 193 §2º). O sistema calculou os dois, manteve o mais benéfico e marcou o
  outro como *alternativo, fora do total* — que é como se pede na inicial.
- **A cascata funcionou.** A remuneração base subiu de R$ 2.400 para R$ 3.296,33
  (periculosidade + adicional noturno). Confira na memória de cálculo das horas
  extras: elas incidem sobre a base majorada, não sobre o salário nominal
  (Súmula 264). Esse é o erro que mais custa dinheiro numa planilha comum.
- **O corte quinquenal cortou de verdade.** Contrato de 03/2019 a 04/2026, mas a
  apuração começa em 18/08/2021. Os dois primeiros anos e meio não entraram na
  conta — não é só um aviso na tela.
- **Ponto britânico virou tese.** A resposta acionou o alerta da Súmula 338, e a
  armadilha "requerer a juntada dos controles de jornada" está na lista.
- **Total: R$ 210.825,86.** Compare com o que você estimaria no olho.

---

## 2. Regina — pejotização, com lacunas de propósito

> *"Fui contratada como consultora de vendas, mas tive que abrir CNPJ. Emitia
> nota todo mês, R$ 3.200. Tinha meta, horário, participava de reunião de equipe,
> usava e-mail da empresa. Trabalhava muito além do horário. Em fevereiro
> simplesmente pararam de me chamar, não pagaram nada, não teve rescisão."*

Metade das perguntas ficou em branco de propósito.

**Confira:**

- **13 pedidos em "a investigar"** — e cada um dizendo *exatamente qual pergunta
  falta*. É esse o coração do sistema: sem o terceiro estado, esses 13 pedidos
  seriam descartados em silêncio porque a pergunta ainda não foi feita.
- Vá respondendo e veja os pedidos migrarem para "cabíveis".
- **A multa do art. 467 aparece sem valor**, com a nota de que falta quantificar
  as verbas incontroversas. Preencha e veja o total mudar.
- A seção **Quantificação** vai abrindo conforme os pedidos se confirmam — ela
  começa fechada e só mostra o que é necessário.

---

## 3. João — processo já ajuizado em 2019

> *"Fui operador de empilhadeira de 2015 a 2019 em Guarulhos. Ponto britânico,
> intervalo cortado quase sempre. A ação foi ajuizada em outubro de 2019."*

Este é o único que mostra a **cisão pela Reforma** — e a razão é instrutiva.

**Confira:**

- **A prescrição conta da data do ajuizamento (15/10/2019), não de hoje.** Por
  isso o corte quinquenal recua a 2014 e o período anterior a 11/11/2017
  sobrevive. Apague o campo *Data do ajuizamento* e veja o caso virar
  integralmente prescrito.
- **Intervalo intrajornada apurado em duas parcelas** na memória de cálculo:
  - até 10/11/2017 → 1 hora **integral** × 1,5, natureza salarial, **com
    reflexos** (Súmula 437);
  - a partir de 11/11/2017 → só os 30 min **suprimidos** × 1,5, natureza
    indenizatória, **sem reflexo nenhum**.
- **Os reflexos incidem só sobre a parcela pré-Reforma.** Confira na memória: a
  base dos reflexos é menor que o principal total da verba. Um cálculo que
  unificasse os dois períodos inflaria o pedido.

---

## Uma observação que vale para a prática

Nos casos 1 e 2, ajuizados hoje, a Reforma **não** cinde nada — porque o corte
quinquenal (agosto de 2021) já é posterior a 11/11/2017. Na prática, para ação
nova em 2026, o regime pré-Reforma virou irrelevante.

A cisão só importa em **processos já ajuizados** — os antigos da carteira, em
fase recursal ou de execução. Que é justamente o cenário da fase 6.

---

## Limites que você vai notar

Os valores são **nominais**: sem correção monetária, juros, INSS ou IRRF. O
cálculo usa o último salário para todo o período, e as horas extras vêm de
estimativa do cliente — a apuração definitiva sai da tabulação dos cartões de
ponto (fase 5). Tudo isso sai impresso no relatório, para o documento nunca
aparentar mais precisão do que tem.

Os parâmetros em [`app/calculo/parametros.yaml`](app/calculo/parametros.yaml)
estão marcados `conferido: false` e **2026 está em branco de propósito** — é a
primeira coisa a preencher se você for usar o adicional de insalubridade com base
no salário mínimo.
