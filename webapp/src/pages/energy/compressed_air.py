# src/pages/energy/compressed_air.py

"""
Página de Monitoramento de Ar Comprimido
Monitoramento de sistema de ar comprimido industrial
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
from src.utils.demo_helpers import add_demo_badge_to_card_header


def layout():
    """
    Página de monitoramento de sistema de ar comprimido
    """
    return dbc.Container([

        # ========================================
        # HEADER DA PÁGINA
        # ========================================
        dbc.Row([
            dbc.Col([
                html.H2("💨 Monitoramento de Ar Comprimido"),
                html.P(
                    "Monitoramento em tempo real do sistema de ar comprimido industrial",
                    className="text-muted"
                )
            ], width=8),
            dbc.Col([
                dbc.ButtonGroup([
                    dbc.Button(
                        [html.I(className="bi bi-download me-2"), "Exportar"],
                        color="info",
                        size="sm"
                    ),
                    dbc.Button(
                        [html.I(className="bi bi-gear me-2"), "Configurar"],
                        color="secondary",
                        size="sm",
                        outline=True
                    ),
                ])
            ], width=4, className="text-end")
        ], className="mb-4"),

        # ========================================
        # TABS PARA DIFERENTES SEÇÕES
        # ========================================
        dbc.Tabs([
            dbc.Tab(label="🏭 Visão Geral", tab_id="overview"),
            dbc.Tab(label="🔧 Compressores", tab_id="compressors"),
            dbc.Tab(label="📊 Eficiência", tab_id="efficiency"),
            dbc.Tab(label="📈 Histórico", tab_id="history"),
        ], id="compressed-air-tabs", active_tab="overview", className="mb-3"),

        # ========================================
        # CONTEÚDO DA TAB ATIVA
        # ========================================
        html.Div(id="compressed-air-tab-content", children=[get_overview_content()])

    ], fluid=True, className="p-4")


def get_overview_content():
    """
    Retorna o conteúdo da visão geral do sistema de ar comprimido
    """
    return html.Div([
        # ========================================
        # SEÇÃO: CARDS DE KPIs PRINCIPAIS
        # ========================================
        dbc.Row([
            # Pressão Média
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(
                        add_demo_badge_to_card_header(
                            "",
                            page_path="/utilities/compressed-air",
                            size="sm"
                        ),
                        className="bg-transparent"
                    ),
                    dbc.CardBody([
                        html.Div([
                            html.I(
                                className="bi bi-speedometer text-primary",
                                style={"fontSize": "2.5rem"}
                            )
                        ], className="text-center mb-2"),
                        html.H6("Pressão Média", className="text-center"),
                        html.H3(
                            "7.2 bar",
                            className="text-center text-primary fw-bold mb-0"
                        ),
                        html.P("Sistema Principal", className="text-center text-muted small")
                    ])
                ], className="shadow-sm h-100")
            ], md=3, className="mb-3"),

            # Vazão Total
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(
                        add_demo_badge_to_card_header(
                            "",
                            page_path="/utilities/compressed-air",
                            size="sm"
                        ),
                        className="bg-transparent"
                    ),
                    dbc.CardBody([
                        html.Div([
                            html.I(
                                className="bi bi-wind text-info",
                                style={"fontSize": "2.5rem"}
                            )
                        ], className="text-center mb-2"),
                        html.H6("Vazão Total", className="text-center"),
                        html.H3(
                            "285 m³/h",
                            className="text-center text-info fw-bold mb-0"
                        ),
                        html.P("Taxa Atual", className="text-center text-muted small")
                    ])
                ], className="shadow-sm h-100")
            ], md=3, className="mb-3"),

            # Consumo de Energia
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(
                        add_demo_badge_to_card_header(
                            "",
                            page_path="/utilities/compressed-air",
                            size="sm"
                        ),
                        className="bg-transparent"
                    ),
                    dbc.CardBody([
                        html.Div([
                            html.I(
                                className="bi bi-lightning-charge text-warning",
                                style={"fontSize": "2.5rem"}
                            )
                        ], className="text-center mb-2"),
                        html.H6("Consumo Energia", className="text-center"),
                        html.H3(
                            "156 kW",
                            className="text-center text-warning fw-bold mb-0"
                        ),
                        html.P("Potência Atual", className="text-center text-muted small")
                    ])
                ], className="shadow-sm h-100")
            ], md=3, className="mb-3"),

            # Eficiência do Sistema
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(
                        add_demo_badge_to_card_header(
                            "",
                            page_path="/utilities/compressed-air",
                            size="sm"
                        ),
                        className="bg-transparent"
                    ),
                    dbc.CardBody([
                        html.Div([
                            html.I(
                                className="bi bi-graph-up-arrow text-success",
                                style={"fontSize": "2.5rem"}
                            )
                        ], className="text-center mb-2"),
                        html.H6("Eficiência", className="text-center"),
                        html.H3(
                            "84%",
                            className="text-center text-success fw-bold mb-0"
                        ),
                        html.P("Sistema Geral", className="text-center text-muted small")
                    ])
                ], className="shadow-sm h-100")
            ], md=3, className="mb-3"),
        ]),

        # ========================================
        # SEÇÃO: GRÁFICOS DE MONITORAMENTO
        # ========================================
        dbc.Row([
            dbc.Col([
                html.H4("Monitoramento em Tempo Real", className="mt-4 mb-3")
            ])
        ]),

        dbc.Row([
            # Gráfico de Pressão ao Longo do Tempo
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("📈 Pressão ao Longo do Tempo", className="mb-0")
                    ]),
                    dbc.CardBody([
                        get_under_development_chart("Gráfico de pressão temporal")
                    ])
                ], className="shadow-sm")
            ], md=8, className="mb-3"),

            # Status dos Compressores
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("🔧 Status", className="mb-0")
                    ]),
                    dbc.CardBody([
                        get_compressor_status()
                    ])
                ], className="shadow-sm")
            ], md=4, className="mb-3"),
        ]),

        # ========================================
        # SEÇÃO: DETALHES DOS COMPRESSORES
        # ========================================
        dbc.Row([
            dbc.Col([
                html.H4("Compressores Ativos", className="mt-4 mb-3")
            ])
        ]),

        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        get_compressors_table()
                    ])
                ], className="shadow-sm")
            ])
        ])
    ])


def get_under_development_chart(title):
    """
    Retorna um placeholder para gráfico em desenvolvimento
    """
    return html.Div([
        html.Div([
            html.I(
                className="bi bi-hourglass-split text-warning",
                style={"fontSize": "3rem"}
            )
        ], className="text-center mb-3"),
        html.H5(title, className="text-center text-muted"),
        html.P(
            "Gráfico em desenvolvimento",
            className="text-center text-muted small mb-0"
        )
    ], className="p-5 text-center", style={"minHeight": "300px", "display": "flex", "flexDirection": "column", "justifyContent": "center"})


def get_compressor_status():
    """
    Retorna status visual dos compressores
    """
    return html.Div([
        # Compressor 1
        html.Div([
            html.Div([
                html.I(className="bi bi-circle-fill text-success me-2"),
                html.Span("Compressor 1", className="fw-bold")
            ], className="d-flex align-items-center mb-2"),
            html.Div([
                html.Small("Status: ", className="text-muted"),
                dbc.Badge("Online", color="success", className="me-2")
            ]),
            html.Div([
                html.Small("Carga: ", className="text-muted"),
                html.Small("78%", className="fw-bold")
            ]),
            html.Hr()
        ]),

        # Compressor 2
        html.Div([
            html.Div([
                html.I(className="bi bi-circle-fill text-success me-2"),
                html.Span("Compressor 2", className="fw-bold")
            ], className="d-flex align-items-center mb-2"),
            html.Div([
                html.Small("Status: ", className="text-muted"),
                dbc.Badge("Online", color="success", className="me-2")
            ]),
            html.Div([
                html.Small("Carga: ", className="text-muted"),
                html.Small("65%", className="fw-bold")
            ]),
            html.Hr()
        ]),

        # Compressor 3
        html.Div([
            html.Div([
                html.I(className="bi bi-circle-fill text-warning me-2"),
                html.Span("Compressor 3", className="fw-bold")
            ], className="d-flex align-items-center mb-2"),
            html.Div([
                html.Small("Status: ", className="text-muted"),
                dbc.Badge("Standby", color="warning", className="me-2")
            ]),
            html.Div([
                html.Small("Carga: ", className="text-muted"),
                html.Small("0%", className="fw-bold")
            ]),
            html.Hr()
        ]),

        # Compressor 4
        html.Div([
            html.Div([
                html.I(className="bi bi-circle-fill text-secondary me-2"),
                html.Span("Compressor 4", className="fw-bold")
            ], className="d-flex align-items-center mb-2"),
            html.Div([
                html.Small("Status: ", className="text-muted"),
                dbc.Badge("Offline", color="secondary", className="me-2")
            ]),
            html.Div([
                html.Small("Carga: ", className="text-muted"),
                html.Small("0%", className="fw-bold")
            ])
        ]),
    ])


def get_compressors_table():
    """
    Retorna tabela detalhada de compressores
    """
    return dbc.Table([
        html.Thead([
            html.Tr([
                html.Th("Compressor"),
                html.Th("Tipo"),
                html.Th("Pressão"),
                html.Th("Vazão"),
                html.Th("Potência"),
                html.Th("Status"),
            ])
        ]),
        html.Tbody([
            html.Tr([
                html.Td([html.I(className="bi bi-circle-fill text-success me-2"), "C-001"]),
                html.Td("Parafuso"),
                html.Td("7.5 bar"),
                html.Td("145 m³/h"),
                html.Td("75 kW"),
                html.Td([dbc.Badge("Online", color="success", className="me-1")])
            ]),
            html.Tr([
                html.Td([html.I(className="bi bi-circle-fill text-success me-2"), "C-002"]),
                html.Td("Parafuso"),
                html.Td("7.2 bar"),
                html.Td("140 m³/h"),
                html.Td("81 kW"),
                html.Td([dbc.Badge("Online", color="success", className="me-1")])
            ]),
            html.Tr([
                html.Td([html.I(className="bi bi-circle-fill text-warning me-2"), "C-003"]),
                html.Td("Centrífugo"),
                html.Td("0 bar"),
                html.Td("0 m³/h"),
                html.Td("0 kW"),
                html.Td([dbc.Badge("Standby", color="warning", className="me-1")])
            ]),
            html.Tr([
                html.Td([html.I(className="bi bi-circle-fill text-secondary me-2"), "C-004"]),
                html.Td("Reserva"),
                html.Td("0 bar"),
                html.Td("0 m³/h"),
                html.Td("0 kW"),
                html.Td([dbc.Badge("Offline", color="secondary", className="me-1")])
            ]),
        ])
    ], striped=True, hover=True, responsive=True)
