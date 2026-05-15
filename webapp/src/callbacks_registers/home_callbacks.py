# src/callbacks_registers/home_callbacks.py

from dash.dependencies import Input, Output, State
from dash import dcc, ctx
import dash
import plotly.graph_objects as go
import plotly.express as px
from src.config.theme_config import TEMPLATE_THEME_MINTY
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import logging

logger = logging.getLogger("home_callbacks")

# ============================================================================
# Mock — Evocon Timeline constants & helpers
# ============================================================================

EVOCON_EQUIPMENTS = [
    {"label": "LCT-08",    "id": "TRANS001", "categoria": "Transversais"},
    {"label": "LCT-16",    "id": "TRANS002", "categoria": "Transversais"},
    {"label": "LCT-2,5",   "id": "TRANS003", "categoria": "Transversais"},
    {"label": "LCL-08",    "id": "LONGI001", "categoria": "Longitudinais"},
    {"label": "LCL-4,5",   "id": "LONGI002", "categoria": "Longitudinais"},
    {"label": "PRENSA-01", "id": "PRENS001", "categoria": "Prensas"},
    {"label": "PRENSA-02", "id": "PRENS002", "categoria": "Prensas"},
]

EVOCON_PALETTE = {
    "producao":     "#198754",
    "avaria":       "#dc3545",
    "setup":        "#ffc107",
    "logistica":    "#fd7e14",
    "microparada":  "#ffc107",
    "refeicao":     "#adb5bd",
    "mtto_auto":    "#6c757d",
    "processo":     "#e85d04",
}

EVOCON_CAUSAS = {
    "producao":    [{"cod": "—",    "desc": "Produção em curso"}],
    "avaria":      [
        {"cod": "201",  "desc": "Paradas por quebra/falhas"},
        {"cod": "202",  "desc": "Quebra matriz/facas"},
        {"cod": "S201", "desc": "Avaria mecânica"},
    ],
    "setup":       [
        {"cod": "301",  "desc": "Troca de referência e bobina"},
        {"cod": "302",  "desc": "Troca de referência"},
        {"cod": "303",  "desc": "Set up bobina"},
    ],
    "logistica":   [
        {"cod": "417",  "desc": "Fracionamento"},
        {"cod": "408",  "desc": "Troca de paletes"},
        {"cod": "404",  "desc": "Desabastecimento de linha"},
        {"cod": "410",  "desc": "Posto embalagem cheio"},
    ],
    "microparada": [{"cod": "504",  "desc": "Microparadas (<3min)"}],
    "refeicao":    [{"cod": "102N", "desc": "Descansos e Refeições"}],
    "mtto_auto":   [{"cod": "111N", "desc": "MTTO Planejado Autônomo"}],
    "processo":    [{"cod": "601",  "desc": "Defeitos de processo"}],
}

EVOCON_LABEL_SHORT = {
    "avaria": "Avaria", "setup": "Setup", "logistica": "Logística",
    "refeicao": "Refeição", "mtto_auto": "MTTO Aut.", "processo": "Processo",
    "microparada": "",
}

EVOCON_POOL = (
    ["producao"] * 22 + ["avaria"] * 3 + ["setup"] * 5 +
    ["logistica"] * 3 + ["microparada"] * 2 + ["refeicao"] * 1 +
    ["mtto_auto"] * 1 + ["processo"] * 1
)

EVOCON_GRANULARITIES = {
    "horas":   {"minutes": 60,    "step_min": 60},
    "dias":    {"minutes": 1440,  "step_min": 1440},
}

# Fim da base de dados mockada — não gerar eventos a partir deste instante
EVOCON_DATA_CUTOFF = datetime(2026, 5, 15, 0, 0, 0)


def _brasilia_now() -> datetime:
    """Datetime atual em horário de Brasília (UTC-3)."""
    return datetime.utcnow() - timedelta(hours=3)


