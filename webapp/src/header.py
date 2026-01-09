# src/header.py

"""
Componente de cabeçalho (header) principal da aplicação.

ATUALIZADO: 
- Menus filtrados por perfil do usuário (controle de acesso matricial)
- Área direita simplificada: Filtros + Theme Switch + Perfil (dropdown)
- Ícones padronizados em todos os menus e submenus
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
from dash_bootstrap_templates import ThemeSwitchAIO

# Importações de ícones
from src.components.icons import (
    hamburger_icon,
    dashboard_icon,
    states_icon,
    supervisory_icon,
    temperature_control_icon,
    filter_icon,
    home_icon,
    maintenance_icon,
    production_icon,
    energy_icon,
    alarm_icon,
    utilities_icon,
    profile_icon,
    users_icon,
    settings_icon,
    water_icon,
    gas_icon,
    compressed_air_icon,
    clipboard_icon,
    calendar_icon,
    history_icon,
    graph_icon,
    sliders_icon,
    logs_icon,
    logout_icon,
    speedometer_icon,
    user_create_icon,
)
from src.config.theme_config import URL_THEME_MINTY, URL_THEME_DARKLY

# Importações dos filtros específicos de cada página
from src.components.headers import (
    create_energy_filters,
    create_states_filters,
    create_default_filters
)

# Footer reutilizável para dropdowns
from src.components.dropdown_footer import create_dropdown_footer

# Sistema de Permissões
from src.utils.permissions import can_see_menu


def get_filters_for_page(pathname):
    """Retorna o conteúdo de filtros baseado na página atual."""
    if pathname in ["/"]:
        return create_default_filters()
    elif pathname == "/production/states":
        return create_states_filters()
    elif pathname in ["/energy", "/utilities/energy"]:
        return create_energy_filters()
    else:
        return create_default_filters()


def create_header(pathname, user):
    """Cria e retorna o componente de cabeçalho (header) da aplicação."""
    
    # ========================================
    # MENU DE NAVEGAÇÃO
    # ========================================
    
    # 🏠 HOME
    home_link = dbc.NavItem(
        dbc.NavLink(
            html.Div([
                html.Span(home_icon(), style={"marginRight": "8px"}),
                html.Span("Início", style={"fontWeight": "600"})
            ], className="d-flex align-items-center"),
            href="/",
            active=(pathname == "/"),
        )
    )
    
    # 🔧 MANUTENÇÃO
    maintenance_dropdown = dbc.DropdownMenu(
        label=html.Div([
            html.Span(maintenance_icon(), style={"marginRight": "8px"}),
            html.Span("Manutenção", style={"fontWeight": "600"})
        ], className="d-flex align-items-center"),
        children=[
            html.Div([
                dbc.DropdownMenuItem(
                    html.Div([html.Span(clipboard_icon(), style={"marginRight": "8px"}), "Ordens de Serviço"], className="d-flex align-items-center"),
                    href="/maintenance/work-orders", disabled=True, style={"opacity": "0.5"}
                ),
                dbc.DropdownMenuItem(
                    html.Div([html.Span(calendar_icon(), style={"marginRight": "8px"}), "Plano de Manutenção"], className="d-flex align-items-center"),
                    href="/maintenance/schedule", disabled=True, style={"opacity": "0.5"}
                ),
                dbc.DropdownMenuItem(divider=True),
                dbc.DropdownMenuItem(
                    html.Div([html.Span(alarm_icon(), style={"marginRight": "8px"}), "Alarmes"], className="d-flex align-items-center"),
                    href="/maintenance/alarms", active=(pathname == "/maintenance/alarms"),
                ),
                dbc.DropdownMenuItem(
                    html.Div([html.Span(clipboard_icon(), style={"marginRight": "8px"}), "Procedimentos"], className="d-flex align-items-center"),
                    href="/maintenance/procedures", active=(pathname == "/maintenance/procedures"),
                ),
                dbc.DropdownMenuItem(divider=True),
                dbc.DropdownMenuItem(
                    html.Div([html.Span(history_icon(), style={"marginRight": "8px"}), "Histórico de Intervenções"], className="d-flex align-items-center"),
                    href="/maintenance/history", disabled=True, style={"opacity": "0.5"}
                ),
                dbc.DropdownMenuItem(
                    html.Div([html.Span(graph_icon(), style={"marginRight": "8px"}), "Indicadores de Manutenção"], className="d-flex align-items-center"),
                    href="/maintenance/indicators", disabled=True, style={"opacity": "0.5"}
                ),

                # Footer "Powered By"
                create_dropdown_footer()
            ], className="simple-dropdown-menu dropdown-menu-with-footer")
        ],
        nav=True, in_navbar=True,
        toggle_style={"display": "inline-flex", "alignItems": "center", "gap": "4px", "fontWeight": "600"}
    )
    
    # 🏭 PRODUÇÃO
    production_dropdown = dbc.DropdownMenu(
        label=html.Div([
            html.Span(production_icon(), style={"marginRight": "8px"}),
            html.Span("Produção", style={"fontWeight": "600"})
        ], className="d-flex align-items-center"),
        children=[
            html.Div([
                dbc.DropdownMenuItem(
                    html.Div([html.Span(dashboard_icon(), style={"marginRight": "8px"}), "Dashboard OEE"], className="d-flex align-items-center"),
                    href="/production/oee", active=(pathname == "/production/oee")
                ),
                dbc.DropdownMenuItem(
                    html.Div([html.Span(states_icon(), style={"marginRight": "8px"}), "Estados da Linha"], className="d-flex align-items-center"),
                    href="/production/states", active=(pathname == "/production/states")
                ),

                # Footer "Powered By"
                create_dropdown_footer()
            ], className="simple-dropdown-menu dropdown-menu-with-footer")
        ],
        nav=True, in_navbar=True,
        toggle_style={"display": "inline-flex", "alignItems": "center", "gap": "4px", "fontWeight": "600"}
    )
    
    # 💧 UTILIDADES - MEGA MENU
    utilities_dropdown = dbc.DropdownMenu(
        label=html.Div([
            html.Span(utilities_icon(), style={"marginRight": "8px"}),
            html.Span("Utilidades", style={"fontWeight": "600"})
        ], className="d-flex align-items-center"),
        children=[
            html.Div([
                dbc.Row([
                    # COLUNA 1: ENERGIA
                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.Span(energy_icon(), style={"marginRight": "6px"}),
                                html.Span("Energia Elétrica", style={"fontWeight": "600", "fontSize": "0.9rem"})
                            ], className="d-flex align-items-center mb-2 px-2", style={"color": "var(--bs-primary)"}),
                            dbc.DropdownMenuItem(
                                "📊 Visão Geral",
                                href="/utilities/energy",
                                active=(pathname == "/utilities/energy"),
                                style={"fontSize": "0.85rem", "paddingLeft": "0.5rem"}
                            ),
                            html.Div("Subestações:", className="mt-2 mb-1 px-2", style={"fontSize": "0.75rem", "opacity": "0.7", "fontWeight": "600"}),
                            dbc.DropdownMenuItem("• SE01 - Principal", href="/utilities/energy/se01", disabled=True, style={"fontSize": "0.8rem", "opacity": "0.5", "paddingLeft": "1rem"}),
                            dbc.DropdownMenuItem("• SE02 - Produção", href="/utilities/energy/se02", disabled=True, style={"fontSize": "0.8rem", "opacity": "0.5", "paddingLeft": "1rem"}),
                            dbc.DropdownMenuItem("• SE03 - AMG", href="/utilities/energy/se03", active=(pathname == "/utilities/energy/se03"), style={"fontSize": "0.8rem", "paddingLeft": "1rem"}),
                            dbc.DropdownMenuItem("• SE04 - Auxiliar", href="/utilities/energy/se04", disabled=True, style={"fontSize": "0.8rem", "opacity": "0.5", "paddingLeft": "1rem"}),
                            dbc.DropdownMenuItem(
                                "📈 Histórico",
                                href="/utilities/energy/history",
                                disabled=True,
                                style={"fontSize": "0.85rem", "opacity": "0.5", "paddingLeft": "0.5rem"}
                            ),
                            dbc.DropdownMenuItem(
                                "⚙️ Configurações",
                                href="/utilities/energy/config",
                                disabled=False,
                                style={"fontSize": "0.85rem", "paddingLeft": "0.5rem"}
                            ),
                            dbc.DropdownMenuItem(
                                "💰 Custos",
                                href="/utilities/energy/costs",
                                disabled=True,
                                style={"fontSize": "0.85rem", "opacity": "0.5", "paddingLeft": "0.5rem"}
                            ),
                        ], style={"minHeight": "200px"})
                    ], width=3, className="border-end"),
                    
                    # COLUNA 2: ÁGUA
                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.Span(water_icon(), style={"marginRight": "6px"}),
                                html.Span("Água", style={"fontWeight": "600", "fontSize": "0.9rem"})
                            ], className="d-flex align-items-center mb-2 px-2", style={"color": "#0dcaf0"}),
                            dbc.DropdownMenuItem(
                                "📊 Visão Geral",
                                href="/utilities/water",
                                disabled=True,
                                style={"fontSize": "0.85rem", "paddingLeft": "0.5rem"}
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
                    
                    # COLUNA 3: GÁS
                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.Span(gas_icon(), style={"marginRight": "6px"}),
                                html.Span("Gás Natural", style={"fontWeight": "600", "fontSize": "0.9rem"})
                            ], className="d-flex align-items-center mb-2 px-2", style={"color": "#fd7e14"}),
                            dbc.DropdownMenuItem(
                                "📊 Visão Geral",
                                href="/utilities/gas",
                                disabled=True,
                                style={"fontSize": "0.85rem", "paddingLeft": "0.5rem"}
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
                    
                    # COLUNA 4: AR COMPRIMIDO
                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.Span(compressed_air_icon(), style={"marginRight": "6px"}),
                                html.Span("Ar Comprimido", style={"fontWeight": "600", "fontSize": "0.9rem"})
                            ], className="d-flex align-items-center mb-2 px-2", style={"color": "#6c757d"}),
                            dbc.DropdownMenuItem(
                                "📊 Visão Geral",
                                href="/utilities/compressed-air",
                                disabled=True,
                                style={"fontSize": "0.85rem", "paddingLeft": "0.5rem"}
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
                            dbc.DropdownMenuItem(
                                "💰 Custos",
                                href="/utilities/compressed-air/costs",
                                disabled=True,
                                style={"fontSize": "0.85rem", "opacity": "0.5", "paddingLeft": "0.5rem"}
                            ),
                        ], style={"minHeight": "200px"})
                    ], width=3),
                ], className="g-0"),
                html.Hr(className="my-2"),
                dbc.DropdownMenuItem(
                    html.Div([html.Span(speedometer_icon(), style={"marginRight": "8px"}), "Dashboard Integrado de Utilidades"], className="d-flex align-items-center justify-content-center"),
                    href="/utilities/dashboard", disabled=True, className="text-center", style={"fontSize": "0.9rem", "opacity": "0.5", "fontWeight": "500"}
                ),

                # Footer "Powered By"
                create_dropdown_footer()
            ], style={"padding": "15px", "minWidth": "750px"})
        ],
        nav=True, in_navbar=True,
        toggle_style={"display": "inline-flex", "alignItems": "center", "gap": "4px", "fontWeight": "600"},
        direction="down",
    )
    
    # 🖥️ SUPERVISÓRIO
    supervision_dropdown = dbc.DropdownMenu(
        label=html.Div([
            html.Span(supervisory_icon(), style={"marginRight": "8px"}),
            html.Span("Supervisório", style={"fontWeight": "600"})
        ], className="d-flex align-items-center"),
        children=[
            html.Div([
                dbc.DropdownMenuItem(
                    html.Div(
                        [html.Span(temperature_control_icon(), style={"marginRight": "8px"}), "Controle de Temperatura"],
                        className="d-flex align-items-center"), href="/supervision", active=(pathname == "/supervision")


                ),

                # Footer "Powered By"
                create_dropdown_footer()
            ], className="simple-dropdown-menu dropdown-menu-with-footer")
        ],
        nav=True, in_navbar=True,
        toggle_style={"display": "inline-flex", "alignItems": "center", "gap": "4px", "fontWeight": "600"}
    )
    
    # ⚙️ CONFIGURAÇÕES
    config_dropdown = dbc.DropdownMenu(
        label=html.Div([
            html.Span(settings_icon(), style={"marginRight": "8px"}),
            html.Span("Configurações", style={"fontWeight": "600"})
        ], className="d-flex align-items-center"),
        children=[
            html.Div([
                dbc.DropdownMenuItem(
                    html.Div([html.Span(users_icon(), style={"marginRight": "8px"}), "Gerenciar Usuários"], className="d-flex align-items-center"),
                    href="/config/users", active=(pathname == "/config/users")
                ),
                dbc.DropdownMenuItem(
                    html.Div([
                        html.Span(user_create_icon(), style={"marginRight": "8px"}),
                        "Criar Novo Usuário"
                    ], className="d-flex align-items-center"),
                    href="/config/users/create",
                    active=(pathname == "/config/users/create")
                ),
                dbc.DropdownMenuItem(divider=True),
                dbc.DropdownMenuItem(
                    html.Div([html.Span(sliders_icon(), style={"marginRight": "8px"}), "Preferências"], className="d-flex align-items-center"),
                    href="/config/preferences", disabled=True, style={"opacity": "0.5"}
                ),
                dbc.DropdownMenuItem(
                    html.Div([html.Span(logs_icon(), style={"marginRight": "8px"}), "Logs do Sistema"], className="d-flex align-items-center"),
                    href="/config/logs", disabled=True, style={"opacity": "0.5"}
                ),

                # Footer "Powered By"
                create_dropdown_footer()
            ], className="simple-dropdown-menu dropdown-menu-with-footer")
        ],
        nav=True, in_navbar=True,
        toggle_style={"display": "inline-flex", "alignItems": "center", "gap": "4px", "fontWeight": "600"}
    )
    
    # ========================================
    # MONTAR NAVBAR COM PERMISSÕES
    # ========================================
    nav_items = []
    if can_see_menu(user, "home"):
        nav_items.append(home_link)
    if can_see_menu(user, "manutencao"):
        nav_items.append(maintenance_dropdown)
    if can_see_menu(user, "producao"):
        nav_items.append(production_dropdown)
    if can_see_menu(user, "utilidades"):
        nav_items.append(utilities_dropdown)
    if can_see_menu(user, "supervisorio"):
        nav_items.append(supervision_dropdown)
    if can_see_menu(user, "configuracoes"):
        nav_items.append(config_dropdown)
    
    navigation_menu = dbc.Nav(nav_items, navbar=True, className="ms-3")

    # ========================================
    # DROPDOWN DE FILTROS
    # ========================================
    filters_dropdown = dbc.DropdownMenu(
        label=html.Div([
            html.Span(filter_icon(), style={"marginRight": "8px"}),
            html.Span("Filtros", style={"fontWeight": "600"})
        ], className="d-flex align-items-center"),
        children=[get_filters_for_page(pathname)],
        nav=True, in_navbar=True, align_end=True, id="filters-dropdown-menu",
        toggle_style={"display": "inline-flex", "alignItems": "center", "gap": "4px", "fontWeight": "600"}
    )

    # ========================================
    # INFORMAÇÕES DO USUÁRIO
    # ========================================
    user_perfil = getattr(user, 'perfil', 'N/A') if user else 'N/A'
    user_level = getattr(user, 'level', 0) if user else 0
    user_name = getattr(user, 'username', 'Usuário') if user else 'Usuário'
    user_email = getattr(user, 'email', '') if user else ''
    
    perfil_colors = {
        "manutencao": "primary", "qualidade": "success", "producao": "warning",
        "utilidades": "info", "admin": "danger"
    }
    perfil_color = perfil_colors.get(user_perfil, "secondary")
    
    perfil_labels = {
        "manutencao": "Manutenção", "qualidade": "Qualidade", "producao": "Produção",
        "utilidades": "Utilidades", "admin": "Administrador"
    }
    perfil_label = perfil_labels.get(user_perfil, user_perfil)

    # ========================================
    # DROPDOWN DE PERFIL (NOVO!)
    # ========================================
    profile_dropdown = dbc.DropdownMenu(
        label=html.Span(profile_icon()),
        children=[
            # Cabeçalho com info do usuário
            html.Div([
                html.Div([
                    html.I(className="bi bi-person-circle", style={"fontSize": "2.5rem", "color": "var(--bs-primary)"})
                ], className="text-center mb-2"),
                html.H6(user_name, className="mb-0 text-center", style={"fontWeight": "600"}),
                html.Small(user_email, className="text-muted d-block text-center") if user_email else None,
                html.Div([
                    dbc.Badge(perfil_label, color=perfil_color, className="me-1"),
                    dbc.Badge(f"Nível {user_level}", color="secondary"),
                ], className="text-center py-2"),
            ], style={"minWidth": "220px", "padding": "12px", "borderBottom": "1px solid var(--bs-border-color)"}),
            
            # Opções
            dbc.DropdownMenuItem(
                html.Div([html.I(className="bi bi-person-gear me-2"), "Meu Perfil"], className="d-flex align-items-center"),
                href="/config/profile", disabled=True, style={"opacity": "0.5"}
            ),
            dbc.DropdownMenuItem(
                html.Div([html.I(className="bi bi-bell me-2"), "Notificações"], className="d-flex align-items-center"),
                href="/notifications", disabled=True, style={"opacity": "0.5"}
            ),
            dbc.DropdownMenuItem(
                html.Div([html.I(className="bi bi-shield-lock me-2"), "Alterar Senha"], className="d-flex align-items-center"),
                href="/change-password"
            ),
            dbc.DropdownMenuItem(divider=True),
            
            # Logout
            dbc.DropdownMenuItem(
                html.Div([html.Span(logout_icon(), style={"marginRight": "8px"}), "Sair"], className="d-flex align-items-center text-danger"),
                id="logout_button", style={"cursor": "pointer"}
            ),

            # Footer "Powered By"
            create_dropdown_footer()
        ],
        nav=True, in_navbar=True, align_end=True, caret=False,
        toggle_style={
            "display": "inline-flex", "alignItems": "center",
            "padding": "6px 10px", "borderRadius": "50%",
            "border": "2px solid var(--bs-border-color)",
        },
    )

    # ========================================
    # LAYOUT FINAL DO HEADER
    # ========================================
    header_layout = html.Div([
        # LADO ESQUERDO
        html.Div([
            dbc.Button(hamburger_icon(), id="collapse-sidebar-btn", color="primary", size="sm", className="me-2"),
            navigation_menu,
        ], className="d-flex align-items-center"),

        # LADO DIREITO (simplificado)
        html.Div([
            filters_dropdown,
            html.Div(style={"width": "5px"}),
            html.Div(ThemeSwitchAIO(aio_id="theme", themes=[URL_THEME_MINTY, URL_THEME_DARKLY]), style={"width": "80px"}),
            html.Div(style={"width": "5px"}),
            profile_dropdown,
        ], className="d-flex align-items-center"),
    ],
    id="header",
    style={
        "position": "fixed", "top": 0, "left": 0, "right": 0,
        "height": "60px", "padding": "0 1rem", "zIndex": 1020,
        "display": "flex", "alignItems": "center", "justifyContent": "space-between",
        "background": "var(--bs-body-bg, #fff)",
        "borderBottom": "1px solid var(--bs-border-color, #dee2e6)",
    })

    return header_layout