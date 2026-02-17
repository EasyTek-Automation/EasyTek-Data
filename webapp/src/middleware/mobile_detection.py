# src/middleware/mobile_detection.py
"""
Middleware para detecção de dispositivos móveis e redirecionamento automático.

Detecta user-agent de smartphones e tablets e redireciona para interface mobile.
Respeita preferência do usuário via cookie 'force_desktop'.
"""

from flask import redirect, request
import re


def is_mobile_device(user_agent_string):
    """
    Detecta se o user-agent é de um dispositivo móvel.

    Args:
        user_agent_string (str): String do user-agent

    Returns:
        bool: True se for mobile/tablet, False caso contrário
    """
    if not user_agent_string:
        return False

    # Padrões de user-agent para mobile
    mobile_patterns = [
        r'Mobile', r'Android', r'iPhone', r'iPad', r'iPod',
        r'BlackBerry', r'Windows Phone', r'webOS', r'Opera Mini',
        r'IEMobile', r'Silk', r'Kindle'
    ]

    # Compila regex case-insensitive
    pattern = re.compile('|'.join(mobile_patterns), re.IGNORECASE)

    # Verifica se match
    is_mobile = bool(pattern.search(user_agent_string))

    # Excluir tablets como "desktop" se necessário (opcional)
    # is_tablet = bool(re.search(r'iPad|Tablet', user_agent_string, re.IGNORECASE))
    # return is_mobile and not is_tablet

    return is_mobile


def mobile_redirect_middleware():
    """
    Middleware que redireciona usuários mobile para /mobile automaticamente.

    Regras:
    1. Ignora rotas de API (/api/*)
    2. Ignora assets estáticos (/assets/*, /_dash-*)
    3. Ignora rotas de autenticação (/login, /register)
    4. Respeita cookie 'force_desktop=true'
    5. Não redireciona se já está em /mobile
    6. Redireciona mobile para /mobile se detectado

    Returns:
        Response ou None: Redirect se mobile, None caso contrário
    """
    path = request.path

    # Ignorar rotas que não devem ser redirecionadas
    ignore_paths = [
        '/api/',           # API REST
        '/assets/',        # Assets estáticos
        '/_dash-',         # Assets do Dash
        '/login',          # Autenticação
        '/register',       # Registro
        '/change-password', # Mudança de senha
        '/mobile',         # Já está na versão mobile
        '/docs-assets/',   # Assets de documentação
    ]

    for ignore_path in ignore_paths:
        if path.startswith(ignore_path):
            return None

    # Verificar preferência do usuário (cookie)
    force_desktop = request.cookies.get('force_desktop') == 'true'
    if force_desktop:
        return None

    # Detectar dispositivo móvel
    user_agent = request.headers.get('User-Agent', '')
    if is_mobile_device(user_agent):
        # Redirecionar para /mobile se não estiver lá
        if not path.startswith('/mobile'):
            return redirect('/mobile' + path)

    return None


def register_mobile_middleware(app):
    """
    Registra o middleware de detecção mobile no Flask app.

    Args:
        app: Flask application instance
    """
    @app.before_request
    def check_mobile_redirect():
        return mobile_redirect_middleware()
