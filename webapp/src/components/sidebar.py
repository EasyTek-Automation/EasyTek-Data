# src/components/sidebar.py

from dash import html
import dash_bootstrap_components as dbc


def create_sidebar_layout(app_instance):
    """
    Cria o layout da sidebar.
    Por enquanto está vazia (apenas logo), aguardando novos itens.
    """

    return dbc.Card([
        dbc.CardBody([
            # Logo
            html.Div([
                html.Img(
                    src="/assets/LogoAMG.png",
                    style={
                        "width": "80%",
                        "max-height": "120px",
                        "object-fit": "contain",
                        "margin": "0 auto 20px",
                        "display": "block"
                    }
                ),
                html.Hr(),
            ], style={"width": "100%"}),

            # Espaço para futuros itens
            html.Div([
                html.P(
                    "Menu em desenvolvimento...",
                    className="text-muted text-center small",
                    style={"marginTop": "20px"}
                ),
            ], id="sidebar-future-content"),

        ], style={"height": "calc(100% - 2rem)", "margin": "0"})
    ], id="sidebar-content", style={
        "flex": "1",
        "height": "100%",
        "visibility": "visible",
        "opacity": 1,
        "overflowY": "auto",
        "transition": "opacity 0.3s ease, visibility 0s linear 0.5s"
    })