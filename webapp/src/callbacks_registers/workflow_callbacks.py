"""
Callbacks para o Dashboard de Pendências (Workflow).

Implementa:
- Expansão/colapso de linhas com pattern-matching
- Aplicação de filtros
- Refresh de dados
- Marcar subatividade como concluída
- Aprovar / Rejeitar subatividades
"""

import pandas as pd
from dash import Input, Output, State, MATCH, ALL, html, callback_context, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import json

from src.pages.workflow.dashboard import (
    carregar_dados_csv,
    criar_tabela_pendencias,
    criar_cards_kpi,
    float_para_hhmm
)


# ======================================================================================
# HELPERS
# ======================================================================================

def criar_checklist_subtarefas(historico_items, username_atual=None,
                               user_level=1, pend_id=None):
    """
    View unificada de subtarefas (estilo ClickUp).

    Cada subtarefa tem seu próprio expand/collapse (dbc.Collapse + btn pattern-matching).
    Quando expandida, exibe: meta info, observações e logs como sub-itens.
    Eventos de sistema ficam numa seção colapsável no topo.
    """
    sub_items = [h for h in historico_items if h.get('record_type', 'subtarefa') == 'subtarefa']
    log_items_all = [h for h in historico_items if h.get('record_type') == 'log']
    criacao_items = [h for h in historico_items if h.get('record_type') == 'criacao']

    botao_nova = html.Div(
        dbc.Button(
            [html.I(className="fas fa-plus me-1"), "Nova Subtarefa"],
            id={"type": "btn-nova-subtarefa", "index": pend_id or ""},
            color="success",
            size="sm",
            outline=True
        ),
        className="px-3 pt-3 pb-2"
    ) if pend_id else html.Div()

    # --- Seção de eventos do sistema (criação/aceite/rejeição) ---
    secao_sistema = None
    if criacao_items:
        eventos_html = []
        for ev in criacao_items:
            desc = ev.get('descricao', '')
            by = ev.get('editado_por') or ev.get('responsavel', '')
            data_ev = ev.get('data', '')
            desc_lower = desc.lower()
            if 'rejeit' in desc_lower:
                icone_ev = "fas fa-times-circle text-danger"
            elif 'aceito' in desc_lower or 'aceita' in desc_lower:
                icone_ev = "fas fa-check-circle text-success"
            else:
                icone_ev = "fas fa-plus-circle text-info"
            eventos_html.append(html.Div([
                html.I(className=f"{icone_ev} me-2"),
                html.Span(desc, className="me-2"),
                html.Span(f"· {by} · {data_ev}", className="text-muted"),
            ], style={"fontSize": "0.82rem"}, className="py-1 border-bottom"))

        secao_sistema = html.Details([
            html.Summary(
                [html.I(className="fas fa-history me-2 text-muted"),
                 html.Span("Linha do tempo do sistema", className="text-muted")],
                style={"cursor": "pointer", "fontSize": "0.83rem",
                       "outline": "none", "userSelect": "none"}
            ),
            html.Div(eventos_html, className="mt-1 ps-3 pb-2"),
        ], className="px-3 py-2 mb-1 rounded",
           style={"backgroundColor": "rgba(0,0,0,0.025)"})

    # --- Estado vazio ---
    if not sub_items:
        return html.Div([
            botao_nova,
            secao_sistema or html.Div(),
            html.Div([
                html.I(className="fas fa-check-square fa-2x text-muted mb-2 d-block"),
                html.Span("Nenhuma subtarefa registrada.", className="text-muted")
            ], className="text-center py-4")
        ])

    # --- Lista de subtarefas com collapse individual ---
    items_html = []
    for item in sub_items:
        concluido = item.get('concluido') is True
        hist_id = item.get('hist_id', '')
        horas_raw = item.get('horas')
        aprovador = item.get('aprovador')
        status_aprovacao = item.get('status_aprovacao')

        _t = item.get('titulo')
        _d = item.get('descricao')
        titulo = (str(_t) if _t and str(_t) != 'nan' else None) or \
                 (str(_d) if _d and str(_d) != 'nan' else None) or ''
        tipo_evento = item.get('tipo_evento', '')
        editado_por = item.get('editado_por') or item.get('responsavel', '')
        data = item.get('data', '')
        observacoes = (item.get('observacoes') or '').strip()

        # Logs desta subtarefa
        logs_da_sub = [h for h in log_items_all if h.get('subtarefa_id') == hist_id]
        n_logs = len(logs_da_sub)
        horas_logs = sum(
            float(h.get('horas') or 0)
            for h in logs_da_sub
            if h.get('horas') is not None and str(h.get('horas')) != 'nan'
        )

        try:
            horas_val = float(horas_raw) if horas_raw is not None and str(horas_raw) != 'nan' else None
        except (ValueError, TypeError):
            horas_val = None

        # Ícone de status
        if concluido:
            icone_status = html.I(className="fas fa-check-circle text-success",
                                  style={"fontSize": "1.1rem"})
        elif status_aprovacao == 'pendente':
            icone_status = html.I(className="fas fa-hourglass-half text-warning",
                                  style={"fontSize": "1.1rem"})
        elif status_aprovacao == 'rejeitado':
            icone_status = html.I(className="fas fa-times-circle text-danger",
                                  style={"fontSize": "1.1rem"})
        else:
            icone_status = html.I(className="far fa-circle text-secondary",
                                  style={"fontSize": "1.1rem"})

        # Badges
        badges = []
        if tipo_evento and tipo_evento not in ('criacao', 'log', 'atualizacao_workflow'):
            badges.append(dbc.Badge(tipo_evento, color="secondary", className="me-1",
                                    style={"fontWeight": "400"}))
        if concluido:
            badges.append(dbc.Badge("Concluída", color="success", className="me-1"))
        if status_aprovacao == 'pendente':
            badges.append(dbc.Badge("Aguard. Aprovação", color="warning", className="me-1"))
        elif status_aprovacao == 'aprovado':
            badges.append(dbc.Badge("Aprovado", color="success", className="me-1"))
        elif status_aprovacao == 'rejeitado':
            badges.append(dbc.Badge("Rejeitado", color="danger", className="me-1"))
        if n_logs > 0:
            horas_logs_fmt = float_para_hhmm(horas_logs) if horas_logs > 0 else ""
            n_label = f"{n_logs} rel."
            if horas_logs_fmt:
                n_label += f" · {horas_logs_fmt}"
            badges.append(dbc.Badge(
                [html.I(className="fas fa-file-alt me-1"), n_label],
                color="info", className="me-1"
            ))

        # Meta info
        horas_fmt = float_para_hhmm(horas_val) if horas_val else None
        meta_partes = [editado_por, data]
        if horas_fmt:
            meta_partes.append(html.Span([
                html.I(className="fas fa-clock me-1 text-info"), horas_fmt
            ], className="text-info fw-semibold"))
        if aprovador and not concluido:
            meta_partes.append(html.Span([
                html.I(className="fas fa-user-check me-1 text-warning"),
                f"Aprovador: {aprovador}"
            ], className="text-warning"))

        meta_children = []
        for i, p in enumerate(meta_partes):
            meta_children.append(p)
            if i < len(meta_partes) - 1:
                meta_children.append(html.Span(" · ", className="text-muted"))

        # Botões de ação
        botoes = []
        if not concluido and hist_id:
            botoes.append(dbc.Button(
                [html.I(className="fas fa-check me-1"), "Concluir"],
                id={"type": "btn-concluir-subtarefa", "index": hist_id},
                color="success", size="sm", outline=True
            ))
        if hist_id:
            botoes.append(dbc.Button(
                html.I(className="fas fa-file-alt"),
                id={"type": "btn-add-log", "index": hist_id},
                color="info", size="sm", outline=True,
                title="Preencher Relatório" if not concluido else "Subtarefa concluída",
                disabled=concluido
            ))
        if user_level >= 3 and hist_id:
            botoes.append(dbc.Button(
                html.I(className="fas fa-pencil-alt"),
                id={"type": "btn-edit-subtarefa", "index": hist_id},
                color="warning", size="sm", outline=True,
                title="Editar Subtarefa"
            ))
            botoes.append(dbc.Button(
                html.I(className="fas fa-trash"),
                id={"type": "btn-delete-subtarefa", "index": hist_id},
                color="danger", size="sm", outline=True,
                title="Excluir Subtarefa"
            ))
        if (status_aprovacao == 'pendente' and aprovador and
                username_atual and username_atual == aprovador and hist_id):
            botoes.append(dbc.Button(
                [html.I(className="fas fa-thumbs-up me-1"), "Aprovar"],
                id={"type": "btn-aprovar", "index": hist_id},
                color="success", size="sm", className="me-1"
            ))
            botoes.append(dbc.Button(
                [html.I(className="fas fa-thumbs-down me-1"), "Rejeitar"],
                id={"type": "btn-rejeitar", "index": hist_id},
                color="danger", size="sm"
            ))

        cor_borda = ("var(--bs-success)" if concluido
                     else "var(--bs-warning)" if status_aprovacao == 'pendente'
                     else "var(--bs-danger)" if status_aprovacao == 'rejeitado'
                     else "var(--bs-primary)")

        # --- Conteúdo do collapse: meta + obs + logs como sub-itens ---
        corpo_collapse = []
        corpo_collapse.append(
            html.Small(meta_children, className="text-muted d-block mb-2")
        )
        if observacoes:
            corpo_collapse.append(
                html.Small(observacoes, className="fst-italic text-muted d-block mb-2",
                           style={"whiteSpace": "pre-line"})
            )
        # Logs como sub-itens
        for log in logs_da_sub:
            obs_log = (log.get('observacoes') or '').strip()
            horas_log_raw = log.get('horas')
            try:
                h_log = float(horas_log_raw) if horas_log_raw is not None and str(horas_log_raw) != 'nan' else None
            except (ValueError, TypeError):
                h_log = None
            horas_log_fmt = float_para_hhmm(h_log) if h_log else None

            log_meta = [
                html.I(className="fas fa-file-alt text-info me-2",
                       style={"fontSize": "0.82rem"}),
                html.Span("Relatório", className="fw-semibold me-2",
                          style={"fontSize": "0.82rem"}),
                html.Span(log.get('editado_por', ''), className="text-muted me-1"),
                html.Span(f"· {log.get('data', '')}", className="text-muted"),
            ]
            if horas_log_fmt:
                log_meta += [
                    html.Span(" · ", className="text-muted"),
                    html.I(className="fas fa-clock me-1 text-info"),
                    html.Span(horas_log_fmt, className="text-info fw-semibold"),
                ]

            corpo_collapse.append(html.Div([
                html.Div(log_meta, className="d-flex align-items-center mb-1 flex-wrap"),
                html.Small(obs_log, className="fst-italic text-muted d-block ps-4",
                           style={"whiteSpace": "pre-line"}) if obs_log else None
            ], className="p-2 mb-1 rounded",
               style={"backgroundColor": "rgba(13,202,240,0.07)",
                      "borderLeft": "2px solid var(--bs-info)"}))

        # Subtarefa com collapse
        tem_corpo = bool(meta_children or observacoes or logs_da_sub)
        item_html = html.Div([
            # Linha do cabeçalho: chevron | status | título+badges | botões
            html.Div([
                dbc.Button(
                    html.I(className="fas fa-chevron-right",
                           id={"type": "chevron-subtask", "index": hist_id}),
                    id={"type": "btn-expand-subtask", "index": hist_id},
                    color="link", size="sm",
                    className="p-0 me-1 text-muted text-decoration-none",
                    style={"visibility": "visible" if tem_corpo else "hidden"}
                ),
                html.Div(icone_status,
                         style={"width": "22px", "flexShrink": "0"}),
                html.Div([
                    html.Span(
                        titulo,
                        className="fw-semibold me-2" + (" text-muted" if concluido else ""),
                        style={"textDecoration": "line-through" if concluido else "none",
                               "fontSize": "0.93rem"}
                    ),
                    *badges
                ], className="flex-grow-1 d-flex align-items-center flex-wrap ms-2"),
                html.Div(
                    html.Div(botoes, className="d-flex gap-1 flex-wrap"),
                    className="ms-2 flex-shrink-0"
                ) if botoes else None,
            ], className="d-flex align-items-center"),

            # Corpo colapsável
            dbc.Collapse(
                html.Div(corpo_collapse, className="ms-4 mt-2 ps-2",
                         style={"borderLeft": "2px solid rgba(0,0,0,0.08)"}),
                id={"type": "collapse-subtask", "index": hist_id},
                is_open=False
            ) if tem_corpo else html.Div(),

        ], className="py-2 px-2 mb-1 rounded" + (" opacity-75" if concluido else ""),
           style={"borderLeft": f"3px solid {cor_borda}",
                  "backgroundColor": "rgba(0,0,0,0.015)" if concluido else "transparent"})

        items_html.append(item_html)

    return html.Div([
        botao_nova,
        secao_sistema or html.Div(),
        html.Div(items_html, className="px-3 pb-3 pt-1")
    ])


