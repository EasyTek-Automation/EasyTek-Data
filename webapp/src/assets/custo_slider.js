// Tooltip dos sliders de valor (custo): o slider trabalha em log10(R$); aqui convertemos
// de volta pra R$ abreviado (mesmo formato do _brl_abrev) pro usuário ver o valor ao arrastar.
window.dccFunctions = window.dccFunctions || {};
window.dccFunctions.custoRsLog = function (value) {
    if (value <= 2.0001) return "tudo";          // piso (R$100) = sem corte no low-end
    var v = Math.pow(10, value);
    if (v >= 1e6) return "R$ " + (v / 1e6).toFixed(1).replace(".", ",") + "M";
    if (v >= 1e3) return "R$ " + Math.round(v / 1e3) + "k";
    return "R$ " + Math.round(v);
};
