"""
Workflow Dashboard - Página principal do módulo Workflow.

Exibe pendências em formato de tabela expansível, onde cada linha pode ser expandida
para revelar o histórico detalhado dessa pendência com suporte a horas, aprovação
e marcação de subatividades como concluídas.
"""

import pandas as pd
from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from flask_login import current_user

from src.components.workflow.create_modal import create_pendencia_modal
from src.components.workflow.edit_modal import edit_pendencia_modal, delete_confirm_modal


# ======================================================================================
# CARREGAMENTO DE DADOS
# ======================================================================================

def carregar_dados_csv():
    """
    Carrega os dados de pendências e histórico do MongoDB.

    Returns:
        tuple: (df_pendencias, df_historico) ou (None, None) em caso de erro
    """
    try:
        from src.utils.workflow_db import carregar_pendencias, carregar_historico

        df_pendencias = carregar_pendencias()
        df_historico = carregar_historico()

        # Ajustar nome da coluna no histórico (para compatibilidade com código existente)
        if 'MaintenanceWF_id' in df_historico.columns:
            df_historico['pendencia_id'] = df_historico['MaintenanceWF_id']

        return df_pendencias, df_historico

    except Exception as e:
        print(f"Erro ao carregar dados do MongoDB: {e}")
        return None, None


# ======================================================================================
# COMPONENTES DE UI
# ======================================================================================

def criar_badge_status(status):
    """Cria um badge colorido para o status."""
    cores = {
        "Pendente": "warning",
        "Em Andamento": "primary",
        "Bloqueado": "danger",
        "Concluído": "success"
    }
    return dbc.Badge(status, color=cores.get(status, "secondary"), className="ms-2")


def criar_grafico_horas(historico_items):
    """
    Cria gráfico de barras horizontal mostrando distribuição de horas por subatividade.

    Args:
        historico_items: Lista de dicts com dados do histórico

    Returns:
        dcc.Graph ou None se não houver horas registradas
    """
    items_com_horas = [
        item for item in historico_items
        if item.get('horas') is not None and item['horas'] > 0
    ]

    if not items_com_horas:
        return None

    # Truncar descrições longas para o eixo Y
    labels = []
    for item in items_com_horas:
        desc = item['descricao']
        if len(desc) > 30:
            desc = desc[:27] + "..."
        labels.append(desc)

    horas = [item['horas'] for item in items_com_horas]
    total = sum(horas)

    # Cores baseadas no status de conclusão
    cores = []
    for item in items_com_horas:
        if item.get('concluido'):
            cores.append('#28a745')  # verde
        elif item.get('status_aprovacao') == 'pendente':
            cores.append('#ffc107')  # amarelo
        elif item.get('status_aprovacao') == 'rejeitado':
            cores.append('#dc3545')  # vermelho
        else:
            cores.append('#007bff')  # azul

    fig = go.Figure(go.Bar(
        x=horas,
        y=labels,
        orientation='h',
        marker_color=cores,
        text=[f"{h}h ({h/total*100:.0f}%)" for h in horas],
        textposition='outside',
        hovertemplate="<b>%{y}</b><br>%{x}h<extra></extra>"
    ))

    fig.update_layout(
        height=max(120, len(items_com_horas) * 40 + 60),
        margin=dict(l=10, r=60, t=30, b=10),
        xaxis=dict(title="Horas", showgrid=True),
        yaxis=dict(showgrid=False),
        title=dict(
            text=f"Distribuição de Horas — Total: {total}h",
            font=dict(size=13),
            x=0
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        showlegend=False
    )

    return dcc.Graph(
        figure=fig,
        config={"displayModeBar": False},
        className="mb-3"
    )


def criar_cards_kpi(df_pendencias, df_historico=None, username_atual=None):
    """
    Cria os cards KPI com estatísticas das pendências.

    Args:
        df_pendencias: DataFrame com as pendências
        df_historico: DataFrame com o histórico (para calcular aprovações pendentes)
        username_atual: Username do usuário logado

    Returns:
        dbc.Row: Linha com os cards KPI
    """
    if df_pendencias is None or df_pendencias.empty:
        total = pendentes = em_andamento = concluidas = 0
    else:
        total = len(df_pendencias)
        pendentes = len(df_pendencias[df_pendencias['status'] == 'Pendente'])
        em_andamento = len(df_pendencias[df_pendencias['status'] == 'Em Andamento'])
        concluidas = len(df_pendencias[df_pendencias['status'] == 'Concluído'])

    # Calcular aprovações pendentes para o usuário atual
    aguardando_aprovacao = 0
    if df_historico is not None and not df_historico.empty and username_atual:
        if 'aprovador' in df_historico.columns and 'status_aprovacao' in df_historico.columns:
            mask = (
                (df_historico['aprovador'] == username_atual) &
                (df_historico['status_aprovacao'] == 'pendente')
            )
            aguardando_aprovacao = int(mask.sum())

    cards = dbc.Row([
        # Card Total
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Total de Workflows", className="text-muted mb-2"),
                    html.H3(str(total), className="mb-0")
                ])
            ], className="shadow-sm")
        ], width=12, lg=True, className="mb-3"),

        # Card Pendentes
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Pendentes", className="text-muted mb-2"),
                    html.H3(str(pendentes), className="mb-0 text-warning")
                ])
            ], className="shadow-sm")
        ], width=12, lg=True, className="mb-3"),

        # Card Em Andamento
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Em Andamento", className="text-muted mb-2"),
                    html.H3(str(em_andamento), className="mb-0 text-primary")
                ])
            ], className="shadow-sm")
        ], width=12, lg=True, className="mb-3"),

        # Card Concluídas
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Concluídas", className="text-muted mb-2"),
                    html.H3(str(concluidas), className="mb-0 text-success")
                ])
            ], className="shadow-sm")
        ], width=12, lg=True, className="mb-3"),

        # Card Aguardando Minha Aprovação
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6([
                        html.I(className="fas fa-clock me-1"),
                        "Aguard. Aprovação"
                    ], className="text-muted mb-2"),
                    html.H3(
                        str(aguardando_aprovacao),
                        className="mb-0 text-warning" if aguardando_aprovacao > 0 else "mb-0"
                    )
                ])
            ], className="shadow-sm border-warning" if aguardando_aprovacao > 0 else "shadow-sm")
        ], width=12, lg=True, className="mb-3"),
    ], className="mb-4")

    return cards


