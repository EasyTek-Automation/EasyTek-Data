# index.py (Versão Final e Robusta)



from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
from flask_login import logout_user, current_user
from dash.exceptions import PreventUpdate
from dash_bootstrap_templates import ThemeSwitchAIO

# --- Importações do Projeto ---
from src.app import app
from src.components import sidebar

# Importa as layouts das páginas
from src.pages import dashboard as dashboard_page

from src.pages import states as states_page
from src.pages import login as login_page
from src.pages import register as register_page
from src.pages import superv as superv_page

from src.config.theme_config import URL_THEME_MINTY, URL_THEME_DARKLY
# Importa a função de registro de callbacks
from src.callbacks import register_callbacks
from src.config import user_loader

# ... (outras importações)
from src.components.icons import hamburger_icon, dashboard_icon, states_icon, supervisory_icon, external_link_icon




template_theme1 = "minty"
template_theme2 = "darkly"
url_theme1 = dbc.themes.MINTY
url_theme2 = dbc.themes.DARKLY





#configura Login
user_loader

# --- Layout Principal do Aplicativo ---
# Este layout é o único que será definido diretamente.
# Ele contém um contêiner que será preenchido pelo nosso callback principal.
app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    dcc.Location(id='logout-url', refresh=True),
    html.Div(id="app-container"),

    
])