def criar_conteudo_historico(pendencia_id, df_historico, username_atual=None, user_level=1):
    """
    Cria o conteúdo expandido de uma pendência — view unificada sem abas.

    Subtarefas são listadas com seus relatórios/logs inline abaixo (colapsáveis).
    Eventos de sistema (criação/aceite/rejeição) ficam numa seção colapsável no topo.
    """
    historico_pendencia = df_historico[df_historico['pendencia_id'] == pendencia_id].copy()
    historico_pendencia = historico_pendencia.sort_values('data')

    historico_items = []
    for _, row in historico_pendencia.iterrows():
        horas_raw = row.get('horas')
        try:
            horas_val = float(horas_raw) if horas_raw is not None and str(horas_raw) != 'nan' else None
        except (ValueError, TypeError):
            horas_val = None

        concluido_val = row.get('concluido') is True

        def _str_or_none(v):
            return str(v) if v is not None and str(v) != 'nan' else None

        historico_items.append({
            'hist_id': row.get('hist_id', ''),
            'titulo': _str_or_none(row.get('titulo')) or row['descricao'],
            'descricao': row['descricao'],
            'observacoes': row.get('observacoes', '') or '',
            'alteracoes': row.get('alteracoes', '') or '',
            'editado_por': row.get('editado_por', row['responsavel']),
            'responsavel': row['responsavel'],
            'data': (row['data'].strftime("%d/%m/%Y")
                     if (bool(row.get('is_retroativo')) or
                         _str_or_none(row.get('tipo_evento')) == 'Lançamento Retroativo')
                     else row['data'].strftime("%d/%m/%Y %H:%M")),
            'is_retroativo': (bool(row.get('is_retroativo')) or
                              _str_or_none(row.get('tipo_evento')) == 'Lançamento Retroativo'),
            'horas': horas_val,
            'concluido': concluido_val,
            'aprovador': _str_or_none(row.get('aprovador')),
            'status_aprovacao': _str_or_none(row.get('status_aprovacao')),
            'tipo_evento': _str_or_none(row.get('tipo_evento')) or '',
            'record_type': row.get('record_type', 'subtarefa') or 'subtarefa',
            'subtarefa_id': _str_or_none(row.get('subtarefa_id')),
        })

    return criar_checklist_subtarefas(
        historico_items, username_atual,
        user_level=user_level, pend_id=pendencia_id
    )