def criar_painel_filtros():
    """Cria o painel de filtros sempre visível."""
    return dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.Label("Responsável:", className="fw-bold mb-2"),
                    dcc.Dropdown(
                        id="filtro-responsavel",
                        options=[{"label": "Todos", "value": "todos"}],
                        value="todos",
                        clearable=False
                    )
                ], width=12, md=4, className="mb-3"),

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

                dbc.Col([
                    html.Label("Buscar:", className="fw-bold mb-2"),
                    dbc.Input(
                        id="filtro-busca",
                        type="text",
                        placeholder="ID ou descrição..."
                    )
                ], width=12, md=4, className="mb-3"),
            ]),
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


def criar_timeline_historico(historico_items, username_atual=None):
    """
    Cria uma timeline visual do histórico da pendência.

    Args:
        historico_items: Lista de dicts com o histórico
        username_atual: Username do usuário logado (para mostrar botões de aprovação)

    Returns:
        html.Div: Timeline do histórico
    """
    if not historico_items:
        return html.Div("Nenhum histórico disponível.", className="text-muted")

    timeline_items = []

    for i, item in enumerate(historico_items):
        is_last = (i == len(historico_items) - 1)
        concluido = item.get('concluido', False)
        hist_id = item.get('hist_id', '')
        horas = item.get('horas')
        aprovador = item.get('aprovador')
        status_aprovacao = item.get('status_aprovacao')

        # Estilo geral do item (opacidade reduzida se concluído)
        item_style = {"opacity": "0.6"} if concluido else {}

        # --- Badges de status ---
        badges = []

        if concluido:
            badges.append(dbc.Badge("Concluída", color="success", className="me-1"))
        else:
            badges.append(dbc.Badge("Pendente", color="secondary", className="me-1 opacity-50"))

        if horas is not None and horas > 0:
            badges.append(dbc.Badge(
                [html.I(className="fas fa-clock me-1"), f"{horas}h"],
                color="info",
                className="me-1"
            ))

        if status_aprovacao == 'pendente':
            badges.append(dbc.Badge("Aguardando Aprovação", color="warning", className="me-1"))
        elif status_aprovacao == 'aprovado':
            badges.append(dbc.Badge("Aprovado", color="success", className="me-1"))
        elif status_aprovacao == 'rejeitado':
            badges.append(dbc.Badge("Rejeitado", color="danger", className="me-1"))

        # --- Observações ---
        observacoes_content = None
        if item.get('observacoes') and item['observacoes'].strip():
            observacoes_content = dbc.Card([
                dbc.CardBody([
                    html.I(className="fas fa-comment-dots me-2 text-muted"),
                    html.Span(
                        item['observacoes'],
                        className="text-dark",
                        style={"whiteSpace": "pre-line"}
                    )
                ], className="py-2 px-3")
            ], className="mb-2 shadow-sm", style={
                "backgroundColor": "#f8f9fa",
                "borderLeft": "4px solid #007bff",
                "borderRadius": "8px"
            })

        # --- Log de alterações ---
        alteracoes_content = None
        if item.get('alteracoes') and item['alteracoes'].strip():
            alteracoes_content = html.Div([
                html.I(className="fas fa-edit me-2 text-info", style={"fontSize": "0.98rem"}),
                html.Span(item['alteracoes'], className="text-muted", style={"fontSize": "1.035rem"})
            ], className="mb-2")

        # --- Botões de ação ---
        botoes = []

        # Botão "Marcar como Concluída" (apenas se não concluído e tem hist_id válido)
        if not concluido and hist_id:
            botoes.append(
                dbc.Button(
                    [html.I(className="fas fa-check-circle me-1"), "Concluir"],
                    id={"type": "btn-concluir-subtarefa", "index": hist_id},
                    color="success",
                    size="sm",
                    outline=True,
                    className="me-1 mt-2"
                )
            )

        # Botões Aprovar / Rejeitar (apenas para o aprovador designado, se pendente)
        if (status_aprovacao == 'pendente' and aprovador and
                username_atual and username_atual == aprovador and hist_id):
            botoes.append(
                dbc.Button(
                    [html.I(className="fas fa-thumbs-up me-1"), "Aprovar"],
                    id={"type": "btn-aprovar", "index": hist_id},
                    color="success",
                    size="sm",
                    className="me-1 mt-2"
                )
            )
            botoes.append(
                dbc.Button(
                    [html.I(className="fas fa-thumbs-down me-1"), "Rejeitar"],
                    id={"type": "btn-rejeitar", "index": hist_id},
                    color="danger",
                    size="sm",
                    className="mt-2"
                )
            )

        # Cor da bolinha baseada no status
        bolinha_cor = "bg-success" if concluido else "bg-primary"
        if status_aprovacao == 'pendente':
            bolinha_cor = "bg-warning"
        elif status_aprovacao == 'rejeitado':
            bolinha_cor = "bg-danger"

        timeline_items.append(
            html.Div([
                # Coluna esquerda: bolinha + linha
                html.Div([
                    html.Div(
                        className=f"rounded-circle {bolinha_cor}",
                        style={"width": "12px", "height": "12px", "flexShrink": "0"}
                    ),
                    html.Div(
                        className="bg-secondary" if not is_last else "",
                        style={"width": "2px", "height": "100%"} if not is_last else {}
                    )
                ], style={
                    "display": "flex", "flexDirection": "column", "alignItems": "center",
                    "marginRight": "15px", "minHeight": "80px", "width": "12px"
                }),

                # Coluna direita: conteúdo
                html.Div([
                    # Título + badges
                    html.Div([
                        html.Span(item['descricao'], className="fw-bold me-2",
                                  style={"fontSize": "1.05rem",
                                         "textDecoration": "line-through" if concluido else "none"}),
                        *badges
                    ], className="mb-2 d-flex flex-wrap align-items-center"),

                    observacoes_content if observacoes_content else html.Div(),
                    alteracoes_content if alteracoes_content else html.Div(),

                    # Info do responsável, aprovador e data
                    html.Small([
                        html.Span(item.get('editado_por', item['responsavel']),
                                  className="text-muted me-3"),
                        html.Span(item['data'], className="text-muted me-3"),
                        (html.Span([
                            html.I(className="fas fa-user-check me-1 text-warning"),
                            f"Aprovador: {aprovador}"
                        ], className="text-muted") if aprovador else html.Span())
                    ]),

                    # Botões de ação
                    html.Div(botoes) if botoes else html.Div()

                ], style={"flex": "1", "paddingBottom": "25px", **item_style})
            ], style={"display": "flex"})
        )

    return html.Div(timeline_items, className="p-3")


