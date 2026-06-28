# src/pages/maintenance/gantt.py

from dash import html, dcc
import dash_bootstrap_components as dbc


# ---------------------------------------------------------------------------
# Helpers de modal
# ---------------------------------------------------------------------------

def _modal_reschedule():
    """Modal de reagendamento de plano (Feature Reagendamento — SP-16 / DS-17).

    Datepicker para a nova data de início + painel de prévia (delta, contagens,
    conflitos cross-projeto) preenchido por callback. Confirmar só habilita
    quando há mudança real."""
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle(id="title-modal-reschedule")),
        dbc.ModalBody([
            dbc.Alert(
                "Reagendar desloca TODO o plano deste projeto — categorias, atividades "
                "e atribuições — pelo mesmo intervalo, preservando as durações. "
                "Os demais projetos não são afetados.",
                color="info", className="py-2", style={"fontSize": "0.85rem"},
            ),
            dbc.Label("Nova data e hora de início do projeto *"),
            dbc.Input(id="input-reschedule-novo-inicio", type="datetime-local",
                      className="mb-3"),
            html.Div(id="reschedule-preview"),
        ]),
        dbc.ModalFooter([
            dbc.Button("Cancelar", id="btn-cancel-reschedule",
                       color="secondary", outline=True),
            dbc.Button("Confirmar reagendamento", id="btn-confirm-reschedule",
                       color="primary", disabled=True),
        ]),
    ], id="modal-reschedule", is_open=False, backdrop="static")


def _modal_project():
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle(id="title-modal-project")),
        dbc.ModalBody([
            dbc.Label("Nome *"),
            dbc.Input(id="input-project-nome", type="text", placeholder="Nome do projeto",
                      maxLength=150, className="mb-3"),
            dbc.Label("Tipo *"),
            dcc.Dropdown(
                id="dropdown-project-tipo",
                options=[
                    {"label": "Parada Preventiva",   "value": "Parada Preventiva"},
                    {"label": "Parada Corretiva",    "value": "Parada Corretiva"},
                    {"label": "Projeto de Melhoria", "value": "Projeto de Melhoria"},
                    {"label": "Outro",               "value": "Outro"},
                ],
                placeholder="Selecionar tipo",
                clearable=False,
                className="mb-3",
            ),
            dbc.Row([
                dbc.Col([
                    dbc.Label("Início *"),
                    dbc.Input(id="input-project-inicio", type="datetime-local"),
                ], width=6),
                dbc.Col([
                    dbc.Label("Fim *"),
                    dbc.Input(id="input-project-fim", type="datetime-local"),
                ], width=6),
            ], className="mb-3"),
            dbc.Label("Observações"),
            dbc.Textarea(id="input-project-observacoes",
                         placeholder="Observações adicionais...",
                         rows=3, className="mb-2"),
        ]),
        dbc.ModalFooter([
            dbc.Button("Cancelar", id="btn-cancel-project", color="secondary", outline=True),
            dbc.Button("Salvar",   id="btn-save-project",   color="primary"),
        ]),
    ], id="modal-project", is_open=False, backdrop="static")


