"""Aba 'Custo de Manutencao' — layout autocontido (DS-06).

Replica o padrao visual sofisticado da indicators-v2: cards com borda superior
colorida (`indicator-v2-card`), valor grande, toolbar com labels uppercase, grafico
com altura FIXA (style explicito no `dcc.Graph` — evita o autosize crescer infinito).
Bloco destacavel (IN-05): stores, ids e graficos proprios. So le do Mongo (DS-01).
Comportamento em `callbacks_registers/custo_callbacks.py`.
"""
from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html

ANO_PADRAO = 2026

_CINZA = "#6c757d"


def _label(txt: str) -> html.Label:
    """Label de toolbar no padrao indicators-v2 (uppercase, espacado, muted)."""
    return html.Label(
        txt,
        className="text-muted fw-semibold d-block mb-1",
        style={"fontSize": "0.72rem", "letterSpacing": "0.4px", "textTransform": "uppercase"},
    )


def build_tab() -> dbc.Tab:
    """Constroi a `dbc.Tab` da feature de custo, para inserir em indicators_v2."""
    return dbc.Tab(
        label="💰 Custo de Manutenção",
        id="tab-v2-custo-component",
        tab_id="tab-v2-custo",
        children=html.Div(
            [
                # Estado proprio (autocontido)
                dcc.Store(id="store-custo-ano", data=ANO_PADRAO),
                dcc.Store(id="store-custo-drill", data={"nivel": "planta"}),
                dcc.Store(id="store-custo-centros", data=[]),
                dcc.Interval(id="custo-init", interval=300, max_intervals=1),

                dcc.Loading(
                    type="circle",
                    color="#0d6efd",
                    children=html.Div(
                        [
                            # ---- Cabecalho ----
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.H4(
                                                [html.I(className="bi bi-cash-coin me-2",
                                                        style={"color": "#0d6efd"}),
                                                 "Custo de Manutenção"],
                                                className="mb-0 fw-bold",
                                                style={"letterSpacing": "-0.3px"},
                                            ),
                                            html.Span(
                                                "Orçado × Executado da manutenção (GT340) — "
                                                "clique numa barra para detalhar grupo → conta → mês → dia.",
                                                className="text-muted",
                                                style={"fontSize": "0.82rem"},
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        [
                                            html.Div(
                                                [_label("Ano"),
                                                 dcc.Dropdown(
                                                     id="custo-ano-select",
                                                     options=[{"label": str(ANO_PADRAO), "value": ANO_PADRAO}],
                                                     value=ANO_PADRAO, clearable=False,
                                                     style={"width": "110px"},
                                                 )],
                                                className="me-3",
                                            ),
                                            html.Div(
                                                [_label("Coleta"),
                                                 dbc.Button(
                                                     [html.I(className="bi bi-arrow-repeat me-2"),
                                                      "Rodar agora"],
                                                     id="btn-custo-rodar-agora",
                                                     color="primary", outline=True, size="sm",
                                                 )],
                                            ),
                                        ],
                                        className="d-flex align-items-end",
                                    ),
                                ],
                                className="d-flex justify-content-between align-items-end mb-3 flex-wrap gap-3",
                            ),

                            html.Div(id="custo-seed-selo", className="mb-2"),
                            html.Div(id="custo-rodar-feedback"),
                            html.Div(id="custo-reconc-banner", className="mb-2"),

                            # ---- Cards KPI do geral ----
                            html.Div(id="custo-card-geral", className="mb-3"),

                            # ---- Corpo: filtro lateral + grafico ----
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dbc.Card(
                                            dbc.CardBody(
                                                [
                                                    html.H6(
                                                        [html.I(className="bi bi-funnel me-2"),
                                                         "Centro de custo"],
                                                        className="mb-2 fw-bold",
                                                    ),
                                                    html.Small(
                                                        "Filtra apenas o executado; o orçado "
                                                        "permanece o total da conta.",
                                                        className="text-muted d-block mb-2",
                                                    ),
                                                    dcc.Dropdown(
                                                        id="custo-centro-filter",
                                                        options=[], value=[], multi=True,
                                                        placeholder="Todos os centros",
                                                    ),
                                                ]
                                            ),
                                            className="shadow-sm h-100 indicator-v2-card-static",
                                            style={"borderTop": f"4px solid {_CINZA}"},
                                        ),
                                        md=3, className="mb-3",
                                    ),
                                    dbc.Col(
                                        dbc.Card(
                                            [
                                                dbc.CardHeader(
                                                    html.Div(id="custo-breadcrumb"),
                                                    className="py-2",
                                                ),
                                                dbc.CardBody(
                                                    dcc.Graph(
                                                        id="custo-graph",
                                                        config={"displayModeBar": False,
                                                                "responsive": True},
                                                        style={"height": "440px", "width": "100%"},
                                                    ),
                                                    className="p-2",
                                                ),
                                            ],
                                            className="shadow-sm h-100 indicator-v2-card-md",
                                            style={"borderTop": "4px solid #0d6efd"},
                                        ),
                                        md=9, className="mb-3",
                                    ),
                                ],
                            ),

                            # ---- Tabela de lancamentos ----
                            dbc.Card(
                                [
                                    dbc.CardHeader(
                                        html.H6(
                                            [html.I(className="bi bi-table me-2"),
                                             "Lançamentos do recorte"],
                                            className="mb-0 fw-bold",
                                        ),
                                        className="py-2",
                                    ),
                                    dbc.CardBody(html.Div(id="custo-tabela"), className="p-2"),
                                ],
                                className="shadow-sm indicator-v2-card-static",
                                style={"borderTop": f"4px solid {_CINZA}"},
                            ),
                        ],
                        className="p-3",
                    ),
                ),
            ],
        ),
    )
