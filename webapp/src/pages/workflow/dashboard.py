"""
Workflow Dashboard - Página principal do módulo Workflow.

Exibe pendências em formato de tabela expansível, onde cada linha pode ser expandida
para revelar o histórico detalhado dessa pendência com suporte a horas, aprovação
e marcação de subatividades como concluídas.
"""

import pandas as pd
from dash import html, dcc
import dash_bootstrap_components as dbc
from flask_login import current_user

from src.components.workflow.create_modal import create_pendencia_modal
from src.components.workflow.edit_modal import edit_pendencia_modal, delete_confirm_modal
from src.components.workflow.subtask_modals import (
    create_subtask_modal,
    add_log_modal,
    edit_subtask_modal,
    delete_subtask_confirm_modal
)


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

def float_para_hhmm(horas_float):
    """Converte horas decimal para string HH:MM. Ex: 1.5 → '01:30', 2.0 → '02:00'"""
    if horas_float is None:
        return ""
    try:
        horas_float = float(horas_float)
    except (ValueError, TypeError):
        return ""
    horas = int(horas_float)
    minutos = round((horas_float - horas) * 60)
    if minutos >= 60:
        horas += 1
        minutos = 0
    return f"{horas:02d}:{minutos:02d}"


def hhmm_para_float(texto):
    """Converte string HH:MM (ou decimal) para horas float. Ex: '01:30'→1.5, '1,5'→1.5"""
    if not texto:
        return None
    texto = str(texto).strip().replace(',', '.')
    if ':' in texto:
        partes = texto.split(':', 1)
        try:
            h = int(partes[0]) if partes[0].strip() else 0
            m = int(partes[1]) if len(partes) > 1 and partes[1].strip() else 0
            if m > 59:
                return None
            return h + m / 60
        except (ValueError, IndexError):
            return None
    try:
        return float(texto)
    except (ValueError, TypeError):
        return None


def criar_badge_status(status):
    """Cria um badge colorido para o status."""
    cores = {
        "Em Fila (Planejamento)": "info",
        "Pendente": "warning",
        "Em Andamento": "primary",
        "Bloqueado": "danger",
        "Concluído": "success"
    }
    return dbc.Badge(status, color=cores.get(status, "secondary"), className="ms-2")


