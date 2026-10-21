/* Painel de contas da aba Custo: clicar FORA dele fecha o painel (e, ao fechar, o filtro é
 * aplicado pelo callback _set_contas). O clique de fora só fecha — é engolido na fase de
 * captura para não disparar o que estiver embaixo (ex.: abrir o detalhamento do gráfico).
 * Fecha clicando no próprio botão das contas, reaproveitando o caminho que já existe. */
(function () {
    function painelAberto() {
        var col = document.getElementById("custo-contas-collapse");
        return col && col.classList.contains("show") ? col : null;
    }
    function foraDoPainel(e) {
        var col = painelAberto();
        if (!col) return false;
        var btn = document.getElementById("custo-contas-toggle");
        return !(col.contains(e.target) || (btn && btn.contains(e.target)));
    }
    document.addEventListener("mousedown", function (e) {
        if (!foraDoPainel(e)) return;
        e.stopPropagation();
        e.preventDefault();
        var btn = document.getElementById("custo-contas-toggle");
        if (btn) btn.click();
        window.__custoContasFechouEm = Date.now();
    }, true);
    // engole o "click" que completa o mesmo gesto (mousedown → mouseup → click)
    document.addEventListener("click", function (e) {
        if (window.__custoContasFechouEm && Date.now() - window.__custoContasFechouEm < 600) {
            var btn = document.getElementById("custo-contas-toggle");
            if (btn && btn.contains(e.target)) return;
            e.stopPropagation();
            e.preventDefault();
            window.__custoContasFechouEm = 0;
        }
    }, true);
})();
