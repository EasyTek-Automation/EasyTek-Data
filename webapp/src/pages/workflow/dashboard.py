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
    edit_log_modal,
    delete_subtask_confirm_modal,
    devolver_atividade_modal,
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
    # Implementado com html.Div/flexbox para controle total de altura (dbc.Progress
    # não garante aplicação do style ao elemento .progress do DOM em DBC 2.0.3)
    COR_HEX = {
        'primary': 'var(--bs-primary)',
        'success': 'var(--bs-success)',
        'info':    'var(--bs-info)',
        'warning': 'var(--bs-warning)',
        'danger':  'var(--bs-danger)',
        'secondary':'var(--bs-secondary)',
    }
    total_fmt = float_para_hhmm(total)
    segmentos = []
    legenda = [
        html.Span([
            html.Span("Total: ", className="fw-semibold"),
            total_fmt
        ], className="me-3", style={"fontSize": "0.85rem", "whiteSpace": "nowrap"})
    ]
    for i, (desc, horas_soma) in enumerate(grupos.items()):
        cor = PALETA[i % len(PALETA)]
        cor_css = COR_HEX.get(cor, f'var(--bs-{cor})')
        pct = horas_soma / total * 100
        desc_curta = desc if len(desc) <= 20 else desc[:17] + "..."
        horas_fmt = float_para_hhmm(horas_soma)

        segmentos.append(html.Div(
            horas_fmt,
            style={
                "width": f"{pct}%",
                "backgroundColor": cor_css,
                "color": "white",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "fontSize": "0.85rem",
                "fontWeight": "600",
                "overflow": "hidden",
                "whiteSpace": "nowrap",
                "padding": "0 4px",
            }
        ))
        legenda.append(
            html.Span([
                html.Span("■ ", style={"color": cor_css}),
                f"{desc_curta} {horas_fmt}"
            ], className="me-2", style={"fontSize": "0.85rem", "whiteSpace": "nowrap"})
        )

    return html.Div([
        html.Div(
            segmentos,
            style={
                "height": "36px",
                "display": "flex",
                "borderRadius": "0.375rem",
                "overflow": "hidden",
            },
            className="mb-1"
        ),
        html.Div(legenda, className="d-flex flex-wrap")
    ], className="mt-1 mb-1")


