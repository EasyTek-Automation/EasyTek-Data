from dash import dcc, html, Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
# --- Importações do Projeto ---
# Importa a função de publicação e o tópico do arquivo de configuração


from src.components.linegraph_temp import tempgraph_card_layout



# ========= Layout da Página Supervisório =========== #
layout = dbc.Container([



    dbc.Col([
        dbc.Row([
            dbc.Col([
                 dbc.Card([
                dbc.CardHeader("Definir Setpoint de Temperatura"),
                dbc.CardBody([
                    # O Input agora é a única peça central
                    dcc.Input(
                        id='input-valor-supervisorio-01',
                        type='number',
                        placeholder='--.-',
                        min=30, max=100, step=0.1,
                        className="display-digital input-box",
                        # Adicionamos um valor inicial para que ele não comece vazio
                        # Usaremos um dcc.Store para lembrar o último valor
                        value=None 
                    ),
                    
                    html.Div(style={'marginTop': '20px'}),

                    dbc.Button(
                        "Carregar Setpoint", 
                        id='botao-carregar-valor-01', 
                        color="primary", 
                        size="lg", 
                        className="w-100"
                    ),
                    
                   
                ])
            ], style={"margin": "10px"}),

            ], sm=6, md=4, lg=3),

            dbc.Col([
                dbc.Card([
                dbc.CardHeader("Definir Setpoint de Temperatura"),
                dbc.CardBody([
                    # O Input agora é a única peça central
                    dcc.Input(
                        id='input-valor-supervisorio-02',
                        type='number',
                        placeholder='--.-',
                        min=30, max=100, step=0.1,
                        className="display-digital input-box",
                        # Adicionamos um valor inicial para que ele não comece vazio
                        # Usaremos um dcc.Store para lembrar o último valor
                        value=None 
                    ),
                    
                    html.Div(style={'marginTop': '20px'}),

                    dbc.Button(
                        "Carregar Setpoint", 
                        id='botao-carregar-valor-02', 
                        color="primary", 
                        size="lg", 
                        className="w-100"
                    ),
                    
                   
                ])
            ], style={"margin": "10px"})

            ], sm=6, md=4, lg=3),

            dbc.Col([
                dbc.Card([
                dbc.CardHeader("Definir Setpoint de Temperatura"),
                dbc.CardBody([
                    # O Input agora é a única peça central
                    dcc.Input(
                        id='input-valor-supervisorio-03',
                        type='number',
                        placeholder='--.-',
                        min=30, max=100, step=0.1,
                        className="display-digital input-box",
                        # Adicionamos um valor inicial para que ele não comece vazio
                        # Usaremos um dcc.Store para lembrar o último valor
                        value=None 
                    ),
                    
                    html.Div(style={'marginTop': '20px'}),

                    dbc.Button(
                        "Carregar Setpoint", 
                        id='botao-carregar-valor-03', 
                        color="primary", 
                        size="lg", 
                        className="w-100"
                    ),
                    
                   
                ])
            ], style={"margin": "10px"})

            ], sm=6, md=4, lg=3),

             dbc.Col([
                dbc.Card([
                dbc.CardHeader("Definir Setpoint de Temperatura"),
                dbc.CardBody([
                    # O Input agora é a única peça central
                    dcc.Input(
                        id='input-valor-supervisorio-04',
                        type='number',
                        placeholder='--.-',
                        min=30, max=100, step=0.1,
                        className="display-digital input-box",
                        # Adicionamos um valor inicial para que ele não comece vazio
                        # Usaremos um dcc.Store para lembrar o último valor
                        value=None 
                    ),
                    
                    html.Div(style={'marginTop': '20px'}),

                    dbc.Button(
                        "Carregar Setpoint", 
                        id='botao-carregar-valor-04', 
                        color="primary", 
                        size="lg", 
                        className="w-100"
                    ),
                    
                   
                ])
            ], style={"margin": "10px"})

            ], sm=6, md=4, lg=3),
           

            
        ], justify="center"),
    ], sm=12),
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    tempgraph_card_layout
                ])
            ], style={"margin": "10px", "width": "99%"})
        ], sm=12)
    ])
], fluid=True)


