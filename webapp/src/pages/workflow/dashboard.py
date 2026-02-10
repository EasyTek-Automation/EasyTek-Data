"""
Dashboard de Pendências - Página principal do módulo Workflow.

Exibe pendências em formato de tabela expansível, onde cada linha pode ser expandida
para revelar o histórico detalhado dessa pendência.
"""

import os
import pandas as pd
from dash import html, dcc
import dash_bootstrap_components as dbc
from datetime import datetime


# ======================================================================================
# CARREGAMENTO DE DADOS
# ======================================================================================

def carregar_dados_csv():
    """
    Carrega os dados de pendências e histórico dos arquivos CSV.

    Returns:
        tuple: (df_pendencias, df_historico) ou (None, None) em caso de erro
    """
    try:
        # Definir caminhos dos arquivos
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        caminho_pendencias = os.path.join(base_dir, "data", "workflow_pendencias.csv")
        caminho_historico = os.path.join(base_dir, "data", "workflow_historico.csv")

        # Carregar CSVs
        df_pendencias = pd.read_csv(caminho_pendencias)
        df_historico = pd.read_csv(caminho_historico)

        # Converter datas
        df_pendencias['data_criacao'] = pd.to_datetime(df_pendencias['data_criacao'])
        df_pendencias['ultima_atualizacao'] = pd.to_datetime(df_pendencias['ultima_atualizacao'])
        df_historico['data'] = pd.to_datetime(df_historico['data'])

        return df_pendencias, df_historico

    except Exception as e:
        print(f"Erro ao carregar dados CSV: {e}")
        return None, None


# ======================================================================================
# COMPONENTES DE UI
# ======================================================================================

def criar_badge_status(status):
    """
    Cria um badge colorido para o status.

    Args:
        status: Status da pendência (Pendente, Em Andamento, Bloqueado, Concluído)

    Returns:
        dbc.Badge: Badge com cor apropriada
    """
    cores = {
        "Pendente": "warning",
        "Em Andamento": "primary",
        "Bloqueado": "danger",
        "Concluído": "success"
    }

    return dbc.Badge(status, color=cores.get(status, "secondary"), className="ms-2")


def criar_cards_kpi(df_pendencias):
    """
    Cria os 4 cards KPI com estatísticas das pendências.

    Args:
        df_pendencias: DataFrame com as pendências

    Returns:
        dbc.Row: Linha com os 4 cards KPI
    """
    if df_pendencias is None or df_pendencias.empty:
        total = pendentes = em_andamento = concluidas = 0
    else:
        total = len(df_pendencias)
        pendentes = len(df_pendencias[df_pendencias['status'] == 'Pendente'])
        em_andamento = len(df_pendencias[df_pendencias['status'] == 'Em Andamento'])
        concluidas = len(df_pendencias[df_pendencias['status'] == 'Concluído'])

    cards = dbc.Row([
        # Card Total
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Total de Pendências", className="text-muted mb-2"),
                    html.H3(str(total), className="mb-0")
                ])
            ], className="shadow-sm")
        ], width=12, lg=3, className="mb-3"),

        # Card Pendentes
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Pendentes", className="text-muted mb-2"),
                    html.H3(str(pendentes), className="mb-0 text-warning")
                ])
            ], className="shadow-sm")
        ], width=12, lg=3, className="mb-3"),

        # Card Em Andamento
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Em Andamento", className="text-muted mb-2"),
                    html.H3(str(em_andamento), className="mb-0 text-primary")
                ])
            ], className="shadow-sm")
        ], width=12, lg=3, className="mb-3"),

        # Card Concluídas
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Concluídas", className="text-muted mb-2"),
                    html.H3(str(concluidas), className="mb-0 text-success")
                ])
            ], className="shadow-sm")
        ], width=12, lg=3, className="mb-3"),
    ], className="mb-4")

    return cards


