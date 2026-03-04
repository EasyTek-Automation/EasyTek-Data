"""Modais para CRUD de subtarefas e logs do Workflow."""
import dash_bootstrap_components as dbc
from dash import html, dcc

# Opções de tipo de evento (mesmas do modal de edição de pendência)
TIPOS_EVENTO_OPTIONS = [
    {"label": "Análise de Falha", "value": "Análise de Falha"},
    {"label": "Aguardando Material", "value": "Aguardando Material"},
    {"label": "Aguardando Aprovação", "value": "Aguardando Aprovação"},
    {"label": "Manutenção Corretiva", "value": "Manutenção Corretiva"},
    {"label": "Manutenção Preventiva", "value": "Manutenção Preventiva"},
    {"label": "Revisão de Software", "value": "Revisão de Software"},
    {"label": "Teste e Validação", "value": "Teste e Validação"},
    {"label": "Em Produção Assistida", "value": "Em Produção Assistida"},
    {"label": "Documentação Técnica", "value": "Documentação Técnica"},
    {"label": "Treinamento Operacional", "value": "Treinamento Operacional"},
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
            # Título (personalizável, obrigatório)
            html.Label("Título:", className="fw-bold mb-1"),
            html.Span(" *", className="text-danger"),
            dbc.Input(
                id="create-subtask-titulo",
                type="text",
                placeholder="Ex: Verificar rolamento do motor A",
                className="mb-3"
            ),

            # Tipo de evento (categoria, obrigatório)
            html.Label("Tipo de Evento:", className="fw-bold mb-1"),
            html.Span(" *", className="text-danger"),
            dcc.Dropdown(
                id="create-subtask-tipo",
                options=TIPOS_EVENTO_OPTIONS,
                placeholder="Selecione o tipo",
                clearable=False,
                className="mb-3"
            ),

            # Responsável
            html.Label("Responsável:", className="fw-bold mb-1"),
            html.Span(" *", className="text-danger"),
            dcc.Dropdown(
                id="create-subtask-responsavel",
                placeholder="Selecione o responsável",
                clearable=False,
                searchable=True,
                className="mb-3"
            ),

            # Aprovador (condicional)
            html.Div([
                html.Label("Aprovador (Nível 3):", className="fw-bold mb-1"),
                html.Span(" *", className="text-danger"),
                dcc.Dropdown(
                    id="create-subtask-aprovador",
                    placeholder="Selecione o aprovador",
                    clearable=False,
                    searchable=True,
                    className="mb-1"
                ),
                html.Small(
                    "Este tipo de evento requer aprovação de um usuário nível 3.",
                    className="text-warning d-block mb-3"
                ),
            ], id="create-subtask-aprovador-container", style={"display": "none"}),

            # Observações (opcional)
            html.Label("Observações:", className="fw-bold mb-1"),
            html.Span(" (opcional)", className="text-muted small"),
            dbc.Textarea(
                id="create-subtask-obs",
                placeholder="Informações adicionais sobre esta subtarefa...",
                rows=3,
                className="mb-3"
            ),

            # Alerta
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

            # Horas (opcional — transferido do create-subtask)
            html.Label("Horas trabalhadas:", className="fw-bold mb-1"),
            html.Span(" (opcional)", className="text-muted small"),
            dbc.Input(
                id="add-log-horas",
                type="number",
                min=0,
                step=0.5,
                placeholder="Ex: 2.5",
                className="mb-3"
            ),

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
            # Título personalizável
            html.Label("Título:", className="fw-bold mb-1"),
            dbc.Input(
                id="edit-subtask-titulo",
                type="text",
                placeholder="Título da subtarefa...",
                className="mb-3"
            ),

            # Tipo de evento (categoria)
            html.Label("Tipo de Evento:", className="fw-bold mb-1"),
            dcc.Dropdown(
                id="edit-subtask-tipo",
                options=TIPOS_EVENTO_OPTIONS,
                clearable=False,
                className="mb-3"
            ),

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

            # Alerta
            html.Div(id="edit-subtask-alert"),

            # Store para hist_id sendo editado
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
