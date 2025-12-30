# src/app.py (VERSÃO FINAL OFFLINE)
import dash
import dash_bootstrap_components as dbc
from flask import Flask
from flask_login import LoginManager
import os
from dash_bootstrap_templates import load_figure_template

# --- Constantes ---
load_figure_template("minty")

# --- Inicialização do Servidor Flask ---
server = Flask(__name__)

SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError(
        "❌ ERRO: A variável de ambiente SECRET_KEY não foi definida!\n"
        "   Crie um arquivo .env com: SECRET_KEY=sua_chave_secreta_aqui"
    )

server.config.update(SECRET_KEY=SECRET_KEY)

# ========== MODO OFFLINE ==========
# Usa arquivos CSS locais ao invés de CDN
external_stylesheets = [
    '/assets/bootstrap.min.css',  # Bootstrap local
    '/assets/fontawesome.min.css'  # Font Awesome local
]

# --- Inicialização do App Dash ---
app = dash.Dash(
    __name__,
    server=server,
    external_stylesheets=external_stylesheets,
    suppress_callback_exceptions=True,
    title="EasyTek-Data",
    serve_locally=True,  # CRÍTICO: Serve todos os assets localmente
    assets_folder='assets',
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"},
    ]
)

# --- Configuração do Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(server)
login_manager.login_view = '/login'