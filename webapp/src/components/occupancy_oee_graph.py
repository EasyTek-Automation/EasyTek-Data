# components/occupancy_oee_graph.py
from dash import dcc, html
import dash_bootstrap_components as dbc # Importar dbc

occupancy_oee_card_layout = html.Div(
    [
        # --- CABEÇALHO COM TÍTULO E BOTÃO ---
        dbc.Row([
            dbc.Col(
                html.H5("Análise de OEE e Ocupação por Estado"),
                width="auto"
            ),
            dbc.Col(
                dbc.Button(
                    "Exportar para Excel",
                    id="btn-export-states", # ID único para este botão
                    className="ms-auto",
                    size="sm"
                    # A cor será definida dinamicamente
                ),
                width="auto"
            )
        ], justify="between", align="center", style={"margin-bottom": "15px"}),

        # --- COMPONENTE DE DOWNLOAD (INVISÍVEL) ---
        dcc.Download(id="download-states-excel"),

        # --- GRÁFICO ---
        dcc.Loading(
            id="loading-oee-occupancy-graph",
            type="circle",
            children=[
                dcc.Graph(
                    id="oee-occupancy-graph",
                    config={"responsive": True, "displayModeBar": False, "showTips": False},
                    style={"height": "350px"}
                )
            ]
        )
    ],
    id="oee-occupancy-card-graph",
    className="report-section",
    # O estilo que controla a visibilidade permanece
    style={"visibility": "hidden", "height": "400px"}
)
