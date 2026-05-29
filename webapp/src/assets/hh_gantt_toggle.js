// HH Gantt — toggle clientside de ordens (sem callback Dash, sem re-render).
// Server renderiza TODAS as sub-linhas com display:none; JS troca a visibilidade.
(function () {
    const ICON_OPEN  = "bi bi-chevron-down hh-ord-chev-icon";
    const ICON_CLOSE = "bi bi-chevron-right hh-ord-chev-icon";

    function setRow(row, open) {
        row.style.display = open ? "block" : "none";
    }
    function setChev(chev, open) {
        const i = chev.querySelector("i");
        if (i) i.className = open ? ICON_OPEN : ICON_CLOSE;
        chev.title = open ? "Recolher técnicos" : "Expandir técnicos";
    }

    document.addEventListener("click", function (e) {
        const chev = e.target.closest(".hh-ord-chevron");
        if (chev) {
            const aufnr = chev.dataset.aufnr;
            const row = document.getElementById("hh-ord-rows-" + aufnr);
            if (!row) return;
            const open = row.style.display !== "none";
            setRow(row, !open);
            setChev(chev, !open);
            return;
        }
        if (e.target.closest("#btn-hh-expand-all")) {
            document.querySelectorAll(".hh-ord-rows").forEach(r => setRow(r, true));
            document.querySelectorAll(".hh-ord-chevron").forEach(c => setChev(c, true));
            return;
        }
        if (e.target.closest("#btn-hh-collapse-all")) {
            document.querySelectorAll(".hh-ord-rows").forEach(r => setRow(r, false));
            document.querySelectorAll(".hh-ord-chevron").forEach(c => setChev(c, false));
            return;
        }
    });
})();
