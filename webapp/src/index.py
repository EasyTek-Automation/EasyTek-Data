# webapp/src/index.py 

from dash import html, dcc, Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from flask_login import logout_user, current_user

# --- Importações do Projeto ---
from src.app import app
from src.config import user_loader
from src import header
from src import sidebar
from src.components import stores
from src.callbacks import register_callbacks
# ========================================
# IMPORTAÇÕES DE PÁGINAS - NOVA ESTRUTURA
# ========================================
# Autenticação
from src.pages.auth import login, register

# Dashboards
from src.pages.dashboards import home, production_oee
# from src.pages.dashboards import home  # ← Criar no Bife 3

# Energia
from src.pages.energy import overview as energy_overview

# Produção
from src.pages.production import states
# from src.pages.production import alarms  # ← Criar no Bife 5

# Supervisório
from src.pages.supervision import control as supervision_control

# Relatórios
from src.pages.reports import reports

from src.pages.energy import overview as energy_overview

# ========================================
# MAPEAMENTO DE ROTAS (NOVA ESTRUTURA)
# ========================================
ROUTES = {
    # Auth
    "/login": login.render_layout,
    "/register": register.render_layout,
    
    # Dashboards
    "/": home.layout,                       
    "/production/oee": production_oee.layout,    
    
    # Energia
    "/energy": energy_overview.layout,
    
    # Produção
    "/production/states": states.layout,           
    # "/production/alarms": alarms.layout,         # ← Criar no Bife 5
    
    # Supervisório
    "/supervision": supervision_control.layout,    
    
    # Relatórios
    "/reports": reports.layout,
}

# ========================================
# ALIASES PARA RETROCOMPATIBILIDADE
# ========================================
ROUTE_ALIASES = {
    "/dashboard": "/production/oee",  # Redireciona rota antiga
    "/states": "/production/states",
    "/superv": "/supervision",
}

# --- Configurações Iniciais ---
user_loader

# --- Layout Principal do Aplicativo ---
app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    dcc.Location(id='logout-url', refresh=True),

    
    html.Div(
        id='loading-overlay',
        children=[dbc.Spinner(color="primary", size="lg")],
        style={
            'position': 'fixed',
            'display': 'flex',
            'justify-content': 'center',
            'align-items': 'center',
            'width': '100%',
            'height': '100%',
            'top': 0,
            'left': 0,
            'background-color': 'rgba(255, 255, 255, 0.8)',
            'z-index': '1050', 
            'visibility': 'visible' 
        }
    ),

    # 2. O container do app começa invisível e transparente para uma transição suave.
    html.Div(id="app-container", style={'visibility': 'hidden', 'opacity': 0}),
    
    # 3. O timer para acionar a revelação do conteúdo.
    dcc.Interval(id='reveal-timer', interval=1000, max_intervals=1, disabled=True)
])

# --- Callback de Roteamento (Apenas monta o layout e ativa o timer) ---
@app.callback(
    Output("app-container", "children"),
    Output("reveal-timer", "disabled"),
    Input("url", "pathname")
)
def route_and_prepare_content(pathname):
    if not current_user.is_authenticated:
        if pathname == '/register': 
            return register.render_layout(), False
        return login.render_layout(), False

    # ========================================
    # RESOLVER ALIASES (RETROCOMPATIBILIDADE)
    # ========================================
    if pathname in ROUTE_ALIASES:
        pathname = ROUTE_ALIASES[pathname]
    
    # ========================================
    # RESOLVER ROTA
    # ========================================
    page_content = ROUTES.get(pathname)
    
    if page_content is None:
        page_content = html.Div([
            html.H2("404 - Página não encontrada"),
            html.P(f"Rota: {pathname}")
        ])
    elif callable(page_content):
        page_content = page_content()

    # Verificar permissões para supervisório
    if pathname == "/supervision":
        if not (hasattr(current_user, 'level') and (current_user.level in [2, 3])):
            page_content = html.Div([
                dbc.Alert([
                    html.H4("⛔ Acesso Negado"),
                    html.P("Você não tem permissão para acessar o supervisório.")
                ], color="danger")
            ])

    main_layout = html.Div([
        *stores.app_stores,
        header.create_header(pathname, current_user),
        html.Div([
            html.Div([sidebar.create_sidebar_layout(app)], 
                     id="sidebar-column", 
                     style={"width": "25%", "height": "100%", "transition": "width 0.5s ease", 
                            "padding": "8px", "overflow": "hidden"}),
            html.Div([html.Div(page_content)], 
                     id="content-column", 
                     style={"width": "75%", "height": "100%", "transition": "width 0.5s ease", 
                            "overflowY": "auto"}),
        ], id="main-container", style={"position": "fixed", "top": "60px", "left": 0, "right": 0, 
                                       "bottom": 0, "display": "flex", "flexDirection": "row", 
                                       "gap": "10px"}),
        dbc.Toast(id="toast-mqtt-status", header="Status da Publicação MQTT", 
                  is_open=False, dismissable=True, duration=4000, icon="info", 
                  style={"position": "fixed", "top": 66, "right": 10, "width": 350, "zIndex": 9999}),
        dcc.Interval(id='interval-component', interval=10 * 1000, n_intervals=0, disabled=False),
    ])
    return main_layout, False

# --- Callback para Revelar o Conteúdo (Acionado pelo Timer) ---
@app.callback(
    Output("app-container", "style"),
    Output("loading-overlay", "style"),
    Input("reveal-timer", "n_intervals")
)
def reveal_content_on_timer(n_intervals):
    if n_intervals is None:
        raise PreventUpdate

    # Estilo para tornar o app visível com uma transição suave
    app_style = {
        'visibility': 'visible',
        'opacity': 1,
        'transition': 'opacity 0.5s ease-in'
    }
    # Estilo para esconder o overlay com uma transição suave
    overlay_style = {
        'visibility': 'hidden',
        'opacity': 0,
        'transition': 'visibility 0s 0.9s, opacity 0.9s ease'
    }
    
    return app_style, overlay_style

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
register_callbacks(app)

# --- Ponto de Entrada da Aplicação ---
if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=8050)