def criar_barra_horas_inline(historico_items):
    """
    Cria barra segmentada colorida inline com total de horas por tipo de evento.

    Agrupa subatividades pelo mesmo tipo (descricao) e soma as horas.
    Cada tipo de evento recebe uma cor fixa — mesmo tipo = mesma cor.
    Retorna None se nenhuma subatividade tiver horas.

    Args:
        historico_items: Lista de dicts com dados do histórico

    Returns:
        html.Div com barra + legenda, ou None se sem horas
    """
    PALETA = ['primary', 'success', 'info', 'warning', 'danger', 'secondary']

    # Índice de subtarefas por hist_id (para lookup do tipo_evento dos logs)
    subtarefa_por_id = {
        item.get('hist_id'): item
        for item in historico_items
        if item.get('record_type', 'subtarefa') == 'subtarefa'
    }

    # Agrupar por tipo_evento e somar horas (subtarefas + logs, excluindo criacao)
    grupos = {}
    for item in historico_items:
        rt = item.get('record_type', 'subtarefa')
        if rt == 'criacao':
            continue
        h = item.get('horas')
        try:
            if h is not None and str(h) != 'nan' and float(h) > 0:
                if rt == 'log':
                    # Herdar tipo_evento da subtarefa pai
                    parent = subtarefa_por_id.get(item.get('subtarefa_id'))
                    tipo = (parent.get('tipo_evento') if parent else None) or 'Relatório'
                else:
                    tipo = item.get('tipo_evento') or 'Sem Tipo'
                grupos[tipo] = grupos.get(tipo, 0.0) + float(h)
        except (ValueError, TypeError):
            pass

    if not grupos:
        return None

    total = sum(grupos.values())

    # Segmentos da barra — um por tipo, cor determinada pela posição
    bars = []
    legenda = []
    for i, (desc, horas_soma) in enumerate(grupos.items()):
        cor = PALETA[i % len(PALETA)]
        pct = horas_soma / total * 100
        desc_curta = desc if len(desc) <= 20 else desc[:17] + "..."
        horas_fmt = float_para_hhmm(horas_soma)

        bars.append(dbc.Progress(
            value=pct,
            color=cor,
            bar=True,
            label=horas_fmt
        ))
        legenda.append(
            html.Span([
                html.Span("■ ", style={"color": f"var(--bs-{cor})"}),
                f"{desc_curta} {horas_fmt}"
            ], className="me-2", style={"fontSize": "0.70rem", "whiteSpace": "nowrap"})
        )

    return html.Div([
        dbc.Progress(
            bars,
            style={"height": "14px"},
            className="mb-1"
        ),
        html.Div(legenda, className="d-flex flex-wrap")
    ], className="mt-1 mb-1")


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
    pct_subtarefas_geral = None

    if df_pendencias is None or df_pendencias.empty:
        total = em_fila = pendentes = em_andamento = bloqueados = concluidas = 0
        aguardando_aceite = 0
        abertos_por_mim = abertos_aceitos = abertos_rejeitados = 0
    else:
        total = len(df_pendencias)
        em_fila = len(df_pendencias[df_pendencias['status'] == 'Em Fila (Planejamento)'])
        pendentes = len(df_pendencias[df_pendencias['status'] == 'Pendente'])
        em_andamento = len(df_pendencias[df_pendencias['status'] == 'Em Andamento'])
        bloqueados = len(df_pendencias[df_pendencias['status'] == 'Bloqueado'])
        concluidas = len(df_pendencias[df_pendencias['status'] == 'Concluído'])

        # Tarefas aguardando aceite pelo usuário atual (responsável)
        aguardando_aceite = 0
        if username_atual and 'status_aceite' in df_pendencias.columns and 'responsavel' in df_pendencias.columns:
            mask_aceite = (
                (df_pendencias['responsavel'] == username_atual) &
                (df_pendencias['status_aceite'] != 'aceito')
            )
            aguardando_aceite = int(mask_aceite.sum())

        # Tarefas abertas por mim e seus status de aceite
        abertos_por_mim = abertos_aceitos = abertos_rejeitados = 0
        if username_atual and 'criado_por' in df_pendencias.columns:
            mask_meus = df_pendencias['criado_por'] == username_atual
            abertos_por_mim = int(mask_meus.sum())
            if 'status_aceite' in df_pendencias.columns:
                abertos_aceitos = int(
                    (mask_meus & (df_pendencias['status_aceite'] == 'aceito')).sum()
                )
                abertos_rejeitados = int(
                    (mask_meus & (df_pendencias['status_aceite'] == 'rejeitado')).sum()
                )

    # Calcular % geral de subtarefas concluídas (excluindo "Em Fila (Planejamento)")
    if df_historico is not None and not df_historico.empty and df_pendencias is not None and not df_pendencias.empty:
        ids_ativas = set(df_pendencias[
            df_pendencias['status'] != 'Em Fila (Planejamento)'
        ]['id'])
        col_id = 'pendencia_id' if 'pendencia_id' in df_historico.columns else 'MaintenanceWF_id'
        mask_ativas = df_historico[col_id].isin(ids_ativas)
        if 'record_type' in df_historico.columns:
            mask_ativas = mask_ativas & (df_historico['record_type'] == 'subtarefa')
        elif 'tipo_evento' in df_historico.columns:
            mask_ativas = mask_ativas & (df_historico['tipo_evento'] != 'criacao')
        hist_ativas = df_historico[mask_ativas]
        if not hist_ativas.empty:
            total_g = len(hist_ativas)
            conc_g = int(hist_ativas['concluido'].eq(True).sum())
            pct_subtarefas_geral = int(conc_g / total_g * 100)

    # Calcular aprovações pendentes para o usuário atual
    aguardando_aprovacao = 0
    if df_historico is not None and not df_historico.empty and username_atual:
        if 'aprovador' in df_historico.columns and 'status_aprovacao' in df_historico.columns:
            mask = (
                (df_historico['aprovador'] == username_atual) &
                (df_historico['status_aprovacao'] == 'pendente')
            )
            aguardando_aprovacao = int(mask.sum())

    # --- Barra de status compacta (substitui a grade de 4 cards) ---
    def _stat(rotulo, valor, cor=""):
        return html.Div([
            html.Span(
                str(valor),
                className=f"d-block fs-3 fw-bold lh-1{' ' + cor if cor else ''}"
            ),
            html.Small(rotulo, className="text-muted"),
        ], className="text-center px-3 py-1 flex-fill")

    def _vsep():
        return html.Div(style={"width": "1px", "backgroundColor": "#dee2e6", "margin": "4px 0"})

    _pct_label = f"{pct_subtarefas_geral}%" if pct_subtarefas_geral is not None else "—"
    _pct_cor = ("text-success" if pct_subtarefas_geral == 100
                else "text-primary" if pct_subtarefas_geral and pct_subtarefas_geral >= 50
                else "text-warning" if pct_subtarefas_geral is not None
                else "")

    status_strip = dbc.Card(
        dbc.CardBody(
            html.Div([
                _stat("Total", total),
                _vsep(),
                _stat("Em Fila", em_fila, "text-info" if em_fila else ""),
                _vsep(),
                _stat("Pendentes", pendentes, "text-warning" if pendentes else ""),
                _vsep(),
                _stat("Em Andamento", em_andamento, "text-primary" if em_andamento else ""),
                _vsep(),
                _stat("Bloqueados", bloqueados, "text-danger" if bloqueados else ""),
                _vsep(),
                _stat("Concluídas", concluidas, "text-success" if concluidas else ""),
                _vsep(),
                _stat("Subtarefas ✓", _pct_label, _pct_cor),
            ], className="d-flex align-items-center justify-content-around flex-wrap"),
            className="py-2"
        ),
        className="shadow-sm mb-3 workflow-kpi-strip"
    )

    # --- Cards de ação pessoal ---
    def _card(titulo, valor, cor_valor=None, icone=None, borda=None):
        h6_children = []
        if icone:
            h6_children.append(html.I(className=f"{icone} me-1"))
        h6_children.append(titulo)
        return dbc.Card([
            dbc.CardBody([
                html.H6(h6_children, className="text-muted mb-2 small"),
                html.H4(str(valor), className=f"mb-0 {cor_valor}" if cor_valor else "mb-0")
            ])
        ], className=f"shadow-sm h-100{' border-' + borda if borda else ''}")

    cards_pessoais = dbc.Row([
        dbc.Col(_card(
            "Aguard. Aceite", aguardando_aceite,
            icone="fas fa-inbox",
            cor_valor="text-secondary" if aguardando_aceite else None,
            borda="secondary" if aguardando_aceite else None
        ), width=True, className="mb-2"),
        dbc.Col(_card(
            "Aguard. Aprovação", aguardando_aprovacao,
            icone="fas fa-clock",
            cor_valor="text-warning" if aguardando_aprovacao else None,
            borda="warning" if aguardando_aprovacao else None
        ), width=True, className="mb-2"),
        dbc.Col(_card(
            "Abertas por Mim", abertos_por_mim,
            icone="fas fa-folder-open"
        ), width=True, className="mb-2"),
        dbc.Col(_card(
            "Abertas — Aceitas", abertos_aceitos,
            icone="fas fa-check-circle",
            cor_valor="text-success" if abertos_aceitos else None,
            borda="success" if abertos_aceitos else None
        ), width=True, className="mb-2"),
        dbc.Col(_card(
            "Abertas — Rejeitadas", abertos_rejeitados,
            icone="fas fa-times-circle",
            cor_valor="text-danger" if abertos_rejeitados else None,
            borda="danger" if abertos_rejeitados else None
        ), width=True, className="mb-2"),
    ], className="workflow-kpi-cards")

    return html.Div([status_strip, cards_pessoais], className="mb-3")


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
                            {"label": "Em Fila (Planejamento)", "value": "Em Fila (Planejamento)"},
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
                        placeholder="ID, descrição ou nota GAM..."
                    )
                ], width=12, md=4, className="mb-3"),
            ]),
            dbc.Row([
                dbc.Col([
                    html.Label("Aceite:", className="fw-bold mb-2"),
                    dcc.Dropdown(
                        id="filtro-status-aceite",
                        options=[
                            {"label": "Aguard. Aceite", "value": "pendente"},
                            {"label": "Aceito", "value": "aceito"},
                            {"label": "Rejeitado", "value": "rejeitado"},
                        ],
                        multi=True,
                        placeholder="Todos"
                    )
                ], width=12, md=3, className="mb-3"),

                dbc.Col([
                    html.Label("Data de:", className="fw-bold mb-2"),
                    dbc.RadioItems(
                        id="filtro-tipo-data",
                        options=[
                            {"label": "Tarefa", "value": "tarefa"},
                            {"label": "Subtarefa", "value": "subtarefa"},
                        ],
                        value="tarefa",
                        inline=True,
                        className="mt-1"
                    )
                ], width=12, md=2, className="mb-3"),

                dbc.Col([
                    html.Label("De:", className="fw-bold mb-2"),
                    dcc.DatePickerSingle(
                        id="filtro-data-inicio",
                        placeholder="Data inicial",
                        display_format="DD/MM/YYYY",
                        first_day_of_week=0,
                        clearable=True,
                        className="w-100"
                    )
                ], width=12, md=2, className="mb-3"),

                dbc.Col([
                    html.Label("Até:", className="fw-bold mb-2"),
                    dcc.DatePickerSingle(
                        id="filtro-data-fim",
                        placeholder="Data final",
                        display_format="DD/MM/YYYY",
                        first_day_of_week=0,
                        clearable=True,
                        className="w-100"
                    )
                ], width=12, md=2, className="mb-3"),

                dbc.Col([
                    html.Label("\u00a0", className="fw-bold mb-2 d-block"),
                    dbc.ButtonGroup([
                        dbc.Button(
                            "Aplicar Filtros",
                            id="btn-aplicar-filtros",
                            color="primary",
                        ),
                        dbc.Button(
                            [html.I(className="fas fa-times me-1"), "Limpar"],
                            id="btn-limpar-filtros",
                            color="secondary",
                            outline=True,
                        ),
                    ], className="w-100")
                ], width=12, md=3)
            ])
        ])
    ], className="shadow-sm mb-3 workflow-filters")


