"""Modal para editar pendência existente."""
import dash_bootstrap_components as dbc
from dash import html, dcc


def edit_pendencia_modal():
    """
    Cria modal de edição de pendência.

    Returns:
        dbc.Modal: Modal com formulário pré-preenchível
    """
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle([
            html.I(className="fas fa-edit me-2"),
            "Editar Demanda"
        ])),

        dbc.ModalBody([
            # ID da pendência (read-only, apenas visual)
            html.Div([
                html.Strong("ID: "),
                html.Span(id="edit-pend-id-display", className="text-muted")
            ], className="mb-3"),

            # Campo: Descrição
            html.Label("Descrição:", className="fw-bold mb-1"),
            dbc.Textarea(
                id="edit-pend-descricao",
                placeholder="Descrição da demanda...",
                className="mb-3",
                rows=4,
                required=True
            ),

            # Campo: Responsável
            html.Label("Responsável:", className="fw-bold mb-1"),
            dcc.Dropdown(
                id="edit-pend-responsavel",
                placeholder="Selecione o responsável",
                className="mb-3",
                clearable=False,
                searchable=True
            ),
            html.Small(id="edit-pend-responsavel-help", className="text-muted d-block mb-3"),

            # Campo: Status
            html.Label("Status:", className="fw-bold mb-1"),
            dcc.Dropdown(
                id="edit-pend-status",
                options=[
                    {"label": "Em Fila (Planejamento)", "value": "Em Fila (Planejamento)"},
                    {"label": "Pendente", "value": "Pendente"},
                    {"label": "Em Andamento", "value": "Em Andamento"},
                    {"label": "Bloqueado", "value": "Bloqueado"},
                    {"label": "Concluído", "value": "Concluído"},
                ],
                clearable=False,
                className="mb-3"
            ),

            # Campo: Nota GAM (opcional)
            html.Label("Nota GAM:", className="fw-bold mb-1"),
            html.Span(" (opcional)", className="text-muted small"),
            dbc.Input(
                id="edit-pend-nota-gam",
                type="text",
                placeholder="Número da OS/nota no sistema GAM",
                className="mb-1"
            ),
            html.Small("Número da ordem de serviço no sistema GAM.",
                      className="text-muted d-block mb-3"),

            # Campo: Observações (OBRIGATÓRIO)
            html.Label("Observações:", className="fw-bold mb-1"),
            html.Span(" *", className="text-danger"),
            dbc.Textarea(
                id="edit-pend-observacoes",
                placeholder="Detalhe as ações realizadas, justificativas ou informações relevantes...",
                className="mb-2",
                rows=3,
                required=True
            ),
            html.Small("Campo obrigatório. Descreva detalhes sobre esta atualização.",
                      className="text-muted d-block mb-3"),

            # Área de alerta
            html.Div(id="edit-pend-alert"),

            # Store para dados originais (comparação)
            dcc.Store(id="edit-pend-original-data")
        ]),

        dbc.ModalFooter([
            # Botão Deletar (apenas nível 3)
            dbc.Button(
                [html.I(className="fas fa-trash-alt me-2"), "Deletar"],
                id="edit-pend-delete-btn",
                color="danger",
                outline=True,
                className="me-auto"
            ),

            dbc.Button(
                "Cancelar",
                id="edit-pend-cancel-btn",
                color="secondary",
                outline=True,
                className="me-2"
            ),
            dbc.Button(
                [html.I(className="fas fa-save me-2"), "Salvar Alterações"],
                id="edit-pend-submit-btn",
                color="primary"
            )
        ])
    ], id="edit-pend-modal", is_open=False, size="lg", centered=True)


def delete_confirm_modal():
    """
    Modal de confirmação para deletar pendência.

    Returns:
        dbc.Modal: Modal de confirmação
    """
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle([
            html.I(className="fas fa-exclamation-triangle me-2 text-danger"),
            "Confirmar Exclusão"
        ])),

        dbc.ModalBody([
            html.H5("Tem certeza que deseja deletar esta demanda?", className="mb-3"),
            html.P([
                "Esta ação é ",
                html.Strong("irreversível", className="text-danger"),
                " e irá remover:"
            ]),
            html.Ul([
                html.Li("A demanda e todos os seus dados"),
                html.Li("Todo o histórico de atualizações"),
            ]),
            html.Div([
                html.Strong("ID: "),
                html.Span(id="delete-confirm-id", className="text-danger fw-bold")
            ], className="mt-3 p-2", style={"backgroundColor": "#fff3cd", "borderRadius": "4px"})
        ]),

        dbc.ModalFooter([
            dbc.Button(
                "Cancelar",
                id="delete-confirm-cancel-btn",
                color="secondary",
                outline=True,
                className="me-2"
            ),
            dbc.Button(
                [html.I(className="fas fa-trash-alt me-2"), "Sim, Deletar"],
                id="delete-confirm-submit-btn",
                color="danger"
            )
        ])
    ], id="delete-confirm-modal", is_open=False, centered=True)
