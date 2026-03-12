"""Modais para CRUD de subtarefas e logs do Workflow."""
import dash_bootstrap_components as dbc
from dash import html, dcc

# Opções de tipo de evento — "Lançamento Retroativo" é um campo separado (switch)
TIPOS_EVENTO_OPTIONS = [
    {"label": "Análise de Falha", "value": "Análise de Falha"},
    {"label": "Aguardando Material", "value": "Aguardando Material"},
    {"label": "Aguardando Aprovação", "value": "Aguardando Aprovação"},
    {"label": "Manutenção Corretiva", "value": "Manutenção Corretiva"},
    {"label": "Manutenção Preventiva", "value": "Manutenção Preventiva"},
    {"label": "Revisão de Software", "value": "Revisão de Software"},
    {"label": "Desenvolvimento de Software", "value": "Desenvolvimento de Software"},
    {"label": "Teste e Validação", "value": "Teste e Validação"},
    {"label": "Em Produção Assistida", "value": "Em Produção Assistida"},
    {"label": "Documentação Técnica", "value": "Documentação Técnica"},
    {"label": "Treinamento Operacional", "value": "Treinamento Operacional"},
    {"label": "Estudo", "value": "Estudo"},
    {"label": "Encerramento", "value": "Encerramento"},
    {"label": "Trabalho Adicional", "value": "Trabalho Adicional"},
]


def create_subtask_modal():
    """Modal para criação de nova subtarefa."""
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle([
            html.I(className="fas fa-tasks me-2"),
            "Nova Subtarefa"
        ])),

        dbc.ModalBody([
            # Título
            html.Label("Título:", className="fw-bold mb-1"),
            html.Span(" *", className="text-danger"),
            dbc.Input(
                id="create-subtask-titulo",
                type="text",
                placeholder="Ex: Verificar rolamento do motor A",
                className="mb-3"
            ),

            # Tipo de evento
            html.Label("Tipo de Evento:", className="fw-bold mb-1"),
            html.Span(" *", className="text-danger"),
            dcc.Dropdown(
                id="create-subtask-tipo",
                options=TIPOS_EVENTO_OPTIONS,
                placeholder="Selecione o tipo",
                clearable=False,
                className="mb-3"
            ),

            # Responsável pela execução
            html.Label("Responsável:", className="fw-bold mb-1"),
            html.Span(" *", className="text-danger"),
            dcc.Dropdown(
                id="create-subtask-responsavel",
                placeholder="Selecione o responsável",
                clearable=False,
                searchable=True,
                className="mb-3"
            ),

            # Aprovador (condicional — aparece quando tipo requer aprovação)
            html.Div([
                html.Hr(className="my-2"),
                dbc.Alert([
                    html.I(className="fas fa-user-check me-2"),
                    html.Strong("Aprovação Necessária"),
                    html.Br(),
                    html.Small("Este tipo de evento requer aprovação de um usuário nível 3.")
                ], color="warning", className="py-2 mb-2"),
                html.Label("Aprovador (Nível 3):", className="fw-bold mb-1"),
                html.Span(" *", className="text-danger"),
                dcc.Dropdown(
                    id="create-subtask-aprovador",
                    placeholder="Selecione o aprovador",
                    clearable=False,
                    searchable=True,
                    className="mb-1"
                ),
            ], id="create-subtask-aprovador-container", style={"display": "none"}),

            # Separador e switch de Lançamento Retroativo
            html.Hr(className="my-3"),
            dbc.Switch(
                id="create-subtask-is-retroativo",
                label="Lançamento Retroativo",
                value=False,
                className="mb-2"
            ),
            html.Small(
                "Marque se esta atividade já ocorreu e está sendo registrada com atraso.",
                className="text-muted d-block mb-2"
            ),

            # Seção retroativo (condicional — aparece quando switch ON)
            html.Div([
                dbc.Alert([
                    html.I(className="fas fa-history me-2"),
                    html.Strong("Lançamento Retroativo"),
                    html.Br(),
                    html.Small("Informe quem registrou, o aprovador e a data real da ocorrência.")
                ], color="info", className="py-2 mb-3"),

                dbc.Row([
                    dbc.Col([
                        html.Label("Responsável pelo Lançamento:", className="fw-bold mb-1"),
                        html.Span(" *", className="text-danger"),
                        dcc.Dropdown(
                            id="create-subtask-responsavel-retroativo",
                            placeholder="Quem está registrando...",
                            clearable=False,
                            searchable=True,
                            className="mb-2"
                        ),
                    ], md=6),
                    dbc.Col([
                        html.Label("Data da Ocorrência:", className="fw-bold mb-1"),
                        html.Span(" *", className="text-danger"),
                        dcc.DatePickerSingle(
                            id="create-subtask-data-retroativa",
                            placeholder="DD/MM/AAAA",
                            display_format="DD/MM/YYYY",
                            first_day_of_week=0,
                            style={"width": "100%"}
                        ),
                    ], md=6),
                ]),
                dbc.Row([
                    dbc.Col([
                        html.Label("Aprovador do Lançamento (Nível 3):", className="fw-bold mb-1"),
                        html.Span(" *", className="text-danger"),
                        dcc.Dropdown(
                            id="create-subtask-aprovador-retroativo",
                            placeholder="Selecione o aprovador...",
                            clearable=False,
                            searchable=True,
                            className="mb-2"
                        ),
                    ], md=12),
                ]),
                html.Div(className="mb-1"),
            ], id="create-subtask-retroativo-container", style={"display": "none"}),

            html.Hr(className="my-3"),

            # Observações
            html.Label("Observações:", className="fw-bold mb-1"),
            html.Span(" (opcional)", className="text-muted small"),
            dbc.Textarea(
                id="create-subtask-obs",
                placeholder="Informações adicionais sobre esta subtarefa...",
                rows=3,
                className="mb-3"
            ),

            html.Div(id="create-subtask-alert")
        ]),

        dbc.ModalFooter([
            dbc.Button(
                "Cancelar",
                id="create-subtask-cancel-btn",
                color="secondary",
                outline=True,
                className="me-2"
            ),
            dbc.Button(
                [html.I(className="fas fa-plus me-2"), "Criar Subtarefa"],
                id="create-subtask-submit-btn",
                color="success"
            )
        ])
    ], id="create-subtask-modal", is_open=False, size="lg", centered=True)


