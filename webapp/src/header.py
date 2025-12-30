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
    filter_icon,
    home_icon,
    maintenance_icon,    # ← NOVO
    production_icon,
    energy_icon,
    alarm_icon,
    report_icon
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
    
    IMPORTANTE: Esta função recebe o pathname JÁ RESOLVIDO após os aliases.
    Por exemplo, se o usuário acessa /dashboard, esta função recebe /production/oee
    
    Args:
        pathname (str): O caminho da URL atual (já resolvido após aliases)
        
    Returns:
        html.Div: Componente com os filtros apropriados para a página
    """
    # ========================================
    # CORRIGIDO: Reconhece rotas NOVAS (após resolução de aliases)
    # ========================================
    
    # Dashboard / Production OEE
    if pathname in ["/", "/production/oee"]:
        return create_dashboard_filters()
    
    # Production States
    elif pathname == "/production/states":
        return create_states_filters()
    
    # Outras páginas (supervision, reports, energy, alarms)
    elif pathname in ["/supervision", "/reports", "/energy", "/production/alarms"]:
        return create_default_filters()
    
    # Fallback para qualquer outra rota
    else:
        return create_default_filters()


def create_header(pathname, user):
    """
    Cria e retorna o componente de cabeçalho (header) da aplicação.
    
    Esta função é responsável por construir dinamicamente o header,
    incluindo o menu de navegação organizado por módulos que dependem 
    da rota atual (pathname) e do nível de permissão do usuário (user).

    Args:
        pathname (str): O caminho da URL atual APÓS resolução de aliases 
                       (ex: "/production/oee", "/production/states", "/supervision").
        user: O objeto current_user do Flask-Login.

    Returns:
        html.Div: O componente Dash que representa o cabeçalho completo.
    """
    
    # ========================================
    # MENU DE NAVEGAÇÃO - ORGANIZADO POR MÓDULOS
    # ========================================
    
    # 🏠 HOME - Link direto
    home_link = dbc.NavItem(
        dbc.NavLink(
            html.Div(
                [
                    html.Span(home_icon(), style={"marginRight": "8px"}),
                    html.Span("Início", style={"fontWeight": "600"})
                ],
                className="d-flex align-items-center"
            ),
            href="/",
            active=(pathname == "/"),
        )
    )
    
    # 🔧 MANUTENÇÃO - Dropdown
    maintenance_dropdown = dbc.DropdownMenu(
        label=html.Div(
            [
                html.Span(maintenance_icon(), style={"marginRight": "8px"}),
                html.Span("Manutenção", style={"fontWeight": "600"})
            ],
            className="d-flex align-items-center"
        ),
        children=[
            dbc.DropdownMenuItem(
                html.Div(
                    [
                        html.I(className="bi bi-clipboard-check me-2"),
                        "Ordens de Serviço"
                    ],
                    className="d-flex align-items-center"
                ),
                href="/maintenance/work-orders",
                disabled=True,
                style={"opacity": "0.5"}
            ),
            dbc.DropdownMenuItem(
                html.Div(
                    [
                        html.I(className="bi bi-calendar-check me-2"),
                        "Plano de Manutenção"
                    ],
                    className="d-flex align-items-center"
                ),
                href="/maintenance/schedule",
                disabled=True,
                style={"opacity": "0.5"}
            ),
            dbc.DropdownMenuItem(divider=True),
            dbc.DropdownMenuItem(
                html.Div(
                    [
                        html.I(className="bi bi-clock-history me-2"),
                        "Histórico de Intervenções"
                    ],
                    className="d-flex align-items-center"
                ),
                href="/maintenance/history",
                disabled=True,
                style={"opacity": "0.5"}
            ),
            dbc.DropdownMenuItem(
                html.Div(
                    [
                        html.I(className="bi bi-graph-up me-2"),
                        "Indicadores de Manutenção"
                    ],
                    className="d-flex align-items-center"
                ),
                href="/maintenance/indicators",
                disabled=True,
                style={"opacity": "0.5"}
            ),
        ],
        nav=True,
        in_navbar=True,
        toggle_style={
            "display": "inline-flex",
            "alignItems": "center",
            "gap": "4px",
            "fontWeight": "600"
        }
    )
    
    # 🏭 PRODUÇÃO - Dropdown
    production_dropdown = dbc.DropdownMenu(
        label=html.Div(
            [
                html.Span(production_icon(), style={"marginRight": "8px"}),
                html.Span("Produção", style={"fontWeight": "600"})
            ],
            className="d-flex align-items-center"
        ),
        children=[
            dbc.DropdownMenuItem(
                html.Div(
                    [
                        html.Span(dashboard_icon(), style={"marginRight": "8px"}),
                        "Dashboard OEE"
                    ],
                    className="d-flex align-items-center"
                ),
                href="/production/oee",
                active=(pathname == "/production/oee")
            ),
            dbc.DropdownMenuItem(
                html.Div(
                    [
                        html.Span(states_icon(), style={"marginRight": "8px"}),
                        "Estados da Linha"
                    ],
                    className="d-flex align-items-center"
                ),
                href="/production/states",
                active=(pathname == "/production/states")
            ),
            dbc.DropdownMenuItem(divider=True),
            dbc.DropdownMenuItem(
                html.Div(
                    [
                        html.Span(alarm_icon(), style={"marginRight": "8px"}),
                        "Alarmes"
                    ],
                    className="d-flex align-items-center"
                ),
                href="/production/alarms",
                active=(pathname == "/production/alarms"),
                disabled=True,
                style={"opacity": "0.5"}
            ),
        ],
        nav=True,
        in_navbar=True,
        toggle_style={
            "display": "inline-flex",
            "alignItems": "center",
            "gap": "4px",
            "fontWeight": "600"
        }
    )
    
    # ⚡ ENERGIA - Dropdown
    energy_dropdown = dbc.DropdownMenu(
        label=html.Div(
            [
                html.Span(energy_icon(), style={"marginRight": "8px"}),
                html.Span("Energia", style={"fontWeight": "600"})
            ],
            className="d-flex align-items-center"
        ),
        children=[
            dbc.DropdownMenuItem(
                html.Div(
                    [
                        html.Span(energy_icon(), style={"marginRight": "8px"}),
                        "Visão Geral"
                    ],
                    className="d-flex align-items-center"
                ),
                href="/energy",
                active=(pathname == "/energy"),
                
                style={"opacity": "0.5"}
            ),
            dbc.DropdownMenuItem(divider=True),
            dbc.DropdownMenuItem("Subestações", header=True, style={"opacity": "0.6"}),
            dbc.DropdownMenuItem(
                "SE01 - Principal",
                href="/energy/se01",
                disabled=True,
                style={"opacity": "0.4", "fontSize": "0.9rem"}
            ),
            dbc.DropdownMenuItem(
                "SE02 - Produção",
                href="/energy/se02",
                disabled=True,
                style={"opacity": "0.4", "fontSize": "0.9rem"}
            ),
            dbc.DropdownMenuItem(
                "SE03 - AMG",
                href="/energy/se03",
                disabled=True,
                style={"opacity": "0.4", "fontSize": "0.9rem"}
            ),
            dbc.DropdownMenuItem(
                "SE04 - Auxiliar",
                href="/energy/se04",
                disabled=True,
                style={"opacity": "0.4", "fontSize": "0.9rem"}
            ),
        ],
        nav=True,
        in_navbar=True,
        toggle_style={
            "display": "inline-flex",
            "alignItems": "center",
            "gap": "4px",
            "fontWeight": "600"
        }
    )
    
    # 🖥️ SUPERVISÓRIO - Dropdown
    supervision_dropdown = dbc.DropdownMenu(
        label=html.Div(
            [
                html.Span(supervisory_icon(), style={"marginRight": "8px"}),
                html.Span("Supervisório", style={"fontWeight": "600"})
            ],
            className="d-flex align-items-center"
        ),
        children=[
            dbc.DropdownMenuItem(
                html.Div(
                    [
                        html.Span(supervisory_icon(), style={"marginRight": "8px"}),
                        "Controle de Temperatura"
                    ],
                    className="d-flex align-items-center"
                ),
                href="/supervision",
                active=(pathname == "/supervision"),
                disabled=not (hasattr(user, 'level') and user.level in [2, 3])
            ),
        ],
        nav=True,
        in_navbar=True,
        toggle_style={
            "display": "inline-flex",
            "alignItems": "center",
            "gap": "4px",
            "fontWeight": "600"
        }
    )
    
    # 📄 RELATÓRIOS - Dropdown
    reports_dropdown = dbc.DropdownMenu(
        label=html.Div(
            [
                html.Span(report_icon(), style={"marginRight": "8px"}),
                html.Span("Relatórios", style={"fontWeight": "600"})
            ],
            className="d-flex align-items-center"
        ),
        children=[
            dbc.DropdownMenuItem(
                html.Div(
                    [
                        html.Span(report_icon(), style={"marginRight": "8px"}),
                        "Gerar Relatório"
                    ],
                    className="d-flex align-items-center"
                ),
                href="/reports",
                active=(pathname == "/reports")
            ),
        ],
        nav=True,
        in_navbar=True,
        toggle_style={
            "display": "inline-flex",
            "alignItems": "center",
            "gap": "4px",
            "fontWeight": "600"
        }
    )
    
    # ========================================
    # NAVBAR COMPLETO
    # ========================================
    navigation_menu = dbc.Nav(
        [
            home_link,
            maintenance_dropdown,    # ← NOVO
            production_dropdown,
            energy_dropdown,
            supervision_dropdown,
            reports_dropdown,
        ],
        navbar=True,
        className="ms-3",
    )

    # ========================================
    # DROPDOWN DE FILTROS - DINÂMICO
    # ========================================
    filters_dropdown = dbc.DropdownMenu(
        label=html.Div(
            [
                html.Span(filter_icon(), style={"marginRight": "8px"}),
                html.Span("Filtros", style={"fontWeight": "600"})
            ],
            className="d-flex align-items-center"
        ),
        children=[get_filters_for_page(pathname)],
        nav=True,
        in_navbar=True,
        align_end=True,
        id="filters-dropdown-menu",
        toggle_style={
            "display": "inline-flex",
            "alignItems": "center",
            "gap": "4px",
            "fontWeight": "600"
        }
    )

    # ========================================
    # LAYOUT FINAL DO HEADER
    # ========================================
    header_layout = html.Div(
        [
            # Seção Esquerda: Hamburger + Logo + Título + Menu
            html.Div(
                [
                    dbc.Button(
                        hamburger_icon(),
                        id="collapse-sidebar-btn",
                        color="primary",
                        size="sm",
                        className="me-2"
                    ),
                    html.Img(
                        src="/assets/LogoAMG.png",
                        style={"height": "35px", "marginRight": "10px"}
                    ),
                    html.Span(
                        "EasyTek-Data",
                        className="navbar-brand mb-0 me-3",
                        style={"fontSize": "1.2rem", "fontWeight": "500"}
                    ),
                    navigation_menu,
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
    )

    return header_layout