def _modal_category():
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle(id="title-modal-category")),
        dbc.ModalBody([
            dbc.Label("Projeto *"),
            dcc.Dropdown(id="dropdown-category-projeto", placeholder="Selecionar projeto",
                         clearable=False, className="mb-3"),
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
            dbc.Label("Projeto *"),
            dcc.Dropdown(id="dropdown-activity-projeto", placeholder="Selecionar projeto",
                         clearable=False, className="mb-3"),
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
            dbc.Label("Observação / Justificativa"),
            dbc.Textarea(
                id="input-activity-observacao",
                placeholder="Opcional — contexto, dependências, riscos, notas",
                style={"minHeight": "90px"},
                className="mb-3",
            ),
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


def _modal_employee_management():
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Funcionários")),
        dbc.ModalBody(
            dbc.Tabs([
                dbc.Tab(
                    html.Div(id="div-employee-list-content", className="pt-3"),
                    label="Cadastrados",
                    tab_id="tab-emp-list",
                ),
                dbc.Tab(
                    html.Div([
                        html.H6("Novo Funcionário", id="employee-form-title", className="mb-3 mt-3 fw-semibold"),
                        dbc.Label("Nome *"),
                        dbc.Input(id="input-employee-nome", type="text",
                                  placeholder="Nome do funcionário",
                                  maxLength=120, className="mb-3"),
                        dbc.Label("Turno padrão *"),
                        dbc.RadioItems(
                            id="radio-employee-turno",
                            options=[
                                {"label": "Turno A (00h–06h)", "value": "A"},
                                {"label": "Turno B (06h–15h)", "value": "B"},
                                {"label": "Turno C (15h–00h)", "value": "C"},
                                {"label": "Administrativo (08h–17h)", "value": "ADM"},
                            ],
                            value="B",
                            className="mt-1 mb-3",
                        ),
                        dbc.Label("Foto (JPG ou PNG, opcional)"),
                        html.Div([
                            html.Div(id="div-employee-photo-preview", className="mb-2"),
                            dcc.Upload(
                                id="upload-employee-photo",
                                children=html.Div([
                                    html.I(className="bi bi-cloud-upload me-2"),
                                    "Arraste uma imagem aqui ou clique para selecionar",
                                ]),
                                accept="image/jpeg,image/png",
                                multiple=False,
                                style={
                                    "width": "100%", "padding": "12px",
                                    "border": "2px dashed var(--bs-border-color)",
                                    "borderRadius": "6px", "textAlign": "center",
                                    "cursor": "pointer", "color": "var(--bs-secondary)",
                                    "fontSize": "0.85rem",
                                },
                            ),
                            dbc.Button(
                                [html.I(className="bi bi-x-circle me-1"), "Remover foto"],
                                id="btn-clear-employee-photo",
                                color="danger", outline=True, size="sm",
                                className="mt-2", style={"display": "none"},
                            ),
                        ], className="mb-4"),
                        dcc.Store(id="store-employee-photo-staged"),
                        dbc.Button("Salvar",   id="btn-save-employee",   color="primary"),
                        dbc.Button("Cancelar", id="btn-cancel-employee", color="secondary",
                                   outline=True, className="ms-2"),
                    ]),
                    label="Novo / Editar",
                    tab_id="tab-emp-form",
                ),
            ], id="tabs-employee", active_tab="tab-emp-list"),
        ),
        dbc.ModalFooter(
            dbc.Button("Fechar", id="btn-close-employee-list", color="secondary", outline=True),
        ),
    ], id="modal-employee-list", is_open=False, size="lg")


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


