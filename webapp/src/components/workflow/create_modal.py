"""Modal para criar novo workflow."""
import dash_bootstrap_components as dbc
from dash import html, dcc


def create_pendencia_modal():
    """
    Cria modal de criação de pendência.

    Returns:
        dbc.Modal: Modal com formulário
    """
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle([
            html.I(className="fas fa-plus-circle me-2"),
            "Novo Workflow"
        ])),

        dbc.ModalBody([
            # Campo: Descrição
            html.Label("Descrição:", className="fw-bold mb-1"),
            dbc.Textarea(
                id="create-pend-descricao",
                placeholder="Descreva a pendência detalhadamente...",
                className="mb-3",
                rows=4,
                required=True
            ),

            # Campo: Responsável (dropdown dinâmico)
            html.Label("Responsável:", className="fw-bold mb-1"),
            dcc.Dropdown(
                id="create-pend-responsavel",
                placeholder="Selecione o responsável",
                className="mb-3",
                clearable=False,
                searchable=True
            ),
            html.Small(id="create-pend-responsavel-help", className="text-muted d-block mb-3"),

            # Campo: Status inicial
            html.Label("Status Inicial:", className="fw-bold mb-1"),
            dcc.Dropdown(
                id="create-pend-status",
                options=[
                    {"label": "Pendente", "value": "Pendente"},
                    {"label": "Em Andamento", "value": "Em Andamento"},
                ],
                value="Pendente",  # Default
                clearable=False,
                className="mb-3"
            ),

            # Campo: Nota GAM (opcional)
            html.Label("Nota GAM:", className="fw-bold mb-1"),
            html.Span(" (opcional)", className="text-muted small"),
            dbc.Input(
                id="create-pend-nota-gam",
                type="text",
                placeholder="Número da OS/nota no sistema GAM",
                className="mb-1"
            ),
            html.Small("Informe o número da ordem de serviço no sistema GAM, se houver.",
                      className="text-muted d-block mb-3"),

            # Área de alerta
            html.Div(id="create-pend-alert")
        ]),

        dbc.ModalFooter([
            dbc.Button(
                "Cancelar",
                id="create-pend-cancel-btn",
                color="secondary",
                outline=True,
                className="me-2"
            ),
            dbc.Button(
                [html.I(className="fas fa-check-circle me-2"), "Criar Pendência"],
                id="create-pend-submit-btn",
                color="success"
            )
        ])
    ], id="create-pend-modal", is_open=False, size="lg", centered=True)
