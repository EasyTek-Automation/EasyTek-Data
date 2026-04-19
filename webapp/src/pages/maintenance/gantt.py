# src/pages/maintenance/gantt.py

from dash import html, dcc
import dash_bootstrap_components as dbc


# ---------------------------------------------------------------------------
# Helpers de modal
# ---------------------------------------------------------------------------

def _modal_category():
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle(id="title-modal-category")),
        dbc.ModalBody([
            dbc.Label("Nome *"),
            dbc.Input(id="input-category-nome", type="text", placeholder="Nome da categoria",
                      maxLength=120, className="mb-3"),
            dbc.Row([
                dbc.Col([
                    dbc.Label("Início *"),
                    dbc.Input(id="input-category-inicio", type="datetime-local"),
                ], width=6),
                dbc.Col([
                    dbc.Label("Fim *"),
                    dbc.Input(id="input-category-fim", type="datetime-local"),
                ], width=6),
            ]),
        ]),
        dbc.ModalFooter([
            dbc.Button("Cancelar", id="btn-cancel-category", color="secondary", outline=True),
            dbc.Button("Salvar",   id="btn-save-category",   color="primary"),
        ]),
    ], id="modal-category", is_open=False, backdrop="static")


def _modal_activity():
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle(id="title-modal-activity")),
        dbc.ModalBody([
            dbc.Label("Título *"),
            dbc.Input(id="input-activity-titulo", type="text", placeholder="Título da atividade",
                      maxLength=200, className="mb-3"),
            dbc.Label("Categoria *"),
            dcc.Dropdown(id="dropdown-activity-categoria", placeholder="Selecionar categoria",
                         clearable=False, className="mb-3"),
            dbc.Row([
                dbc.Col([
                    dbc.Label("Início *"),
                    dbc.Input(id="input-activity-inicio", type="datetime-local"),
                ], width=6),
                dbc.Col([
                    dbc.Label("Fim *"),
                    dbc.Input(id="input-activity-fim", type="datetime-local"),
                ], width=6),
            ], className="mb-3"),
            html.Div([
                dbc.Label("Progresso real (%)"),
                dbc.Input(id="input-activity-progresso", type="number",
                          min=0, max=100, step=1, placeholder="0"),
            ], id="div-activity-progresso", style={"display": "none"}),
        ]),
        dbc.ModalFooter([
            dbc.Button("Cancelar", id="btn-cancel-activity", color="secondary", outline=True),
            dbc.Button("Salvar",   id="btn-save-activity",   color="primary"),
        ]),
    ], id="modal-activity", is_open=False, backdrop="static")


def _modal_assignment():
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle(id="title-modal-assignment")),
        dbc.ModalBody([
            dbc.Label("Funcionário *"),
            dcc.Dropdown(id="dropdown-assignment-funcionario", placeholder="Selecionar funcionário",
                         clearable=False, className="mb-3"),
            dbc.Row([
                dbc.Col([
                    dbc.Label("Entrada *"),
                    dbc.Input(id="input-assignment-entrada", type="datetime-local"),
                ], width=6),
                dbc.Col([
                    dbc.Label("Saída *"),
                    dbc.Input(id="input-assignment-saida", type="datetime-local"),
                ], width=6),
            ]),
        ]),
        dbc.ModalFooter([
            dbc.Button("Cancelar", id="btn-cancel-assignment", color="secondary", outline=True),
            dbc.Button("Salvar",   id="btn-save-assignment",   color="primary"),
        ]),
    ], id="modal-assignment", is_open=False, backdrop="static")


def _modal_employee():
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle(id="title-modal-employee")),
        dbc.ModalBody([
            dbc.Label("Nome *"),
            dbc.Input(id="input-employee-nome", type="text", placeholder="Nome do funcionário",
                      maxLength=120, className="mb-3"),
            dbc.Label("Turno padrão *"),
            dbc.RadioItems(
                id="radio-employee-turno",
                options=[
                    {"label": "Turno A (00h–06h)", "value": "A"},
                    {"label": "Turno B (06h–15h)", "value": "B"},
                    {"label": "Turno C (15h–00h)", "value": "C"},
                ],
                value="B",
                className="mt-1",
            ),
        ]),
        dbc.ModalFooter([
            dbc.Button("Cancelar", id="btn-cancel-employee", color="secondary", outline=True),
            dbc.Button("Salvar",   id="btn-save-employee",   color="primary"),
        ]),
    ], id="modal-employee", is_open=False, backdrop="static")


def _modal_validation_errors():
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Não foi possível salvar")),
        dbc.ModalBody([
            html.P("⚠ Os seguintes problemas foram encontrados:", className="fw-semibold"),
            html.Ul(id="list-validation-errors"),
        ]),
        dbc.ModalFooter(
            dbc.Button("Fechar", id="btn-close-validation-errors", color="secondary")
        ),
    ], id="modal-validation-errors", is_open=False)


