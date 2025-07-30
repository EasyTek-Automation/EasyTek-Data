# index.py 

from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
from flask_login import logout_user, current_user
from dash.exceptions import PreventUpdate

# --- Importações do Projeto ---
from src.app import app
from src.config import user_loader

# 1. Importa os componentes de layout modulares
from src.components import header
from src.components import sidebar
from src.components.stores import app_stores # <<< Importa a lista de Stores

# 2. Importa as funções de registro de callbacks
from src.callbacks import register_callbacks # Callbacks das páginas


# 3. Importa os layouts das páginas
from src.pages import (
    dashboard as dashboard_page,
    states as states_page,
    login as login_page,
    register as register_page,
    superv as superv_page
)

# --- Configurações Iniciais ---
user_loader  # Garante que o loader do Flask-Login seja inicializado

# --- Layout Principal do Aplicativo ---
# O layout agora é apenas um esqueleto mínimo.
# O conteúdo será preenchido dinamicamente pelo callback de roteamento.
app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    dcc.Location(id='logout-url', refresh=True),
    html.Div(id="app-container"),
])

# --- Callback de Roteamento e Renderização de Conteúdo ---
@app.callback(
    Output("app-container", "children"),
    Input("url", "pathname")
)
def route_and_render_content(pathname):
    """
    Controla o roteamento da aplicação. Renderiza a página de login/registro
    para usuários não autenticados ou o layout principal para usuários autenticados.
    """
    if not current_user.is_authenticated:
        # Se o usuário NÃO estiver logado, mostra apenas as páginas de login/registro
        if pathname == '/register':
            return register_page.render_layout()
        # Para qualquer outra URL, força o login
        return login_page.render_layout()

    # --- Se o usuário ESTIVER logado, monta o layout principal ---

    # 1. Define o conteúdo da página (page_content) baseado na rota
    if pathname == "/":
        page_content = dashboard_page.layout
    elif pathname == "/states":
        page_content = states_page.layout
    elif pathname == "/superv" and hasattr(current_user, 'level') and (current_user.level in [2, 3]):
        page_content = superv_page.layout
    else:
        # Página padrão para rotas não encontradas ou sem permissão
        page_content = html.Div([
            html.H2("404: Página não encontrada ou Acesso Negado"),
            html.P("Verifique a URL ou suas permissões de acesso."),
            dcc.Link("Voltar ao Dashboard", href="/")
        ], style={'textAlign': 'center', 'marginTop': '50px'})

    # 2. Monta o layout completo da aplicação usando os módulos
    main_layout = html.Div([
        # Insere todos os dcc.Store importados do módulo stores.py
        *app_stores,

        # Cria o header usando a função do módulo header.py
        header.create_header(pathname, current_user),

        # Área Principal (Sidebar + Conteúdo da Página)
        html.Div([
            # Coluna da Sidebar
            html.Div(
                [sidebar.create_sidebar_layout(app)],
                id="sidebar-column",
                style={"width": "25%", "height": "100%", "transition": "width 0.5s ease", "padding": "8px", "overflow": "hidden"}
            ),
            # Coluna do Conteúdo Principal, que recebe o page_content definido acima
            html.Div(
                [html.Div(page_content)],
                id="content-column",
                style={"width": "75%", "height": "100%", "transition": "width 0.5s ease", "overflowY": "auto"}
            ),
        ], id="main-container", style={
            "position": "fixed", "top": "60px", "left": 0, "right": 0, "bottom": 0,
            "display": "flex", "flexDirection": "row", "gap": "10px"
        }),
        
        # Componentes globais como Toast e Interval
        dbc.Toast(id="toast-mqtt-status", header="Status da Publicação MQTT", is_open=False, dismissable=True, duration=4000, icon="info", style={"position": "fixed", "top": 66, "right": 10, "width": 350, "zIndex": 9999}),
        dcc.Interval(id='interval-component', interval=10 * 1000, n_intervals=0, disabled=False),
    ])

    return main_layout

# --- Callback de Logout ---
@app.callback(
    Output('logout-url', 'pathname'),
    Input('logout_button', 'n_clicks'),
    prevent_initial_call=True
)
def logout(n_clicks):
    if not n_clicks:
        raise PreventUpdate
    logout_user()
    return '/login'

# --- Registro de Todos os Callbacks da Aplicação ---
register_callbacks(app)             # Registra os callbacks específicos de cada página


# --- Ponto de Entrada da Aplicação ---
if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=8050)
