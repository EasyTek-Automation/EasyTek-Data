"""Pagina admin pra editar agendamento do SAP Scheduler (DS-08 / SP-09).

Layout bifurcado seguindo precedente `pages/admin/create_user.py` e
`manage_users.py` (RV-05 F-05-01):
- `layout_wrapper()` registrado em ROUTES; importa `current_user` (Flask-Login)
  e passa pro `layout(user)`.
- `layout(user)` renderiza dbc.Container com `dcc.Store`s propagando user context
  para os callbacks Dash (DC-05-02: Flask-Login indisponivel em callback Dash;
  passar via Store e padrao obrigatorio).

Rota: `/config/sap-scheduler`. Permissao: perfil "admin" min_level 3
(DC-04-01 — alinhado com precedente /config/users).
"""
from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html
from flask_login import current_user


def layout_wrapper():
    """Entry point registrada em ROUTES. Captura `current_user` em request scope Flask."""
    return layout(current_user)


def layout(user):
    """Renderiza a pagina com user context propagado via `dcc.Store` (DC-05-02).

    NAO chama `check_access()` — route-level check em `index.py` bloqueia antes.
    Callbacks fazem re-check server-side via State (defesa em profundidade —
    DC-05-03 / SP-09 RF-09-25).
    """
    return dbc.Container(
        [
            # User context propagado via dcc.Store (DC-05-02)
            dcc.Store(
                id="sap-sched-admin-user-level",
                data=getattr(user, "level", 0),
            ),
            dcc.Store(
                id="sap-sched-admin-user-perfil",
                data=getattr(user, "perfil", ""),
            ),
            dcc.Store(
                id="sap-sched-admin-user-username",
                data=getattr(user, "username", ""),
            ),

            # Estado compartilhado entre callbacks load e save (captura `antes`)
            dcc.Store(id="sap-sched-config-atual", data=None),

            # Trigger inicial para disparar load 1x (padrao Dash F-05-08)
            dcc.Interval(
                id="sap-sched-load-trigger",
                interval=1,
                n_intervals=0,
                max_intervals=1,
            ),

            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.H3(
                                "Agendamento do SAP Scheduler",
                                className="mt-3 mb-3",
                            ),
                            html.P(
                                [
                                    html.I(className="bi bi-info-circle me-2"),
                                    "Mudancas sao aplicadas em ate 60 segundos pelo proximo tick — "
                                    "sem necessidade de restart de container.",
                                ],
                                className="text-muted small",
                            ),

                            # Card 1 — tabela + botao salvar + alert + ultima alteracao
                            dbc.Card(
                                dbc.CardBody(
                                    [
                                        html.Div(id="sap-sched-tabela-container"),
                                        dbc.Button(
                                            [
                                                html.I(className="bi bi-save me-2"),
                                                "Salvar",
                                            ],
                                            id="sap-sched-btn-salvar",
                                            color="primary",
                                            className="mt-3",
                                        ),
                                        dbc.Alert(
                                            id="sap-sched-alert",
                                            is_open=False,
                                            dismissable=True,
                                            className="mt-3 mb-0",
                                        ),
                                        html.Div(
                                            id="sap-sched-ultima-alteracao",
                                            className="text-muted mt-2 small",
                                        ),
                                    ]
                                ),
                                className="mb-3",
                            ),

                            # Card 2 — collapse de historico
                            dbc.Card(
                                dbc.CardBody(
                                    [
                                        dbc.Button(
                                            [
                                                html.I(
                                                    className="bi bi-clock-history me-2"
                                                ),
                                                "Historico de alteracoes (ultimas 20)",
                                            ],
                                            id="sap-sched-historico-toggle",
                                            color="link",
                                            className="text-decoration-none p-0",
                                        ),
                                        dbc.Collapse(
                                            html.Div(
                                                id="sap-sched-historico-container"
                                            ),
                                            id="sap-sched-historico-collapse",
                                            is_open=False,
                                        ),
                                    ]
                                ),
                            ),
                        ],
                        width=12,
                    )
                ]
            ),
        ],
        fluid=True,
    )
