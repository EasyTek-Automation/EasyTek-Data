# pages/auth/change_password.py

"""
Password Change Page

This page allows users to change their password. It has two modes:
1. First-time mode: For users created with blank password (no current password required)
2. Normal mode: For users changing their password (current password required)
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
from flask_login import current_user
from werkzeug.security import check_password_hash


def layout_wrapper():
    """
    Wrapper function to pass current_user to layout.
    Also checks if user has blank password to determine mode.
    """
    # Check if user has blank password (hash of empty string)
    is_first_time = check_password_hash(current_user.password, "")

    return layout(current_user, is_first_time)


def layout(user, is_first_time=False):
    """
    Password change page layout.

    Args:
        user: current_user object from Flask-Login
        is_first_time (bool): True if user has blank password (first-time setup)

    Returns:
        dbc.Container: Page layout with password change form
    """

    card_style = {
        'width': '500px',
        'padding': '30px',
        'margin': '50px auto',
        'background-color': 'rgba(255, 255, 255, 0.1)',
        'border': '1px solid rgba(255, 255, 255, 0.2)',
        'border-radius': '15px',
        'box-shadow': '0 4px 30px rgba(0, 0, 0, 0.1)',
        'backdrop-filter': 'blur(5px)',
        '-webkit-backdrop-filter': 'blur(5px)',
    }

    # Build the form fields based on mode
    form_fields = []

    # Header message
    if is_first_time:
        header_message = dbc.Alert([
            html.I(className="bi bi-info-circle me-2"),
            "Primeira configuração: Por favor, crie sua senha."
        ], color="info", className="mb-4")
    else:
        header_message = html.Div()

    # Current password field (always exists, but hidden for first-time mode)
    if is_first_time:
        # Hidden for first-time users
        form_fields.append(html.Div([
            dbc.Input(
                id="current-password",
                type="password",
                style={"display": "none"},
                value=""  # Empty value for first-time
            ),
        ]))
    else:
        # Visible for normal mode
        form_fields.append(html.Div([
            html.Label("Senha Atual:", className="fw-bold mb-1"),
            dbc.Input(
                id="current-password",
                placeholder="Digite sua senha atual",
                type="password",
                className="mb-3",
                required=True
            ),
        ]))

    # New password fields (both modes)
    form_fields.extend([
        html.Label("Nova Senha:", className="fw-bold mb-1"),
        dbc.Input(
            id="new-password",
            placeholder="Nova senha (mínimo 8 caracteres)",
            type="password",
            className="mb-3",
            required=True,
            minLength=8
        ),

        html.Label("Confirmar Nova Senha:", className="fw-bold mb-1"),
        dbc.Input(
            id="confirm-password",
            placeholder="Digite a nova senha novamente",
            type="password",
            className="mb-3",
            required=True,
            minLength=8
        ),
    ])

    return dbc.Container([
        # Hidden store to track mode
        dcc.Store(id="password-change-mode", data={"is_first_time": is_first_time}),
        dcc.Store(id="user-id-store", data=user.id),

        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        # Header
                        html.Div([
                            html.I(className="bi bi-shield-lock", style={"fontSize": "3rem", "color": "#007bff"}),
                        ], className="text-center mb-3"),

                        html.H2("Alterar Senha", className="text-center mb-4"),

                        # Mode-specific message
                        header_message,

                        # Form fields
                        *form_fields,

                        # Submit button
                        dbc.Button(
                            [html.I(className="bi bi-check-circle me-2"), "Alterar Senha"],
                            id="change-password-submit",
                            color="primary",
                            size="lg",
                            className="w-100 mt-3"
                        ),

                        # Alert area
                        html.Div(id="change-password-alert", className="mt-3"),

                        # Back to home link (only for non-first-time)
                        html.Div([
                            dbc.Button(
                                "Voltar",
                                href="/",
                                color="link",
                                className="mt-2"
                            )
                        ], className="text-center") if not is_first_time else html.Div(),
                    ])
                ], style=card_style),
            ], width=12)
        ])
    ], fluid=True, className="py-4")
