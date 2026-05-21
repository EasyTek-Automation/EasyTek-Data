/* v2_animated_counter.js — Sprint Visual 3
 * Anima [data-v2-anim] de 0 (ou last) → target em 3000ms (easeOutQuint).
 * Re-anima quando data-v2-anim muda, CANCELANDO animação em andamento.
 */
(function () {
    "use strict";

    // Track de animation frame ID por elemento — pra cancelar quando target muda
    var rafIds = new WeakMap();

    function animate(el, from, to) {
        // cancela anim anterior se houver
        var prev = rafIds.get(el);
        if (prev != null) cancelAnimationFrame(prev);

        var start = performance.now();
        var dur = 3000;
        var unit = el.dataset.v2Unit || "";
        var dec = parseInt(el.dataset.v2Decimals || "2", 10);

        function step(t) {
            var p = Math.min((t - start) / dur, 1);
            var ease = 1 - Math.pow(1 - p, 5);  // easeOutQuint
            var v = from + (to - from) * ease;
            el.textContent = v.toFixed(dec) + unit;
            if (p < 1) {
                rafIds.set(el, requestAnimationFrame(step));
            } else {
                rafIds.delete(el);
            }
        }
        rafIds.set(el, requestAnimationFrame(step));
    }

    function setup(el) {
        var target = parseFloat(el.dataset.v2Anim);
        if (isNaN(target)) return;
        // Skip se target == 0 e nenhuma anim anterior (sem dados ainda)
        if (target === 0 && !el.dataset.v2LastTarget) {
            el.textContent = "—";
            return;
        }
        var lastAnimated = parseFloat(el.dataset.v2LastTarget);
        // Mesmo target → skip (já animou)
        if (!isNaN(lastAnimated) && Math.abs(lastAnimated - target) < 0.001) return;
        var from = isNaN(lastAnimated) ? 0 : lastAnimated;
        el.dataset.v2LastTarget = String(target);
        animate(el, from, target);
    }

    function scan() {
        document.querySelectorAll("[data-v2-anim]").forEach(setup);
    }

    var observer = new MutationObserver(function (muts) {
        var pendingScan = false;
        muts.forEach(function (m) {
            if (m.type === "attributes" && m.attributeName === "data-v2-anim") {
                setup(m.target);
            } else if (m.type === "childList" && m.addedNodes.length) {
                for (var i = 0; i < m.addedNodes.length; i++) {
                    var n = m.addedNodes[i];
                    if (n.nodeType === 1 && (
                        (n.hasAttribute && n.hasAttribute("data-v2-anim")) ||
                        (n.querySelector && n.querySelector("[data-v2-anim]"))
                    )) {
                        pendingScan = true;
                        break;
                    }
                }
            }
        });
        if (pendingScan) scan();
    });

    function init() {
        scan();
        observer.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ["data-v2-anim"],
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
