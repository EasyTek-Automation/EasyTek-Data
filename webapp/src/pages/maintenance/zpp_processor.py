"""
Página de Processamento de Planilhas ZPP.
Acesso restrito a usuários nível 3+.
"""
from dash import html, dcc
import dash_bootstrap_components as dbc
from flask_login import current_user

from src.components.zpp_processor_components import create_file_list_card


def _build_upload_tab():
    return dbc.Card(dbc.CardBody([
        html.H5("Upload Retroativo", className="card-title mb-4"),
        html.P(
            "Envie um arquivo Excel para um mês histórico. "
            "O mês de destino é definido por você — os dados do SAP são ignorados para esse cálculo.",
            className="text-muted mb-4"
        ),

        dbc.Row([
            # Upload area
            dbc.Col([
                dcc.Upload(
                    id="upload-zpp-retroativo",
                    children=html.Div([
                        html.I(className="bi bi-cloud-upload fs-3 d-block mb-2"),
                        html.Span("Arraste o arquivo ou "),
                        html.A("clique para selecionar", href="#"),
                        html.Br(),
                        html.Small(".xlsx ou .xls", className="text-muted"),
                    ]),
                    accept=".xlsx,.xls",
                    className="border border-dashed rounded p-4 text-center",
                    style={"cursor": "pointer"},
                ),
                html.Div(id="upload-zpp-filename", className="text-muted small mt-1"),
            ], md=12, className="mb-3"),
        ]),

        dbc.Row([
            dbc.Col([
                dbc.Label("Ano"),
                dbc.Select(
                    id="select-ano-retroativo",
                    options=[{"label": str(y), "value": str(y)} for y in range(2020, 2030)],
                    placeholder="Selecione...",
                ),
            ], md=3),
            dbc.Col([
                dbc.Label("Mês"),
                dbc.Select(
                    id="select-mes-retroativo",
                    options=[
                        {"label": m, "value": str(i+1)}
                        for i, m in enumerate([
                            "Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                            "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"
                        ])
                    ],
                    placeholder="Selecione...",
                ),
            ], md=3),
        ], className="mb-3"),

        dbc.Row([
            dbc.Col([
                dbc.Label("Justificativa"),
                dbc.Textarea(
                    id="textarea-justificativa-retroativo",
                    placeholder="Descreva o motivo do upload retroativo (mínimo 10 caracteres)...",
                    rows=3,
                ),
            ], md=12),
        ], className="mb-4"),

        dbc.Button(
            [html.I(className="bi bi-upload me-2"), "Enviar"],
            id="btn-enviar-retroativo",
            color="primary",
            disabled=True,
        ),
        dbc.Spinner(
            html.Div(id="spinner-upload-retroativo"),
            size="sm",
            color="primary",
            spinner_class_name="ms-2",
        ),

        html.Div(id="resultado-upload-retroativo", className="mt-4"),
    ]))


def _build_logs_tab():
    return dbc.Card(dbc.CardBody([
        html.H5("Histórico de Processamentos", className="card-title mb-4"),

        # Filtros
        dbc.Row([
            dbc.Col([
                dbc.Label("Tipo", className="small"),
                dbc.Select(
                    id="filter-tipo-logs",
                    options=[
                        {"label": "Todos", "value": ""},
                        {"label": "ZPP Produção", "value": "zppprd"},
                        {"label": "ZPP Paradas", "value": "zppparadas"},
                    ],
                    value="",
                ),
            ], md=3),
            dbc.Col([
                dbc.Label("Canal", className="small"),
                dbc.Select(
                    id="filter-canal-logs",
                    options=[
                        {"label": "Todos", "value": ""},
                        {"label": "Padrão", "value": "padrao"},
                        {"label": "Retroativo", "value": "retroativo"},
                    ],
                    value="",
                ),
            ], md=3),
            dbc.Col([
                dbc.Label("Status", className="small"),
                dbc.Select(
                    id="filter-status-logs",
                    options=[
                        {"label": "Todos", "value": ""},
                        {"label": "Sucesso", "value": "success"},
                        {"label": "Rejeitado", "value": "rejected"},
                        {"label": "Erro", "value": "failed"},
                    ],
                    value="",
                ),
            ], md=3),
            dbc.Col([
                dbc.Label("Mês (AAAA-MM)", className="small"),
                dbc.Input(
                    id="filter-mes-logs",
                    type="month",
                    debounce=True,
                ),
            ], md=3),
        ], className="mb-3 g-2"),

        # Tabela
        html.Div(id="tabela-logs-zpp-container", children=[
            dbc.Spinner(color="primary", size="sm"),
        ]),

        # Paginação
        html.Div(id="paginacao-logs-zpp", className="d-flex justify-content-center mt-3"),

        # Store de página atual
        dcc.Store(id="store-logs-page", data=1),
    ]))


def layout():
    """Layout da página ZPP — restrito a nível 3+."""
    if not current_user.is_authenticated or current_user.level < 3:
        return html.Div()

    return dbc.Container([
        # Header
        dbc.Row([
            dbc.Col([
                html.H2([
                    html.I(className="bi bi-file-earmark-spreadsheet me-3",
                           style={"color": "#0d6efd"}),
                    "Processamento de Planilhas ZPP",
                ], className="mb-1"),
                html.P("Processamento automático de planilhas SAP (Produção e Paradas)",
                       className="text-muted"),
            ]),
        ], className="mb-4"),

        # Cards de arquivos pendentes / processados
        dbc.Row([
            dbc.Col(create_file_list_card("input"),  md=6, className="mb-3"),
            dbc.Col(create_file_list_card("output"), md=6, className="mb-3"),
        ], className="g-3 mb-4"),

        # Tabs: Upload Retroativo + Histórico
        dbc.Tabs([
            dbc.Tab(_build_upload_tab(), label="Upload Retroativo",
                    tab_id="tab-upload-retroativo"),
            dbc.Tab(_build_logs_tab(),   label="Histórico de Logs",
                    tab_id="tab-historico-logs"),
        ], id="zpp-tabs", active_tab="tab-upload-retroativo", className="mb-3"),

        # Modal de detalhe de log
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="modal-log-title")),
            dbc.ModalBody(id="modal-log-body"),
            dbc.ModalFooter(
                dbc.Button("Fechar", id="btn-fechar-modal-log", color="secondary", size="sm")
            ),
        ], id="modal-detalhe-log", size="lg", scrollable=True),

    ], fluid=True, className="p-4")
