# callbacks_registers/manage_users_callbacks.py

"""
Callbacks for User Management Page

This module handles user management operations:
- List users (with RBAC filtering)
- Edit username and email
- Reset user password
- Delete user
"""

from dash import Input, Output, State, html, dash_table, callback_context, ALL
import dash_bootstrap_components as dbc
from werkzeug.security import generate_password_hash
from bson.objectid import ObjectId
import logging

logger = logging.getLogger(__name__)


def register_manage_users_callbacks(app):
    """Register all callbacks for user management page"""

    # ============================================
    # CALLBACK 1: Show Admin Permissions Info
    # ============================================
    @app.callback(
        Output("manage-permissions-info", "children"),
        Input("manage-admin-user-perfil", "data")
    )
    def show_manage_permissions(admin_perfil):
        """Display what users the admin can manage"""
        if admin_perfil == "admin":
            return dbc.Alert([
                html.I(className="bi bi-shield-check me-2"),
                "Você tem privilégios de Administrador: pode gerenciar usuários de todos os departamentos."
            ], color="info", className="mb-0")
        else:
            perfil_map = {
                "manutencao": "Manutenção", "qualidade": "Qualidade",
                "producao": "Produção", "utilidades": "Utilidades",
                "meio_ambiente": "Meio Ambiente", "seguranca": "Segurança",
                "engenharias": "Engenharias"
            }
            dept_name = perfil_map.get(admin_perfil, admin_perfil)
            return dbc.Alert([
                html.I(className="bi bi-info-circle me-2"),
                f"Você pode gerenciar apenas usuários do departamento {dept_name}."
            ], color="warning", className="mb-0")

    # ============================================
    # CALLBACK 2: Populate Department Filter
    # ============================================
    @app.callback(
        Output("user-filter-department", "options"),
        Input("manage-admin-user-perfil", "data")
    )
    def populate_department_filter(admin_perfil):
        """Populate department filter based on admin permissions"""
        from src.config.access_control import PERFIS

        perfil_labels = {
            "producao": "📊 Produção", "manutencao": "🔧 Manutenção",
            "qualidade": "✓ Qualidade", "meio_ambiente": "🌿 Meio Ambiente",
            "seguranca": "🛡️ Segurança", "engenharias": "🛠️ Engenharias",
            "utilidades": "💧 Utilidades", "admin": "👑 Administrador"
        }

        if admin_perfil == "admin":
            # Admin can filter by any department
            return [{"label": perfil_labels.get(p, p), "value": p} for p in PERFIS]
        else:
            # Others can only see their own department
            return [{"label": perfil_labels.get(admin_perfil, admin_perfil), "value": admin_perfil}]

    # ============================================
    # CALLBACK 3: Load Users Table
    # ============================================
    @app.callback(
        [
            Output("users-table-container", "children"),
            Output("users-table-loading", "children")
        ],
        [
            Input("refresh-users-button", "n_clicks"),
            Input("refresh-users-table", "n_intervals"),
            Input("user-filter-department", "value"),
            Input("user-search-input", "value")
        ],
        [
            State("manage-admin-user-perfil", "data"),
            State("manage-admin-user-level", "data")
        ]
    )
    def load_users_table(n_clicks, n_intervals, filter_dept, search_query, admin_perfil, admin_level):
        """Load and display users table with RBAC filtering"""
        from dash import no_update
        from src.database.connection import get_mongo_connection

        try:
            usuarios = get_mongo_connection("usuarios")

            # Build query based on RBAC
            query = {}

            # Admin can see all, others only their department
            if admin_perfil != "admin":
                query["perfil"] = admin_perfil
            elif filter_dept:
                # Admin with filter selected
                query["perfil"] = filter_dept

            # Apply search filter
            if search_query:
                query["$or"] = [
                    {"username": {"$regex": search_query, "$options": "i"}},
                    {"email": {"$regex": search_query, "$options": "i"}}
                ]

            # Fetch users
            users_cursor = usuarios.find(query)
            users_list = []

            perfil_labels = {
                "producao": "Produção", "manutencao": "Manutenção",
                "qualidade": "Qualidade", "meio_ambiente": "Meio Ambiente",
                "seguranca": "Segurança", "engenharias": "Engenharias",
                "utilidades": "Utilidades", "admin": "Administrador"
            }

            for user in users_cursor:
                # Usar campo password_set (RÁPIDO!) em vez de check_password_hash (LENTO!)
                password_set = user.get("password_set", True)  # Default True para usuários antigos

                users_list.append({
                    "id": str(user["_id"]),
                    "username": user.get("username", "N/A"),
                    "email": user.get("email", "N/A"),
                    "perfil": perfil_labels.get(user.get("perfil", ""), user.get("perfil", "N/A")),
                    "perfil_raw": user.get("perfil", ""),
                    "level": user.get("level", 1),
                    "status": "🔓 Senha Temporária" if not password_set else "✅ Ativo",
                    "actions": user.get("username", "")  # For action buttons
                })

            if not users_list:
                return html.Div([
                    html.I(className="bi bi-inbox", style={"fontSize": "3rem", "color": "#ccc"}),
                    html.H5("Nenhum usuário encontrado", className="mt-3 text-muted")
                ], className="text-center py-5"), ""

            # Create table with action buttons
            table_rows = []
            for user in users_list:
                table_rows.append(
                    html.Tr([
                        html.Td(user["username"], className="align-middle"),
                        html.Td(user["email"], className="align-middle"),
                        html.Td(
                            dbc.Badge(user["perfil"], color="primary", className="px-3 py-2"),
                            className="align-middle"
                        ),
                        html.Td(
                            dbc.Badge(f"Nível {user['level']}", color="secondary", className="px-3 py-2"),
                            className="align-middle"
                        ),
                        html.Td(user["status"], className="align-middle"),
                        html.Td([
                            dbc.ButtonGroup([
                                dbc.Button(
                                    [
                                        html.I(className="bi bi-pencil-square me-1"),
                                        "Editar"
                                    ],
                                    id={"type": "edit-user-btn", "index": user["id"]},
                                    color="info",
                                    outline=True,
                                    size="sm"
                                ),
                                dbc.Button(
                                    [
                                        html.I(className="bi bi-key-fill me-1"),
                                        "Resetar"
                                    ],
                                    id={"type": "reset-password-btn", "index": user["id"]},
                                    color="warning",
                                    outline=True,
                                    size="sm"
                                ),
                                dbc.Button(
                                    [
                                        html.I(className="bi bi-trash-fill me-1"),
                                        "Deletar"
                                    ],
                                    id={"type": "delete-user-btn", "index": user["id"]},
                                    color="danger",
                                    outline=True,
                                    size="sm"
                                ),
                            ])
                        ], className="align-middle text-end")
                    ])
                )

            table = dbc.Table([
                html.Thead([
                    html.Tr([
                        html.Th("Usuário"),
                        html.Th("E-mail"),
                        html.Th("Departamento"),
                        html.Th("Nível"),
                        html.Th("Status"),
                        html.Th("Ações", className="text-end"),
                    ])
                ]),
                html.Tbody(table_rows)
            ], bordered=True, hover=True, responsive=True, striped=True)

            return table, ""

        except Exception as e:
            logger.error(f"[LOAD_USERS_ERROR] {str(e)}")
            return html.Div([
                html.I(className="bi bi-exclamation-triangle", style={"fontSize": "2rem", "color": "#dc3545"}),
                html.H5(f"Erro ao carregar usuários: {str(e)}", className="mt-3 text-danger")
            ], className="text-center py-5"), ""

    # ============================================
    # CALLBACK 4: Reset User Password
    # ============================================
    @app.callback(
        Output("manage-users-alert", "children"),
        Input({"type": "reset-password-btn", "index": ALL}, "n_clicks"),
        [
            State("manage-admin-user-perfil", "data"),
            State("manage-admin-user-level", "data")
        ],
        prevent_initial_call=True
    )
    def reset_user_password(n_clicks_list, admin_perfil, admin_level):
        """Reset user password to blank (force first-time login)"""
        from dash import no_update
        from src.database.connection import get_mongo_connection

        # Check which button was clicked
        ctx = callback_context
        if not ctx.triggered or not any(n_clicks_list):
            return no_update

        # Get the user ID from the button that was clicked
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        import json
        button_data = json.loads(button_id)
        user_id = button_data["index"]

        try:
            usuarios = get_mongo_connection("usuarios")
            target_user = usuarios.find_one({"_id": ObjectId(user_id)})

            if not target_user:
                return dbc.Alert([
                    html.I(className="bi bi-x-circle me-2"),
                    "Erro: Usuário não encontrado."
                ], color="danger", dismissable=True)

            # RBAC Check: Admin can reset any, others only their department
            if admin_perfil != "admin" and target_user.get("perfil") != admin_perfil:
                logger.warning(
                    f"[PERMISSION_DENIED] User '{admin_perfil}' attempted to reset password "
                    f"for user '{target_user.get('username')}' from department '{target_user.get('perfil')}'"
                )
                return dbc.Alert([
                    html.I(className="bi bi-shield-x me-2"),
                    "PERMISSÃO NEGADA: Você só pode resetar senhas de usuários do seu departamento."
                ], color="danger", dismissable=True)

            # Reset password to blank (hash of empty string)
            blank_password_hash = generate_password_hash("", method='pbkdf2:sha256')

            result = usuarios.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {
                    "password": blank_password_hash,
                    "password_set": False  # Senha resetada - aguardando redefinição
                }}
            )

            if result.modified_count == 1:
                logger.info(
                    f"[PASSWORD_RESET] Admin '{admin_perfil}' reset password for user '{target_user.get('username')}'"
                )
                return dbc.Alert([
                    html.I(className="bi bi-check-circle me-2"),
                    f"Senha resetada com sucesso para o usuário '{target_user.get('username')}'. "
                    f"O usuário será obrigado a criar nova senha no próximo login."
                ], color="success", dismissable=True, duration=4000)
            else:
                return dbc.Alert([
                    html.I(className="bi bi-x-circle me-2"),
                    "Erro ao resetar senha."
                ], color="danger", dismissable=True)

        except Exception as e:
            logger.error(f"[PASSWORD_RESET_ERROR] {str(e)}")
            return dbc.Alert([
                html.I(className="bi bi-x-circle me-2"),
                f"Erro interno: {str(e)}"
            ], color="danger", dismissable=True)

    # ============================================
    # CALLBACK 5: Delete User
    # ============================================
    @app.callback(
        Output("manage-users-alert", "children", allow_duplicate=True),
        Input({"type": "delete-user-btn", "index": ALL}, "n_clicks"),
        [
            State("manage-admin-user-perfil", "data"),
            State("manage-admin-user-level", "data")
        ],
        prevent_initial_call=True
    )
    def delete_user(n_clicks_list, admin_perfil, admin_level):
        """Delete user from database"""
        from dash import no_update
        from src.database.connection import get_mongo_connection

        # Check which button was clicked
        ctx = callback_context
        if not ctx.triggered or not any(n_clicks_list):
            return no_update

        # Get the user ID from the button that was clicked
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        import json
        button_data = json.loads(button_id)
        user_id = button_data["index"]

        try:
            usuarios = get_mongo_connection("usuarios")
            target_user = usuarios.find_one({"_id": ObjectId(user_id)})

            if not target_user:
                return dbc.Alert([
                    html.I(className="bi bi-x-circle me-2"),
                    "Erro: Usuário não encontrado."
                ], color="danger", dismissable=True)

            # RBAC Check: Admin can delete any, others only their department
            if admin_perfil != "admin" and target_user.get("perfil") != admin_perfil:
                logger.warning(
                    f"[PERMISSION_DENIED] User '{admin_perfil}' attempted to delete "
                    f"user '{target_user.get('username')}' from department '{target_user.get('perfil')}'"
                )
                return dbc.Alert([
                    html.I(className="bi bi-shield-x me-2"),
                    "PERMISSÃO NEGADA: Você só pode deletar usuários do seu departamento."
                ], color="danger", dismissable=True)

            # Delete user
            result = usuarios.delete_one({"_id": ObjectId(user_id)})

            if result.deleted_count == 1:
                logger.info(
                    f"[USER_DELETED] Admin '{admin_perfil}' deleted user '{target_user.get('username')}' "
                    f"(perfil: {target_user.get('perfil')}, level: {target_user.get('level')})"
                )
                return dbc.Alert([
                    html.I(className="bi bi-check-circle me-2"),
                    f"Usuário '{target_user.get('username')}' deletado com sucesso."
                ], color="success", dismissable=True, duration=4000)
            else:
                return dbc.Alert([
                    html.I(className="bi bi-x-circle me-2"),
                    "Erro ao deletar usuário."
                ], color="danger", dismissable=True)

        except Exception as e:
            logger.error(f"[USER_DELETE_ERROR] {str(e)}")
            return dbc.Alert([
                html.I(className="bi bi-x-circle me-2"),
                f"Erro interno: {str(e)}"
            ], color="danger", dismissable=True)

    # ============================================
    # CALLBACK 6: Open Edit Modal
    # ============================================
    @app.callback(
        [
            Output("edit-user-modal", "is_open"),
            Output("edit-username-input", "value"),
            Output("edit-email-input", "value"),
            Output("edit-user-data", "data"),
            Output("edit-user-modal-alert", "children")
        ],
        [
            Input({"type": "edit-user-btn", "index": ALL}, "n_clicks"),
            Input("edit-user-cancel-btn", "n_clicks"),
            Input("edit-user-save-btn", "n_clicks")
        ],
        [
            State("manage-admin-user-perfil", "data"),
            State("edit-user-data", "data")
        ],
        prevent_initial_call=True
    )
    def toggle_edit_modal(edit_clicks, cancel_clicks, save_clicks, admin_perfil, current_user_data):
        """Open/close edit modal and populate fields"""
        from dash import no_update
        from src.database.connection import get_mongo_connection
        import json

        ctx = callback_context
        if not ctx.triggered:
            return no_update, no_update, no_update, no_update, no_update

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # Check if any button was actually clicked (not just table refresh)
        if not any(edit_clicks) and not cancel_clicks and not save_clicks:
            return no_update, no_update, no_update, no_update, no_update

        # Close modal on cancel or save
        if "cancel" in trigger_id or "save" in trigger_id:
            return False, "", "", None, ""

        # Open modal on edit button click
        if "edit-user-btn" in trigger_id:
            # Check if this specific button was clicked
            try:
                button_data = json.loads(trigger_id)
                user_id = button_data["index"]

                # Find which button was clicked
                button_index = None
                for idx, clicks in enumerate(edit_clicks):
                    if clicks and clicks > 0:
                        button_index = idx
                        break

                # If no button has clicks, don't open modal
                if button_index is None:
                    return no_update, no_update, no_update, no_update, no_update

                usuarios = get_mongo_connection("usuarios")
                user = usuarios.find_one({"_id": ObjectId(user_id)})

                if not user:
                    return False, "", "", None, dbc.Alert([
                        html.I(className="bi bi-x-circle me-2"),
                        "Erro: Usuário não encontrado."
                    ], color="danger")

                # RBAC Check: Admin can edit any, others only their department
                if admin_perfil != "admin" and user.get("perfil") != admin_perfil:
                    logger.warning(
                        f"[PERMISSION_DENIED] User '{admin_perfil}' attempted to edit "
                        f"user '{user.get('username')}' from department '{user.get('perfil')}'"
                    )
                    return False, "", "", None, dbc.Alert([
                        html.I(className="bi bi-shield-x me-2"),
                        "PERMISSÃO NEGADA: Você só pode editar usuários do seu departamento."
                    ], color="danger")

                # Store user data for save operation
                user_data = {
                    "id": user_id,
                    "original_username": user.get("username"),
                    "original_email": user.get("email")
                }

                return True, user.get("username", ""), user.get("email", ""), user_data, ""

            except Exception as e:
                logger.error(f"[EDIT_MODAL_ERROR] {str(e)}")
                return False, "", "", None, dbc.Alert([
                    html.I(className="bi bi-x-circle me-2"),
                    f"Erro interno: {str(e)}"
                ], color="danger")

        return no_update, no_update, no_update, no_update, no_update

    # ============================================
    # CALLBACK 7: Save User Edits
    # ============================================
    @app.callback(
        Output("manage-users-alert", "children", allow_duplicate=True),
        Input("edit-user-save-btn", "n_clicks"),
        [
            State("edit-username-input", "value"),
            State("edit-email-input", "value"),
            State("edit-user-data", "data"),
            State("manage-admin-user-perfil", "data")
        ],
        prevent_initial_call=True
    )
    def save_user_edits(n_clicks, new_username, new_email, user_data, admin_perfil):
        """Save username and email changes with validation"""
        from dash import no_update
        from src.database.connection import get_mongo_connection

        if not n_clicks or not user_data:
            return no_update

        try:
            # Validate inputs
            if not new_username or not new_email:
                return dbc.Alert([
                    html.I(className="bi bi-exclamation-triangle me-2"),
                    "Nome de usuário e e-mail são obrigatórios."
                ], color="danger", dismissable=True)

            if "@" not in new_email or "." not in new_email:
                return dbc.Alert([
                    html.I(className="bi bi-exclamation-triangle me-2"),
                    "Formato de e-mail inválido."
                ], color="danger", dismissable=True)

            usuarios = get_mongo_connection("usuarios")
            user_id = user_data["id"]
            original_username = user_data["original_username"]
            original_email = user_data["original_email"]

            # Check if user still exists
            target_user = usuarios.find_one({"_id": ObjectId(user_id)})
            if not target_user:
                return dbc.Alert([
                    html.I(className="bi bi-x-circle me-2"),
                    "Erro: Usuário não encontrado."
                ], color="danger", dismissable=True)

            # RBAC Check (double-check)
            if admin_perfil != "admin" and target_user.get("perfil") != admin_perfil:
                return dbc.Alert([
                    html.I(className="bi bi-shield-x me-2"),
                    "PERMISSÃO NEGADA: Você só pode editar usuários do seu departamento."
                ], color="danger", dismissable=True)

            # Check uniqueness (exclude current user)
            if new_username != original_username:
                existing_user = usuarios.find_one({
                    "username": new_username,
                    "_id": {"$ne": ObjectId(user_id)}
                })
                if existing_user:
                    return dbc.Alert([
                        html.I(className="bi bi-exclamation-triangle me-2"),
                        f"O nome de usuário '{new_username}' já está em uso."
                    ], color="danger", dismissable=True)

            if new_email != original_email:
                existing_email = usuarios.find_one({
                    "email": new_email,
                    "_id": {"$ne": ObjectId(user_id)}
                })
                if existing_email:
                    return dbc.Alert([
                        html.I(className="bi bi-exclamation-triangle me-2"),
                        f"O e-mail '{new_email}' já está em uso."
                    ], color="danger", dismissable=True)

            # Update user
            result = usuarios.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {
                    "username": new_username,
                    "email": new_email
                }}
            )

            if result.modified_count == 1:
                logger.info(
                    f"[USER_EDITED] Admin '{admin_perfil}' edited user '{original_username}' "
                    f"(new username: {new_username}, new email: {new_email})"
                )
                return dbc.Alert([
                    html.I(className="bi bi-check-circle me-2"),
                    f"Usuário atualizado com sucesso! Username: {new_username}, E-mail: {new_email}"
                ], color="success", dismissable=True, duration=4000)
            else:
                # No changes were made (values are the same)
                return dbc.Alert([
                    html.I(className="bi bi-info-circle me-2"),
                    "Nenhuma alteração foi feita."
                ], color="info", dismissable=True, duration=3000)

        except Exception as e:
            logger.error(f"[USER_EDIT_ERROR] {str(e)}")
            return dbc.Alert([
                html.I(className="bi bi-x-circle me-2"),
                f"Erro interno: {str(e)}"
            ], color="danger", dismissable=True)
