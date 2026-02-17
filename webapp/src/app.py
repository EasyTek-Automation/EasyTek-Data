# src/app.py (Versão Corrigida e Segura)

import dash
import dash_bootstrap_components as dbc
from flask import Flask, send_from_directory, abort
from flask_login import LoginManager
import os
from pathlib import Path
from dash_bootstrap_templates import load_figure_template

# --- Constantes ---
# Recursos locais para modo offline
FONT_AWESOME = ["/assets/vendor/fontawesome/css/all.min.css"]
BOOTSTRAP_ICONS = ["/assets/vendor/bootstrap-icons/font/bootstrap-icons.min.css"]

# Define a folha de estilos que você já usa (agora local)
external_stylesheets = ["/assets/vendor/bootstrap/minty/bootstrap.min.css"]

# ADICIONE ESTA LINHA PARA CARREGAR OS TEMAS PARA OS GRÁFICOS
load_figure_template("minty")

# --- Inicialização do Servidor Flask ---
server = Flask(__name__ )

SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
   
    raise ValueError("A variável de ambiente SECRET_KEY é obrigatória e não foi definida.")

server.config.update(
    SECRET_KEY=SECRET_KEY,
    # Configurações de cookies para API REST mobile
    SESSION_COOKIE_SAMESITE='Lax',      # Permite navegação cross-location no mesmo domínio
    SESSION_COOKIE_SECURE=True,         # Exige HTTPS (produção)
    SESSION_COOKIE_HTTPONLY=True,       # Proteção contra XSS
    SESSION_COOKIE_PATH='/',            # Cookie válido para todo o domínio
    SESSION_COOKIE_NAME='etd_session',  # Nome customizado
)



# --- Inicialização do App Dash ---
app = dash.Dash(
    __name__,
    server=server,
    external_stylesheets=[
        "/assets/vendor/bootstrap/minty/bootstrap.min.css",
        "/assets/vendor/fontawesome/css/all.min.css",
        "/assets/vendor/bootstrap-icons/font/bootstrap-icons.min.css"
    ],
    suppress_callback_exceptions=True,
    title="EasyTek-Data",
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"},
        # Preload Font Awesome e Bootstrap Icons local para otimização
        {"rel": "preload", "href": "/assets/vendor/fontawesome/css/all.min.css", "as": "style"},
        {"rel": "preload", "href": "/assets/vendor/bootstrap-icons/font/bootstrap-icons.min.css", "as": "style"}
    ]
)

# --- Configuração do Favicon Customizado ---
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        <link rel="icon" type="image/x-icon" href="/assets/favicon.ico">
        <link rel="stylesheet" href="/assets/vendor/bootstrap-icons/font/bootstrap-icons.min.css">
        {%css%}
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# --- Configuração do Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(server)
login_manager.login_view = '/login'


# --- Registro da API REST ---
from src.api import api_bp
server.register_blueprint(api_bp)


# --- Rota para servir assets do volume de documentação ---
def get_docs_base_path():
    """Retorna o caminho do volume de documentação."""
    env_path = os.environ.get("DOCS_PROCEDURES_PATH")
    if env_path:
        return Path(env_path)
    # Fallback para desenvolvimento
    return Path(__file__).parent.parent.parent / "docs" / "procedures"


@server.route('/docs-assets/<path:filename>')
def serve_docs_asset(filename):
    """
    Serve arquivos estáticos (imagens, etc.) do volume de documentação.
    Rota: /docs-assets/Assets/Images/exemplo.png
    """
    docs_path = get_docs_base_path()

    # Verificação de segurança: garantir que o arquivo está dentro do volume
    try:
        requested_path = (docs_path / filename).resolve()
        if not str(requested_path).startswith(str(docs_path.resolve())):
            abort(404)
    except (OSError, ValueError):
        abort(404)

    # Verificar se o arquivo existe
    if not requested_path.exists() or not requested_path.is_file():
        abort(404)

    # Servir o arquivo
    return send_from_directory(
        requested_path.parent,
        requested_path.name
    )
