/*
 * Gantt — navegação temporal client-side (Feature H).
 *
 * Mecânica:
 *   - build_gantt_chart renderiza UMA janela LARGA (6 meses+) fixa.
 *   - Botões ◀ / Hoje / ▶ no header NÃO disparam re-render server-side.
 *   - Este script intercepta clicks e ajusta scrollLeft do container do Gantt.
 *
 * Como achar o container:
 *   - O div com overflow-x: auto que envolve as rows é a raiz com class
 *     `gantt-zebra-root` (criada em build_gantt_chart return).
 *
 * Sem persistência — scroll position é volátil entre renders. Próximo render
 * server-side (granularidade ou refresh) reseta para o ponto onde "agora" cai.
 */
(function () {
    'use strict';

    function getScroller() {
        return document.querySelector('.gantt-zebra-root');
    }

    function scrollByFraction(fraction) {
        var sc = getScroller();
        if (!sc) return;
        var step = sc.clientWidth * fraction;
        if (Math.abs(step) < 100) step = (step < 0 ? -100 : 100);
        sc.scrollBy({ left: step, behavior: 'smooth' });
    }

    function centerToday() {
        var sc = getScroller();
        if (!sc) return;
        // Procurar a now-line (linha vermelha) — primeiro elemento absoluto com
        // background-color vermelho/laranja correspondente a #E96D38 ou #DC3545.
        // Fallback: scrollLeft = scrollWidth/2 (a janela é centrada em "agora").
        var nowLines = sc.querySelectorAll('div[style*="background"][style*="position: absolute"]');
        var targetLeft = null;
        for (var i = 0; i < nowLines.length; i++) {
            var s = nowLines[i].getAttribute('style') || '';
            // Heurística — agora-line tem largura pequena, top:0, bottom:0
            if (s.indexOf('width: 2px') !== -1 || s.indexOf('width: 1px') !== -1) {
                var rect = nowLines[i].getBoundingClientRect();
                if (rect.height > sc.clientHeight * 0.3) {
                    var scRect = sc.getBoundingClientRect();
                    targetLeft = (rect.left + sc.scrollLeft) - scRect.left - (sc.clientWidth / 2);
                    break;
                }
            }
        }
        if (targetLeft === null) {
            // Fallback: janela é simétrica em torno do "agora", então metade
            targetLeft = (sc.scrollWidth - sc.clientWidth) / 2;
        }
        sc.scrollTo({ left: Math.max(0, targetLeft), behavior: 'smooth' });
    }

    document.addEventListener('click', function (e) {
        var prev = e.target.closest('#btn-hour-prev');
        if (prev) {
            e.preventDefault();
            e.stopPropagation();
            scrollByFraction(-0.5);
            return;
        }
        var next = e.target.closest('#btn-hour-next');
        if (next) {
            e.preventDefault();
            e.stopPropagation();
            scrollByFraction(0.5);
            return;
        }
        var today = e.target.closest('#btn-hour-today');
        if (today) {
            e.preventDefault();
            e.stopPropagation();
            centerToday();
            return;
        }
    }, true);

    // Centralizar no "agora" após cada render do Gantt — observa mudanças no
    // gantt-chart-container e re-centra (apenas na primeira aparição de
    // .gantt-zebra-root depois de um render).
    var lastScrollWidth = 0;
    var observer = new MutationObserver(function () {
        var sc = getScroller();
        if (!sc) return;
        if (sc.scrollWidth !== lastScrollWidth && sc.scrollWidth > 0) {
            lastScrollWidth = sc.scrollWidth;
            // Centro = scrollWidth / 2 - clientWidth / 2 (janela é centrada em "agora")
            sc.scrollLeft = Math.max(0, (sc.scrollWidth - sc.clientWidth) / 2);
        }
    });

    function startObserver() {
        var container = document.getElementById('gantt-chart-container');
        if (container) {
            observer.observe(container, { childList: true, subtree: true });
        } else {
            setTimeout(startObserver, 250);
        }
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', startObserver);
    } else {
        startObserver();
    }
})();
