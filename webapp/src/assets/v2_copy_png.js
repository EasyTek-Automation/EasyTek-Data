/* v2_copy_png.js
 * Botão flutuante "copiar PNG" em todos os gráficos da página Indicadores V2.
 *
 * Escopo: age SÓ na rota /maintenance/indicators-v2 (Dash é SPA — re-checa a cada scan).
 * Injeta um ícone (bi-clipboard) no canto superior direito de cada gráfico Plotly
 * (.js-plotly-plot), revelado no hover via CSS. Clique → Plotly.toImage → clipboard.
 *
 * Cobre gráficos dinâmicos (modais de drilldown, grid de heatmaps, abas Custo/Relatório)
 * via MutationObserver. Nos 3 cards KPI o gráfico vive dentro de um card clicável
 * (drilldown) — o clique do botão faz stopPropagation pra não abrir o modal.
 *
 * Fallback: contexto inseguro (sem https) ou browser sem ClipboardItem → baixa o PNG,
 * pra o botão nunca "não fazer nada".
 */
(function () {
    "use strict";

    var ROUTE_PREFIX = "/maintenance/indicators-v2";
    var FLASH_MS = 1200;

    // -------- estilo self-contained (injetado uma vez) --------
    function ensureStyle() {
        if (document.getElementById("v2-copy-png-style")) return;
        var css =
            ".js-plotly-plot { }" +
            ".v2-copy-btn {" +
            "  position: absolute; top: 6px; right: 6px; z-index: 20;" +
            "  width: 30px; height: 30px; padding: 0;" +
            "  display: flex; align-items: center; justify-content: center;" +
            "  border: 1px solid rgba(0,0,0,0.10); border-radius: 7px;" +
            "  background: rgba(255,255,255,0.92); color: #495057;" +
            "  cursor: pointer; opacity: 0; transform: translateY(-2px);" +
            "  transition: opacity .15s ease, transform .15s ease, background .15s ease, color .15s ease;" +
            "  box-shadow: 0 1px 4px rgba(0,0,0,0.12); font-size: 0.95rem; line-height: 1;" +
            "}" +
            ".js-plotly-plot:hover > .v2-copy-btn," +
            ".v2-copy-btn:focus-visible { opacity: 1; transform: translateY(0); }" +
            ".v2-copy-btn:hover { background: #fff; color: #0d6efd; }" +
            ".v2-copy-btn.is-ok { opacity: 1; background: #198754; color: #fff; border-color: #198754; }" +
            ".v2-copy-btn.is-dl { opacity: 1; background: #0d6efd; color: #fff; border-color: #0d6efd; }" +
            ".v2-copy-btn.is-err { opacity: 1; background: #dc3545; color: #fff; border-color: #dc3545; }" +
            ".v2-copy-toast {" +
            "  position: absolute; top: 40px; right: 6px; z-index: 20;" +
            "  background: rgba(33,37,41,0.92); color: #fff; font-size: 0.72rem;" +
            "  padding: 2px 8px; border-radius: 5px; white-space: nowrap;" +
            "  pointer-events: none; opacity: 0; transition: opacity .15s ease;" +
            "}" +
            ".v2-copy-toast.show { opacity: 1; }";
        var st = document.createElement("style");
        st.id = "v2-copy-png-style";
        st.textContent = css;
        document.head.appendChild(st);
    }

    function onRoute() {
        return (window.location.pathname || "").indexOf(ROUTE_PREFIX) === 0;
    }

    function iconClip() { return '<i class="bi bi-clipboard"></i>'; }

    function flash(btn, kind) {
        var map = {
            ok:  { cls: "is-ok",  icon: '<i class="bi bi-check-lg"></i>',   msg: "Copiado!" },
            dl:  { cls: "is-dl",  icon: '<i class="bi bi-download"></i>',   msg: "Baixado (clipboard indisponível)" },
            err: { cls: "is-err", icon: '<i class="bi bi-x-lg"></i>',        msg: "Falhou" }
        };
        var m = map[kind] || map.err;
        btn.classList.remove("is-ok", "is-dl", "is-err");
        btn.classList.add(m.cls);
        btn.innerHTML = m.icon;
        var toast = btn._toast;
        if (toast) { toast.textContent = m.msg; toast.classList.add("show"); }
        clearTimeout(btn._flashT);
        btn._flashT = setTimeout(function () {
            btn.classList.remove("is-ok", "is-dl", "is-err");
            btn.innerHTML = iconClip();
            if (toast) toast.classList.remove("show");
        }, FLASH_MS);
    }

    function downloadBlob(blob, name) {
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = name;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    }

    function copyGraph(gd, btn) {
        if (!window.Plotly || !Plotly.toImage) { flash(btn, "err"); return; }
        var fname = "indicador-" + (gd.id || "grafico") + "-" + Date.now() + ".png";
        Plotly.toImage(gd, { format: "png", scale: 2 })
            .then(function (dataUrl) { return fetch(dataUrl); })
            .then(function (r) { return r.blob(); })
            .then(function (blob) {
                var canClip = navigator.clipboard && window.ClipboardItem && window.isSecureContext;
                if (canClip) {
                    return navigator.clipboard.write([new window.ClipboardItem({ "image/png": blob })])
                        .then(function () { flash(btn, "ok"); })
                        .catch(function (e) {
                            console.warn("[v2-copy-png] clipboard falhou, baixando:", e);
                            downloadBlob(blob, fname);
                            flash(btn, "dl");
                        });
                }
                downloadBlob(blob, fname);
                flash(btn, "dl");
            })
            .catch(function (e) {
                console.error("[v2-copy-png] toImage falhou:", e);
                flash(btn, "err");
            });
    }

    function attach(gd) {
        if (!gd || gd.dataset.copyBtn === "1") return;
        // gd é o .js-plotly-plot (graph div do Plotly). Precisa ancestral posicionado.
        var cs = window.getComputedStyle(gd);
        if (cs.position === "static") gd.style.position = "relative";
        gd.dataset.copyBtn = "1";

        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "v2-copy-btn";
        btn.title = "Copiar imagem do gráfico";
        btn.setAttribute("aria-label", "Copiar imagem do gráfico");
        btn.innerHTML = iconClip();

        var toast = document.createElement("span");
        toast.className = "v2-copy-toast";
        btn._toast = toast;

        btn.addEventListener("click", function (e) {
            // Cards KPI: gráfico dentro de Div clicável (drilldown). Não deixar borbulhar.
            e.stopPropagation();
            e.preventDefault();
            copyGraph(gd, btn);
        });
        // mousedown/pointerdown também borbulham pro handler do card — bloquear.
        ["mousedown", "pointerdown"].forEach(function (ev) {
            btn.addEventListener(ev, function (e) { e.stopPropagation(); });
        });

        gd.appendChild(toast);
        gd.appendChild(btn);
    }

    function scan() {
        if (!onRoute()) return;
        ensureStyle();
        var plots = document.querySelectorAll(".js-plotly-plot");
        for (var i = 0; i < plots.length; i++) attach(plots[i]);
    }

    var rafPending = false;
    function scheduleScan() {
        if (rafPending) return;
        rafPending = true;
        window.requestAnimationFrame(function () { rafPending = false; scan(); });
    }

    function init() {
        scan();
        var observer = new MutationObserver(function () { scheduleScan(); });
        observer.observe(document.body, { childList: true, subtree: true });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