def _evocon_compute_window(granularity: str, offset: int) -> tuple:
    """Calcula (t_start, t_end, label) da janela ancorada no cutoff dos dados + offset.

    Cada granularidade desloca por uma janela completa por unidade de offset.
    offset=0 → janela imediatamente anterior ao cutoff; offset=-1 → janela ainda mais antiga.
    """
    gran = EVOCON_GRANULARITIES.get(granularity, EVOCON_GRANULARITIES["horas"])
    cutoff = EVOCON_DATA_CUTOFF
    if granularity == "horas":
        anchor = (cutoff - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    else:  # dias
        anchor = (cutoff - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    delta = timedelta(minutes=gran["minutes"]) * offset
    t_start = anchor + delta
    t_end = t_start + timedelta(minutes=gran["minutes"])

    if granularity == "horas":
        label = f"{t_start.strftime('%d/%m/%Y')} — {t_start.strftime('%H:%M')} → {t_end.strftime('%H:%M')}"
    else:
        WD = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        label = f"{WD[t_start.weekday()]}, {t_start.strftime('%d/%m/%Y')}"
    return t_start, t_end, label


def _generate_day_events(day: date, eq_id: str, eq_idx: int) -> list:
    """Gera lista determinística de eventos para 1 dia × 1 equipamento, respeitando cutoff."""
    seed = int(day.strftime("%Y%m%d")) * 10 + eq_idx
    rng = np.random.default_rng(seed)
    events = []
    cursor = 0
    base_day = datetime(day.year, day.month, day.day)
    if base_day >= EVOCON_DATA_CUTOFF:
        return events
    max_minutes = 1440
    if base_day.date() == EVOCON_DATA_CUTOFF.date():
        max_minutes = int((EVOCON_DATA_CUTOFF - base_day).total_seconds() / 60)
    while cursor < max_minutes:
        status = str(rng.choice(EVOCON_POOL))
        if status == "producao":
            duration = int(rng.integers(20, 80))
        elif status == "microparada":
            duration = int(rng.integers(1, 4))
        elif status == "refeicao":
            duration = int(rng.integers(30, 60))
        elif status == "avaria":
            duration = int(rng.integers(15, 90))
        else:
            duration = int(rng.integers(5, 30))
        end = min(cursor + duration, max_minutes)
        causa = EVOCON_CAUSAS[status][int(rng.integers(0, len(EVOCON_CAUSAS[status])))]
        events.append({
            "equipment_id": eq_id,
            "start_dt": base_day + timedelta(minutes=cursor),
            "end_dt":   base_day + timedelta(minutes=end),
            "status":   status,
            "cod":      causa["cod"],
            "desc":     causa["desc"],
        })
        cursor = end
    return events


def _gather_events_window(t_start: datetime, t_end: datetime) -> pd.DataFrame:
    """Coleta eventos de todos equipamentos dentro [t_start, t_end), clampa às bordas."""
    rows = []
    day = t_start.date()
    while day <= t_end.date():
        for idx, eq in enumerate(EVOCON_EQUIPMENTS):
            for ev in _generate_day_events(day, eq["id"], idx):
                if ev["end_dt"] <= t_start or ev["start_dt"] >= t_end:
                    continue
                start = max(ev["start_dt"], t_start)
                end = min(ev["end_dt"], t_end)
                start_min = (start - t_start).total_seconds() / 60
                dur_min = (end - start).total_seconds() / 60
                if dur_min <= 0:
                    continue
                rows.append({
                    "label_eq": eq["label"],
                    "y":        idx,
                    "start":    start_min,
                    "duration": dur_min,
                    "status":   ev["status"],
                    "color":    EVOCON_PALETTE[ev["status"]],
                    "pattern":  "/" if ev["status"] == "setup" else "",
                    "cod":      ev["cod"],
                    "desc":     ev["desc"],
                })
        day += timedelta(days=1)
    return pd.DataFrame(rows)


def _evocon_xaxis_ticks(granularity: str, t_start: datetime, window_min: float):
    """Retorna (tickvals, ticktext) por granularidade."""
    if granularity == "horas":
        return [0, 15, 30, 45, 60], ["", ":15", ":30", ":45", ""]
    vals = [h * 60 for h in range(0, 25, 3)]
    labels = [f"{h:02d}h" for h in range(0, 25, 3)]
    labels[0] = ""; labels[-1] = ""
    return vals, labels


def _label_threshold_for(granularity: str) -> float:
    """Duração mínima (em min) para mostrar texto inside-bar — escala com janela."""
    return {"horas": 5, "dias": 60}.get(granularity, 5)

def register_home_callbacks(app):
    """Callbacks para a página home"""
    
    # ========================================
    # CALLBACK: Gráfico OEE 24h
    # ========================================
    @app.callback(
        [
            Output("graph-home-oee", "figure"),
            Output("graph-home-oee", "style")
        ],
        [
            Input("interval-component", "n_intervals")
        ]
    )
    def update_home_oee_graph(n_intervals):
        """
        Gráfico de OEE simplificado para home.
        Retorna figura E style para evitar flash branco.
        """
        template = TEMPLATE_THEME_MINTY  # Tema fixo em Minty (claro)
        
        # Style visível (gráfico pronto)
        visible_style = {"visibility": "visible", "height": "250px"}
        
        try:
            # ========================================
            # DADOS MOCKADOS (SUBSTITUIR POR DADOS REAIS)
            # ========================================
            # TODO: Buscar dados reais do banco
            hours = pd.date_range(end=datetime.now(), periods=24, freq='H')
            oee_values = [75 + (i % 10) * 2 for i in range(24)]
            
            # ========================================
            # CRIA FIGURA
            # ========================================
            fig = go.Figure()
            
            # Linha de OEE
            fig.add_trace(go.Scatter(
                x=hours,
                y=oee_values,
                mode='lines',
                name='OEE',
                line=dict(color='#28a745', width=3),
                fill='tozeroy',
                fillcolor='rgba(40, 167, 69, 0.2)',
                hovertemplate='<b>%{x|%d/%m %H:%M}</b><br>OEE: %{y:.1f}%<extra></extra>'
            ))
            
            # Linha de meta (85%)
            fig.add_hline(
                y=85, 
                line_dash="dash", 
                line_color="red", 
                opacity=0.5,
                annotation_text="Meta: 85%",
                annotation_position="right"
            )
            
            # Layout
            fig.update_layout(
                template=template,
                margin=dict(l=40, r=20, t=20, b=40),
                xaxis_title="",
                yaxis_title="OEE (%)",
                showlegend=False,
                hovermode='x unified',
                yaxis=dict(range=[0, 100]),  # OEE sempre 0-100%
            )
            
            logger.debug(f"[HOME_OEE] Gráfico gerado com {len(hours)} pontos")
            return fig, visible_style
            
        except Exception as e:
            logger.error(f"[HOME_OEE] Erro ao gerar gráfico: {e}")
            
            # Figura de erro
            error_fig = go.Figure()
            error_fig.add_annotation(
                text=f"Erro ao carregar dados<br>{str(e)}",
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(size=14, color="red")
            )
            error_fig.update_layout(
                template=template,
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                margin=dict(l=0, r=0, t=0, b=0)
            )
            
            return error_fig, visible_style
    
    # =======================================
    # CALLBACK: Gráfico Energia
    # ======================================= 
    @app.callback(
        [
            Output("graph-home-energy", "figure"),
            Output("graph-home-energy", "style")
        ],
        [
            Input("interval-component", "n_intervals")
        ]
    )
    def update_home_energy_graph(n_intervals):
        """
        Gráfico de energia simplificado para home.
        Retorna figura E style para evitar flash branco.
        """
        template = TEMPLATE_THEME_MINTY  # Tema fixo em Minty (claro)
        
        # Style visível (gráfico pronto)
        visible_style = {"visibility": "visible", "height": "250px"}
        
        try:
            # ========================================
            # DADOS MOCKADOS (SUBSTITUIR POR DADOS REAIS)
            # ========================================
            # TODO: Buscar dados reais do banco
            hours = pd.date_range(end=datetime.now(), periods=24, freq='H')
            consumption = [1000 + (i % 6) * 50 for i in range(24)]
            
            # ========================================
            # CRIA FIGURA
            # ========================================
            fig = go.Figure()
            
            # Barras de consumo
            fig.add_trace(go.Bar(
                x=hours,
                y=consumption,
                name='Consumo',
                marker_color='#ffc107',
                hovertemplate='<b>%{x|%d/%m %H:%M}</b><br>Consumo: %{y:.0f} kWh<extra></extra>'
            ))
            
            # Linha de média
            avg_consumption = sum(consumption) / len(consumption)
            fig.add_hline(
                y=avg_consumption,
                line_dash="dash",
                line_color="orange",
                opacity=0.5,
                annotation_text=f"Média: {avg_consumption:.0f} kWh",
                annotation_position="right"
            )
            
            # Layout
            fig.update_layout(
                template=template,
                margin=dict(l=40, r=20, t=20, b=40),
                xaxis_title="",
                yaxis_title="Consumo (kWh)",
                showlegend=False,
                hovermode='x unified',
                bargap=0.2,
            )
            
            logger.debug(f"[HOME_ENERGY] Gráfico gerado com {len(hours)} pontos")
            return fig, visible_style
            
        except Exception as e:
            logger.error(f"[HOME_ENERGY] Erro ao gerar gráfico: {e}")
            
            # Figura de erro
            error_fig = go.Figure()
            error_fig.add_annotation(
                text=f"Erro ao carregar dados<br>{str(e)}",
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(size=14, color="red")
            )
            error_fig.update_layout(
                template=template,
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                margin=dict(l=0, r=0, t=0, b=0)
            )
            
            return error_fig, visible_style
    
    # ========================================
    # CALLBACK: Evocon-Style Timeline (mock)
    # Multi-linha (hora), barras horizontais largura=duração,
    # padrão hashed para changeover, dots brancos, contador PCS/meta
    # ========================================
    @app.callback(
        [
            Output("graph-home-evocon-timeline", "figure"),
            Output("graph-home-evocon-timeline", "style"),
            Output("label-evocon-period", "children"),
        ],
        [
            Input("store-evocon-granularity", "data"),
            Input("store-evocon-offset", "data"),
            Input("interval-evocon-now", "n_intervals"),
        ],
    )
    def update_home_evocon_timeline(granularity, offset, n_intervals):
        granularity = granularity or "horas"
        offset = int(offset or 0)
        visible_style = {"visibility": "visible", "height": "560px"}

        try:
            t_start, t_end, period_label = _evocon_compute_window(granularity, offset)
            window_min = (t_end - t_start).total_seconds() / 60

            df = _gather_events_window(t_start, t_end)
            if df.empty:
                fig = go.Figure()
                fig.update_layout(
                    template=TEMPLATE_THEME_MINTY,
                    annotations=[dict(text="Sem eventos no período", x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False)],
                )
                return fig, visible_style, period_label

            label_thresh = _label_threshold_for(granularity)
            df["text"] = df.apply(
                lambda r: EVOCON_LABEL_SHORT.get(r["status"], "") if r["duration"] >= label_thresh else "",
                axis=1,
            )

            fig = go.Figure()

            fig.add_trace(go.Bar(
                y=df["y"],
                x=df["duration"],
                base=df["start"],
                orientation="h",
                marker=dict(
                    color=df["color"].tolist(),
                    line=dict(width=0),
                    pattern=dict(
                        shape=df["pattern"].tolist(),
                        fgcolor="#6c757d",
                        size=6,
                        solidity=0.4,
                    ),
                ),
                text=df["text"],
                textposition="inside",
                insidetextanchor="middle",
                textfont=dict(color="white", size=11, family="Arial Black"),
                width=0.62,
                customdata=df[["label_eq", "cod", "desc", "duration"]].values,
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "<b>Cód %{customdata[1]}</b> — %{customdata[2]}<br>"
                    "Duração: %{customdata[3]:.0f} min<extra></extra>"
                ),
                showlegend=False,
            ))

            # Dots na transição (só legível em granularidade fina)
            if granularity in ("horas", "dias"):
                transitions = df[df["start"] > 0]
                if not transitions.empty:
                    fig.add_trace(go.Scatter(
                        x=transitions["start"].tolist(),
                        y=(transitions["y"] + 0.42).tolist(),
                        mode="markers",
                        marker=dict(symbol="circle", size=6, color="#495057", line=dict(color="white", width=1)),
                        hoverinfo="skip",
                        showlegend=False,
                    ))

            tickvals, ticktext = _evocon_xaxis_ticks(granularity, t_start, window_min)
            for tv in tickvals:
                if 0 < tv < window_min:
                    fig.add_shape(
                        type="line",
                        x0=tv, x1=tv,
                        y0=-0.5, y1=len(EVOCON_EQUIPMENTS) - 0.5,
                        line=dict(color="rgba(0,0,0,0.08)", width=1),
                    )

            fig.update_layout(
                template=TEMPLATE_THEME_MINTY,
                height=540,
                bargap=0.32,
                xaxis=dict(
                    range=[-window_min * 0.005, window_min * 1.005],
                    tickmode="array",
                    tickvals=tickvals,
                    ticktext=ticktext,
                    side="top",
                    showgrid=False,
                    zeroline=False,
                    tickfont=dict(size=11, color="#6c757d"),
                ),
                yaxis=dict(
                    tickmode="array",
                    tickvals=list(range(len(EVOCON_EQUIPMENTS))),
                    ticktext=[eq["label"] for eq in EVOCON_EQUIPMENTS],
                    autorange="reversed",
                    showgrid=False,
                    zeroline=False,
                    tickfont=dict(size=14, color="#212529", family="Arial Black"),
                ),
                margin=dict(l=80, r=30, t=50, b=30),
                showlegend=False,
            )

            logger.debug(f"[EVOCON_TIMELINE] gran={granularity} offset={offset} eventos={len(df)} janela={t_start}→{t_end}")
            return fig, visible_style, period_label

        except Exception as e:
            logger.exception(f"[EVOCON_TIMELINE] Erro: {e}")
            err = go.Figure()
            err.add_annotation(text=f"Erro: {e}", x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False, font=dict(color="red"))
            err.update_layout(template=TEMPLATE_THEME_MINTY)
            return err, visible_style, "—"

    # Nav callback — ◀ / Hoje / ▶
    @app.callback(
        Output("store-evocon-offset", "data"),
        [
            Input("btn-evocon-prev",  "n_clicks"),
            Input("btn-evocon-next",  "n_clicks"),
            Input("btn-evocon-today", "n_clicks"),
            Input("store-evocon-granularity", "data"),
        ],
        State("store-evocon-offset", "data"),
        prevent_initial_call=True,
    )
    def update_evocon_offset(prev, nxt, today, granularity, current):
        triggered = ctx.triggered_id
        if triggered in ("btn-evocon-today", "store-evocon-granularity"):
            return 0
        current = int(current or 0)
        if triggered == "btn-evocon-prev":
            return current - 1
        if triggered == "btn-evocon-next":
            return current + 1
        raise dash.exceptions.PreventUpdate

    # Granularity dropdown
    @app.callback(
        Output("store-evocon-granularity", "data"),
        Input("dropdown-evocon-granularity", "value"),
        prevent_initial_call=False,
    )
    def update_evocon_granularity(value):
        return value or "horas"

    # ========================================
    # CLIENTSIDE: Animação fodástica do timeline
    # Slide ◀/▶, bounce no Hoje, fade-scale no dropdown.
    # Manipula DOM direto (force reflow) pra reiniciar
    # animação mesmo quando classe não mudou.
    # ========================================
    app.clientside_callback(
        """
        function(prev_n, next_n, today_n, gran_value) {
            const ctx = dash_clientside.callback_context;
            if (!ctx.triggered || !ctx.triggered.length) {
                return window.dash_clientside.no_update;
            }
            const trig = ctx.triggered[0].prop_id.split('.')[0];
            const wrap = document.getElementById('evocon-anim-wrap');
            if (!wrap) return window.dash_clientside.no_update;

            const allClasses = [
                'evocon-slide-right',
                'evocon-slide-left',
                'evocon-bounce',
                'evocon-fade-scale',
                'evocon-glitch'
            ];
            allClasses.forEach(c => wrap.classList.remove(c));
            // Force reflow para restart de animação CSS
            void wrap.offsetWidth;

            let animClass = null;
            let btnId = null;
            if (trig === 'btn-evocon-prev') {
                animClass = 'evocon-slide-right';
                btnId = 'btn-evocon-prev';
            } else if (trig === 'btn-evocon-next') {
                animClass = 'evocon-slide-left';
                btnId = 'btn-evocon-next';
            } else if (trig === 'btn-evocon-today') {
                animClass = 'evocon-bounce';
                btnId = 'btn-evocon-today';
            } else if (trig === 'dropdown-evocon-granularity') {
                animClass = 'evocon-glitch';
            }
            if (animClass) wrap.classList.add(animClass);

            // Pulse no botão clicado
            if (btnId) {
                const btn = document.getElementById(btnId);
                if (btn) {
                    btn.classList.remove('evocon-btn-pulse');
                    void btn.offsetWidth;
                    btn.classList.add('evocon-btn-pulse');
                    setTimeout(() => btn.classList.remove('evocon-btn-pulse'), 600);
                }
            }

            // Flip 3D no label de período
            const label = document.getElementById('label-evocon-period');
            if (label) {
                label.classList.remove('evocon-label-flip');
                void label.offsetWidth;
                label.classList.add('evocon-label-flip');
                setTimeout(() => label.classList.remove('evocon-label-flip'), 650);
            }

            return window.dash_clientside.no_update;
        }
        """,
        Output("evocon-anim-dummy", "data"),
        [
            Input("btn-evocon-prev", "n_clicks"),
            Input("btn-evocon-next", "n_clicks"),
            Input("btn-evocon-today", "n_clicks"),
            Input("dropdown-evocon-granularity", "value"),
        ],
        prevent_initial_call=True,
    )

    # ========================================
    # CALLBACK: Time-Series OEE Mock (4 séries)
    # Replica padrão legado linegrapg01 + oeegraph_callback
    # ========================================
    @app.callback(
        [
            Output("graph-home-oee-mock", "figure"),
            Output("graph-home-oee-mock", "style"),
        ],
        Input("interval-component", "n_intervals"),
    )
    def update_home_oee_mock(n_intervals):
        template = TEMPLATE_THEME_MINTY
        visible_style = {"visibility": "visible", "height": "450px"}

        try:
            rng = np.random.default_rng(42)
            n_points = 96
            timestamps = pd.date_range(end=datetime.now(), periods=n_points, freq="15min")

            base = 0.82 + rng.normal(0, 0.04, n_points).cumsum() * 0.01
            base = np.clip(base, 0.55, 0.98)
            df = pd.DataFrame({
                "DateTime": timestamps,
                "OEE":    np.clip(base + rng.normal(0, 0.02, n_points), 0.5, 1.0) * 100,
                "Desemp": np.clip(base + 0.05 + rng.normal(0, 0.02, n_points), 0.5, 1.0) * 100,
                "Quali":  np.clip(base + 0.08 + rng.normal(0, 0.015, n_points), 0.5, 1.0) * 100,
                "Disp":   np.clip(base + 0.06 + rng.normal(0, 0.02, n_points), 0.5, 1.0) * 100,
            })

            fig = px.line(
                df,
                x="DateTime",
                y=["OEE", "Desemp", "Quali", "Disp"],
                title="Indicadores ao Longo do Tempo (dados mockados)",
            )
            fig.update_traces(hovertemplate="<b>%{x|%d/%m %H:%M}</b><br>%{y:.1f}%<extra>%{fullData.name}</extra>")
            fig.add_hline(
                y=85,
                line_dash="dash",
                line_color="red",
                opacity=0.4,
                annotation_text="Meta OEE: 85%",
                annotation_position="top right",
            )
            fig.update_layout(
                template=template,
                xaxis_title="Data e Hora",
                yaxis_title="Indicadores (%)",
                margin=dict(l=40, r=10, t=40, b=40),
                xaxis=dict(tickfont=dict(size=8), nticks=10),
                yaxis=dict(tickfont=dict(size=8), range=[50, 105]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=9)),
                hovermode="x unified",
            )
            logger.debug(f"[HOME_OEE_MOCK] Gerado {n_points} pontos × 4 séries")
            return fig, visible_style

        except Exception as e:
            logger.error(f"[HOME_OEE_MOCK] Erro: {e}")
            err_fig = px.line(title=f"Erro ao gerar mock: {e}")
            err_fig.update_layout(template=template)
            return err_fig, visible_style

    @app.callback(
        Output("download-home-oee-mock-excel", "data"),
        Input("btn-export-home-oee-mock", "n_clicks"),
        State("graph-home-oee-mock", "figure"),
        prevent_initial_call=True,
    )
    def export_home_oee_mock(n_clicks, figure):
        if not figure or "data" not in figure:
            raise dash.exceptions.PreventUpdate
        rows = []
        for trace in figure["data"]:
            name = trace.get("name", "serie")
            for x, y in zip(trace.get("x", []), trace.get("y", [])):
                rows.append({"DateTime": x, "Serie": name, "Valor": y})
        df = pd.DataFrame(rows)
        return dcc.send_data_frame(df.to_excel, "home_oee_mock.xlsx", sheet_name="Dados", index=False)

    # ========================================
    # CALLBACK: Atualizar valores dos cards
    # ========================================
    @app.callback(
        [
            Output("home-oee-value", "children"),
            Output("home-power-value", "children"),
            Output("home-alarms-count", "children"),
            Output("home-temp-value", "children"),
        ],
        Input("interval-component", "n_intervals")
    )
    def update_home_cards(n_intervals):
        """
        Atualiza valores dos cards de status.
        TODO: Buscar dados reais do banco.
        """
        # Dados mockados - substituir por dados reais
        oee = "85.2%"
        power = "1.245 kW"
        alarms = "3"
        temp = "72.5°C"
        
        return oee, power, alarms, temp