def aplicar_filtros_dataframe(df, responsavel, status_list, busca, status_aceite_list=None,
                              data_inicio=None, data_fim=None):
    """Aplica filtros ao DataFrame de pendências."""
    df_filtrado = df.copy()

    if responsavel and responsavel != "todos":
        df_filtrado = df_filtrado[df_filtrado['responsavel'] == responsavel]

    if status_list and len(status_list) > 0:
        df_filtrado = df_filtrado[df_filtrado['status'].isin(status_list)]

    if status_aceite_list and len(status_aceite_list) > 0:
        if 'status_aceite' in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado['status_aceite'].isin(status_aceite_list)]

    if busca and busca.strip():
        busca_lower = busca.lower()
        mask = (
            df_filtrado['id'].str.lower().str.contains(busca_lower, na=False) |
            df_filtrado['descricao'].str.lower().str.contains(busca_lower, na=False) |
            df_filtrado['nota_gam'].astype(str).str.lower().str.contains(busca_lower, na=False)
        )
        df_filtrado = df_filtrado[mask]

    if data_inicio and 'data_criacao' in df_filtrado.columns:
        from datetime import datetime as _dt
        dt_inicio = _dt.fromisoformat(data_inicio)
        df_filtrado = df_filtrado[pd.to_datetime(df_filtrado['data_criacao']) >= dt_inicio]

    if data_fim and 'data_criacao' in df_filtrado.columns:
        from datetime import datetime as _dt, timedelta
        dt_fim = _dt.fromisoformat(data_fim) + timedelta(days=1)
        df_filtrado = df_filtrado[pd.to_datetime(df_filtrado['data_criacao']) < dt_fim]

    return df_filtrado


