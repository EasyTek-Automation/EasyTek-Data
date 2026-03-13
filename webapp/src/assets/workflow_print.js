/**
 * Workflow PDF Export — Janela de impressão isolada
 *
 * Estratégia: abre uma nova janela limpa contendo apenas os cards KPI
 * e a tabela de demandas, copiando os estilos CSS da página atual.
 * Isso elimina completamente a interferência do layout do Dash:
 * navbar, sidebar, overflow-y, duplicação de camadas, etc.
 *
 * A página original não é modificada em momento algum.
 */
document.addEventListener('click', function (e) {
    if (!e.target.closest('#btn-export')) return;

    var kpiEl   = document.getElementById('container-cards-kpi');
    var tableEl = document.getElementById('container-tabela');
    if (!kpiEl || !tableEl) return;

    var now = new Date().toLocaleString('pt-BR', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
    });

    /* ----------------------------------------------------------------
       Coletar <link rel="stylesheet"> da página atual.
       São URLs absolutas (http://localhost:8050/assets/...) que
       funcionam corretamente em qualquer janela do mesmo origin.
    ---------------------------------------------------------------- */
    var linkTags = '';
    Array.from(document.querySelectorAll('link[rel="stylesheet"]')).forEach(function (l) {
        linkTags += '<link rel="stylesheet" href="' + l.href + '">\n';
    });

    var html = [
        '<!DOCTYPE html>',
        '<html lang="pt-BR">',
        '<head>',
        '<meta charset="UTF-8">',
        '<title>AMG \u2014 Relat\u00f3rio de Demandas</title>',
        linkTags,
        '<style>',

        /* Página A4 paisagem */
        '@page { size: A4 landscape; margin: 1.5cm 1cm; }',

        /* Preservar cores exatas (evita que o browser remova backgrounds em @media print) */
        '* { -webkit-print-color-adjust: exact !important;',
        '    print-color-adjust: exact !important; }',

        /* Reset limpo */
        'html, body { margin: 0; padding: 0; background: white;',
        '  font-size: 11px; }',

        /* Cabeçalho do relatório */
        '#amg-print-header {',
        '  display: flex; justify-content: space-between; align-items: center;',
        '  border-bottom: 2px solid #333; padding-bottom: 8px; margin-bottom: 16px;',
        '}',
        '#amg-print-header strong { font-size: 15px; }',
        '#amg-print-header span   { font-size: 11px; color: #555; }',

        /* KPI cards: forçar 3 colunas (Bootstrap reseta para block em @media print) */
        '#kpi-wrap .row { display: flex !important; flex-wrap: nowrap !important; }',
        '#kpi-wrap [class*="col-"] {',
        '  width: 33.33% !important; max-width: 33.33% !important;',
        '  flex: 0 0 33.33% !important; }',
        '#kpi-wrap .card { break-inside: avoid !important; }',
        '#kpi-wrap { margin-bottom: 16px; }',

        /* Tabela: resolver overflow do wrapper responsivo */
        '.table-responsive { overflow: visible !important; }',

        /* Compactar fontes e padding */
        '.workflow-table th, .workflow-table td {',
        '  padding: 4px 8px !important; font-size: 11px !important;',
        '  vertical-align: middle; }',
        '.workflow-table th { font-size: 10px !important; }',

        /* Ocultar colunas de interação: chevron (1ª) e ações (última) */
        '.workflow-table th:first-child, .workflow-table td:first-child,',
        '.workflow-table th:last-child,  .workflow-table td:last-child {',
        '  display: none !important; }',

        /* Botões viram texto puro */
        '.workflow-table .btn {',
        '  color: inherit !important; background: none !important;',
        '  border: none !important; padding: 0 !important;',
        '  font-weight: 600; text-decoration: none !important;',
        '  box-shadow: none !important; }',

        /* Quebras de página:
           break-after:avoid nas linhas ÍMPARES (linha principal da demanda)
           → impede que a linha de detalhe fique órfã no topo da próxima página.
           break-inside:avoid na mesma linha
           → impede que o conteúdo da linha seja cortado no meio. */
        '.workflow-table tbody tr:nth-child(2n+1) {',
        '  break-after: avoid !important; page-break-after: avoid !important;',
        '  break-inside: avoid !important; page-break-inside: avoid !important; }',

        /* Painel expandido: não cortar no meio */
        '.workflow-table .collapse.show { overflow: visible !important; }',
        '.workflow-subtask-panel {',
        '  break-inside: avoid !important; page-break-inside: avoid !important; }',

        '</style>',
        '</head>',
        '<body>',

        /* Cabeçalho do relatório */
        '<div id="amg-print-header">',
        '  <strong>AMG \u2014 Relat\u00f3rio de Demandas</strong>',
        '  <span>Emitido em: ' + now + '</span>',
        '</div>',

        /* KPI cards */
        '<div id="kpi-wrap">' + kpiEl.outerHTML + '</div>',

        /* Tabela de demandas */
        tableEl.outerHTML,

        /* Aguarda estilos carregarem, então abre diálogo de impressão */
        '<script>',
        'window.addEventListener("load", function () {',
        '  setTimeout(function () { window.print(); }, 700);',
        '});',
        'window.addEventListener("afterprint", function () { window.close(); });',
        '</scr' + 'ipt>',   /* separar tag para evitar parsing prematuro */

        '</body>',
        '</html>'
    ].join('\n');

    var pw = window.open('', '_blank', 'width=1400,height=900');
    if (!pw) {
        alert('Exportação bloqueada pelo navegador. Permita pop-ups para este site e tente novamente.');
        return;
    }
    pw.document.write(html);
    pw.document.close();
});
