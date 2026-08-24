"""Monta a pagina de revisao do gabarito, para conferencia juridica.

    python revisao_gabarito.py     # le divergencias.json, escreve revisao_gabarito.html

Existe porque a ingestao das sumulas mudou o que a busca devolve, e o gabarito de
`avaliacao.py` foi escrito quando o corpus era so a CLT: em 25 das 72 consultas o
dispositivo esperado deixou de ser o primeiro. Parte disso e o buscador errando,
parte e o gabarito ter ficado estreito - e separar as duas coisas e juizo juridico,
nao ajuste de codigo.

O dicionario PARECER guarda, consulta a consulta, o que EU proponho e por que. Sao
hipoteses de quem le a lei, nao de quem a aplica: a pagina existe para serem
confirmadas ou corrigidas por quem opera o sistema.

**O texto de cada dispositivo sai do corpus, nunca redigitado.** E o ponto do
documento: quem revisa julga pelo texto da norma, nao pela minha parafrase dele.

`divergencias.json` vem de uma passada de `busca.buscar` sobre os casos de
`avaliacao.py`, guardando os cinco primeiros resultados de cada consulta em que o
alvo perdeu o primeiro lugar.
"""
import html
import json
from pathlib import Path

RAIZ = Path(__file__).parent
SAIDA = RAIZ / "revisao_gabarito.html"
dados = json.loads((RAIZ / "divergencias.json").read_text(encoding="utf-8"))

