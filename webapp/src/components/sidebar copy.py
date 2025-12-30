# sidebar.py

from dash import dcc, html
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta
from flask_login import current_user
from zoneinfo import ZoneInfo


def create_sidebar_layout(app_instance):
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

    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.Img(
                    src="/assets/LogoAMG.png",
                    style={
                        "width": "50%",
                        "max-height": "150px",
                        "object-fit": "contain",
                        "margin": "0 auto 20px",
                        "display": "block"
                    }
                ),
                html.Hr(),
               
                html.Label("Insira a Data:", id="label-date-range"),
                dcc.DatePickerRange(
                    id='date-picker-range',
                    start_date=initial_start_date,
                    end_date=initial_end_date,
                    display_format='DD/MM/YYYY',
                    start_date_placeholder_text='Data início',
                    end_date_placeholder_text='Data fim'
                ),
            ], style={"width": "100%"}),

            # === Transversais ===
            html.Div([
                html.Div([
                    dbc.Label(
                        "Transversais - Equipamentos",
                        id="label-group1",
                        style={"font-weight": "bold", "color": "#1f77b4", "margin-bottom": "5px"}
                    ),
                ]),
                dcc.Dropdown(
                    id="machine-dropdown-group1",
                    options=mm_options,
                    value=["SE03_MM01"],  # Valor padrão
                    multi=True,
                    placeholder="Selecione equipamentos do Transversais",
                    className="machine-dropdown-group1",
                ),
            ], style={"margin-top": "15px"}, id="container-group1"),

            # === Longitudinais ===
            html.Div([
                html.Div([
                    dbc.Label(
                        "Longitudinais - Equipamentos",
                        id="label-group2",
                        style={"font-weight": "bold", "color": "#ff7f0e", "margin-bottom": "5px"}
                    ),
                ]),
                dcc.Dropdown(
                    id="machine-dropdown-group2",
                    options=mm_options,
                    value=[],  # Vazio por padrão
                    multi=True,
                    placeholder="Selecione equipamentos do Longitudinais",
                    className="machine-dropdown-group2",
                ),
            ], style={"margin-top": "15px"}, id="container-group2"),

            # === MENSAGEM DE VALIDAÇÃO ===
            html.Div(
                id="validation-message",
                style={
                    "margin-top": "10px",
                    "padding": "8px",
                    "border-radius": "4px",
                    "font-size": "0.85rem",
                    "display": "none"
                }
            ),

            # === HORAS ===
            html.Div([
                html.Div([
                    html.Label("Hora de início:", id="label-start-hour"),
                    dcc.Dropdown(
                        id="start-hour",
                        options=[{"label": h, "value": h} for h in hours_30],
                        value=default_start_hour,
                        clearable=False
                    )
                ], style={'display': 'inline-block', 'margin-right': '20px'}),
                html.Div([
                    html.Label("Hora de término:", id="label-end-hour"),
                    dcc.Dropdown(
                        id="end-hour",
                        options=[{"label": h, "value": h} for h in hours_30],
                        value=default_end_hour,
                        clearable=False
                    )
                ], style={'display': 'inline-block'})
            ], style={'margin-top': '20px'}),

            # === AUTO-UPDATE ===
            html.Div([
                dbc.Switch(
                    id="auto-update-switch",
                    label="Atualização Automática (a cada 10s)",
                    value=False,
                    className="d-inline-block me-2"
                ),
                html.I(className="bi bi-info-circle", id="tooltip-target"),
                dbc.Tooltip(
                    "Quando desativado, os dados só serão atualizados ao alterar o intervalo de datas/horas.",
                    target="tooltip-target",
                    placement="right"
                )
            ], style={'margin-top': '20px', 'display': 'flex', 'align-items': 'center'})
        ], style={"height": "calc(100% - 2rem)", "margin": "0"})
    ], id="sidebar-content", style={
        "flex": "1",
        "height": "100%",
        "visibility": "visible",
        "opacity": 1,
        "overflowY": "auto",
        "transition": "opacity 0.3s ease, visibility 0s linear 0.5s"
    })