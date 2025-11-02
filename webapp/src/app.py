# src/app.py (Versão Corrigida e Segura)

import dash
import dash_bootstrap_components as dbc
from flask import Flask
from flask_login import LoginManager
import os
from dash_bootstrap_templates import load_figure_template

# --- Constantes ---
FONT_AWESOME = ["https://use.fontawesome.com/releases/v5.10.2/css/all.css"]

# Define a folha de estilos que você já usa
external_stylesheets = [dbc.themes.MINTY]

# ADICIONE ESTA LINHA PARA CARREGAR OS TEMAS PARA OS GRÁFICOS
load_figure_template("minty")

# --- Inicialização do Servidor Flask ---
server = Flask(__name__ )

SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
   
    raise ValueError("A variável de ambiente SECRET_KEY é obrigatória e não foi definida.")

server.config.update(SECRET_KEY=SECRET_KEY)



# --- Inicialização do App Dash ---
app = dash.Dash(
    __name__,
    server=server,
        external_stylesheets=[external_stylesheets, FONT_AWESOME],
    suppress_callback_exceptions=True,
        title="EasyTek-Data",
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"},
        
        {"rel": "preload", "href": "https://use.fontawesome.com/releases/v5.10.2/css/all.css", "as": "style"}
    ]
  )

# --- Configuração do Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(server)
login_manager.login_view = '/login'