# veredito: manter | ambos | trocar | decidir
PARECER = {
 "dispensa imotivada aviso previo": ("manter", "clt/art-487",
  "O art. 487 e a norma do aviso previo. A Sumula 276 responde outra pergunta - se o "
  "empregado pode renunciar ao aviso -, que a consulta nao fez. O alvo caiu para #16, "
  "entao aqui o problema e de ordenacao, nao de gabarito."),
 "grupo economico responsabilidade solidaria": ("manter", "clt/art-2/par-2",
  "O art. 2o, par. 2o e a norma da solidariedade no grupo economico. A OJ 411 diz o "
  "OPOSTO do perguntado: que o sucessor NAO responde solidariamente. E o caso mais claro "
  "de degradacao da lista."),
 "ausencia do reclamante arquivamento custas": ("decidir", "clt/art-844/par-2",
  "A consulta junta dois assuntos. Arquivamento e a Sumula 9; custas pela ausencia e o "
  "art. 844, par. 2o. As duas respostas estao certas para metades diferentes da pergunta - "
  "qual delas o sistema deve por em primeiro depende do que se quis perguntar."),
 "peticao inicial pedido certo determinado": ("decidir", "clt/art-840/par-1",
  "O art. 840, par. 1o (rito ordinario) e o art. 852-B, I (sumarissimo) dizem a mesma "
  "coisa para ritos diferentes. Sem saber o rito, nao ha como dizer qual e a resposta - "
  "e talvez as duas devessem contar."),
 "fornecimento gratuito de equipamento de protecao": ("manter", "clt/art-166",
  "A consulta parafraseia o art. 166 quase palavra por palavra. A Sumula 289 trata de "
  "outra coisa: que o EPI nao exime o adicional de insalubridade."),
 "multa por atraso no pagamento das verbas rescisorias": ("manter", "clt/art-477/par-8",
  "O art. 477, par. 8o e a multa. A OJ 238 e um recorte dela - aplicacao a pessoa juridica "
  "de direito publico -, mais estreito que a pergunta."),
 "jornada de doze horas por trinta e seis de descanso": ("manter", "clt/art-59-A",
  "O art. 59-A e a regra geral do 12x36. O art. 235-F, que veio em #1, e o recorte do "
  "motorista profissional. O alvo esta em #2, entao a perda e pequena."),
 "periodo aquisitivo de ferias faltas injustificadas": ("manter", "clt/art-130",
  "O art. 130 traz a proporcao de dias de ferias conforme as faltas - nos incisos, nao no "
  "caput, que e o que o buscador exibe. O art. 140 trata de contrato com menos de 12 meses, "
  "que e outra hipotese."),
 "duracao normal do trabalho dos bancarios": ("manter", "clt/art-224",
  "A consulta diz 'duracao normal', que e o art. 224. O art. 225, em #1, e a prorrogacao "
  "excepcional para 8 horas - o contrario de normal."),
 "verbas rescisorias incontroversas acrescimo de cinquenta": ("manter", "clt/art-467",
  "O art. 467 e exatamente a parte incontroversa com acrescimo de 50%. A Sumula 69 fala de "
  "revelia e confissao, que a consulta nao mencionou."),
 "transferencia adicional de vinte e cinco por cento": ("ambos", "clt/art-469/par-3 + oj-sdi1-tst/113",
  "O art. 469, par. 3o institui o adicional de 25%. A OJ 113 diz quando ele e devido - "
  "transferencia provisoria, ainda que haja cargo de confianca ou clausula contratual. Uma "
  "peca sobre transferencia costuma citar as duas."),
 "faltas justificadas sem prejuizo do salario": ("manter", "clt/art-473",
  "O art. 473 e literalmente a lista de faltas que nao geram desconto. A Sumula 89 trata do "
  "efeito dessas faltas sobre o periodo aquisitivo de ferias, que e um passo adiante."),
 "justica gratuita insuficiencia de recursos": ("trocar", "clt/art-790/par-4",
  "A consulta usa 'insuficiencia de recursos', que e a expressao do par. 4o. O par. 3o, "
  "apontado hoje pelo gabarito, trata de quem recebe ate 40% do teto do RGPS - outro "
  "criterio. Este parece ser um erro do gabarito, nao do buscador."),
 "deposito recursal para interposicao de recurso": ("decidir", "clt/art-899",
  "O deposito recursal esta no par. 1o do art. 899; o gabarito aponta o caput, que trata "
  "do efeito devolutivo. A Sumula 245 responde sobre o PRAZO do deposito. Tres respostas "
  "possiveis para uma consulta curta demais."),
 "rescisao indireta do contrato de trabalho": ("manter", "clt/art-483",
  "O art. 483 e a rescisao indireta. A Sumula 69, em #1, fala de revelia e casou apenas "
  "por 'rescisao do contrato de trabalho'. E o pior caso da lista: o alvo foi para #47."),
 "sobreaviso escala de plantao": ("ambos", "clt/art-244/par-2 + sumula-tst/428",
  "O art. 244, par. 2o define o sobreaviso e a escala. A Sumula 428 e o que se cita hoje, "
  "porque trata do sobreaviso por instrumento telematico - a forma como o plantao "
  "efetivamente acontece agora."),
 "empregado hipersuficiente pode negociar direto": ("manter", "clt/art-444/par-unico",
  "O art. 444, par. unico e o hipersuficiente. O art. 510-A, em #1, e a comissao de "
  "representantes dos empregados - casou por 'entendimento direto com os empregadores'."),
 "demissao em massa sem negociacao com o sindicato": ("manter", "clt/art-477-A",
  "O art. 477-A e exatamente a dispensa coletiva sem necessidade de autorizacao sindical. "
  "O art. 617, em #1, trata de prazo para o sindicato assumir negociacao - outro assunto."),
 "acumulo de funcao servico compativel com a condicao pessoal": ("manter", "clt/art-456/par-unico",
  "O art. 456, par. unico e a resposta literal. O #1 e 'art. 4o, VII - higiene pessoal', "
  "que casou pela palavra 'pessoal'. Ruido puro, e o exemplo mais evidente de que o "
  "problema aqui e ordenacao."),
 "perda da gratificacao apos dez anos de funcao": ("decidir", "clt/art-468/par-2",
  "Aqui ha um corte de regime, nao uma escolha de melhor resposta. A Sumula 372, I "
  "consagrava a estabilidade financeira apos dez anos; o art. 468, par. 2o, da Reforma, diz "
  "que a gratificacao NAO se incorpora. Sao respostas opostas para periodos diferentes - e "
  "veja a ressalva sobre a Sumula 372 no fim deste documento."),
 "abandono de emprego apos trinta dias de falta": ("ambos", "clt/art-482/al-i + sumula-tst/32",
  "O art. 482, 'i' e a hipotese de justa causa, mas so diz 'abandono de emprego'. A Sumula "
  "32 traz o prazo de 30 dias - com uma ressalva que pode importar: ela fala do retorno "
  "apos cessacao de beneficio previdenciario, nao de falta injustificada em geral."),
 "embargos a execucao com o juizo garantido": ("manter", "clt/art-884",
  "O art. 884 e exatamente embargos com a execucao garantida. A Sumula 419, em #1, trata "
  "de embargos de TERCEIRO em carta precatoria - outro instituto."),
 "trabalho intermitente com convocacao por periodos": ("decidir", "clt/art-443/par-3",
  "O art. 443, par. 3o define o contrato intermitente; o art. 452-A e quem trata da "
  "convocacao, que a consulta menciona expressamente. As duas respondem partes da pergunta."),
 "contratacao por empresa de fachada para fraudar direitos": ("ambos", "clt/art-9 + sumula-tst/331",
  "O art. 9o e a nulidade generica dos atos que fraudam a CLT. A Sumula 331 e o caso "
  "especifico da empresa interposta. Ressalva: o item I da Sumula 331 foi cancelado pela "
  "Reforma - ver o fim deste documento."),
 "assedio no ambiente de trabalho ofensa a honra": ("manter", "clt/art-223-C",
  "O art. 223-C lista a honra entre os bens tutelados de quem SOFRE o dano. O art. 482, "
  "'j' e 'k', que vieram em #1 e #2, sao a justa causa de quem PRATICA a ofensa - "
  "perspectiva invertida."),
}

