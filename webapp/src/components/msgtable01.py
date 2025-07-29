# components/msgtable01.py
from dash import dcc, html
import dash_bootstrap_components as dbc
from dash import dash_table

messagestable_cards_layout = html.Div(
    [
        # --- INÍCIO DA MODIFICAÇÃO ---
        # Envolvemos o conteúdo (o CardBody) em um dcc.Loading.
        dcc.Loading(
            id="loading-messages-table",
            type="circle",
            children=[
                dbc.CardBody([
                    html.H5("Histórico de Alarmes e Mensagens", style={"margin-bottom": "20px"}),
                    dash_table.DataTable(
                        id="data-table",
                        columns=[],
                        data=[],
                        page_size=10,
                        style_header={
                            'backgroundColor': 'lightgrey',
                            'fontWeight': 'bold',
                            'textAlign': 'center'
                        },
                    )
                ])
            ]
        )
        # --- FIM DA MODIFICAÇÃO ---
    ],
    id="messagestable-cards-layout",
    className="report-section",
    # 1. O estilo inicial esconde o componente, mas reserva espaço.
    style={"visibility": "hidden", "min-height": "400px"} # Ajuste a altura mínima conforme necessário
)
