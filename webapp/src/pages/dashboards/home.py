# src/pages/dashboards/home.py

from dash import html, dcc
import dash_bootstrap_components as dbc
from datetime import datetime
from src.utils.demo_helpers import add_page_demo_warning, add_demo_badge_to_card_header
from src.components.demo_badge import demo_data_badge

def layout():
    """
    Dashboard principal - Visão geral de toda a fábrica
    """
    return dbc.Container([

        # ========================================
        # ALERTA DE DADOS DE DEMONSTRAÇÃO
        # ========================================
        add_page_demo_warning("/"),

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
                        # Badge de demonstração
                        html.Div([
                            demo_data_badge(size="sm")
                        ], className="text-end mb-2"),
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
                        # Badge de demonstração
                        html.Div([
                            demo_data_badge(size="sm")
                        ], className="text-end mb-2"),
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
                            className="w-100"
                            
                        )
                    ])
                ], className="h-100 shadow-sm")
            ], md=3, className="mb-3"),
            
            # Card: Alarmes
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        # Badge de demonstração
                        html.Div([
                            demo_data_badge(size="sm")
                        ], className="text-end mb-2"),
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
                            className="w-100"
                        )
                    ])
                ], className="h-100 shadow-sm")
            ], md=3, className="mb-3"),
            
            # Card: Temperatura
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        # Badge de demonstração
                        html.Div([
                            demo_data_badge(size="sm")
                        ], className="text-end mb-2"),
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
                    dbc.CardHeader(
                        add_demo_badge_to_card_header([
                            html.I(className="bi bi-graph-up me-2"),
                            "OEE - Últimas 24 Horas"
                        ], page_path="/")
                    ),
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
                    dbc.CardHeader(
                        add_demo_badge_to_card_header([
                            html.I(className="bi bi-lightning me-2"),
                            "Consumo de Energia - Hoje"
                        ], page_path="/")
                    ),
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
        # GRÁFICO TIME-SERIES OEE (PADRÃO LEGADO — MOCK)
        # ========================================
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(
                        add_demo_badge_to_card_header([
                            dbc.Row([
                                dbc.Col(
                                    html.Span([
                                        html.I(className="bi bi-activity me-2"),
                                        "Monitoramento de OEE — Decapado Mecânico (Mock)"
                                    ]),
                                    width="auto"
                                ),
                                dbc.Col(
                                    dbc.Button(
                                        "Exportar para Excel",
                                        id="btn-export-home-oee-mock",
                                        className="ms-auto",
                                        size="sm",
                                        color="primary"
                                    ),
                                    width="auto"
                                )
                            ], justify="between", align="center")
                        ], page_path="/")
                    ),
                    dbc.CardBody([
                        dcc.Download(id="download-home-oee-mock-excel"),
                        dcc.Loading(
                            id="loading-home-oee-mock",
                            type="circle",
                            children=[
                                dcc.Graph(
                                    id="graph-home-oee-mock",
                                    config={"responsive": True, "displayModeBar": False, "showTips": False},
                                    style={"visibility": "hidden", "height": "450px"}
                                )
                            ]
                        )
                    ])
                ], className="shadow-sm")
            ])
        ], className="mb-4"),

        # ========================================
        # POC — DRILLDOWN PARADAS (Anos → Meses → Dias → Tabela)
        # ========================================
        dcc.Store(id="store-drill-level", data="anos"),
        dcc.Store(id="store-drill-year", data=None),
        dcc.Store(id="store-drill-month", data=None),
        dcc.Store(id="store-drill-day", data=None),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(
                        add_demo_badge_to_card_header([
                            html.I(className="bi bi-bar-chart me-2"),
                            "Paradas por Ano (POC drilldown) — clique numa barra"
                        ], page_path="/")
                    ),
                    dbc.CardBody([
                        dcc.Graph(
                            id="graph-drill-years",
                            config={"displayModeBar": False},
                            style={"height": "320px"}
                        )
                    ])
                ], className="shadow-sm")
            ])
        ], className="mb-4"),
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="drill-modal-title")),
            dbc.ModalBody([
                html.Div([
                    dbc.Button(
                        [html.I(className="bi bi-arrow-left me-1"), "Voltar"],
                        id="btn-drill-back",
                        size="sm",
                        color="secondary",
                        outline=True,
                        className="mb-2"
                    ),
                ]),
                html.Div(id="drill-modal-content")
            ]),
            dbc.ModalFooter(
                dbc.Button("Fechar", id="btn-drill-close", className="ms-auto")
            ),
        ], id="modal-drill", size="xl", is_open=False, scrollable=True),

        # ========================================
        # TIMELINE EVOCON-STYLE (MOCK)
        # ========================================
        dcc.Store(id="store-evocon-granularity", storage_type="local", data="horas"),
        dcc.Store(id="store-evocon-offset",      storage_type="memory", data=0),
        dcc.Store(id="evocon-anim-dummy",        storage_type="memory"),
        dcc.Store(id="store-evocon-mtto-only",   storage_type="local", data=False),
        dcc.Interval(id="interval-evocon-now",   interval=30_000, n_intervals=0),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(
                        add_demo_badge_to_card_header([
                            html.I(className="bi bi-bar-chart-steps me-2", style={"color": "#0d6efd"}),
                            "Linha do Tempo de Estados — Visão Operacional (Mock)"
                        ], page_path="/")
                    ),
                    dbc.CardBody([
                        # Toolbar — granularidade + navegação
                        dbc.Row([
                            dbc.Col([
                                html.Small("Escala do eixo", className="text-muted fw-semibold d-block mb-1"),
                                dbc.ButtonGroup([
                                    dbc.Button(
                                        [html.I(className="bi bi-clock me-1"), "Horas"],
                                        id="btn-evocon-gran-horas", color="primary", size="sm",
                                        outline=False, n_clicks=0, className="evocon-gran-btn",
                                    ),
                                    dbc.Button(
                                        [html.I(className="bi bi-calendar-day me-1"), "Dias"],
                                        id="btn-evocon-gran-dias", color="primary", size="sm",
                                        outline=True, n_clicks=0, className="evocon-gran-btn",
                                    ),
                                ], className="shadow-sm"),
                            ], width="auto"),
                            dbc.Col([
                                html.Small("Navegação no tempo", className="text-muted fw-semibold d-block mb-1"),
                                dbc.ButtonGroup([
                                    dbc.Button("◀",    id="btn-evocon-prev",  color="secondary", outline=True, size="sm"),
                                    dbc.Button("Hoje", id="btn-evocon-today", color="info",      outline=True, size="sm"),
                                    dbc.Button("▶",    id="btn-evocon-next",  color="secondary", outline=True, size="sm"),
                                ]),
                            ], width="auto"),
                            dbc.Col([
                                html.Small("Período exibido", className="text-muted fw-semibold d-block mb-1"),
                                html.Div(
                                    id="label-evocon-period",
                                    className="fw-bold",
                                    style={"fontSize": "1rem", "color": "#212529", "lineHeight": "32px"},
                                ),
                            ]),
                        ], className="g-3 mb-2 align-items-end"),
                        html.Div([
                            html.Small("Legenda: ", className="text-muted me-2"),
                            dbc.Badge("Produção", color="success", className="me-1"),
                            dbc.Badge("Avaria", color="danger", className="me-1"),
                            dbc.Badge("Setup", color="warning", className="me-1"),
                            dbc.Badge("Logística", style={"backgroundColor": "#fd7e14"}, className="me-1"),
                            dbc.Badge("Refeição", color="secondary", className="me-1"),
                            dbc.Badge("MTTO Aut.", color="dark", className="me-1"),
                            dbc.Badge("Processo", style={"backgroundColor": "#e85d04"}, className="me-1"),
                        ], className="mb-2"),
                        dcc.Loading(
                            id="loading-home-evocon",
                            type="circle",
                            children=[
                                html.Div(
                                    id="evocon-anim-wrap",
                                    children=[
                                        dcc.Graph(
                                            id="graph-home-evocon-timeline",
                                            config={"responsive": True, "displayModeBar": False, "showTips": False},
                                            style={"visibility": "hidden", "height": "560px"}
                                        )
                                    ],
                                )
                            ]
                        )
                    ])
                ], className="shadow-sm")
            ])
        ], className="mb-4"),

        # ========================================
        # TABELA DE ALARMES RECENTES
        # ========================================
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(
                        add_demo_badge_to_card_header([
                            html.Div([
                                html.I(className="bi bi-bell me-2"),
                                html.Span("Alarmes Recentes"),
                                dbc.Badge("3", color="danger", className="ms-2")
                            ], className="d-flex align-items-center")
                        ], page_path="/")
                    ),
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