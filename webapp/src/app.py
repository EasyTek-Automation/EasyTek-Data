# src/app.py (Versão Corrigida e Segura)

import dash
import dash_bootstrap_components as dbc
from flask import Flask, send_from_directory, abort, request
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


# --- Registro do Middleware de Detecção Mobile ---
from src.middleware import mobile_redirect_middleware
from src.middleware.mobile_detection import register_mobile_middleware
register_mobile_middleware(server)


# --- Rota Placeholder para Mobile (será substituída por Next.js via NPM) ---
from flask import render_template_string, make_response

@server.route('/mobile')
@server.route('/mobile/')
@server.route('/mobile/<path:subpath>')
def mobile_placeholder(subpath=None):
    """
    Rota placeholder para interface mobile.

    Em produção, o Nginx Proxy Manager roteará /mobile para o container Next.js.
    Em desenvolvimento, mostra mensagem informativa.
    """
    html = '''
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AMG Mobile - Em Desenvolvimento</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .container {
                background: white;
                border-radius: 20px;
                padding: 40px;
                max-width: 500px;
                text-align: center;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }
            h1 {
                color: #667eea;
                font-size: 28px;
                margin-bottom: 20px;
            }
            p {
                color: #666;
                line-height: 1.6;
                margin-bottom: 15px;
            }
            .badge {
                display: inline-block;
                background: #48bb78;
                color: white;
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 14px;
                font-weight: 600;
                margin-top: 20px;
            }
            .info {
                background: #f7fafc;
                border-left: 4px solid #4299e1;
                padding: 15px;
                margin-top: 20px;
                text-align: left;
                border-radius: 4px;
            }
            .info strong { color: #2d3748; }
            a {
                color: #667eea;
                text-decoration: none;
                font-weight: 600;
            }
            a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📱 Interface Mobile Detectada!</h1>
            <p>Você foi redirecionado automaticamente para a versão mobile.</p>

            <div class="badge">✨ Detecção Automática Funcionando</div>

            <div class="info">
                <strong>Status:</strong> Middleware ativo<br>
                <strong>User-Agent:</strong> {{ user_agent }}<br>
                <strong>Caminho:</strong> {{ path }}
            </div>

            <p style="margin-top: 20px; font-size: 14px;">
                <a href="/?desktop=true">🖥️ Forçar versão desktop</a>
            </p>

            <p style="margin-top: 30px; font-size: 12px; color: #999;">
                Em produção, esta rota será servida pelo Next.js via Nginx Proxy Manager.
            </p>
        </div>
    </body>
    </html>
    '''

    response = make_response(
        render_template_string(
            html,
            user_agent=request.headers.get('User-Agent', 'Desconhecido'),
            path=request.path
        )
    )

    # Se query param ?desktop=true, setar cookie
    if request.args.get('desktop') == 'true':
        response.set_cookie('force_desktop', 'true', max_age=30*24*60*60)  # 30 dias

    return response


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
