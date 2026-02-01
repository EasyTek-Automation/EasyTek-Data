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

        # ==================== TABS ====================
        dbc.Tabs([
            # Tab 1: Geral (Todos Equipamentos)
            dbc.Tab(
                label="📊 Geral",
                tab_id="tab-general",
                children=[
                    html.Div([
                        # Seção: Hierarquias Sunburst (MOVIDA PARA CIMA)
                        html.H5([
                            html.I(className="bi bi-pie-chart-fill me-2"),
                            "Hierarquia por Categoria"
                        ], className="mt-4 mb-3"),
                        dbc.Row([
                            # Sunburst MTBF
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader([
                                        html.I(className="bi bi-clock-history me-2"),
                                        html.Strong("Hierarquia MTBF")
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
                            ], xs=12, md=4),

                            # Sunburst MTTR
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader([
                                        html.I(className="bi bi-tools me-2"),
                                        html.Strong("Hierarquia MTTR")
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
                            ], xs=12, md=4),

                            # Sunburst Taxa Avaria
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader([
                                        html.I(className="bi bi-exclamation-triangle me-2"),
                                        html.Strong("Hierarquia Avarias")
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
                            ], xs=12, md=4)
                        ], className="mb-4"),

                        # Seção: Gráficos de Barras (MOVIDA PARA BAIXO)
                        html.H5([
                            html.I(className="bi bi-bar-chart-fill me-2"),
                            "Indicadores por Equipamento"
                        ], className="mt-4 mb-3"),
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
                                ], className="shadow-sm")
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
                                ], className="shadow-sm")
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
                                ], className="shadow-sm")
                            ], xs=12, md=4)
                        ], className="mb-4"),

                        # Seção: Tabela Resumo
                        html.H5([
                            html.I(className="bi bi-table me-2"),
                            "Resumo Geral"
                        ], className="mt-4 mb-3"),
                        html.Div(
                            id="kpi-summary-table-container",
                            children=[
                                html.P(
                                    "Selecione os filtros e clique em 'Aplicar' para visualizar os dados.",
                                    className="text-muted text-center py-4"
                                )
                            ]
                        )
                    ], className="p-3")
                ]
            ),

            # Tab 2: Individual (Equipamento Selecionado)
            dbc.Tab(
                label="🔧 Individual",
                tab_id="tab-individual",
                children=[
                    html.Div([
                        # Seletor de Equipamento
                        dbc.Row([
                            dbc.Col([
                                html.Label("Selecione o Equipamento:", className="form-label fw-bold"),
                                dcc.Dropdown(
                                    id="dropdown-equipment-individual",
                                    options=[],
                                    placeholder="Selecione um equipamento...",
                                    clearable=False
                                ),
                                # Badges compactos com metas logo abaixo do dropdown
                                html.Div(
                                    id="equipment-targets-badges",
                                    className="mt-2"
                                )
                            ], md=6)
                        ], className="mb-4"),

                        # Paradas Críticas + Gauges de Indicadores
                        dbc.Row([
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader([
                                        html.I(className="bi bi-graph-up-arrow me-2"),
                                        html.Strong("Paradas Críticas e Indicadores")
                                    ]),
                                    dbc.CardBody([
                                        dbc.Row([
                                            # Coluna 1/3: Gráfico de barras horizontais (Top Paradas)
                                            dbc.Col([
                                                html.H6("Top 10 Paradas com Maior Tempo", className="text-center mb-3"),
                                                dcc.Loading(
                                                    type="default",
                                                    children=dcc.Graph(
                                                        id="top-breakdowns-chart-individual",
                                                        config={'displayModeBar': True, 'displaylogo': False}
                                                    )
                                                )
                                            ], md=4, className="d-flex flex-column justify-content-center"),

                                            # Coluna 2/3: 3 Gauges lado a lado com Metas
                                            dbc.Col([
                                                # Metas do Equipamento
                                                html.Div(
                                                    id="equipment-targets-info",
                                                    className="mb-3"
                                                ),
                                                # Gauges
                                                dbc.Row([
                                                    # Gauge MTBF
                                                    dbc.Col([
                                                        dcc.Loading(
                                                            type="default",
                                                            children=dcc.Graph(
                                                                id="gauge-mtbf-individual",
                                                                config={'displayModeBar': False, 'displaylogo': False}
                                                            )
                                                        )
                                                    ], md=4),

                                                    # Gauge MTTR
                                                    dbc.Col([
                                                        dcc.Loading(
                                                            type="default",
                                                            children=dcc.Graph(
                                                                id="gauge-mttr-individual",
                                                                config={'displayModeBar': False, 'displaylogo': False}
                                                            )
                                                        )
                                                    ], md=4),

                                                    # Gauge Taxa de Avaria
                                                    dbc.Col([
                                                        dcc.Loading(
                                                            type="default",
                                                            children=dcc.Graph(
                                                                id="gauge-breakdown-individual",
                                                                config={'displayModeBar': False, 'displaylogo': False}
                                                            )
                                                        )
                                                    ], md=4)
                                                ], className="align-items-center")
                                            ], md=8, className="d-flex flex-column")
                                        ], className="align-items-center")
                                    ], className="p-3")
                                ], className="shadow-sm")
                            ])
                        ], className="mb-4"),

                        # Gráficos de Linha (Evolução Temporal)
                        html.H5([
                            html.I(className="bi bi-graph-up me-2"),
                            "Evolução Temporal"
                        ], className="mt-4 mb-3"),
                        dbc.Row([
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader("MTBF - Evolução Mensal"),
                                    dbc.CardBody([
                                        dcc.Loading(
                                            type="default",
                                            children=dcc.Graph(
                                                id="line-chart-mtbf-individual",
                                                config={'displayModeBar': True, 'displaylogo': False}
                                            )
                                        )
                                    ])
                                ], className="shadow-sm")
                            ], md=4),
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader("MTTR - Evolução Mensal"),
                                    dbc.CardBody([
                                        dcc.Loading(
                                            type="default",
                                            children=dcc.Graph(
                                                id="line-chart-mttr-individual",
                                                config={'displayModeBar': True, 'displaylogo': False}
                                            )
                                        )
                                    ])
                                ], className="shadow-sm")
                            ], md=4),
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader("Taxa Avaria - Evolução Mensal"),
                                    dbc.CardBody([
                                        dcc.Loading(
                                            type="default",
                                            children=dcc.Graph(
                                                id="line-chart-breakdown-individual",
                                                config={'displayModeBar': True, 'displaylogo': False}
                                            )
                                        )
                                    ])
                                ], className="shadow-sm")
                            ], md=4)
                        ], className="mb-4"),

                        # Comparação com Média Geral
                        html.H5([
                            html.I(className="bi bi-bar-chart me-2"),
                            "Comparação com Média Geral"
                        ], className="mt-4 mb-3"),
                        dbc.Row([
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader("Comparativo de Performance"),
                                    dbc.CardBody([
                                        dcc.Loading(
                                            type="default",
                                            children=dcc.Graph(
                                                id="comparison-chart-individual",
                                                config={'displayModeBar': True, 'displaylogo': False}
                                            )
                                        )
                                    ])
                                ], className="shadow-sm")
                            ])
                        ]),


                    ], className="p-3")
                ]
            )

        ], id="indicator-tabs", active_tab="tab-general", className="mb-4"),

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
