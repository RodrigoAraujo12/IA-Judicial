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

**10 pedidos cabíveis, 1 a investigar.** O que conferir:

- **Insalubridade e periculosidade aparecem os dois** — e os dois trazem o alerta
  de que não se acumulam (art. 193 §2º), com a instrução de pedir em caráter
  alternativo/sucessivo pelo mais benéfico. O sistema não escolhe por você:
  escolher exige a perícia, que ainda não aconteceu.
- **O corte quinquenal recua a 18/08/2021.** Contrato de 03/2019 a 04/2026 — os
  dois primeiros anos e meio estão prescritos. O painel diz isso na cara.
- **Ponto britânico virou tese.** A resposta acionou o alerta da Súmula 338, e a
  armadilha "requerer a juntada dos controles de jornada" está na lista.
- **A lista de documentos a solicitar** sai montada no fim do relatório, sem
  repetição, a partir de todos os pedidos em jogo. É o que quem usa o sistema
  descreveu como o objetivo da triagem: ver se tem tudo que precisa antes de
  seguir com o pedido da pessoa.
- **É o único dos três pronto para redigir.** No fim do relatório, o bloco
  *Material para a inicial* traz a qualificação das partes e a história dos
  fatos, e **não** exibe o aviso de pendência — porque não há nenhuma. Compare
  com a Regina, logo abaixo.
- **A jornada real aparece narrada, não só marcada.** O campo só foi pedido
  depois que a triagem confirmou horas extras: detalhe de fato se pergunta
  quando o pedido já existe, não antes.

---

## 2. Regina — pejotização, com lacunas de propósito

> *"Fui contratada como consultora de vendas, mas tive que abrir CNPJ. Emitia
> nota todo mês, R$ 3.200. Tinha meta, horário, participava de reunião de equipe,
> usava e-mail da empresa. Trabalhava muito além do horário. Em fevereiro
> simplesmente pararam de me chamar, não pagaram nada, não teve rescisão."*

Metade das perguntas ficou em branco de propósito: **15 de 56 respondidas**.

**Confira:**

- **13 pedidos em "a investigar"** — e cada um dizendo *exatamente qual pergunta
  falta*. É esse o coração do sistema: sem o terceiro estado, esses 13 pedidos
  seriam descartados em silêncio porque a pergunta ainda não foi feita.
- Vá respondendo e veja os pedidos migrarem para "cabíveis". São 5 hoje.
- O vínculo em si (arts. 2º e 3º da CLT) já está confirmado pelas respostas de
  subordinação — o que falta é o entorno.
- **O bloco *Material para a inicial* abre com o aviso de pendência** e lista
  14 campos: qualificação inteira e nenhuma linha de narrativa. Com pedidos e
  sem história, a peça sairia genérica — que é o que o próprio catálogo aponta
  como principal causa de improcedência no dano moral.

---

## 3. João — processo já ajuizado em 2019

> *"Fui operador de empilhadeira de 2015 a 2019 em Guarulhos. Ponto britânico,
> intervalo cortado quase sempre. A ação foi ajuizada em outubro de 2019."*

Este é o único que mostra a **cisão pela Reforma** — e a razão é instrutiva.

**Confira:**

- **A prescrição conta da data do ajuizamento (15/10/2019), não de hoje.** Por
  isso o corte quinquenal recua a 15/10/2014 e o período anterior a 11/11/2017
  sobrevive. Apague o campo *Data do ajuizamento* e veja o caso virar
  integralmente prescrito.
- **O intervalo intrajornada vem marcado "cindir por período"**, com as duas
  regras impressas lado a lado no relatório:
  - até 10/11/2017 → 1 hora **integral** × 1,5, natureza salarial, **com
    reflexos** (Súmula 437);
  - a partir de 11/11/2017 → só os minutos **suprimidos** × 1,5, natureza
    indenizatória, **sem reflexo nenhum**.
  - Formular num pedido só uniria duas naturezas jurídicas distintas.
- É o único dos três com `atravessa_reforma`, e o único com pedido cindido.

---

## Uma observação que vale para a prática

Nos casos 1 e 2, ajuizados hoje, a Reforma **não** cinde nada — porque o corte
quinquenal (agosto de 2021) já é posterior a 11/11/2017. Na prática, para ação
nova em 2026, o regime pré-Reforma virou irrelevante.

A cisão só importa em **processos já ajuizados** — os antigos da carteira, em
fase recursal ou de execução. Que é justamente o cenário do consultor de processo
parado, ainda por fazer.

---

## Limites que você vai notar

O sistema **não apura valores**. A indicação exigida pelo art. 840 §1º vem do
contador ou do calculista. A triagem responde *se* o pedido cabe e *o que falta
provar*; quanto vale é outra conta, e de outra pessoa.

As referências marcadas "conferir no índice" são **teses em disputa**, não
citações duvidosas: o relatório destaca em vez de afirmar. Desde que o corpus
entrou, dá para checar o texto em `/corpus`, com a data do contrato — mas só da
CLT, que é o que está ingerido. Súmulas, OJs, NRs e Constituição ainda não.

E o sistema **ainda não escreve a peça**. Ele já coleta os quatro blocos que ela
exige — qualificação, fatos, fundamentação, pedido — e mostra o que falta em
cada um. Juntá-los num texto é o próximo passo.
