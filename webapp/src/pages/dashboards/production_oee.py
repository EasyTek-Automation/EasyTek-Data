# pages/dashboard.py
from dash import dcc, html
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta

# Importe seus componentes existentes
from src.components.linegrapg01 import oeegraph_card_layout
from src.components.linegraph_energy import energygraph_card_layout
from src.components.linegraph_energy02 import energygraph_card_layout02
from src.components.bargraph_consumo_hora import consumptiongraph_card_layout
from src.components.kpicards01 import kpicards_cards_layout
from src.components.msgtable01 import messagestable_cards_layout

# ========= Layout da Página Dashboard =========== #
layout = dbc.Container([
    dbc.Col([ # Esta coluna agora representa o conteúdo principal da página
    dbc.Row(
            [
                dbc.Col(
                    dbc.Card([
                        dbc.CardBody(
                            [
                                energygraph_card_layout
                            ]
                        )
            ],style={"margin-top": "10px"}),
                    xs=12,  # ocupa 12 colunas no mobile
                    md=6,   # ocupa metade da tela a partir de md (>= 768px)
                ),
                dbc.Col(
                    dbc.Card([
                        dbc.CardBody(
                            [
                                energygraph_card_layout02
                            ]
                        )
            ],style={"margin-top": "10px"}),
                    xs=12,
                    md=6,
                ),
            ],
            className="g-2",  # espaço (gutter) entre as colunas
        ),

    #############
    

    ###########
    dbc.Row([
        dbc.Card([
            dbc.CardBody([
                consumptiongraph_card_layout

              


            ])

        ],style={"margin": "10px", "width":"99%"})
        
    ]),
  
], 
sm=12,

)
    ], fluid=True)