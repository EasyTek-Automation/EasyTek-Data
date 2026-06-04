// Modo apresentação da home: quando o usuário sai do fullscreen (Esc ou botão
// nativo do browser), desliga o present mode clicando no botão (que alterna a flag
// e para a rotação). Guard via dataset.present pra não reativar por engano.
(function () {
    function onFsChange() {
        if (!document.fullscreenElement && !document.webkitFullscreenElement) {
            var btn = document.getElementById('btn-home-present');
            if (btn && btn.dataset.present === 'true') {
                btn.click();  // dispara o clientside toggle → present=false, interval para
            }
        }
    }
    document.addEventListener('fullscreenchange', onFsChange);
    document.addEventListener('webkitfullscreenchange', onFsChange);
})();
