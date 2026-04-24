"""
Endpoints internos do webapp — consumidos apenas por outros serviços na rede Docker.
Não expostos externamente pelo Nginx.
"""
from flask import jsonify
from flask_login import current_user

from src.app import server


@server.route("/internal/validate-session")
def validate_session_internal():
    """Valida cookie de sessão para o zpp-processor (e outros serviços internos)."""
    if not current_user.is_authenticated:
        return jsonify({"valid": False}), 401

    return jsonify({
        "valid":    True,
        "level":    current_user.level,
        "username": current_user.username,
    }), 200