# --- Callback de Roteamento Principal (Unificado) ---
@app.callback(
    Output("app-container", "children"),
    Input("url", "pathname")
)
def route_and_render_content(pathname):
    print(f"--- DEBUG: Roteando para '{pathname}'. Autenticado: {current_user.is_authenticated} ---")

    if not current_user.is_authenticated:
        # Se o usuário NÃO estiver logado, mostre apenas as páginas de login/registro
        if pathname == '/register':
            return register_page.render_layout()
        # Para qualquer outra URL, force o login
        return login_page.render_layout()
     # 1. Links para a coluna "Visualização"
    visualization_links = [
        dbc.DropdownMenuItem(
            # --- ENVOLVEMOS TUDO EM UM DIV COM FLEXBOX ---
            html.Div(
                [dashboard_icon(), "Dashboard OEE"],
                className="d-flex align-items-center"
            ),
            href="/", 
            active=(pathname == "/")
        ),
        dbc.DropdownMenuItem(
            html.Div([states_icon(), "Estados"], className="d-flex align-items-center"), # <<< MUDANÇA AQUI
            href="/states", 
            active=(pathname == "/states")
        ),
        ]
    # (Aqui você pode adicionar a lógica para o link de Relatórios no futuro, se precisar)

    # 2. Links para a coluna "Ajustes"
    settings_links = [
        # Adiciona o link Supervisório, mas controla se está habilitado ou não
        dbc.DropdownMenuItem(
            html.Div([supervisory_icon(), "Supervisório"], className="d-flex align-items-center"), # <<< MUDANÇA AQUI
            href="/superv", 
            active=(pathname == "/superv"),
            disabled=not (current_user.level == 2 or current_user.level == 3)
        ),
    ]
    
    # --- Se o usuário ESTIVER logado ---

    # Layout do Dashboard (será a base para todas as páginas autenticadas)
    dashboard_layout = html.Div([
        dbc.Toast(
            id="toast-mqtt-status",
            header="Status da Publicação MQTT",
            is_open=False,
            dismissable=True,
            duration=4000,
            icon="info",
            # Estilo para fixar no canto superior direito da tela
            style={"position": "fixed", "top": 66, "right": 10, "width": 350, "zIndex": 9999},
        ),
        # Stores
        dcc.Store(id='store-start-date', storage_type='session'),
        dcc.Store(id='store-end-date', storage_type='session'),
        dcc.Store(id='store-start-hour', storage_type='session'),
        dcc.Store(id='store-end-hour', storage_type='session'),
        dcc.Store(id='store-auto-update-enabled', storage_type='session'),
        dcc.Store(id='stored-graph-data', storage_type='session'),
        dcc.Store(id='stored-table-data', storage_type='session'),
        dcc.Store(id='stored-oee-occupancy-card-graph', storage_type='session'),
        dcc.Store(id='stored-oee-occupancy02-card-graph', storage_type='session'),
        dcc.Store(id='theme-store', storage_type='local'),
        dcc.Store(id='stored-energy-data'),
        dcc.Store(id='stored-temp-data'),
        dcc.Store(id="sidebar-state", storage_type="session", data="expanded"),

       html.Div(
    [
        # --- Seção Esquerda: Botão Hamburger ---
        html.Div(
            dbc.Button(
                hamburger_icon(), # <<< Nosso novo e confiável ícone SVG
                id="collapse-sidebar-btn",
                color="primary",
                className="m-1",
            ),
            className="d-flex align-items-center",
        ),

        # --- Seção Central: MENU DE TESTE ---
        html.Div(
    [
        dbc.DropdownMenu(
            label="Visão Geral",
            children=[
                # Container principal do menu com padding
                html.Div([
                    dbc.Row([
                        # Coluna 1: Navegação
                        dbc.Col([
                            html.H5("Visualização", className="fw-bold"),
                            # Os links de navegação são inseridos aqui
                            *visualization_links, 
                            dbc.DropdownMenuItem(divider=True),
                            dbc.DropdownMenuItem(
                                html.Div([external_link_icon(), "Visite o Site"], className="d-flex align-items-center"), 
                                href="https://tekmont.com.br/",
                                target="_blank"
                            ),
                            ], width=6),

                        # Coluna 2: Configurações
                        dbc.Col([
                            html.H5("Ajustes", className="fw-bold"),
                            *settings_links, # <<< Usa a nova variável
                        ], width=6),
                    ])
                ], style={'padding': '1rem', 'width': '400px'}) # Largura do menu
            ],
            nav=True,
            in_navbar=True,
            
            align_end=False,
            style={'padding-left': '15px'}
        )
    ],
    className="d-flex align-items-center justify-content-start flex-grow-1",
),
        # --- Seção Direita: Usuário e Logout ---
        html.Div(
            [
                ThemeSwitchAIO(aio_id="theme", themes=[url_theme1, url_theme2]),
                html.Span(
                    [
                        "Bem-vindo, ",
                        html.Strong(f"{current_user.username}", style={'color': '#0d6efd'})
                    ],
                    className="me-3 align-middle",
                    style={'fontSize': '0.9rem'}
                ),
                dbc.Button("Logout", id="logout_button", color="danger", size="sm"),
            ],
            # Alinha à direita
            className="d-flex align-items-center",
        ),
    ],
    id="header",
    # O estilo do header permanece o mesmo
    style={
        "position": "fixed",
        "top": 0,
        "left": 0,
        "right": 0,
        "height": "60px",
        "padding": "0 1rem",
        "zIndex": 1020,
        "display": "flex",
        "alignItems": "center",
        "justifyContent": "space-between",
        "background": "var(--bs-body-bg, #fff)",
        "borderBottom": "1px solid var(--bs-border-color, #dee2e6)",
    },
),
                # Área Principal
        html.Div([
            # Coluna da Sidebar
            html.Div(
                # O conteúdo da sidebar (o Card) é inserido aqui
                [sidebar.create_sidebar_layout(app)],
                id="sidebar-column",
                # Aplicando o estilo 'sidebar_style_expanded'
                style={
                    "width": "25%",
                    "height": "100%",
                    "transition": "width 0.5s ease",
                    "padding": "8px", # Padding aplicado na coluna
                    "overflow": "hidden"
                }
            ),
            # Coluna do Conteúdo Principal
            html.Div(
                [html.Div(id="page-content")],
                id="content-column",
                # Aplicando o estilo 'content_style_expanded'
                style={
                    "width": "75%",
                    "height": "100%",
                    "transition": "width 0.5s ease",
                    "overflowY": "auto"
                }
            ),
        ], id="main-container",
        style={
            "position": "fixed",
            "top": "60px",
            "left": 0,
            "right": 0,
            "bottom": 0,
            "display": "flex",
            "flexDirection": "row",
            "gap": "10px" # Mantém o espaço entre as colunas
        }),

        # Intervalo
        dcc.Interval(id='interval-component', interval=10 * 1000, n_intervals=0, disabled=False),
    ], style={"height": "100vh", "width": "100vw", "overflow": "hidden"})

    # Agora, preenchemos o `page-content` dentro do `dashboard_layout`
    page_content = html.Div() # Default
    if pathname == "/":
        page_content = dashboard_page.layout
    elif pathname == "/states":
        page_content = states_page.layout
    elif pathname == "/reports":
        if current_user.level == 3:
            ...
    elif pathname == "/superv":
        if (current_user.level == 2 or current_user.level == 3):
            page_content = superv_page.layout
        else:
            page_content = html.Div([
                html.H2("Acesso Negado"),
                html.P("Você não tem permissão para acessar esta página."),
                dcc.Link("Voltar ao Dashboard", href="/")
            ], style={'textAlign': 'center', 'marginTop': '50px'})
    else:
        page_content = html.P("404: Página não encontrada")

    # Injeta o conteúdo da página no layout do dashboard
    main_container_index = -2 # O penúltimo item da lista
    content_column = dashboard_layout.children[main_container_index].children[1]
    content_column.children[0].children = page_content

    return dashboard_layout

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

