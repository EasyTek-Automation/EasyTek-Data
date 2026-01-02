# src/pages/production/alarms.py

from dash import html, dcc
import dash_bootstrap_components as dbc
from src.components.msgtable01 import messagestable_cards_layout

def layout():
    """
    Página dedicada ao histórico de alarmes
    """
    return dbc.Container([
        
        # ========================================
        # HEADER DA PÁGINA
        # ========================================
        dbc.Row([
            dbc.Col([
                html.H2("🔔 Histórico de Alarmes"),
                html.P(
                    "Registro completo de alarmes e mensagens do sistema",
                    className="text-muted"
                )
            ], width=8),
            dbc.Col([
                dbc.ButtonGroup([
                    dbc.Button(
                        [html.I(className="bi bi-download me-2"), "Exportar"],
                        color="primary",
                        size="sm"
                    ),
                    dbc.Button(
                        [html.I(className="bi bi-funnel me-2"), "Filtros"],
                        color="secondary",
                        size="sm",
                        outline=True,
                        id="btn-toggle-alarm-filters"
                    ),
                ])
            ], width=4, className="text-end")
        ], className="mb-4"),
        
        # ========================================
        # ESTATÍSTICAS RÁPIDAS
        # ========================================
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.H2("3", className="text-danger fw-bold mb-0"),
                            html.P("Alarmes Ativos", className="text-muted small mb-0")
                        ])
                    ])
                ], className="shadow-sm text-center")
            ], md=3),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.H2("12", className="text-warning fw-bold mb-0"),
                            html.P("Hoje", className="text-muted small mb-0")
                        ])
                    ])
                ], className="shadow-sm text-center")
            ], md=3),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.H2("87", className="text-info fw-bold mb-0"),
                            html.P("Esta Semana", className="text-muted small mb-0")
                        ])
                    ])
                ], className="shadow-sm text-center")
            ], md=3),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.H2("342", className="text-secondary fw-bold mb-0"),
                            html.P("Este Mês", className="text-muted small mb-0")
                        ])
                    ])
                ], className="shadow-sm text-center")
            ], md=3),
        ], className="mb-4"),
        
        # ========================================
        # PAINEL DE FILTROS (COLAPSÁVEL)
        # ========================================
        dbc.Collapse([
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Label("Período", className="form-label small fw-bold"),
                            dcc.Dropdown(
                                id="filter-alarm-period",
                                options=[
                                    {"label": "Última hora", "value": "1h"},
                                    {"label": "Últimas 24h", "value": "24h"},
                                    {"label": "Última semana", "value": "7d"},
                                    {"label": "Último mês", "value": "30d"},
                                    {"label": "Personalizado", "value": "custom"},
                                ],
                                value="24h",
                                clearable=False
                            )
                        ], md=3),
                        
                        dbc.Col([
                            html.Label("Máquina", className="form-label small fw-bold"),
                            dcc.Dropdown(
                                id="filter-alarm-machine",
                                options=[
                                    {"label": "Todas", "value": "all"},
                                    {"label": "Decapado", "value": "decapado"},
                                    {"label": "LCT08", "value": "lct08"},
                                    {"label": "LCL08", "value": "lcl08"},
                                    # Adicionar suas máquinas
                                ],
                                value="all",
                                multi=True
                            )
                        ], md=3),
                        
                        dbc.Col([
                            html.Label("Categoria", className="form-label small fw-bold"),
                            dcc.Dropdown(
                                id="filter-alarm-category",
                                options=[
                                    {"label": "Todas", "value": "all"},
                                    {"label": "Falha", "value": "falha"},
                                    {"label": "Manutenção", "value": "manutencao"},
                                    {"label": "Temperatura", "value": "temperatura"},
                                    {"label": "Elétrica", "value": "eletrica"},
                                ],
                                value="all",
                                multi=True
                            )
                        ], md=3),
                        
                        dbc.Col([
                            html.Label("Ações", className="form-label small fw-bold"),
                            dbc.Button(
                                [html.I(className="bi bi-check-circle me-2"), "Aplicar"],
                                color="primary",
                                size="sm",
                                className="w-100"
                            )
                        ], md=3, className="d-flex align-items-end")
                    ])
                ])
            ], className="mb-3 shadow-sm")
        ], id="collapse-alarm-filters", is_open=False),
        
        # ========================================
        # TABELA DE ALARMES
        # ========================================
        dbc.Row([
            dbc.Col([
                messagestable_cards_layout
            ])
        ])
        
    ], fluid=True, className="p-4")