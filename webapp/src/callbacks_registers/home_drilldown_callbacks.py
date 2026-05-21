"""POC drilldown bar chart: anos -> meses -> dias -> tabela paradas. Mock data.

Usa pattern matching IDs ({"type": "drill-bar", "level": ...}) pra evitar erro
'nonexistent object' do Dash quando graphs dos níveis 'meses'/'dias' ainda não
foram renderizados.
"""

import random
import calendar

import dash
from dash import html, dcc, dash_table, no_update, ALL
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objects as go


MESES_PT = [
    "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
]

EQUIPAMENTOS = ["LCT-08", "LCT-16", "LCL-08", "PRENSA-01", "PRENSA-02"]
CAUSAS = [
    "Avaria mecânica",
    "Avaria elétrica",
    "Falta de material",
    "Setup",
    "Manutenção corretiva",
    "Quebra de ferramenta",
    "Ajuste de processo",
]


def _seed(*parts):
    return sum(hash(str(p)) % 100_000 for p in parts)


def _mock_paradas_por_ano():
    rng = random.Random(42)
    anos = list(range(2021, 2027))
    return anos, [rng.randint(180, 520) for _ in anos]


def _mock_paradas_por_mes(year):
    rng = random.Random(_seed("mes", year))
    return [rng.randint(8, 60) for _ in range(12)]


def _mock_paradas_por_dia(year, month):
    rng = random.Random(_seed("dia", year, month))
    n_days = calendar.monthrange(year, month)[1]
    return list(range(1, n_days + 1)), [rng.randint(0, 8) for _ in range(n_days)]


def _mock_eventos_do_dia(year, month, day):
    rng = random.Random(_seed("eventos", year, month, day))
    n = rng.randint(0, 7)
    eventos = []
    for _ in range(n):
        h = rng.randint(0, 23)
        m = rng.randint(0, 59)
        dur = rng.randint(5, 240)
        eventos.append({
            "Hora": f"{h:02d}:{m:02d}",
            "Equipamento": rng.choice(EQUIPAMENTOS),
            "Causa": rng.choice(CAUSAS),
            "Duração (min)": dur,
            "Código": rng.choice(["201", "S201", "202", "S202", "203"]),
        })
    eventos.sort(key=lambda e: e["Hora"])
    return eventos


def _fig_bar(x_labels, y_values, title, color="#0d6efd"):
    fig = go.Figure(go.Bar(
        x=x_labels,
        y=y_values,
        marker_color=color,
        text=y_values,
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>%{y} paradas<extra></extra>",
    ))
    fig.update_layout(
        title=title,
        margin=dict(l=40, r=20, t=60, b=40),
        plot_bgcolor="white",
        yaxis=dict(gridcolor="#eee", title="Paradas"),
        xaxis=dict(title=""),
        showlegend=False,
    )
    return fig