# --- Callback para controlar a sidebar (sem alterações) ---
@app.callback(
    [Output("sidebar-column", "style"), 
     Output("content-column", "style"), 
     Output("sidebar-content", "style"), 
     Output("collapse-sidebar-btn", "children"), 
     Output("sidebar-state", "data")],
    [Input("collapse-sidebar-btn", "n_clicks")],
    [State("sidebar-state", "data")],
    prevent_initial_call=True # Evita que execute na carga inicial
)
def toggle_sidebar(n_clicks, current_state):
    if not n_clicks:
        raise PreventUpdate

    sidebar_style_expanded = {"width": "25%",
                              "height": "100%", 
                              "transition": "width 0.5s ease", 
                              "padding": "8px",
                              "overflow": "hidden"}
    sidebar_style_collapsed = {"width": "0%", 
                               "height": "100%", 
                               "transition": "width 0.5s ease", 
                               "padding": "8px",
                               "overflow": "hidden"}
    content_style_expanded = {"width": "75%", 
                              "height": "100%", 
                              "transition": "width 0.5s ease", 
                              "overflowY": "auto"}
    content_style_collapsed = {"width": "100%", 
                               "height": "100%", 
                               "transition": 
                               "width 0.5s ease", 
                               "overflowY": "auto"}
    sidebar_content_style_visible = {"height": "100%", 
                                     "visibility": "visible", 
                                     "opacity": 1, 
                                     "overflowY": "auto", 
                                     "transition": "opacity 0.3s ease, visibility 0s linear 0.5s"}
    sidebar_content_style_hidden = {"height": "100%", 
                                    "visibility": "hidden", 
                                    "opacity": 0, 
                                    "overflow": "hidden", 
                                    "transition": "opacity 0.2s ease, visibility 0s linear 0.2s"}

    if current_state == "expanded":
        return sidebar_style_collapsed, content_style_collapsed, sidebar_content_style_hidden, hamburger_icon(), "collapsed"
    else:
        return sidebar_style_expanded, content_style_expanded, sidebar_content_style_visible, hamburger_icon(), "expanded"

# Registra os outros callbacks do seu aplicativo
register_callbacks(app)

# --- Ponto de Entrada ---
if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=8050)
