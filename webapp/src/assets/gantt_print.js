/**
 * Gantt PDF Export — Janela de impressão isolada
 *
 * Clona os KPI cards e o container do Gantt, gera HTML standalone
 * print-friendly e POSTa para /gantt/export-pdf (WeasyPrint server-side).
 *
 * Baseado no padrão estabelecido em workflow_print.js.
 */
document.addEventListener('click', function (e) {
    if (!e.target.closest('#btn-export-gantt')) return;

    var kpiEl   = document.getElementById('row-gantt-kpis');
    var ganttEl = document.getElementById('gantt-chart-container');
    if (!ganttEl) {
        alert('Gantt não está carregado. Aguarde e tente novamente.');
        return;
    }

    var now = new Date().toLocaleString('pt-BR', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
    });
    var base      = window.location.origin;
    var logoAMG   = base + '/assets/LogoAMG.png';
    var logoTek   = base + '/assets/logo.png';

    /* Clonar o Gantt preservando o estado atual de expand/collapse. */
    var ganttClone = ganttEl.cloneNode(true);
    /* Tirar sticky dos painéis esquerdos (não faz sentido em PDF estático). */
    ganttClone.querySelectorAll('[style*="position: sticky"]').forEach(function (el) {
        el.style.position = 'static';
    });

    /* Coletar <link rel="stylesheet"> da página (Bootstrap + custom) */
    var linkTags = '';
    Array.from(document.querySelectorAll('link[rel="stylesheet"]')).forEach(function (l) {
        linkTags += '<link rel="stylesheet" href="' + l.href + '">\n';
    });

    var kpiHtml = kpiEl ? ('<div id="kpi-wrap">' + kpiEl.outerHTML + '</div>') : '';

    var html = [
        '<!DOCTYPE html>',
        '<html lang="pt-BR">',
        '<head>',
        '<meta charset="UTF-8">',
        '<title>AMG \u2014 Planejamento Gantt</title>',
        linkTags,
        '<style>',

        '@page { size: A4 landscape; margin: 1.5cm 1cm; }',
        '* { -webkit-print-color-adjust: exact !important;',
        '    print-color-adjust: exact !important; }',
        'html, body { margin: 0; padding: 0; background: white; width: 100%;',
        '  font-size: 11px; }',

        '#outer-layout {',
        '  width: 100%; border-spacing: 0; border-collapse: collapse; }',
        '#outer-layout > tbody > tr > td { padding: 0; vertical-align: top; }',
        '#outer-layout > tfoot > tr > td { padding: 0; }',

        '#print-root { width: 100%; padding: 0 8px; box-sizing: border-box; }',

        /* Cabeçalho */
        '#amg-print-header {',
        '  display: flex; justify-content: space-between; align-items: center;',
        '  border-bottom: 2px solid #66A593; padding-bottom: 10px; margin-bottom: 16px;',
        '}',
        '#amg-print-header .hdr-logo img {',
        '  display: block; opacity: 0.90;',
        '  height: 90px !important; width: auto !important; max-width: 340px !important; }',
        '#amg-print-header .hdr-info { text-align: right; line-height: 1.55; }',
        '#amg-print-header .hdr-title { font-size: 16px; font-weight: 700; color: #66A593; margin-bottom: 2px; }',
        '#amg-print-header .hdr-meta  { font-size: 12px; color: #555; }',

        /* Rodapé repetido via tfoot */
        '#amg-print-footer {',
        '  display: flex; align-items: center; justify-content: flex-end; gap: 6px;',
        '  padding: 4px 10px;',
        '  border-top: 1px solid #dee2e6;',
        '}',
        '#amg-print-footer .ftr-text { font-size: 0.72rem; color: #6c757d; opacity: 0.7; }',
        '#amg-print-footer .ftr-logo { height: 22px; width: auto; opacity: 0.65; }',

        /* KPI cards 4 colunas */
        '#kpi-wrap .row { display: flex !important; flex-wrap: nowrap !important; margin: 0 !important; }',
        '#kpi-wrap [class*="col-"] {',
        '  width: 25% !important; max-width: 25% !important;',
        '  flex: 0 0 25% !important; padding: 0 6px !important; }',
        '#kpi-wrap .card { break-inside: avoid !important; }',
        '#kpi-wrap { margin-bottom: 16px; }',

        /* Gantt clone: remover overflow-x pra renderizar toda a largura */
        '#gantt-wrap { margin-top: 8px; overflow: visible !important; }',
        '#gantt-wrap * { overflow: visible !important; }',

        '</style>',
        '</head>',
        '<body>',

        '<table id="outer-layout">',
        '<tfoot>',
        '<tr><td>',
        '<div id="amg-print-footer">',
        '  <span class="ftr-text">Powered by</span>',
        '  <img src="' + logoTek + '" class="ftr-logo" alt="Tekmont">',
        '</div>',
        '</td></tr>',
        '</tfoot>',

        '<tbody>',
        '<tr><td>',

        '<div id="print-root">',

        '<div id="amg-print-header">',
        '  <div class="hdr-logo"><img src="' + logoAMG + '" height="81" alt="AMG"></div>',
        '  <div class="hdr-info">',
        '    <div class="hdr-title">AMG \u2014 Planejamento Gantt</div>',
        '    <div class="hdr-meta">Emitido em: ' + now + '</div>',
        '  </div>',
        '</div>',

        kpiHtml,

        '<div id="gantt-wrap">' + ganttClone.outerHTML + '</div>',

        '</div>',

        '</td></tr>',
        '</tbody>',
        '</table>',

        '</body>',
        '</html>'
    ].join('\n');

    var btn = document.getElementById('btn-export-gantt');
    var originalHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="bi bi-hourglass-split me-1"></i>Gerando PDF...';

    fetch('/gantt/export-pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'text/html; charset=utf-8' },
        body: html,
    })
    .then(function (response) {
        if (!response.ok) {
            return response.text().then(function (msg) { throw new Error(msg); });
        }
        return response.blob();
    })
    .then(function (blob) {
        var url = URL.createObjectURL(blob);
        var a   = document.createElement('a');
        a.href  = url;
        a.download = 'planejamento-gantt.pdf';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    })
    .catch(function (err) {
        console.error('Falha ao gerar PDF:', err);
        alert('Erro ao gerar PDF: ' + err.message);
    })
    .finally(function () {
        btn.disabled    = false;
        btn.innerHTML   = originalHtml;
    });
});
