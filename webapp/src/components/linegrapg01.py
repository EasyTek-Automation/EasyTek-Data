# components/linegraph01.py
from dash import dcc, html
import dash_bootstrap_components as dbc

oeegraph_card_layout = html.Div([
    # --- CABEÇALHO COM TÍTULO E BOTÃO ---
    dbc.Row([
        # Coluna para o Título
        dbc.Col(
            html.H5("Monitoramento de OEE - Decapado Mecânico"),
            width="auto"
        ),
        # Coluna para o Botão de Exportação
        dbc.Col(
            dbc.Button(
                "Exportar para Excel",
                id="btn-export-oee", # ID específico para este botão
                className="ms-auto", # Alinha o botão à direita
                size="sm"
                # A cor será definida dinamicamente pelo callback
            ),
            width="auto"
        )
    ], justify="between", align="center", style={"margin-bottom": "20px"}),

    # --- COMPONENTE DE DOWNLOAD (INVISÍVEL) ---
    dcc.Download(id="download-oee-excel"),

    # --- GRÁFICO ---
    dcc.Loading(
        id="loading-oee-graph",
        type="circle",
        children=[
            dcc.Graph(
                id="oee-graph",
                style={'visibility': 'hidden', 'height': '450px'},
                config={"responsive": True, "displayModeBar": False, "showTips": False}
            )
        ]
    )
],
id="oee-card-graph",
className="report-section",
)
