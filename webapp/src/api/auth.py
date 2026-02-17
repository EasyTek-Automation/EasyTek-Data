# src/api/auth.py
"""
Endpoints de autenticação e perfil de usuário
"""

from flask import jsonify
from flask_login import login_required, current_user
from . import api_bp


@api_bp.route('/ping', methods=['GET'])
@login_required
def ping():
    """
    Endpoint de teste simples.
    Retorna status OK se usuário estiver autenticado.
    """
    return jsonify({
        'status': 'ok',
        'message': 'API funcionando!',
        'user': current_user.username,
        'authenticated': True
    })


@api_bp.route('/user/profile', methods=['GET'])
@login_required
def get_user_profile():
    """
    Retorna perfil completo do usuário autenticado.
    """
    return jsonify({
        'username': current_user.username,
        'email': current_user.email,
        'level': current_user.level,
        'perfil': current_user.perfil,
    })


@api_bp.route('/user/permissions', methods=['GET'])
@login_required
def get_user_permissions():
    """
    Retorna permissões do usuário (para controle de acesso no mobile).
    """
    from src.config.access_control import ROUTE_ACCESS

    # Lista de rotas que o usuário pode acessar
    accessible_routes = []

    for route, config in ROUTE_ACCESS.items():
        min_level = config.get('min_level', 1)
        perfis = config.get('perfis', [])
        shared = config.get('shared', False)

        # Verificar se usuário tem acesso
        has_level = current_user.level >= min_level
        has_perfil = shared or (current_user.perfil in perfis)

        if has_level and has_perfil:
            accessible_routes.append(route)

    return jsonify({
        'user': current_user.username,
        'level': current_user.level,
        'perfil': current_user.perfil,
        'accessible_routes': accessible_routes
    })
