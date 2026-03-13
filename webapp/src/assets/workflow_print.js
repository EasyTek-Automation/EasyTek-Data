/**
 * Workflow PDF Export — Injeção de cabeçalho e disparo de window.print()
 *
 * Usa event delegation para capturar clique no #btn-export independente
 * de quando o Dash renderizar o botão no DOM.
 */
document.addEventListener('click', function (e) {
    if (!e.target.closest('#btn-export')) return;

    // --- Cabeçalho de impressão ---
    var header = document.createElement('div');
    header.id = 'workflow-print-header';

    var now = new Date().toLocaleString('pt-BR', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
    });

    header.innerHTML =
        '<div style="display:flex;justify-content:space-between;align-items:center;' +
        'border-bottom:2px solid #333;padding-bottom:8px;margin-bottom:16px">' +
        '<strong style="font-size:16px">AMG &mdash; Relatório de Demandas</strong>' +
        '<span style="font-size:12px;color:#555">Emitido em: ' + now + '</span>' +
        '</div>';

    var page = document.querySelector('.workflow-page');
    if (page) {
        page.insertBefore(header, page.firstChild);
    }

    window.print();

    // Remove o cabeçalho após o diálogo de impressão fechar
    window.addEventListener('afterprint', function cleanup() {
        var h = document.getElementById('workflow-print-header');
        if (h) h.parentNode.removeChild(h);
        window.removeEventListener('afterprint', cleanup);
    });
});
