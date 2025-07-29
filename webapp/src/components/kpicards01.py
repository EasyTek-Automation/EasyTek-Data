# components/kpicards01.py
from dash import dcc, html
import dash_bootstrap_components as dbc

kpicards_cards_layout = html.Div(
    [
        # --- INÍCIO DA MODIFICAÇÃO ---
        # Envolvemos o conteúdo dos cards (o CardBody) em um dcc.Loading.
        dcc.Loading(
            id="loading-kpi-cards",
            type="circle", # ou "dots", "default", etc.
            children=[
                # O conteúdo original dos cards vai aqui dentro.
                dbc.CardBody([
                    html.H5("Principais Indicadores", style={"margin-bottom": "20px"}),
                    dbc.Row([
                        dbc.Col(dbc.Card(
                            dbc.CardBody([
                                html.H6("OEE Médio", className="card-title text-center"),
                                # Usamos um Div como placeholder para o valor
                                html.H5(id="card-media-oee", className="card-text text-center text-primary fw-bold"),
                                html.Small("Overal Equipment Effectiveness", className="text-muted text-center d-block")
                            ]), className="text-center"
                        ), sm=6),
                        dbc.Col(dbc.Card(
                            dbc.CardBody([
                                html.H6("Disponibilidade Média", className="card-title text-center"),
                                html.H5(id="card-media-disp", className="card-text text-center text-success fw-bold"),
                                html.Small("Disponibilidade da Máquina", className="text-muted text-center d-block")
                            ]), className="text-center"
                        ), sm=6),
                        dbc.Col(dbc.Card(
                            dbc.CardBody([
                                html.H6("Desempenho Médio", className="card-title text-center"),
                                html.H5(id="card-media-desemp", className="card-text text-center text-info fw-bold"),
                                html.Small("Performance de Produção", className="text-muted text-center d-block")
                            ]), className="text-center"
                        ), sm=6),
                        dbc.Col(dbc.Card(
                            dbc.CardBody([
                                html.H6("Qualidade Média", className="card-title text-center"),
                                html.H5(id="card-media-quali", className="card-text text-center text-warning fw-bold"),
                                html.Small("Qualidade do Produto", className="text-muted text-center d-block")
                            ]), className="text-center"
                        ), sm=6),
                    ], id="kpi-cards-row", className="g-4")
                ])
            ]
        )
        # --- FIM DA MODIFICAÇÃO ---
    ],
    id="kpi-main-card",
    className="report-section",
    # 1. O estilo inicial esconde o componente, mas reserva espaço.
    style={"visibility": "hidden", "min-height": "250px"} # Ajuste a altura mínima conforme necessário
)
