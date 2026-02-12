"""
Componentes UI para a página de Processamento ZPP
"""
from dash import html, dcc
import dash_bootstrap_components as dbc
from datetime import datetime


def create_process_button():
    """
    Botão principal de processamento com spinner
    """
    return dbc.Card([
        dbc.CardHeader([
            html.I(className="bi bi-play-circle me-2"),
            "Processamento Manual"
        ], className="bg-primary text-white"),
        dbc.CardBody([
            html.P(
                "Clique no botão abaixo para iniciar o processamento das planilhas pendentes.",
                className="text-muted mb-3"
            ),
            dbc.Button(
                [
                    dbc.Spinner(
                        size="sm",
                        id="spinner-process",
                        children=html.Span(id="process-button-content", children=[
                            html.I(className="bi bi-play-fill me-2"),
                            "Processar Agora"
                        ])
                    )
                ],
                id="btn-process-zpp",
                color="success",
                size="lg",
                className="w-100",
                disabled=False
            ),
            # Status do processamento
            html.Div(id="process-status", className="mt-3")
        ])
    ], className="mb-3 shadow-sm")


def create_file_list_card(folder_type: str):
    """
    Card com lista de arquivos (pendentes ou processados)

    Args:
        folder_type: "input" ou "output"
    """
    is_input = folder_type == "input"

    icon = "bi-file-earmark-spreadsheet" if is_input else "bi-archive"
    title = "Arquivos Pendentes" if is_input else "Arquivos Processados"
    color = "warning" if is_input else "success"
    card_id = "card-files-input" if is_input else "card-files-output"
    list_id = "list-files-input" if is_input else "list-files-output"

    return dbc.Card([
        dbc.CardHeader([
            html.I(className=f"{icon} me-2"),
            title
        ], className=f"bg-{color} text-white"),
        dbc.CardBody([
            # Badge com contador
            dbc.Badge(
                "0 arquivos",
                id=f"badge-count-{folder_type}",
                color="secondary",
                className="mb-2"
            ),
            # Lista de arquivos
            html.Div(
                id=list_id,
                children=[
                    html.P(
                        "Nenhum arquivo encontrado",
                        className="text-muted text-center my-4"
                    )
                ],
                style={"maxHeight": "250px", "overflowY": "auto"}
            )
        ], id=card_id)
    ], className="mb-3 shadow-sm")


def create_config_panel():
    """
    Painel collapsible de configurações
    """
    return dbc.Card([
        dbc.CardHeader([
            dbc.Button(
                [
                    html.I(className="bi bi-gear me-2"),
                    "Configurações do Processamento Automático"
                ],
                id="collapse-config-button",
                color="link",
                className="text-decoration-none w-100 text-start p-0"
            )
        ]),
        dbc.Collapse([
            dbc.CardBody([
                # Switch de auto-process
                dbc.Row([
                    dbc.Col([
                        html.Label("Processamento Automático:", className="fw-bold"),
                        html.P(
                            "Ativa o processamento periódico de arquivos na pasta 'input'",
                            className="text-muted small mb-2"
                        )
                    ], width=8),
                    dbc.Col([
                        dbc.Switch(
                            id="switch-auto-process",
                            value=True,
                            className="float-end"
                        )
                    ], width=4)
                ], className="mb-3"),

                # Input de intervalo
                dbc.Row([
                    dbc.Col([
                        html.Label("Intervalo (minutos):", className="fw-bold"),
                        html.P(
                            "Tempo entre cada verificação automática (1-1440 min)",
                            className="text-muted small mb-2"
                        )
                    ], width=8),
                    dbc.Col([
                        dbc.Input(
                            id="input-interval-minutes",
                            type="number",
                            min=1,
                            max=1440,
                            step=1,
                            value=60,
                            size="sm"
                        )
                    ], width=4)
                ], className="mb-3"),

                # Botões de ação
                dbc.Row([
                    dbc.Col([
                        dbc.Button(
                            [html.I(className="bi bi-check-circle me-2"), "Salvar Configurações"],
                            id="btn-save-config",
                            color="primary",
                            size="sm",
                            className="w-100"
                        )
                    ], width=6),
                    dbc.Col([
                        html.Div(id="config-save-status")
                    ], width=6, className="d-flex align-items-center")
                ])
            ])
        ], id="collapse-config", is_open=False)
    ], className="mb-4 shadow-sm")


