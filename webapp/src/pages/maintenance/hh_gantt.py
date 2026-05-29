"""HH Gantt — aproveitamento hora-homem da manutenção (mock, dados reais SAP 3 meses).

Duas visualizações sobre a mesma timeline semanal (cortes 2/4h):
- Por Ordem: ordens com técnicos empilhados (planejado pálido × real preenchido).
- Por Funcionário: técnicos com seus apontamentos + fundo de ocupação (capacidade).

Dados: `utils/hh_gantt_data` (CSVs reais em `data/hh_mock/`). Sem SAP/Mongo.
SDD: `.dev-docs/projects/SapIntegration/` (feature de aproveitamento HH).
"""

from dash import html, dcc
import dash_bootstrap_components as dbc

from src.utils import hh_gantt_data as data
from src.components import hh_week_picker


def _kpi_card(label, value, sub="", color="primary"):
    return dbc.Card(dbc.CardBody([
        html.Div(value, style={"fontSize": "1.4rem", "fontWeight": "700",
                               "color": f"var(--bs-{color})", "lineHeight": "1.1"}),
        html.Div(label, style={"fontSize": "0.7rem", "fontWeight": "600",
                               "textTransform": "uppercase", "letterSpacing": "0.02em"}),
        html.Div(sub, style={"fontSize": "0.66rem", "color": "var(--bs-secondary)"}),
    ], style={"padding": "10px 12px"}), style={"flex": "1", "minWidth": "120px"})


def _toggle_btn(label, btn_id, active, icon=None):
    children = ([html.I(className=f"bi bi-{icon} me-1")] if icon else []) + [label]
    return dbc.Button(children, id=btn_id, size="sm", color="primary",
                      outline=not active, className="hh-toggle-btn")


def _filters_panel(opts):
    """Painel de filtros (colapsável). Conjunto amplo — o usuário poda o que não servir."""
    def col(label, control, width=3):
        return dbc.Col([html.Label(label, style={"fontSize": "0.7rem", "fontWeight": "600",
                                                  "marginBottom": "2px"}), control],
                       md=width, style={"marginBottom": "8px"})

    body = dbc.Row([
        col("Técnico", dcc.Dropdown(id="hh-f-tecnicos", options=opts["tecnicos"], multi=True,
                                    placeholder="todos", clearable=True)),
        col("Centro de trabalho", dcc.Dropdown(id="hh-f-centros", options=opts["centros"], multi=True,
                                               placeholder="todos")),
        col("Tipo de ordem", dcc.Dropdown(id="hh-f-tipos", options=opts["tipos"], multi=True,
                                          placeholder="todos")),
        col("Equipamento (local)", dcc.Dropdown(id="hh-f-equip", options=opts["equipamentos"], multi=True,
                                                placeholder="todos")),
        col("Nº da ordem (contém)", dbc.Input(id="hh-f-ordem", type="text", placeholder="ex: 50182",
                                              size="sm")),
        col("Faixa de aproveitamento", dcc.Dropdown(id="hh-f-bandas", multi=True, placeholder="todas",
            options=[{"label": "Dentro do plano (≤100%)", "value": "dentro"},
                     {"label": "Estouro leve (100–150%)", "value": "leve"},
                     {"label": "Estouro alto (150–300%)", "value": "alto"},
                     {"label": "Estouro extremo (>300%)", "value": "extremo"},
                     {"label": "Sem plano", "value": "sem_plano"}])),
        col("Duração mín. do apontamento (min)", dbc.Input(id="hh-f-durmin", type="number", min=0,
                                                           step=5, value=0, size="sm")),
        col("Visual", dbc.Checklist(id="hh-f-showplan",
            options=[{"label": " Mostrar faixa planejada", "value": "plan"}],
            value=["plan"], switch=True), width=3),
        col("Filtro extra", dbc.Checklist(id="hh-f-naoplan",
            options=[{"label": " Só não planejadas (sem agendamento no IW37)", "value": "naoplan"}],
            value=[], switch=True), width=3),
    ])
    actions = html.Div([
        dbc.Button([html.I(className="bi bi-funnel-fill me-1"), "Aplicar"],
                   id="btn-hh-apply-filters", size="sm", color="primary", className="me-2"),
        dbc.Button([html.I(className="bi bi-x-circle me-1"), "Limpar"],
                   id="btn-hh-clear-filters", size="sm", color="secondary", outline=True),
        html.Span(id="hh-filters-summary", style={"fontSize": "0.72rem", "color": "var(--bs-secondary)",
                                                  "marginLeft": "12px"}),
    ], style={"marginTop": "4px"})

    return dbc.Collapse(dbc.Card(dbc.CardBody([body, actions], style={"padding": "12px"}),
                                 style={"marginBottom": "12px"}),
                        id="hh-filters-collapse", is_open=False)