def criar_timeline_historico(historico_items, username_atual=None, mostrar_botoes=True):
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
                [html.I(className="fas fa-clock me-1"), float_para_hhmm(horas)],
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

        # --- Botões de ação (apenas na aba Subtarefas) ---
        botoes = []
        if mostrar_botoes:
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
                        className="bg-danger" if not is_last else "",
                        style={"width": "2px", "flexGrow": 1, "minHeight": "30px"} if not is_last else {}
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
                        html.Span([
                            html.I(className="fas fa-calendar-alt me-1"),
                            item['data'],
                        ], className="text-warning fw-semibold me-3",
                           title="Data retroativa — informada manualmente")
                        if item.get('is_retroativo') else
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


def criar_linha_pendencia(pendencia, index, historico_pendencia=None,
                          user_level=1, username_atual=None):
    """
    Cria duas linhas (<tr>) para cada pendência: linha principal + linha de histórico colapsável.

    Args:
        pendencia: Dict com dados da pendência
        index: Índice da linha (para IDs dinâmicos)
        historico_pendencia: Lista de dicts do histórico desta pendência
        user_level: Nível do usuário logado (1, 2 ou 3)
        username_atual: Username do usuário logado

    Returns:
        list: Lista com 2 elementos <tr>
    """
    data_criacao = pendencia['data_criacao'].strftime("%d/%m/%Y")
    ultima_atualizacao = pendencia['ultima_atualizacao'].strftime("%d/%m/%Y")

    # Status de aceite e aprovação pendente
    status_aceite = str(pendencia.get('status_aceite') or 'aceito')
    tem_aprovacao_pendente = False

    if historico_pendencia:
        tem_aprovacao_pendente = any(
            str(item.get('status_aprovacao', '') or '') == 'pendente'
            for item in historico_pendencia
        )

    # Barra de horas inline
    barra_horas = None
    if historico_pendencia:
        barra_horas = criar_barra_horas_inline(historico_pendencia)

    # Célula de progresso dedicada (apenas subtarefas, excluindo logs e registros de criação)
    sub_reais = [h for h in (historico_pendencia or [])
                 if h.get('record_type', 'subtarefa') == 'subtarefa']
    if sub_reais:
        total_sub = len(sub_reais)
        concluidas_sub = sum(1 for h in sub_reais if h.get('concluido') is True)
        pct = int(concluidas_sub / total_sub * 100)
        cor_prog = "success" if pct == 100 else "primary" if pct >= 50 else "warning"
        td_progresso = html.Td(
            html.Div([
                dbc.Progress(value=pct, color=cor_prog,
                             style={"height": "8px"}, className="mb-1"),
                html.Small(f"{concluidas_sub}/{total_sub}",
                           className=f"text-{cor_prog} fw-semibold"),
            ], style={"minWidth": "80px"}),
            style={"width": "100px", "verticalAlign": "middle"}
        )
    else:
        td_progresso = html.Td(
            html.Small("—", className="text-muted"),
            style={"width": "100px", "textAlign": "center", "verticalAlign": "middle"}
        )

    # Badge de aprovação pendente (se houver)
    badge_aprov = None
    if tem_aprovacao_pendente:
        badge_aprov = dbc.Badge(
            [html.I(className="fas fa-hourglass-half me-1"), "Aguard. Aprov."],
            color="warning",
            className="ms-2"
        )

    # Badge de aceite pendente
    badge_aceite = None
    if status_aceite == 'pendente':
        badge_aceite = dbc.Badge(
            [html.I(className="fas fa-inbox me-1"), "Aguard. Aceite"],
            color="secondary",
            className="ms-2"
        )
    elif status_aceite == 'rejeitado':
        badge_aceite = dbc.Badge(
            [html.I(className="fas fa-ban me-1"), "Rejeitado"],
            color="danger",
            className="ms-2"
        )

    # Célula de descrição: texto + nota GAM + barra de horas + badges
    nota_gam = pendencia.get('nota_gam') or ''
    desc_content = [pendencia['descricao']]
    if nota_gam:
        desc_content.append(
            dbc.Badge(
                [html.I(className="fas fa-hashtag me-1"), nota_gam],
                color="light",
                className="ms-2 align-middle border border-secondary text-secondary",
                style={"fontSize": "0.75rem", "fontWeight": "500"}
            )
        )
    if badge_aceite:
        desc_content.append(badge_aceite)
    if badge_aprov:
        desc_content.append(badge_aprov)
    if barra_horas:
        desc_content.append(barra_horas)

    # Botões de ação na linha
    pend_id = pendencia['id']
    responsavel = pendencia.get('responsavel', '')
    e_responsavel_atual = (username_atual and responsavel == username_atual)

    _btn_edit = lambda cor="info", disabled=False, titulo=None: dbc.Button(
        html.I(className="fas fa-edit"),
        id={"type": "btn-edit-pend", "index": pend_id},
        color=cor, size="sm", outline=True,
        disabled=disabled,
        title=titulo or ""
    )

    if status_aceite == 'pendente':
        if e_responsavel_atual:
            # Responsável (qualquer nível): aceitar ou rejeitar
            botoes_acao = html.Div([
                dbc.Button(
                    [html.I(className="fas fa-check me-1"), "Aceitar"],
                    id={"type": "btn-aceitar-tarefa", "index": pend_id},
                    color="success", size="sm", className="me-1"
                ),
                dbc.Button(
                    [html.I(className="fas fa-times me-1"), "Rejeitar"],
                    id={"type": "btn-rejeitar-tarefa-aceite", "index": pend_id},
                    color="danger", size="sm", outline=True
                )
            ], className="d-flex")
        elif user_level >= 3:
            # Nível 3 não-responsável: pode editar/redesignar mesmo pendente
            botoes_acao = _btn_edit()
        else:
            # Nível < 3 não-responsável: apenas visualiza
            botoes_acao = html.Div()

    elif status_aceite == 'rejeitado':
        if user_level >= 3:
            # Nível 3 (qualquer, inclusive responsável): pode editar para redesignar
            botoes_acao = _btn_edit()
        elif e_responsavel_atual:
            # Nível < 3 responsável: aguardando nível 3 redesignar
            botoes_acao = _btn_edit(cor="secondary", disabled=True,
                                    titulo="Tarefa rejeitada — aguardando redesignação por nível 3")
        else:
            # Nível < 3 não-responsável: apenas visualiza
            botoes_acao = html.Div()

    else:
        # status_aceite == 'aceito': botão editar para todos
        botoes_acao = _btn_edit()

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
        html.Td(pend_id),
        html.Td(desc_content),
        html.Td(responsavel),
        html.Td(criar_badge_status(pendencia['status'])),
        td_progresso,
        html.Td(data_criacao),
        html.Td(ultima_atualizacao),
        html.Td(botoes_acao, style={"width": "120px", "textAlign": "center"})
    ])

    # Linha de histórico (colapsável)
    linha_historico = html.Tr([
        html.Td(
            dbc.Collapse(
                dbc.Card([
                    dbc.CardBody(id={"type": "historico-content", "index": index},
                                 className="p-0 workflow-subtask-panel")
                ], className="border-0"),
                id={"type": "collapse-historico", "index": index},
                is_open=False
            ),
            colSpan=9,
            className="p-0"
        )
    ])

    return [linha_principal, linha_historico]