def _modal_confirm_delete():
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Confirmar exclusão")),
        dbc.ModalBody([
            html.P([
                "Tem certeza que deseja excluir ",
                html.Strong(id="text-confirm-delete-name"),
                "?",
            ]),
            html.P("Esta ação não pode ser desfeita.", className="text-muted small"),
        ]),
        dbc.ModalFooter([
            dbc.Button("Cancelar", id="btn-cancel-delete",  color="secondary", outline=True),
            dbc.Button("Excluir",  id="btn-confirm-delete", color="danger"),
        ]),
    ], id="modal-confirm-delete", is_open=False, backdrop="static")


def _modal_block_info():
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle(id="text-block-info-title")),
        dbc.ModalBody(html.P(id="text-block-info-message")),
        dbc.ModalFooter(
            dbc.Button("Fechar", id="btn-close-block-info", color="secondary")
        ),
    ], id="modal-block-info", is_open=False)


# ---------------------------------------------------------------------------
# Layout principal
# ---------------------------------------------------------------------------

def layout():
    """Página principal do Planejamento Gantt."""
    return dbc.Container([
        # Stores
        dcc.Store(id="store-gantt-granularity",      storage_type="local",  data="dias"),
        dcc.Store(id="store-gantt-categories-state", storage_type="local",  data={}),
        dcc.Store(id="store-gantt-refresh",          storage_type="memory", data=0),
        dcc.Store(id="store-category-editing-id",    storage_type="memory"),
        dcc.Store(id="store-activity-editing-id",    storage_type="memory"),
        dcc.Store(id="store-assignment-editing-id",  storage_type="memory"),
        dcc.Store(id="store-assignment-activity-id", storage_type="memory"),
        dcc.Store(id="store-employee-editing-id",    storage_type="memory"),
        dcc.Store(id="store-validation-errors",      storage_type="memory"),
        dcc.Store(id="store-confirm-delete",         storage_type="memory"),
        dcc.Store(id="store-block-info",             storage_type="memory"),

        # Header
        dbc.Row([
            dbc.Col([
                html.H2("Planejamento Gantt"),
                html.P("Visualização e gerenciamento de atividades por categoria",
                       className="text-muted"),
            ], width=8),
            dbc.Col([
                dbc.ButtonGroup([
                    dbc.Button(
                        [html.I(className="bi bi-person-plus me-1"), "Funcionários"],
                        id="btn-open-employee-list",
                        color="secondary",
                        outline=True,
                        size="sm",
                    ),
                    dbc.Button(
                        [html.I(className="bi bi-plus-lg me-1"), "Nova Categoria"],
                        id="btn-new-category",
                        color="primary",
                        size="sm",
                    ),
                ])
            ], width=4, className="text-end"),
        ], className="mb-3"),

        # Controles
        dbc.Row([
            dbc.Col([
                dbc.InputGroup([
                    dbc.InputGroupText("Escala"),
                    dcc.Dropdown(
                        id="dropdown-gantt-granularity",
                        options=[
                            {"label": "Horas",   "value": "horas"},
                            {"label": "Dias",    "value": "dias"},
                            {"label": "Semanas", "value": "semanas"},
                            {"label": "Meses",   "value": "meses"},
                        ],
                        value="dias",
                        clearable=False,
                        style={"minWidth": "120px"},
                    ),
                ], size="sm"),
            ], width="auto"),
            dbc.Col([
                dbc.ButtonGroup([
                    dbc.Button("Expandir tudo",  id="btn-expand-all",   color="secondary",
                               outline=True, size="sm"),
                    dbc.Button("Recolher tudo",  id="btn-collapse-all", color="secondary",
                               outline=True, size="sm"),
                ]),
            ], width="auto"),
            dbc.Col([
                dbc.Button(
                    [html.I(className="bi bi-plus me-1"), "Nova Atividade"],
                    id="btn-new-activity",
                    color="success",
                    outline=True,
                    size="sm",
                ),
            ], width="auto"),
        ], className="mb-3 g-2 align-items-center"),

        # Área do Gantt
        html.Div(id="gantt-chart-container", style={"minHeight": "200px"}),

        # Modais
        _modal_category(),
        _modal_activity(),
        _modal_assignment(),
        _modal_employee(),
        _modal_validation_errors(),
        _modal_confirm_delete(),
        _modal_block_info(),

    ], fluid=True, className="p-4")


# ---------------------------------------------------------------------------
# Layout do log de auditoria
# ---------------------------------------------------------------------------

def audit_log_layout():
    """Página de log de auditoria (nível 2+)."""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H2("Log de Auditoria — Gantt"),
                html.P("Registro de todas as operações de criação, edição e exclusão",
                       className="text-muted"),
            ], width=10),
            dbc.Col([
                dbc.Button(
                    [html.I(className="bi bi-arrow-clockwise me-1"), "Atualizar"],
                    id="btn-refresh-audit-log",
                    color="secondary",
                    outline=True,
                    size="sm",
                ),
            ], width=2, className="text-end"),
        ], className="mb-4"),

        dcc.Store(id="store-audit-log-refresh", storage_type="memory", data=0),

        html.Div(id="audit-log-table-container"),

    ], fluid=True, className="p-4")
