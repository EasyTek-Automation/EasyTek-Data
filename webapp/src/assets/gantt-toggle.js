/*
 * Gantt — toggle expand/collapse client-side (Feature D).
 *
 * Intercepta clicks em btn-toggle-{project,category,activity} via event
 * delegation e altera display + ícone do wrapper correspondente direto no
 * DOM, sem ida ao servidor. Server callbacks (gantt_callbacks.py CB-03,
 * CB-03b, CB-21) continuam atualizando store-gantt-*-state para persistência
 * em localStorage, mas render_gantt (CB-01) NÃO re-dispara — esses stores
 * são State, não Input (Feature D / Patch 1).
 */
(function () {
    'use strict';

    var WRAPPER_BY_BTN = {
        'btn-toggle-project':  'gantt-project-rows',
        'btn-toggle-category': 'gantt-category-rows',
        'btn-toggle-activity': 'gantt-activity-rows',
    };

    function parsePatternId(idStr) {
        if (!idStr || idStr.charAt(0) !== '{') return null;
        try { return JSON.parse(idStr); } catch (e) { return null; }
    }

    function findToggleButton(el) {
        // Sobe pelos elementos pais procurando um nó com id pattern-matching de toggle
        while (el && el !== document) {
            if (el.id && WRAPPER_BY_BTN[parsePatternId(el.id) ? parsePatternId(el.id).type : '']) {
                return el;
            }
            el = el.parentElement;
        }
        return null;
    }

    function flipDisplay(idObj, isExpanded) {
        var wrapperId = JSON.stringify({ index: idObj.index, type: idObj.wrapperType });
        var wrapper = document.querySelector('[id=\'' + wrapperId + '\']');
        if (wrapper) {
            wrapper.style.display = isExpanded ? 'block' : 'none';
        }
    }

    function flipIcon(btnEl, isExpanded) {
        // Procura primeiro span filho que contém ▼ ou ▶ e troca
        var spans = btnEl.querySelectorAll('span');
        for (var i = 0; i < spans.length; i++) {
            var t = spans[i].textContent;
            if (t === '▼' || t === '▶') {
                spans[i].textContent = isExpanded ? '▼' : '▶';
                return;
            }
        }
    }

    document.addEventListener('click', function (e) {
        var btn = findToggleButton(e.target);
        if (!btn) return;
        var parsed = parsePatternId(btn.id);
        if (!parsed) return;
        var wrapperType = WRAPPER_BY_BTN[parsed.type];
        if (!wrapperType) return;

        var wrapperId = JSON.stringify({ index: parsed.index, type: wrapperType });
        var wrapper = document.querySelector('[id=\'' + wrapperId + '\']');
        if (!wrapper) return;

        var wasHidden = wrapper.style.display === 'none';
        var isExpanded = wasHidden;
        flipDisplay({ wrapperType: wrapperType, index: parsed.index }, isExpanded);
        flipIcon(btn, isExpanded);
        // O server callback ainda dispara e atualiza store-gantt-*-state — apenas
        // não re-renderiza render_gantt (Input → State). Estado fica sincronizado.
    }, true);
})();