def _modal_archived_projects():
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle([
            html.I(className="bi bi-archive-fill me-2"),
            "Projetos Arquivados",
        ])),
        dbc.ModalBody(
            html.Div(id="div-archived-projects-content", className="pt-1"),
        ),
        dbc.ModalFooter(
            dbc.Button("Fechar", id="btn-close-archived-projects",
                       color="secondary", outline=True),
        ),
    ], id="modal-archived-projects", is_open=False, size="lg")


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
        dcc.Store(id="store-gantt-granularity",       storage_type="local",  data="dias"),
        dcc.Store(id="store-gantt-projects-state",   storage_type="local",  data={}),
        dcc.Store(id="store-gantt-categories-state", storage_type="local",  data={}),
        dcc.Store(id="store-gantt-activities-state", storage_type="local",  data={}),
        dcc.Store(id="store-project-editing-id",     storage_type="memory"),
        dcc.Store(id="store-reschedule-target",      storage_type="memory"),
        dcc.Store(id="store-conflict-highlight",     storage_type="memory", data=[]),
        dcc.Store(id="store-gantt-refresh",          storage_type="memory", data=0),
        dcc.Store(id="store-category-editing-id",    storage_type="memory"),
        dcc.Store(id="store-activity-editing-id",    storage_type="memory"),
        dcc.Store(id="store-assignment-editing-id",  storage_type="memory"),
        dcc.Store(id="store-assignment-activity-id", storage_type="memory"),
        dcc.Store(id="store-employee-editing-id",    storage_type="memory"),
        dcc.Store(id="store-validation-errors",      storage_type="memory"),
        dcc.Store(id="store-confirm-delete",         storage_type="memory"),
        dcc.Store(id="store-block-info",             storage_type="memory"),
        dcc.Store(id="store-gantt-hour-offset",      storage_type="memory", data=0),
        dcc.Store(id="store-gantt-filter",           storage_type="memory", data=""),
        dcc.Store(id="store-gantt-view-mode",        storage_type="local",  data="projeto"),
        dcc.Store(id="store-gantt-employees-state",  storage_type="local",  data={}),

        # Stores de dados estruturais (Feature C — DS-10 / SP-14)
        # Inicial None distingue "ainda não carregado" (None) de "sem dados" ([]).
        dcc.Store(id="store-gantt-data-projects",    storage_type="memory", data=None),
        dcc.Store(id="store-gantt-data-categories",  storage_type="memory", data=None),
        dcc.Store(id="store-gantt-data-activities",  storage_type="memory", data=None),
        dcc.Store(id="store-gantt-data-assignments", storage_type="memory", data=None),
        dcc.Store(id="store-gantt-data-employees",   storage_type="memory", data=None),
        dcc.Store(id="store-gantt-data-status",      storage_type="memory", data="idle"),

        # Header
        dbc.Row([
            dbc.Col([
                html.H2([
                    html.I(className="bi bi-bar-chart-steps me-2",
                           style={"color": "#66A593"}),
                    "Planejamento Gantt",
                ], className="mb-1"),
                html.P("Visualização e gerenciamento de projetos, categorias e atividades",
                       className="text-muted mb-0"),
            ], width=6),
            dbc.Col([
                # ButtonGroup do header — pré-15/05 tinha 5 botões em uma linha
                # com width=4. Atualizar (Feature C) entra GRUDADO como 1º item;
                # width da coluna passa para 5 para acomodar 6 botões sem quebra
                # de linha em viewport >=1366 px. Ver .dev-docs/projects/
                # GantManagement/regra-preservar-ui.md.
                dbc.ButtonGroup([
                    dbc.Button(
                        [html.I(className="bi bi-arrow-clockwise me-1"), "Atualizar"],
                        id="btn-gantt-refresh",
                        color="secondary",
                        outline=True,
                        size="sm",
                        n_clicks=0,
                        title="Recarregar dados do banco",
                        style={"whiteSpace": "nowrap"},
                    ),
                    dbc.Button(
                        [html.I(className="bi bi-journal-text me-1"), "Auditoria"],
                        href="/maintenance/gantt/audit-log",
                        color="secondary",
                        outline=True,
                        size="sm",
                        external_link=False,
                        style={"whiteSpace": "nowrap"},
                    ),
                    dbc.Button(
                        [html.I(className="bi bi-person-plus me-1"), "Funcionários"],
                        id="btn-open-employee-list",
                        color="secondary",
                        outline=True,
                        size="sm",
                        style={"whiteSpace": "nowrap"},
                    ),
                    dbc.Button(
                        [html.I(className="bi bi-archive me-1"), "Arquivados"],
                        id="btn-open-archived-projects",
                        color="secondary",
                        outline=True,
                        size="sm",
                        style={"whiteSpace": "nowrap"},
                    ),
                    dbc.Button(
                        [html.I(className="bi bi-file-earmark-pdf me-1"), "Exportar PDF"],
                        id="btn-export-gantt",
                        color="secondary",
                        outline=True,
                        size="sm",
                        style={"whiteSpace": "nowrap"},
                    ),
                    dbc.Button(
                        [html.I(className="bi bi-folder-plus me-1"), "Novo Projeto"],
                        id="btn-new-project",
                        color="primary",
                        size="sm",
                        style={"whiteSpace": "nowrap"},
                    ),
                ])
            ], width=6, className="text-end d-flex align-items-center justify-content-end"),
        ], className="mb-3"),

        # Toolbar — controles com rótulos
        dbc.Card([
            dbc.CardHeader(
                html.H5([
                    html.I(className="bi bi-sliders me-2"),
                    "Filtros & Visualização",
                ], className="mb-0 text-white fw-semibold"),
                style={"backgroundColor": "#66A593", "borderBottom": "none"},
            ),
            dbc.CardBody(
                dbc.Row([
                    dbc.Col([
                        html.Small("Escala do eixo", className="text-muted fw-semibold d-block mb-1"),
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
                            style={"minWidth": "140px"},
                        ),
                    ], width="auto"),
                    dbc.Col([
                        html.Small("Visualização da hierarquia",
                                   className="text-muted fw-semibold d-block mb-1"),
                        dbc.ButtonGroup([
                            dbc.Button([html.I(className="bi bi-arrows-expand me-1"), "Expandir tudo"],
                                       id="btn-expand-all", color="secondary", outline=True, size="sm"),
                            dbc.Button([html.I(className="bi bi-arrows-collapse me-1"), "Recolher tudo"],
                                       id="btn-collapse-all", color="secondary", outline=True, size="sm"),
                        ]),
                    ], width="auto"),
                    dbc.Col([
                        html.Small("Agrupar por",
                                   className="text-muted fw-semibold d-block mb-1"),
                        dbc.ButtonGroup([
                            dbc.Button([html.I(className="bi bi-diagram-3 me-1"), "Projeto"],
                                       id="btn-view-projeto", color="primary", size="sm"),
                            dbc.Button([html.I(className="bi bi-people me-1"), "Funcionário"],
                                       id="btn-view-funcionario", color="secondary", outline=True, size="sm"),
                        ], id="group-view-mode"),
                    ], width="auto"),
                    dbc.Col([
                        html.Small("Navegação no tempo",
                                   className="text-muted fw-semibold d-block mb-1"),
                        html.Div([
                            dbc.ButtonGroup([
                                dbc.Button("◀",    id="btn-hour-prev",  color="secondary", outline=True, size="sm"),
                                dbc.Button("Hoje", id="btn-hour-today", color="info",      outline=True, size="sm"),
                                dbc.Button("▶",    id="btn-hour-next",  color="secondary", outline=True, size="sm"),
                            ], className="me-2"),
                            dcc.Dropdown(
                                id="dropdown-hour-step",
                                options=[
                                    {"label": "± 4h",   "value": 4},
                                    {"label": "± 12h",  "value": 12},
                                    {"label": "± 1 dia", "value": 24},
                                    {"label": "± 1 sem","value": 168},
                                    {"label": "± 1 mês","value": 720},
                                ],
                                value=24,
                                clearable=False,
                                style={"minWidth": "110px"},
                            ),
                        ], id="div-hour-nav",
                           style={"display": "none", "alignItems": "center", "gap": "0"}),
                    ], width="auto"),
                    dbc.Col([
                        html.Small("Buscar",
                                   className="text-muted fw-semibold d-block mb-1"),
                        dbc.InputGroup([
                            dbc.InputGroupText(html.I(className="bi bi-search")),
                            dbc.Input(
                                id="input-gantt-filter",
                                type="search",
                                placeholder="Projeto, categoria ou atividade...",
                                debounce=True,
                                size="sm",
                            ),
                        ], size="sm"),
                    ], width=True),
                ], className="g-3 align-items-end"),
                className="py-2 px-3",
            ),
        ], className="mb-3 shadow",
           style={"border": "1px solid var(--bs-border-color)"}),

        # Cards de KPI — resumo rápido do estado atual
        dbc.Row(id="row-gantt-kpis", className="mb-3 g-3"),

        # Card dos projetos — CardHeader em sticky para que o título
        # "Projetos & Manutenções" trave no topo do viewport ao rolar a página,
        # permitindo que o conteúdo do Gantt continue rolando abaixo dele.
        dbc.Card([
            dbc.CardHeader(
                html.H5([
                    html.I(className="bi bi-kanban-fill me-2"),
                    "Projetos & Manutenções",
                ], className="mb-0 text-white fw-semibold"),
                style={
                    "backgroundColor": "#66A593", "borderBottom": "none",
                    "position": "sticky", "top": "0", "zIndex": "100",
                },
            ),
            dbc.CardBody(
                html.Div([
                    dcc.Loading(
                        id="loading-gantt",
                        type="circle",
                        color="#66A593",
                        children=html.Div(id="gantt-chart-container",
                                          style={"minHeight": "200px"}),
                        parent_className="gantt-loading-wrapper",
                    ),
                    # Handle de resize da coluna esquerda (Feature E) — JS em
                    # assets/gantt-resize.js controla drag e persiste em localStorage.
                    html.Div(id="gantt-resize-handle",
                             className="gantt-resize-handle",
                             title="Arraste para ajustar a largura da coluna"),
                ], className="gantt-resize-wrapper"),
                className="p-2",
            ),
        ], className="mb-3 shadow",
           style={"border": "1px solid var(--bs-border-color)"}),

        # Modais
        _modal_project(),
        _modal_reschedule(),
        _modal_category(),
        _modal_activity(),
        _modal_assignment(),
        _modal_employee_management(),
        _modal_archived_projects(),
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
