# src/header.py

"""
Componente de cabeçalho (header) principal da aplicação.
Responsável por montar o header com menu de navegação, filtros e controles de usuário.
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
from dash_bootstrap_templates import ThemeSwitchAIO

# Importações de ícones e temas
from src.components.icons import (
    hamburger_icon,
    dashboard_icon,
    states_icon,
    supervisory_icon,
    external_link_icon,
    filter_icon
)
from src.config.theme_config import URL_THEME_MINTY, URL_THEME_DARKLY

# Importações dos filtros específicos de cada página
from src.components.headers import (
    create_dashboard_filters,
    create_states_filters,
    create_default_filters
)


def get_filters_for_page(pathname):
    """
    Retorna o conteúdo de filtros baseado na página atual.
    
    Args:
        pathname (str): O caminho da URL atual
        
    Returns:
        html.Div: Componente com os filtros apropriados para a página
    """
    if pathname == "/" or pathname == "/dashboard":
        return create_dashboard_filters()
    elif pathname == "/states":
        return create_states_filters()
    else:
        return create_default_filters()


def create_header(pathname, user):
    """
    Cria e retorna o componente de cabeçalho (header) da aplicação.
    
    Esta função é responsável por construir dinamicamente o header,
    incluindo o mega menu com links que dependem da rota atual (pathname)
    e do nível de permissão do usuário (user).

    Args:
        pathname (str): O caminho da URL atual (ex: "/", "/states").
        user: O objeto current_user do Flask-Login.

    Returns:
        html.Div: O componente Dash que representa o cabeçalho completo.
    """
    # 1. Links para a coluna "Visualização" do menu
    visualization_links = [
        dbc.DropdownMenuItem(
            html.Div([dashboard_icon(), "Dashboard OEE"], className="d-flex align-items-center"),
            href="/",
            active=(pathname == "/")
        ),
        dbc.DropdownMenuItem(
            html.Div([states_icon(), "Estados"], className="d-flex align-items-center"),
            href="/states",
            active=(pathname == "/states")
        ),
    ]

    # 2. Links para a coluna "Ajustes" do menu
    settings_links = [
        dbc.DropdownMenuItem(
            html.Div([supervisory_icon(), "Supervisório"], className="d-flex align-items-center"),
            href="/superv",
            active=(pathname == "/superv"),
            disabled=not (hasattr(user, 'level') and (user.level == 2 or user.level == 3))
        ),
    ]

    # 3. Construção do Mega Menu Dropdown (Visão Geral)
    mega_menu = dbc.DropdownMenu(
        label="Visão Geral",
        children=[
            html.Div([
                dbc.Row([
                    dbc.Col([
                        html.H5("Visualização", className="fw-bold"),
                        *visualization_links,
                        dbc.DropdownMenuItem(divider=True),
                        dbc.DropdownMenuItem(
                            html.Div([external_link_icon(), "Visite o Site"], className="d-flex align-items-center"),
                            href="https://tekmont.com.br/",
                            target="_blank"
                        ),
                    ], width=6),
                    dbc.Col([
                        html.H5("Ajustes", className="fw-bold"),
                        *settings_links,
                    ], width=6),
                ])
            ], style={'padding': '1rem', 'width': '400px'})
        ],
        nav=True,
        in_navbar=True,
        align_end=False,
        style={'padding-left': '15px'}
    )

    # 4. Dropdown de Filtros - conteúdo baseado na página
    filters_dropdown = dbc.DropdownMenu(
        label=html.Div([filter_icon(), " Filtros"], className="d-flex align-items-center"),
        children=[get_filters_for_page(pathname)],
        nav=True,
        in_navbar=True,
        align_end=True,
        id="filters-dropdown-menu",
    )

    # 5. Montagem do layout final do Header
    header_layout = html.Div(
        [
            # Seção Esquerda: Botão Hamburger + Mega Menu
            html.Div(
                [
                    dbc.Button(hamburger_icon(), id="collapse-sidebar-btn", color="primary", className="m-1"),
                    mega_menu,
                ],
                className="d-flex align-items-center",
            ),

            # Seção Direita: Filtros + Tema + Usuário + Logout
            html.Div(
                [
                    filters_dropdown,
                    html.Div(style={"width": "20px"}),  # Espaçador
                    ThemeSwitchAIO(aio_id="theme", themes=[URL_THEME_MINTY, URL_THEME_DARKLY]),
                    html.Span(
                        ["Bem-vindo, ", html.Strong(f"{user.username}", style={'color': '#0d6efd'})],
                        className="me-3 align-middle",
                        style={'fontSize': '0.9rem'}
                    ),
                    dbc.Button("Logout", id="logout_button", color="danger", size="sm"),
                ],
                className="d-flex align-items-center",
            ),
        ],
        id="header",
        style={
            "position": "fixed", "top": 0, "left": 0, "right": 0, "height": "60px",
            "padding": "0 1rem", "zIndex": 1020, "display": "flex",
            "alignItems": "center", "justifyContent": "space-between",
            "background": "var(--bs-body-bg, #fff)",
            "borderBottom": "1px solid var(--bs-border-color, #dee2e6)",
        },
    )

    return header_layout