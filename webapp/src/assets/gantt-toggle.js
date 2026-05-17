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

    /* ------------------------------------------------------------------
     * Indicador de seleção (Feature F) — marca o último row clicado.
     * Sobrevive reload via localStorage; restaurado no boot.
     * ------------------------------------------------------------------ */

    var SELECTION_STORAGE_KEY = 'gantt.selection';

    function findRowAncestor(btnEl) {
        // O toggle btn fica dentro do sticky-col container, que fica dentro do row.
        // Sobe até achar um elemento cujo style.display === 'flex' E cujo parent NÃO
        // seja flex (= é o row top-level, não a sticky col interna).
        var el = btnEl;
        while (el && el !== document.body) {
            var s = el.style;
            if (s && s.display === 'flex' && s.alignItems === 'center' && s.height) {
                return el;
            }
            el = el.parentElement;
        }
        return null;
    }

    function clearSelection() {
        var prev = document.querySelectorAll('.gantt-selected');
        for (var i = 0; i < prev.length; i++) prev[i].classList.remove('gantt-selected');
    }

    function markSelection(row, idObj) {
        clearSelection();
        if (!row) return;
        row.classList.add('gantt-selected');
        try {
            localStorage.setItem(SELECTION_STORAGE_KEY, JSON.stringify({
                type: idObj.type, index: idObj.index,
            }));
        } catch (e) {}
    }

    function restoreSelection() {
        var raw;
        try { raw = localStorage.getItem(SELECTION_STORAGE_KEY); } catch (e) { return; }
        if (!raw) return;
        var saved;
        try { saved = JSON.parse(raw); } catch (e) { return; }
        if (!saved || !saved.type || !saved.index) return;
        var btnId = JSON.stringify({ index: saved.index, type: saved.type });
        var btn = document.querySelector('[id=\'' + btnId + '\']');
        if (!btn) return;
        var row = findRowAncestor(btn);
        if (row) row.classList.add('gantt-selected');
    }

    /* ------------------------------------------------------------------
     * Expand/collapse all (Feature D) — clientside porque os stores de
     * state viraram State de render_gantt; o server callback CB-04
     * ainda atualiza os stores, mas não dispara re-render.
     * ------------------------------------------------------------------ */
    function setAllWrappers(displayValue, arrowChar) {
        var wrappers = document.querySelectorAll(
            '[id*="gantt-project-rows"], [id*="gantt-category-rows"], [id*="gantt-activity-rows"]'
        );
        for (var i = 0; i < wrappers.length; i++) {
            wrappers[i].style.display = displayValue;
        }
        // Atualiza arrows dos toggles de projeto/categoria/atividade
        var btns = document.querySelectorAll(
            '[id*="btn-toggle-project"], [id*="btn-toggle-category"], [id*="btn-toggle-activity"]'
        );
        for (var j = 0; j < btns.length; j++) {
            var spans = btns[j].querySelectorAll('span');
            for (var k = 0; k < spans.length; k++) {
                var t = spans[k].textContent;
                if (t === '▼' || t === '▶') {
                    spans[k].textContent = arrowChar;
                    break;
                }
            }
        }
    }

    document.addEventListener('click', function (e) {
        var expandBtn = e.target.closest('#btn-expand-all');
        if (expandBtn) {
            setAllWrappers('block', '▼');
            return;
        }
        var collapseBtn = e.target.closest('#btn-collapse-all');
        if (collapseBtn) {
            setAllWrappers('none', '▶');
            return;
        }
        var btn = findToggleButton(e.target);
        if (!btn) return;
        var parsed = parsePatternId(btn.id);
        if (!parsed) return;
        var wrapperType = WRAPPER_BY_BTN[parsed.type];
        if (!wrapperType) return;

        // Seleção (Feature F) — SEMPRE marca o row, mesmo quando não há
        // wrapper de expansão (atividade sem atribuições não tem
        // gantt-activity-rows no DOM, mas a linha ainda pode ser selecionada).
        markSelection(findRowAncestor(btn), parsed);

        // Expansão/colapso (Feature D) — só roda se o wrapper existir.
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

    // Restaura seleção no carregamento — espera o Gantt render terminar (até 5s
    // de tentativas com backoff curto, suficiente para overcoming load_gantt_data).
    function tryRestore(attemptsLeft) {
        if (attemptsLeft <= 0) return;
        var hasButtons = document.querySelector('[id*="btn-toggle-project"]');
        if (hasButtons) {
            restoreSelection();
            return;
        }
        setTimeout(function () { tryRestore(attemptsLeft - 1); }, 250);
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { tryRestore(20); });
    } else {
        tryRestore(20);
    }
})();
