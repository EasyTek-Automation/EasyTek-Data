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

# Energia
from src.pages.energy import overview as energy_overview

# Produção
from src.pages.production import states

# Manutenção
from src.pages.maintenance import alarms

# Supervisório
from src.pages.supervision import control as supervision_control

# Relatórios
from src.pages.reports import reports

# Comum - Páginas de utilidade
from src.pages.common import under_development

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
    "/utilities/energy": energy_overview.layout,  # Alias
    
    # Produção
    
    # Manutenção
    "/maintenance/alarms": alarms.layout,
    
    # Supervisório
    "/supervision": supervision_control.layout,    
    
    # Relatórios
    "/reports": reports.layout,
    
    # ========================================
    # ROTAS EM DESENVOLVIMENTO
    # ========================================

    # Produção - Estados
    "/production/states": lambda: under_development.layout("Status de Ativos - Em Desenvolvimento"),
    


    # Energia - Subestações
    "/utilities/energy/se01": lambda: under_development.layout("Subestação SE01 - Em Desenvolvimento"),
    "/utilities/energy/se02": lambda: under_development.layout("Subestação SE02 - Em Desenvolvimento"),
    "/utilities/energy/se03": lambda: under_development.layout("Subestação SE03 - Em Desenvolvimento"),
    "/utilities/energy/se04": lambda: under_development.layout("Subestação SE04 - Em Desenvolvimento"),
    "/utilities/energy/history": lambda: under_development.layout("Histórico de Consumo - Em Desenvolvimento"),
    "/utilities/energy/costs": lambda: under_development.layout("Análise de Custos - Em Desenvolvimento"),
    
    # Água
    "/utilities/water": lambda: under_development.utilities_development(),
    "/utilities/water/points": lambda: under_development.utilities_development(),
    "/utilities/water/history": lambda: under_development.utilities_development(),
    "/utilities/water/costs": lambda: under_development.utilities_development(),
    
    # Gás Natural
    "/utilities/gas": lambda: under_development.utilities_development(),
    "/utilities/gas/points": lambda: under_development.utilities_development(),
    "/utilities/gas/history": lambda: under_development.utilities_development(),
    "/utilities/gas/costs": lambda: under_development.utilities_development(),
    
    # Ar Comprimido
    "/utilities/compressed-air": lambda: under_development.utilities_development(),
    "/utilities/compressed-air/compressors": lambda: under_development.utilities_development(),
    "/utilities/compressed-air/efficiency": lambda: under_development.utilities_development(),
    
    # Dashboard Integrado de Utilidades
    "/utilities/dashboard": lambda: under_development.layout(
        "Dashboard Integrado de Utilidades - Em Desenvolvimento",
        "O dashboard consolidado de todas as utilidades (energia, água, gás e ar comprimido) está sendo desenvolvido."
    ),
    
    # Manutenção
    "/maintenance/work-orders": lambda: under_development.maintenance_development(),
    "/maintenance/schedule": lambda: under_development.maintenance_development(),
    "/maintenance/history": lambda: under_development.maintenance_development(),
    "/maintenance/indicators": lambda: under_development.maintenance_development(),
    
    # Configurações
    "/config/users": lambda: under_development.config_development(),
    "/config/preferences": lambda: under_development.config_development(),
    "/config/logs": lambda: under_development.config_development(),
}

# ========================================
# ALIASES PARA RETROCOMPATIBILIDADE
# ========================================
ROUTE_ALIASES = {
    "/dashboard": "/production/oee",
    "/states": "/production/states",
    "/superv": "/supervision",
    "/production/alarms": "/maintenance/alarms",
    "/alarms": "/maintenance/alarms",
}

# --- Configurações Iniciais ---
user_loader

# --- Layout Principal do Aplicativo ---
app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    dcc.Location(id='logout-url', refresh=True),
    
    # Store para estado da sidebar (precisa estar aqui para o callback funcionar)
    dcc.Store(id="sidebar-state", storage_type="session", data="collapsed"),
    
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

    html.Div(id="app-container", style={'visibility': 'hidden', 'opacity': 0}),
    
    dcc.Interval(id='reveal-timer', interval=1000, max_intervals=1, disabled=True)
])