def criar_painel_filtros():
    """
    Cria o painel de filtros colapsável.

    Returns:
        dbc.Collapse: Painel de filtros
    """
    painel = dbc.Collapse([
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    # Filtro por responsável
                    dbc.Col([
                        html.Label("Responsável:", className="fw-bold mb-2"),
                        dcc.Dropdown(
                            id="filtro-responsavel",
                            options=[
                                {"label": "Todos", "value": "todos"},
                                {"label": "João Silva", "value": "João Silva"},
                                {"label": "Maria Santos", "value": "Maria Santos"},
                                {"label": "Pedro Costa", "value": "Pedro Costa"},
                                {"label": "Ana Oliveira", "value": "Ana Oliveira"},
                                {"label": "Carlos Souza", "value": "Carlos Souza"}
                            ],
                            value="todos",
                            clearable=False
                        )
                    ], width=12, md=4, className="mb-3"),

                    # Filtro por status (multi-select)
                    dbc.Col([
                        html.Label("Status:", className="fw-bold mb-2"),
                        dcc.Dropdown(
                            id="filtro-status",
                            options=[
                                {"label": "Pendente", "value": "Pendente"},
                                {"label": "Em Andamento", "value": "Em Andamento"},
                                {"label": "Bloqueado", "value": "Bloqueado"},
                                {"label": "Concluído", "value": "Concluído"}
                            ],
                            multi=True,
                            placeholder="Todos os status"
                        )
                    ], width=12, md=4, className="mb-3"),

                    # Busca por texto
                    dbc.Col([
                        html.Label("Buscar:", className="fw-bold mb-2"),
                        dbc.Input(
                            id="filtro-busca",
                            type="text",
                            placeholder="ID ou descrição..."
                        )
                    ], width=12, md=4, className="mb-3"),
                ]),

                # Botão Aplicar Filtros
                dbc.Row([
                    dbc.Col([
                        dbc.Button(
                            "Aplicar Filtros",
                            id="btn-aplicar-filtros",
                            color="primary",
                            className="w-100"
                        )
                    ], width=12, md=3)
                ])
            ])
        ], className="shadow-sm mb-4")
    ], id="collapse-filtros", is_open=False)

    return painel


def criar_timeline_historico(historico_items):
    """
    Cria uma timeline visual do histórico da pendência.

    Args:
        historico_items: Lista de dicts com o histórico

    Returns:
        html.Div: Timeline do histórico
    """
    if not historico_items:
        return html.Div("Nenhum histórico disponível.", className="text-muted")

    timeline_items = []

    for i, item in enumerate(historico_items):
        # Última item não tem linha vertical
        is_last = (i == len(historico_items) - 1)

        timeline_items.append(
            html.Div([
                # Coluna esquerda: bolinha + linha
                html.Div([
                    html.Div(className="rounded-circle bg-primary",
                             style={"width": "12px", "height": "12px"}),
                    html.Div(className="bg-secondary" if not is_last else "",
                             style={"width": "2px", "height": "100%", "marginLeft": "5px"} if not is_last else {})
                ], style={"display": "flex", "flexDirection": "column", "alignItems": "center",
                         "marginRight": "15px", "minHeight": "60px"}),

                # Coluna direita: conteúdo
                html.Div([
                    html.Div(item['descricao'], className="fw-bold mb-1"),
                    html.Small([
                        html.Span(item['responsavel'], className="text-muted me-3"),
                        html.Span(item['data'], className="text-muted")
                    ])
                ], style={"flex": "1", "paddingBottom": "20px"})
            ], style={"display": "flex"})
        )

    return html.Div(timeline_items, className="p-3")


def criar_linha_pendencia(pendencia, index):
    """
    Cria duas linhas (<tr>) para cada pendência: linha principal + linha de histórico colapsável.

    Args:
        pendencia: Dict com dados da pendência
        index: Índice da linha (para IDs dinâmicos)

    Returns:
        list: Lista com 2 elementos <tr>
    """
    # Formatar datas
    data_criacao = pendencia['data_criacao'].strftime("%d/%m/%Y")
    ultima_atualizacao = pendencia['ultima_atualizacao'].strftime("%d/%m/%Y")

    # Linha principal
    linha_principal = html.Tr([
        html.Td([
            dbc.Button(
                html.I(className="fas fa-chevron-right", id={"type": "chevron-icon", "index": index}),
                id={"type": "btn-expand", "index": index},
                color="link",
                size="sm",
                className="p-0 text-decoration-none"
            )
        ], style={"width": "40px", "textAlign": "center"}),
        html.Td(pendencia['id']),
        html.Td(pendencia['descricao']),
        html.Td(pendencia['responsavel']),
        html.Td(criar_badge_status(pendencia['status'])),
        html.Td(data_criacao),
        html.Td(ultima_atualizacao)
    ])

    # Linha de histórico (colapsável)
    linha_historico = html.Tr([
        html.Td(
            dbc.Collapse(
                dbc.Card([
                    dbc.CardHeader("Histórico da Pendência", className="fw-bold"),
                    dbc.CardBody(id={"type": "historico-content", "index": index})
                ], className="border-0 shadow-sm"),
                id={"type": "collapse-historico", "index": index},
                is_open=False
            ),
            colSpan=7,
            className="p-0"
        )
    ])

    return [linha_principal, linha_historico]


