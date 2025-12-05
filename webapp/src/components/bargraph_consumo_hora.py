# components/linegraph_consumption.py

from dash import dcc, html
import dash_bootstrap_components as dbc

consumptiongraph_card_layout = html.Div([
    dbc.Row([
        dbc.Col(
            html.H5("Monitoramento de Energia - SE03!"),
            width="auto"
        ),
        dbc.Col(
            dbc.Button(
                "Exportar para Excel",
                id="btn-export-consumption",
                className="ms-auto",
                size="sm"
            ),
            width="auto"
        )
    ], justify="between", align="center", style={"margin-bottom": "20px"}),

    # --- COMPONENTE DE DOWNLOAD (INVISÍVEL) ---
    # Ele vai receber os dados do callback para iniciar o download
    dcc.Download(id="download-consumption-excel"),

    # --- GRÁFICO ---
    dcc.Loading(
        id="loading-consumption-graph",
        type="circle",
        children=[
            dcc.Graph(
                id="hourly-consumption-graph",
                style={"visibility": "hidden", "height": "450px"},
                config={"responsive": True, "displayModeBar": False, "showTips": False},
            )
        ]
    )
],
id="consumption-card-graph",
className="report-section",
)


