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
    maintenance_icon,
    production_icon,
    energy_icon,
    alarm_icon,
    utilities_icon,
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
    
    Args:
        pathname (str): O caminho da URL atual (já resolvido após aliases)
        
    Returns:
        html.Div: Componente com os filtros apropriados para a página
    """
    # Dashboard / Production OEE
    if pathname in ["/", "/production/oee"]:
        return create_dashboard_filters()
    
    # Production States
    elif pathname == "/production/states":
        return create_states_filters()
    
    # Outras páginas
    elif pathname in ["/supervision", "/utilities", "/energy", "/maintenance/alarms"]:
        return create_default_filters()
    
    # Fallback
    else:
        return create_default_filters()


def create_header(pathname, user):
    """
    Cria e retorna o componente de cabeçalho (header) da aplicação.
    
    Args:
        pathname (str): O caminho da URL atual APÓS resolução de aliases
        user: O objeto current_user do Flask-Login.

    Returns:
        html.Div: O componente Dash que representa o cabeçalho completo.
    """
    
    # ========================================
    # ÍCONES AUXILIARES (inline)
    # ========================================
    def water_icon():
        return html.I(className="bi bi-droplet")
    
    def gas_icon():
        return html.I(className="bi bi-fire")
    
    def compressed_air_icon():
        return html.I(className="bi bi-wind")
    
    def settings_icon():
        return html.I(className="bi bi-gear")
    
    def users_icon():
        return html.I(className="bi bi-people")

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
    
    # 🔧 MANUTENÇÃO - Dropdown (COM ALARMES HABILITADO)
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
                        html.Span(alarm_icon(), style={"marginRight": "8px"}),
                        "Alarmes"
                    ],
                    className="d-flex align-items-center"
                ),
                href="/maintenance/alarms",
                active=(pathname == "/maintenance/alarms"),
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
    
    # 💧 UTILIDADES - MEGA MENU COM 4 COLUNAS (CORRIGIDO - USA DropdownMenuItem)
    utilities_dropdown = dbc.DropdownMenu(
        label=html.Div(
            [
                html.Span(utilities_icon(), style={"marginRight": "8px"}),
                html.Span("Utilidades", style={"fontWeight": "600"})
            ],
            className="d-flex align-items-center"
        ),
        children=[
            # Wrapper com Grid Layout
            html.Div([
                dbc.Row([
                    # ========================================
                    # COLUNA 1: ENERGIA ELÉTRICA
                    # ========================================
                    dbc.Col([
                        html.Div([
                            # Cabeçalho da coluna
                            html.Div([
                                html.Span(energy_icon(), style={"marginRight": "6px"}),
                                html.Span("Energia Elétrica", style={"fontWeight": "600", "fontSize": "0.9rem"})
                            ], className="d-flex align-items-center mb-2 px-2", style={"color": "var(--bs-primary)"}),
                            
                            # Itens (usando DropdownMenuItem)
                            dbc.DropdownMenuItem(
                                "📊 Visão Geral",
                                href="/utilities/energy",
                                active=(pathname == "/utilities/energy"),
                                style={"fontSize": "0.85rem", "paddingLeft": "0.5rem"}
                            ),
                            
                            html.Div("Subestações:", className="mt-2 mb-1 px-2", 
                                    style={"fontSize": "0.75rem", "opacity": "0.7", "fontWeight": "600"}),
                            
                            dbc.DropdownMenuItem(
                                "• SE01 - Principal",
                                href="/utilities/energy/se01",
                                disabled=True,
                                style={"fontSize": "0.8rem", "opacity": "0.5", "paddingLeft": "1rem"}
                            ),
                            dbc.DropdownMenuItem(
                                "• SE02 - Produção",
                                href="/utilities/energy/se02",
                                disabled=True,
                                style={"fontSize": "0.8rem", "opacity": "0.5", "paddingLeft": "1rem"}
                            ),
                            dbc.DropdownMenuItem(
                                "• SE03 - AMG",
                                href="/utilities/energy/se03",
                                active=(pathname == "/utilities/energy/se03"),
                                style={"fontSize": "0.8rem", "paddingLeft": "1rem"}
                            ),
                            dbc.DropdownMenuItem(
                                "• SE04 - Auxiliar",
                                href="/utilities/energy/se04",
                                disabled=True,
                                style={"fontSize": "0.8rem", "opacity": "0.5", "paddingLeft": "1rem"}
                            ),
                            
                            dbc.DropdownMenuItem(
                                "📈 Histórico",
                                href="/utilities/energy/history",
                                disabled=True,
                                style={"fontSize": "0.85rem", "opacity": "0.5", "paddingLeft": "0.5rem"}
                            ),
                            dbc.DropdownMenuItem(
                                "💰 Custos",
                                href="/utilities/energy/costs",
                                disabled=True,
                                style={"fontSize": "0.85rem", "opacity": "0.5", "paddingLeft": "0.5rem"}
                            ),
                        ], style={"minHeight": "200px"})
                    ], width=3, className="border-end"),
                    
                    # ========================================
                    # COLUNA 2: ÁGUA
                    # ========================================
                    dbc.Col([
                        html.Div([
                            # Cabeçalho
                            html.Div([
                                html.Span(water_icon(), style={"marginRight": "6px"}),
                                html.Span("Água", style={"fontWeight": "600", "fontSize": "0.9rem"})
                            ], className="d-flex align-items-center mb-2 px-2", style={"color": "#0dcaf0"}),
                            
                            # Itens
                            dbc.DropdownMenuItem(
                                "📊 Visão Geral",
                                href="/utilities/water",
                                disabled=True,
                                style={"fontSize": "0.85rem", "opacity": "0.5", "paddingLeft": "0.5rem"}
                            ),
                            dbc.DropdownMenuItem(
                                "🚰 Pontos de Consumo",
                                href="/utilities/water/points",
                                disabled=True,
                                style={"fontSize": "0.85rem", "opacity": "0.5", "paddingLeft": "0.5rem"}
                            ),
                            dbc.DropdownMenuItem(
                                "📈 Histórico",
                                href="/utilities/water/history",
                                disabled=True,
                                style={"fontSize": "0.85rem", "opacity": "0.5", "paddingLeft": "0.5rem"}
                            ),
                            dbc.DropdownMenuItem(
                                "💰 Custos",
                                href="/utilities/water/costs",
                                disabled=True,
                                style={"fontSize": "0.85rem", "opacity": "0.5", "paddingLeft": "0.5rem"}
                            ),
                        ], style={"minHeight": "200px"})
                    ], width=3, className="border-end"),
                    
                    # ========================================
                    # COLUNA 3: GÁS NATURAL
                    # ========================================
                    dbc.Col([
                        html.Div([
                            # Cabeçalho
                            html.Div([
                                html.Span(gas_icon(), style={"marginRight": "6px"}),
                                html.Span("Gás Natural", style={"fontWeight": "600", "fontSize": "0.9rem"})
                            ], className="d-flex align-items-center mb-2 px-2", style={"color": "#fd7e14"}),
                            
                            # Itens
                            dbc.DropdownMenuItem(
                                "📊 Visão Geral",
                                href="/utilities/gas",
                                disabled=True,
                                style={"fontSize": "0.85rem", "opacity": "0.5", "paddingLeft": "0.5rem"}
                            ),
                            dbc.DropdownMenuItem(
                                "📍 Pontos de Medição",
                                href="/utilities/gas/points",
                                disabled=True,
                                style={"fontSize": "0.85rem", "opacity": "0.5", "paddingLeft": "0.5rem"}
                            ),
                            dbc.DropdownMenuItem(
                                "📈 Histórico",
                                href="/utilities/gas/history",
                                disabled=True,
                                style={"fontSize": "0.85rem", "opacity": "0.5", "paddingLeft": "0.5rem"}
                            ),
                            dbc.DropdownMenuItem(
                                "💰 Custos",
                                href="/utilities/gas/costs",
                                disabled=True,
                                style={"fontSize": "0.85rem", "opacity": "0.5", "paddingLeft": "0.5rem"}
                            ),
                        ], style={"minHeight": "200px"})
                    ], width=3, className="border-end"),
                    
                    # ========================================
                    # COLUNA 4: AR COMPRIMIDO
                    # ========================================
                    dbc.Col([
                        html.Div([
                            # Cabeçalho
                            html.Div([
                                html.Span(compressed_air_icon(), style={"marginRight": "6px"}),
                                html.Span("Ar Comprimido", style={"fontWeight": "600", "fontSize": "0.9rem"})
                            ], className="d-flex align-items-center mb-2 px-2", style={"color": "#6c757d"}),
                            
                            # Itens
                            dbc.DropdownMenuItem(
                                "📊 Visão Geral",
                                href="/utilities/compressed-air",
                                disabled=True,
                                style={"fontSize": "0.85rem", "opacity": "0.5", "paddingLeft": "0.5rem"}
                            ),
                            dbc.DropdownMenuItem(
                                "🔧 Compressores",
                                href="/utilities/compressed-air/compressors",
                                disabled=True,
                                style={"fontSize": "0.85rem", "opacity": "0.5", "paddingLeft": "0.5rem"}
                            ),
                            dbc.DropdownMenuItem(
                                "📈 Eficiência",
                                href="/utilities/compressed-air/efficiency",
                                disabled=True,
                                style={"fontSize": "0.85rem", "opacity": "0.5", "paddingLeft": "0.5rem"}
                            ),
                        ], style={"minHeight": "200px"})
                    ], width=3),
                    
                ], className="g-0"),
                
                # ========================================
                # DASHBOARD INTEGRADO (rodapé)
                # ========================================
                html.Hr(className="my-2"),
                dbc.DropdownMenuItem(
                    [
                        html.I(className="bi bi-speedometer2 me-2"),
                        "Dashboard Integrado de Utilidades"
                    ],
                    href="/utilities/dashboard",
                    disabled=True,
                    className="text-center",
                    style={"fontSize": "0.9rem", "opacity": "0.5", "fontWeight": "500"}
                )
                
            ], style={"padding": "15px", "minWidth": "750px"})
        ],
        nav=True,
        in_navbar=True,
        toggle_style={
            "display": "inline-flex",
            "alignItems": "center",
            "gap": "4px",
            "fontWeight": "600"
        },
        direction="down",
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
    
    # ⚙️ CONFIGURAÇÕES - Dropdown (NÍVEL 3 APENAS)
    config_dropdown = None
    if hasattr(user, 'level') and user.level == 3:
        config_dropdown = dbc.DropdownMenu(
            label=html.Div(
                [
                    html.Span(settings_icon(), style={"marginRight": "8px"}),
                    html.Span("Configurações", style={"fontWeight": "600"})
                ],
                className="d-flex align-items-center"
            ),
            children=[
                dbc.DropdownMenuItem(
                    html.Div([
                        html.Span(users_icon(), style={"marginRight": "8px"}),
                        "Gerenciar Usuários"
                    ], className="d-flex align-items-center"),
                    href="/config/users",
                    active=(pathname == "/config/users")
                ),
                dbc.DropdownMenuItem(divider=True),
                dbc.DropdownMenuItem(
                    html.Div([html.I(className="bi bi-sliders me-2"), "Preferências"], className="d-flex align-items-center"),
                    href="/config/preferences",
                    disabled=True,
                    style={"opacity": "0.5"}
                ),
                dbc.DropdownMenuItem(
                    html.Div([html.I(className="bi bi-file-text me-2"), "Logs do Sistema"], className="d-flex align-items-center"),
                    href="/config/logs",
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
    
    # ========================================
    # NAVBAR COMPLETO
    # ========================================
    nav_items = [
        home_link,
        maintenance_dropdown,
        production_dropdown,
        utilities_dropdown,
        supervision_dropdown,
    ]
    
    if config_dropdown:
        nav_items.append(config_dropdown)
    
    navigation_menu = dbc.Nav(
        nav_items,
        navbar=True,
        className="ms-3",
    )

    # ========================================
    # DROPDOWN DE FILTROS
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
    # LAYOUT FINAL DO HEADER (SEM LOGO)
    # ========================================
    header_layout = html.Div(
        [
            html.Div(
                [
                    dbc.Button(
                        hamburger_icon(),
                        id="collapse-sidebar-btn",
                        color="primary",
                        size="sm",
                        className="me-2"
                    ),
                    navigation_menu,
                ],
                className="d-flex align-items-center",
            ),

            html.Div(
                [
                    filters_dropdown,
                    html.Div(style={"width": "40px"}),
                    ThemeSwitchAIO(aio_id="theme", themes=[URL_THEME_MINTY, URL_THEME_DARKLY]),
                    html.Div(style={"width": "20px"}),
                    html.Span(
                        ["Bem-vindo, ", html.Strong(f"{user.username}", style={'color': '#0d6efd'})],
                        className="align-middle",
                        style={'fontSize': '0.9rem'}
                    ),
                    html.Div(style={"width": "15px"}),
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