def criar_tabela_pendencias(df_pendencias):
    """
    Cria a tabela Bootstrap com todas as pendências.

    Args:
        df_pendencias: DataFrame com as pendências

    Returns:
        dbc.Table: Tabela com pendências expansíveis
    """
    if df_pendencias is None or df_pendencias.empty:
        return html.Div([
            html.I(className="fas fa-inbox fa-3x text-muted mb-3"),
            html.H5("Nenhuma pendência encontrada", className="text-muted")
        ], className="text-center py-5")

    # Cabeçalho da tabela
    thead = html.Thead([
        html.Tr([
            html.Th("", style={"width": "40px"}),
            html.Th("ID", style={"width": "100px"}),
            html.Th("Descrição"),
            html.Th("Responsável", style={"width": "150px"}),
            html.Th("Status", style={"width": "150px"}),
            html.Th("Criação", style={"width": "120px"}),
            html.Th("Atualização", style={"width": "120px"})
        ])
    ])

    # Corpo da tabela
    linhas = []
    for index, row in df_pendencias.iterrows():
        pendencia = row.to_dict()
        linhas.extend(criar_linha_pendencia(pendencia, index))

    tbody = html.Tbody(linhas)

    return dbc.Table(
        [thead, tbody],
        bordered=True,
        hover=True,
        responsive=True,
        striped=True,
        className="mb-0"
    )


# ======================================================================================
# LAYOUT PRINCIPAL
# ======================================================================================

def layout():
    """
    Layout principal da página Dashboard de Pendências.

    Returns:
        dbc.Container: Layout completo da página
    """
    # Carregar dados iniciais
    df_pendencias, df_historico = carregar_dados_csv()

    return dbc.Container([
        # Store para cachear histórico
        dcc.Store(id="store-historico", data=df_historico.to_dict('records') if df_historico is not None else []),
        dcc.Store(id="store-pendencias", data=df_pendencias.to_dict('records') if df_pendencias is not None else []),

        # Header
        dbc.Row([
            dbc.Col([
                html.H2([
                    html.I(className="fas fa-project-diagram me-2"),
                    "Dashboard de Pendências"
                ], className="mb-0")
            ], width=12, md=6),

            dbc.Col([
                dbc.ButtonGroup([
                    dbc.Button([
                        html.I(className="fas fa-sync-alt me-2"),
                        "Atualizar"
                    ], id="btn-refresh", color="secondary", outline=True),

                    dbc.Button([
                        html.I(className="fas fa-download me-2"),
                        "Exportar"
                    ], id="btn-export", color="secondary", outline=True, disabled=True),

                    dbc.Button([
                        html.I(className="fas fa-filter me-2"),
                        "Filtros"
                    ], id="btn-toggle-filtros", color="primary", outline=True)
                ], className="w-100")
            ], width=12, md=6, className="text-end")
        ], className="mb-4 align-items-center"),

        # Cards KPI
        criar_cards_kpi(df_pendencias),

        # Painel de Filtros
        criar_painel_filtros(),

        # Tabela de Pendências
        dbc.Card([
            dbc.CardBody([
                html.Div(
                    criar_tabela_pendencias(df_pendencias),
                    id="container-tabela"
                )
            ], className="p-0")
        ], className="shadow-sm")

    ], fluid=True, className="px-4 py-4")
