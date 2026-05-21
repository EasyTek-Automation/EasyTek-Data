/* v2_lang_width_sync.js
 * Sincroniza width do .v2-lang-switcher com width do ButtonGroup
 * (Atualizar+Filtros+Exportar) — garante alinhamento perfeito + card cobre
 * exatamente a largura dos botões abaixo.
 */
(function () {
    "use strict";

    function sync() {
        var btnGroup = document.querySelector('#btn-refresh-indicators-v2');
        if (!btnGroup) return;
        // pega o ButtonGroup pai (.btn-group)
        var group = btnGroup.closest('.btn-group');
        var sw = document.querySelector('.v2-lang-switcher');
        if (!group || !sw) return;
        var w = group.offsetWidth;
        if (w > 0 && Math.abs(parseFloat(sw.style.width || 0) - w) > 0.5) {
            sw.style.width = w + 'px';
            sw.style.minWidth = w + 'px';
        }
    }

    function init() {
        sync();
        // observa mudanças no DOM (Dash re-render)
        new MutationObserver(sync).observe(document.body, {
            childList: true, subtree: true,
        });
        // re-sync em resize
        window.addEventListener('resize', sync);
        // re-sync periódico curto pra cobrir Dash bootstrap (fonts loading etc)
        var n = 0;
        var iv = setInterval(function () {
            sync();
            if (++n > 20) clearInterval(iv);
        }, 200);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