def reconstruir_tabela_com_filtros(df_pendencias, df_historico, filtros, user_level, username):
    """
    Reconstrói a tabela aplicando os filtros ativos do store.

    Args:
        df_pendencias: DataFrame completo de pendências (já recarregado do banco)
        df_historico: DataFrame de histórico
        filtros: dict com chaves responsavel/status/busca/status_aceite, ou None
        user_level: nível do usuário
        username: username do usuário

    Returns:
        tuple: (tabela_html, store_pendencias_data)
    """
    if filtros:
        df_filtrado = aplicar_filtros_dataframe(
            df_pendencias,
            filtros.get("responsavel", "todos"),
            filtros.get("status"),
            filtros.get("busca"),
            filtros.get("status_aceite"),
            filtros.get("data_inicio"),
            filtros.get("data_fim"),
        )
    else:
        df_filtrado = df_pendencias

    nova_tabela = criar_tabela_pendencias(
        df_filtrado, df_historico,
        user_level=user_level or 1,
        username_atual=username
    )
    store_data = df_filtrado.to_dict('records') if df_filtrado is not None else []
    return nova_tabela, store_data


# ======================================================================================
# REGISTRO DE CALLBACKS
# ======================================================================================

def register_workflow_callbacks(app):
    """Registra todos os callbacks do módulo Workflow."""

    # ==================================================================================
    # CALLBACK 0: Expand/Colapso individual de subtarefa (Pattern-Matching)
    # ==================================================================================
    @app.callback(
        Output({"type": "collapse-subtask", "index": MATCH}, "is_open"),
        Output({"type": "chevron-subtask", "index": MATCH}, "className"),
        Input({"type": "btn-expand-subtask", "index": MATCH}, "n_clicks"),
        State({"type": "collapse-subtask", "index": MATCH}, "is_open"),
        prevent_initial_call=True
    )
    def toggle_subtask_collapse(n_clicks, is_open):
        if not n_clicks:
            raise PreventUpdate
        new_open = not is_open
        chevron = "fas fa-chevron-down" if new_open else "fas fa-chevron-right"
        return new_open, chevron

    # ==================================================================================
    # CALLBACK 1: Expansão/Colapso de linha individual (Pattern-Matching)
    # ==================================================================================
    @app.callback(
        Output({"type": "collapse-historico", "index": MATCH}, "is_open"),
        Output({"type": "chevron-icon", "index": MATCH}, "className"),
        Output({"type": "historico-content", "index": MATCH}, "children"),
        Input({"type": "btn-expand", "index": MATCH}, "n_clicks"),
        State({"type": "collapse-historico", "index": MATCH}, "is_open"),
        State("store-pendencias", "data"),
        State("store-historico", "data"),
        State("user-username-store", "data"),
        State("user-level-store", "data"),
        prevent_initial_call=True
    )
    def toggle_linha_historico(n_clicks, is_open, pendencias_data, historico_data,
                               username_atual, user_level):
        """Expande/colapsa uma linha individual e carrega o histórico."""
        if not n_clicks:
            raise PreventUpdate

        df_pendencias = pd.DataFrame(pendencias_data)
        df_historico = pd.DataFrame(historico_data)

        if not df_historico.empty:
            df_historico['data'] = pd.to_datetime(df_historico['data'], format='mixed')

        triggered_id = callback_context.triggered[0]['prop_id']
        id_dict = json.loads(triggered_id.split('.')[0])
        index = id_dict['index']

        if index >= len(df_pendencias):
            raise PreventUpdate

        pendencia_id = df_pendencias.iloc[index]['id']

        # Ajustar coluna pendencia_id no histórico
        if not df_historico.empty and 'MaintenanceWF_id' in df_historico.columns and 'pendencia_id' not in df_historico.columns:
            df_historico['pendencia_id'] = df_historico['MaintenanceWF_id']

        new_is_open = not is_open
        chevron_class = "fas fa-chevron-down" if new_is_open else "fas fa-chevron-right"

        if new_is_open:
            conteudo_historico = criar_conteudo_historico(
                pendencia_id, df_historico, username_atual,
                user_level=user_level or 1
            )
        else:
            conteudo_historico = html.Div()

        return new_is_open, chevron_class, conteudo_historico


    # ==================================================================================
    # CALLBACK 2: Aplicar filtros
    # ==================================================================================
    @app.callback(
        Output("container-tabela", "children"),
        Output("store-pendencias", "data"),
        Output("store-filtros-ativos", "data"),
        Input("btn-aplicar-filtros", "n_clicks"),
        State("filtro-responsavel", "value"),
        State("filtro-status", "value"),
        State("filtro-busca", "value"),
        State("filtro-status-aceite", "value"),
        State("filtro-data-inicio", "date"),
        State("filtro-data-fim", "date"),
        State("user-level-store", "data"),
        State("user-username-store", "data"),
        prevent_initial_call=True
    )
    def aplicar_filtros(n_clicks, responsavel, status_list, busca, status_aceite_list,
                        data_inicio, data_fim, user_level, username_atual):
        """Aplica os filtros selecionados e reconstrói a tabela."""
        if not n_clicks:
            raise PreventUpdate

        df_pendencias, df_historico = carregar_dados_csv()

        if df_pendencias is None or df_pendencias.empty:
            return html.Div("Erro ao carregar dados.", className="text-danger"), [], None

        filtros = {
            "responsavel": responsavel,
            "status": status_list,
            "busca": busca,
            "status_aceite": status_aceite_list,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
        }
        nova_tabela, store_data = reconstruir_tabela_com_filtros(
            df_pendencias, df_historico, filtros, user_level, username_atual
        )
        return nova_tabela, store_data, filtros


    # ==================================================================================
    # CALLBACK 3: Refresh de dados
    # ==================================================================================
    @app.callback(
        Output("container-tabela", "children", allow_duplicate=True),
        Output("store-pendencias", "data", allow_duplicate=True),
        Output("store-historico", "data"),
        Input("btn-refresh", "n_clicks"),
        State("user-level-store", "data"),
        State("user-username-store", "data"),
        State("store-filtros-ativos", "data"),
        prevent_initial_call=True
    )
    def refresh_dados(n_clicks, user_level, username_atual, filtros):
        """Recarrega os dados e reconstrói a tabela preservando filtros ativos."""
        if not n_clicks:
            raise PreventUpdate

        df_pendencias, df_historico = carregar_dados_csv()

        if df_pendencias is None or df_historico is None:
            return html.Div("Erro ao carregar dados.", className="text-danger"), [], []

        nova_tabela, store_data = reconstruir_tabela_com_filtros(
            df_pendencias, df_historico, filtros, user_level, username_atual
        )
        return nova_tabela, store_data, df_historico.to_dict('records')


    # ==================================================================================
    # CALLBACK 4: Popular dropdown de responsáveis
    # ==================================================================================
    @app.callback(
        Output("filtro-responsavel", "options"),
        Input("store-pendencias", "data")
    )
    def popular_filtro_responsavel(pendencias_data):
        """Popula dropdown de responsáveis com usuários únicos do MongoDB."""
        from src.database.connection import get_mongo_connection

        try:
            usuarios = get_mongo_connection("usuarios")
            users = list(usuarios.find({}, {"username": 1}).sort("username", 1))

            options = [{"label": "Todos", "value": "todos"}]
            options.extend([
                {"label": u['username'], "value": u['username']}
                for u in users
            ])
            return options

        except Exception as e:
            print(f"Erro ao buscar usuários: {e}")
            return [{"label": "Todos", "value": "todos"}]


    # ==================================================================================
    # CALLBACK 5: Atualizar cards KPI
    # ==================================================================================
    @app.callback(
        Output("container-cards-kpi", "children"),
        Input("store-pendencias", "data"),
        Input("store-historico", "data"),
        State("user-username-store", "data")
    )
    def atualizar_cards_kpi(pendencias_data, historico_data, username_atual):
        """Atualiza os cards KPI quando os dados mudam."""
        df_pendencias = None
        df_historico = None

        if pendencias_data:
            df_pendencias = pd.DataFrame(pendencias_data)
            if not df_pendencias.empty:
                if 'data_criacao' in df_pendencias.columns:
                    df_pendencias['data_criacao'] = pd.to_datetime(
                        df_pendencias['data_criacao'], format='mixed'
                    )
                if 'ultima_atualizacao' in df_pendencias.columns:
                    df_pendencias['ultima_atualizacao'] = pd.to_datetime(
                        df_pendencias['ultima_atualizacao'], format='mixed'
                    )

        if historico_data:
            df_historico = pd.DataFrame(historico_data)

        return criar_cards_kpi(df_pendencias, df_historico, username_atual)


    # ==================================================================================
    # CALLBACK 6: Abrir/fechar modal de confirmação para concluir subatividade
    # O confirm é tratado apenas pelo callback 7 para evitar duplo Input
    # ==================================================================================
    @app.callback(
        Output("concluir-subtarefa-modal", "is_open"),
        Output("store-subtarefa-concluir-pending", "data"),
        Input({"type": "btn-concluir-subtarefa", "index": ALL}, "n_clicks"),
        Input("concluir-subtarefa-cancel-btn", "n_clicks"),
        State("concluir-subtarefa-modal", "is_open"),
        prevent_initial_call=True
    )
    def toggle_concluir_modal(concluir_clicks, cancel_clicks, is_open):
        """Abre modal ao clicar 'Concluir'; fecha ao cancelar."""
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate

        trigger_prop = ctx.triggered[0]['prop_id']
        trigger_id_str = trigger_prop.split('.')[0]

        # Fechar modal ao cancelar
        if 'cancel' in trigger_id_str:
            return False, no_update

        # Abrir modal ao clicar no botão de concluir
        if 'btn-concluir-subtarefa' in trigger_id_str:
            if not any(c for c in concluir_clicks if c):
                raise PreventUpdate
            id_dict = json.loads(trigger_id_str)
            hist_id = id_dict['index']
            return True, hist_id

        raise PreventUpdate


    # ==================================================================================
    # CALLBACK 7: Confirmar conclusão da subatividade
    # ==================================================================================
    @app.callback(
        Output("container-tabela", "children", allow_duplicate=True),
        Output("store-pendencias", "data", allow_duplicate=True),
        Output("store-historico", "data", allow_duplicate=True),
        Output("alert-container-workflow", "children", allow_duplicate=True),
        Output("concluir-subtarefa-modal", "is_open", allow_duplicate=True),
        Input("concluir-subtarefa-confirm-btn", "n_clicks"),
        State("store-subtarefa-concluir-pending", "data"),
        State("user-level-store", "data"),
        State("user-username-store", "data"),
        State("store-filtros-ativos", "data"),
        prevent_initial_call=True
    )
    def confirmar_concluir_subtarefa(n_clicks, hist_id, user_level, username_atual, filtros):
        """Marca a subatividade como concluída após confirmação."""
        if not n_clicks or not hist_id:
            raise PreventUpdate

        from src.utils.workflow_db import marcar_subtarefa_concluida

        sucesso = marcar_subtarefa_concluida(hist_id)

        df_pend, df_hist = carregar_dados_csv()
        nova_tabela, store_data = reconstruir_tabela_com_filtros(
            df_pend, df_hist, filtros, user_level, username_atual
        )

        if sucesso:
            alerta = dbc.Alert([
                html.I(className="fas fa-check-circle me-2"),
                "Subatividade marcada como concluída."
            ], color="success", dismissable=True, duration=5000)
        else:
            alerta = dbc.Alert([
                html.I(className="fas fa-exclamation-circle me-2"),
                "Não foi possível marcar como concluída (já concluída ou erro)."
            ], color="warning", dismissable=True, duration=5000)

        return (
            nova_tabela,
            store_data,
            df_hist.to_dict('records') if df_hist is not None else [],
            alerta,
            False  # Fechar modal
        )


    # ==================================================================================
    # CALLBACK 8: Aprovar subatividade (pattern-matching)
    # ==================================================================================
    @app.callback(
        Output("container-tabela", "children", allow_duplicate=True),
        Output("store-pendencias", "data", allow_duplicate=True),
        Output("store-historico", "data", allow_duplicate=True),
        Output("alert-container-workflow", "children", allow_duplicate=True),
        Input({"type": "btn-aprovar", "index": ALL}, "n_clicks"),
        State("user-level-store", "data"),
        State("user-username-store", "data"),
        State("store-filtros-ativos", "data"),
        prevent_initial_call=True
    )
    def aprovar_subtarefa(n_clicks, user_level, username_atual, filtros):
        """Aprova uma subatividade pendente de aprovação."""
        ctx = callback_context
        if not ctx.triggered or not any(c for c in n_clicks if c):
            raise PreventUpdate

        trigger_id_str = ctx.triggered[0]['prop_id'].split('.')[0]
        id_dict = json.loads(trigger_id_str)
        hist_id = id_dict['index']

        from src.utils.workflow_db import aprovar_ou_rejeitar

        sucesso = aprovar_ou_rejeitar(hist_id, 'aprovado')
        df_pend, df_hist = carregar_dados_csv()
        nova_tabela, store_data = reconstruir_tabela_com_filtros(
            df_pend, df_hist, filtros, user_level, username_atual
        )

        if sucesso:
            alerta = dbc.Alert([
                html.I(className="fas fa-thumbs-up me-2"),
                "Subatividade aprovada com sucesso."
            ], color="success", dismissable=True, duration=5000)
        else:
            alerta = dbc.Alert([
                html.I(className="fas fa-exclamation-circle me-2"),
                "Erro ao aprovar subatividade."
            ], color="danger", dismissable=True, duration=5000)

        return (
            nova_tabela,
            store_data,
            df_hist.to_dict('records') if df_hist is not None else [],
            alerta
        )


    # ==================================================================================
    # CALLBACK 9: Rejeitar subatividade (pattern-matching)
    # ==================================================================================
    @app.callback(
        Output("container-tabela", "children", allow_duplicate=True),
        Output("store-pendencias", "data", allow_duplicate=True),
        Output("store-historico", "data", allow_duplicate=True),
        Output("alert-container-workflow", "children", allow_duplicate=True),
        Input({"type": "btn-rejeitar", "index": ALL}, "n_clicks"),
        State("user-level-store", "data"),
        State("user-username-store", "data"),
        State("store-filtros-ativos", "data"),
        prevent_initial_call=True
    )
    def rejeitar_subtarefa(n_clicks, user_level, username_atual, filtros):
        """Rejeita uma subatividade pendente de aprovação."""
        ctx = callback_context
        if not ctx.triggered or not any(c for c in n_clicks if c):
            raise PreventUpdate

        trigger_id_str = ctx.triggered[0]['prop_id'].split('.')[0]
        id_dict = json.loads(trigger_id_str)
        hist_id = id_dict['index']

        from src.utils.workflow_db import aprovar_ou_rejeitar

        sucesso = aprovar_ou_rejeitar(hist_id, 'rejeitado')
        df_pend, df_hist = carregar_dados_csv()
        nova_tabela, store_data = reconstruir_tabela_com_filtros(
            df_pend, df_hist, filtros, user_level, username_atual
        )

        if sucesso:
            alerta = dbc.Alert([
                html.I(className="fas fa-thumbs-down me-2"),
                "Subatividade rejeitada."
            ], color="warning", dismissable=True, duration=5000)
        else:
            alerta = dbc.Alert([
                html.I(className="fas fa-exclamation-circle me-2"),
                "Erro ao rejeitar subatividade."
            ], color="danger", dismissable=True, duration=5000)

        return (
            nova_tabela,
            store_data,
            df_hist.to_dict('records') if df_hist is not None else [],
            alerta
        )


    # ==================================================================================
    # CALLBACK 10: Aceitar tarefa (responsável aceita a designação)
    # ==================================================================================
    @app.callback(
        Output("container-tabela", "children", allow_duplicate=True),
        Output("store-pendencias", "data", allow_duplicate=True),
        Output("store-historico", "data", allow_duplicate=True),
        Output("alert-container-workflow", "children", allow_duplicate=True),
        Output("container-cards-kpi", "children", allow_duplicate=True),
        Input({"type": "btn-aceitar-tarefa", "index": ALL}, "n_clicks"),
        State("user-level-store", "data"),
        State("user-username-store", "data"),
        State("store-filtros-ativos", "data"),
        prevent_initial_call=True
    )
    def aceitar_tarefa_callback(n_clicks, user_level, username_atual, filtros):
        """Aceita uma tarefa designada ao responsável."""
        ctx = callback_context
        if not ctx.triggered or not any(c for c in n_clicks if c):
            raise PreventUpdate

        trigger_id_str = ctx.triggered[0]['prop_id'].split('.')[0]
        id_dict = json.loads(trigger_id_str)
        pend_id = id_dict['index']

        from src.utils.workflow_db import aceitar_tarefa as _aceitar

        sucesso, mensagem = _aceitar(pend_id, username_atual or '')
        df_pend, df_hist = carregar_dados_csv()
        nova_tabela, store_data = reconstruir_tabela_com_filtros(
            df_pend, df_hist, filtros, user_level, username_atual
        )
        novos_kpis = criar_cards_kpi(df_pend, df_hist, username_atual)

        if sucesso:
            alerta = dbc.Alert([
                html.I(className="fas fa-check me-2"),
                mensagem
            ], color="success", dismissable=True, duration=5000)
        else:
            alerta = dbc.Alert([
                html.I(className="fas fa-exclamation-circle me-2"),
                f"Erro: {mensagem}"
            ], color="danger", dismissable=True, duration=5000)

        return (
            nova_tabela,
            store_data,
            df_hist.to_dict('records') if df_hist is not None else [],
            alerta,
            novos_kpis
        )


    # ==================================================================================
    # CALLBACK 12: Limpar filtros
    # ==================================================================================
    @app.callback(
        Output("filtro-responsavel", "value"),
        Output("filtro-status", "value"),
        Output("filtro-busca", "value"),
        Output("filtro-status-aceite", "value"),
        Output("filtro-data-inicio", "date"),
        Output("filtro-data-fim", "date"),
        Output("store-filtros-ativos", "data", allow_duplicate=True),
        Output("container-tabela", "children", allow_duplicate=True),
        Output("store-pendencias", "data", allow_duplicate=True),
        Input("btn-limpar-filtros", "n_clicks"),
        State("user-level-store", "data"),
        State("user-username-store", "data"),
        prevent_initial_call=True
    )
    def limpar_filtros(n_clicks, user_level, username_atual):
        """Limpa todos os filtros e reexibe todas as pendências."""
        if not n_clicks:
            raise PreventUpdate

        df_pendencias, df_historico = carregar_dados_csv()
        if df_pendencias is None:
            raise PreventUpdate

        nova_tabela = criar_tabela_pendencias(
            df_pendencias, df_historico,
            user_level=user_level or 1,
            username_atual=username_atual
        )
        return (
            "todos", [], "", [], None, None,  # resetar UI dos filtros + datas
            None,                             # limpar store de filtros
            nova_tabela,
            df_pendencias.to_dict('records')
        )


    # ==================================================================================
    # CALLBACK 11: Rejeitar aceite de tarefa (responsável recusa a designação)
    # ==================================================================================
    @app.callback(
        Output("container-tabela", "children", allow_duplicate=True),
        Output("store-pendencias", "data", allow_duplicate=True),
        Output("store-historico", "data", allow_duplicate=True),
        Output("alert-container-workflow", "children", allow_duplicate=True),
        Output("container-cards-kpi", "children", allow_duplicate=True),
        Input({"type": "btn-rejeitar-tarefa-aceite", "index": ALL}, "n_clicks"),
        State("user-level-store", "data"),
        State("user-username-store", "data"),
        State("store-filtros-ativos", "data"),
        prevent_initial_call=True
    )
    def rejeitar_tarefa_aceite_callback(n_clicks, user_level, username_atual, filtros):
        """Rejeita a designação de uma tarefa (responsável recusa)."""
        ctx = callback_context
        if not ctx.triggered or not any(c for c in n_clicks if c):
            raise PreventUpdate

        trigger_id_str = ctx.triggered[0]['prop_id'].split('.')[0]
        id_dict = json.loads(trigger_id_str)
        pend_id = id_dict['index']

        from src.utils.workflow_db import rejeitar_tarefa as _rejeitar

        sucesso, mensagem = _rejeitar(pend_id, username_atual or '')
        df_pend, df_hist = carregar_dados_csv()
        nova_tabela, store_data = reconstruir_tabela_com_filtros(
            df_pend, df_hist, filtros, user_level, username_atual
        )
        novos_kpis = criar_cards_kpi(df_pend, df_hist, username_atual)

        if sucesso:
            alerta = dbc.Alert([
                html.I(className="fas fa-ban me-2"),
                mensagem
            ], color="warning", dismissable=True, duration=7000)
        else:
            alerta = dbc.Alert([
                html.I(className="fas fa-exclamation-circle me-2"),
                f"Erro: {mensagem}"
            ], color="danger", dismissable=True, duration=5000)

        return (
            nova_tabela,
            store_data,
            df_hist.to_dict('records') if df_hist is not None else [],
            alerta,
            novos_kpis
        )