def add_log_modal():
    """Modal para adicionar relatório/log a uma subtarefa."""
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle([
            html.I(className="fas fa-file-alt me-2"),
            "Preencher Relatório"
        ])),

        dbc.ModalBody([
            # Contexto da subtarefa
            html.Div([
                html.Small("Subtarefa:", className="text-muted"),
                html.Div(
                    id="add-log-subtarefa-titulo",
                    className="fw-semibold"
                )
            ], className="p-2 mb-3 rounded",
               style={"backgroundColor": "rgba(0,0,0,0.04)", "borderLeft": "3px solid var(--bs-primary)"}),

            # Relatório (obrigatório)
            html.Label("Relatório:", className="fw-bold mb-1"),
            html.Span(" *", className="text-danger"),
            dbc.Textarea(
                id="add-log-obs",
                placeholder="Descreva o que foi feito, resultados, próximos passos...",
                rows=4,
                className="mb-3",
                required=True
            ),

            # Duração (opcional — transferido do create-subtask)
            html.Label("Duração:", className="fw-bold mb-1"),
            html.Span(" (opcional)", className="text-muted small"),
            dbc.InputGroup([
                dbc.InputGroupText(
                    html.I(className="fas fa-hourglass-half",
                           style={"color": "var(--bs-info)", "fontSize": "0.9rem"}),
                    style={"backgroundColor": "transparent"}
                ),
                dbc.Input(
                    id="add-log-horas",
                    type="text",
                    placeholder="00:00",
                    maxLength=5,
                    autocomplete="off",
                    style={
                        "fontFamily": "monospace",
                        "fontWeight": "600",
                        "letterSpacing": "0.12em",
                        "fontSize": "1.05rem"
                    }
                ),
                dbc.InputGroupText(
                    "hh:mm",
                    style={"fontSize": "0.75rem", "color": "var(--bs-secondary)",
                           "backgroundColor": "transparent"}
                ),
            ], className="mb-3"),

            # Alerta
            html.Div(id="add-log-alert")
        ]),

        dbc.ModalFooter([
            dbc.Button(
                "Cancelar",
                id="add-log-cancel-btn",
                color="secondary",
                outline=True,
                className="me-2"
            ),
            dbc.Button(
                [html.I(className="fas fa-save me-2"), "Adicionar Relatório"],
                id="add-log-submit-btn",
                color="primary"
            )
        ])
    ], id="add-log-modal", is_open=False, size="lg", centered=True)


