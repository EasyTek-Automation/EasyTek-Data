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
            "Editar Pendência"
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
                placeholder="Descrição da pendência...",
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
                    {"label": "Pendente", "value": "Pendente"},
                    {"label": "Em Andamento", "value": "Em Andamento"},
                    {"label": "Bloqueado", "value": "Bloqueado"},
                    {"label": "Concluído", "value": "Concluído"},
                ],
                clearable=False,
                className="mb-3"
            ),

            # Campo: Tipo de Evento (dropdown pré-determinado)
            html.Label("Tipo de Evento:", className="fw-bold mb-1"),
            dcc.Dropdown(
                id="edit-pend-tipo-evento",
                options=[
                    {"label": "Primeira inspeção concluída", "value": "Primeira inspeção concluída"},
                    {"label": "Teste realizado com sucesso", "value": "Teste realizado com sucesso"},
                    {"label": "Aguardando peça do fornecedor", "value": "Aguardando peça do fornecedor"},
                    {"label": "Manutenção preventiva realizada", "value": "Manutenção preventiva realizada"},
                    {"label": "Problema identificado", "value": "Problema identificado"},
                    {"label": "Solução implementada", "value": "Solução implementada"},
                    {"label": "Revisão técnica concluída", "value": "Revisão técnica concluída"},
                    {"label": "Documentação atualizada", "value": "Documentação atualizada"},
                    {"label": "Treinamento realizado", "value": "Treinamento realizado"},
                    {"label": "Validação em andamento", "value": "Validação em andamento"},
                ],
                placeholder="Selecione o tipo de evento",
                clearable=False,
                className="mb-3"
            ),
            html.Small("Selecione o evento que descreve esta atualização no workflow.",
                      className="text-muted d-block mb-3"),

            # Campo: Observações (OBRIGATÓRIO)
            html.Label("Observações:", className="fw-bold mb-1"),
            html.Span("*", className="text-danger ms-1"),
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
