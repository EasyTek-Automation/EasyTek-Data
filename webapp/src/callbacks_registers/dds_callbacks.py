# src/callbacks_registers/dds_callbacks.py
#
# Callbacks do DDS (Diálogo Diário de Segurança) em tela cheia.
#
# São GLOBAIS de propósito: o overlay vive no layout principal (`index.py`), não
# numa página, porque a tecla F9 chama o guia de qualquer tela do sistema. Todos
# os componentes referenciados aqui existem em toda página — nada de Input
# apontando para um id que só nasce na Visão Geral.
#
# A pausa do carrossel da Visão Geral NÃO é feita aqui: quem cuida disso é o
# `assets/home_dds.js`, clicando no botão de pausa quando ele existe na tela.
# Fazer isso por callback exigiria um Output para um id ausente nas demais
# páginas — o que suja o console do navegador com erro a cada abertura.

from dash import Input, Output, State, ctx


def register_dds_callbacks(app):
    """Registra os callbacks globais do DDS em tela cheia."""

    # 1. Gatilho (F9 / botão "DDS") e "X" alternam o overlay.
    @app.callback(
        Output("store-home-dds", "data"),
        Input("btn-dds-trigger", "n_clicks"),
        Input("btn-home-dds-close", "n_clicks"),
        State("store-home-dds", "data"),
        prevent_initial_call=True,
    )
    def toggle_dds(_abre, _fecha, aberto):
        if ctx.triggered_id == "btn-home-dds-close":
            return False              # o "X" só fecha
        return not bool(aberto)       # o gatilho alterna

    # 2. Estado → classe do overlay, marca no body e nos botões (lidas pelo JS).
    app.clientside_callback(
        """
        function(aberto) {
            const ov = document.getElementById('home-dds-overlay');
            if (ov) { ov.classList.toggle('open', !!aberto); }
            document.body.classList.toggle('home-dds-open', !!aberto);
            // O botão visível da Visão Geral (quando estamos nela) espelha o estado.
            const btn = document.getElementById('btn-home-dds');
            if (btn) { btn.dataset.dds = aberto ? 'true' : 'false'; }
            const trig = document.getElementById('btn-dds-trigger');
            if (trig) { trig.dataset.dds = aberto ? 'true' : 'false'; }
            return aberto ? 'home-dds-overlay open' : 'home-dds-overlay';
        }
        """,
        Output("home-dds-overlay", "className"),
        Input("store-home-dds", "data"),
        prevent_initial_call=True,
    )

    # 3. Ao abrir, busca no banco os dias sem acidente, o recorde e o ritmo.
    #    Recalculado a cada abertura — um telão ligado há dias não pode exibir a
    #    contagem de ontem.
    @app.callback(
        Output("store-dds-cfg", "data"),
        Input("store-home-dds", "data"),
        prevent_initial_call=True,
    )
    def carregar_dds_cfg(aberto):
        from dash import no_update
        if not aberto:
            return no_update
        from src.utils import dds_data
        recorde, batendo = dds_data.recorde_dias()
        return {"dias": dds_data.dias_sem_acidente(),
                "recorde": recorde,
                "batendo_recorde": batendo,
                "passos": dds_data.passos_minutos()}

    # 4. Config + abertura → liga/desliga o motor (cronômetro, passo da vez, arte
    #    viva). Roda no navegador: contar de 1 em 1 segundo não vai ao servidor.
    app.clientside_callback(
        """
        function(cfg, aberto) {
            if (window.DDS) {
                if (cfg) { window.DDS.configurar(cfg); }
                if (aberto) { window.DDS.iniciar(); } else { window.DDS.parar(); }
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output("home-dds-art", "data-motor"),
        Input("store-dds-cfg", "data"),
        Input("store-home-dds", "data"),
        prevent_initial_call=True,
    )
