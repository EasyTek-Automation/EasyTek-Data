/**
 * Fecha o mega menu de filtros quando qualquer botão "Aplicar Filtros" é clicado.
 *
 * Abordagem client-side para evitar round-trip desnecessário ao servidor.
 * Padrão de ID: qualquer botão com id começando por "btn-apply-" fecha o mega menu.
 */
document.addEventListener('click', function (e) {
    if (!e.target.closest('[id^="btn-apply-"]')) return;

    // Pequeno delay para os callbacks Dash do botão rodarem antes de fechar o menu
    setTimeout(function () {
        var container = document.getElementById('filters-dropdown-menu');
        if (!container) return;

        var toggle = container.querySelector('[aria-expanded="true"]');
        if (toggle) toggle.click();
    }, 100);
});
