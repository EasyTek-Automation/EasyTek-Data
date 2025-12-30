# src/components/header.py

from dash import html, dcc
import dash_bootstrap_components as dbc
from dash_bootstrap_templates import ThemeSwitchAIO
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

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


def create_dashboard_filters():
    """
    Filtros específicos para a página Dashboard.
    Layout: Transversais | Período | Longitudinais
    """
    TZ_SP = ZoneInfo("America/Sao_Paulo")

    def floor_to_30(dt: datetime) -> datetime:
        minute = 0 if dt.minute < 30 else 30
        return dt.replace(minute=minute, second=0, microsecond=0)

    now = datetime.now(TZ_SP)
    end_dt = floor_to_30(now)
    start_dt = end_dt - timedelta(hours=24)

    initial_start_date = start_dt.date()
    initial_end_date = end_dt.date()

    hours_30 = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]

    default_start_hour = start_dt.strftime("%H:%M")
    default_end_hour = end_dt.strftime("%H:%M")

    # Opções dos multimedidores
    mm_options = [
        {"label": "SE03_MM01_Geral", "value": "SE03_MM01"},
        {"label": "SE03_MM02_PR01/05", "value": "SE03_MM02"},
        {"label": "SE03_MM03_PR02/08", "value": "SE03_MM03"},
        {"label": "SE03_MM04_LCT16", "value": "SE03_MM04"},
        {"label": "SE03_MM05_LCL08", "value": "SE03_MM05"},
        {"label": "SE03_MM06_LCT08", "value": "SE03_MM06"},
        {"label": "SE03_MM07_LCL4,5", "value": "SE03_MM07"},
    ]

    return html.Div([
        dbc.Row([
            # Coluna 1: Transversais (Esquerda)
            dbc.Col([
                html.H6(
                    "Transversais",
                    id="label-group1",  # ID NECESSÁRIO PARA O CALLBACK
                    className="fw-bold mb-3",
                    style={"color": "#1f77b4", "borderBottom": "2px solid #1f77b4", "paddingBottom": "8px"}
                ),
                dcc.Dropdown(
                    id="machine-dropdown-group1",
                    options=mm_options,
                    value=["SE03_MM01"],
                    multi=True,
                    placeholder="Selecione equipamentos...",
                    className="machine-dropdown-group1",
                ),
                # Mensagem de validação
                html.Div(
                    id="validation-message",
                    style={
                        "marginTop": "8px",
                        "padding": "6px",
                        "borderRadius": "4px",
                        "fontSize": "0.75rem",
                        "display": "none"
                    }
                ),
            ], md=4, className="filter-column", style={"borderRight": "1px solid var(--bs-border-color)", "paddingRight": "20px"}),

            # Coluna 2: Período (Centro)
            dbc.Col([
                html.H6(
                    "Período",
                    className="fw-bold mb-3 text-center",
                    style={"color": "var(--bs-primary)", "borderBottom": "2px solid var(--bs-primary)", "paddingBottom": "8px"}
                ),
                
                # Data
                html.Div([
                    html.Label("Data:", id="label-date-range", className="small mb-1 d-block text-center"),
                    html.Div([
                        dcc.DatePickerRange(
                            id='date-picker-range',
                            start_date=initial_start_date,
                            end_date=initial_end_date,
                            display_format='DD/MM/YYYY',
                            start_date_placeholder_text='Início',
                            end_date_placeholder_text='Fim',
                        ),
                    ], style={"display": "flex", "justifyContent": "center"}),
                ], className="mb-3"),
                
                # Horas
                html.Div([
                    html.Div([
                        html.Label("Início:", id="label-start-hour", className="small mb-1"),
                        dcc.Dropdown(
                            id="start-hour",
                            options=[{"label": h, "value": h} for h in hours_30],
                            value=default_start_hour,
                            clearable=False,
                        )
                    ], style={"flex": "1", "marginRight": "10px"}),
                    html.Div([
                        html.Label("Término:", id="label-end-hour", className="small mb-1"),
                        dcc.Dropdown(
                            id="end-hour",
                            options=[{"label": h, "value": h} for h in hours_30],
                            value=default_end_hour,
                            clearable=False,
                        )
                    ], style={"flex": "1"}),
                ], style={"display": "flex"}),
                
            ], md=4, className="filter-column", style={"borderRight": "1px solid var(--bs-border-color)", "paddingLeft": "20px", "paddingRight": "20px"}),

            # Coluna 3: Longitudinais (Direita)
            dbc.Col([
                html.H6(
                    "Longitudinais",
                    id="label-group2",  # ID NECESSÁRIO PARA O CALLBACK
                    className="fw-bold mb-3",
                    style={"color": "#ff7f0e", "borderBottom": "2px solid #ff7f0e", "paddingBottom": "8px"}
                ),
                dcc.Dropdown(
                    id="machine-dropdown-group2",
                    options=mm_options,
                    value=[],
                    multi=True,
                    placeholder="Selecione equipamentos...",
                    className="machine-dropdown-group2",
                ),
            ], md=4, className="filter-column", style={"paddingLeft": "20px"}),
        ], className="g-0"),
    ], style={"padding": "20px 25px", "minWidth": "900px"}, id="dashboard-filters-content")


def create_states_filters():
    """
    Filtros específicos para a página States.
    Pode ser customizado conforme necessário.
    """
    return html.Div([
        html.Div([
            html.I(className="fas fa-cog fa-2x text-muted mb-3"),
            html.P("Filtros da página States", className="fw-bold mb-1"),
            html.P("Em desenvolvimento...", className="text-muted small"),
        ], className="text-center py-4")
    ], style={"padding": "1rem", "minWidth": "300px"}, id="states-filters-content")


def create_default_filters():
    """
    Filtros padrão para outras páginas.
    """
    return html.Div([
        html.Div([
            html.I(className="fas fa-filter fa-2x text-muted mb-3"),
            html.P("Nenhum filtro disponível para esta página.", className="text-muted small"),
        ], className="text-center py-4")
    ], style={"padding": "1rem", "minWidth": "250px"}, id="default-filters-content")


def get_filters_for_page(pathname):
    """
    Retorna o conteúdo de filtros baseado na página atual.
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