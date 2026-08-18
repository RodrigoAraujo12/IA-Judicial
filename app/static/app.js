// Tres responsabilidades:
//  1. visibilidade condicional simples, avaliada localmente para nao perder o
//     foco enquanto se digita;
//  2. atualizacao do painel lateral, sempre calculado no servidor;
//  3. visibilidade das perguntas de QUANTIFICACAO, que depende da triagem e por
//     isso vem pronta do servidor junto com o painel.
//
// O padrao e o mesmo do HTMX (POST -> fragmento de HTML -> swap). Quando o
// formulario crescer, trocar por HTMX e substituir estas linhas por
// hx-post/hx-target, sem mudar o servidor.

(function () {
  "use strict";

  const form = document.getElementById("entrevista");
  const painel = document.getElementById("analise");
  if (!form) return;

  const REGRAS = JSON.parse(document.getElementById("regras").textContent);
  const TIPOS = JSON.parse(document.getElementById("tipos").textContent);

  function valor(fd, campo) {
    const tipo = TIPOS[campo];
    if (tipo === "multipla") {
      const v = fd.getAll(campo).filter(Boolean);
      return v.length ? v : null;
    }
    const bruto = fd.get(campo);
    if (bruto === null || String(bruto).trim() === "") return null;
    const s = String(bruto).trim();
    if (tipo === "bool") return s === "sim";
    return s;
  }

  // Espelha app/motor.py: true, false ou null (nao respondido).
  function condicao(c, fd) {
    const v = valor(fd, c.campo);
    if (c.op === "preenchido") return v !== null;
    if (v === null) return null;
    switch (c.op) {
      case "verdadeiro": return v === true;
      case "falso":      return v === false;
      case "igual":      return v === c.valor;
      case "diferente":  return v !== c.valor;
      case "em": {
        const alvo = c.valor || [];
        return Array.isArray(v) ? v.some((x) => alvo.includes(x)) : alvo.includes(v);
      }
      case "maior":      return parseFloat(v) > parseFloat(c.valor);
      case "menor":      return parseFloat(v) < parseFloat(c.valor);
      default:           return null;
    }
  }

  // Dentro do grupo vale E, entre grupos vale OU. Indefinido nao esconde.
  function grupos(lista, fd) {
    if (!lista || !lista.length) return true;
    let algumIndefinido = false;
    for (const grupo of lista) {
      const rs = grupo.map((c) => condicao(c, fd));
      if (rs.some((r) => r === false)) continue;
      if (rs.some((r) => r === null)) { algumIndefinido = true; continue; }
      return true;
    }
    return algumIndefinido ? null : false;
  }

  function aplicarVisibilidade() {
    const fd = new FormData(form);
    for (const [id, regra] of Object.entries(REGRAS)) {
      const bloco = document.querySelector(`.pergunta[data-id="${id}"]`);
      if (bloco) bloco.hidden = grupos(regra, fd) === false;
    }
  }

  // Quantificacao: o servidor decide, porque depende do resultado da triagem.
  function aplicarQuantificacao() {
    const dados = document.getElementById("quant-visiveis");
    if (!dados) return;
    const visiveis = new Set(JSON.parse(dados.textContent));
    document.querySelectorAll(".pergunta[data-quant]").forEach((bloco) => {
      bloco.hidden = !visiveis.has(bloco.dataset.id);
    });
  }

  let pendente = null;
  async function atualizarPainel() {
    const resposta = await fetch("/analise", { method: "POST", body: new FormData(form) });
    painel.innerHTML = await resposta.text();
    aplicarQuantificacao();
  }

  function aoMudar() {
    aplicarVisibilidade();
    clearTimeout(pendente);
    pendente = setTimeout(atualizarPainel, 180);
  }

  form.addEventListener("input", aoMudar);
  form.addEventListener("change", aoMudar);

  // --- salvar ---------------------------------------------------------------
  const botao = document.getElementById("salvar");
  const aviso = document.getElementById("aviso-salvo");
  if (botao) {
    botao.addEventListener("click", async () => {
      const resposta = await fetch("/caso/salvar", { method: "POST", body: new FormData(form) });
      const dados = await resposta.json();
      document.getElementById("caso_id").value = dados.id;
      aviso.textContent = "salvo " + new Date().toLocaleTimeString("pt-BR");
      setTimeout(() => { aviso.textContent = ""; }, 4000);
    });
  }

  aplicarVisibilidade();
  aplicarQuantificacao();
})();
