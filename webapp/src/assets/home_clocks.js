/* home_clocks.js — relógios Brasília/Madrid no banner da home.
 * 100% client-side: usa o relógio do navegador + Intl (timeZone). Zero custo de
 * servidor (sem callback Dash / dcc.Interval). Atualiza só se os elementos existem.
 */
(function () {
    "use strict";

    function horaEm(tz) {
        return new Intl.DateTimeFormat("pt-BR", {
            timeZone: tz, hour: "2-digit", minute: "2-digit", hour12: false,
        }).format(new Date());
    }

    function tick() {
        var b = document.getElementById("clock-brt");
        var m = document.getElementById("clock-mad");
        if (!b && !m) return;                 // home não está montada — nada a fazer
        if (b) b.textContent = horaEm("America/Sao_Paulo");
        if (m) m.textContent = horaEm("Europe/Madrid");
    }

    // 1×/s mantém o minuto sempre correto; custo desprezível (só lê 2 nós quando existem)
    setInterval(tick, 1000);
    tick();
})();