def criar_tabela_pendencias(df_pendencias, df_historico=None, user_level=1, username_atual=None):
    """
    Cria a tabela Bootstrap com todas as pendências.

    Args:
        df_pendencias: DataFrame com as pendências
        df_historico: DataFrame com o histórico (para barra de horas e badges)
        user_level: Nível do usuário logado (1, 2 ou 3)
        username_atual: Username do usuário logado

    Returns:
        dbc.Table: Tabela com pendências expansíveis
    """
    if df_pendencias is None or df_pendencias.empty:
        return html.Div([
            html.I(className="fas fa-inbox fa-3x text-muted mb-3"),
            html.H5("Nenhuma pendência encontrada", className="text-muted")
        ], className="text-center py-5")

    # Resetar índice para garantir 0, 1, 2... independente de filtros aplicados
    df_pendencias = df_pendencias.reset_index(drop=True)

    # Cabeçalho da tabela
    thead = html.Thead([
        html.Tr([
            html.Th("", style={"width": "40px"}),
            html.Th("ID", style={"width": "100px"}),
            html.Th("Descrição"),
            html.Th("Responsável", style={"width": "150px"}),
            html.Th("Status", style={"width": "150px"}),
            html.Th("Progresso", style={"width": "100px"}),
            html.Th("Criação", style={"width": "100px"}),
            html.Th("Atualização", style={"width": "100px"}),
            html.Th("Ações", style={"width": "120px"})
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

        linhas.extend(criar_linha_pendencia(
            pendencia, index, hist_items,
            user_level=user_level, username_atual=username_atual
        ))

    tbody = html.Tbody(linhas)

    return dbc.Table(
        [thead, tbody],
        bordered=False,
        hover=True,
        responsive=True,
        striped=True,
        className="mb-0 workflow-table",
        style={"borderTop": "1px solid var(--bs-border-color)"}
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

        # Store para filtros ativos (preserva filtros durante ações)
        dcc.Store(id="store-filtros-ativos"),

        # Store para contexto de subtarefa (pend_id + subtarefa_id)
        dcc.Store(id="store-subtask-context", storage_type="memory"),

        # Modais de pendência
        create_pendencia_modal(),
        edit_pendencia_modal(),
        delete_confirm_modal(),
        concluir_subtarefa_modal(),

        # Modais de subtarefa
        create_subtask_modal(),
        add_log_modal(),
        edit_subtask_modal(),
        delete_subtask_confirm_modal(),

        # Header
        dbc.Row([
            dbc.Col([
                html.H2([
                    html.I(className="fas fa-project-diagram me-2"),
                    "Workflow Dashboard"
                ], className="mb-0 workflow-page-title")
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
                    ], id="btn-export", color="secondary", outline=True, disabled=True),

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
                    criar_tabela_pendencias(
                        df_pendencias, df_historico,
                        user_level=current_user.level if current_user.is_authenticated else 1,
                        username_atual=username_atual
                    ),
                    id="container-tabela"
                )
            ], className="p-0")
        ], className="shadow-sm")

    ], fluid=True, className="px-4 py-3 workflow-page")
