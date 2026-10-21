// webapp/src/assets/fa_diagrama_imagem.js
//
// Imagem do diagrama para o slide (IM-AF3-08). Depois que a análise é carregada ou
// salva, o navegador:
//   1. pergunta ao servidor se a imagem guardada ainda desenha a árvore do banco;
//   2. se não, pede ao quadro (iframe do Excalidraw) o SVG + PNG do desenho;
//   3. envia para a rota, junto com a versão da análise que está na tela.
//
// Tudo em segundo plano: falhar aqui não afeta o Salvar — o slide só usa o redesenho
// do servidor. Com alteração não salva na tela, não envia (a imagem tem de ser a da
// árvore gravada). Funciona com o quadro escondido (botão v2.0): exportar não depende
// da área visível.

(function () {
  "use strict";

  var ESPERA_MS = 2500;      // deixa o quadro redesenhar a árvore recém-salva
  var TENTATIVAS = 5;
  var alvo = null;           // {id, versao} da análise na tela
  var timer = null;
  var seq = 0;
  var pendente = {};         // req -> {id, versao, tentativa}

  function temAlteracaoNaoSalva() {
    var b = document.getElementById("fa-btn-salvar");
    return !!(b && b.classList.contains("fa-dirty-blink"));
  }

  function quadro() {
    var f = document.getElementById("fa-frame");
    return f && f.contentWindow ? f.contentWindow : null;
  }

  function base(id) { return "/api/failure-analysis/" + encodeURIComponent(id) + "/diagram"; }

  function tentar(id, versao, tentativa) {
    if (!alvo || alvo.id !== id || alvo.versao !== versao) return;   // outra análise/versão
    if (temAlteracaoNaoSalva()) return;
    fetch(base(id) + "/estado?versao=" + versao, { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        if (!j || j.atual || j.versao_banco !== undefined) return;    // em dia, ou tela velha
        var w = quadro();
        if (!w) return;
        var req = "img" + (++seq);
        pendente[req] = { id: id, versao: versao, tentativa: tentativa };
        w.postMessage({ cmd: "exportar", req: req }, "*");
      })
      .catch(function () { /* sem rede: o slide usa o redesenho */ });
  }

  window.addEventListener("message", function (e) {
    var d = e.data || {};
    if (d.type !== "exportado" || !pendente[d.req]) return;
    var p = pendente[d.req];
    delete pendente[d.req];
    if (d.erro) {
      if (d.erro === "ocupado" && p.tentativa < TENTATIVAS) {
        setTimeout(function () { tentar(p.id, p.versao, p.tentativa + 1); }, 3000);
      }
      return;
    }
    if (temAlteracaoNaoSalva()) return;   // mexeram enquanto exportava
    fetch(base(p.id), {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ svg: d.svg, png: d.png, versao: p.versao }),
    }).catch(function () {});
  });

  // Chamado pelo clientside callback que ouve `store-fa-analise`.
  window.faDiagramaImagem = {
    agendar: function (id, versao) {
      alvo = { id: id, versao: versao };
      clearTimeout(timer);
      timer = setTimeout(function () { tentar(id, versao, 1); }, ESPERA_MS);
    },
  };
})();
