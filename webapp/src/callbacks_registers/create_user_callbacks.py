# callbacks_registers/create_user_callbacks.py

"""
Callbacks for Admin User Creation Page

This module contains all callbacks for the user creation page with comprehensive
RBAC enforcement and server-side validation.

Security Model:
- Layer 1: Route-level access control (min_level=3)
- Layer 2: Menu visibility (level 3 only)
- Layer 3: UI state management (lock dropdowns based on perfil)
- Layer 4: Server-side validation (prevent DevTools bypass)
"""

from dash import Input, Output, State
import dash_bootstrap_components as dbc
from dash import html
import logging

logger = logging.getLogger(__name__)


def register_create_user_callbacks(app):
    """Register all callbacks for admin user creation page"""

    # ============================================
    # CALLBACK 1: Show Admin Permissions
    # ============================================
    @app.callback(
        Output("admin-permissions-info", "children"),
        Input("admin-user-perfil", "data")
    )
    def show_admin_permissions(admin_perfil):
        """
        Display the current admin's permissions and capabilities.

        Args:
            admin_perfil (str): Current admin's department/perfil

        Returns:
            dbc.Alert: Info card showing what the admin can do
        """
        if admin_perfil == "admin":
            return dbc.Alert([
                html.I(className="bi bi-shield-check me-2"),
                "Você tem privilégios completos de Administrador: pode criar usuários de qualquer departamento e nível."
            ], color="info")
        else:
            # Map perfil codes to display names
            perfil_map = {
                "manutencao": "Manutenção",
                "qualidade": "Qualidade",
                "producao": "Produção",
                "utilidades": "Utilidades",
                "meio_ambiente": "Meio Ambiente",
                "seguranca": "Segurança",
                "engenharias": "Engenharias",
                "admin": "Admin"
            }
            dept_name = perfil_map.get(admin_perfil, admin_perfil)
            return dbc.Alert([
                html.I(className="bi bi-info-circle me-2"),
                f"Você pode criar usuários apenas do departamento {dept_name} com níveis 1-2."
            ], color="warning")

    # ============================================
    # CALLBACK 2: Populate Department Dropdown
    # ============================================
    @app.callback(
        [
            Output("create-user-department", "options"),
            Output("create-user-department", "value"),
            Output("create-user-department", "disabled"),
            Output("department-help-text", "children")
        ],
        Input("admin-user-perfil", "data")
    )
    def populate_department_dropdown(admin_perfil):
        """
        Populate department dropdown based on admin's perfil.

        RBAC Rules:
        - TI: Can select any department (dropdown enabled, all options)
        - Others: Can only create users in their own department (dropdown disabled, pre-filled)

        Args:
            admin_perfil (str): Current admin's department/perfil

        Returns:
            tuple: (options, value, disabled, help_text)
        """
        from src.config.access_control import PERFIS

        # Department labels with icons
        perfil_labels = {
            "producao": "📊 Produção",
            "manutencao": "🔧 Manutenção",
            "qualidade": "✓ Qualidade",
            "meio_ambiente": "🌿 Meio Ambiente",
            "seguranca": "🛡️ Segurança",
            "engenharias": "🛠️ Engenharias",
            "utilidades": "💧 Utilidades",
            "admin": "👑 Administrador"
        }

        if admin_perfil == "admin":
            # Admin users: show all departments, enable dropdown
            options = [
                {"label": perfil_labels.get(p, p), "value": p}
                for p in PERFIS
            ]
            value = None  # No pre-selection
            disabled = False
            help_text = "Selecione o departamento do novo usuário"

        else:
            # Non-TI users: lock to their own department
            options = [
                {"label": perfil_labels.get(admin_perfil, admin_perfil), "value": admin_perfil}
            ]
            value = admin_perfil  # Pre-fill with admin's department
            disabled = True  # Lock dropdown
            help_text = f"Você só pode criar usuários no seu departamento"

        return options, value, disabled, help_text

    # ============================================
    # CALLBACK 3: Populate Level Dropdown
    # ============================================
    @app.callback(
        [
            Output("create-user-level", "options"),
            Output("create-user-level", "value"),
            Output("level-help-text", "children")
        ],
        Input("admin-user-perfil", "data")
    )
    def populate_level_dropdown(admin_perfil):
        """
        Populate level dropdown based on admin's perfil.

        RBAC Rules:
        - Admin: Can assign any level (1, 2, 3)
        - Others: Can only assign levels 1-2 (cannot create level 3 admins)

        Args:
            admin_perfil (str): Current admin's department/perfil

        Returns:
            tuple: (options, value, help_text)
        """
        if admin_perfil == "admin":
            # Admin users can create any level
            options = [
                {"label": "Nível 1 - Visualizador", "value": 1},
                {"label": "Nível 2 - Operador", "value": 2},
                {"label": "Nível 3 - Administrador", "value": 3},
            ]
            help_text = "TI pode criar usuários de qualquer nível"
        else:
            # Non-TI users cannot create level 3
            options = [
                {"label": "Nível 1 - Visualizador", "value": 1},
                {"label": "Nível 2 - Operador", "value": 2},
            ]
            help_text = "Você pode criar apenas usuários de nível 1 ou 2"

        return options, None, help_text

    # ============================================
    # CALLBACK 4: Create User (with validation)
    # ============================================
    @app.callback(
        Output("create-user-alert", "children"),
        Input("create-user-submit", "n_clicks"),
        [
            State("create-user-username", "value"),
            State("create-user-email", "value"),
            State("create-user-password", "value"),
            State("create-user-department", "value"),
            State("create-user-level", "value"),
            State("admin-user-perfil", "data"),
            State("admin-user-level", "data"),
        ],
        prevent_initial_call=True
    )
    def create_new_user(n_clicks, username, email, password, target_department,
                       target_level, admin_perfil, admin_level):
        """
        Create new user with comprehensive server-side validation.

        Security: Defense in depth - validate even if UI enforces rules.
        This prevents bypass via browser DevTools or API calls.

        Args:
            n_clicks: Submit button click count
            username: New user's username
            email: New user's email
            password: New user's password (will be hashed)
            target_department: New user's department/perfil
            target_level: New user's access level
            admin_perfil: Current admin's department/perfil
            admin_level: Current admin's access level

        Returns:
            dbc.Alert: Success or error message
        """

        from src.database.connection import get_user_by_username, get_user_by_email, save_user
        from src.config.access_control import PERFIS

        # ========================================
        # INPUT VALIDATION
        # ========================================

        # Check required fields (password can be blank for first-time setup)
        if not all([username, email, target_department, target_level]):
            return dbc.Alert([
                html.I(className="bi bi-exclamation-triangle me-2"),
                "Todos os campos são obrigatórios (senha pode ficar em branco)."
            ], color="danger")

        # Password strength validation (only if password is provided)
        if password and len(password) < 8:
            return dbc.Alert([
                html.I(className="bi bi-exclamation-triangle me-2"),
                "A senha deve ter no mínimo 8 caracteres (ou deixe em branco para senha temporária)."
            ], color="danger")

        # If password is empty, use empty string (will be hashed)
        if not password:
            password = ""  # Blank password for first-time login

        # Basic email format validation
        if "@" not in email or "." not in email:
            return dbc.Alert([
                html.I(className="bi bi-exclamation-triangle me-2"),
                "Formato de e-mail inválido."
            ], color="danger")

        # ========================================
        # UNIQUENESS VALIDATION
        # ========================================

        # Check if username already exists
        if get_user_by_username(username):
            return dbc.Alert([
                html.I(className="bi bi-exclamation-triangle me-2"),
                f"O nome de usuário '{username}' já existe."
            ], color="danger")

        # Check if email already exists
        if get_user_by_email(email):
            return dbc.Alert([
                html.I(className="bi bi-exclamation-triangle me-2"),
                f"O e-mail '{email}' já está em uso."
            ], color="danger")

        # ========================================
        # RBAC VALIDATION (SERVER-SIDE)
        # ========================================
        # Critical: Re-validate all permission rules on server side
        # to prevent bypass via browser DevTools

        # Rule 1: Only Admin can create level 3 users
        if target_level == 3 and admin_perfil != "admin":
            logger.warning(
                f"[PERMISSION_DENIED] Admin '{admin_perfil}' (level {admin_level}) "
                f"attempted to create level 3 user '{username}'"
            )
            return dbc.Alert([
                html.I(className="bi bi-shield-x me-2"),
                "PERMISSÃO NEGADA: Apenas Administradores podem criar usuários nível 3."
            ], color="danger")

        # Rule 2: Only Admin can create users in other departments
        if target_department != admin_perfil and admin_perfil != "admin":
            logger.warning(
                f"[PERMISSION_DENIED] Admin '{admin_perfil}' (level {admin_level}) "
                f"attempted to create user in department '{target_department}'"
            )
            return dbc.Alert([
                html.I(className="bi bi-shield-x me-2"),
                f"PERMISSÃO NEGADA: Você só pode criar usuários no seu próprio departamento."
            ], color="danger")

        # Rule 3: Validate department exists in PERFIS
        if target_department not in PERFIS:
            return dbc.Alert([
                html.I(className="bi bi-exclamation-triangle me-2"),
                f"Departamento inválido: {target_department}"
            ], color="danger")

        # Rule 4: Validate level is 1, 2, or 3
        if target_level not in [1, 2, 3]:
            return dbc.Alert([
                html.I(className="bi bi-exclamation-triangle me-2"),
                f"Nível inválido: {target_level}"
            ], color="danger")

        # ========================================
        # SAVE USER
        # ========================================

        try:
            success = save_user(
                username=username,
                email=email,
                password=password,
                level=target_level,
                perfil=target_department
            )

            if success:
                # Log successful user creation for audit trail
                logger.info(
                    f"[USER_CREATED] Admin '{admin_perfil}' (level {admin_level}) "
                    f"created user '{username}' (perfil: {target_department}, level: {target_level})"
                )

                return dbc.Alert([
                    html.I(className="bi bi-check-circle me-2"),
                    html.Div([
                        html.Strong("Usuário criado com sucesso!"),
                        html.Br(),
                        html.Small(
                            f"Usuário: {username} | Departamento: {target_department} | Nível: {target_level}"
                        )
                    ])
                ], color="success")
            else:
                return dbc.Alert([
                    html.I(className="bi bi-x-circle me-2"),
                    "Erro ao salvar usuário no banco de dados."
                ], color="danger")

        except Exception as e:
            logger.error(f"[USER_CREATE_ERROR] {str(e)}")
            return dbc.Alert([
                html.I(className="bi bi-x-circle me-2"),
                f"Erro interno: {str(e)}"
            ], color="danger")
