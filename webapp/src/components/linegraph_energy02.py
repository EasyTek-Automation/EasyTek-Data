# src/components/linegraph_energy02.py

from dash import dcc, html
import dash_bootstrap_components as dbc

# Layout do card para o gráfico de CORRENTE
energygraph_card_layout02 = html.Div([
    dbc.Row([
        # Título do novo gráfico
        dbc.Col(
            html.H5("Monitoramento de Corrente - SE03"), 
            width="auto"
        ),
        # Botão de exportação para o novo gráfico (opcional, mas bom ter)
        dbc.Col(
            dbc.Button(
                "Exportar Corrente para Excel", 
                id="btn-export-current",  # <-- ID Alterado
                className="ms-auto", 
                size="sm"
            ), 
            width="auto"
        )
    ], justify="between", align="center", style={"margin-bottom": "20px"}),

    # Componente de download para o novo gráfico
    dcc.Download(id="download-current-excel"),  # <-- ID Alterado

    # Gráfico de Corrente
    dcc.Loading(
        id="loading-current-graph",  # <-- ID Alterado
        type="circle",
        children=[
            dcc.Graph(
                id="current-graph",  # <-- ID Principal Alterado
                style={'visibility': 'hidden', 'height': '450px'},
                config={"responsive": True, "displayModeBar": False, "showTips": False}
            )
        ]
    )
], 
id="current-card-graph",  # <-- ID Alterado
className="report-section",
)