def edit_subtask_modal():
    """Modal para editar uma subtarefa existente."""
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle([
            html.I(className="fas fa-pencil-alt me-2"),
            "Editar Subtarefa"
        ])),

        dbc.ModalBody([
            # Título
            html.Label("Título:", className="fw-bold mb-1"),
            dbc.Input(
                id="edit-subtask-titulo",
                type="text",
                placeholder="Título da subtarefa...",
                className="mb-3"
            ),

            # Tipo de evento
            html.Label("Tipo de Evento:", className="fw-bold mb-1"),
            dcc.Dropdown(
                id="edit-subtask-tipo",
                options=TIPOS_EVENTO_OPTIONS,
                clearable=False,
                className="mb-3"
            ),

            # Aprovador (condicional — aparece quando tipo requer aprovação)
            html.Div([
                html.Hr(className="my-2"),
                dbc.Alert([
                    html.I(className="fas fa-user-check me-2"),
                    html.Strong("Aprovação Necessária"),
                    html.Br(),
                    html.Small("Este tipo de evento requer aprovação de um usuário nível 3.")
                ], color="warning", className="py-2 mb-2"),
                html.Label("Aprovador (Nível 3):", className="fw-bold mb-1"),
                html.Span(" *", className="text-danger"),
                dcc.Dropdown(
                    id="edit-subtask-aprovador",
                    placeholder="Selecione o aprovador",
                    clearable=True,
                    searchable=True,
                    className="mb-1"
                ),
            ], id="edit-subtask-aprovador-container", style={"display": "none"}),

            # Switch Lançamento Retroativo
            html.Hr(className="my-3"),
            dbc.Switch(
                id="edit-subtask-is-retroativo",
                label="Lançamento Retroativo",
                value=False,
                className="mb-2"
            ),
            html.Small(
                "Marque se esta atividade já ocorreu e está sendo registrada com atraso.",
                className="text-muted d-block mb-2"
            ),

            # Seção retroativo (condicional)
            html.Div([
                dbc.Alert([
                    html.I(className="fas fa-history me-2"),
                    html.Strong("Lançamento Retroativo"),
                    html.Br(),
                    html.Small("Informe quem registrou, o aprovador e a data real da ocorrência.")
                ], color="info", className="py-2 mb-3"),

                dbc.Row([
                    dbc.Col([
                        html.Label("Responsável pelo Lançamento:", className="fw-bold mb-1"),
                        html.Span(" *", className="text-danger"),
                        dcc.Dropdown(
                            id="edit-subtask-responsavel-retroativo",
                            placeholder="Quem está registrando...",
                            clearable=False,
                            searchable=True,
                            className="mb-2"
                        ),
                    ], md=6),
                    dbc.Col([
                        html.Label("Data da Ocorrência:", className="fw-bold mb-1"),
                        html.Span(" *", className="text-danger"),
                        dcc.DatePickerSingle(
                            id="edit-subtask-data-retroativa",
                            placeholder="DD/MM/AAAA",
                            display_format="DD/MM/YYYY",
                            first_day_of_week=0,
                            style={"width": "100%"}
                        ),
                    ], md=6),
                ]),
                dbc.Row([
                    dbc.Col([
                        html.Label("Aprovador do Lançamento (Nível 3):", className="fw-bold mb-1"),
                        html.Span(" *", className="text-danger"),
                        dcc.Dropdown(
                            id="edit-subtask-aprovador-retroativo",
                            placeholder="Selecione o aprovador...",
                            clearable=False,
                            searchable=True,
                            className="mb-2"
                        ),
                    ], md=12),
                ]),
                html.Div(className="mb-1"),
            ], id="edit-subtask-retroativo-container", style={"display": "none"}),

            html.Hr(className="my-3"),

            # Observações
            html.Label("Observações:", className="fw-bold mb-1"),
            html.Span(" (opcional)", className="text-muted small"),
            dbc.Textarea(
                id="edit-subtask-obs",
                placeholder="Observações...",
                rows=3,
                className="mb-3"
            ),

            # Concluído
            dbc.Checkbox(
                id="edit-subtask-concluido",
                label="Marcar como concluída",
                className="mb-3"
            ),

            html.Div(id="edit-subtask-alert"),
            dcc.Store(id="edit-subtask-hist-id")
        ]),

        dbc.ModalFooter([
            dbc.Button(
                "Cancelar",
                id="edit-subtask-cancel-btn",
                color="secondary",
                outline=True,
                className="me-2"
            ),
            dbc.Button(
                [html.I(className="fas fa-save me-2"), "Salvar"],
                id="edit-subtask-submit-btn",
                color="primary"
            )
        ])
    ], id="edit-subtask-modal", is_open=False, centered=True)


