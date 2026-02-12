# callbacks_registers/change_password_callbacks.py

"""
Callbacks for Password Change Page

This module handles password changes with two modes:
1. First-time setup (blank password users)
2. Normal password change (requires current password validation)
"""

from dash import Input, Output, State
import dash_bootstrap_components as dbc
from dash import html
from werkzeug.security import check_password_hash, generate_password_hash
from bson.objectid import ObjectId
import logging

logger = logging.getLogger(__name__)


def register_change_password_callbacks(app):
    """Register all callbacks for password change page"""

    @app.callback(
        [
            Output("change-password-alert", "children"),
            Output("url", "pathname", allow_duplicate=True)
        ],
        Input("change-password-submit", "n_clicks"),
        [
            State("current-password", "value"),
            State("new-password", "value"),
            State("confirm-password", "value"),
            State("password-change-mode", "data"),
            State("user-id-store", "data"),
        ],
        prevent_initial_call=True
    )
    def change_password(n_clicks, current_password, new_password, confirm_password,
                       mode_data, user_id):
        """Handle password change with validation."""
        from dash import no_update
        from src.database.connection import get_mongo_connection

        try:
            is_first_time = mode_data.get("is_first_time", False)
            logger.info(f"[PASSWORD_CHANGE_START] is_first_time={is_first_time}, user_id={user_id}")

            # INPUT VALIDATION
            if not new_password or not confirm_password:
                return dbc.Alert([
                    html.I(className="bi bi-exclamation-triangle me-2"),
                    "Por favor, preencha a nova senha e a confirmação."
                ], color="danger"), no_update

            if len(new_password) < 8:
                return dbc.Alert([
                    html.I(className="bi bi-exclamation-triangle me-2"),
                    "A nova senha deve ter no mínimo 8 caracteres."
                ], color="danger"), no_update

            if new_password != confirm_password:
                return dbc.Alert([
                    html.I(className="bi bi-exclamation-triangle me-2"),
                    "As senhas não coincidem. Por favor, verifique."
                ], color="danger"), no_update

            # CURRENT PASSWORD VALIDATION (Normal Mode Only)
            if not is_first_time:
                try:
                    usuarios = get_mongo_connection("usuarios")
                    user_doc = usuarios.find_one({"_id": ObjectId(user_id)})

                    if not user_doc:
                        return dbc.Alert([
                            html.I(className="bi bi-x-circle me-2"),
                            "Erro: Usuário não encontrado."
                        ], color="danger"), no_update

                    if not current_password:
                        return dbc.Alert([
                            html.I(className="bi bi-exclamation-triangle me-2"),
                            "Por favor, digite sua senha atual."
                        ], color="danger"), no_update

                    if not check_password_hash(user_doc["password"], current_password):
                        logger.warning(
                            f"[PASSWORD_CHANGE_FAILED] User {user_doc.get('username')} "
                            f"provided incorrect current password"
                        )
                        return dbc.Alert([
                            html.I(className="bi bi-x-circle me-2"),
                            "Senha atual incorreta. Por favor, tente novamente."
                        ], color="danger"), no_update

                except Exception as e:
                    logger.error(f"[PASSWORD_CHANGE_ERROR] Error validating current password: {str(e)}")
                    return dbc.Alert([
                        html.I(className="bi bi-x-circle me-2"),
                        f"Erro ao validar senha: {str(e)}"
                    ], color="danger"), no_update

            # UPDATE PASSWORD
            try:
                usuarios = get_mongo_connection("usuarios")
                new_password_hash = generate_password_hash(new_password, method='pbkdf2:sha256')

                result = usuarios.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$set": {
                        "password": new_password_hash,
                        "password_set": True  # Senha foi definida
                    }}
                )

                if result.modified_count == 1:
                    user_doc = usuarios.find_one({"_id": ObjectId(user_id)})
                    username = user_doc.get("username", "unknown")

                    logger.info(
                        f"[PASSWORD_CHANGED] User '{username}' "
                        f"(first_time={is_first_time}) successfully changed password"
                    )

                    return dbc.Alert([
                        html.I(className="bi bi-check-circle me-2"),
                        "Senha alterada com sucesso! Redirecionando..."
                    ], color="success"), "/"
                else:
                    return dbc.Alert([
                        html.I(className="bi bi-x-circle me-2"),
                        "Erro ao atualizar senha. Por favor, tente novamente."
                    ], color="danger"), no_update

            except Exception as e:
                logger.error(f"[PASSWORD_CHANGE_ERROR] Error updating password: {str(e)}")
                return dbc.Alert([
                    html.I(className="bi bi-x-circle me-2"),
                    f"Erro interno: {str(e)}"
                ], color="danger"), no_update

        except Exception as e:
            logger.error(f"[PASSWORD_CHANGE_CALLBACK_ERROR] Unexpected error: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return dbc.Alert([
                html.I(className="bi bi-x-circle me-2"),
                f"Erro inesperado: {str(e)}"
            ], color="danger"), no_update
