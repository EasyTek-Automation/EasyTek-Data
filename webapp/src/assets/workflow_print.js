/**
 * Workflow PDF Export
 *
 * Estratégia: em vez de depender de @media print para esconder elementos
 * (fraco contra estilos inline e alta especificidade do Dash/Bootstrap),
 * o JS manipula o DOM diretamente antes de window.print() e restaura tudo
 * via evento afterprint.
 *
 * Responsabilidades:
 *   JS  → ocultar/mostrar elementos da aplicação, remover overflow do layout
 *   CSS → formatação visual da tabela e quebras de página (@media print)
 */
document.addEventListener('click', function (e) {
    if (!e.target.closest('#btn-export')) return;

    /* ---------------------------------------------------------------
       1. Cabeçalho de impressão
    --------------------------------------------------------------- */
    var now = new Date().toLocaleString('pt-BR', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
    });
    var header = document.createElement('div');
    header.id = 'workflow-print-header';
    header.innerHTML =
        '<div style="display:flex;justify-content:space-between;align-items:center;' +
        'border-bottom:2px solid #333;padding-bottom:8px;margin-bottom:16px;">' +
        '<strong style="font-size:16px;">AMG \u2014 Relat\u00f3rio de Demandas</strong>' +
        '<span style="font-size:12px;color:#555;">Emitido em: ' + now + '</span>' +
        '</div>';

    var page = document.querySelector('.workflow-page');
    if (page) page.insertBefore(header, page.firstChild);

    /* ---------------------------------------------------------------
       2. Ocultar elementos da aplicação (chrome)
          Guardar estilos originais para restaurar depois.
    --------------------------------------------------------------- */
    var toHide = [
        document.querySelector('.navbar'),
        document.querySelector('nav.navbar'),
        document.querySelector('#sidebar-column'),
        document.querySelector('#sidebar-overlay'),
        document.getElementById('workflow-header-row'),
        document.getElementById('alert-container-workflow'),
        document.querySelector('.workflow-filters'),
        document.getElementById('loading-overlay'),
    ];
    var origDisplays = toHide.map(function (el) {
        if (!el) return null;
        var orig = el.style.display;
        el.style.setProperty('display', 'none', 'important');
        return orig;
    });

    /* ---------------------------------------------------------------
       3. Remover overflow do content-column para evitar duplicação
          O scrollable container impresso sem correção gera páginas duplas.
    --------------------------------------------------------------- */
    var contentCol = document.getElementById('content-column');
    var origContent = {};
    if (contentCol) {
        origContent.overflow   = contentCol.style.overflow;
        origContent.height     = contentCol.style.height;
        origContent.maxHeight  = contentCol.style.maxHeight;
        origContent.width      = contentCol.style.width;
        origContent.flex       = contentCol.style.flex;
        contentCol.style.setProperty('overflow',   'visible', 'important');
        contentCol.style.setProperty('height',     'auto',    'important');
        contentCol.style.setProperty('max-height', 'none',    'important');
        contentCol.style.setProperty('width',      '100%',    'important');
        contentCol.style.setProperty('flex',       '0 0 100%','important');
    }

    /* Também garantir que a linha Bootstrap que contém sidebar + content
       não limite o layout */
    var layoutRow = contentCol && contentCol.parentElement;
    var origRowOverflow = '';
    if (layoutRow) {
        origRowOverflow = layoutRow.style.overflow;
        layoutRow.style.setProperty('overflow', 'visible', 'important');
    }

    /* ---------------------------------------------------------------
       4. Imprimir
    --------------------------------------------------------------- */
    window.print();

    /* ---------------------------------------------------------------
       5. Restaurar tudo após o diálogo de impressão fechar
    --------------------------------------------------------------- */
    window.addEventListener('afterprint', function cleanup() {
        // Remove cabeçalho
        var h = document.getElementById('workflow-print-header');
        if (h) h.parentNode.removeChild(h);

        // Restaura elementos ocultados
        toHide.forEach(function (el, i) {
            if (!el) return;
            el.style.display = origDisplays[i];
        });

        // Restaura content-column
        if (contentCol) {
            contentCol.style.overflow  = origContent.overflow;
            contentCol.style.height    = origContent.height;
            contentCol.style.maxHeight = origContent.maxHeight;
            contentCol.style.width     = origContent.width;
            contentCol.style.flex      = origContent.flex;
        }
        if (layoutRow) {
            layoutRow.style.overflow = origRowOverflow;
        }

        window.removeEventListener('afterprint', cleanup);
    });
});
