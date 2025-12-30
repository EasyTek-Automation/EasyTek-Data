# pages/register.py

from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
from dash_bootstrap_templates import ThemeSwitchAIO, template_from_url
import dash

from src.app import app
from src.database.connection import get_user_by_username, get_user_by_email, save_user

from src.config.theme_config import URL_THEME_MINTY, URL_THEME_DARKLY

def render_layout():
    card_style = {
        'width': '400px',
        'padding': '25px',
        'margin': '50px auto',
        'background-color': 'rgba(255, 255, 255, 0.1)',
        'border': '1px solid rgba(255, 255, 255, 0.2)',
        'border-radius': '15px',
        'box-shadow': '0 4px 30px rgba(0, 0, 0, 0.1)',
        'backdrop-filter': 'blur(5px)',
        '-webkit-backdrop-filter': 'blur(5px)',
    }

    register_layout = dbc.Container([
        dcc.Location(id='register-url', refresh=True),
        dcc.Store(id='theme-store', storage_type='local'),
        dbc.Row(
            dbc.Col(
                dbc.Card([
                    html.Div(
                        [
                            html.Img(src="/assets/LogoAMG.png", style={"height": "40px"}),
                            # Dentro do layout de register.py
                            ThemeSwitchAIO(aio_id="theme", themes=[URL_THEME_MINTY, URL_THEME_DARKLY]),

                        ],
                        className="d-flex justify-content-between align-items-center"
                    ),
                    html.Hr(className="my-4"),
                    
                    # CORREÇÃO: Removida a classe 'text-white'
                    html.H2("Criar Conta", className="text-center mb-4"),
                    
                    dbc.Input(id="user_register", placeholder="Usuário", type="text", className="mb-3"),
                    dbc.Input(id="email_register", placeholder="E-mail", type="email", className="mb-3"),
                    dbc.Input(id="pwd_register", placeholder="Senha", type="password", className="mb-3"),
                    dbc.Input(id="level_register", placeholder="Nível de Acesso (1, 2 ou 3)", type="number", min=1, max=3, step=1, className="mb-3"),
                    
                    dbc.Button("Registrar", id='register-button', color="success", className="w-100"),
                    
                    html.Div(id="register-error-message", className="text-danger text-center mt-3"),
                    
                    html.Div([
                        # CORREÇÃO: Trocada 'text-white-50' por 'text-muted'
                        dcc.Link("Já tem uma conta? Faça login", href="/login", className="text-muted"),
                    ], className="text-center mt-3"),

                    html.Hr(className="mt-4"),
                    html.Div(
                        [
                            html.Span("Powered by:", style={'fontSize': '0.8rem', 'color': '#aaa', 'marginRight': '10px'}),
                            html.Img(src="/assets/LogoAMG.png", style={"height": "25px"})
                        ],
                        className="d-flex justify-content-end align-items-center"
                    )

                ], body=True, style=card_style),
                width=12
            )
        )
    ], fluid=True, className=template_from_url(URL_THEME_DARKLY), id="register-container",
       style={"height": "100vh", "display": "flex", "align-items": "center", "justify-content": "center"})
    
    return register_layout

@app.callback(
    [Output('register-url', 'pathname'),
     Output('register-error-message', 'children')],
    Input('register-button', 'n_clicks'),
    [State('user_register', 'value'),
     State('pwd_register', 'value'),
     State('email_register', 'value'),
     State('level_register', 'value')],
    prevent_initial_call=True
)
def successful_register(n_clicks, username, password, email, level):
    if not all([username, password, email, level]):
        return dash.no_update, "Todos os campos são obrigatórios."
    if get_user_by_username(username):
        return dash.no_update, "Este nome de usuário já existe."
    if get_user_by_email(email):
        return dash.no_update, "Este e-mail já está em uso."
    save_user(username, email, password, level)
    return '/login', "Registro bem-sucedido! Faça o login."
