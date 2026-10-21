// webapp/src/assets/fa_diagrama_versao.js
//
// Troca de versão do diagrama da Análise de Falhas: v2.0 (Cytoscape, o antigo) ou
// v3.0 (Excalidraw, o novo). Os dois ficam no DOM e ouvem o mesmo store de balões
// (`store-fa-nos`); trocar é só mostrar um e esconder o outro.
//
// - A escolha fica no navegador de cada pessoa (localStorage); padrão = v3.0.
// - Com alteração não salva a troca é recusada: um diagrama pode estar no meio de
//   uma edição que o outro não vê (ex.: seta solta no desenho livre).
// - O Cytoscape desenhado escondido fica com tamanho zero; ao aparecer, reajusta
//   o tamanho e enquadra os balões.

(function () {
  "use strict";

  var CHAVE = "fa-diagrama-versao";
  var PADRAO = "v3";

  function lerVersao() {
    try { return localStorage.getItem(CHAVE) === "v2" ? "v2" : PADRAO; }
    catch (e) { return PADRAO; }
  }

  function gravarVersao(v) {
    try { localStorage.setItem(CHAVE, v); } catch (e) { /* sem storage: vale só nesta tela */ }
  }

  function temAlteracaoNaoSalva() {
    var b = document.getElementById("fa-btn-salvar");
    return !!(b && b.classList.contains("fa-dirty-blink"));
  }

  function avisar(texto) {
    var el = document.getElementById("fa-diag-versao-aviso");
    if (!el) return;
    el.textContent = texto;
    clearTimeout(el._faT);
    if (texto) el._faT = setTimeout(function () { el.textContent = ""; }, 4000);
  }

  function marcarBotao(id, ativo) {
    var b = document.getElementById(id);
    if (!b) return;
    b.classList.toggle("btn-primary", ativo);
    b.classList.toggle("btn-outline-primary", !ativo);
  }

  function enquadrarCytoscape() {
    var el = document.getElementById("fa-diagrama");
    var cy = el && el._cyreg && el._cyreg.cy;
    if (!cy) return;
    cy.resize();
    cy.fit(undefined, 30);
  }

  function aplicar(v) {
    var novo = document.getElementById("fa-diagrama-v3");
    var antigo = document.getElementById("fa-diagrama-legado");
    if (!novo || !antigo) return false;
    novo.style.display = v === "v3" ? "" : "none";
    antigo.style.display = v === "v2" ? "" : "none";
    marcarBotao("fa-btn-diag-v2", v === "v2");
    marcarBotao("fa-btn-diag-v3", v === "v3");
    if (v === "v2") setTimeout(enquadrarCytoscape, 50);
    return true;
  }

  document.addEventListener("click", function (ev) {
    var b = ev.target.closest && ev.target.closest("#fa-btn-diag-v2, #fa-btn-diag-v3");
    if (!b) return;
    var v = b.id === "fa-btn-diag-v2" ? "v2" : "v3";
    if (v === lerVersao()) return;
    if (temAlteracaoNaoSalva()) {
      avisar("Salve ou descarte as alterações antes de trocar de versão.");
      return;
    }
    avisar("");
    gravarVersao(v);
    aplicar(v);
  });

  // A página é SPA: o diagrama entra e sai do DOM ao navegar. Quando ele aparece,
  // aplica a versão lembrada.
  var montado = null;
  new MutationObserver(function () {
    var atual = document.getElementById("fa-diagrama-v3");
    if (atual && atual !== montado && aplicar(lerVersao())) montado = atual;
  }).observe(document.documentElement, { childList: true, subtree: true });
})();
