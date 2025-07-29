# components/linegraph_energy.py

from dash import dcc, html
import dash_bootstrap_components as dbc

tempgraph_card_layout = html.Div([
    dbc.Row([
        dbc.Col(
            html.H5("Monitoramento de Temperatura"),
            width="auto"
        ),
        dbc.Col(
            dbc.Button(
                "Exportar para Excel",
                id="btn-export-temp",
                className="ms-auto",
                size="sm"
            ),
            width="auto"
        )
    ], justify="between", align="center", style={"margin-bottom": "20px"}),

    # --- COMPONENTE DE DOWNLOAD (INVISÍVEL) ---
    # Ele vai receber os dados do callback para iniciar o download
    dcc.Download(id="download-temp-excel"),

    # --- GRÁFICO ---
    dcc.Loading(
        id="loading-temp-graph",
        type="circle",
        children=[
            dcc.Graph(
                id="temp-graph",
                style={'visibility': 'hidden', 'height': '450px'},
                config={"responsive": True, "displayModeBar": False, "showTips": False}
            )
        ]
    )
],
id="temp-card-graph",
className="report-section",
)
