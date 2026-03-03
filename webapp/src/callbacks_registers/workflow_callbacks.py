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
    criar_timeline_historico
)


# ======================================================================================
# HELPERS
# ======================================================================================

def criar_conteudo_historico(pendencia_id, df_historico, username_atual=None):
    """
    Cria o conteúdo do histórico para uma pendência específica.

    Args:
        pendencia_id: ID da pendência
        df_historico: DataFrame com todo o histórico
        username_atual: Username do usuário logado (para botões de aprovação)

    Returns:
        html.Div: Timeline do histórico + gráfico de horas
    """
    historico_pendencia = df_historico[df_historico['pendencia_id'] == pendencia_id].copy()
    historico_pendencia = historico_pendencia.sort_values('data')

    historico_items = []
    for _, row in historico_pendencia.iterrows():
        # Normalizar horas: None/NaN → None, valor numérico válido → float
        horas_raw = row.get('horas')
        try:
            horas_val = float(horas_raw) if horas_raw is not None and str(horas_raw) != 'nan' else None
        except (ValueError, TypeError):
            horas_val = None

        # Normalizar concluido: apenas bool True conta como concluído
        concluido_val = row.get('concluido') is True

        # Normalizar strings (None/NaN → None)
        def _str_or_none(v):
            return str(v) if v is not None and str(v) != 'nan' else None

        historico_items.append({
            'hist_id': row.get('hist_id', ''),
            'descricao': row['descricao'],
            'observacoes': row.get('observacoes', '') or '',
            'alteracoes': row.get('alteracoes', '') or '',
            'editado_por': row.get('editado_por', row['responsavel']),
            'responsavel': row['responsavel'],
            'data': row['data'].strftime("%d/%m/%Y %H:%M"),
            'horas': horas_val,
            'concluido': concluido_val,
            'aprovador': _str_or_none(row.get('aprovador')),
            'status_aprovacao': _str_or_none(row.get('status_aprovacao')),
        })

    timeline = criar_timeline_historico(historico_items, username_atual)

    return html.Div([timeline])


def aplicar_filtros_dataframe(df, responsavel, status_list, busca):
    """Aplica filtros ao DataFrame de pendências."""
    df_filtrado = df.copy()

    if responsavel and responsavel != "todos":
        df_filtrado = df_filtrado[df_filtrado['responsavel'] == responsavel]

    if status_list and len(status_list) > 0:
        df_filtrado = df_filtrado[df_filtrado['status'].isin(status_list)]

    if busca and busca.strip():
        busca_lower = busca.lower()
        mask = (
            df_filtrado['id'].str.lower().str.contains(busca_lower, na=False) |
            df_filtrado['descricao'].str.lower().str.contains(busca_lower, na=False)
        )
        df_filtrado = df_filtrado[mask]

    return df_filtrado


# ======================================================================================
# REGISTRO DE CALLBACKS
# ======================================================================================

def register_workflow_callbacks(app):
    """Registra todos os callbacks do módulo Workflow."""

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
            conteudo_historico = criar_conteudo_historico(pendencia_id, df_historico, username_atual)
        else:
            conteudo_historico = html.Div()

        return new_is_open, chevron_class, conteudo_historico


    # ==================================================================================
    # CALLBACK 2: Aplicar filtros
    # ==================================================================================
    @app.callback(
        Output("container-tabela", "children"),
        Output("store-pendencias", "data"),
        Input("btn-aplicar-filtros", "n_clicks"),
        State("filtro-responsavel", "value"),
        State("filtro-status", "value"),
        State("filtro-busca", "value"),
        State("user-level-store", "data"),
        State("user-username-store", "data"),
        prevent_initial_call=True
    )
    def aplicar_filtros(n_clicks, responsavel, status_list, busca, user_level, username_atual):
        """Aplica os filtros selecionados e reconstrói a tabela."""
        if not n_clicks:
            raise PreventUpdate

        df_pendencias, df_historico = carregar_dados_csv()

        if df_pendencias is None or df_pendencias.empty:
            return html.Div("Erro ao carregar dados.", className="text-danger"), []

        df_filtrado = aplicar_filtros_dataframe(df_pendencias, responsavel, status_list, busca)
        nova_tabela = criar_tabela_pendencias(df_filtrado, df_historico,
                                              user_level=user_level or 1,
                                              username_atual=username_atual)

        return nova_tabela, df_filtrado.to_dict('records')


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
        prevent_initial_call=True
    )
    def refresh_dados(n_clicks, user_level, username_atual):
        """Recarrega os dados e reconstrói a tabela."""
        if not n_clicks:
            raise PreventUpdate

        df_pendencias, df_historico = carregar_dados_csv()

        if df_pendencias is None or df_historico is None:
            return html.Div("Erro ao carregar dados.", className="text-danger"), [], []

        nova_tabela = criar_tabela_pendencias(df_pendencias, df_historico,
                                              user_level=user_level or 1,
                                              username_atual=username_atual)

        return (
            nova_tabela,
            df_pendencias.to_dict('records'),
            df_historico.to_dict('records')
        )


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
        Output("container-cards-kpi", "children", allow_duplicate=True),
        Input("store-pendencias", "data"),
        Input("store-historico", "data"),
        State("user-username-store", "data"),
        prevent_initial_call=False
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
        prevent_initial_call=True
    )
    def confirmar_concluir_subtarefa(n_clicks, hist_id, user_level, username_atual):
        """Marca a subatividade como concluída após confirmação."""
        if not n_clicks or not hist_id:
            raise PreventUpdate

        from src.utils.workflow_db import marcar_subtarefa_concluida

        sucesso = marcar_subtarefa_concluida(hist_id)

        df_pend, df_hist = carregar_dados_csv()
        nova_tabela = criar_tabela_pendencias(df_pend, df_hist,
                                              user_level=user_level or 1,
                                              username_atual=username_atual)

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
            df_pend.to_dict('records') if df_pend is not None else [],
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
        prevent_initial_call=True
    )
    def aprovar_subtarefa(n_clicks, user_level, username_atual):
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
        nova_tabela = criar_tabela_pendencias(df_pend, df_hist,
                                              user_level=user_level or 1,
                                              username_atual=username_atual)

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
            df_pend.to_dict('records') if df_pend is not None else [],
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
        prevent_initial_call=True
    )
    def rejeitar_subtarefa(n_clicks, user_level, username_atual):
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
        nova_tabela = criar_tabela_pendencias(df_pend, df_hist,
                                              user_level=user_level or 1,
                                              username_atual=username_atual)

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
            df_pend.to_dict('records') if df_pend is not None else [],
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
        prevent_initial_call=True
    )
    def aceitar_tarefa_callback(n_clicks, user_level, username_atual):
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
        nova_tabela = criar_tabela_pendencias(df_pend, df_hist,
                                              user_level=user_level or 1,
                                              username_atual=username_atual)
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
            df_pend.to_dict('records') if df_pend is not None else [],
            df_hist.to_dict('records') if df_hist is not None else [],
            alerta,
            novos_kpis
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
        prevent_initial_call=True
    )
    def rejeitar_tarefa_aceite_callback(n_clicks, user_level, username_atual):
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
        nova_tabela = criar_tabela_pendencias(df_pend, df_hist,
                                              user_level=user_level or 1,
                                              username_atual=username_atual)
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
            df_pend.to_dict('records') if df_pend is not None else [],
            df_hist.to_dict('records') if df_hist is not None else [],
            alerta,
            novos_kpis
        )
