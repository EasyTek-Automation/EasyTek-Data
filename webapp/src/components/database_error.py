"""
Componente de erro amigável para falhas de conexão com o MongoDB
"""

from dash import html, dcc
import dash_bootstrap_components as dbc


def create_database_error_layout(error_message=None, show_retry=True):
    """
    Cria layout amigável informando que o banco de dados está offline.

    Args:
        error_message (str, optional): Mensagem de erro técnica
        show_retry (bool): Se deve exibir botão "Tentar Novamente"

    Returns:
        dbc.Container: Componente Dash com a mensagem de erro
    """

    return dbc.Container([
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        # Ícone de aviso
                        html.Div([
                            html.I(
                                className="bi bi-database-exclamation",
                                style={
                                    "fontSize": "64px",
                                    "color": "#dc3545"
                                }
                            )
                        ], className="text-center mb-4"),

                        # Título
                        html.H3(
                            "🔌 Banco de Dados Offline",
                            className="text-center text-danger mb-3"
                        ),

                        # Mensagem principal
                        html.P(
                            "O sistema não conseguiu conectar ao MongoDB. "
                            "Isso pode acontecer se o serviço estiver parado ou inacessível.",
                            className="text-center text-muted mb-4"
                        ),

                        # Detalhes técnicos (colapsável)
                        dbc.Collapse([
                            dbc.Alert([
                                html.H6("📋 Detalhes Técnicos:", className="mb-2"),
                                html.Pre(
                                    error_message or "Nenhum detalhe disponível",
                                    style={
                                        "fontSize": "12px",
                                        "whiteSpace": "pre-wrap",
                                        "wordWrap": "break-word"
                                    }
                                )
                            ], color="warning", className="mt-3")
                        ], id="collapse-db-error-details", is_open=False),

                        # Botões de ação
                        html.Div([
                            dbc.ButtonGroup([
                                dbc.Button(
                                    [html.I(className="bi bi-arrow-clockwise me-2"), "Tentar Novamente"],
                                    id="btn-retry-database",
                                    color="primary",
                                    size="lg",
                                    className="me-2"
                                ) if show_retry else None,

                                dbc.Button(
                                    [html.I(className="bi bi-info-circle me-2"), "Detalhes"],
                                    id="btn-toggle-db-error-details",
                                    color="secondary",
                                    outline=True,
                                    size="lg"
                                )
                            ])
                        ], className="text-center mb-4"),

                        # Instruções
                        html.Div([
                            html.H6("💡 O que fazer:", className="mb-2"),
                            html.Ul([
                                html.Li("Verifique se o serviço MongoDB está rodando"),
                                html.Li("Confirme a configuração no arquivo .env (MONGO_URI, DB_NAME)"),
                                html.Li("Tente clicar em 'Tentar Novamente' após reiniciar o MongoDB"),
                                html.Li("Entre em contato com o suporte se o problema persistir")
                            ], className="text-start")
                        ], className="mt-4 p-3 bg-light rounded")
                    ])
                ], className="shadow-lg border-danger")
            ], width={"size": 8, "offset": 2}, lg={"size": 6, "offset": 3})
        ], className="mt-5")
    ], fluid=True, className="p-4")


def create_inline_database_error(component_name="este componente", error_message=None):
    """
    Cria mensagem de erro inline (menor) para usar dentro de cards/gráficos.

    Args:
        component_name (str): Nome do componente que falhou
        error_message (str, optional): Mensagem de erro técnica

    Returns:
        dbc.Alert: Componente de alerta compacto
    """

    return dbc.Alert([
        html.Div([
            html.I(className="bi bi-database-exclamation me-2"),
            html.Strong("Banco de Dados Offline")
        ], className="d-flex align-items-center mb-2"),

        html.P(
            f"Não foi possível carregar os dados para {component_name}. "
            "O MongoDB está inacessível no momento.",
            className="mb-2 small"
        ),

        dbc.Collapse([
            html.Hr(),
            html.Small([
                html.Strong("Erro: "),
                error_message or "Detalhes não disponíveis"
            ], className="text-muted")
        ], id=f"collapse-inline-error-{component_name.replace(' ', '-')}", is_open=False),

        html.Div([
            dbc.Button(
                "Detalhes",
                id=f"btn-toggle-inline-error-{component_name.replace(' ', '-')}",
                color="link",
                size="sm",
                className="p-0"
            )
        ], className="mt-2")
    ], color="danger", className="mb-0")


# Callback para toggle dos detalhes (deve ser registrado nos callbacks)
def get_database_error_callbacks():
    """
    Retorna lista de callbacks para os componentes de erro.

    Returns:
        list: Lista de tuplas (callback_function, inputs, outputs)
    """
    from dash import Input, Output, State

    callbacks = []

    # Callback para toggle do collapse de detalhes (página inteira)
    def toggle_details_callback(app):
        @app.callback(
            Output("collapse-db-error-details", "is_open"),
            Input("btn-toggle-db-error-details", "n_clicks"),
            State("collapse-db-error-details", "is_open"),
            prevent_initial_call=True
        )
        def toggle_collapse(n_clicks, is_open):
            if n_clicks:
                return not is_open
            return is_open

        callbacks.append(toggle_collapse)

    return callbacks
