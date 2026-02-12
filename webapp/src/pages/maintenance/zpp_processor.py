"""
Página de Processamento de Planilhas ZPP
Interface para processamento manual e configuração do serviço
"""
from dash import html, dcc
import dash_bootstrap_components as dbc
from src.components.zpp_processor_components import (
    create_process_button,
    create_file_list_card,
    create_config_panel,
    create_history_table,
    create_log_detail_modal
)


def layout():
    """
    Layout da página de Processamento ZPP

    Estrutura:
    - Header com título e botões
    - Linha 1: Botão processar + Arquivos pendentes + Arquivos processados
    - Linha 2: Painel de configurações (collapsible)
    - Linha 3: Tabela de histórico
    """

    return dbc.Container([
        # ==================== HEADER ====================
        dbc.Row([
            dbc.Col([
                html.H2([
                    html.I(
                        className="bi bi-file-earmark-spreadsheet me-3",
                        style={"color": "#0d6efd"}
                    ),
                    "Processamento de Planilhas ZPP"
                ], className="mb-2"),
                html.P(
                    "Processamento automático de planilhas SAP (Produção e Paradas)",
                    className="text-muted"
                )
            ], width=8),
            dbc.Col([
                dbc.ButtonGroup([
                    dbc.Button(
                        [html.I(className="bi bi-arrow-clockwise me-2"), "Atualizar"],
                        id="btn-refresh-zpp",
                        color="primary",
                        size="sm",
                        outline=True
                    ),
                    dbc.Button(
                        [html.I(className="bi bi-question-circle me-2"), "Ajuda"],
                        id="btn-help-zpp",
                        color="secondary",
                        size="sm",
                        outline=True
                    )
                ])
            ], width=4, className="text-end d-flex align-items-center justify-content-end")
        ], className="mb-4"),

        # ==================== LINHA 1: PROCESSAMENTO E ARQUIVOS ====================
        dbc.Row([
            # Botão de processamento
            dbc.Col([
                create_process_button()
            ], xs=12, md=4, className="mb-3"),

            # Arquivos pendentes
            dbc.Col([
                create_file_list_card("input")
            ], xs=12, md=4, className="mb-3"),

            # Arquivos processados
            dbc.Col([
                create_file_list_card("output")
            ], xs=12, md=4, className="mb-3")
        ], className="g-3 mb-4"),

        # ==================== LINHA 2: CONFIGURAÇÕES ====================
        dbc.Row([
            dbc.Col([
                create_config_panel()
            ], width=12)
        ]),

        # ==================== LINHA 3: HISTÓRICO ====================
        dbc.Row([
            dbc.Col([
                create_history_table()
            ], width=12)
        ]),

        # ==================== STORES E INTERVALS ====================
        # Store para job_id em processamento
        dcc.Store(id='store-zpp-job-id', data=None),

        # Store para configuração atual
        dcc.Store(id='store-zpp-config', data=None),

        # Interval para polling de status (apenas quando processando)
        dcc.Interval(
            id='interval-zpp-status',
            interval=2000,  # 2 segundos
            n_intervals=0,
            disabled=True  # Inicia desabilitado
        ),

        # Interval para refresh de arquivos e histórico
        dcc.Interval(
            id='interval-zpp-refresh',
            interval=10000,  # 10 segundos
            n_intervals=0,
            disabled=False
        ),

        # Interval para auto-load inicial
        dcc.Interval(
            id='interval-zpp-autoload',
            interval=500,  # 0.5 segundo
            n_intervals=0,
            max_intervals=1  # Executa apenas 1 vez
        ),

        # ==================== MODAL DE DETALHES ====================
        create_log_detail_modal(),

        # ==================== TOAST DE AJUDA ====================
        dbc.Toast(
            [
                html.P([
                    html.Strong("Como usar:"), html.Br(),
                    "1. Coloque arquivos .xlsx na pasta ", html.Code("volumes/zpp/input/"), html.Br(),
                    "2. Clique em 'Processar Agora' ou aguarde processamento automático", html.Br(),
                    "3. Arquivos processados são movidos para ", html.Code("volumes/zpp/output/"), html.Br(),
                    html.Br(),
                    html.Strong("Tipos suportados:"), html.Br(),
                    "• ZPP PRD (Produção)", html.Br(),
                    "• ZPP Paradas", html.Br(),
                    html.Br(),
                    html.Small("O tipo é detectado automaticamente pela estrutura das colunas", className="text-muted")
                ]),
            ],
            id="toast-help-zpp",
            header="Ajuda - Processamento ZPP",
            is_open=False,
            dismissable=True,
            icon="info",
            duration=10000,
            style={"position": "fixed", "top": 80, "right": 10, "width": 400, "zIndex": 9999}
        ),

        # ==================== TOAST DE NOTIFICAÇÕES ====================
        dbc.Toast(
            id="toast-notification-zpp",
            header="Notificação",
            is_open=False,
            dismissable=True,
            duration=4000,
            icon="success",
            style={"position": "fixed", "top": 80, "right": 10, "width": 350, "zIndex": 9999}
        )

    ], fluid=True, className="p-4")
