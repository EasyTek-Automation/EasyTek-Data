"""Aba 'Custo de Manutencao' — layout autocontido (DS-06).

Bloco destacavel (IN-05): stores, ids e graficos proprios, acoplamento minimo as
demais abas. So le do Mongo (DS-01). Drill-down grupo -> conta -> mes -> dia, com
filtro lateral de centro de custo, card do geral, tarja de reconciliacao, selo de
seed e botao "Rodar agora" isolado (SP-10). O comportamento vive em
`callbacks_registers/custo_callbacks.py`.
"""
from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html

ANO_PADRAO = 2026


def build_tab() -> dbc.Tab:
    """Constroi a `dbc.Tab` da feature de custo, para inserir em indicators_v2."""
    return dbc.Tab(
        label="💰 Custo de Manutenção",
        id="tab-v2-custo-component",
        tab_id="tab-v2-custo",
        children=html.Div(
            [
                # Estado proprio da aba (autocontido)
                dcc.Store(id="store-custo-ano", data=ANO_PADRAO),
                dcc.Store(id="store-custo-drill", data={"nivel": "planta"}),
                dcc.Store(id="store-custo-centros", data=[]),
                dcc.Interval(id="custo-init", interval=300, max_intervals=1),

                dcc.Loading(
                    type="circle",
                    color="#0d6efd",
                    children=html.Div(
                        [
                            # Cabecalho: titulo + ano + botao Rodar agora
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.H5(
                                                [html.I(className="bi bi-cash-coin me-2"),
                                                 "Custo de Manutenção"],
                                                className="mb-0",
                                            ),
                                            html.Small(
                                                "Orçado × Executado da manutenção (GT340) — "
                                                "clique para detalhar grupo → conta → mês → dia.",
                                                className="text-muted",
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Ano:", className="me-2 small text-muted"),
                                            dcc.Dropdown(
                                                id="custo-ano-select",
                                                options=[{"label": str(ANO_PADRAO), "value": ANO_PADRAO}],
                                                value=ANO_PADRAO,
                                                clearable=False,
                                                style={"width": "120px"},
                                            ),
                                            dbc.Button(
                                                [html.I(className="bi bi-arrow-repeat me-2"),
                                                 "Rodar agora"],
                                                id="btn-custo-rodar-agora",
                                                color="outline-primary",
                                                size="sm",
                                                className="ms-3",
                                            ),
                                        ],
                                        className="d-flex align-items-center",
                                    ),
                                ],
                                className="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2",
                            ),

                            # Selo de seed + feedback do botao + tarja de reconciliacao
                            html.Div(id="custo-seed-selo", className="mb-2"),
                            html.Div(id="custo-rodar-feedback"),
                            html.Div(id="custo-reconc-banner", className="mb-2"),

                            dbc.Row(
                                [
                                    # Lateral: filtro de centro de custo
                                    dbc.Col(
                                        dbc.Card(
                                            dbc.CardBody(
                                                [
                                                    html.H6(
                                                        [html.I(className="bi bi-funnel me-2"),
                                                         "Centro de custo"],
                                                        className="mb-2",
                                                    ),
                                                    html.Small(
                                                        "Filtra apenas o executado; o orçado "
                                                        "permanece o total da conta.",
                                                        className="text-muted d-block mb-2",
                                                    ),
                                                    dcc.Dropdown(
                                                        id="custo-centro-filter",
                                                        options=[],
                                                        value=[],
                                                        multi=True,
                                                        placeholder="Todos os centros",
                                                    ),
                                                ]
                                            ),
                                            className="mb-3",
                                        ),
                                        md=3,
                                    ),
                                    # Corpo: card geral + breadcrumb + grafico
                                    dbc.Col(
                                        [
                                            html.Div(id="custo-card-geral", className="mb-3"),
                                            html.Div(id="custo-breadcrumb", className="mb-2"),
                                            dcc.Graph(id="custo-graph", config={"displayModeBar": False}),
                                        ],
                                        md=9,
                                    ),
                                ],
                            ),

                            # Rodape: tabela de lancamentos do recorte
                            html.H6(
                                [html.I(className="bi bi-table me-2"), "Lançamentos do recorte"],
                                className="mt-4 mb-2",
                            ),
                            html.Div(id="custo-tabela"),
                        ],
                        className="p-3",
                    ),
                ),
            ],
        ),
    )
