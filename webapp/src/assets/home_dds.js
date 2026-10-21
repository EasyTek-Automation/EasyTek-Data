/* ============================================================================
   DDS no telão — condutor do Diálogo Diário de Segurança
   ----------------------------------------------------------------------------
   Exibe o guia em 6 passos em tela cheia e conduz a sessão:
     · acende o card do passo da vez e apaga os demais (arte SVG viva);
     · conta o tempo de cada passo e o tempo total;
     · avisa quando o tempo do passo estoura (o card pulsa — NÃO avança sozinho);
     · mostra há quantos dias a planta está sem acidente.

   Atalhos:  F9 abre/fecha · Esc fecha · Espaço ou → avança o passo ·
             ← volta · P pausa/retoma · R recomeça

   F9 vale em QUALQUER tela do sistema: o overlay é global (vive no layout
   principal) e o atalho clica num gatilho invisível que existe em toda página.
   O F9 só não responde se a janela do navegador não estiver em foco — o
   navegador não recebe teclas de uma janela que não é a ativa.

   O cronômetro roda inteiro no navegador de propósito: contar de 1 em 1 segundo
   no servidor geraria um callback por segundo, por telão aberto.
   ========================================================================== */
(function () {
  "use strict";

  var ART_URL = "/assets/dds/dds-andragogico.svg";
  var LARANJA = "rgb(244, 125, 0)";     // card aceso (cor da arte)
  var ESCURO  = "rgb(47, 52, 54)";      // card apagado (cor da arte)

  var DDS = {
    cfg: { dias: null, passos: [1, 2, 2, 2, 2, 1] },
    passos: [1, 2, 2, 2, 2, 1],   // cópia ajustável só nesta sessão
    nomes: [],
    idx: 0,
    inicioPasso: 0,               // timestamp do início do passo atual
    inicioTotal: 0,
    pausadoEm: 0,
    rodando: false,
    tick: null,
    arte: null,                   // {cards: [], minutos: [], barras: []}
  };

  // ---------------------------------------------------------------- utilidades
  function el(id) { return document.getElementById(id); }

  function mmss(seg) {
    var neg = seg < 0;
    seg = Math.abs(Math.round(seg));
    var m = Math.floor(seg / 60), s = seg % 60;
    return (neg ? "−" : "") + m + ":" + (s < 10 ? "0" : "") + s;
  }

  function agora() { return Date.now(); }

  // ------------------------------------------------------------- arte SVG viva
  function montarArte() {
    var palco = el("home-dds-art");
    if (!palco || palco.dataset.pronto === "1") { return Promise.resolve(); }

    return fetch(ART_URL)
      .then(function (r) { return r.text(); })
      .then(function (svgTexto) {
        palco.innerHTML = svgTexto;
        var svg = palco.querySelector("svg");
        if (!svg) { return; }
        svg.removeAttribute("width");
        svg.removeAttribute("height");
        svg.classList.add("home-dds-svg");

        // Os 6 cards são os retângulos 145×335 da arte — ordenados da esquerda
        // para a direita, batem com os passos 1..6.
        var cards = Array.prototype.slice.call(svg.querySelectorAll("rect"))
          .filter(function (r) {
            return Math.round(+r.getAttribute("width")) === 145 &&
                   Math.round(+r.getAttribute("height")) === 335;
          })
          .sort(function (a, b) { return (+a.getAttribute("x")) - (+b.getAttribute("x")); });

        // Os rótulos "1 min" / "2 min" impressos na arte viram texto vivo.
        var minutos = Array.prototype.slice.call(svg.querySelectorAll("text"))
          .filter(function (t) { return /^\s*\d+\s*min\s*$/.test(t.textContent); })
          .sort(function (a, b) { return (+a.getAttribute("x")) - (+b.getAttribute("x")); });

        // Nome de cada passo: o texto em caixa alta dentro do card que não é o
        // rótulo "O QUE SE ESPERA" nem o número do passo.
        DDS.nomes = cards.map(function (c) {
          var x0 = +c.getAttribute("x"), x1 = x0 + 145;
          var achado = Array.prototype.slice.call(svg.querySelectorAll("text"))
            .filter(function (t) {
              var x = +t.getAttribute("x");
              var txt = (t.textContent || "").trim();
              return x > x0 && x < x1 && txt === txt.toUpperCase() &&
                     txt.length > 3 && txt !== "O QUE SE ESPERA" && !/\d/.test(txt);
            });
          return achado.length ? achado[0].textContent.trim() : "";
        });

        // Barra de tempo desenhada dentro de cada card, na base.
        var ns = "http://www.w3.org/2000/svg";
        var barras = cards.map(function (c, i) {
          var x = +c.getAttribute("x"), y = +c.getAttribute("y");
          var trilho = document.createElementNS(ns, "rect");
          trilho.setAttribute("x", x + 12); trilho.setAttribute("y", y + 335 - 16);
          trilho.setAttribute("width", 121); trilho.setAttribute("height", 5);
          trilho.setAttribute("rx", 2.5); trilho.setAttribute("class", "dds-trilho");
          var cheio = document.createElementNS(ns, "rect");
          cheio.setAttribute("x", x + 12); cheio.setAttribute("y", y + 335 - 16);
          cheio.setAttribute("width", 0); cheio.setAttribute("height", 5);
          cheio.setAttribute("rx", 2.5); cheio.setAttribute("class", "dds-cheio");
          svg.appendChild(trilho); svg.appendChild(cheio);
          c.setAttribute("class", "dds-card");
          c.setAttribute("data-step", i + 1);
          return cheio;
        });

        DDS.arte = { cards: cards, minutos: minutos, barras: barras, svg: svg };
        palco.dataset.pronto = "1";
      })
      .catch(function (e) { console.warn("DDS: falha ao carregar a arte", e); });
  }

  // ------------------------------------------------------------------- pintura
  function pintar() {
    var a = DDS.arte;
    var decorrido = DDS.rodando ? (agora() - DDS.inicioPasso) / 1000
                                : (DDS.pausadoEm - DDS.inicioPasso) / 1000;
    var orcamento = DDS.passos[DDS.idx] * 60;
    var restante = orcamento - decorrido;
    var estourou = restante < 0;

    if (a) {
      a.cards.forEach(function (c, i) {
        var ativo = (i === DDS.idx);
        c.setAttribute("fill", ativo ? LARANJA : ESCURO);
        c.classList.toggle("ativo", ativo);
        c.classList.toggle("concluido", i < DDS.idx);
        c.classList.toggle("estourado", ativo && estourou);
      });
      a.minutos.forEach(function (t, i) {
        var novo = DDS.passos[i] + " min";
        if (t.textContent !== novo) { t.textContent = novo; }
      });
      a.barras.forEach(function (b, i) {
        var frac = 0;
        if (i < DDS.idx) { frac = 1; }
        else if (i === DDS.idx) { frac = Math.max(0, Math.min(1, decorrido / orcamento)); }
        b.setAttribute("width", (121 * frac).toFixed(1));
        b.classList.toggle("estourado", i === DDS.idx && estourou);
      });
    }

    // Painel de condução
    var totalSeg = DDS.rodando ? (agora() - DDS.inicioTotal) / 1000
                               : (DDS.pausadoEm - DDS.inicioTotal) / 1000;
    var set = function (id, txt) { var e = el(id); if (e && e.textContent !== txt) { e.textContent = txt; } };
    set("home-dds-step-num", String(DDS.idx + 1));
    set("home-dds-step-name", DDS.nomes[DDS.idx] || "");
    set("home-dds-step-clock", mmss(restante));
    set("home-dds-step-budget", DDS.passos[DDS.idx] + " min");
    set("home-dds-total-clock", mmss(totalSeg));

    var relogio = el("home-dds-step-clock");
    if (relogio) { relogio.classList.toggle("estourado", estourou); }
    var ov = el("home-dds-overlay");
    if (ov) {
      ov.classList.toggle("dds-estourado", estourou);
      ov.classList.toggle("dds-pausado", !DDS.rodando);
    }
  }

  // -------------------------------------------------------------------- motor
  function comecarPasso(i) {
    DDS.idx = Math.max(0, Math.min(DDS.passos.length - 1, i));
    DDS.inicioPasso = agora();
    if (!DDS.rodando) { DDS.pausadoEm = DDS.inicioPasso; }
    pintar();
  }

  DDS.configurar = function (cfg) {
    cfg = cfg || {};
    DDS.cfg = cfg;
    if (Array.isArray(cfg.passos) && cfg.passos.length === 6) {
      DDS.passos = cfg.passos.slice();
    }
    var dias = el("home-dds-safe-days");
    if (dias) { dias.textContent = (cfg.dias === null || cfg.dias === undefined) ? "—" : String(cfg.dias); }

    var rec = el("home-dds-safe-record");
    if (rec) {
      if (cfg.recorde === null || cfg.recorde === undefined) {
        rec.textContent = "";
      } else if (cfg.batendo_recorde) {
        rec.textContent = "recorde sendo batido";
        rec.classList.add("batendo");
      } else {
        rec.textContent = "recorde: " + cfg.recorde;
        rec.classList.remove("batendo");
      }
    }
  };

  DDS.iniciar = function () {
    montarArte().then(function () {
      DDS.passos = (DDS.cfg.passos || DDS.passos).slice();   // volta ao padrão a cada DDS
      DDS.rodando = true;
      DDS.inicioTotal = agora();
      comecarPasso(0);
      if (DDS.tick) { clearInterval(DDS.tick); }
      DDS.tick = setInterval(pintar, 250);
    });
  };

  DDS.parar = function () {
    DDS.rodando = false;
    if (DDS.tick) { clearInterval(DDS.tick); DDS.tick = null; }
  };

  DDS.proximo = function () {
    if (DDS.idx < DDS.passos.length - 1) { comecarPasso(DDS.idx + 1); }
  };

  DDS.anterior = function () {
    if (DDS.idx > 0) { comecarPasso(DDS.idx - 1); }
  };

  DDS.pausar = function () {
    if (DDS.rodando) {
      DDS.pausadoEm = agora();
      DDS.rodando = false;
    } else {
      var parado = agora() - DDS.pausadoEm;
      DDS.inicioPasso += parado;
      DDS.inicioTotal += parado;
      DDS.rodando = true;
    }
    pintar();
  };

  DDS.reiniciar = function () {
    DDS.passos = (DDS.cfg.passos || DDS.passos).slice();
    DDS.rodando = true;
    DDS.inicioTotal = agora();
    comecarPasso(0);
  };

  // Ajuste rápido: vale só nesta condução; o padrão do banco volta no próximo DDS.
  DDS.ajustar = function (delta) {
    var novo = DDS.passos[DDS.idx] + delta;
    DDS.passos[DDS.idx] = Math.max(1, Math.min(60, novo));
    pintar();
  };

  window.DDS = DDS;

  // ------------------------------------------------------------------ atalhos
  function digitando(e) {
    if (!e) { return false; }
    var tag = (e.tagName || "").toLowerCase();
    return tag === "input" || tag === "textarea" || tag === "select" || e.isContentEditable;
  }

  function gatilho() { return el("btn-dds-trigger"); }

  function estaAberto() {
    var g = gatilho();
    return !!g && g.dataset.dds === "true";
  }

  // Pausa do carrossel da Visão Geral. Feito aqui, e não por callback, porque o
  // overlay é global: um Output para o store de pausa quebraria em toda página
  // que não tem carrossel. Só retomamos se fomos NÓS que pausamos — quem já
  // estava pausado antes do DDS continua pausado ao sair.
  var pausamosNos = false;

  function carrosselTocando() {
    var icone = el("icon-home-pause");
    return !!icone && icone.className.indexOf("pause-fill") !== -1;
  }

  function pausarCarrossel() {
    var btn = el("btn-home-present-pause");
    if (btn && carrosselTocando()) { btn.click(); pausamosNos = true; }
  }

  function retomarCarrossel() {
    var btn = el("btn-home-present-pause");
    if (btn && pausamosNos && !carrosselTocando()) { btn.click(); }
    pausamosNos = false;
  }

  function alternar() {
    var g = gatilho();
    if (!g) { return; }
    if (estaAberto()) { retomarCarrossel(); } else { pausarCarrossel(); }
    g.click();
  }

  document.addEventListener("keydown", function (ev) {
    if (!gatilho()) { return; }                  // layout ainda não montou
    if (digitando(ev.target)) { return; }        // não sequestra digitação

    if (ev.key === "F9") { ev.preventDefault(); alternar(); return; }
    if (!estaAberto()) { return; }               // os demais só valem com o DDS aberto

    if (ev.key === "Escape") { ev.preventDefault(); alternar(); }
    else if (ev.key === " " || ev.key === "Spacebar" || ev.key === "ArrowRight") {
      ev.preventDefault(); DDS.proximo();
    }
    else if (ev.key === "ArrowLeft") { ev.preventDefault(); DDS.anterior(); }
    else if (ev.key === "p" || ev.key === "P") { ev.preventDefault(); DDS.pausar(); }
    else if (ev.key === "r" || ev.key === "R") { ev.preventDefault(); DDS.reiniciar(); }
  });

  // Cliques: o botão "DDS" da Visão Geral e o "X" do overlay entram pelo mesmo
  // caminho do atalho; os demais controlam o cronômetro.
  document.addEventListener("click", function (ev) {
    var alvo = ev.target.closest && ev.target.closest("button");
    if (!alvo) { return; }
    if (alvo.id === "btn-home-dds")      { ev.preventDefault(); alternar(); return; }
    if (alvo.id === "btn-home-dds-close"){ retomarCarrossel(); return; }  // o callback fecha
    if (alvo.id === "btn-dds-mais")      { ev.preventDefault(); DDS.ajustar(+1); }
    if (alvo.id === "btn-dds-menos")     { ev.preventDefault(); DDS.ajustar(-1); }
    if (alvo.id === "btn-dds-pausa")     { ev.preventDefault(); DDS.pausar(); }
    if (alvo.id === "btn-dds-reset")     { ev.preventDefault(); DDS.reiniciar(); }
  });
})();