def criar_cards_kpi(df_pendencias, df_historico=None, username_atual=None):  # noqa: E501
    """
    Cria o dashboard KPI do workflow com cards visuais.

    Args:
        df_pendencias: DataFrame com as pendências
        df_historico: DataFrame com o histórico
        username_atual: Username do usuário logado

    Returns:
        html.Div: Dashboard KPI completo
    """
    # === Métricas de Demandas ===
    if df_pendencias is None or df_pendencias.empty:
        total = em_fila = pendentes = em_andamento = bloqueados = concluidas_d = 0
        aguardando_aceite = abertos_por_mim = abertos_aceitos = abertos_rejeitados = 0
    else:
        total = len(df_pendencias)
        em_fila = len(df_pendencias[df_pendencias['status'] == 'Em Fila (Planejamento)'])
        pendentes = len(df_pendencias[df_pendencias['status'] == 'Pendente'])
        em_andamento = len(df_pendencias[df_pendencias['status'] == 'Em Andamento'])
        bloqueados = len(df_pendencias[df_pendencias['status'] == 'Bloqueado'])
        concluidas_d = len(df_pendencias[df_pendencias['status'] == 'Concluído'])

        aguardando_aceite = 0
        if username_atual and 'status_aceite' in df_pendencias.columns and 'responsavel' in df_pendencias.columns:
            mask_aceite = (
                (df_pendencias['responsavel'] == username_atual) &
                (df_pendencias['status_aceite'] != 'aceito')
            )
            aguardando_aceite = int(mask_aceite.sum())

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

    # === Métricas de Atividades e Horas ===
    total_ativ = em_andamento_ativ = concluidas_ativ = 0
    horas_concluidas = horas_total = 0.0
    aguardando_aprovacao = 0

    if df_historico is not None and not df_historico.empty:
        if 'record_type' in df_historico.columns:
            df_ativ = df_historico[df_historico['record_type'] == 'subtarefa']
        else:
            df_ativ = df_historico

        total_ativ = len(df_ativ)
        if total_ativ > 0 and 'concluido' in df_ativ.columns:
            concluidas_ativ = int(df_ativ['concluido'].eq(True).sum())
        em_andamento_ativ = total_ativ - concluidas_ativ

        # Índice de subtarefas por hist_id (para herdar concluido nos logs)
        subtarefa_por_id = {}
        if 'record_type' in df_historico.columns and 'hist_id' in df_historico.columns:
            for _, r in df_ativ.iterrows():
                hid = r.get('hist_id') if hasattr(r, 'get') else (r['hist_id'] if 'hist_id' in r.index else None)
                if hid:
                    subtarefa_por_id[hid] = r

        # Somar horas de subtarefas + logs (excluindo criacao)
        for _, row in df_historico.iterrows():
            rt = row.get('record_type', 'subtarefa') if hasattr(row, 'get') else (row['record_type'] if 'record_type' in row.index else 'subtarefa')
            if rt == 'criacao':
                continue
            h = row.get('horas') if hasattr(row, 'get') else (row['horas'] if 'horas' in row.index else None)
            try:
                if h is not None and str(h) != 'nan' and float(h) > 0:
                    horas_total += float(h)
                    if rt == 'log':
                        parent_id = row.get('subtarefa_id') if hasattr(row, 'get') else (row['subtarefa_id'] if 'subtarefa_id' in row.index else None)
                        parent = subtarefa_por_id.get(parent_id)
                        concluido = (parent.get('concluido') if hasattr(parent, 'get') else parent['concluido'] if parent is not None and 'concluido' in parent.index else False) is True if parent is not None else False
                    else:
                        concluido = row.get('concluido') if hasattr(row, 'get') else (row['concluido'] if 'concluido' in row.index else False)
                        concluido = concluido is True
                    if concluido:
                        horas_concluidas += float(h)
            except (ValueError, TypeError):
                pass

        if username_atual and 'aprovador' in df_historico.columns and 'status_aprovacao' in df_historico.columns:
            mask = (
                (df_historico['aprovador'] == username_atual) &
                (df_historico['status_aprovacao'] == 'pendente')
            )
            aguardando_aprovacao = int(mask.sum())

    # === Helpers visuais ===
    COR = {
        'primary':   'var(--bs-primary)',
        'success':   'var(--bs-success)',
        'info':      'var(--bs-info)',
        'warning':   'var(--bs-warning)',
        'danger':    'var(--bs-danger)',
        'secondary': 'var(--bs-secondary)',
    }

    def _barra(segmentos, altura=26, formatter=None):
        """segmentos: list of (valor_numerico, cor_key, label_tooltip)"""
        total_v = sum(v for v, _, _ in segmentos if v > 0)
        if total_v == 0:
            return html.Div(style={
                "height": f"{altura}px",
                "backgroundColor": "#e9ecef",
                "borderRadius": "0.375rem"
            })
        segs = []
        for valor, cor_key, label in segmentos:
            if valor <= 0:
                continue
            pct = valor / total_v * 100
            label_display = (formatter(valor) if formatter else str(valor)) if pct > 9 else ""
            segs.append(html.Div(
                label_display,
                title=f"{label}: {valor}",
                style={
                    "width": f"{pct}%",
                    "backgroundColor": COR.get(cor_key, f'var(--bs-{cor_key})'),
                    "color": "white",
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "fontSize": "0.78rem",
                    "fontWeight": "700",
                    "overflow": "hidden",
                    "whiteSpace": "nowrap",
                    "padding": "0 4px",
                    "cursor": "default",
                }
            ))
        return html.Div(segs, style={
            "height": f"{altura}px",
            "display": "flex",
            "borderRadius": "0.375rem",
            "overflow": "hidden",
        })

    def _legenda(itens):
        """itens: list of (cor_key, label, valor_str)"""
        spans = []
        for cor_key, label, valor in itens:
            cor_css = COR.get(cor_key, f'var(--bs-{cor_key})')
            spans.append(html.Span([
                html.Span("■ ", style={"color": cor_css}),
                html.Span(f"{label} ", style={"color": "#6c757d"}),
                html.Span(str(valor), style={"fontWeight": "700"}),
            ], className="me-3", style={"fontSize": "0.8rem", "whiteSpace": "nowrap"}))
        return html.Div(spans, className="d-flex flex-wrap mt-2")

    def _num(valor, cor_key=None, tamanho="2.6rem"):
        style = {"lineHeight": "1", "fontWeight": "800", "fontSize": tamanho}
        if cor_key:
            style["color"] = COR.get(cor_key, f'var(--bs-{cor_key})')
        return html.Div(str(valor), style=style)

    def _sub(valor, label, cor_key):
        return html.Div([
            html.Span(str(valor), style={
                "fontSize": "1.4rem",
                "fontWeight": "700",
                "color": COR.get(cor_key, f'var(--bs-{cor_key})'),
            }),
            html.Span(f" {label}", style={"fontSize": "0.8rem", "color": "#6c757d", "marginLeft": "3px"}),
        ])

    # ============================================================
    # CARD 1 — DEMANDAS
    # ============================================================
    planejadas = total - concluidas_d

    card_demandas = dbc.Card([
        dbc.CardBody([
            # Cabeçalho do card
            html.Div([
                html.I(className="fas fa-tasks me-2",
                       style={"color": COR['primary'], "fontSize": "1.1rem"}),
                html.Span("Demandas", className="fw-semibold",
                           style={"fontSize": "0.95rem", "color": "#495057"}),
            ], className="mb-3"),

            # Números principais
            html.Div([
                html.Div([
                    _num(total),
                    html.Div("total", style={"fontSize": "0.75rem", "color": "#adb5bd", "marginTop": "2px"}),
                ], className="me-4"),
                html.Div([
                    _sub(planejadas, "planejadas", "primary"),
                    _sub(em_andamento, "em andamento", "primary"),
                ]),
            ], className="d-flex align-items-center mb-3"),

            # Barra visual
            _barra([
                (em_fila,      'info',    'Em Fila'),
                (pendentes,    'warning', 'Pendente'),
                (em_andamento, 'primary', 'Em Andamento'),
                (bloqueados,   'danger',  'Bloqueado'),
                (concluidas_d, 'success', 'Concluído'),
            ]),

            # Legenda
            _legenda([
                ('info',    'Em Fila',      em_fila),
                ('warning', 'Pendente',     pendentes),
                ('primary', 'Em Andamento', em_andamento),
                ('danger',  'Bloqueado',    bloqueados),
                ('success', 'Concluído',    concluidas_d),
            ]),
        ], className="p-3")
    ], className="shadow-sm h-100")

    # ============================================================
    # CARD 2 — ATIVIDADES
    # ============================================================
    pct_ativ = int(concluidas_ativ / total_ativ * 100) if total_ativ > 0 else 0
    pct_ativ_cor = (
        'success' if pct_ativ == 100 else
        'primary' if pct_ativ >= 50 else
        'warning'
    )

    card_atividades = dbc.Card([
        dbc.CardBody([
            html.Div([
                html.I(className="fas fa-tasks me-2",
                       style={"color": COR['success'], "fontSize": "1.1rem"}),
                html.Span("Atividades", className="fw-semibold",
                           style={"fontSize": "0.95rem", "color": "#495057"}),
            ], className="mb-3"),

            html.Div([
                html.Div([
                    _num(total_ativ, 'success'),
                    html.Div("total", style={"fontSize": "0.75rem", "color": "#adb5bd", "marginTop": "2px"}),
                ], className="me-4"),
                html.Div([
                    _sub(em_andamento_ativ, "em andamento", "warning"),
                    _sub(concluidas_ativ, "concluídas", "success"),
                ]),
            ], className="d-flex align-items-center mb-3"),

            _barra([
                (em_andamento_ativ, 'warning', 'Em Andamento'),
                (concluidas_ativ,   'success', 'Concluídas'),
            ]),

            html.Div([
                *_legenda([
                    ('warning', 'Em Andamento', em_andamento_ativ),
                    ('success', 'Concluídas',   concluidas_ativ),
                ]).children,
                html.Span([
                    html.Span(f"{pct_ativ}%", style={
                        "fontWeight": "700",
                        "color": COR[pct_ativ_cor],
                        "fontSize": "0.88rem",
                    }),
                    html.Span(" concluídas", style={"fontSize": "0.8rem", "color": "#6c757d"}),
                ], className="ms-auto"),
            ], className="d-flex flex-wrap align-items-center mt-2"),
        ], className="p-3")
    ], className="shadow-sm h-100")

    # ============================================================
    # CARD 3 — HORAS
    # ============================================================
    pct_horas = int(horas_concluidas / horas_total * 100) if horas_total > 0 else 0
    horas_pend = horas_total - horas_concluidas
    horas_conc_fmt = float_para_hhmm(horas_concluidas) or "—"
    horas_total_fmt = float_para_hhmm(horas_total) or "—"
    horas_pend_fmt = float_para_hhmm(horas_pend) or "—"

    cor_circ = (
        'success'   if pct_horas == 100 else
        'primary'   if pct_horas >= 50  else
        'warning'   if pct_horas > 0    else
        'secondary'
    )

    card_horas = dbc.Card([
        dbc.CardBody([
            html.Div([
                html.I(className="fas fa-clock me-2",
                       style={"color": COR['info'], "fontSize": "1.1rem"}),
                html.Span("Horas", className="fw-semibold",
                           style={"fontSize": "0.95rem", "color": "#495057"}),
            ], className="mb-3"),

            html.Div([
                # Círculo de progresso (visual)
                html.Div([
                    html.Div(f"{pct_horas}%", style={
                        "fontSize": "1.7rem",
                        "fontWeight": "800",
                        "color": COR[cor_circ],
                        "lineHeight": "1",
                    }),
                    html.Div("concluídas", style={"fontSize": "0.68rem", "color": "#adb5bd"}),
                ], style={
                    "width": "76px",
                    "height": "76px",
                    "borderRadius": "50%",
                    "border": f"5px solid {COR[cor_circ]}",
                    "display": "flex",
                    "flexDirection": "column",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "flexShrink": "0",
                    "marginRight": "16px",
                }),
                html.Div([
                    _sub(horas_conc_fmt, "concluídas", "success"),
                    _sub(horas_total_fmt, "total", "secondary"),
                ]),
            ], className="d-flex align-items-center mb-3"),

            _barra([
                (horas_concluidas, 'success',   'Concluídas'),
                (horas_pend,       'secondary', 'Pendentes'),
            ], formatter=lambda v: f"{v:.2f}h"),

            _legenda([
                ('success',   'Concluídas', horas_conc_fmt),
                ('secondary', 'Pendentes',  horas_pend_fmt),
            ]),
        ], className="p-3")
    ], className="shadow-sm h-100")

    # ============================================================
    # NOTIFICAÇÕES PESSOAIS (compacto)
    # ============================================================
    def _notif_item(icone, label, valor, cor_key=None, destaque=False):
        num_style = {
            "fontSize": "1.6rem",
            "fontWeight": "800",
            "lineHeight": "1.1",
            "color": COR.get(cor_key, "#212529") if cor_key else "#212529",
        }
        return html.Div([
            html.Div([
                html.I(className=f"{icone} me-1 text-muted",
                       style={"fontSize": "0.75rem"}),
                html.Span(label, style={"fontSize": "0.75rem", "color": "#6c757d"}),
            ]),
            html.Div(str(valor), style=num_style),
        ], className="text-center px-4 py-2", style={
            "borderLeft": "1px solid #dee2e6",
            "minWidth": "80px",
        })

    notif_items = []
    if username_atual:
        notif_items.append(_notif_item(
            "fas fa-inbox", "Para Aceitar", aguardando_aceite,
            cor_key="secondary" if aguardando_aceite else None
        ))
        notif_items.append(_notif_item(
            "fas fa-clock", "Para Aprovar", aguardando_aprovacao,
            cor_key="warning" if aguardando_aprovacao else None
        ))
        notif_items.append(_notif_item(
            "fas fa-folder-open", "Criadas p/ Mim", abertos_por_mim
        ))
        notif_items.append(_notif_item(
            "fas fa-check-circle", "Aceitas", abertos_aceitos,
            cor_key="success" if abertos_aceitos else None
        ))
        notif_items.append(_notif_item(
            "fas fa-times-circle", "Rejeitadas", abertos_rejeitados,
            cor_key="danger" if abertos_rejeitados else None
        ))

    notif_card = None
    if notif_items:
        notif_card = dbc.Card([
            dbc.CardBody([
                html.Div([
                    html.Div([
                        html.I(className="fas fa-user-circle me-2",
                               style={"color": COR['primary']}),
                        html.Span("Suas notificações", className="fw-semibold",
                                   style={"fontSize": "0.85rem", "color": "#6c757d"}),
                    ], className="px-3 py-2",
                       style={"borderBottom": "1px solid #dee2e6"}),
                    html.Div([
                        # Remove a borda esquerda do primeiro item
                        html.Div(notif_items[0].children, className="text-center px-4 py-2",
                                 style={"minWidth": "80px"}),
                        *notif_items[1:],
                    ], className="d-flex align-items-center flex-wrap"),
                ])
            ], className="p-0")
        ], className="shadow-sm mb-3")

    tres_cards = dbc.Row([
        dbc.Col(card_demandas,   width=12, lg=4, className="mb-3"),
        dbc.Col(card_atividades, width=12, lg=4, className="mb-3"),
        dbc.Col(card_horas,      width=12, lg=4, className="mb-3"),
    ], className="g-3 mb-0")

    children = [tres_cards]
    if notif_card:
        children.append(notif_card)

    return html.Div(children, className="mb-3")


