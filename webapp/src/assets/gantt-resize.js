/*
 * Gantt — drag-to-resize da coluna esquerda (Feature E).
 *
 * Mecânica:
 *   - Lê valor persistido em localStorage e aplica em --gantt-left-width antes
 *     do primeiro render do Gantt para evitar flash de 360px → tamanho salvo.
 *   - Intercepta mousedown no .gantt-resize-handle; durante o mousemove,
 *     atualiza a CSS var no <html> (afeta todas as células sticky de uma vez).
 *   - Mouseup persiste o valor final em localStorage.
 *   - Limites: 200px ≤ largura ≤ 600px (texto não some, timeline não some).
 */
(function () {
    'use strict';

    var STORAGE_KEY = 'gantt.left-width';
    var MIN_WIDTH = 200;
    var MAX_WIDTH = 800;
    var DEFAULT_WIDTH = 360;

    function clamp(v) {
        if (v < MIN_WIDTH) return MIN_WIDTH;
        if (v > MAX_WIDTH) return MAX_WIDTH;
        return v;
    }

    function applyWidth(px) {
        document.documentElement.style.setProperty('--gantt-left-width', px + 'px');
    }

    // Restaura ao carregar — antes do Gantt aparecer
    try {
        var saved = parseInt(localStorage.getItem(STORAGE_KEY), 10);
        if (!isNaN(saved)) applyWidth(clamp(saved));
    } catch (e) { /* localStorage indisponível — usa default */ }

    var dragState = null;

    function onMouseDown(e) {
        if (!e.target.classList.contains('gantt-resize-handle')) return;
        e.preventDefault();
        var current = parseInt(getComputedStyle(document.documentElement)
            .getPropertyValue('--gantt-left-width'), 10) || DEFAULT_WIDTH;
        dragState = {
            startX: e.clientX,
            startWidth: current,
            handle: e.target,
        };
        e.target.classList.add('is-dragging');
        document.body.classList.add('gantt-resizing');
    }

    function onMouseMove(e) {
        if (!dragState) return;
        var delta = e.clientX - dragState.startX;
        var newW = clamp(dragState.startWidth + delta);
        applyWidth(newW);
    }

    function onMouseUp() {
        if (!dragState) return;
        var finalW = parseInt(getComputedStyle(document.documentElement)
            .getPropertyValue('--gantt-left-width'), 10);
        try { localStorage.setItem(STORAGE_KEY, String(finalW)); } catch (e) {}
        dragState.handle.classList.remove('is-dragging');
        document.body.classList.remove('gantt-resizing');
        dragState = null;
    }

    document.addEventListener('mousedown', onMouseDown);
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
})();
