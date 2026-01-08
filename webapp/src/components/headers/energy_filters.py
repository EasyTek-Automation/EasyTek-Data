# src/components/headers/dashboard_filters.py

"""
Filtros específicos para a página Dashboard.
Layout: Transversais | Período | Longitudinais
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from src.components.dropdown_footer import create_dropdown_footer


def create_energy_filters():
    """
    Cria os filtros específicos para a página Dashboard.
    Inclui seleção de equipamentos em 2 grupos e período de datas.
    
    Returns:
        html.Div: Componente com os filtros do dashboard
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
                    id="label-group1",
                    className="fw-bold mb-3",
                    style={"color": "#1f77b4", "borderBottom": "2px solid #1f77b4", "paddingBottom": "8px"}
                ),
                dcc.Dropdown(
                    id="machine-dropdown-group1",
                    options=mm_options,
                    value=["SE03_MM02", "SE03_MM04", "SE03_MM06"],
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
                    id="label-group2",
                    className="fw-bold mb-3",
                    style={"color": "#ff7f0e", "borderBottom": "2px solid #ff7f0e", "paddingBottom": "8px"}
                ),
                dcc.Dropdown(
                    id="machine-dropdown-group2",
                    options=mm_options,
                    value=["SE03_MM03", "SE03_MM05", "SE03_MM07"],
                    multi=True,
                    placeholder="Selecione equipamentos...",
                    className="machine-dropdown-group2",
                ),
            ], md=4, className="filter-column", style={"paddingLeft": "20px"}),
        ], className="g-0"),

        # Footer "Powered By"
        create_dropdown_footer()
    ], style={"padding": "20px 25px", "minWidth": "900px"}, id="dashboard-filters-content")
