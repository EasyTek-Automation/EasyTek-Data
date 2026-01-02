# src/pages/energy/overview.py

from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
from src.components.linegraph_energy import energygraph_card_layout
from src.components.linegraph_energy02 import energygraph_card_layout02
from src.components.bargraph_consumo_hora import consumptiongraph_card_layout

def layout():
    """
    Página de visão geral de energia
    Consolida todos os gráficos de energia em um só lugar
    """
    return dbc.Container([
        
        # ========================================
        # HEADER DA PÁGINA
        # ========================================
        dbc.Row([
            dbc.Col([
                html.H2("⚡ Gestão de Energia"),
                html.P(
                    "Monitoramento em tempo real de todas as subestações",
                    className="text-muted"
                )
            ], width=8),
            dbc.Col([
                dbc.ButtonGroup([
                    dbc.Button(
                        [html.I(className="bi bi-download me-2"), "Exportar Tudo"],
                        color="success",
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
        # TABS PARA DIFERENTES SUBESTAÇÕES
        # ========================================
        dbc.Tabs([
            dbc.Tab(label="🏢 Todas", tab_id="all"),
            dbc.Tab(label="SE00 - Entrada", tab_id="se00"),
            dbc.Tab(label="SE01 - Decapado", tab_id="se01"),
            dbc.Tab(label="SE02 - Prensas / Utilidades", tab_id="se02"),
            dbc.Tab(label="SE03 - Cortadeiras Transversais/Longitudinais", tab_id="se03"),
            dbc.Tab(label="SE04 - LWB", tab_id="se04"),
        ], id="energy-tabs", active_tab="all", className="mb-3"),  # ← MUDEI DEFAULT PARA se03
        
        # ========================================
        # CONTEÚDO DA TAB ATIVA (Dinâmico via callback)
        # ========================================
        html.Div(id="energy-tab-content")
        
    ], fluid=True, className="p-4")


def get_se03_content():
    """
    Retorna o conteúdo completo da SE03 (já existente)
    """
    return html.Div([
        # Gráficos de Tensão e Corrente lado a lado
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([energygraph_card_layout])
                ], className="shadow-sm")
            ], xs=12, md=6, className="mb-3"),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([energygraph_card_layout02])
                ], className="shadow-sm")
            ], xs=12, md=6, className="mb-3"),
        ], className="g-2 mb-3"),
        
        # Gráfico de Consumo por Hora (largura total)
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([consumptiongraph_card_layout])
                ], className="shadow-sm")
            ])
        ]),
        
        # ========================================
        # SEÇÃO: CARDS DE QUALIDADE DE ENERGIA
        # ========================================
        dbc.Row([
            dbc.Col([
                html.H4("Qualidade de Energia", className="mt-4 mb-3")
            ])
        ]),
        
        dbc.Row([
            # Fator de Potência
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.I(
                                className="bi bi-speedometer text-info",
                                style={"fontSize": "2rem"}
                            )
                        ], className="text-center mb-2"),
                        html.H6("Fator de Potência", className="text-center"),
                        html.H4(
                            "0.92",
                            className="text-center text-success fw-bold mb-0"
                        ),
                        html.P("FP Médio", className="text-center text-muted small")
                    ])
                ], className="shadow-sm h-100")
            ], md=3, className="mb-3"),
            
            # Demanda Máxima
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.I(
                                className="bi bi-arrow-up-circle text-warning",
                                style={"fontSize": "2rem"}
                            )
                        ], className="text-center mb-2"),
                        html.H6("Demanda Máxima", className="text-center"),
                        html.H4(
                            "1.450 kW",
                            className="text-center text-warning fw-bold mb-0"
                        ),
                        html.P("Pico do Dia", className="text-center text-muted small")
                    ])
                ], className="shadow-sm h-100")
            ], md=3, className="mb-3"),
            
            # THD Tensão
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.I(
                                className="bi bi-activity text-danger",
                                style={"fontSize": "2rem"}
                            )
                        ], className="text-center mb-2"),
                        html.H6("THD Tensão", className="text-center"),
                        html.H4(
                            "2.8%",
                            className="text-center text-success fw-bold mb-0"
                        ),
                        html.P("Distorção Harmônica", className="text-center text-muted small")
                    ])
                ], className="shadow-sm h-100")
            ], md=3, className="mb-3"),
            
            # Consumo Total Hoje
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.I(
                                className="bi bi-bar-chart text-primary",
                                style={"fontSize": "2rem"}
                            )
                        ], className="text-center mb-2"),
                        html.H6("Consumo Hoje", className="text-center"),
                        html.H4(
                            "18.240 kWh",
                            className="text-center text-primary fw-bold mb-0"
                        ),
                        html.P("Total Acumulado", className="text-center text-muted small")
                    ])
                ], className="shadow-sm h-100")
            ], md=3, className="mb-3"),
        ])
    ])


def get_under_development_content(tab_name):
    """
    Retorna conteúdo "Em Desenvolvimento" para outras tabs
    """
    tab_titles = {
        "all": "Visão Consolidada de Todas as Subestações",
        "se00": "Subestação SE00 - Entrada",
        "se01": "Subestação SE01 - Decapado",
        "se02": "Subestação SE02 - Prensas / Utilidades",
        "se04": "Subestação SE04 - LWB"
    }
    
    title = tab_titles.get(tab_name, "Subestação")
    
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    # Ícone grande
                    html.Div([
                        html.I(
                            className="bi bi-cone-striped",
                            style={
                                "fontSize": "5rem",
                                "color": "#ffc107"
                            }
                        )
                    ], className="text-center mb-4"),
                    
                    # Título
                    html.H3(
                        f"{title} - Em Desenvolvimento",
                        className="text-center mb-3",
                        style={"fontWeight": "600"}
                    ),
                    
                    # Mensagem
                    html.P(
                        "O monitoramento desta subestação está sendo configurado e "
                        "estará disponível em breve.",
                        className="text-center text-muted mb-4",
                        style={"fontSize": "1.1rem"}
                    ),
                    
                    # Badge de status
                    html.Div([
                        dbc.Badge(
                            [
                                html.I(className="bi bi-hourglass-split me-2"),
                                "Em Desenvolvimento"
                            ],
                            color="warning",
                            className="px-4 py-2",
                            style={"fontSize": "0.9rem"}
                        )
                    ], className="text-center mb-4"),
                    
                    # Linha separadora
                    html.Hr(),
                    
                    # Informações adicionais
                    dbc.Row([
                        dbc.Col([
                            html.Div([
                                html.I(className="bi bi-lightning-charge text-warning", 
                                      style={"fontSize": "2rem"}),
                                html.P("Medidores em instalação", className="mt-2 mb-0 small text-muted")
                            ], className="text-center")
                        ], width=4),
                        dbc.Col([
                            html.Div([
                                html.I(className="bi bi-graph-up text-info", 
                                      style={"fontSize": "2rem"}),
                                html.P("Dashboards em construção", className="mt-2 mb-0 small text-muted")
                            ], className="text-center")
                        ], width=4),
                        dbc.Col([
                            html.Div([
                                html.I(className="bi bi-clock-history text-success", 
                                      style={"fontSize": "2rem"}),
                                html.P("Em breve disponível", className="mt-2 mb-0 small text-muted")
                            ], className="text-center")
                        ], width=4),
                    ], className="mt-3"),
                    
                ], className="p-5")
            ], className="shadow-lg", style={"borderRadius": "15px"})
            
        ], width={"size": 10, "offset": 1}, lg={"size": 8, "offset": 2})
    ], className="mt-4")