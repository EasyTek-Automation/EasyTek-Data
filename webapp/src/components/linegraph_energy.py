# components/linegraph_energy.py

from dash import dcc, html
import dash_bootstrap_components as dbc

energygraph_card_layout = html.Div([
    dbc.Row([
        dbc.Col(
            html.H5("Monitoramento de Energia - Decapado Mecânico"),
            width="auto"
        ),
        dbc.Col(
            dbc.Button(
                "Exportar para Excel",
                id="btn-export-energy",
                className="ms-auto",
                size="sm"
            ),
            width="auto"
        )
    ], justify="between", align="center", style={"margin-bottom": "20px"}),

    # --- COMPONENTE DE DOWNLOAD (INVISÍVEL) ---
    # Ele vai receber os dados do callback para iniciar o download
    dcc.Download(id="download-energy-excel"),

    # --- GRÁFICO ---
    dcc.Loading(
        id="loading-energy-graph",
        type="circle",
        children=[
            dcc.Graph(
                id="energy-graph",
                style={'visibility': 'hidden', 'height': '450px'},
                config={"responsive": True, "displayModeBar": False, "showTips": False}
            )
        ]
    )
],
id="energy-card-graph",
className="report-section",
)