def criar_linha_pendencia(pendencia, index, historico_pendencia=None):
    """
    Cria duas linhas (<tr>) para cada pendência: linha principal + linha de histórico colapsável.

    Args:
        pendencia: Dict com dados da pendência
        index: Índice da linha (para IDs dinâmicos)
        historico_pendencia: Lista de dicts do histórico desta pendência (para calcular horas/badges)

    Returns:
        list: Lista com 2 elementos <tr>
    """
    data_criacao = pendencia['data_criacao'].strftime("%d/%m/%Y")
    ultima_atualizacao = pendencia['ultima_atualizacao'].strftime("%d/%m/%Y")

    # Calcular total de horas das subatividades
    total_horas = None
    tem_aprovacao_pendente = False

    if historico_pendencia:
        horas_lista = []
        for item in historico_pendencia:
            h = item.get('horas')
            try:
                if h is not None and str(h) != 'nan' and float(h) > 0:
                    horas_lista.append(float(h))
            except (ValueError, TypeError):
                pass
        if horas_lista:
            total_horas = sum(horas_lista)

        tem_aprovacao_pendente = any(
            str(item.get('status_aprovacao', '') or '') == 'pendente'
            for item in historico_pendencia
        )

    # Badges extras na linha principal
    badges_linha = []
    if total_horas is not None:
        badges_linha.append(dbc.Badge(
            [html.I(className="fas fa-clock me-1"), f"{total_horas}h"],
            color="info",
            className="ms-2",
            title=f"Total de horas registradas: {total_horas}h"
        ))
    if tem_aprovacao_pendente:
        badges_linha.append(dbc.Badge(
            [html.I(className="fas fa-hourglass-half me-1"), "Aguard. Aprov."],
            color="warning",
            className="ms-2"
        ))

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
        html.Td([pendencia['descricao'], *badges_linha]),
        html.Td(pendencia['responsavel']),
        html.Td(criar_badge_status(pendencia['status'])),
        html.Td(data_criacao),
        html.Td(ultima_atualizacao),
        html.Td([
            dbc.Button(
                html.I(className="fas fa-edit"),
                id={"type": "btn-edit-pend", "index": pendencia['id']},
                color="info",
                size="sm",
                outline=True
            )
        ], style={"width": "60px", "textAlign": "center"})
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
            colSpan=8,
            className="p-0"
        )
    ])

    return [linha_principal, linha_historico]


