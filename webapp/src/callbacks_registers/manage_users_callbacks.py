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


# ============================================
# REGRAS DE NÍVEL (espelham create_user_callbacks)
# ============================================

LEVEL_LABELS = {
    1: "Nível 1 - Visualizador",
    2: "Nível 2 - Operador",
    3: "Nível 3 - Administrador",
}


def level_options_for_admin(admin_perfil):
    """Opções de nível que um admin do perfil dado pode atribuir.

    Espelha a regra do create_user: perfil ``admin`` (TI) atribui níveis 1-3;
    demais perfis atribuem apenas 1-2 (não criam/promovem nível 3).
    """
    niveis = [1, 2, 3] if admin_perfil == "admin" else [1, 2]
    return [{"label": LEVEL_LABELS[n], "value": n} for n in niveis]


def assignable_levels(admin_perfil):
    """Conjunto de níveis que um admin do perfil dado pode atribuir/alterar.

    ``admin`` (TI) opera 1-3; demais perfis apenas 1-2. Níveis fora do conjunto
    (ex: nível 4 = gestor) são especiais e ficam fora do alcance de edição.
    """
    return {1, 2, 3} if admin_perfil == "admin" else {1, 2}


def validate_level_change(admin_perfil, admin_id, target_user, new_level):
    """Valida server-side a troca de nível de um usuário (defesa em profundidade).

    Edge cases cobertos: (a) no-op — manter o mesmo nível nunca é bloqueado, mesmo
    para níveis especiais (ex: gestor nível 4), pra não travar edição de nome/email;
    (b) anti-lockout — ninguém altera o próprio nível; (c) níveis especiais (fora do
    conjunto atribuível, ex: nível 4) não podem ser alterados por esta tela.
    Retorna ``(ok: bool, erro: str | None)``.
    """
    try:
        new_level = int(new_level)
    except (TypeError, ValueError):
        return False, "Nível inválido."

    current_level = int(target_user.get("level", 1))
    target_id = str(target_user.get("_id"))

    # No-op: manter o mesmo nível nunca é bloqueado (inclui nível 4 = gestor)
    if new_level == current_level:
        return True, None

    # Daqui em diante há mudança real de nível.
    # Anti-lockout: ninguém altera o próprio nível de acesso
    if admin_id is not None and target_id == str(admin_id):
        return False, "Você não pode alterar o seu próprio nível de acesso."

    allowed = assignable_levels(admin_perfil)

    # Nível atual especial (fora do alcance do admin, ex: gestor nível 4)
    if current_level not in allowed:
        if current_level == 3:
            return False, "PERMISSÃO NEGADA: apenas Administradores podem alterar o nível de um usuário nível 3."
        return False, f"Nível especial (nível {current_level}) não pode ser alterado por esta tela."

    # Novo nível precisa estar no alcance do admin
    if new_level not in allowed:
        if new_level == 3:
            return False, "PERMISSÃO NEGADA: apenas Administradores podem atribuir o nível 3."
        return False, f"Nível inválido: {new_level}"

    return True, None


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
            Output("edit-user-modal-alert", "children"),
            Output("edit-level-input", "options"),
            Output("edit-level-input", "value"),
            Output("edit-level-input", "disabled"),
            Output("edit-level-note", "children")
        ],
        [
            Input({"type": "edit-user-btn", "index": ALL}, "n_clicks"),
            Input("edit-user-cancel-btn", "n_clicks"),
            Input("edit-user-save-btn", "n_clicks")
        ],
        [
            State("manage-admin-user-perfil", "data"),
            State("manage-admin-user-id", "data"),
            State("edit-user-data", "data")
        ],
        prevent_initial_call=True
    )
    def toggle_edit_modal(edit_clicks, cancel_clicks, save_clicks, admin_perfil, admin_id, current_user_data):
        """Open/close edit modal and populate fields (inclui nível, com trava nos edge cases)"""
        from dash import no_update
        from src.database.connection import get_mongo_connection
        import json

        ctx = callback_context
        if not ctx.triggered:
            return (no_update,) * 9

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # Check if any button was actually clicked (not just table refresh)
        if not any(edit_clicks) and not cancel_clicks and not save_clicks:
            return (no_update,) * 9

        # Close modal on cancel or save
        if "cancel" in trigger_id or "save" in trigger_id:
            return False, "", "", None, "", [], None, False, ""

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
                    return (no_update,) * 9

                usuarios = get_mongo_connection("usuarios")
                user = usuarios.find_one({"_id": ObjectId(user_id)})

                if not user:
                    return False, "", "", None, dbc.Alert([
                        html.I(className="bi bi-x-circle me-2"),
                        "Erro: Usuário não encontrado."
                    ], color="danger"), [], None, False, ""

                # RBAC Check: Admin can edit any, others only their department
                if admin_perfil != "admin" and user.get("perfil") != admin_perfil:
                    logger.warning(
                        f"[PERMISSION_DENIED] User '{admin_perfil}' attempted to edit "
                        f"user '{user.get('username')}' from department '{user.get('perfil')}'"
                    )
                    return False, "", "", None, dbc.Alert([
                        html.I(className="bi bi-shield-x me-2"),
                        "PERMISSÃO NEGADA: Você só pode editar usuários do seu departamento."
                    ], color="danger"), [], None, False, ""

                # Nível: opções + trava conforme regras e edge cases aprovados
                current_level = int(user.get("level", 1))
                is_self = (user_id == str(admin_id))
                allowed = assignable_levels(admin_perfil)
                # Trava quando: é o próprio usuário, OU o nível atual está fora do
                # alcance deste admin (nível 3 pra não-admin, nível 4+ gestor pra todos)
                special = current_level not in allowed
                locked = is_self or special

                if locked:
                    lvl_options = [{
                        "label": LEVEL_LABELS.get(current_level, f"Nível {current_level} - Especial"),
                        "value": current_level
                    }]
                    lvl_disabled = True
                    if is_self:
                        lvl_note = "Você não pode alterar o seu próprio nível de acesso."
                    elif current_level == 3:
                        lvl_note = "Apenas Administradores podem alterar o nível de um usuário nível 3."
                    else:
                        lvl_note = f"Nível especial (nível {current_level}, gestor). Alteração não disponível por aqui."
                else:
                    lvl_options = level_options_for_admin(admin_perfil)
                    lvl_disabled = False
                    lvl_note = (
                        "TI pode atribuir qualquer nível (1-3)."
                        if admin_perfil == "admin" else
                        "Você pode atribuir apenas níveis 1 ou 2."
                    )

                # Store user data for save operation
                user_data = {
                    "id": user_id,
                    "original_username": user.get("username"),
                    "original_email": user.get("email"),
                    "original_level": current_level
                }

                return (True, user.get("username", ""), user.get("email", ""), user_data, "",
                        lvl_options, current_level, lvl_disabled, lvl_note)

            except Exception as e:
                logger.error(f"[EDIT_MODAL_ERROR] {str(e)}")
                return False, "", "", None, dbc.Alert([
                    html.I(className="bi bi-x-circle me-2"),
                    f"Erro interno: {str(e)}"
                ], color="danger"), [], None, False, ""

        return (no_update,) * 9

    # ============================================
    # CALLBACK 7: Save User Edits
    # ============================================
    @app.callback(
        Output("manage-users-alert", "children", allow_duplicate=True),
        Input("edit-user-save-btn", "n_clicks"),
        [
            State("edit-username-input", "value"),
            State("edit-email-input", "value"),
            State("edit-level-input", "value"),
            State("edit-user-data", "data"),
            State("manage-admin-user-perfil", "data"),
            State("manage-admin-user-id", "data")
        ],
        prevent_initial_call=True
    )
    def save_user_edits(n_clicks, new_username, new_email, new_level, user_data, admin_perfil, admin_id):
        """Save username, email and access-level changes with validation"""
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

            # Level change validation (server-side, defense in depth)
            effective_level = new_level if new_level is not None else target_user.get("level", 1)
            ok_level, level_error = validate_level_change(
                admin_perfil, admin_id, target_user, effective_level
            )
            if not ok_level:
                logger.warning(
                    f"[PERMISSION_DENIED] Admin '{admin_perfil}' level-change blocked for "
                    f"'{target_user.get('username')}': {level_error}"
                )
                return dbc.Alert([
                    html.I(className="bi bi-shield-x me-2"),
                    level_error
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
                    "email": new_email,
                    "level": int(effective_level)
                }}
            )

            if result.modified_count == 1:
                logger.info(
                    f"[USER_EDITED] Admin '{admin_perfil}' edited user '{original_username}' "
                    f"(new username: {new_username}, new email: {new_email}, new level: {int(effective_level)})"
                )
                return dbc.Alert([
                    html.I(className="bi bi-check-circle me-2"),
                    f"Usuário atualizado com sucesso! Username: {new_username}, "
                    f"E-mail: {new_email}, Nível: {int(effective_level)}"
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
