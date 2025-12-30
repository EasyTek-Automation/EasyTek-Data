# pages/states.py
from dash import html, dcc
import dash_bootstrap_components as dbc

# 1. Importe o layout do novo gráfico de energia
from src.components.linegraph_energy import energygraph_card_layout

# Layout da Página "States"
layout = dbc.Container([
    # --- CARD 1: GRÁFICO COM SWITCH ---
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    # Switch (sem alterações)
                    dbc.Row([
                        dbc.Col(
                            dbc.Label("Alternar Visualização de Gráfico"), 
                            width="auto", 
                            className="me-2"
                        ),
                        dbc.Col(
                            dbc.Switch(
                                id="graph-view-switch",
                                value=True,
                                className="mt-1"
                            ),
                            width="auto"
                        )
                    ], align="center", justify="end", className="mb-3"),

                    # --- INÍCIO DA MODIFICAÇÃO ---
                    # Contêiner com altura mínima pré-definida para evitar o "salto"
                    html.Div(
                        id="graph-container",
                        style={'minHeight': '400px'} # Reserva o espaço para o gráfico
                    )
                    # --- FIM DA MODIFICAÇÃO ---
                ])
            ], style={"margin": "10px", "width": "99%"})
        ], sm=12)
    ]),

    # --- CARD 2: NOVO GRÁFICO DE ENERGIA (sem alterações) ---
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    energygraph_card_layout
                ])
            ], style={"margin": "10px", "width": "99%"})
        ], sm=12)
    ])

], fluid=True)
