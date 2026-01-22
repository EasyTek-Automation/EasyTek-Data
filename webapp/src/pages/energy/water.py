# src/pages/energy/water.py

"""
Página de Monitoramento de Água
Monitoramento de consumo de água industrial
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
from src.utils.demo_helpers import add_demo_badge_to_card_header


def layout():
    """
    Página de monitoramento de consumo de água
    """
    return dbc.Container([

        # ========================================
        # HEADER DA PÁGINA
        # ========================================
        dbc.Row([
            dbc.Col([
                html.H2("💧 Monitoramento de Água"),
                html.P(
                    "Monitoramento em tempo real do consumo de água industrial",
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
        # TABS PARA DIFERENTES ÁREAS/MEDIDORES
        # ========================================
        dbc.Tabs([
            dbc.Tab(label="🏭 Visão Geral", tab_id="overview"),
            dbc.Tab(label="📊 Medidores", tab_id="meters"),
            dbc.Tab(label="💰 Custos", tab_id="costs"),
            dbc.Tab(label="📈 Histórico", tab_id="history"),
        ], id="water-tabs", active_tab="overview", className="mb-3"),

        # ========================================
        # CONTEÚDO DA TAB ATIVA
        # ========================================
        html.Div(id="water-tab-content", children=[get_overview_content()])

    ], fluid=True, className="p-4")


def get_overview_content():
    """
    Retorna o conteúdo da visão geral de água
    """
    return html.Div([
        # ========================================
        # SEÇÃO: CARDS DE KPIs PRINCIPAIS
        # ========================================
        dbc.Row([
            # Consumo Total Hoje
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(
                        add_demo_badge_to_card_header(
                            "",
                            page_path="/utilities/water",
                            size="sm"
                        ),
                        className="bg-transparent"
                    ),
                    dbc.CardBody([
                        html.Div([
                            html.I(
                                className="bi bi-droplet-fill text-primary",
                                style={"fontSize": "2.5rem"}
                            )
                        ], className="text-center mb-2"),
                        html.H6("Consumo Hoje", className="text-center"),
                        html.H3(
                            "1.245 m³",
                            className="text-center text-primary fw-bold mb-0"
                        ),
                        html.P("Total Acumulado", className="text-center text-muted small")
                    ])
                ], className="shadow-sm h-100")
            ], md=3, className="mb-3"),

            # Vazão Atual
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(
                        add_demo_badge_to_card_header(
                            "",
                            page_path="/utilities/water",
                            size="sm"
                        ),
                        className="bg-transparent"
                    ),
                    dbc.CardBody([
                        html.Div([
                            html.I(
                                className="bi bi-speedometer2 text-info",
                                style={"fontSize": "2.5rem"}
                            )
                        ], className="text-center mb-2"),
                        html.H6("Vazão Atual", className="text-center"),
                        html.H3(
                            "52 m³/h",
                            className="text-center text-info fw-bold mb-0"
                        ),
                        html.P("Taxa Instantânea", className="text-center text-muted small")
                    ])
                ], className="shadow-sm h-100")
            ], md=3, className="mb-3"),

            # Custo Estimado Hoje
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(
                        add_demo_badge_to_card_header(
                            "",
                            page_path="/utilities/water",
                            size="sm"
                        ),
                        className="bg-transparent"
                    ),
                    dbc.CardBody([
                        html.Div([
                            html.I(
                                className="bi bi-currency-dollar text-success",
                                style={"fontSize": "2.5rem"}
                            )
                        ], className="text-center mb-2"),
                        html.H6("Custo Estimado", className="text-center"),
                        html.H3(
                            "R$ 12.450",
                            className="text-center text-success fw-bold mb-0"
                        ),
                        html.P("Valor do Dia", className="text-center text-muted small")
                    ])
                ], className="shadow-sm h-100")
            ], md=3, className="mb-3"),

            # Eficiência vs Meta
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(
                        add_demo_badge_to_card_header(
                            "",
                            page_path="/utilities/water",
                            size="sm"
                        ),
                        className="bg-transparent"
                    ),
                    dbc.CardBody([
                        html.Div([
                            html.I(
                                className="bi bi-bullseye text-warning",
                                style={"fontSize": "2.5rem"}
                            )
                        ], className="text-center mb-2"),
                        html.H6("Meta do Mês", className="text-center"),
                        html.H3(
                            "87%",
                            className="text-center text-warning fw-bold mb-0"
                        ),
                        html.P("Atingido", className="text-center text-muted small")
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
            # Gráfico de Consumo ao Longo do Tempo
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("📈 Consumo ao Longo do Tempo", className="mb-0")
                    ]),
                    dbc.CardBody([
                        get_under_development_chart("Gráfico de consumo temporal")
                    ])
                ], className="shadow-sm")
            ], md=8, className="mb-3"),

            # Distribuição por Área
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("🏭 Por Área", className="mb-0")
                    ]),
                    dbc.CardBody([
                        get_under_development_chart("Distribuição por área")
                    ])
                ], className="shadow-sm")
            ], md=4, className="mb-3"),
        ]),

        # ========================================
        # SEÇÃO: MEDIDORES ATIVOS
        # ========================================
        dbc.Row([
            dbc.Col([
                html.H4("Medidores Ativos", className="mt-4 mb-3")
            ])
        ]),

        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        get_meters_table()
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


def get_meters_table():
    """
    Retorna tabela de medidores
    """
    return dbc.Table([
        html.Thead([
            html.Tr([
                html.Th("Medidor"),
                html.Th("Localização"),
                html.Th("Vazão Atual"),
                html.Th("Consumo Hoje"),
                html.Th("Status"),
            ])
        ]),
        html.Tbody([
            html.Tr([
                html.Td([html.I(className="bi bi-circle-fill text-success me-2"), "M-001"]),
                html.Td("Entrada Principal"),
                html.Td("52 m³/h"),
                html.Td("1.245 m³"),
                html.Td([dbc.Badge("Online", color="success", className="me-1")])
            ]),
            html.Tr([
                html.Td([html.I(className="bi bi-circle-fill text-success me-2"), "M-002"]),
                html.Td("Linha de Produção 1"),
                html.Td("18 m³/h"),
                html.Td("432 m³"),
                html.Td([dbc.Badge("Online", color="success", className="me-1")])
            ]),
            html.Tr([
                html.Td([html.I(className="bi bi-circle-fill text-success me-2"), "M-003"]),
                html.Td("Linha de Produção 2"),
                html.Td("15 m³/h"),
                html.Td("360 m³"),
                html.Td([dbc.Badge("Online", color="success", className="me-1")])
            ]),
            html.Tr([
                html.Td([html.I(className="bi bi-circle-fill text-warning me-2"), "M-004"]),
                html.Td("Torre de Resfriamento"),
                html.Td("8 m³/h"),
                html.Td("192 m³"),
                html.Td([dbc.Badge("Alerta", color="warning", className="me-1")])
            ]),
            html.Tr([
                html.Td([html.I(className="bi bi-circle-fill text-success me-2"), "M-005"]),
                html.Td("Utilidades"),
                html.Td("11 m³/h"),
                html.Td("261 m³"),
                html.Td([dbc.Badge("Online", color="success", className="me-1")])
            ]),
        ])
    ], striped=True, hover=True, responsive=True)