ROTULO = {
    "manter": "Manter o gabarito",
    "ambos": "Aceitar as duas",
    "trocar": "Trocar o gabarito",
    "decidir": "Precisa da sua decisao",
}
EXPLICA = {
    "manter": "O dispositivo esperado continua sendo a resposta. O que veio em primeiro nao "
              "responde a pergunta feita - e falha de ordenacao, nao de gabarito.",
    "ambos": "A lei e a jurisprudencia respondem juntas. O gabarito hoje so aceita uma URN; "
             "estes casos pedem que aceite duas.",
    "trocar": "O dispositivo apontado pelo gabarito parece nao ser o que a consulta pede.",
    "decidir": "Ha mais de uma leitura defensavel e nenhuma delas e obviamente melhor. "
               "Nao tenho como decidir isto sem formacao juridica.",
}
ORDEM = ["decidir", "trocar", "ambos", "manter"]


def e(t):
    return html.escape(t or "")


def ficha(i, c):
    veredito, proposta, porque = PARECER[c["consulta"]]
    g = c["gabarito"]
    pos = g["posicao"]
    pos_txt = f"#{pos}" if pos else "fora do top 50"
    grave = " grave" if (pos is None or pos > 10) else ""
    cands = "".join(
        f'''<li class="cand {'alvo' if t['urn'] == g['urn'] else ''}">
              <span class="pos">{t['pos']}</span>
              <div class="cand-corpo">
                <p class="cand-topo"><span class="fonte {t['obra'].lower()}">{t['obra']}</span>
                   <strong>{e(t['rotulo'])}</strong>
                   <code>{e(t['urn'])}</code></p>
                <p class="lei">{e(t['texto'])}</p>
              </div>
            </li>''' for t in c["topo"])
    cid = f"c{i}"
    return f'''
<article class="ficha" id="{cid}">
  <header class="ficha-top">
    <span class="num">{i:02d}</span>
    <div>
      <p class="rot">Consulta digitada</p>
      <p class="consulta">{e(c['consulta'])}</p>
    </div>
    <span class="grupo" title="Grupo A: o termo esta no texto da lei. Grupo B: termo forense que a lei nao usa.">Grupo {c['grupo']}</span>
  </header>

  <div class="par">
    <section class="lado">
      <p class="rot">Resposta esperada pelo gabarito <span class="posicao{grave}">hoje em {pos_txt}</span></p>
      <p class="cand-topo"><span class="fonte clt">CLT</span><strong>{e(g['rotulo'])}</strong>
         <code>{e(g['urn'])}</code></p>
      <p class="lei">{e(g['texto'])}</p>
    </section>
    <section class="lado">
      <p class="rot">O que o buscador devolve</p>
      <ol class="cands">{cands}</ol>
    </section>
  </div>

  <section class="parecer v-{veredito}">
    <p class="rot">Minha proposta</p>
    <p class="veredito">{ROTULO[veredito]} <code>{e(proposta)}</code></p>
    <p class="porque">{e(porque)}</p>
  </section>

  <fieldset class="resposta" data-caso="{cid}">
    <legend>Sua verificacao</legend>
    <div class="opcoes">
      <label><input type="radio" name="{cid}" value="concordo"> Concordo</label>
      <label><input type="radio" name="{cid}" value="outra"> A resposta certa e outra</label>
      <label><input type="radio" name="{cid}" value="duvida"> Precisa conversar</label>
    </div>
    <input class="nota" type="text" name="{cid}-nota"
           placeholder="Se for outra: qual dispositivo, e por que" aria-label="Observacao sobre {e(c['consulta'])}">
  </fieldset>
</article>'''


secoes = ""
for v in ORDEM:
    casos = [c for c in dados if PARECER[c["consulta"]][0] == v]
    if not casos:
        continue
    fichas = "".join(ficha(dados.index(c) + 1, c) for c in casos)
    secoes += f'''
<section class="bloco" id="b-{v}">
  <header class="bloco-top">
    <h2><span class="chip v-{v}">{ROTULO[v]}</span> <span class="conta">{len(casos)} consulta{'s' if len(casos) > 1 else ''}</span></h2>
    <p>{EXPLICA[v]}</p>
  </header>
  {fichas}
</section>'''

contagem = {v: sum(1 for c in dados if PARECER[c["consulta"]][0] == v) for v in ORDEM}
resumo = "".join(
    f'<a class="cartao v-{v}" href="#b-{v}"><span class="n">{contagem[v]}</span>'
    f'<span class="l">{ROTULO[v]}</span></a>' for v in ORDEM)

