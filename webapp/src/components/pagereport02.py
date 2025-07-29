# components/pagereport01.py
from dash import html, dcc
import dash_bootstrap_components as dbc

from src.components.linegrapg01 import oeegraph_card_layout
from src.components.kpicards01 import kpicards_cards_layout
from src.components.msgtable01 import messagestable_cards_layout

folha2_content = html.Div(
    className="page",
    children=[
        html.Div(
            className="subpage",
            children=[
                
                
            ],
        )
    ],
)
