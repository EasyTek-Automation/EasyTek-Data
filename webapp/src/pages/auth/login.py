# pages/login.py

from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
from werkzeug.security import check_password_hash
from flask_login import login_user
from dash.exceptions import PreventUpdate
from dash_bootstrap_templates import template_from_url
import dash

from src.app import app
from src.database.connection import get_user_by_email
from src.config.theme_config import URL_THEME_MINTY



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

    login_layout = dbc.Container([
        dcc.Store(id='theme-store', storage_type='local'),
        dbc.Row(
            dbc.Col(
                dbc.Card([
                    html.Div(
                        [
                            html.Img(src="/assets/LogoAMG.png", style={"height": "100px"}),
                            # ThemeSwitchAIO removido
                        ],
                        className="d-flex justify-content-between align-items-center"
                    ),
                    html.Hr(className="my-4"),
                    
                    
                    html.H2("EasyTek-Data", className="text-center mb-4"),
                    
                    dbc.Input(id="email_login", placeholder="E-mail", type="email", className="mb-3"),
                    dbc.Input(id="pwd_login", placeholder="Senha", type="password", className="mb-3"),
                    dbc.Button("Login", id="login_button", color="primary", className="w-100"),
                    
                    html.Div(id="login-error-message", className="text-danger text-center mt-3"),
                    
                    

                    html.Hr(className="mt-4"),
                    html.Div(
                        [
                            html.Span("Powered by:", style={'fontSize': '0.8rem', 'color': '#aaa', 'marginRight': '10px'}),
                            html.Img(src="/assets/logo.png", style={"height": "50px"})
                        ],
                        className="d-flex justify-content-end align-items-center"
                    )
                    
                ], body=True, style=card_style),
                width=12
            )
        )
    ], fluid=True, className=template_from_url(URL_THEME_MINTY), id="login-container",
       style={"height": "100vh", "display": "flex", "align-items": "center", "justify-content": "center"})
    
    return login_layout

@app.callback(
    [Output('url', 'pathname', allow_duplicate=True),
     Output('login-error-message', 'children')],
    Input('login_button', 'n_clicks'),
    [
        State('email_login', 'value'),
        State('pwd_login', 'value')
    ],
    prevent_initial_call=True
)
def successful_login(n_clicks, email, password):
    # Only require email (password can be blank for first-time users)
    if not email:
        raise PreventUpdate

    # Allow password to be None or empty string
    if password is None:
        password = ""

    user = get_user_by_email(email)
    if user and check_password_hash(user.password, password):
        login_user(user)

        # Check if user has blank password (first-time setup)
        if check_password_hash(user.password, ""):
            # Redirect to password change page for first-time setup
            return "/change-password", ""
        else:
            # Normal login - redirect to home
            return "/", ""
    else:
        return dash.no_update, "E-mail ou senha inválidos."