PAGINA = f'''<title>Calibracao do Gabarito</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Spectral:ital,wght@0,400;0,500;1,400&display=swap">
<style>
:root {{
  --paper:#F3F6F7; --surface:#FFFFFF; --surface-2:#E9EEF0; --ink:#16212A;
  --ink-2:#41525C; --muted:#6B7C86; --line:#D5DDE1; --line-forte:#B6C3C9;
  --accent:#14627F; --accent-soft:#E0EDF2;
  --clt:#8A6326; --clt-soft:#F3EADA; --tst:#1D6A57; --tst-soft:#DFEEEA;
  --alert:#9E4726; --alert-soft:#F6E7DF;
  --sans:"IBM Plex Sans",ui-sans-serif,system-ui,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,"SFMono-Regular",monospace;
  --serif:"Spectral",Georgia,"Times New Roman",serif;
}}
@media (prefers-color-scheme:dark) {{
  :root:not([data-theme="light"]) {{
    --paper:#0F161B; --surface:#161F26; --surface-2:#1C272F; --ink:#E4ECF0;
    --ink-2:#B0BFC8; --muted:#7F929D; --line:#28353E; --line-forte:#3A4A55;
    --accent:#5DB2D2; --accent-soft:#13303C;
    --clt:#D6AB69; --clt-soft:#33280F; --tst:#6BC3A8; --tst-soft:#102E26;
    --alert:#DE8A64; --alert-soft:#391E11;
  }}
}}
:root[data-theme="dark"] {{
  --paper:#0F161B; --surface:#161F26; --surface-2:#1C272F; --ink:#E4ECF0;
  --ink-2:#B0BFC8; --muted:#7F929D; --line:#28353E; --line-forte:#3A4A55;
  --accent:#5DB2D2; --accent-soft:#13303C;
  --clt:#D6AB69; --clt-soft:#33280F; --tst:#6BC3A8; --tst-soft:#102E26;
  --alert:#DE8A64; --alert-soft:#391E11;
}}
* {{ box-sizing:border-box; }}
body {{
  background:var(--paper); color:var(--ink); font-family:var(--sans);
  font-size:16px; line-height:1.6; margin:0; padding:0 20px 90px;
  -webkit-font-smoothing:antialiased;
}}
.env {{ max-width:940px; margin:0 auto; }}
h1,h2,h3 {{ text-wrap:balance; margin:0; }}
p {{ margin:0; }}
code {{ font-family:var(--mono); font-size:.8em; color:var(--muted); }}
.rot {{
  font-size:.7rem; text-transform:uppercase; letter-spacing:.09em;
  font-weight:600; color:var(--muted);
}}
.lei {{
  font-family:var(--serif); font-size:.97rem; line-height:1.62; color:var(--ink-2);
  border-left:2px solid var(--line-forte); padding-left:14px; margin-top:8px;
}}

/* topo */
header.capa {{ padding:64px 0 34px; border-bottom:1px solid var(--line); }}
.eyebrow {{
  font-family:var(--mono); font-size:.72rem; letter-spacing:.12em;
  text-transform:uppercase; color:var(--accent); margin-bottom:16px;
}}
header.capa h1 {{ font-family:var(--serif); font-size:clamp(2rem,5vw,2.9rem); font-weight:500; line-height:1.15; }}
.sub {{ margin-top:18px; max-width:66ch; color:var(--ink-2); font-size:1.03rem; }}
.aviso {{
  margin-top:26px; padding:16px 18px; background:var(--accent-soft);
  border-radius:3px; border-left:3px solid var(--accent); max-width:70ch;
  font-size:.93rem; color:var(--ink-2);
}}
.aviso strong {{ color:var(--ink); }}

.resumo {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin:34px 0 10px; }}
.cartao {{
  background:var(--surface); border:1px solid var(--line); border-top:3px solid var(--muted);
  padding:16px; text-decoration:none; color:inherit; display:flex; flex-direction:column; gap:2px;
  transition:border-color .15s, transform .15s;
}}
.cartao:hover {{ transform:translateY(-2px); }}
.cartao .n {{ font-size:1.9rem; font-weight:600; font-variant-numeric:tabular-nums; line-height:1; }}
.cartao .l {{ font-size:.82rem; color:var(--muted); }}
.cartao.v-manter {{ border-top-color:var(--muted); }}
.cartao.v-ambos {{ border-top-color:var(--accent); }}
.cartao.v-trocar {{ border-top-color:var(--alert); }}
.cartao.v-decidir {{ border-top-color:var(--clt); }}

/* blocos */
.bloco {{ margin-top:56px; scroll-margin-top:20px; }}
.bloco-top {{ margin-bottom:22px; }}
.bloco-top h2 {{ font-size:1.02rem; display:flex; align-items:center; gap:12px; flex-wrap:wrap; }}
.bloco-top p {{ margin-top:9px; color:var(--muted); font-size:.92rem; max-width:68ch; }}
.chip {{
  font-size:.76rem; font-weight:600; letter-spacing:.03em; padding:5px 11px;
  border-radius:2px; background:var(--surface-2); color:var(--ink);
}}
.chip.v-ambos {{ background:var(--accent-soft); color:var(--accent); }}
.chip.v-trocar {{ background:var(--alert-soft); color:var(--alert); }}
.chip.v-decidir {{ background:var(--clt-soft); color:var(--clt); }}
.conta {{ font-size:.8rem; color:var(--muted); font-variant-numeric:tabular-nums; }}

/* ficha */
.ficha {{
  background:var(--surface); border:1px solid var(--line); margin-bottom:20px;
  padding:22px 24px 20px;
}}
.ficha-top {{ display:flex; gap:16px; align-items:flex-start; padding-bottom:16px; border-bottom:1px solid var(--line); }}
.num {{
  font-family:var(--mono); font-size:.8rem; color:var(--muted);
  border:1px solid var(--line); padding:3px 7px; font-variant-numeric:tabular-nums;
}}
.consulta {{ font-family:var(--mono); font-size:1.02rem; color:var(--ink); margin-top:3px; }}
.ficha-top > div {{ flex:1; min-width:0; }}
.grupo {{ font-size:.72rem; color:var(--muted); white-space:nowrap; cursor:help; }}

.par {{ display:grid; grid-template-columns:1fr; gap:26px; padding:18px 0; }}
@media (min-width:820px) {{ .par {{ grid-template-columns:minmax(0,.86fr) minmax(0,1.14fr); gap:34px; }} }}
.lado {{ min-width:0; display:flex; flex-direction:column; gap:8px; }}
.posicao {{
  font-family:var(--mono); font-size:.68rem; letter-spacing:0; text-transform:none;
  background:var(--surface-2); color:var(--ink-2); padding:2px 7px; margin-left:6px;
}}
.posicao.grave {{ background:var(--alert-soft); color:var(--alert); }}
.cand-topo {{ display:flex; gap:8px; align-items:baseline; flex-wrap:wrap; font-size:.93rem; }}
.fonte {{
  font-size:.65rem; font-weight:600; letter-spacing:.07em; padding:2px 6px; border-radius:2px;
}}
.fonte.clt {{ background:var(--clt-soft); color:var(--clt); }}
.fonte.tst {{ background:var(--tst-soft); color:var(--tst); }}
.cands {{ list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:14px; }}
.cand {{ display:flex; gap:11px; }}
.cand .pos {{
  font-family:var(--mono); font-size:.72rem; color:var(--muted); padding-top:2px;
  min-width:16px; font-variant-numeric:tabular-nums;
}}
.cand-corpo {{ min-width:0; }}
.cand.alvo .cand-corpo {{ background:var(--accent-soft); margin:-6px -9px; padding:6px 9px; }}
.cand .lei {{ font-size:.9rem; margin-top:5px; }}

.parecer {{
  background:var(--surface-2); padding:15px 17px; border-left:3px solid var(--muted);
  display:flex; flex-direction:column; gap:6px;
}}
.parecer.v-ambos {{ border-left-color:var(--accent); }}
.parecer.v-trocar {{ border-left-color:var(--alert); }}
.parecer.v-decidir {{ border-left-color:var(--clt); }}
.veredito {{ font-weight:600; font-size:.98rem; display:flex; gap:9px; align-items:baseline; flex-wrap:wrap; }}
.porque {{ color:var(--ink-2); font-size:.93rem; max-width:74ch; }}

.resposta {{ border:1px dashed var(--line-forte); margin:16px 0 0; padding:13px 16px 15px; }}
.resposta legend {{ font-size:.7rem; text-transform:uppercase; letter-spacing:.09em; color:var(--muted); font-weight:600; padding:0 6px; }}
.opcoes {{ display:flex; gap:18px; flex-wrap:wrap; }}
.opcoes label {{ display:flex; gap:7px; align-items:center; font-size:.9rem; cursor:pointer; color:var(--ink-2); }}
input[type=radio] {{ accent-color:var(--accent); }}
.nota {{
  margin-top:11px; width:100%; padding:8px 10px; font-family:var(--sans); font-size:.9rem;
  background:var(--surface); color:var(--ink); border:1px solid var(--line);
}}
.nota::placeholder {{ color:var(--muted); }}
:focus-visible {{ outline:2px solid var(--accent); outline-offset:2px; }}

/* anexos */
.anexo {{ margin-top:56px; padding-top:30px; border-top:1px solid var(--line); }}
.anexo h2 {{ font-family:var(--serif); font-size:1.45rem; font-weight:500; }}
.anexo h3 {{ font-size:.98rem; margin-top:26px; }}
.anexo p {{ color:var(--ink-2); margin-top:10px; max-width:70ch; font-size:.95rem; }}
.tab {{ width:100%; border-collapse:collapse; margin-top:14px; font-size:.9rem; }}
.tab th, .tab td {{ text-align:left; padding:9px 12px; border-bottom:1px solid var(--line); vertical-align:top; }}
.tab th {{ font-size:.7rem; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); }}
.rolar {{ overflow-x:auto; }}

.modo {{
  display:flex; align-items:center; gap:10px; margin-top:22px; max-width:70ch;
  padding:11px 15px; background:var(--surface); border:1px solid var(--line);
  font-size:.88rem; color:var(--ink-2);
}}
.ponto {{ width:8px; height:8px; border-radius:50%; background:var(--muted); flex:none; }}
.modo-salva {{ border-color:var(--tst); }}
.modo-salva .ponto {{ background:var(--tst); }}
.modo-local {{ border-color:var(--clt); }}
.modo-local .ponto {{ background:var(--clt); }}
.saida {{ margin-top:22px; }}
.saida textarea {{
  width:100%; min-height:190px; font-family:var(--mono); font-size:.82rem; line-height:1.6;
  padding:13px; background:var(--surface); color:var(--ink); border:1px solid var(--line);
}}
button {{
  font-family:var(--sans); font-size:.9rem; font-weight:500; padding:10px 18px;
  background:var(--accent); color:var(--paper); border:0; cursor:pointer;
}}
button:hover {{ opacity:.9; }}
.botoes {{ display:flex; align-items:center; gap:12px; flex-wrap:wrap; margin-bottom:14px; }}
button.secundario {{ background:transparent; color:var(--accent); border:1px solid var(--accent); }}
.copiado {{ font-size:.84rem; color:var(--tst); }}
footer {{ margin-top:50px; padding-top:22px; border-top:1px solid var(--line); color:var(--muted); font-size:.85rem; }}
@media (prefers-reduced-motion:reduce) {{ * {{ transition:none !important; }} }}
</style>

<div class="env">
<header class="capa">
  <p class="eyebrow">IA-Judicial &middot; revisao do conjunto de avaliacao</p>
  <h1>Calibracao do gabarito de busca</h1>
  <p class="sub">O sistema passou a indexar as sumulas e OJs do TST, alem da CLT. Em
  25 das 72 consultas de teste, o dispositivo que o gabarito espera deixou de ser o
  primeiro resultado. Parte disso e o buscador errando; parte e o gabarito ter sido
  escrito quando o corpus era so a CLT. Separar as duas coisas exige leitura juridica.</p>
  <div class="aviso"><strong>O que eu preciso de voce:</strong> em cada ficha ha o texto
  integral dos candidatos e uma proposta minha. As propostas sao hipoteses de quem le a
  lei, nao de quem a aplica &mdash; confirme, corrija ou marque para conversarmos.</div>
  <p id="modo" class="modo modo-verificando"><span class="ponto"></span><span id="modo-txt">Suas respostas estao sendo guardadas neste navegador.</span></p>
  <nav class="resumo">{resumo}</nav>
</header>

{secoes}

<section class="anexo">
  <h2>Duas coisas que apareceram no caminho</h2>

  <h3>1. Tres sumulas tiveram apenas um <em>item</em> cancelado, e o sistema as serve inteiras</h3>
  <p>A ingestao trata cancelamento no nivel do verbete. Quando o TST cancela so um item,
  a sumula continua vigente e o item cancelado permanece no texto exibido &mdash; com a
  marca do cancelamento visivel, mas sem que a busca o filtre. Sao tres casos, todos
  cancelados pela Reforma em 11/11/2017:</p>
  <div class="rolar"><table class="tab">
    <tr><th>Verbete</th><th>Item cancelado</th><th>Efeito hoje</th></tr>
    <tr><td>Sumula 6 do TST</td><td>equiparacao em quadro de carreira homologado</td><td rowspan="3">Servida como vigente. O texto mostra a marca de cancelamento, entao quem le percebe &mdash; mas a busca nao separa.</td></tr>
    <tr><td>Sumula 331 do TST</td><td>item I, contratacao por empresa interposta</td></tr>
    <tr><td>Sumula 372 do TST</td><td>item I, estabilidade financeira apos dez anos</td></tr>
  </table></div>
  <p>Se isso importar na pratica, da para tratar item por item &mdash; e trabalho de
  parsing, nao de decisao juridica. Preciso saber se vale.</p>

  <h3>2. O catalogo cita tres normas que nao valem mais</h3>
  <p>A conferencia entre catalogo e corpus encontrou isto sozinha. Nao sao erros de
  ingestao: sao fundamentos do catalogo apontando para norma cancelada. O sistema nao as
  transcreve para um caso atual &mdash; devolve o aviso de quando cairam &mdash; mas o
  catalogo segue as tratando como fundamento presente.</p>
  <div class="rolar"><table class="tab">
    <tr><th>Citada por</th><th>Verbete</th><th>Ate</th><th>Por que caiu</th></tr>
    <tr><td>Intervalo intrajornada suprimido</td><td>Sumula 437 do TST</td><td>10/11/2017</td><td>perda de eficacia pela Lei 13.467/2017</td></tr>
    <tr><td>Ferias em dobro</td><td>Sumula 450 do TST</td><td>14/08/2022</td><td>decisao do STF na ADPF 501</td></tr>
    <tr><td>Intervalo interjornada desrespeitado</td><td>OJ 355 da SBDI-I</td><td>10/11/2017</td><td>perda de eficacia pela Lei 13.467/2017</td></tr>
  </table></div>
  <p>Para contrato anterior ao corte elas continuam citaveis, e a peca ja as traz com a
  janela de vigencia ao lado. O que precisa de decisao e o que colocar no lugar delas
  para os casos de hoje.</p>

  <h3>3. Uma proposta de formato, se voce concordar com as fichas azuis</h3>
  <p>Hoje o gabarito aceita <em>uma</em> resposta certa por consulta. Nos casos marcados
  como <span class="chip v-ambos">Aceitar as duas</span>, a lei e a jurisprudencia
  respondem juntas, e obrigar o teste a escolher uma reprova o sistema quando ele acerta.
  Se voce confirmar esses casos, mudo o conjunto de avaliacao para aceitar uma lista de
  dispositivos por consulta. E mudanca de codigo, so depende da sua confirmacao.</p>
</section>

<section class="anexo saida" id="devolver">
  <h2>Devolver as respostas</h2>
  <p>Suas marcacoes ficam guardadas neste navegador enquanto voce trabalha, e so voce as
  ve. Para devolve-las, o botao junta tudo num texto simples &mdash; pode mandar por onde
  preferir.</p>
  <p class="botoes"><button id="gerar" type="button">Gerar texto das respostas</button>
     <button id="copiar" type="button" class="secundario" hidden>Copiar</button>
     <span id="copiado" class="copiado" hidden>Copiado</span></p>
  <textarea id="texto" readonly aria-label="Respostas reunidas para copiar"
            placeholder="Marque as fichas acima e clique no botao."></textarea>
</section>

<script type="application/json" id="respostas">{{}}</script>

<footer>Gerado a partir do corpus em dados/corpus.db &mdash; 4.716 dispositivos, 6.804
redacoes. O texto de cada dispositivo sai do indice, sem redigitacao.</footer>
</div>

<script>
(function () {{
  var CHAVE = "calibracao-gabarito-v1";
  var INICIAL = "Suas respostas estao sendo guardadas neste navegador.";
  var estado = {{}};
  try {{ estado = JSON.parse(document.getElementById("respostas").textContent) || {{}}; }}
  catch (e) {{ estado = {{}}; }}

  var artifact = null, podeSalvar = false;
  var timer = null, publicando = false, refazer = false;

  function lerLocal() {{
    try {{ return JSON.parse(localStorage.getItem(CHAVE) || "{{}}") || {{}}; }} catch (e) {{ return {{}}; }}
  }}
  function gravarLocal() {{
    try {{ localStorage.setItem(CHAVE, JSON.stringify(estado)); }} catch (e) {{ /* janela anonima */ }}
  }}
  function modo(classe, texto) {{
    document.getElementById("modo").className = "modo " + classe;
    document.getElementById("modo-txt").textContent = texto;
  }}

  // O documento a publicar. So o bloco JSON muda: os controles sao markup estatico
  // e o script mexe apenas em propriedades (.checked, .value), que nao serializam.
  // Por isso o clone sai limpo, sem as marcacoes assadas no HTML duas vezes.
  function documento() {{
    var clone = document.documentElement.cloneNode(true);
    clone.querySelector("#respostas").textContent = JSON.stringify(estado);
    clone.querySelector("#modo").className = "modo modo-verificando";
    clone.querySelector("#modo-txt").textContent = INICIAL;
    clone.querySelector("#texto").value = "";
    return "<!doctype html>\\n<html lang=\\"pt-br\\">" + clone.innerHTML + "</html>";
  }}

  function publicar() {{
    if (publicando) {{ refazer = true; return; }}
    publicando = true;
    modo("modo-salva", "Salvando\\u2026");
    artifact.publish(documento()).then(function () {{
      publicando = false;
      modo("modo-salva", "Respostas salvas na pagina. Quem abrir este link ve o que voce marcou.");
      if (refazer) {{ refazer = false; agendar(); }}
    }}).catch(function (erro) {{
      publicando = false;
      // Conflito e rotina: alguem publicou antes e toda visao recarrega para a
      // versao vencedora. Reenviar por cima seria apagar o que a outra salvou.
      if (erro && erro.code === "conflict") {{
        modo("modo-salva", "Outra pessoa salvou primeiro \\u2014 a pagina vai recarregar com a versao dela.");
        return;
      }}
      cairParaLocal();
    }});
  }}

  function agendar() {{
    gravarLocal();
    if (!podeSalvar) return;
    clearTimeout(timer);
    timer = setTimeout(publicar, 700);
  }}

  function cairParaLocal() {{
    podeSalvar = false;
    var local = lerLocal();
    for (var k in local) {{ if (!estado[k]) estado[k] = local[k]; }}
    aplicar();
    gravarLocal();
    modo("modo-local", "Suas respostas ficam neste navegador. Para devolve-las, use \\u201cDevolver as respostas\\u201d, no fim da pagina.");
  }}

  function aplicar() {{
    document.querySelectorAll(".resposta").forEach(function (bloco) {{
      var d = estado[bloco.dataset.caso] || {{}};
      bloco.querySelectorAll("input[type=radio]").forEach(function (r) {{
        r.checked = (d.escolha === r.value);
      }});
      var nota = bloco.querySelector(".nota");
      if (nota.value !== (d.nota || "")) nota.value = d.nota || "";
    }});
  }}

  document.querySelectorAll(".resposta").forEach(function (bloco) {{
    var id = bloco.dataset.caso;
    bloco.querySelectorAll("input[type=radio]").forEach(function (r) {{
      r.addEventListener("change", function () {{
        estado[id] = Object.assign({{}}, estado[id], {{ escolha: r.value }});
        agendar();
      }});
    }});
    var nota = bloco.querySelector(".nota");
    // Cada tecla vai para o armazenamento local; a publicacao so no "change",
    // que dispara ao sair do campo. Publicar recarrega TODA visao aberta, e
    // fazer isso a cada letra tiraria o cursor da mao dela.
    nota.addEventListener("input", function () {{
      estado[id] = Object.assign({{}}, estado[id], {{ nota: nota.value }});
      gravarLocal();
    }});
    nota.addEventListener("change", function () {{
      estado[id] = Object.assign({{}}, estado[id], {{ nota: nota.value }});
      agendar();
    }});
  }});

  aplicar();

  var NOMES = {{ concordo: "concordo", outra: "OUTRA RESPOSTA", duvida: "conversar" }};
  document.getElementById("gerar").addEventListener("click", function () {{
    var linhas = ["Revisao do gabarito de busca - respostas", ""], pendentes = 0;
    document.querySelectorAll(".ficha").forEach(function (f) {{
      var d = estado[f.id];
      if (!d || !d.escolha) {{ pendentes++; return; }}
      linhas.push("- " + f.querySelector(".consulta").textContent.trim());
      linhas.push("    proposta: " + f.querySelector(".veredito").textContent.trim());
      linhas.push("    resposta: " + (NOMES[d.escolha] || d.escolha));
      if (d.nota) linhas.push("    nota: " + d.nota);
      linhas.push("");
    }});
    if (pendentes) linhas.push("(" + pendentes + " ficha(s) ainda sem resposta)");
    document.getElementById("texto").value = linhas.join("\\n");
    document.getElementById("copiar").hidden = false;
  }});

  document.getElementById("copiar").addEventListener("click", function () {{
    var campo = document.getElementById("texto");
    var aviso = document.getElementById("copiado");
    function confirmou() {{
      aviso.hidden = false;
      setTimeout(function () {{ aviso.hidden = true; }}, 2500);
    }}
    // A area de transferencia pode estar bloqueada pelo navegador ou pela moldura
    // da pagina. Quando estiver, seleciona o texto para o Ctrl+C dela funcionar -
    // o botao nunca fica sem efeito nenhum.
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      navigator.clipboard.writeText(campo.value).then(confirmou).catch(function () {{
        campo.focus(); campo.select();
      }});
    }} else {{
      campo.focus(); campo.select();
    }}
  }});

  if (window.claude && typeof window.claude.use === "function") {{
    window.claude.use("artifact").then(function (ns) {{
      if (!ns) {{ cairParaLocal(); return; }}
      artifact = ns;
      podeSalvar = true;
      // Nada de anunciar que salva. Em Pro e Max o link publico e a unica forma de
      // compartilhar, e nao existe papel de editor: quem abre pelo link e leitor,
      // e a recusa so chega na PRIMEIRA publicacao, nunca no use(). Prometer aqui
      // seria mentir para a maioria dos leitores. A faixa so muda quando uma
      // publicacao de fato passar.
    }}).catch(cairParaLocal);
  }} else {{
    cairParaLocal();
  }}
}})();
</script>'''

SAIDA.write_text(PAGINA, encoding="utf-8")
print(f"{SAIDA}  {len(PAGINA):,} bytes")
print(f"fichas: {len(dados)}   sem parecer: {[c['consulta'] for c in dados if c['consulta'] not in PARECER]}")
for v in ORDEM:
    print(f"  {v}: {contagem[v]}")