def edit_log_horas_modal():
    """Modal simples para editar as horas de um relatório (log)."""
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle([
            html.I(className="fas fa-clock me-2"),
            "Editar Horas do Relatório"
        ])),

        dbc.ModalBody([
            html.Label("Duração:", className="fw-bold mb-1"),
            dbc.InputGroup([
                dbc.InputGroupText(
                    html.I(className="fas fa-hourglass-half",
                           style={"color": "var(--bs-info)", "fontSize": "0.9rem"}),
                    style={"backgroundColor": "transparent"}
                ),
                dbc.Input(
                    id="edit-log-horas-input",
                    type="text",
                    placeholder="00:00",
                    maxLength=5,
                    autocomplete="off",
                    style={
                        "fontFamily": "monospace",
                        "fontWeight": "600",
                        "letterSpacing": "0.12em",
                        "fontSize": "1.05rem"
                    }
                ),
                dbc.InputGroupText(
                    "hh:mm",
                    style={"fontSize": "0.75rem", "color": "var(--bs-secondary)",
                           "backgroundColor": "transparent"}
                ),
            ], className="mb-3"),

            html.Div(id="edit-log-horas-alert"),
            dcc.Store(id="edit-log-horas-hist-id"),
        ]),

        dbc.ModalFooter([
            dbc.Button(
                "Cancelar",
                id="edit-log-horas-cancel-btn",
                color="secondary",
                outline=True,
                className="me-2"
            ),
            dbc.Button(
                [html.I(className="fas fa-save me-2"), "Salvar"],
                id="edit-log-horas-submit-btn",
                color="primary"
            )
        ])
    ], id="edit-log-horas-modal", is_open=False, centered=True)


def delete_subtask_confirm_modal():
    """Modal de confirmação para exclusão de subtarefa."""
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle([
            html.I(className="fas fa-exclamation-triangle me-2 text-danger"),
            "Confirmar Exclusão"
        ])),

        dbc.ModalBody([
            html.P([
                "Deseja excluir esta subtarefa e todos os seus ",
                html.Strong("relatórios vinculados", className="text-danger"),
                "?"
            ]),
            html.P([
                "Esta ação é ",
                html.Strong("irreversível", className="text-danger"),
                "."
            ], className="text-muted small"),
            html.Div([
                html.Strong("ID: "),
                html.Span(id="delete-subtask-id-display", className="text-danger fw-bold")
            ], className="mt-2 p-2 rounded",
               style={"backgroundColor": "#fff3cd"})
        ]),

        dbc.ModalFooter([
            dbc.Button(
                "Cancelar",
                id="delete-subtask-cancel-btn",
                color="secondary",
                outline=True,
                className="me-2"
            ),
            dbc.Button(
                [html.I(className="fas fa-trash me-2"), "Sim, Excluir"],
                id="delete-subtask-submit-btn",
                color="danger"
            )
        ])
    ], id="delete-subtask-modal", is_open=False, centered=True)
