# src/callbacks_registers/home_callbacks.py
#
# Callbacks da Visão Geral da Manutenção (home):
#   1. Troca de idioma (pt/es/en) via bandeiras
#   2. Destaque da bandeira ativa
#   3. Toggle de período (mês/semana)
#   4. Render dos cards + veredito + textos i18n
#
# ⚠️ Render alimentado pelo MOCK descartável de home.py — trocar por fetch real
# (ZPP_Producao / ZPP_Paradas) quando a feature for plugada.

from dash import Input, Output, State, ALL, ctx
from src.pages.dashboards import home as home_page


def register_home_callbacks(app):
    """Registra os callbacks da home (idioma + período + render mock)."""

    # 1. Click na bandeira → store-home-lang
    @app.callback(
        Output("store-home-lang", "data"),
        Input({"type": "home-lang-btn", "lang": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def set_home_lang(_clicks):
        trig = ctx.triggered_id
        if not trig:
            return "pt"
        return trig.get("lang", "pt")

    # 2. store-home-lang → classe active nas bandeiras
    @app.callback(
        Output({"type": "home-lang-btn", "lang": ALL}, "className"),
        Input("store-home-lang", "data"),
        State({"type": "home-lang-btn", "lang": ALL}, "id"),
    )
    def highlight_home_flag(lang, ids):
        base = "v2-lang-flag"
        return [f"{base} active" if (i or {}).get("lang") == (lang or "pt") else base
                for i in ids]

    # 3. Toggle manual de granularidade → slide (0/1/2 = mês/semana/faixa)
    @app.callback(
        Output("store-home-slide", "data"),
        Input("btn-home-period-month", "n_clicks"),
        Input("btn-home-period-week", "n_clicks"),
        Input("btn-home-period-band", "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_home_period(_m, _w, _b):
        trig = ctx.triggered_id
        return {"btn-home-period-week": 1, "btn-home-period-band": 2}.get(trig, 0)

    # 3c. Slide → corte (period) + gráfico ativo (graph). Fonte única do carrossel.
    @app.callback(
        Output("store-home-period", "data"),
        Output("store-home-graph", "data"),
        Input("store-home-slide", "data"),
    )
    def map_slide(idx):
        from dash import no_update
        slide = home_page.SLIDES[(idx or 0) % len(home_page.SLIDES)]
        if slide in home_page.GRAPH_SLIDES:
            return no_update, slide          # gráfico: mantém o corte atual
        return slide, None                    # corte: arena visível

    # 3b. store-home-period → estado outline dos 3 botões (vale p/ manual E rotação automática)
    @app.callback(
        Output("btn-home-period-month", "outline"),
        Output("btn-home-period-week", "outline"),
        Output("btn-home-period-band", "outline"),
        Input("store-home-period", "data"),
    )
    def highlight_period_btn(period):
        period = period or "month"
        return (period != "month"), (period != "week"), (period != "band")

    # 4. Render: período + idioma → gráficos + veredito + textos i18n
    @app.callback(
        Output("home-charts-container", "children"),
        Output("home-verdict-container", "children"),
        Output("home-i18n-period-sub", "children"),
        Output("home-i18n-title", "children"),
        Output("home-i18n-subtitle", "children"),
        Output("home-i18n-mock-badge", "children"),
        Output("home-mock-tooltip", "children"),
        Output("home-i18n-btn-month", "children"),
        Output("home-i18n-btn-week", "children"),
        Output("home-i18n-btn-band", "children"),
        Output("home-i18n-btn-present", "children"),
        Output("store-rendered-cuts", "data"),
        Input("store-home-period", "data"),
        Input("store-home-lang", "data"),
        State("store-rendered-cuts", "data"),
    )
    def render_home(period, lang, ccount):
        period = period or "month"
        lang = lang or "pt"
        t = home_page.t
        psub = home_page.period_meta(period, lang, today=home_page._data_anchor())["psub"]
        return (
            home_page.render_duels(period, lang),
            home_page.render_verdict(period, lang),
            psub,
            t("title", lang),
            t("subtitle", lang),
            t("mock_badge", lang),
            t("mock_tooltip", lang),
            t("btn_month", lang),
            t("btn_week", lang),
            t("btn_band", lang),
            t("btn_present", lang),
            (ccount or 0) + 1,  # confirma render dos cortes
        )

    # 5. Split de paradas por duração (slider de corte + período + idioma) — sem win/lose
    @app.callback(
        Output("home-stops-split", "children"),
        Output("home-i18n-split-title", "children"),
        Output("home-i18n-split-help", "children"),
        Output("home-i18n-split-cut", "children"),
        Output("home-split-cut-val", "children"),
        Input("slider-home-cutoff", "value"),
        Input("store-home-period", "data"),
        Input("store-home-lang", "data"),
    )
    def render_stops(cutoff, period, lang):
        cutoff = cutoff or 30
        period = period or "month"
        lang = lang or "pt"
        t = home_page.t
        return (
            home_page.render_stops_split(period, lang, cutoff),
            t("split_title", lang),
            t("split_help", lang).format(c=cutoff),
            t("split_cut", lang),
            f"< {cutoff} {t('split_min', lang)}",
        )

    # 6. Modo apresentação — botão alterna fullscreen + flag (clientside; browser API)
    app.clientside_callback(
        """
        function(n, cur) {
            if (!n) { return window.dash_clientside.no_update; }
            const active = !cur;
            const btn = document.getElementById('btn-home-present');
            if (btn) { btn.dataset.present = active ? 'true' : 'false'; }
            document.body.classList.toggle('home-present-mode', active);
            if (active) {
                const el = document.documentElement;
                const req = el.requestFullscreen || el.webkitRequestFullscreen || el.msRequestFullscreen;
                if (req) { req.call(el).catch(function(){}); }
            } else if (document.fullscreenElement) {
                const ex = document.exitFullscreen || document.webkitExitFullscreen;
                if (ex) { ex.call(document); }
            }
            return active;
        }
        """,
        Output("store-home-present", "data"),
        Input("btn-home-present", "n_clicks"),
        State("store-home-present", "data"),
        prevent_initial_call=True,
    )

    # 6b. Rotação ativa só quando present ON e NÃO pausado.
    # (O timer de 15s só "vale" após o render: reset_interval reinicia em store-home-rendered.)
    @app.callback(
        Output("interval-home-present", "disabled"),
        Input("store-home-present", "data"),
        Input("store-home-paused", "data"),
    )
    def toggle_present_interval(active, paused):
        return (not bool(active)) or bool(paused)

    # 6d. Botão pausar → alterna store-home-paused
    @app.callback(
        Output("store-home-paused", "data"),
        Input("btn-home-present-pause", "n_clicks"),
        State("store-home-paused", "data"),
        prevent_initial_call=True,
    )
    def toggle_pause(_n, paused):
        return not bool(paused)

    # 6e. Ao (re)entrar no present mode: começa tocando + do slide 0 (mês)
    @app.callback(
        Output("store-home-paused", "data", allow_duplicate=True),
        Output("store-home-slide", "data", allow_duplicate=True),
        Input("store-home-present", "data"),
        prevent_initial_call=True,
    )
    def reset_on_present(_active):
        return False, 0

    # 6f. Estado pausado + idioma → ícone, rótulo e APARÊNCIA do botão (contraste)
    @app.callback(
        Output("icon-home-pause", "className"),
        Output("home-i18n-btn-pause", "children"),
        Output("btn-home-present-pause", "color"),
        Output("btn-home-present-pause", "outline"),
        Input("store-home-paused", "data"),
        Input("store-home-lang", "data"),
    )
    def pause_view(paused, lang):
        lang = lang or "pt"
        if paused:
            # pausado: amber preenchido + ícone play → contraste claro
            return "bi bi-play-fill me-1", home_page.t("btn_play", lang), "warning", False
        # tocando: escuro outline + ícone pause
        return "bi bi-pause-fill me-1", home_page.t("btn_pause", lang), "dark", True

    # 6c. Tick do Interval → avança o slide (6 posições: 3 cortes + 3 gráficos)
    @app.callback(
        Output("store-home-slide", "data", allow_duplicate=True),
        Input("interval-home-present", "n_intervals"),
        State("store-home-slide", "data"),
        prevent_initial_call=True,
    )
    def rotate_slide(_n, idx):
        return ((idx or 0) + 1) % len(home_page.SLIDES)

    # 6g. Navegação manual < > → passo no slide (inclui os gráficos)
    @app.callback(
        Output("store-home-slide", "data", allow_duplicate=True),
        Input("btn-home-present-prev", "n_clicks"),
        Input("btn-home-present-next", "n_clicks"),
        State("store-home-slide", "data"),
        prevent_initial_call=True,
    )
    def step_slide(_p, _n, idx):
        step = -1 if ctx.triggered_id == "btn-home-present-prev" else 1
        return ((idx or 0) + step) % len(home_page.SLIDES)

    # 6i-pre. Skeleton IMEDIATO ao entrar no slide de gráfico — 3 cards na MESMA posição/tamanho
    # dos originais (mesma kpi-row-v2). Substituído pelo render real (callback abaixo).
    @app.callback(
        Output("home-graph-slide", "children", allow_duplicate=True),
        Input("store-home-slide", "data"),
        prevent_initial_call=True,
    )
    def show_skeleton(idx):
        from dash import no_update
        slide = home_page.SLIDES[(idx or 0) % len(home_page.SLIDES)]
        return home_page.render_kpi_skeleton() if slide in home_page.GRAPH_SLIDES else no_update

    # 6i. Slide de gráfico ativo → renderiza o chart REAL (lento) e emite sinal de render concluído.
    @app.callback(
        Output("home-graph-slide", "children"),
        Output("store-rendered-graph", "data"),
        Input("store-home-graph", "data"),
        Input("store-home-lang", "data"),
        State("store-home-period", "data"),
        State("store-rendered-graph", "data"),
    )
    def render_graph(graph, lang, period, gcount):
        from dash import no_update
        if not graph:
            return None, no_update
        row = home_page.render_v2_kpi_row(period or "month", lang or "pt")
        return row, (gcount or 0) + 1  # confirma render do gráfico

    # 6i-2. Combinador: render concluído (gráfico OU cortes) → bump store-home-rendered
    @app.callback(
        Output("store-home-rendered", "data"),
        Input("store-rendered-graph", "data"),
        Input("store-rendered-cuts", "data"),
        State("store-home-rendered", "data"),
        prevent_initial_call=True,
    )
    def combine_render(_g, _c, rendered):
        return (rendered or 0) + 1

    # 6j. Alterna visibilidade: cortes (arena) vs slide de gráfico
    @app.callback(
        Output("home-cuts-view", "style"),
        Output("home-graph-view", "style"),
        Input("store-home-graph", "data"),
    )
    def toggle_views(graph):
        if graph:
            return {"display": "none"}, {"display": "block"}
        return {"display": "block"}, {"display": "none"}

    # 6k. Os 8s começam SÓ após o render confirmar (não na troca de slide).
    # Trocar o prop `interval` faz o dcc.Interval recriar o setInterval do zero.
    @app.callback(
        Output("interval-home-present", "interval"),
        Input("store-home-rendered", "data"),
        State("interval-home-present", "interval"),
    )
    def reset_interval(_rendered, cur):
        return 15001 if cur == 15000 else 15000

    # 6l. Transição chique de 1500ms a cada troca de slide (mascara o render real)
    app.clientside_callback(
        """
        function(slide) {
            const stage = document.getElementById('home-stage');
            const ov = document.getElementById('home-transition');
            if (stage && ov) {
                ov.classList.remove('run'); void ov.offsetWidth; ov.classList.add('run');
                stage.classList.add('transitioning');
                if (window.__homeTransT) clearTimeout(window.__homeTransT);
                window.__homeTransT = setTimeout(function(){ stage.classList.remove('transitioning'); }, 1150);
            }
            return slide;
        }
        """,
        Output("store-home-transition", "data"),
        Input("store-home-slide", "data"),
        prevent_initial_call=True,
    )

    # 6h. Barrinha de tempo regressivo (server) — remonta e DRENA os 8s a cada render confirmado.
    # Pausado → congela. Fora do present → some.
    @app.callback(
        Output("home-countdown", "children"),
        Input("store-home-rendered", "data"),
        Input("store-home-present", "data"),
        Input("store-home-paused", "data"),
    )
    def render_countdown(rendered, present, paused):
        from dash import html
        if not present:
            return None  # :empty → barra some fora do present mode
        cls = "home-countdown-fill paused" if paused else "home-countdown-fill"
        return html.Div(className=cls, key=f"{rendered}-{paused}")

    # 6h-2. Ao trocar de slide, a barra fica INDETERMINADA na hora (clientside) até o render
    # confirmar — aí o callback acima a remonta drenando. Sem contadores no servidor.
    app.clientside_callback(
        """
        function(slide) {
            const f = document.querySelector('.home-countdown-fill');
            if (f) { f.className = 'home-countdown-fill loading'; }
            return window.dash_clientside.no_update;
        }
        """,
        Output("store-home-transition", "data", allow_duplicate=True),
        Input("store-home-slide", "data"),
        prevent_initial_call=True,
    )