def criar_painel_filtros(username_inicial="todos"):
    """Cria o painel de filtros sempre visível."""
    return dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.Label("Responsável:", className="fw-bold mb-2"),
                    dcc.Dropdown(
                        id="filtro-responsavel",
                        options=[{"label": "Todos", "value": "todos"}],
                        value=username_inicial,
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
                ], width=12, md=2, className="mb-3"),

                dbc.Col([
                    html.Label("Horas:", className="fw-bold mb-2"),
                    dbc.Switch(
                        id="filtro-horas-uteis",
                        label="Com horas",
                        value=False,
                        className="mt-1"
                    )
                ], width=12, md=1, className="mb-3"),

                dbc.Col([
                    html.Label("Referência:", className="fw-bold mb-2"),
                    dbc.Checklist(
                        id="filtro-tipo-data",
                        options=[
                            {"label": "Demanda", "value": "tarefa"},
                            {"label": "Atividade", "value": "subtarefa"},
                            {"label": "Planejada", "value": "planejada"},
                        ],
                        value=["tarefa", "subtarefa"],
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
            ]),
            dbc.Row([
                dbc.Col([
                    html.Label("Prioridade das atividades:", className="fw-bold mb-2"),
                    dcc.Dropdown(
                        id="filtro-prioridade",
                        options=[
                            {"label": "● Urgente", "value": "urgente"},
                            {"label": "● Alta",    "value": "alta"},
                            {"label": "● Normal",  "value": "normal"},
                            {"label": "● Baixa",   "value": "baixa"},
                        ],
                        multi=True,
                        placeholder="Todas as prioridades"
                    )
                ], width=12, md=4, className="mb-3"),
                dbc.Col([
                    html.Label("Validação Gestor:", className="fw-bold mb-2"),
                    dbc.Checklist(
                        id="filtro-validacao-gestor",
                        options=[
                            {"label": "Ag. Validação", "value": "pendente"},
                            {"label": "Aprovadas",     "value": "aprovado"},
                            {"label": "Devolvidas",    "value": "devolvido"},
                        ],
                        value=[],
                        inline=True,
                        className="mt-1"
                    )
                ], width=12, md=4, className="mb-3"),
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

    COR_PRIORIDADE = {
        "urgente": "var(--bs-danger)",
        "alta":    "var(--bs-warning)",
        "normal":  "var(--bs-primary)",
        "baixa":   "var(--bs-secondary)",
    }
    LABEL_PRIORIDADE = {
        "urgente": "Urgente",
        "alta":    "Alta",
        "normal":  "Normal",
        "baixa":   "Baixa",
    }

    for i, item in enumerate(historico_items):
        is_last = (i == len(historico_items) - 1)
        concluido = item.get('concluido', False)
        hist_id = item.get('hist_id', '')
        horas = item.get('horas')
        aprovador = item.get('aprovador')
        status_aprovacao = item.get('status_aprovacao')
        record_type = item.get('record_type', 'subtarefa')
        prioridade = item.get('prioridade', 'normal') or 'normal'

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
                    # Título + prioridade (subtarefas) + badges
                    html.Div([
                        # Indicador de prioridade ClickUp-style (apenas subtarefas)
                        dbc.DropdownMenu(
                            [
                                dbc.DropdownMenuItem([
                                    html.Span("●", style={"color": COR_PRIORIDADE["urgente"], "marginRight": "6px"}),
                                    "Urgente"
                                ], id={"type": "set-prioridade", "index": f"{hist_id}__urgente"}),
                                dbc.DropdownMenuItem([
                                    html.Span("●", style={"color": COR_PRIORIDADE["alta"], "marginRight": "6px"}),
                                    "Alta"
                                ], id={"type": "set-prioridade", "index": f"{hist_id}__alta"}),
                                dbc.DropdownMenuItem([
                                    html.Span("●", style={"color": COR_PRIORIDADE["normal"], "marginRight": "6px"}),
                                    "Normal"
                                ], id={"type": "set-prioridade", "index": f"{hist_id}__normal"}),
                                dbc.DropdownMenuItem([
                                    html.Span("●", style={"color": COR_PRIORIDADE["baixa"], "marginRight": "6px"}),
                                    "Baixa"
                                ], id={"type": "set-prioridade", "index": f"{hist_id}__baixa"}),
                            ],
                            label=html.Span(
                                "●",
                                title=f"Prioridade: {LABEL_PRIORIDADE.get(prioridade, 'Normal')}",
                                style={"color": COR_PRIORIDADE.get(prioridade, COR_PRIORIDADE["normal"]),
                                       "fontSize": "1.3rem", "lineHeight": "1", "cursor": "pointer"},
                            ),
                            size="sm",
                            direction="down",
                            className="me-1 d-inline-flex align-items-center",
                            toggle_class_name="p-0 border-0 bg-transparent shadow-none",
                            caret=False,
                        ) if record_type == 'subtarefa' and hist_id and mostrar_botoes else html.Span(),
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
            colSpan=7,
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
            html.H5("Nenhuma demanda encontrada", className="text-muted")
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
                "Deseja marcar esta atividade como ",
                html.Strong("concluída", className="text-success"),
                "?"
            ]),
            html.P([
                "Esta ação é ",
                html.Strong("irreversível", className="text-danger"),
                ". Para desfazer, será necessário criar uma nova entrada."
            ], className="text-muted small"),
            html.Hr(className="my-3"),
            html.Label("Data de Execução:", className="fw-bold mb-1"),
            html.Span(" *", className="text-danger"),
            html.Div(
                dcc.DatePickerSingle(
                    id="concluir-subtarefa-data-execucao",
                    placeholder="DD/MM/AAAA",
                    display_format="DD/MM/YYYY",
                    first_day_of_week=0,
                    clearable=True,
                    style={"width": "100%"}
                ),
                className="mb-2"
            ),
            html.Small(
                "Informe quando a atividade foi executada.",
                className="text-muted"
            ),
            html.Div(id="concluir-subtarefa-alert", className="mt-2"),
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

        # Store para filtros ativos — inicializado com filtro pelo usuário logado
        dcc.Store(id="store-filtros-ativos", data={
            "responsavel": username_atual or "todos",
            "status": None,
            "busca": None,
            "status_aceite": None,
            "tipo_data": ["tarefa", "subtarefa"],
            "data_inicio": None,
            "data_fim": None,
            "horas_uteis": False,
            "prioridade": [],
            "validacao_gestor": [],
        }),

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
        edit_log_modal(),
        delete_subtask_confirm_modal(),
        devolver_atividade_modal(),

        # Header
        dbc.Row([
            dbc.Col([
                html.H2([
                    html.I(className="fas fa-project-diagram me-2"),
                    "Demandas"
                ], className="mb-0 workflow-page-title")
            ], width=12, md=6),

            dbc.Col([
                dbc.ButtonGroup([
                    dbc.Button([
                        html.I(className="fas fa-plus-circle me-2"),
                        "Nova Demanda"
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
        criar_painel_filtros(username_inicial=username_atual or "todos"),

        # Tabela de Pendências — pré-filtrada pelo usuário logado
        dbc.Card([
            dbc.CardBody([
                html.Div(
                    criar_tabela_pendencias(
                        df_pendencias[df_pendencias['responsavel'] == username_atual]
                        if (df_pendencias is not None and not df_pendencias.empty and username_atual)
                        else df_pendencias,
                        df_historico,
                        user_level=current_user.level if current_user.is_authenticated else 1,
                        username_atual=username_atual
                    ),
                    id="container-tabela"
                )
            ], className="p-0")
        ], className="shadow-sm")

    ], fluid=True, className="px-4 py-3 workflow-page")
