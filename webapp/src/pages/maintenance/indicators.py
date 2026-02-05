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

# ==================== CONFIGURAÇÃO PLOTLY ====================
# Configuração padrão para mode bar: apenas Print e Auto Scale
PLOTLY_CONFIG = {
    'displayModeBar': True,
    'displaylogo': False,
    'modeBarButtonsToRemove': [
        'zoom2d', 'pan2d', 'select2d', 'lasso2d',
        'zoomIn2d', 'zoomOut2d', 'resetScale2d',
        'hoverClosestCartesian', 'hoverCompareCartesian',
        'toggleSpikelines'
    ],
    'toImageButtonOptions': {
        'format': 'png',
        'filename': 'grafico_manutencao',
        'height': None,
        'width': None,
        'scale': 2
    }
}


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
                                            type="circle",
                                            color="#198754",
                                            children=dcc.Graph(
                                                id='sunburst-chart-mtbf',
                                                config=PLOTLY_CONFIG
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
                                            type="circle",
                                            color="#0d6efd",
                                            children=dcc.Graph(
                                                id='sunburst-chart-mttr',
                                                config=PLOTLY_CONFIG
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
                                            type="circle",
                                            color="#ffc107",
                                            children=dcc.Graph(
                                                id='sunburst-chart-breakdown',
                                                config=PLOTLY_CONFIG
                                            )
                                        )
                                    ])
                                ], className="shadow-sm")
                            ], xs=12, md=4)
                        ], className="mb-4"),

                        # Seção: Evolução Temporal Geral (NOVO)
                        html.H5([
                            html.I(className="bi bi-graph-up me-2"),
                            "Evolução Temporal da Planta"
                        ], className="mt-4 mb-3"),
                        dbc.Row([
                            # Gráfico MTBF - Evolução Mensal
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader("MTBF - Evolução Mensal"),
                                    dbc.CardBody([
                                        dcc.Loading(
                                            type="circle",
                                            color="#198754",
                                            children=dcc.Graph(
                                                id="line-chart-mtbf-general",
                                                config=PLOTLY_CONFIG
                                            )
                                        )
                                    ])
                                ], className="shadow-sm")
                            ], md=4),

                            # Gráfico MTTR - Evolução Mensal
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader("MTTR - Evolução Mensal"),
                                    dbc.CardBody([
                                        dcc.Loading(
                                            type="circle",
                                            color="#0d6efd",
                                            children=dcc.Graph(
                                                id="line-chart-mttr-general",
                                                config=PLOTLY_CONFIG
                                            )
                                        )
                                    ])
                                ], className="shadow-sm")
                            ], md=4),

                            # Gráfico Taxa Avaria - Evolução Mensal
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader("Taxa Avaria - Evolução Mensal"),
                                    dbc.CardBody([
                                        dcc.Loading(
                                            type="circle",
                                            color="#ffc107",
                                            children=dcc.Graph(
                                                id="line-chart-breakdown-general",
                                                config=PLOTLY_CONFIG
                                            )
                                        )
                                    ])
                                ], className="shadow-sm")
                            ], md=4)
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
                                            type="circle",
                                            color="#0d6efd",
                                            children=dcc.Graph(
                                                id='bar-chart-mtbf',
                                                config=PLOTLY_CONFIG
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
                                            type="circle",
                                            color="#0d6efd",
                                            children=dcc.Graph(
                                                id='bar-chart-mttr',
                                                config=PLOTLY_CONFIG
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
                                            type="circle",
                                            color="#0d6efd",
                                            children=dcc.Graph(
                                                id='bar-chart-breakdown',
                                                config=PLOTLY_CONFIG
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
                                            # Coluna 1: Gráfico de barras horizontais (Top Paradas) - 42% do espaço
                                            dbc.Col([
                                                html.H6("Top 5 Paradas com Maior Tempo", className="text-center mb-3"),
                                                dcc.Loading(
                                                    type="circle",
                                                    color="#dc3545",
                                                    children=dcc.Graph(
                                                        id="top-breakdowns-chart-individual",
                                                        config=PLOTLY_CONFIG
                                                    )
                                                )
                                            ], md=5, className="d-flex flex-column justify-content-center"),

                                            # Coluna 2: 3 Gauges lado a lado com Metas - 58% do espaço
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
                                                            type="circle",
                                                            color="#198754",
                                                            children=dcc.Graph(
                                                                id="gauge-mtbf-individual",
                                                                config=PLOTLY_CONFIG
                                                            )
                                                        )
                                                    ], md=4),

                                                    # Gauge MTTR
                                                    dbc.Col([
                                                        dcc.Loading(
                                                            type="circle",
                                                            color="#0d6efd",
                                                            children=dcc.Graph(
                                                                id="gauge-mttr-individual",
                                                                config=PLOTLY_CONFIG
                                                            )
                                                        )
                                                    ], md=4),

                                                    # Gauge Taxa de Avaria
                                                    dbc.Col([
                                                        dcc.Loading(
                                                            type="circle",
                                                            color="#ffc107",
                                                            children=dcc.Graph(
                                                                id="gauge-breakdown-individual",
                                                                config=PLOTLY_CONFIG
                                                            )
                                                        )
                                                    ], md=4)
                                                ], className="align-items-center")
                                            ], md=7, className="d-flex flex-column")
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
                                            type="circle",
                                            color="#198754",
                                            children=dcc.Graph(
                                                id="line-chart-mtbf-individual",
                                                config=PLOTLY_CONFIG
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
                                            type="circle",
                                            color="#0d6efd",
                                            children=dcc.Graph(
                                                id="line-chart-mttr-individual",
                                                config=PLOTLY_CONFIG
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
                                            type="circle",
                                            color="#ffc107",
                                            children=dcc.Graph(
                                                id="line-chart-breakdown-individual",
                                                config=PLOTLY_CONFIG
                                            )
                                        )
                                    ])
                                ], className="shadow-sm")
                            ], md=4)
                        ], className="mb-4"),

                        # Performance Radar e Calendar Heatmap
                        html.H5([
                            html.I(className="bi bi-diagram-3 me-2"),
                            "Análise de Performance e Padrões"
                        ], className="mt-4 mb-3"),
                        dbc.Row([
                            # Calendar Heatmap (Padrão de Falhas) - 33%
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader([
                                        html.I(className="bi bi-calendar-week me-2"),
                                        html.Strong("Padrão Temporal de Falhas")
                                    ]),
                                    dbc.CardBody([
                                        dcc.Loading(
                                            type="circle",
                                            color="#6c757d",
                                            children=dcc.Graph(
                                                id="calendar-heatmap-individual",
                                                config=PLOTLY_CONFIG
                                            )
                                        )
                                    ])
                                ], className="shadow-sm")
                            ], md=4, lg=4),

                            # Estatísticas (NOVO) - 33%
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader([
                                        html.I(className="bi bi-bar-chart me-2"),
                                        html.Strong("Estatísticas")
                                    ]),
                                    dbc.CardBody(
                                        id="heatmap-stats-card",
                                        style={"fontSize": "0.85rem", "height": "530px", "overflowY": "auto"}
                                    )
                                ], className="shadow-sm")
                            ], md=4, lg=4),

                            # Radar Chart (Performance) - 33%
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader([
                                        html.I(className="bi bi-pentagon me-2"),
                                        html.Strong("Performance Geral")
                                    ]),
                                    dbc.CardBody([
                                        dcc.Loading(
                                            type="circle",
                                            color="#6c757d",
                                            children=dcc.Graph(
                                                id="comparison-chart-individual",
                                                config=PLOTLY_CONFIG
                                            )
                                        )
                                    ])
                                ], className="shadow-sm")
                            ], md=4, lg=4)
                        ]),


                    ], className="p-3")
                ]
            )

        ], id="indicator-tabs", active_tab="tab-general", className="mb-4"),

        # ==================== STORES & DOWNLOADS ====================
        dcc.Store(id='store-indicator-filters', storage_type='session'),
        dcc.Download(id="download-indicators-data"),

        # Interval para carregamento inicial de dados (executa apenas 1 vez)
        dcc.Interval(
            id='interval-initial-load',
            interval=500,  # 500ms (carrega rápido no início)
            n_intervals=0,
            max_intervals=1  # Executa apenas 1 vez no carregamento
        )

    ], fluid=True, className="p-4")
