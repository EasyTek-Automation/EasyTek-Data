"""
Callbacks para CRUD de subtarefas e logs do Workflow.

Gerencia os 4 modais de subtarefa:
- create-subtask-modal  → criar nova subtarefa
- add-log-modal         → adicionar relatório a uma subtarefa
- edit-subtask-modal    → editar subtarefa existente (nível 3)
- delete-subtask-modal  → confirmar exclusão de subtarefa (nível 3)
"""
import json
import pandas as pd

from dash import Input, Output, State, ALL, callback_context, no_update, html
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from src.utils.workflow_db import (
    criar_subtarefa,
    adicionar_log,
    editar_subtarefa,
    deletar_subtarefa,
    get_usuarios_por_perfil,
    get_usuarios_nivel3_por_perfil,
    TIPOS_REQUEREM_APROVACAO
)
from src.callbacks_registers.workflow_callbacks import reconstruir_tabela_com_filtros


def register_subtask_callbacks(app):
    """Registra callbacks de CRUD de subtarefas."""

    # ==============================================================================
    # CB1: Abrir create-subtask-modal ao clicar btn-nova-subtarefa
    # ==============================================================================
    @app.callback(
        Output("create-subtask-modal", "is_open"),
        Output("store-subtask-context", "data"),
        Input({"type": "btn-nova-subtarefa", "index": ALL}, "n_clicks"),
        State("create-subtask-modal", "is_open"),
        prevent_initial_call=True
    )
    def abrir_create_subtask_modal(n_clicks, is_open):
        ctx = callback_context
        if not ctx.triggered or not any(c for c in n_clicks if c):
            raise PreventUpdate

        trigger_id_str = ctx.triggered[0]['prop_id'].split('.')[0]
        id_dict = json.loads(trigger_id_str)
        pend_id = id_dict['index']

        return True, {"pend_id": pend_id, "subtarefa_id": None}

    # ==============================================================================
    # CB2: Fechar create-subtask-modal (Cancelar / limpar campos)
    # ==============================================================================
    @app.callback(
        Output("create-subtask-modal", "is_open", allow_duplicate=True),
        Output("create-subtask-titulo", "value"),
        Output("create-subtask-tipo", "value"),
        Output("create-subtask-responsavel", "value"),
        Output("create-subtask-obs", "value"),
        Output("create-subtask-aprovador", "value"),
        Output("create-subtask-alert", "children"),
        Input("create-subtask-cancel-btn", "n_clicks"),
        prevent_initial_call=True
    )
    def fechar_create_subtask_modal(n_clicks):
        if not n_clicks:
            raise PreventUpdate
        return False, "", None, None, "", None, ""

    # ==============================================================================
    # CB3: Mostrar/ocultar campo aprovador no create-subtask-modal
    # ==============================================================================
    @app.callback(
        Output("create-subtask-aprovador-container", "style"),
        Output("create-subtask-aprovador", "options"),
        Input("create-subtask-tipo", "value"),
        State("user-perfil-store", "data"),
        prevent_initial_call=True
    )
    def toggle_aprovador_create_subtask(tipo_evento, user_perfil):
        if tipo_evento in TIPOS_REQUEREM_APROVACAO:
            aprovadores = get_usuarios_nivel3_por_perfil(user_perfil or "admin")
            return {"display": "block"}, aprovadores
        return {"display": "none"}, []

    # ==============================================================================
    # CB4: Popular dropdown de responsáveis no create-subtask-modal
    # ==============================================================================
    @app.callback(
        Output("create-subtask-responsavel", "options"),
        Input("create-subtask-modal", "is_open"),
        State("user-perfil-store", "data")
    )
    def popular_responsavel_create_subtask(is_open, user_perfil):
        if not is_open:
            return no_update
        return get_usuarios_por_perfil(user_perfil or "admin")

    # ==============================================================================
    # CB5: Submeter nova subtarefa
    # ==============================================================================
    @app.callback(
        Output("create-subtask-modal", "is_open", allow_duplicate=True),
        Output("create-subtask-alert", "children", allow_duplicate=True),
        Output("alert-container-workflow", "children", allow_duplicate=True),
        Output("container-tabela", "children", allow_duplicate=True),
        Output("store-pendencias", "data", allow_duplicate=True),
        Output("store-historico", "data", allow_duplicate=True),
        Input("create-subtask-submit-btn", "n_clicks"),
        State("create-subtask-titulo", "value"),
        State("create-subtask-tipo", "value"),
        State("create-subtask-responsavel", "value"),
        State("create-subtask-obs", "value"),
        State("create-subtask-aprovador", "value"),
        State("store-subtask-context", "data"),
        State("user-username-store", "data"),
        State("user-level-store", "data"),
        State("store-filtros-ativos", "data"),
        prevent_initial_call=True
    )
    def submeter_create_subtask(n_clicks, titulo, tipo, responsavel, obs, aprovador,
                                context, username, user_level, filtros):
        if not n_clicks:
            raise PreventUpdate

        pend_id = (context or {}).get("pend_id")
        if not pend_id:
            raise PreventUpdate

        # Validações
        if not titulo or not titulo.strip():
            return (True,
                    dbc.Alert("O título é obrigatório.", color="warning"),
                    no_update, no_update, no_update, no_update)
        if not tipo:
            return (True,
                    dbc.Alert("Selecione o tipo de evento.", color="warning"),
                    no_update, no_update, no_update, no_update)
        if not responsavel:
            return (True,
                    dbc.Alert("Selecione o responsável.", color="warning"),
                    no_update, no_update, no_update, no_update)
        if tipo in TIPOS_REQUEREM_APROVACAO and not aprovador:
            return (True,
                    dbc.Alert(f"O tipo '{tipo}' requer aprovador.", color="warning"),
                    no_update, no_update, no_update, no_update)

        sucesso, mensagem = criar_subtarefa(
            pend_id=pend_id,
            titulo=titulo.strip(),
            tipo_evento=tipo,
            responsavel=responsavel,
            observacoes=obs.strip() if obs else '',
            editado_por=username or '',
            aprovador=aprovador if tipo in TIPOS_REQUEREM_APROVACAO else None
        )

        from src.pages.workflow.dashboard import carregar_dados_csv
        df_pend, df_hist = carregar_dados_csv()
        nova_tabela, store_data = reconstruir_tabela_com_filtros(
            df_pend, df_hist, filtros, user_level, username
        )

        if sucesso:
            return (
                False, "",
                dbc.Alert([html.I(className="fas fa-check-circle me-2"), mensagem],
                          color="success", dismissable=True, duration=5000),
                nova_tabela, store_data,
                df_hist.to_dict('records') if df_hist is not None else []
            )
        else:
            return (
                True,
                dbc.Alert(f"Erro: {mensagem}", color="danger"),
                no_update, no_update, no_update, no_update
            )

    # ==============================================================================
    # CB6: Abrir add-log-modal ao clicar btn-add-log
    # ==============================================================================
    @app.callback(
        Output("add-log-modal", "is_open"),
        Output("store-subtask-context", "data", allow_duplicate=True),
        Output("add-log-subtarefa-titulo", "children"),
        Input({"type": "btn-add-log", "index": ALL}, "n_clicks"),
        State("store-historico", "data"),
        State("store-subtask-context", "data"),
        prevent_initial_call=True
    )
    def abrir_add_log_modal(n_clicks, historico_data, context):
        ctx = callback_context
        if not ctx.triggered or not any(c for c in n_clicks if c):
            raise PreventUpdate

        trigger_id_str = ctx.triggered[0]['prop_id'].split('.')[0]
        id_dict = json.loads(trigger_id_str)
        hist_id = id_dict['index']

        # Buscar título da subtarefa
        titulo = hist_id
        if historico_data:
            df = pd.DataFrame(historico_data)
            match = df[df['hist_id'] == hist_id]
            if not match.empty:
                row = match.iloc[0]
                titulo = row.get('titulo') or row.get('descricao', hist_id) or hist_id

        pend_id = (context or {}).get("pend_id", "")
        novo_context = {"pend_id": pend_id, "subtarefa_id": hist_id}

        return True, novo_context, titulo

    # ==============================================================================
    # CB7: Fechar add-log-modal (Cancelar)
    # ==============================================================================
    @app.callback(
        Output("add-log-modal", "is_open", allow_duplicate=True),
        Output("add-log-obs", "value"),
        Output("add-log-horas", "value"),
        Output("add-log-alert", "children"),
        Input("add-log-cancel-btn", "n_clicks"),
        prevent_initial_call=True
    )
    def fechar_add_log_modal(n_clicks):
        if not n_clicks:
            raise PreventUpdate
        return False, "", None, ""

    # ==============================================================================
    # CB8: Submeter novo log
    # ==============================================================================
    @app.callback(
        Output("add-log-modal", "is_open", allow_duplicate=True),
        Output("add-log-alert", "children", allow_duplicate=True),
        Output("alert-container-workflow", "children", allow_duplicate=True),
        Output("container-tabela", "children", allow_duplicate=True),
        Output("store-pendencias", "data", allow_duplicate=True),
        Output("store-historico", "data", allow_duplicate=True),
        Input("add-log-submit-btn", "n_clicks"),
        State("add-log-obs", "value"),
        State("add-log-horas", "value"),
        State("store-subtask-context", "data"),
        State("user-username-store", "data"),
        State("user-level-store", "data"),
        State("store-filtros-ativos", "data"),
        prevent_initial_call=True
    )
    def submeter_add_log(n_clicks, obs, horas, context, username, user_level, filtros):
        if not n_clicks:
            raise PreventUpdate

        context = context or {}
        pend_id = context.get("pend_id")
        subtarefa_id = context.get("subtarefa_id")

        if not pend_id or not subtarefa_id:
            raise PreventUpdate

        if not obs or not obs.strip():
            return (True,
                    dbc.Alert("O relatório não pode estar vazio.", color="warning"),
                    no_update, no_update, no_update, no_update)

        horas_val = float(horas) if horas is not None else None
        sucesso, mensagem = adicionar_log(
            subtarefa_hist_id=subtarefa_id,
            pend_id=pend_id,
            observacoes=obs.strip(),
            editado_por=username or '',
            horas=horas_val
        )

        from src.pages.workflow.dashboard import carregar_dados_csv
        df_pend, df_hist = carregar_dados_csv()
        nova_tabela, store_data = reconstruir_tabela_com_filtros(
            df_pend, df_hist, filtros, user_level, username
        )

        if sucesso:
            return (
                False, "",
                dbc.Alert([html.I(className="fas fa-check-circle me-2"), mensagem],
                          color="success", dismissable=True, duration=5000),
                nova_tabela, store_data,
                df_hist.to_dict('records') if df_hist is not None else []
            )
        else:
            return (
                True,
                dbc.Alert(f"Erro: {mensagem}", color="danger"),
                no_update, no_update, no_update, no_update
            )

    # ==============================================================================
    # CB9: Abrir edit-subtask-modal ao clicar btn-edit-subtarefa
    # ==============================================================================
    @app.callback(
        Output("edit-subtask-modal", "is_open"),
        Output("edit-subtask-hist-id", "data"),
        Output("edit-subtask-titulo", "value"),
        Output("edit-subtask-tipo", "value"),
        Output("edit-subtask-obs", "value"),
        Output("edit-subtask-concluido", "value"),
        Input({"type": "btn-edit-subtarefa", "index": ALL}, "n_clicks"),
        State("store-historico", "data"),
        prevent_initial_call=True
    )
    def abrir_edit_subtask_modal(n_clicks, historico_data):
        ctx = callback_context
        if not ctx.triggered or not any(c for c in n_clicks if c):
            raise PreventUpdate

        trigger_id_str = ctx.triggered[0]['prop_id'].split('.')[0]
        id_dict = json.loads(trigger_id_str)
        hist_id = id_dict['index']

        # Buscar dados da subtarefa
        titulo_val = ""
        tipo_val = None
        obs_val = ""
        concluido_val = False

        if historico_data:
            df = pd.DataFrame(historico_data)
            match = df[df['hist_id'] == hist_id]
            if not match.empty:
                row = match.iloc[0]
                titulo_val = row.get('titulo') or row.get('descricao', '') or ''
                tipo_val = row.get('tipo_evento')
                obs_val = row.get('observacoes', '') or ''
                concluido_val = row.get('concluido') is True

        return True, hist_id, titulo_val, tipo_val, obs_val, concluido_val

    # ==============================================================================
    # CB10: Fechar edit-subtask-modal (Cancelar)
    # ==============================================================================
    @app.callback(
        Output("edit-subtask-modal", "is_open", allow_duplicate=True),
        Output("edit-subtask-alert", "children"),
        Input("edit-subtask-cancel-btn", "n_clicks"),
        prevent_initial_call=True
    )
    def fechar_edit_subtask_modal(n_clicks):
        if not n_clicks:
            raise PreventUpdate
        return False, ""

    # ==============================================================================
    # CB11: Submeter edição de subtarefa
    # ==============================================================================
    @app.callback(
        Output("edit-subtask-modal", "is_open", allow_duplicate=True),
        Output("edit-subtask-alert", "children", allow_duplicate=True),
        Output("alert-container-workflow", "children", allow_duplicate=True),
        Output("container-tabela", "children", allow_duplicate=True),
        Output("store-pendencias", "data", allow_duplicate=True),
        Output("store-historico", "data", allow_duplicate=True),
        Input("edit-subtask-submit-btn", "n_clicks"),
        State("edit-subtask-hist-id", "data"),
        State("edit-subtask-titulo", "value"),
        State("edit-subtask-tipo", "value"),
        State("edit-subtask-obs", "value"),
        State("edit-subtask-concluido", "value"),
        State("user-username-store", "data"),
        State("user-level-store", "data"),
        State("store-filtros-ativos", "data"),
        prevent_initial_call=True
    )
    def submeter_edit_subtask(n_clicks, hist_id, titulo, tipo, obs, concluido,
                              username, user_level, filtros):
        if not n_clicks or not hist_id:
            raise PreventUpdate

        obs_val = obs.strip() if obs else None

        sucesso, mensagem = editar_subtarefa(
            hist_id=hist_id,
            titulo=titulo.strip() if titulo else None,
            tipo_evento=tipo if tipo else None,
            observacoes=obs_val,
            concluido=bool(concluido) if concluido is not None else None
        )

        from src.pages.workflow.dashboard import carregar_dados_csv
        df_pend, df_hist = carregar_dados_csv()
        nova_tabela, store_data = reconstruir_tabela_com_filtros(
            df_pend, df_hist, filtros, user_level, username
        )

        if sucesso:
            return (
                False, "",
                dbc.Alert([html.I(className="fas fa-check-circle me-2"), mensagem],
                          color="success", dismissable=True, duration=5000),
                nova_tabela, store_data,
                df_hist.to_dict('records') if df_hist is not None else []
            )
        else:
            return (
                True,
                dbc.Alert(f"Erro: {mensagem}", color="danger"),
                no_update, no_update, no_update, no_update
            )

    # ==============================================================================
    # CB12: Abrir delete-subtask-modal ao clicar btn-delete-subtarefa
    # ==============================================================================
    @app.callback(
        Output("delete-subtask-modal", "is_open"),
        Output("delete-subtask-id-display", "children"),
        Output("store-subtask-context", "data", allow_duplicate=True),
        Input({"type": "btn-delete-subtarefa", "index": ALL}, "n_clicks"),
        State("store-subtask-context", "data"),
        prevent_initial_call=True
    )
    def abrir_delete_subtask_modal(n_clicks, context):
        ctx = callback_context
        if not ctx.triggered or not any(c for c in n_clicks if c):
            raise PreventUpdate

        trigger_id_str = ctx.triggered[0]['prop_id'].split('.')[0]
        id_dict = json.loads(trigger_id_str)
        hist_id = id_dict['index']

        context = context or {}
        novo_context = {**context, "subtarefa_id": hist_id}

        return True, hist_id[:8] + "...", novo_context

    # ==============================================================================
    # CB13: Fechar delete-subtask-modal (Cancelar)
    # ==============================================================================
    @app.callback(
        Output("delete-subtask-modal", "is_open", allow_duplicate=True),
        Input("delete-subtask-cancel-btn", "n_clicks"),
        prevent_initial_call=True
    )
    def fechar_delete_subtask_modal(n_clicks):
        if not n_clicks:
            raise PreventUpdate
        return False

    # ==============================================================================
    # CB14: Confirmar exclusão de subtarefa
    # ==============================================================================
    @app.callback(
        Output("delete-subtask-modal", "is_open", allow_duplicate=True),
        Output("alert-container-workflow", "children", allow_duplicate=True),
        Output("container-tabela", "children", allow_duplicate=True),
        Output("store-pendencias", "data", allow_duplicate=True),
        Output("store-historico", "data", allow_duplicate=True),
        Input("delete-subtask-submit-btn", "n_clicks"),
        State("store-subtask-context", "data"),
        State("user-username-store", "data"),
        State("user-level-store", "data"),
        State("store-filtros-ativos", "data"),
        prevent_initial_call=True
    )
    def confirmar_delete_subtask(n_clicks, context, username, user_level, filtros):
        if not n_clicks:
            raise PreventUpdate

        hist_id = (context or {}).get("subtarefa_id")
        if not hist_id:
            raise PreventUpdate

        sucesso, mensagem = deletar_subtarefa(hist_id)

        from src.pages.workflow.dashboard import carregar_dados_csv
        df_pend, df_hist = carregar_dados_csv()
        nova_tabela, store_data = reconstruir_tabela_com_filtros(
            df_pend, df_hist, filtros, user_level, username
        )

        if sucesso:
            return (
                False,
                dbc.Alert([html.I(className="fas fa-check-circle me-2"), mensagem],
                          color="success", dismissable=True, duration=5000),
                nova_tabela, store_data,
                df_hist.to_dict('records') if df_hist is not None else []
            )
        else:
            return (
                False,
                dbc.Alert([html.I(className="fas fa-exclamation-circle me-2"), f"Erro: {mensagem}"],
                          color="danger", dismissable=True, duration=5000),
                nova_tabela, store_data,
                df_hist.to_dict('records') if df_hist is not None else []
            )

    # ==============================================================================
    # CB15: Abrir / fechar modal de migração
    # ==============================================================================
    @app.callback(
        Output("migration-modal", "is_open"),
        Output("migration-result", "children"),
        Input("btn-open-migration", "n_clicks"),
        Input("btn-close-migration", "n_clicks"),
        State("migration-modal", "is_open"),
        prevent_initial_call=True
    )
    def toggle_migration_modal(open_clicks, close_clicks, is_open):
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate
        trigger = ctx.triggered[0]['prop_id'].split('.')[0]
        if trigger == "btn-open-migration":
            return True, ""
        return False, ""

    # ==============================================================================
    # CB16: Executar migração de record_type
    # ==============================================================================
    @app.callback(
        Output("migration-result", "children", allow_duplicate=True),
        Output("btn-run-migration", "disabled"),
        Input("btn-run-migration", "n_clicks"),
        State("user-level-store", "data"),
        prevent_initial_call=True
    )
    def executar_migracao(n_clicks, user_level):
        if not n_clicks:
            raise PreventUpdate

        # Apenas nível 3
        if (user_level or 1) < 3:
            return dbc.Alert("Permissão negada.", color="danger"), False

        try:
            from src.database.connection import get_mongo_connection
            collection = get_mongo_connection("MaintenanceHistory_workflow")

            sem_campo = list(collection.find({"record_type": {"$exists": False}}))
            total = len(sem_campo)

            if total == 0:
                return dbc.Alert([
                    html.I(className="fas fa-check-circle me-2"),
                    "Nenhum documento precisava de migração. Tudo já está atualizado."
                ], color="success"), False

            criacao_count = 0
            subtarefa_count = 0

            for doc in sem_campo:
                tipo_evento = doc.get('tipo_evento', '')
                record_type = 'criacao' if tipo_evento == 'criacao' else 'subtarefa'
                if record_type == 'criacao':
                    criacao_count += 1
                else:
                    subtarefa_count += 1

                collection.update_one(
                    {'_id': doc['_id']},
                    {'$set': {'record_type': record_type, 'subtarefa_id': None}}
                )

            return dbc.Alert([
                html.I(className="fas fa-check-circle me-2"),
                html.Strong(f"Migração concluída! {total} documento(s) atualizados."),
                html.Br(),
                html.Small([
                    f"→ {criacao_count} marcado(s) como 'criacao'  |  "
                    f"{subtarefa_count} marcado(s) como 'subtarefa'"
                ], className="text-muted")
            ], color="success"), True  # desabilita botão após executar

        except Exception as e:
            return dbc.Alert(f"Erro durante migração: {e}", color="danger"), False
