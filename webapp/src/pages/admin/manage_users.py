# pages/admin/manage_users.py

"""
User Management Page

This page allows level 3 administrators to manage existing users:
- View list of users (filtered by department for non-admin)
- Edit username and email
- Reset user password (force first-time login)
- Delete users

RBAC Rules:
- Admin: Can manage users from any department
- Others: Can only manage users from their own department
"""

from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc
from flask_login import current_user


def layout_wrapper():
    """
    Wrapper function to pass current_user to layout.
    """
    return layout(current_user)


def layout(user):
    """
    User management page layout.

    Args:
        user: current_user object from Flask-Login

    Returns:
        dbc.Container: Page layout with user management table
    """

    return dbc.Container([
        # ============================================
        # HIDDEN STORES (Pass user context to callbacks)
        # ============================================
        dcc.Store(id="manage-admin-user-level", data=user.level),
        dcc.Store(id="manage-admin-user-perfil", data=user.perfil),
        dcc.Store(id="edit-user-data", data=None),  # Store data of user being edited
        dcc.Interval(id="refresh-users-table", interval=5000, n_intervals=0),  # Auto-refresh every 5s

        dbc.Row([
            dbc.Col([
                # ============================================
                # PAGE HEADER
                # ============================================
                html.Div([
                    html.H2([
                        html.I(className="bi bi-people me-3"),
                        "Gerenciar Usuários"
                    ], className="mb-2"),
                    html.P(
                        "Visualize, edite e gerencie usuários do sistema",
                        className="text-muted"
                    )
                ], className="mb-4"),

                # ============================================
                # FILTER AND ACTIONS BAR
                # ============================================
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.InputGroup([
                                    dbc.InputGroupText(html.I(className="bi bi-search")),
                                    dbc.Input(
                                        id="user-search-input",
                                        placeholder="Buscar por nome ou email...",
                                        type="text"
                                    ),
                                ]),
                            ], md=6),
                            dbc.Col([
                                dcc.Dropdown(
                                    id="user-filter-department",
                                    placeholder="Filtrar por departamento",
                                    clearable=True
                                ),
                            ], md=4),
                            dbc.Col([
                                dbc.Button(
                                    [html.I(className="bi bi-arrow-clockwise me-2"), "Atualizar"],
                                    id="refresh-users-button",
                                    color="secondary",
                                    outline=True,
                                    className="w-100"
                                ),
                            ], md=2),
                        ], className="g-2")
                    ])
                ], className="mb-4"),

                # ============================================
                # PERMISSIONS INFO
                # ============================================
                html.Div(id="manage-permissions-info", className="mb-3"),

                # ============================================
                # USERS TABLE
                # ============================================
                dbc.Card([
                    dbc.CardBody([
                        html.Div(id="users-table-container"),
                        html.Div(id="users-table-loading", className="text-center py-3")
                    ])
                ], className="shadow"),

                # ============================================
                # ALERT AREA (Success/Error Messages)
                # ============================================
                html.Div(id="manage-users-alert", className="mt-3"),

            ], width=12)
        ]),

        # ============================================
        # EDIT USER MODAL
        # ============================================
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle([
                html.I(className="bi bi-pencil-square me-2"),
                "Editar Usuário"
            ])),
            dbc.ModalBody([
                # Username field
                html.Label("Nome de Usuário:", className="fw-bold mb-1"),
                dbc.Input(
                    id="edit-username-input",
                    type="text",
                    placeholder="Nome de usuário",
                    className="mb-3"
                ),

                # Email field
                html.Label("E-mail:", className="fw-bold mb-1"),
                dbc.Input(
                    id="edit-email-input",
                    type="email",
                    placeholder="email@exemplo.com",
                    className="mb-3"
                ),

                # Alert for errors in modal
                html.Div(id="edit-user-modal-alert"),
            ]),
            dbc.ModalFooter([
                dbc.Button(
                    "Cancelar",
                    id="edit-user-cancel-btn",
                    color="secondary",
                    outline=True,
                    className="me-2"
                ),
                dbc.Button(
                    [html.I(className="bi bi-check-circle me-2"), "Salvar Alterações"],
                    id="edit-user-save-btn",
                    color="primary"
                ),
            ])
        ], id="edit-user-modal", is_open=False, centered=True),

    ], fluid=True, className="py-4")
