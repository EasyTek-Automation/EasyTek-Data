# sidebar.py

from dash import dcc, html
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta

from flask_login import current_user # << IMPORTANTE

# --- Definições de data (mantidas como estavam) ---
today = datetime.now()
initial_start_date = (today - timedelta(hours=24)).date()
initial_end_date = today.date()
now = datetime.now()
minutes = (now.minute + 29) // 30 * 30
rounded_now = (now + timedelta(minutes=minutes - now.minute)).replace(second=0, microsecond=0)
last_24_hours = [(rounded_now - timedelta(minutes=30 * x)).strftime('%H:%M') for x in range(48)]


def create_sidebar_layout(app_instance):
   

    # --- Layout da Sidebar ---
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                

                html.Img(src="/assets/logo.png", style={"width": "50%", "max-height": "150px", "object-fit": "contain", "margin": "0 auto 20px", "display": "block"}),
                html.Hr(),
               
                html.Label("Data:", id="label-date-range"),
                dcc.DatePickerRange(id='date-picker-range', start_date=initial_start_date, end_date=initial_end_date, display_format='DD/MM/YYYY', start_date_placeholder_text='Data início', end_date_placeholder_text='Data fim'),
            ], style={"width": "100%"}),
            html.Div([
                html.Div([
                    html.Label("Hora de início:", id="label-start-hour"),
                    dcc.Dropdown(id='start-hour', options=[{'label': hour, 'value': hour} for hour in reversed(last_24_hours)], value=last_24_hours[-1])
                ], style={'display': 'inline-block', 'margin-right': '20px'}),
                html.Div([
                    html.Label("Hora de término:", id="label-end-hour"),
                    dcc.Dropdown(id='end-hour', options=[{'label': hour, 'value': hour} for hour in reversed(last_24_hours)], value=last_24_hours[0])
                ], style={'display': 'inline-block'})
            ], style={'margin-top': '20px'}),
            html.Div([
                dbc.Switch(id="auto-update-switch", label="Atualização Automática (a cada 10s)", value=False, className="d-inline-block me-2"),
                html.I(className="bi bi-info-circle", id="tooltip-target"),
                dbc.Tooltip("Quando desativado, os dados só serão atualizados ao alterar o intervalo de datas/horas.", target="tooltip-target", placement="right")
            ], style={'margin-top': '20px', 'display': 'flex', 'align-items': 'center'})
        ], style={"height": "calc(100% - 2rem)", "margin": "0"})
    ], id="sidebar-content", style={
        "flex": "1", # <<< ADICIONE ESTA LINHA DE VOLTA
        "height": "100%",
        "visibility": "visible",
        "opacity": 1,
        "overflowY": "auto",
        "transition": "opacity 0.3s ease, visibility 0s linear 0.5s"
    })
