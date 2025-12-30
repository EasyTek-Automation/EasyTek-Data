# src/pages/dashboards/home.py

from dash import html, dcc
import dash_bootstrap_components as dbc
from datetime import datetime

def layout():
    """
    Dashboard principal - Visão geral de toda a fábrica
    """
    return dbc.Container([
        
        # ========================================
        # HEADER DA PÁGINA
        # ========================================
        dbc.Row([
            dbc.Col([
                html.H2("🏭 Visão Geral da Fábrica"),
                html.P(
                    f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                    className="text-muted"
                )
            ], width=8),
            dbc.Col([
                dbc.ButtonGroup([
                    dbc.Button(
                        [html.I(className="bi bi-arrow-clockwise me-2"), "Atualizar"],
                        id="btn-refresh-home",
                        color="primary",
                        size="sm"
                    ),
                    dbc.Button(
                        [html.I(className="bi bi-funnel me-2"), "Filtros"],
                        color="secondary",
                        size="sm",
                        outline=True
                    ),
                ])
            ], width=4, className="text-end")
        ], className="mb-4"),
        
        # ========================================
        # CARDS DE STATUS RÁPIDO
        # ========================================
        dbc.Row([
            # Card: Produção
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.I(
                                className="bi bi-gear-wide-connected text-primary",
                                style={"fontSize": "2.5rem"}
                            ),
                        ], className="text-center mb-3"),
                        html.H6("Produção", className="text-center text-muted mb-2"),
                        html.H3(
                            "85.2%",
                            id="home-oee-value",
                            className="text-center text-success fw-bold mb-1"
                        ),
                        html.P("OEE Médio (24h)", className="text-center text-muted small mb-3"),
                        dbc.Button(
                            "Ver Detalhes →",
                            href="/production/oee",
                            size="sm",
                            color="primary",
                            outline=True,
                            className="w-100"
                        )
                    ])
                ], className="h-100 shadow-sm")
            ], md=3, className="mb-3"),
            
            # Card: Energia
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.I(
                                className="bi bi-lightning text-warning",
                                style={"fontSize": "2.5rem"}
                            ),
                        ], className="text-center mb-3"),
                        html.H6("Energia", className="text-center text-muted mb-2"),
                        html.H3(
                            "1.245 kW",
                            id="home-power-value",
                            className="text-center text-info fw-bold mb-1"
                        ),
                        html.P("Demanda Atual", className="text-center text-muted small mb-3"),
                        dbc.Button(
                            "Ver Detalhes →",
                            href="/energy",
                            size="sm",
                            color="warning",
                            outline=True,
                            className="w-100",
                            disabled=True  # ← Habilitar no Bife 4
                        )
                    ])
                ], className="h-100 shadow-sm")
            ], md=3, className="mb-3"),
            
            # Card: Alarmes
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.I(
                                className="bi bi-bell text-danger",
                                style={"fontSize": "2.5rem"}
                            ),
                        ], className="text-center mb-3"),
                        html.H6("Alarmes", className="text-center text-muted mb-2"),
                        html.H3(
                            "3",
                            id="home-alarms-count",
                            className="text-center text-danger fw-bold mb-1"
                        ),
                        html.P("Ativos Agora", className="text-center text-muted small mb-3"),
                        dbc.Button(
                            "Ver Alarmes →",
                            href="/production/alarms",
                            size="sm",
                            color="danger",
                            outline=True,
                            className="w-100",
                            disabled=True  # ← Habilitar no Bife 5
                        )
                    ])
                ], className="h-100 shadow-sm")
            ], md=3, className="mb-3"),
            
            # Card: Temperatura
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.I(
                                className="bi bi-thermometer-half text-info",
                                style={"fontSize": "2.5rem"}
                            ),
                        ], className="text-center mb-3"),
                        html.H6("Temperatura", className="text-center text-muted mb-2"),
                        html.H3(
                            "72.5°C",
                            id="home-temp-value",
                            className="text-center text-success fw-bold mb-1"
                        ),
                        html.P("Média Atual", className="text-center text-muted small mb-3"),
                        dbc.Button(
                            "Supervisório →",
                            href="/supervision",
                            size="sm",
                            color="info",
                            outline=True,
                            className="w-100"
                        )
                    ])
                ], className="h-100 shadow-sm")
            ], md=3, className="mb-3"),
        ], className="mb-4"),
        
        # ========================================
        # GRÁFICOS PRINCIPAIS
        # ========================================
        dbc.Row([
            # Gráfico: OEE das últimas 24h
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="bi bi-graph-up me-2"),
                        "OEE - Últimas 24 Horas"
                    ]),
                    dbc.CardBody([
                        dcc.Loading(
                            id="loading-home-oee",
                            type="circle",
                            children=[
                                dcc.Graph(
                                    id="graph-home-oee",
                                    config={"displayModeBar": False},
                                    style={"visibility": "hidden", "height": "250px"}  # ← CORRIGIDO: Inicia invisível
                                )
                            ]
                        )
                    ])
                ], className="shadow-sm")
            ], md=6, className="mb-3"),
            
            # Gráfico: Consumo de Energia
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="bi bi-lightning me-2"),
                        "Consumo de Energia - Hoje"
                    ]),
                    dbc.CardBody([
                        dcc.Loading(
                            id="loading-home-energy",
                            type="circle",
                            children=[
                                dcc.Graph(
                                    id="graph-home-energy",
                                    config={"displayModeBar": False},
                                    style={"visibility": "hidden", "height": "250px"}  # ← CORRIGIDO: Inicia invisível
                                )
                            ]
                        )
                    ])
                ], className="shadow-sm")
            ], md=6, className="mb-3"),
        ], className="mb-4"),
        
        # ========================================
        # TABELA DE ALARMES RECENTES
        # ========================================
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.Div([
                            html.I(className="bi bi-bell me-2"),
                            html.Span("Alarmes Recentes"),
                            dbc.Badge("3", color="danger", className="ms-2")
                        ], className="d-flex align-items-center")
                    ]),
                    dbc.CardBody([
                        dbc.Table([
                            html.Thead([
                                html.Tr([
                                    html.Th("Data/Hora"),
                                    html.Th("Máquina"),
                                    html.Th("Categoria"),
                                    html.Th("Descrição"),
                                    html.Th("Status"),
                                ])
                            ]),
                            html.Tbody(id="table-recent-alarms", children=[
                                # Dados mockados por enquanto
                                html.Tr([
                                    html.Td("30/12/2024 14:32"),
                                    html.Td("Decapado"),
                                    html.Td("Temperatura"),
                                    html.Td("Temp acima do setpoint"),
                                    html.Td(dbc.Badge("Ativo", color="danger"))
                                ]),
                                html.Tr([
                                    html.Td("30/12/2024 13:15"),
                                    html.Td("LCT08"),
                                    html.Td("Mecânica"),
                                    html.Td("Vibração anormal"),
                                    html.Td(dbc.Badge("Ativo", color="danger"))
                                ]),
                                html.Tr([
                                    html.Td("30/12/2024 11:48"),
                                    html.Td("PR01"),
                                    html.Td("Elétrica"),
                                    html.Td("Queda de tensão"),
                                    html.Td(dbc.Badge("Resolvido", color="success"))
                                ]),
                            ])
                        ], bordered=True, hover=True, responsive=True, size="sm", striped=True)
                    ])
                ], className="shadow-sm")
            ])
        ])
        
    ], fluid=True, className="p-4")