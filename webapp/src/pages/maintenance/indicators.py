"""
Página de Indicadores de Manutenção
KPIs: MTBF, MTTR e Taxa de Avaria
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
from src.components.maintenance_kpi_cards import (
    create_mtbf_summary_card,
    create_mttr_summary_card,
    create_breakdown_summary_card,
    create_equipment_count_card
)
from src.components.maintenance_kpi_graphs import create_empty_kpi_figure


def layout():
    """
    Layout da página de Indicadores de Manutenção

    Estrutura:
    - Header com título e botões de ação
    - 4 Cards de resumo (MTBF, MTTR, Avaria, Equipamentos)
    - Filtros colapsáveis (Ano, Meses)
    - Sistema de Tabs:
      - Visão Geral: 3 gráficos de barras + tabela resumo
      - Hierarquia MTBF: Sunburst MTBF
      - Hierarquia MTTR: Sunburst MTTR
      - Hierarquia Avarias: Sunburst Avarias
    """

    return dbc.Container([
        # ==================== DEMO WARNING ====================
        dbc.Alert([
            html.I(className="bi bi-info-circle me-2"),
            html.Strong("Dados Demonstrativos: "),
            "Esta página está utilizando dados fictícios para avaliação de layout e UX."
        ], color="info", className="mb-3", dismissable=True, id="demo-alert-indicators"),

        # ==================== HEADER ====================
        dbc.Row([
            dbc.Col([
                html.H2([
                    html.I(
                        className="bi bi-graph-up-arrow me-3",
                        style={"color": "#0d6efd"}
                    ),
                    "Indicadores de Manutenção"
                ], className="mb-2"),
                html.P(
                    "Análise de MTBF, MTTR e Taxa de Avaria por equipamento",
                    className="text-muted"
                )
            ], width=8),
            dbc.Col([
                dbc.ButtonGroup([
                    dbc.Button(
                        [html.I(className="bi bi-arrow-clockwise me-2"), "Atualizar"],
                        id="btn-refresh-indicators",
                        color="primary",
                        size="sm",
                        outline=True
                    ),
                    dbc.Button(
                        [html.I(className="bi bi-download me-2"), "Exportar"],
                        id="btn-export-indicators",
                        color="secondary",
                        size="sm",
                        outline=True
                    ),
                    dbc.Button(
                        [html.I(className="bi bi-funnel me-2"), "Filtros"],
                        id="btn-toggle-indicator-filters",
                        color="secondary",
                        size="sm",
                        outline=True
                    )
                ])
            ], width=4, className="text-end d-flex align-items-center justify-content-end")
        ], className="mb-4"),

        # ==================== SUMMARY CARDS ====================
        dbc.Row([
            dbc.Col([create_mtbf_summary_card()], xs=12, sm=6, md=3, className="mb-3"),
            dbc.Col([create_mttr_summary_card()], xs=12, sm=6, md=3, className="mb-3"),
            dbc.Col([create_breakdown_summary_card()], xs=12, sm=6, md=3, className="mb-3"),
            dbc.Col([create_equipment_count_card()], xs=12, sm=6, md=3, className="mb-3")
        ], className="g-3 mb-4"),

        # ==================== FILTERS (COLLAPSIBLE) ====================
        dbc.Collapse([
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Label("Ano", className="form-label small fw-bold"),
                            dcc.Dropdown(
                                id="filter-indicator-year",
                                options=[
                                    {"label": "2024", "value": 2024},
                                    {"label": "2025", "value": 2025},
                                    {"label": "2026", "value": 2026}
                                ],
                                value=2026,
                                clearable=False
                            )
                        ], md=2),
                        dbc.Col([
                            html.Label("Meses", className="form-label small fw-bold"),
                            dcc.Dropdown(
                                id="filter-indicator-months",
                                options=[
                                    {"label": "Janeiro", "value": 1},
                                    {"label": "Fevereiro", "value": 2},
                                    {"label": "Março", "value": 3},
                                    {"label": "Abril", "value": 4},
                                    {"label": "Maio", "value": 5},
                                    {"label": "Junho", "value": 6},
                                    {"label": "Julho", "value": 7},
                                    {"label": "Agosto", "value": 8},
                                    {"label": "Setembro", "value": 9},
                                    {"label": "Outubro", "value": 10},
                                    {"label": "Novembro", "value": 11},
                                    {"label": "Dezembro", "value": 12}
                                ],
                                value=list(range(1, 13)),  # Todos os meses selecionados
                                multi=True,
                                placeholder="Selecione os meses"
                            )
                        ], md=8),
                        dbc.Col([
                            html.Label("Ações", className="form-label small fw-bold"),
                            dbc.Button(
                                [html.I(className="bi bi-check-circle me-2"), "Aplicar"],
                                id="btn-apply-indicator-filters",
                                color="primary",
                                size="sm",
                                className="w-100"
                            )
                        ], md=2, className="d-flex align-items-end")
                    ])
                ])
            ], className="mb-3 shadow-sm")
        ], id="collapse-indicator-filters", is_open=True),

        # ==================== TABS ====================
        dbc.Tabs([
            # Tab 1: Visão Geral
            dbc.Tab(
                label="Visão Geral",
                tab_id="tab-overview",
                children=[
                    html.Div([
                        # Seção: Gráficos de Barras
                        dbc.Row([
                            dbc.Col([
                                html.H5([
                                    html.I(className="bi bi-bar-chart-fill me-2"),
                                    "Indicadores por Equipamento"
                                ], className="mb-3")
                            ], width=12)
                        ]),

                        dbc.Row([
                            # Gráfico MTBF
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader([
                                        html.I(className="bi bi-clock-history me-2"),
                                        html.Strong("MTBF (Mean Time Between Failures)")
                                    ]),
                                    dbc.CardBody([
                                        dcc.Loading(
                                            id="loading-bar-mtbf",
                                            type="default",
                                            children=dcc.Graph(
                                                id='bar-chart-mtbf',
                                                figure=create_empty_kpi_figure("MTBF"),
                                                config={
                                                    'displayModeBar': True,
                                                    'displaylogo': False,
                                                    'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
                                                    'doubleClick': 'reset',
                                                    'responsive': True
                                                }
                                            )
                                        )
                                    ])
                                ], className="shadow-sm mb-4")
                            ], xs=12, md=4),

                            # Gráfico MTTR
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader([
                                        html.I(className="bi bi-tools me-2"),
                                        html.Strong("MTTR (Mean Time To Repair)")
                                    ]),
                                    dbc.CardBody([
                                        dcc.Loading(
                                            id="loading-bar-mttr",
                                            type="default",
                                            children=dcc.Graph(
                                                id='bar-chart-mttr',
                                                figure=create_empty_kpi_figure("MTTR"),
                                                config={
                                                    'displayModeBar': True,
                                                    'displaylogo': False,
                                                    'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
                                                    'doubleClick': 'reset',
                                                    'responsive': True
                                                }
                                            )
                                        )
                                    ])
                                ], className="shadow-sm mb-4")
                            ], xs=12, md=4),

                            # Gráfico Taxa de Avaria
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader([
                                        html.I(className="bi bi-exclamation-triangle me-2"),
                                        html.Strong("Taxa de Avaria")
                                    ]),
                                    dbc.CardBody([
                                        dcc.Loading(
                                            id="loading-bar-breakdown",
                                            type="default",
                                            children=dcc.Graph(
                                                id='bar-chart-breakdown',
                                                figure=create_empty_kpi_figure("Taxa de Avaria"),
                                                config={
                                                    'displayModeBar': True,
                                                    'displaylogo': False,
                                                    'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
                                                    'doubleClick': 'reset',
                                                    'responsive': True
                                                }
                                            )
                                        )
                                    ])
                                ], className="shadow-sm mb-4")
                            ], xs=12, md=4)
                        ], className="mb-4"),

                        # Seção: Tabela Resumo
                        dbc.Row([
                            dbc.Col([
                                html.H5([
                                    html.I(className="bi bi-table me-2"),
                                    "Resumo por Equipamento"
                                ], className="mb-3"),
                                html.Div(
                                    id="kpi-summary-table-container",
                                    children=[
                                        html.P(
                                            "Selecione os filtros e clique em 'Aplicar' para visualizar os dados.",
                                            className="text-muted text-center py-4"
                                        )
                                    ]
                                )
                            ], width=12)
                        ])
                    ], className="p-3")
                ]
            ),

            # Tab 2: Hierarquia MTBF
            dbc.Tab(
                label="Hierarquia MTBF",
                tab_id="tab-sunburst-mtbf",
                children=[
                    html.Div([
                        dbc.Card([
                            dbc.CardHeader([
                                html.I(className="bi bi-pie-chart-fill me-2"),
                                html.Strong("Hierarquia de MTBF por Categoria")
                            ]),
                            dbc.CardBody([
                                dcc.Loading(
                                    id="loading-sunburst-mtbf",
                                    type="default",
                                    children=dcc.Graph(
                                        id='sunburst-chart-mtbf',
                                        config={
                                            'displayModeBar': True,
                                            'displaylogo': False,
                                            'responsive': True
                                        }
                                    )
                                )
                            ])
                        ], className="shadow-sm")
                    ], className="p-3")
                ]
            ),

            # Tab 3: Hierarquia MTTR
            dbc.Tab(
                label="Hierarquia MTTR",
                tab_id="tab-sunburst-mttr",
                children=[
                    html.Div([
                        dbc.Card([
                            dbc.CardHeader([
                                html.I(className="bi bi-pie-chart-fill me-2"),
                                html.Strong("Hierarquia de MTTR por Categoria")
                            ]),
                            dbc.CardBody([
                                dcc.Loading(
                                    id="loading-sunburst-mttr",
                                    type="default",
                                    children=dcc.Graph(
                                        id='sunburst-chart-mttr',
                                        config={
                                            'displayModeBar': True,
                                            'displaylogo': False,
                                            'responsive': True
                                        }
                                    )
                                )
                            ])
                        ], className="shadow-sm")
                    ], className="p-3")
                ]
            ),

            # Tab 4: Hierarquia Avarias
            dbc.Tab(
                label="Hierarquia Avarias",
                tab_id="tab-sunburst-breakdown",
                children=[
                    html.Div([
                        dbc.Card([
                            dbc.CardHeader([
                                html.I(className="bi bi-pie-chart-fill me-2"),
                                html.Strong("Hierarquia de Taxa de Avaria por Categoria")
                            ]),
                            dbc.CardBody([
                                dcc.Loading(
                                    id="loading-sunburst-breakdown",
                                    type="default",
                                    children=dcc.Graph(
                                        id='sunburst-chart-breakdown',
                                        config={
                                            'displayModeBar': True,
                                            'displaylogo': False,
                                            'responsive': True
                                        }
                                    )
                                )
                            ])
                        ], className="shadow-sm")
                    ], className="p-3")
                ]
            )

        ], id="indicator-tabs", active_tab="tab-overview", className="mb-4"),

        # ==================== STORES & DOWNLOADS ====================
        dcc.Store(id='store-indicator-filters', storage_type='session'),
        dcc.Download(id="download-indicators-data"),

        # Interval para carregar dados automaticamente ao abrir a página
        dcc.Interval(
            id='interval-initial-load',
            interval=500,  # 500ms
            n_intervals=0,
            max_intervals=1  # Dispara apenas uma vez
        )

    ], fluid=True, className="p-4")