def register_home_drilldown_callbacks(app):

    @app.callback(
        Output("graph-drill-years", "figure"),
        Input("url", "pathname"),
    )
    def render_years_chart(pathname):
        if pathname not in ("/", "/home"):
            return no_update
        anos, valores = _mock_paradas_por_ano()
        return _fig_bar([str(a) for a in anos], valores, "Paradas por Ano", color="#0d6efd")

    # Click em qualquer barra: gráfico de anos (id fixo) OU gráficos dinâmicos (pattern id).
    # Pattern matching evita erro client-side 'nonexistent object' quando dynamic
    # graphs ainda não estão no DOM.
    @app.callback(
        Output("modal-drill", "is_open"),
        Output("store-drill-level", "data"),
        Output("store-drill-year", "data"),
        Output("store-drill-month", "data"),
        Output("store-drill-day", "data"),
        Input("graph-drill-years", "clickData"),
        Input({"type": "drill-bar", "level": ALL}, "clickData"),
        Input("btn-drill-back", "n_clicks"),
        Input("btn-drill-close", "n_clicks"),
        State("store-drill-level", "data"),
        State("store-drill-year", "data"),
        State("store-drill-month", "data"),
        prevent_initial_call=True,
    )
    def control_modal(yr_click, pattern_clicks, back, close, level, year, month):
        trig = dash.callback_context.triggered_id

        if trig == "btn-drill-close":
            return False, "anos", None, None, None

        if trig == "btn-drill-back":
            if level == "tabela":
                return True, "dias", year, month, None
            if level == "dias":
                return True, "meses", year, None, None
            if level == "meses":
                return False, "anos", None, None, None
            return no_update, no_update, no_update, no_update, no_update

        if trig == "graph-drill-years" and yr_click:
            picked = int(yr_click["points"][0]["x"])
            return True, "meses", picked, None, None

        # Pattern matching click — trig é dict {"type":"drill-bar","level":...}
        if isinstance(trig, dict) and trig.get("type") == "drill-bar":
            clicked_level = trig.get("level")
            ctx_triggered = dash.callback_context.triggered
            if not ctx_triggered or ctx_triggered[0].get("value") is None:
                return no_update, no_update, no_update, no_update, no_update
            click = ctx_triggered[0]["value"]
            x_val = click["points"][0]["x"]
            if clicked_level == "meses":
                return True, "dias", year, MESES_PT.index(x_val) + 1, None
            if clicked_level == "dias":
                return True, "tabela", year, month, int(x_val)

        return no_update, no_update, no_update, no_update, no_update

    @app.callback(
        Output("drill-modal-content", "children"),
        Output("drill-modal-title", "children"),
        Output("btn-drill-back", "style"),
        Input("store-drill-level", "data"),
        Input("store-drill-year", "data"),
        Input("store-drill-month", "data"),
        Input("store-drill-day", "data"),
    )
    def render_modal_content(level, year, month, day):
        show_back = {}

        if level == "meses" and year:
            valores = _mock_paradas_por_mes(year)
            fig = _fig_bar(MESES_PT, valores, f"Paradas por Mês — {year}", color="#198754")
            content = dcc.Graph(
                id={"type": "drill-bar", "level": "meses"},
                figure=fig,
                config={"displayModeBar": False},
                style={"height": "380px"},
            )
            return content, f"Detalhe {year} — clique num mês", show_back

        if level == "dias" and year and month:
            dias, valores = _mock_paradas_por_dia(year, month)
            fig = _fig_bar(
                [f"{d:02d}" for d in dias],
                valores,
                f"Paradas por Dia — {MESES_PT[month-1]}/{year}",
                color="#fd7e14",
            )
            content = dcc.Graph(
                id={"type": "drill-bar", "level": "dias"},
                figure=fig,
                config={"displayModeBar": False},
                style={"height": "380px"},
            )
            return content, f"Detalhe {MESES_PT[month-1]}/{year} — clique num dia", show_back

        if level == "tabela" and year and month and day:
            eventos = _mock_eventos_do_dia(year, month, day)

            if not eventos:
                body = dbc.Alert("Nenhuma parada registrada nesse dia.", color="success")
            else:
                body = dash_table.DataTable(
                    data=eventos,
                    columns=[{"name": k, "id": k} for k in eventos[0].keys()],
                    style_table={"overflowX": "auto"},
                    style_cell={"padding": "8px", "fontFamily": "system-ui", "fontSize": "13px"},
                    style_header={
                        "backgroundColor": "#f1f3f5",
                        "fontWeight": "600",
                        "borderBottom": "2px solid #dee2e6",
                    },
                    style_data_conditional=[
                        {"if": {"filter_query": "{Duração (min)} >= 120"},
                         "backgroundColor": "#fff3cd"},
                        {"if": {"filter_query": "{Duração (min)} >= 180"},
                         "backgroundColor": "#f8d7da"},
                    ],
                    page_size=15,
                    sort_action="native",
                )

            titulo = f"Paradas em {day:02d}/{month:02d}/{year} ({len(eventos)} eventos)"
            return body, titulo, show_back

        return None, "", {"display": "none"}
