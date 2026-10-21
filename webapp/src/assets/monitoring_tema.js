/* Monitoramento de Ativos — painel claro × escuro, resolvido no navegador.
 *
 * A escolha é de quem está olhando, não do sistema: fica guardada no navegador e acompanha a
 * pessoa na próxima visita. Por isso vive aqui e não num callback do Dash — o botão existe em
 * dois lugares (a barra de controles e a faixa de tela cheia) e nem sempre os dois estão na
 * tela ao mesmo tempo; um callback exigiria os dois ids presentes sempre. O navegador resolve
 * lendo a classe, e ainda mantém os dois rótulos sincronizados.
 *
 * O atributo é escrito no elemento raiz do documento porque, em tela cheia, quem ocupa a
 * janela é o documento inteiro — preso à página, o tema deixaria a moldura de fora.
 *
 * Restaurar no carregamento é o que evita o piscar: sem isso, um F5 abriria claro e a tela
 * escureceria só depois do primeiro clique.
 */
(function () {
  "use strict";

  var CHAVE = "mon-tema";

  function guardado() {
    try { return localStorage.getItem(CHAVE) || "claro"; } catch (e) { return "claro"; }
  }

  function guardar(tema) {
    try { localStorage.setItem(CHAVE, tema); } catch (e) { /* aba anônima */ }
  }

  /* Idempotente de propósito: só escreve o que estiver diferente.
   *
   * O observador abaixo acorda a cada mudança do layout — e as mudanças que esta função faz
   * são mudanças do layout. Escrevendo sem conferir, ela acordaria a si mesma em laço e
   * travaria a página (aconteceu na primeira versão: a tela congelou por completo). */
  function aplicar(tema) {
    if (document.documentElement.getAttribute("data-mon-tema") !== tema) {
      document.documentElement.setAttribute("data-mon-tema", tema);
    }
    var escuro = tema === "escuro";
    // Os dois botões dizem a mesma coisa, e o rótulo aponta para onde o clique leva — não
    // para onde se está: "Painel claro" enquanto se olha o escuro.
    var classe = (escuro ? "bi bi-sun" : "bi bi-moon-stars") + " me-2 mon-tema-icone";
    document.querySelectorAll(".mon-tema-icone").forEach(function (icone) {
      if (icone.className !== classe) { icone.className = classe; }
    });
    var rotulo = escuro ? "Painel claro" : "Painel escuro";
    document.querySelectorAll(".mon-tema-texto").forEach(function (texto) {
      if (texto.textContent !== rotulo) { texto.textContent = rotulo; }
    });
  }

  /* Quem chama a alternância é um callback do Dash, não um ouvinte de clique daqui.
   *
   * Parece rodeio, e não é: um botão do Dash com `n_clicks` que ninguém escuta faz o Dash
   * remontar a árvore da rota ao ser clicado — e os blocos da página do ativo (linha do tempo,
   * cards, tabelas) nascem vazios nessa árvore, porque quem os preenche é outro callback. O
   * resultado é a página se esvaziando ao trocar de tema. Com o callback no lugar, o clique é
   * consumido normalmente e nada se perde. */
  function alternar() {
    var proximo = guardado() === "escuro" ? "claro" : "escuro";
    guardar(proximo);
    aplicar(proximo);
  }

  window.monTema = { alternar: alternar, aplicar: function () { aplicar(guardado()); } };

  // O layout do Dash é montado depois deste arquivo: o atributo vai na raiz agora, e os
  // rótulos são acertados quando os botões aparecem na tela.
  document.documentElement.setAttribute("data-mon-tema", guardado());

  var observador = new MutationObserver(function () {
    if (document.querySelector(".mon-tema-texto")) { aplicar(guardado()); }
  });


  function ligar() {
    aplicar(guardado());
    observador.observe(document.body, { childList: true, subtree: true });
  }

  if (document.body) { ligar(); }
  else { document.addEventListener("DOMContentLoaded", ligar); }
})();