# --- Callback de Roteamento ---
@app.callback(
    Output("app-container", "children"),
    Output("reveal-timer", "disabled"),
    Input("url", "pathname"),
    State("sidebar-state", "data")
)
def route_and_prepare_content(pathname, sidebar_state):
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
        # 404 - Página não encontrada
        page_content = dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.Div([
                                html.I(className="bi bi-exclamation-triangle-fill text-danger", 
                                      style={"fontSize": "5rem"})
                            ], className="text-center mb-4"),
                            
                            html.H2("404 - Página Não Encontrada", className="text-center mb-3"),
                            html.P(f"A rota '{pathname}' não existe.", 
                                  className="text-center text-muted mb-4"),
                            
                            html.Div([
                                dbc.Button([
                                    html.I(className="bi bi-house-door me-2"),
                                    "Voltar ao Início"
                                ], href="/", color="primary", size="lg")
                            ], className="text-center")
                        ], className="p-5")
                    ], className="shadow")
                ], width={"size": 6, "offset": 3})
            ], className="mt-5")
        ], fluid=True, style={"minHeight": "70vh", "display": "flex", "alignItems": "center"})
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

    # Definir estilos baseado no estado da sidebar
    if sidebar_state == "expanded":
        sidebar_col_style = {"width": "25%", "height": "100%", "transition": "width 0.5s ease", 
                            "padding": "8px", "overflow": "hidden"}
        content_col_style = {"width": "75%", "height": "100%", "transition": "width 0.5s ease", 
                            "overflowY": "auto"}
        sidebar_content_style = {
            "height": "100%", "visibility": "visible", "opacity": 1, 
            "overflowY": "auto", "transition": "opacity 0.3s ease, visibility 0s linear 0.5s"
        }
    else:  # collapsed ou None
        sidebar_col_style = {"width": "0%", "height": "100%", "transition": "width 0.5s ease", 
                            "padding": "8px", "overflow": "hidden"}
        content_col_style = {"width": "100%", "height": "100%", "transition": "width 0.5s ease", 
                            "overflowY": "auto"}
        sidebar_content_style = {
            "height": "100%", "visibility": "hidden", "opacity": 0, 
            "overflow": "hidden", "transition": "opacity 0.2s ease, visibility 0s linear 0.2s"
        }

    main_layout = html.Div([
        *stores.app_stores,
        header.create_header(pathname, current_user),
        html.Div([
            html.Div([sidebar.create_sidebar_layout(app, pathname, sidebar_content_style)], 
                     id="sidebar-column", 
                     style=sidebar_col_style),
            html.Div([html.Div(page_content)], 
                     id="content-column", 
                     style=content_col_style),
        ], id="main-container", style={"position": "fixed", "top": "60px", "left": 0, "right": 0, 
                                       "bottom": 0, "display": "flex", "flexDirection": "row", 
                                       "gap": "10px"}),
        dbc.Toast(id="toast-mqtt-status", header="Status da Publicação MQTT", 
                  is_open=False, dismissable=True, duration=4000, icon="info", 
                  style={"position": "fixed", "top": 66, "right": 10, "width": 350, "zIndex": 9999}),
        dcc.Interval(id='interval-component', interval=10 * 1000, n_intervals=0, disabled=False),
    ])
    return main_layout, False

# --- Callback para Revelar o Conteúdo ---
@app.callback(
    Output("app-container", "style"),
    Output("loading-overlay", "style"),
    Input("reveal-timer", "n_intervals")
)
def reveal_content_on_timer(n_intervals):
    if n_intervals is None:
        raise PreventUpdate

    app_style = {
        'visibility': 'visible',
        'opacity': 1,
        'transition': 'opacity 0.5s ease-in'
    }
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