def layout():
    t_start, t_end = data.week_window(0)
    ds = data.get_dataset()
    dmin, dmax = ds["date_min"], ds["date_max"]
    opts = data.filter_options()

    header = html.Div([
        html.Div([
            html.H4([html.I(className="bi bi-bar-chart-steps me-2"),
                     "Aproveitamento HH — Gantt"],
                    style={"marginBottom": "2px"}),
            html.Span("BETA · dados reais do SAP (mock, 3 meses) · planejado nível-dia, real no relógio",
                      className="badge bg-warning text-dark", style={"fontSize": "0.62rem"}),
        ]),
        html.Div([
            # filtros
            dbc.Button([html.I(className="bi bi-funnel me-1"), "Filtros"],
                       id="btn-hh-filters-toggle", size="sm", color="secondary",
                       outline=True, className="me-3"),
            # toggle de view
            dbc.ButtonGroup([
                _toggle_btn("Por Ordem", "btn-hh-view-ordem", True, "list-task"),
                _toggle_btn("Por Funcionário", "btn-hh-view-func", False, "people"),
            ], className="me-3"),
            # navegação de semana
            dbc.ButtonGroup([
                dbc.Button(html.I(className="bi bi-chevron-left"), id="btn-hh-week-prev",
                           size="sm", color="secondary", outline=True),
                dbc.Button("Hoje", id="btn-hh-week-today", size="sm", color="secondary", outline=True),
                dbc.Button(html.I(className="bi bi-chevron-right"), id="btn-hh-week-next",
                           size="sm", color="secondary", outline=True),
            ], className="me-2"),
            # saltar pra qualquer semana (sem clicar ‹ › 300×)
            # Calendário custom Mon-first com nº da semana à esquerda
            dbc.Button([html.I(className="bi bi-calendar-week me-1"),
                        "Selecionar semana"],
                       id="btn-hh-weekpick", size="sm", color="secondary",
                       outline=True, className="ms-2"),
            dbc.Popover(
                html.Div(hh_week_picker.build_week_picker(
                    t_start.year, t_start.month, dmin=dmin, dmax=dmax),
                    id="hh-weekpick-content"),
                target="btn-hh-weekpick", trigger="legacy",
                placement="bottom-end", id="pop-hh-weekpick",
                style={"maxWidth": "330px", "padding": "0"},
                hide_arrow=False,
            ),
        ], style={"display": "flex", "alignItems": "center", "flexWrap": "wrap", "gap": "6px"}),
    ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-start",
              "flexWrap": "wrap", "gap": "10px", "marginBottom": "10px"})

    kpi_strip = html.Div(id="hh-kpi-strip",
                         style={"display": "flex", "gap": "8px", "flexWrap": "wrap",
                                "marginBottom": "12px"})

    return html.Div([
        dcc.Store(id="store-hh-view", data="ordem"),
        dcc.Store(id="store-hh-week-offset", data=0),
        dcc.Store(id="store-hh-day", data=None),   # ISO date quando em modo dia
        dcc.Store(id="store-hh-filters", data={}),
        dcc.Store(id="store-hh-sort", data="ordem"),
        dcc.Store(id="store-hh-scope", data="exec"),
        dcc.Store(id="store-hh-picker-month",
                  data=f"{t_start.year}-{t_start.month:02d}"),
        header,
        _filters_panel(opts),
        kpi_strip,
        # título do período — entre os cards e o gráfico
        html.Div(id="hh-week-label", style={
            "fontSize": "1.05rem", "fontWeight": "700", "margin": "4px 0 8px",
            "color": "var(--bs-body-color)", "borderLeft": "4px solid var(--bs-primary)",
            "paddingLeft": "10px",
        }),
        # escopo (quais linhas listar) + ordenação — acima da barra
        html.Div([
            html.Span("Listar:", style={"fontSize": "0.72rem", "color": "var(--bs-secondary)",
                                         "marginRight": "6px"}),
            dbc.ButtonGroup([
                _toggle_btn("Executado", "btn-hh-scope-exec", True, "play-circle"),
                _toggle_btn("Planejado", "btn-hh-scope-plan", False, "calendar2-week"),
                _toggle_btn("Ambos",     "btn-hh-scope-both", False, "intersect"),
            ], className="me-4"),
            html.Span("Ordenar:", style={"fontSize": "0.72rem", "color": "var(--bs-secondary)",
                                         "marginRight": "6px"}),
            dbc.ButtonGroup([
                _toggle_btn("Por data", "btn-hh-sort-data", False, "calendar3"),
                _toggle_btn("Por nº da ordem", "btn-hh-sort-ordem", True, "sort-numeric-down"),
            ], className="me-4"),
            html.Span("Ordens:", style={"fontSize": "0.72rem", "color": "var(--bs-secondary)",
                                         "marginRight": "6px"}),
            dbc.ButtonGroup([
                dbc.Button([html.I(className="bi bi-chevron-expand me-1"), "Expandir tudo"],
                           id="btn-hh-expand-all", size="sm", color="secondary", outline=True),
                dbc.Button([html.I(className="bi bi-chevron-contract me-1"), "Recolher tudo"],
                           id="btn-hh-collapse-all", size="sm", color="secondary", outline=True),
            ]),
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "8px",
                  "flexWrap": "wrap", "gap": "6px"}),
        dcc.Loading(html.Div(id="hh-gantt-container"), type="default"),
        # legenda
        html.Div([
            html.Span([html.Span(className="hh-legend-swatch hh-shift-cell"),
                       "Disponibilidade (turno)"], className="hh-legend-item"),
            html.Span([html.Span(className="hh-legend-swatch hh-extra-cell"),
                       "Extra (+2h após o turno)"], className="hh-legend-item"),
            html.Span([html.Span(className="hh-legend-swatch",
                                 style={"backgroundColor": "#9ec5fe", "opacity": "0.7"}),
                       "Planejado (janela da ordem IW37)"], className="hh-legend-item"),
            html.Span([html.Span(className="hh-legend-swatch",
                                 style={"backgroundColor": "#c0392b"}),
                       "Executado · YPM1 (corretiva)"], className="hh-legend-item"),
            html.Span([html.Span(className="hh-legend-swatch",
                                 style={"backgroundColor": "#27ae60"}),
                       "Executado · YPM2"], className="hh-legend-item"),
            html.Span([html.Span(className="hh-legend-swatch",
                                 style={"backgroundColor": "#8e44ad"}),
                       "Executado · YPM9 (preventiva)"], className="hh-legend-item"),
            html.Span([html.Span(className="hh-legend-swatch",
                                 style={"backgroundColor": "#2f6fb0"}),
                       "Executado · outro AUART"], className="hh-legend-item"),
        ], style={"marginTop": "8px", "fontSize": "0.7rem", "color": "var(--bs-secondary)",
                  "display": "flex", "gap": "16px", "flexWrap": "wrap"}),
    ], style={"padding": "16px"})