def create_history_table():
    """
    Tabela de histórico de processamentos
    """
    return dbc.Card([
        dbc.CardHeader([
            html.I(className="bi bi-clock-history me-2"),
            "Histórico de Processamentos"
        ]),
        dbc.CardBody([
            # Placeholder inicial
            html.Div(
                id="history-table-container",
                children=[
                    html.P(
                        "Carregando histórico...",
                        className="text-muted text-center my-4"
                    )
                ]
            )
        ])
    ], className="shadow-sm")


def create_file_item(filename: str, size_mb: float, modified_at: str):
    """
    Cria um item de arquivo para a lista

    Args:
        filename: Nome do arquivo
        size_mb: Tamanho em MB
        modified_at: Data de modificação (ISO string)
    """
    try:
        # Formatar data
        dt = datetime.fromisoformat(modified_at)
        date_str = dt.strftime("%d/%m/%Y %H:%M")
    except:
        date_str = modified_at

    return dbc.ListGroupItem([
        dbc.Row([
            dbc.Col([
                html.I(className="bi bi-file-earmark-excel text-success me-2"),
                html.Span(filename, className="fw-bold")
            ], width=8),
            dbc.Col([
                dbc.Badge(f"{size_mb} MB", color="light", text_color="dark", className="me-2"),
            ], width=4, className="text-end")
        ]),
        html.Small(date_str, className="text-muted")
    ], className="py-2")


def create_history_row(log: dict):
    """
    Cria uma linha da tabela de histórico

    Args:
        log: Dicionário com dados do log
    """
    # Status badge
    status = log.get('status', 'unknown')
    if status == 'success':
        badge = dbc.Badge("Sucesso", color="success", className="me-2")
        icon = html.I(className="bi bi-check-circle text-success me-2")
    elif status == 'failed':
        badge = dbc.Badge("Erro", color="danger", className="me-2")
        icon = html.I(className="bi bi-x-circle text-danger me-2")
    else:  # running
        badge = dbc.Badge("Processando...", color="warning", className="me-2")
        icon = dbc.Spinner(size="sm", className="me-2")

    # Formatar data
    try:
        started = datetime.fromisoformat(log['started_at'])
        date_str = started.strftime("%d/%m/%Y %H:%M")
    except:
        date_str = log.get('started_at', '-')

    # Trigger type
    trigger = log.get('trigger_type', 'manual')
    trigger_badge = dbc.Badge(
        "Manual" if trigger == 'manual' else "Automático",
        color="info" if trigger == 'manual' else "secondary",
        className="me-2"
    )

    # Estatísticas
    summary = log.get('summary', {})
    files = summary.get('total_files', 0)
    records = summary.get('total_uploaded_records', 0)

    duration = log.get('duration_seconds', 0)
    duration_str = f"{int(duration)}s" if duration else "-"

    return html.Tr([
        html.Td([icon, date_str]),
        html.Td(badge),
        html.Td(trigger_badge),
        html.Td(f"{files} arquivo(s)"),
        html.Td(f"{records:,} registros" if records else "-"),
        html.Td(duration_str),
        html.Td([
            dbc.Button(
                html.I(className="bi bi-eye"),
                id={"type": "btn-view-log", "index": log['job_id']},
                color="link",
                size="sm",
                className="p-0"
            )
        ])
    ])


def create_history_table_component(logs: list):
    """
    Cria componente de tabela de histórico completo

    Args:
        logs: Lista de dicionários com logs
    """
    if not logs:
        return html.P(
            "Nenhum processamento registrado ainda",
            className="text-muted text-center my-4"
        )

    return dbc.Table([
        html.Thead([
            html.Tr([
                html.Th("Data/Hora"),
                html.Th("Status"),
                html.Th("Tipo"),
                html.Th("Arquivos"),
                html.Th("Registros"),
                html.Th("Duração"),
                html.Th("Ações")
            ])
        ]),
        html.Tbody([
            create_history_row(log) for log in logs
        ])
    ], bordered=True, hover=True, responsive=True, size="sm")


def create_log_detail_modal():
    """
    Modal para exibir detalhes de um log
    """
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Detalhes do Processamento")),
        dbc.ModalBody(
            id="modal-log-detail-body",
            children="Carregando..."
        ),
        dbc.ModalFooter([
            dbc.Button("Fechar", id="btn-close-log-modal", color="secondary", size="sm")
        ])
    ], id="modal-log-detail", size="lg", is_open=False)
