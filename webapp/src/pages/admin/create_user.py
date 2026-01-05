# pages/admin/create_user.py

"""
Admin User Creation Page

This page allows level 3 administrators to create new users with department-based RBAC controls.

RBAC Rules:
- Only level 3 users can access this page
- TI department: Can create users in any department with levels 1-3
- Other departments: Can only create users in their own department with levels 1-2
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
from flask_login import current_user


def layout_wrapper():
    """
    Wrapper function to pass current_user to layout.

    This is necessary because current_user from Flask-Login is only accessible
    in the routing context, not in regular Dash callbacks.
    """
    return layout(current_user)


def layout(user):
    """
    Admin user creation page layout.

    Args:
        user: current_user object from Flask-Login with attributes:
            - level (int): User's access level (1-3)
            - perfil (str): User's department/profile

    Returns:
        dbc.Container: Page layout with form and permission controls
    """

    return dbc.Container([
        # ============================================
        # HIDDEN STORES (Pass user context to callbacks)
        # ============================================
        # These stores allow callbacks to access the current user's level and perfil
        # since current_user is not directly accessible in Dash callbacks
        dcc.Store(id="admin-user-level", data=user.level),
        dcc.Store(id="admin-user-perfil", data=user.perfil),

        dbc.Row([
            dbc.Col([
                # ============================================
                # PAGE HEADER
                # ============================================
                html.H2([
                    html.I(className="bi bi-person-plus me-3"),
                    "Criar Novo Usuário"
                ], className="mb-4"),

                # ============================================
                # PERMISSIONS INFO CARD
                # ============================================
                # Shows the current admin's permissions (populated by callback)
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Suas Permissões:", className="text-muted mb-2"),
                        html.Div(id="admin-permissions-info")
                    ])
                ], className="mb-4 bg-light"),

                # ============================================
                # MAIN FORM CARD
                # ============================================
                dbc.Card([
                    dbc.CardBody([
                        # ========================================
                        # USERNAME FIELD
                        # ========================================
                        html.Label("Nome de Usuário:", className="fw-bold mb-1"),
                        dbc.Input(
                            id="create-user-username",
                            placeholder="Nome de usuário",
                            type="text",
                            className="mb-3",
                            required=True
                        ),

                        # ========================================
                        # EMAIL FIELD
                        # ========================================
                        html.Label("E-mail:", className="fw-bold mb-1"),
                        dbc.Input(
                            id="create-user-email",
                            placeholder="email@exemplo.com",
                            type="email",
                            className="mb-3",
                            required=True
                        ),

                        # ========================================
                        # PASSWORD FIELD
                        # ========================================
                        html.Label("Senha:", className="fw-bold mb-1"),
                        dbc.Input(
                            id="create-user-password",
                            placeholder="Senha (mínimo 8 caracteres)",
                            type="password",
                            className="mb-3",
                            required=True,
                            minLength=8
                        ),

                        # ========================================
                        # DEPARTMENT DROPDOWN (SMART)
                        # ========================================
                        # Populated and locked/unlocked by callback based on admin's perfil
                        html.Label("Departamento:", className="fw-bold mb-1"),
                        dcc.Dropdown(
                            id="create-user-department",
                            options=[],  # Populated by callback
                            placeholder="Selecione o departamento",
                            className="mb-2",
                            clearable=False,
                            searchable=True,
                        ),
                        html.Small(id="department-help-text", className="text-muted d-block mb-3"),

                        # ========================================
                        # LEVEL DROPDOWN (SMART)
                        # ========================================
                        # Populated by callback with restricted options for non-TI admins
                        html.Label("Nível de Acesso:", className="fw-bold mb-1"),
                        dcc.Dropdown(
                            id="create-user-level",
                            options=[],  # Populated by callback
                            placeholder="Selecione o nível",
                            className="mb-2",
                            clearable=False,
                            searchable=False,
                        ),
                        html.Small(id="level-help-text", className="text-muted d-block mb-3"),

                        # ========================================
                        # SUBMIT BUTTON
                        # ========================================
                        dbc.Button(
                            [html.I(className="bi bi-check-circle me-2"), "Criar Usuário"],
                            id="create-user-submit",
                            color="success",
                            size="lg",
                            className="w-100 mt-3"
                        ),

                        # ========================================
                        # ALERT AREA (Success/Error Messages)
                        # ========================================
                        html.Div(id="create-user-alert", className="mt-3"),
                    ])
                ], className="shadow"),

            ], width={"size": 8, "offset": 2}, lg={"size": 6, "offset": 3})
        ])
    ], fluid=True, className="py-4")
