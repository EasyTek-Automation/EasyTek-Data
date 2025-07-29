# components/occupancy_oee_graph02.py
from dash import dcc, html
import dash_bootstrap_components as dbc # Importar dbc

occupancy_oee_card_layout02 = html.Div(
    [
        # --- CABEÇALHO COM TÍTULO E BOTÃO ---
        dbc.Row([
            dbc.Col(
                # O título no código original estava repetido, ajustei para o título real do gráfico
                html.H5("Indicador OEE ao Longo do Tempo (com Status)"),
                width="auto"
            ),
            dbc.Col(
                dbc.Button(
                    "Exportar para Excel",
                    id="btn-export-states02", # ID único
                    className="ms-auto",
                    size="sm"
                    # Cor definida dinamicamente
                ),
                width="auto"
            )
        ], justify="between", align="center", style={"margin-bottom": "15px"}),

        # --- COMPONENTE DE DOWNLOAD (INVISÍVEL) ---
        dcc.Download(id="download-states02-excel"),

        # --- GRÁFICO ---
        dcc.Loading(
            id="loading-oee-occupancy-graph02",
            type="circle",
            children=[
                dcc.Graph(
                    id="oee-occupancy-graph02",
                    config={"responsive": True, "displayModeBar": False, "showTips": False},
                    style={"height": "350px"}
                )
            ]
        )
    ],
    id="oee-occupancy-card-graph02",
    className="report-section",
    style={"visibility": "hidden", "height": "400px"}
)
