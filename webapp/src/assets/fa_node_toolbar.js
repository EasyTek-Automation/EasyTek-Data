// webapp/src/assets/fa_node_toolbar.js
//
// Duas responsabilidades sobre o diagrama cytoscape (#fa-diagrama):
//
// 1. TOOLBAR NO HOVER — ao passar o mouse sobre um balão, a toolbar
//    (#fa-node-toolbar: + / ++ / ✎ editar / ★ causa raiz / ⏱ tempo / 🗑 excluir /
//    ∅ explicativo) aparece
//    ancorada ACIMA dele, SEM precisar clicar. O balão sob o mouse vira o selecionado
//    (store-fa-selecionado via set_props), então os botões agem sobre ele.
//
// 2. ZOOM SÓ COM SHIFT+SCROLL — a roda nativa do cytoscape é desligada
//    (userZoomingEnabled=False no Python). Aqui: Shift+roda dá zoom no ponto do
//    cursor; roda sem Shift NÃO faz zoom e deixa a página rolar normalmente.
//
// Só posicionamento/eventos são JS — as operações são callbacks Python. Padrão
// da casa (assets/*.js + `el._cyreg.cy` + dash_clientside.set_props).

(function () {
  "use strict";

  function getCy() {
    var el = document.getElementById("fa-diagrama");
    return el && el._cyreg && el._cyreg.cy ? el._cyreg.cy : null;
  }

  function setSelecionado(id) {
    var cs = window.dash_clientside;
    if (cs && cs.set_props) cs.set_props("store-fa-selecionado", { data: id });
  }

  function place(node, cy) {
    var tb = document.getElementById("fa-node-toolbar");
    if (!tb || !node || !cy) return;
    // Torna visível ANTES de medir, senão offsetHeight vem 0 (display:none).
    tb.style.display = "block";
    var p = node.renderedPosition();
    var h = node.renderedHeight ? node.renderedHeight() : 58;
    var tbH = tb.offsetHeight || 34;   // altura real da toolbar
    var gap = 12;                       // folga base entre a toolbar e o topo do balão
    // Posiciona a toolbar INTEIRA acima do balão (topo do balão = p.y - h/2),
    // subindo a própria altura + a folga. O ×1.4 sobe mais 40% (pedido do usuário).
    var lift = (tbH + gap) * 1.4;
    tb.style.left = Math.max(0, p.x - 70) + "px";
    tb.style.top = Math.max(0, p.y - h / 2 - lift) + "px";
  }

  // Faz o INPUT ocupar o interior do balão — mesma posição, tamanho, fonte e cor,
  // e com o MESMO fundo do nó (opaco), cobrindo o label do canvas. Dá a impressão
  // de que o próprio texto do balão virou editável (estilo PowerPoint), sem uma
  // caixa flutuando por cima com o texto atrás.
  function placeInline(node, cy) {
    var ed = document.getElementById("fa-inline-editor");
    var inp = document.getElementById("fa-inline-text");
    if (!ed || !node || !cy) return;
    var p = node.renderedPosition();
    var w = node.renderedWidth ? node.renderedWidth() : 170;
    var h = node.renderedHeight ? node.renderedHeight() : 58;
    var pad = 5;   // deixa a borda + um anel do fundo do nó aparecerem em volta
    ed.style.left = (p.x - w / 2 + pad) + "px";
    ed.style.top = (p.y - h / 2 + pad) + "px";
    ed.style.width = Math.max(20, w - 2 * pad) + "px";
    ed.style.height = Math.max(16, h - 2 * pad) + "px";
    if (inp) {
      var fs = 11;
      try { fs = parseFloat(node.numericStyle("font-size")) || 11; } catch (e) {}
      inp.style.fontSize = (fs * cy.zoom()) + "px";  // acompanha o zoom, como o label
      try {
        inp.style.color = node.style("color") || "#212529";
        inp.style.background = node.style("background-color") || "#ffffff";  // cobre o label
      } catch (e2) {}
    }
  }

  function hide(id) {
    var el = document.getElementById(id);
    if (el) el.style.display = "none";
  }

  // Limita o pan às BORDAS do conteúdo: nenhum balão pode passar da borda da tela.
  // Quando a borda do conteúdo bate no limite do container, o pan para ali (0% para
  // fora). Se o conteúdo cabe no container → fica totalmente dentro; se é maior (zoom)
  // → o container fica sempre coberto pelo conteúdo (sem espaço vazio além dele).
  function clampPan(cy) {
    var container = cy.container();
    if (!container) return;
    var eles = cy.elements();
    if (eles.length === 0) return;
    var w = container.clientWidth, h = container.clientHeight;
    var bb = eles.boundingBox();      // caixa do conteúdo em coords do modelo
    var z = cy.zoom(), p = cy.pan();
    // extents renderizados: xr = modelo*z + pan.
    //   lo = pan que encosta a borda ESQUERDA do conteúdo na esquerda do container
    //   hi = pan que encosta a borda DIREITA  do conteúdo na direita do container
    var loX = -bb.x1 * z, hiX = w - bb.x2 * z;
    var loY = -bb.y1 * z, hiY = h - bb.y2 * z;
    // cabe (lo<=hi) → mantém dentro [lo,hi]; maior (hi<lo) → cobre o viewport [hi,lo].
    var nx = Math.min(Math.max(p.x, Math.min(loX, hiX)), Math.max(loX, hiX));
    var ny = Math.min(Math.max(p.y, Math.min(loY, hiY)), Math.max(loY, hiY));
    if (Math.abs(nx - p.x) > 0.5 || Math.abs(ny - p.y) > 0.5) cy.pan({ x: nx, y: ny });
  }

  // Agenda o clamp num requestAnimationFrame — desacopla do evento 'pan' (a própria
  // `cy.pan` dispara 'pan' de novo; fazer isso síncrono re-entra e congela). O
  // guard `_faClampRaf` garante um clamp por frame; converge em 1–2 frames.
  function scheduleClamp(cy) {
    if (cy._faClampRaf) return;
    cy._faClampRaf = requestAnimationFrame(function () {
      cy._faClampRaf = null;
      clampPan(cy);
    });
  }

  // Aviso estilo mapa: aparece ao rolar sem Shift sobre o diagrama e some 3,5s
  // depois de parar de rolar. Renova o timer a cada rolagem sem Shift.
  var _zoomHintTimer = null;
  function showZoomHint() {
    var el = document.getElementById("fa-zoom-hint");
    if (!el) return;
    el.style.display = "block";
    void el.offsetWidth;          // força reflow p/ a transição de opacidade valer
    el.style.opacity = "1";
    if (_zoomHintTimer) clearTimeout(_zoomHintTimer);
    _zoomHintTimer = setTimeout(function () {
      el.style.opacity = "0";
      setTimeout(function () { if (el.style.opacity === "0") el.style.display = "none"; }, 350);
    }, 3500);
  }

  function wire(cy) {
    if (cy._faWired) return;
    cy._faWired = true;
    // cy NOVO (re-render / navegação SPA que recria o diagrama): começa com estado
    // limpo — esconde overlays que possam ter ficado presos abertos no cy anterior.
    hide("fa-node-toolbar"); hide("fa-inline-editor"); hide("fa-tempo-editor");

    var hideTimer = null;
    var cancelHide = function () { if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; } };
    var scheduleHide = function () {
      cancelHide();
      hideTimer = setTimeout(function () { hide("fa-node-toolbar"); }, 350);
    };

    // Hover no balão → seleciona + mostra a toolbar ancorada nele (sem clique).
    // NÃO esconde o editor inline aqui: se estiver aberto, deve sobreviver ao
    // mouse passar por cima dos balões enquanto o usuário digita.
    cy.on("mouseover", "node", function (evt) {
      // Durante a edição inline (ou na janela do balão recém-criado, `cy._faLockSel`),
      // NÃO trocar a seleção pelo balão sob o mouse — senão passar o mouse por cima
      // faz o Enter/salvar gravar no balão errado. Para recuperar a toolbar durante
      // a edição, basta UM TOQUE em qualquer balão (fecha o editor — ver o tap abaixo).
      // Só bloqueia a troca de seleção quando o usuário está DE FATO editando —
      // i.e., o input inline tem o foco (ou a trava curta `_faLockSel` do balão
      // recém-aberto). Antes bastava o editor estar `display:block`; se ele ficasse
      // preso aberto/invisível (fechamento perdido num re-render), a toolbar sumia
      // PERMANENTEMENTE e só voltava com reload. Agora, editor preso sem foco não
      // mata mais o hover.
      var edI = document.getElementById("fa-inline-editor");
      var digitando = edI && edI.style.display !== "none" &&
          document.activeElement && document.activeElement.id === "fa-inline-text";
      if (digitando || cy._faLockSel) return;
      cancelHide();
      cy._faActive = evt.target;          // nó ativo (sob o mouse) p/ toolbar e editor
      setSelecionado(evt.target.id());
      place(evt.target, cy);
    });
    // Sai do balão → agenda esconder (cancelado se entrar na própria toolbar).
    cy.on("mouseout", "node", scheduleHide);

    // Duplo clique no balão → editar texto. Detecção manual (dois taps no mesmo
    // nó em < 350ms) para não depender do evento `dbltap` do cytoscape. Reusa o
    // fluxo do ✎: o clique no botão abre o editor (Python) e o posiciona (JS).
    var lastTap = { id: null, t: 0 };
    cy.on("tap", "node", function (evt) {
      // Editor inline aberto → um toque em qualquer balão CONFIRMA e fecha (a seleção
      // ainda é o balão em edição, então salva no certo). Recuperação simples do
      // estado de edição sem precisar do Esc; não abre novo editor neste toque.
      var ed = document.getElementById("fa-inline-editor");
      if (ed && ed.style.display !== "none") {
        var ok = document.getElementById("fa-inline-ok");
        if (ok) ok.click();
        lastTap = { id: null, t: 0 };
        return;
      }
      var id = evt.target.id();
      var now = Date.now();
      if (lastTap.id === id && (now - lastTap.t) < 350) {
        lastTap = { id: null, t: 0 };
        cy._faActive = evt.target;
        setSelecionado(id);
        var btn = document.getElementById("fa-tb-editar");
        if (btn) btn.click();
      } else {
        lastTap = { id: id, t: now };
      }
    });

    // Manter a toolbar aberta enquanto o mouse estiver sobre ela.
    var tb = document.getElementById("fa-node-toolbar");
    if (tb) {
      tb.addEventListener("mouseenter", cancelHide);
      tb.addEventListener("mouseleave", scheduleHide);
    }

    // Editar texto (✎): ancora o editor inline sobre o balão selecionado e foca
    // o input. O display=block quem liga é o callback Python; aqui só posiciona.
    var btnEd = document.getElementById("fa-tb-editar");
    if (btnEd && !btnEd._faEditWired) {
      btnEd._faEditWired = true;
      btnEd.addEventListener("click", function () {
        // Trava a seleção enquanto o editor abre e o input ainda não focou (fecha o
        // "gap" em que o hover roubaria a seleção — a guarda por foco só protege
        // depois do foco). Destrava ao focar, ao exaurir, ou por segurança em 1,2s.
        cy._faLockSel = true;
        if (cy._faActive) placeInline(cy._faActive, cy);
        var t = 0;
        var focar = setInterval(function () {
          var inp = document.getElementById("fa-inline-text");
          var ed = document.getElementById("fa-inline-editor");
          if (ed && ed.style.display !== "none" && inp) {
            inp.focus(); inp.select(); clearInterval(focar); cy._faLockSel = false;
          }
          if (++t > 20) { clearInterval(focar); cy._faLockSel = false; }
        }, 50);
        setTimeout(function () { cy._faLockSel = false; }, 1200);
      });
    }

    // Editar tempo (⏱): posiciona o editor de tempo logo abaixo do balão e foca.
    var btnTempo = document.getElementById("fa-tb-tempo");
    if (btnTempo && !btnTempo._faWired) {
      btnTempo._faWired = true;
      btnTempo.addEventListener("click", function () {
        var node = cy._faActive;
        var ed = document.getElementById("fa-tempo-editor");
        if (node && ed) {
          var p = node.renderedPosition();
          var h = node.renderedHeight ? node.renderedHeight() : 58;
          ed.style.left = Math.max(0, p.x - 105) + "px";
          ed.style.top = Math.max(0, p.y + h / 2 + 6) + "px";
        }
        var t = 0;
        var focar = setInterval(function () {
          var inp = document.getElementById("fa-tempo-input");
          if (ed && ed.style.display !== "none" && inp) { inp.focus(); inp.select(); clearInterval(focar); }
          if (++t > 20) clearInterval(focar);
        }, 50);
      });
    }

    // Confirmar/cancelar a edição inline (estilo PowerPoint):
    // Enter confirma (Shift+Enter = nova linha), Esc cancela, clicar fora confirma.
    var inpEl = document.getElementById("fa-inline-text");
    var edEl = document.getElementById("fa-inline-editor");
    var okClick = function () {
      var ok = document.getElementById("fa-inline-ok");
      if (ok && edEl && edEl.style.display !== "none") ok.click();  // Python grava + fecha
    };
    if (inpEl && !inpEl._faWired) {
      inpEl._faWired = true;
      inpEl.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); okClick(); }
        else if (e.key === "Escape") { e.preventDefault(); if (edEl) edEl.style.display = "none"; }
      });
      inpEl.addEventListener("blur", okClick);  // clicar fora confirma
    }

    // Tap no fundo → esconde tudo.
    cy.on("tap", function (evt) {
      if (evt.target === cy) { hide("fa-node-toolbar"); hide("fa-inline-editor"); }
    });

    // Reancora ao mexer no viewport / arrastar (toolbar E editor, se abertos).
    var reanchor = function () {
      var node = cy._faActive;
      if (!node) return;
      if (tb && tb.style.display !== "none") place(node, cy);
      var ed = document.getElementById("fa-inline-editor");
      if (ed && ed.style.display !== "none") placeInline(node, cy);
    };
    cy.on("pan zoom", reanchor);
    cy.on("drag", "node", reanchor);
    // Limita o pan ao arrastar o fundo (e após zoom) — não deixa o diagrama sumir.
    cy.on("pan zoom", function () { scheduleClamp(cy); });

    // --- Zoom só com Shift+scroll -----------------------------------------
    cy.userZoomingEnabled(false);  // reforça, além do prop no Python
    var container = cy.container();
    // Os editores (inline/tempo) e o aviso de zoom são IRMÃOS do canvas, não filhos
    // do container do cytoscape. Se o listener ficasse só no container, rolar sobre o
    // editor aberto não daria zoom nem mostraria o aviso (bug: zoom "trava" com o
    // editor aberto). Ancorar no WRAPPER (pai comum) faz o wheel valer sobre o canvas
    // E sobre os editores/overlays.
    var wrapper = container ? container.parentElement : null;
    if (wrapper && !wrapper._faWheel) {
      wrapper._faWheel = true;
      wrapper.addEventListener("wheel", function (e) {
        if (!e.shiftKey) { showZoomHint(); return; }  // sem Shift: página rola + aviso
        e.preventDefault();                  // com Shift: zoom, sem rolar a página
        var rect = container.getBoundingClientRect();
        var pos = { x: e.clientX - rect.left, y: e.clientY - rect.top };
        var fator = e.deltaY < 0 ? 1.12 : 0.89;
        cy.zoom({ level: cy.zoom() * fator, renderedPosition: pos });
      }, { passive: false });
    }

    // Colapsar o accordion do diagrama põe o container em display:none (0px);
    // ao reexpandir o canvas do cytoscape fica em branco até um resize. O
    // ResizeObserver reajusta assim que o container volta a ter tamanho.
    if (container && window.ResizeObserver && !container._faRO) {
      container._faRO = true;
      var ro = new ResizeObserver(function () {
        if (container.offsetWidth > 0 && container.offsetHeight > 0) cy.resize();
      });
      ro.observe(container);
    }
  }

  // Guard de navegação in-app: o beforeunload NÃO dispara ao clicar num link do
  // menu (navegação SPA do Dash, sem recarregar a página). Aqui interceptamos o
  // clique num link que sai da análise enquanto há alterações não salvas
  // (`window.__faDirty`, setado pelo callback do beforeunload) e pedimos confirmação.
  // Registrado uma vez, no document (o menu vive fora da página).
  if (!window.__faNavGuard) {
    window.__faNavGuard = true;
    document.addEventListener("click", function (e) {
      if (!window.__faDirty) return;
      if (location.pathname.indexOf("/analise-de-falhas/ishikawa") === -1) return;
      var a = e.target.closest ? e.target.closest("a[href]") : null;
      if (!a) return;
      var href = a.getAttribute("href") || "";
      if (!href || href.charAt(0) === "#" || href.indexOf("javascript") === 0) return;
      if (a.target === "_blank") return;
      if (href.indexOf("/analise-de-falhas/ishikawa") !== -1) return;  // continua na página
      if (window.confirm("Há alterações não salvas nesta análise.\n\nSair sem salvar? As mudanças serão perdidas.")) {
        window.onbeforeunload = null;  // já confirmou aqui — não perguntar de novo se for reload
      } else {
        e.preventDefault();
        e.stopImmediatePropagation();  // bloqueia o handler de rota do Dash
      }
    }, true);  // fase de captura: roda ANTES do roteador do Dash
  }

  // Guard de Voltar/Avançar do navegador (popstate). O trap empilhado no callback
  // do beforeunload faz o Back cair de volta no mesmo url; aqui pedimos confirmação.
  if (!window.__faPopGuard) {
    window.__faPopGuard = true;
    window.addEventListener("popstate", function () {
      if (!window.__faDirty) return;
      if (location.pathname.indexOf("/analise-de-falhas/ishikawa") === -1) return;
      if (window.confirm("Há alterações não salvas nesta análise.\n\nSair sem salvar? As mudanças serão perdidas.")) {
        window.__faDirty = false;
        window.onbeforeunload = null;
        history.back();  // consome a entrada real e sai de fato
      } else {
        try { history.pushState({ faTrap: 1 }, "", location.href); } catch (e) {}  // fica: re-arma
      }
    });
  }

  // Poller PERMANENTE (não para após um tempo): cada re-render/navegação SPA pode
  // criar um NOVO objeto cy do cytoscape. `wire()` é idempotente por cy (`_faWired`),
  // então re-verificar reconecta qualquer cy novo. Se parasse (como antes, após ~40s),
  // um cy criado depois ficaria sem toolbar até um reload. Custo: 1 getElementById a
  // cada 300ms — desprezível.
  setInterval(function () {
    var cy = getCy();
    if (cy) wire(cy);
  }, 300);
})();