def criar_tabela_pendencias(df_pendencias, df_historico=None):
    """
    Cria a tabela Bootstrap com todas as pendências.

    Args:
        df_pendencias: DataFrame com as pendências
        df_historico: DataFrame com o histórico (para badges de horas e aprovação)

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
            html.Th("Atualização", style={"width": "120px"}),
            html.Th("Ações", style={"width": "60px"})
        ])
    ])

    linhas = []
    for index, row in df_pendencias.iterrows():
        pendencia = row.to_dict()

        # Filtrar histórico desta pendência
        hist_items = None
        if df_historico is not None and not df_historico.empty:
            col_id = 'pendencia_id' if 'pendencia_id' in df_historico.columns else 'MaintenanceWF_id'
            hist_df = df_historico[df_historico[col_id] == pendencia['id']]
            if not hist_df.empty:
                hist_items = hist_df.to_dict('records')

        linhas.extend(criar_linha_pendencia(pendencia, index, hist_items))

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
# MODAIS AUXILIARES
# ======================================================================================

def concluir_subtarefa_modal():
    """Modal de confirmação para marcar subatividade como concluída."""
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle([
            html.I(className="fas fa-check-circle me-2 text-success"),
            "Confirmar Conclusão"
        ])),
        dbc.ModalBody([
            html.P([
                "Deseja marcar esta subatividade como ",
                html.Strong("concluída", className="text-success"),
                "?"
            ]),
            html.P([
                "Esta ação é ",
                html.Strong("irreversível", className="text-danger"),
                ". Para desfazer, será necessário criar uma nova entrada."
            ], className="text-muted small")
        ]),
        dbc.ModalFooter([
            dbc.Button(
                "Cancelar",
                id="concluir-subtarefa-cancel-btn",
                color="secondary",
                outline=True,
                className="me-2"
            ),
            dbc.Button(
                [html.I(className="fas fa-check-circle me-2"), "Sim, Concluir"],
                id="concluir-subtarefa-confirm-btn",
                color="success"
            )
        ])
    ], id="concluir-subtarefa-modal", is_open=False, centered=True)


# ======================================================================================
# LAYOUT PRINCIPAL
# ======================================================================================

def layout():
    """
    Layout principal da página Workflow Dashboard.

    Returns:
        dbc.Container: Layout completo da página
    """
    df_pendencias, df_historico = carregar_dados_csv()

    username_atual = current_user.username if current_user.is_authenticated else ""

    return dbc.Container([
        # Stores para cachear dados
        dcc.Store(id="store-historico", data=df_historico.to_dict('records') if df_historico is not None else []),
        dcc.Store(id="store-pendencias", data=df_pendencias.to_dict('records') if df_pendencias is not None else []),

        # Stores para contexto do usuário (RBAC)
        dcc.Store(id="user-level-store", data=current_user.level if current_user.is_authenticated else 1),
        dcc.Store(id="user-perfil-store", data=current_user.perfil if current_user.is_authenticated else ""),
        dcc.Store(id="user-username-store", data=username_atual),

        # Store para hist_id pendente de confirmação de conclusão
        dcc.Store(id="store-subtarefa-concluir-pending"),

        # Modais
        create_pendencia_modal(),
        edit_pendencia_modal(),
        delete_confirm_modal(),
        concluir_subtarefa_modal(),

        # Header
        dbc.Row([
            dbc.Col([
                html.H2([
                    html.I(className="fas fa-project-diagram me-2"),
                    "Workflow Dashboard"
                ], className="mb-0")
            ], width=12, md=6),

            dbc.Col([
                dbc.ButtonGroup([
                    dbc.Button([
                        html.I(className="fas fa-plus-circle me-2"),
                        "Novo Workflow"
                    ], id="btn-nova-pendencia", color="success", outline=True,
                       style={"display": "inline-block" if current_user.is_authenticated and current_user.level == 3 else "none"}),

                    dbc.Button([
                        html.I(className="fas fa-sync-alt me-2"),
                        "Atualizar"
                    ], id="btn-refresh", color="secondary", outline=True),

                    dbc.Button([
                        html.I(className="fas fa-download me-2"),
                        "Exportar"
                    ], id="btn-export", color="secondary", outline=True, disabled=True)
                ], className="w-100")
            ], width=12, md=6, className="text-end")
        ], className="mb-4 align-items-center"),

        # Container de Alertas
        html.Div(id="alert-container-workflow", className="mb-3"),

        # Cards KPI
        html.Div(
            criar_cards_kpi(df_pendencias, df_historico, username_atual),
            id="container-cards-kpi"
        ),

        # Painel de Filtros
        criar_painel_filtros(),

        # Tabela de Pendências
        dbc.Card([
            dbc.CardBody([
                html.Div(
                    criar_tabela_pendencias(df_pendencias, df_historico),
                    id="container-tabela"
                )
            ], className="p-0")
        ], className="shadow-sm")

    ], fluid=True, className="px-4 py-4")
