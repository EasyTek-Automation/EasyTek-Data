/* v2_timeline_lupa.js
 * Hover magnifier sobre o gráfico de timeline (graph-home-evocon-timeline).
 * Renderiza overlay flutuante 200×130 com viewBox SVG ampliado 3x da região do cursor.
 * Tooltip Plotly nativo continua funcionando (lupa é pointer-events: none).
 */
(function () {
    "use strict";

    var GRAPH_ID = "graph-home-evocon-timeline";
    var LUPA_W = 220, LUPA_H = 140;
    var VIEW_W = 70, VIEW_H = 45;  // área original (em px svg) → zoom = LUPA_W/VIEW_W ≈ 3.1x

    var lupa = null;

    function ensureLupa() {
        if (lupa) return lupa;
        lupa = document.createElement("div");
        lupa.className = "evocon-lupa";
        lupa.innerHTML =
            '<svg xmlns="http://www.w3.org/2000/svg" width="' + LUPA_W + '" height="' + LUPA_H + '"' +
            ' preserveAspectRatio="xMidYMid slice"></svg>' +
            '<div class="evocon-lupa-crosshair"></div>';
        document.body.appendChild(lupa);
        return lupa;
    }

    function attach(graphEl) {
        if (!graphEl || graphEl.dataset.lupaAttached === "1") return;
        var svg = graphEl.querySelector("svg.main-svg");
        if (!svg) return;
        graphEl.dataset.lupaAttached = "1";

        var lupaSvg = ensureLupa().querySelector("svg");

        // clone do conteúdo SVG (uma vez no mouseenter; re-clone ao re-render)
        var lastInnerHTML = "";
        function refreshClone() {
            if (svg.innerHTML !== lastInnerHTML) {
                lupaSvg.innerHTML = svg.innerHTML;
                lastInnerHTML = svg.innerHTML;
            }
        }

        graphEl.addEventListener("mouseenter", function () {
            refreshClone();
            lupa.style.display = "block";
        });
        graphEl.addEventListener("mouseleave", function () {
            lupa.style.display = "none";
        });

        graphEl.addEventListener("mousemove", function (e) {
            var rect = svg.getBoundingClientRect();
            // Detecta se cursor está dentro da plot area; se sair (toolbar/axes), esconde
            if (e.clientX < rect.left || e.clientX > rect.right ||
                e.clientY < rect.top  || e.clientY > rect.bottom) {
                lupa.style.display = "none";
                return;
            }
            if (lupa.style.display !== "block") {
                refreshClone();
                lupa.style.display = "block";
            }

            // Posição relativa dentro do SVG
            var vbox = svg.viewBox.baseVal;
            var ratioX = vbox && vbox.width  ? vbox.width  / rect.width  : 1;
            var ratioY = vbox && vbox.height ? vbox.height / rect.height : 1;
            var xSvg = (e.clientX - rect.left) * ratioX;
            var ySvg = (e.clientY - rect.top)  * ratioY;
            // viewBox da lupa centrado no cursor
            var vbW = VIEW_W * ratioX;
            var vbH = VIEW_H * ratioY;
            lupaSvg.setAttribute("viewBox",
                (xSvg - vbW / 2) + " " + (ySvg - vbH / 2) + " " + vbW + " " + vbH);

            // Posição da lupa: offset oposto ao tooltip Plotly (que abre na direita do cursor)
            // colocamos lupa em cima-esquerda
            var lx = e.pageX - LUPA_W - 20;
            var ly = e.pageY - LUPA_H - 20;
            // Se sair da viewport esquerda, joga pra direita
            if (lx < 8) lx = e.pageX + 20;
            // Se sair da viewport top, joga pra baixo
            if (ly < window.scrollY + 8) ly = e.pageY + 20;
            lupa.style.left = lx + "px";
            lupa.style.top  = ly + "px";
        });
    }

    function scan() {
        var g = document.getElementById(GRAPH_ID);
        if (g) attach(g);
    }

    // MutationObserver — Dash re-renderiza o graph quando granularidade/nav muda
    var observer = new MutationObserver(function () {
        var g = document.getElementById(GRAPH_ID);
        if (!g) return;
        // Se foi re-renderizado, novo svg existe → reset flag pra re-attach
        if (g.dataset.lupaAttached === "1") {
            var svg = g.querySelector("svg.main-svg");
            if (svg && !svg.dataset.lupaSvg) {
                g.dataset.lupaAttached = "";
                svg.dataset.lupaSvg = "1";
            }
        }
        attach(g);
    });

    function init() {
        scan();
        observer.observe(document.body, { childList: true, subtree: true });
    }
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
