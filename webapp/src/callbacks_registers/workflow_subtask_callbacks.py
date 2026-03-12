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
    editar_log,
    deletar_subtarefa,
    get_usuarios_por_perfil,
    get_usuarios_nivel3_por_perfil,
    TIPOS_REQUEREM_APROVACAO,
    validar_atividade,
    devolver_atividade,
)
from src.callbacks_registers.workflow_callbacks import reconstruir_tabela_com_filtros
from src.pages.workflow.dashboard import hhmm_para_float


def register_subtask_callbacks(app):
    """Registra callbacks de CRUD de subtarefas."""

    # ==============================================================================
    # CB1: Abrir create-subtask-modal ao clicar btn-nova-subtarefa
    # ==============================================================================
    @app.callback(
        Output("create-subtask-modal", "is_open"),
        Output("store-subtask-context", "data"),
        Output("create-subtask-titulo", "value", allow_duplicate=True),
        Output("create-subtask-tipo", "value", allow_duplicate=True),
        Output("create-subtask-responsavel", "value", allow_duplicate=True),
        Output("create-subtask-obs", "value", allow_duplicate=True),
        Output("create-subtask-aprovador", "value", allow_duplicate=True),
        Output("create-subtask-data-retroativa", "date", allow_duplicate=True),
        Output("create-subtask-alert", "children", allow_duplicate=True),
        Output("create-subtask-is-retroativo", "value", allow_duplicate=True),
        Output("create-subtask-responsavel-retroativo", "value", allow_duplicate=True),
        Output("create-subtask-aprovador-retroativo", "value", allow_duplicate=True),
        Output("create-subtask-prioridade", "value", allow_duplicate=True),
        Output("create-subtask-data-planejada", "date", allow_duplicate=True),
        Input({"type": "btn-nova-subtarefa", "index": ALL}, "n_clicks"),
        State("create-subtask-modal", "is_open"),
        State("user-username-store", "data"),
        prevent_initial_call=True
    )
    def abrir_create_subtask_modal(n_clicks, is_open, username):
        ctx = callback_context
        if not ctx.triggered or not any(c for c in n_clicks if c):
            raise PreventUpdate

        trigger_id_str = ctx.triggered[0]['prop_id'].split('.')[0]
        id_dict = json.loads(trigger_id_str)
        pend_id = id_dict['index']

        return True, {"pend_id": pend_id, "subtarefa_id": None}, "", None, username or None, "", None, None, "", False, None, None, "normal", None

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
        Output("create-subtask-data-retroativa", "date"),
        Output("create-subtask-alert", "children"),
        Output("create-subtask-is-retroativo", "value"),
        Output("create-subtask-responsavel-retroativo", "value"),
        Output("create-subtask-aprovador-retroativo", "value"),
        Output("create-subtask-prioridade", "value"),
        Output("create-subtask-data-planejada", "date"),
        Input("create-subtask-cancel-btn", "n_clicks"),
        prevent_initial_call=True
    )
    def fechar_create_subtask_modal(n_clicks):
        if not n_clicks:
            raise PreventUpdate
        return False, "", None, None, "", None, None, "", False, None, None, "normal", None

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
    # CB3b: Mostrar/ocultar seção retroativo ao ligar/desligar o switch
    # ==============================================================================
    @app.callback(
        Output("create-subtask-retroativo-container", "style"),
        Input("create-subtask-is-retroativo", "value"),
        prevent_initial_call=True
    )
    def toggle_retroativo_create(is_retroativo):
        if is_retroativo:
            return {"display": "block"}
        return {"display": "none"}

    # ==============================================================================
    # CB3c: Popular dropdowns responsavel-retroativo e aprovador-retroativo (create modal)
    # ==============================================================================
    @app.callback(
        Output("create-subtask-responsavel-retroativo", "options"),
        Output("create-subtask-aprovador-retroativo", "options"),
        Input("create-subtask-modal", "is_open"),
        State("user-perfil-store", "data")
    )
    def popular_retroativo_dropdowns_create(is_open, user_perfil):
        if not is_open:
            return no_update, no_update
        todos = get_usuarios_por_perfil(user_perfil or "admin")
        aprovadores = get_usuarios_nivel3_por_perfil(user_perfil or "admin")
        return todos, aprovadores

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
        State("create-subtask-data-retroativa", "date"),
        State("create-subtask-is-retroativo", "value"),
        State("create-subtask-responsavel-retroativo", "value"),
        State("create-subtask-aprovador-retroativo", "value"),
        State("create-subtask-prioridade", "value"),
        State("create-subtask-data-planejada", "date"),
        State("store-subtask-context", "data"),
        State("user-username-store", "data"),
        State("user-level-store", "data"),
        State("store-filtros-ativos", "data"),
        prevent_initial_call=True
    )
    def submeter_create_subtask(n_clicks, titulo, tipo, responsavel, obs, aprovador,
                                data_retroativa, is_retroativo, responsavel_retroativo,
                                aprovador_retroativo, prioridade, data_planejada_str,
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
        if is_retroativo and not data_retroativa:
            return (True,
                    dbc.Alert("Informe a data da ocorrência para o lançamento retroativo.", color="warning"),
                    no_update, no_update, no_update, no_update)
        if is_retroativo and not responsavel_retroativo:
            return (True,
                    dbc.Alert("Informe o responsável pelo lançamento retroativo.", color="warning"),
                    no_update, no_update, no_update, no_update)
        if is_retroativo and not aprovador_retroativo:
            return (True,
                    dbc.Alert("Informe o aprovador do lançamento retroativo.", color="warning"),
                    no_update, no_update, no_update, no_update)

        # Converter datas de string ISO para datetime
        from datetime import datetime as _dt
        data_retro_dt = None
        if is_retroativo and data_retroativa:
            try:
                data_retro_dt = _dt.fromisoformat(data_retroativa)
            except (ValueError, TypeError):
                data_retro_dt = None

        data_planejada_dt = None
        if data_planejada_str:
            try:
                data_planejada_dt = _dt.fromisoformat(data_planejada_str)
            except (ValueError, TypeError):
                data_planejada_dt = None

        sucesso, mensagem = criar_subtarefa(
            pend_id=pend_id,
            titulo=titulo.strip(),
            tipo_evento=tipo,
            responsavel=responsavel,
            observacoes=obs.strip() if obs else '',
            editado_por=username or '',
            aprovador=aprovador if tipo in TIPOS_REQUEREM_APROVACAO else None,
            data_retroativa=data_retro_dt,
            is_retroativo=bool(is_retroativo),
            responsavel_retroativo=responsavel_retroativo if is_retroativo else None,
            aprovador_retroativo=aprovador_retroativo if is_retroativo else None,
            prioridade=prioridade or 'normal',
            data_planejada=data_planejada_dt,
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
        Output("add-log-obs", "value", allow_duplicate=True),
        Output("add-log-horas", "value", allow_duplicate=True),
        Output("add-log-alert", "children", allow_duplicate=True),
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
                _t = row.get('titulo')
                _d = row.get('descricao')
                titulo = (str(_t) if _t and str(_t) != 'nan' else None) or \
                         (str(_d) if _d and str(_d) != 'nan' else None) or hist_id

        pend_id = (context or {}).get("pend_id", "")

        # Se pend_id não está no contexto, busca a partir do historico_data
        if not pend_id and historico_data:
            df_h = pd.DataFrame(historico_data)
            col_id = 'pendencia_id' if 'pendencia_id' in df_h.columns else 'MaintenanceWF_id'
            match_sub = df_h[df_h['hist_id'] == hist_id]
            if not match_sub.empty:
                val = match_sub.iloc[0].get(col_id)
                if val and str(val) != 'nan':
                    pend_id = str(val)

        novo_context = {"pend_id": pend_id, "subtarefa_id": hist_id}

        return True, novo_context, titulo, "", "", ""

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
        return False, "", "", ""

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

        horas_val = hhmm_para_float(horas) if horas else None
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
        Output("edit-subtask-aprovador", "value"),
        Output("edit-subtask-data-retroativa", "date"),
        Output("edit-subtask-is-retroativo", "value"),
        Output("edit-subtask-responsavel-retroativo", "value"),
        Output("edit-subtask-aprovador-retroativo", "value"),
        Output("edit-subtask-prioridade", "value"),
        Output("edit-subtask-data-planejada", "date"),
        Output("edit-subtask-data-execucao", "date"),
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

        titulo_val = ""
        tipo_val = None
        obs_val = ""
        concluido_val = False
        aprovador_val = None
        data_retro_val = None
        is_retro_val = False
        resp_retro_val = None
        aprov_retro_val = None
        prioridade_val = "normal"
        data_planejada_val = None
        data_execucao_val = None

        if historico_data:
            df = pd.DataFrame(historico_data)
            match = df[df['hist_id'] == hist_id]
            if not match.empty:
                row = match.iloc[0]
                _t = row.get('titulo')
                _d = row.get('descricao')
                titulo_val = (str(_t) if _t and str(_t) != 'nan' else None) or \
                             (str(_d) if _d and str(_d) != 'nan' else None) or ''
                tipo_val = row.get('tipo_evento')
                obs_val = row.get('observacoes', '') or ''
                concluido_val = row.get('concluido') is True
                _aprov = row.get('aprovador')
                aprovador_val = str(_aprov) if _aprov and str(_aprov) != 'nan' else None
                dr_raw = row.get('data_retroativa')
                data_retro_val = str(dr_raw)[:10] if dr_raw and str(dr_raw) != 'nan' else None
                # Retrocompat: is_retroativo pode vir do campo novo ou do tipo_evento antigo
                is_retro_val = bool(row.get('is_retroativo')) or (tipo_val == 'Lançamento Retroativo')
                _rr = row.get('responsavel_retroativo')
                resp_retro_val = str(_rr) if _rr and str(_rr) != 'nan' else None
                _ar = row.get('aprovador_retroativo')
                aprov_retro_val = str(_ar) if _ar and str(_ar) != 'nan' else None
                _p = row.get('prioridade')
                prioridade_val = str(_p) if _p and str(_p) != 'nan' else 'normal'
                dp_raw = row.get('data_planejada')
                data_planejada_val = str(dp_raw)[:10] if dp_raw and str(dp_raw) != 'nan' else None
                de_raw = row.get('data_execucao')
                data_execucao_val = str(de_raw)[:10] if de_raw and str(de_raw) != 'nan' else None

        return (True, hist_id, titulo_val, tipo_val, obs_val, concluido_val, aprovador_val,
                data_retro_val, is_retro_val, resp_retro_val, aprov_retro_val, prioridade_val,
                data_planejada_val, data_execucao_val)

    # ==============================================================================
    # CB9b: Toggle visibilidade aprovador no edit modal (por tipo de evento)
    # ==============================================================================
    @app.callback(
        Output("edit-subtask-aprovador-container", "style"),
        Input("edit-subtask-tipo", "value"),
        prevent_initial_call=True
    )
    def toggle_edit_aprovador_container(tipo):
        if tipo in TIPOS_REQUEREM_APROVACAO:
            return {"display": "block"}
        return {"display": "none"}

    # ==============================================================================
    # CB9b2: Toggle visibilidade seção retroativo no edit modal (por switch)
    # ==============================================================================
    @app.callback(
        Output("edit-subtask-retroativo-container", "style"),
        Input("edit-subtask-is-retroativo", "value"),
        prevent_initial_call=True
    )
    def toggle_edit_retroativo_container(is_retroativo):
        if is_retroativo:
            return {"display": "block"}
        return {"display": "none"}

    # ==============================================================================
    # CB9b3: Popular dropdowns responsavel-retroativo e aprovador-retroativo no edit modal
    # ==============================================================================
    @app.callback(
        Output("edit-subtask-responsavel-retroativo", "options"),
        Output("edit-subtask-aprovador-retroativo", "options"),
        Input("edit-subtask-modal", "is_open"),
        State("user-perfil-store", "data"),
    )
    def popular_retroativo_dropdowns_edit(is_open, user_perfil):
        if not is_open:
            return no_update, no_update
        todos = get_usuarios_por_perfil(user_perfil or "admin")
        aprovadores = get_usuarios_nivel3_por_perfil(user_perfil or "admin")
        return todos, aprovadores

    # ==============================================================================
    # CB9c: Popular dropdown aprovador no edit modal
    # ==============================================================================
    @app.callback(
        Output("edit-subtask-aprovador", "options"),
        Input("edit-subtask-modal", "is_open"),
        State("user-perfil-store", "data"),
    )
    def popular_edit_aprovador(is_open, user_perfil):
        if not is_open:
            return no_update
        return get_usuarios_nivel3_por_perfil(user_perfil or "admin")

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
        State("edit-subtask-aprovador", "value"),
        State("edit-subtask-data-retroativa", "date"),
        State("edit-subtask-is-retroativo", "value"),
        State("edit-subtask-responsavel-retroativo", "value"),
        State("edit-subtask-aprovador-retroativo", "value"),
        State("edit-subtask-prioridade", "value"),
        State("edit-subtask-data-planejada", "date"),
        State("edit-subtask-data-execucao", "date"),
        State("user-username-store", "data"),
        State("user-level-store", "data"),
        State("store-filtros-ativos", "data"),
        prevent_initial_call=True
    )
    def submeter_edit_subtask(n_clicks, hist_id, titulo, tipo, obs, concluido,
                              aprovador, data_retroativa, is_retroativo, responsavel_retroativo,
                              aprovador_retroativo, prioridade, data_planejada_str,
                              data_execucao_str, username, user_level, filtros):
        if not n_clicks or not hist_id:
            raise PreventUpdate

        obs_val = obs.strip() if obs else None

        from datetime import datetime as _dt
        data_retro_dt = None
        if is_retroativo and data_retroativa:
            try:
                data_retro_dt = _dt.fromisoformat(data_retroativa)
            except (ValueError, TypeError):
                data_retro_dt = None

        data_planejada_dt = None
        if data_planejada_str:
            try:
                data_planejada_dt = _dt.fromisoformat(data_planejada_str)
            except (ValueError, TypeError):
                data_planejada_dt = None

        data_execucao_dt = None
        if data_execucao_str:
            try:
                data_execucao_dt = _dt.fromisoformat(data_execucao_str)
            except (ValueError, TypeError):
                data_execucao_dt = None

        sucesso, mensagem = editar_subtarefa(
            hist_id=hist_id,
            titulo=titulo.strip() if titulo else None,
            tipo_evento=tipo if tipo else None,
            observacoes=obs_val,
            concluido=bool(concluido) if concluido is not None else None,
            aprovador=aprovador,
            update_aprovador=True,
            data_retroativa=data_retro_dt,
            update_data_retroativa=True,
            is_retroativo=bool(is_retroativo),
            responsavel_retroativo=responsavel_retroativo if is_retroativo else None,
            aprovador_retroativo=aprovador_retroativo if is_retroativo else None,
            update_retroativo=True,
            prioridade=prioridade or 'normal',
            data_planejada=data_planejada_dt,
            update_data_planejada=True,
            data_execucao=data_execucao_dt,
            update_data_execucao=True,
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
    # CB14b: Alterar prioridade inline (ClickUp-style badge)
    # index format: "{hist_id}__{prioridade}"
    # ==============================================================================
    @app.callback(
        Output("alert-container-workflow", "children", allow_duplicate=True),
        Output("container-tabela", "children", allow_duplicate=True),
        Output("store-pendencias", "data", allow_duplicate=True),
        Output("store-historico", "data", allow_duplicate=True),
        Input({"type": "set-prioridade", "index": ALL}, "n_clicks"),
        State("user-username-store", "data"),
        State("user-level-store", "data"),
        State("store-filtros-ativos", "data"),
        prevent_initial_call=True
    )
    def set_prioridade_inline(n_clicks, username, user_level, filtros):
        ctx = callback_context
        if not ctx.triggered or not any(c for c in n_clicks if c):
            raise PreventUpdate

        trigger_id_str = ctx.triggered[0]['prop_id'].split('.')[0]
        id_dict = json.loads(trigger_id_str)
        index_val = id_dict['index']  # "{hist_id}__{prioridade}"

        parts = index_val.rsplit('__', 1)
        if len(parts) != 2:
            raise PreventUpdate
        hist_id, nova_prioridade = parts

        sucesso, mensagem = editar_subtarefa(hist_id=hist_id, prioridade=nova_prioridade)

        from src.pages.workflow.dashboard import carregar_dados_csv
        df_pend, df_hist = carregar_dados_csv()
        nova_tabela, store_data = reconstruir_tabela_com_filtros(
            df_pend, df_hist, filtros, user_level, username
        )

        if sucesso:
            return (
                dbc.Alert([html.I(className="fas fa-check-circle me-2"),
                           f"Prioridade alterada para {nova_prioridade}."],
                          color="success", dismissable=True, duration=3000),
                nova_tabela, store_data,
                df_hist.to_dict('records') if df_hist is not None else []
            )
        else:
            return (
                dbc.Alert(f"Erro: {mensagem}", color="danger", dismissable=True, duration=4000),
                nova_tabela, store_data,
                df_hist.to_dict('records') if df_hist is not None else []
            )

    # ==============================================================================
    # CB_V1: Validar atividade (Gestor - nível 4)
    # ==============================================================================
    @app.callback(
        Output("alert-container-workflow", "children", allow_duplicate=True),
        Output("container-tabela", "children", allow_duplicate=True),
        Output("store-pendencias", "data", allow_duplicate=True),
        Output("store-historico", "data", allow_duplicate=True),
        Input({"type": "btn-validar-atividade", "index": ALL}, "n_clicks"),
        State("user-username-store", "data"),
        State("user-level-store", "data"),
        State("store-filtros-ativos", "data"),
        prevent_initial_call=True
    )
    def validar_atividade_callback(n_clicks, username, user_level, filtros):
        ctx = callback_context
        if not ctx.triggered or not any(c for c in n_clicks if c):
            raise PreventUpdate

        trigger_id_str = ctx.triggered[0]['prop_id'].split('.')[0]
        id_dict = json.loads(trigger_id_str)
        hist_id = id_dict['index']

        sucesso = validar_atividade(hist_id, validado_por=username or '')

        from src.pages.workflow.dashboard import carregar_dados_csv
        df_pend, df_hist = carregar_dados_csv()
        nova_tabela, store_data = reconstruir_tabela_com_filtros(
            df_pend, df_hist, filtros, user_level, username
        )

        if sucesso:
            alerta = dbc.Alert([
                html.I(className="fas fa-user-check me-2"),
                "Atividade validada pelo gestor."
            ], color="success", dismissable=True, duration=5000)
        else:
            alerta = dbc.Alert([
                html.I(className="fas fa-exclamation-circle me-2"),
                "Erro ao validar atividade."
            ], color="danger", dismissable=True, duration=5000)

        return (
            alerta,
            nova_tabela,
            store_data,
            df_hist.to_dict('records') if df_hist is not None else []
        )

    # ==============================================================================
    # CB_D1: Abrir modal de devolução (Gestor - nível 4)
    # ==============================================================================
    @app.callback(
        Output("devolver-atividade-modal", "is_open"),
        Output("devolver-atividade-hist-id", "data"),
        Output("devolver-atividade-nota", "value", allow_duplicate=True),
        Output("devolver-atividade-alert", "children", allow_duplicate=True),
        Input({"type": "btn-devolver-atividade", "index": ALL}, "n_clicks"),
        prevent_initial_call=True
    )
    def abrir_devolver_modal(n_clicks):
        ctx = callback_context
        if not ctx.triggered or not any(c for c in n_clicks if c):
            raise PreventUpdate

        trigger_id_str = ctx.triggered[0]['prop_id'].split('.')[0]
        id_dict = json.loads(trigger_id_str)
        hist_id = id_dict['index']

        return True, hist_id, "", ""

    # ==============================================================================
    # CB_D2: Fechar modal de devolução (Cancelar)
    # ==============================================================================
    @app.callback(
        Output("devolver-atividade-modal", "is_open", allow_duplicate=True),
        Output("devolver-atividade-nota", "value"),
        Output("devolver-atividade-alert", "children"),
        Input("devolver-atividade-cancel-btn", "n_clicks"),
        prevent_initial_call=True
    )
    def fechar_devolver_modal(n_clicks):
        if not n_clicks:
            raise PreventUpdate
        return False, "", ""

    # ==============================================================================
    # CB_D3: Submeter devolução
    # ==============================================================================
    @app.callback(
        Output("devolver-atividade-modal", "is_open", allow_duplicate=True),
        Output("devolver-atividade-alert", "children", allow_duplicate=True),
        Output("alert-container-workflow", "children", allow_duplicate=True),
        Output("container-tabela", "children", allow_duplicate=True),
        Output("store-pendencias", "data", allow_duplicate=True),
        Output("store-historico", "data", allow_duplicate=True),
        Input("devolver-atividade-submit-btn", "n_clicks"),
        State("devolver-atividade-hist-id", "data"),
        State("devolver-atividade-nota", "value"),
        State("user-username-store", "data"),
        State("user-level-store", "data"),
        State("store-filtros-ativos", "data"),
        prevent_initial_call=True
    )
    def submeter_devolver(n_clicks, hist_id, nota, username, user_level, filtros):
        if not n_clicks or not hist_id:
            raise PreventUpdate

        if not nota or not nota.strip():
            return (
                True,
                dbc.Alert("A nota de devolução é obrigatória.", color="warning"),
                no_update, no_update, no_update, no_update
            )

        sucesso = devolver_atividade(
            hist_id_str=hist_id,
            nota_devolucao=nota.strip(),
            devolvido_por=username or ''
        )

        from src.pages.workflow.dashboard import carregar_dados_csv
        df_pend, df_hist = carregar_dados_csv()
        nova_tabela, store_data = reconstruir_tabela_com_filtros(
            df_pend, df_hist, filtros, user_level, username
        )

        if sucesso:
            return (
                False, "",
                dbc.Alert([html.I(className="fas fa-undo me-2"), "Atividade devolvida para revisão."],
                          color="warning", dismissable=True, duration=6000),
                nova_tabela, store_data,
                df_hist.to_dict('records') if df_hist is not None else []
            )
        else:
            return (
                True,
                dbc.Alert("Erro ao devolver atividade.", color="danger"),
                no_update, no_update, no_update, no_update
            )

    # ==============================================================================
    # CB15: Auto-format campo HH:MM ao perder foco (add-log-modal)
    # ==============================================================================
    _HHMM_JS = """
        function(n_blur, value) {
            if (!value) return '';
            value = String(value).trim().replace(',', '.');
            if (/^\\d+:\\d{1,2}$/.test(value)) {
                var parts = value.split(':');
                var h = parseInt(parts[0], 10);
                var m = parseInt(parts[1], 10);
                if (isNaN(h) || isNaN(m) || m > 59) return '';
                return String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0');
            }
            if (/^\\d*\\.?\\d+$/.test(value)) {
                var hours = parseFloat(value);
                var h = Math.floor(hours);
                var m = Math.round((hours - h) * 60);
                if (m >= 60) { h += 1; m = 0; }
                return String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0');
            }
            if (/^\\d{3,4}$/.test(value)) {
                var padded = value.padStart(4, '0');
                var h = parseInt(padded.slice(0, -2), 10);
                var m = parseInt(padded.slice(-2), 10);
                if (m > 59) return '';
                return String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0');
            }
            return '';
        }
        """
    app.clientside_callback(
        _HHMM_JS,
        Output("add-log-horas", "value", allow_duplicate=True),
        Input("add-log-horas", "n_blur"),
        State("add-log-horas", "value"),
        prevent_initial_call=True
    )

    # ==============================================================================
    # CB15b: Auto-format campo HH:MM ao perder foco (edit-log-modal)
    # ==============================================================================
    app.clientside_callback(
        _HHMM_JS,
        Output("edit-log-horas-input", "value", allow_duplicate=True),
        Input("edit-log-horas-input", "n_blur"),
        State("edit-log-horas-input", "value"),
        prevent_initial_call=True
    )

    # ==============================================================================
    # CB16: Abrir edit-log-modal ao clicar btn-edit-log
    # ==============================================================================
    @app.callback(
        Output("edit-log-modal", "is_open"),
        Output("edit-log-hist-id", "data"),
        Output("edit-log-obs", "value", allow_duplicate=True),
        Output("edit-log-horas-input", "value", allow_duplicate=True),
        Output("edit-log-alert", "children", allow_duplicate=True),
        Input({"type": "btn-edit-log", "index": ALL}, "n_clicks"),
        State("store-historico", "data"),
        prevent_initial_call=True
    )
    def abrir_edit_log_modal(n_clicks, historico_data):
        ctx = callback_context
        if not ctx.triggered or not any(c for c in n_clicks if c):
            raise PreventUpdate

        trigger_id_str = ctx.triggered[0]['prop_id'].split('.')[0]
        id_dict = json.loads(trigger_id_str)
        hist_id = id_dict['index']

        obs_atual = ""
        horas_atual = ""
        if historico_data:
            df = pd.DataFrame(historico_data)
            match = df[df['hist_id'] == hist_id]
            if not match.empty:
                row = match.iloc[0]
                obs_val = row.get('observacoes')
                obs_atual = str(obs_val) if obs_val and str(obs_val) != 'nan' else ""
                h_raw = row.get('horas')
                try:
                    h_val = float(h_raw) if h_raw is not None and str(h_raw) != 'nan' else None
                except (ValueError, TypeError):
                    h_val = None
                if h_val:
                    from src.pages.workflow.dashboard import float_para_hhmm
                    horas_atual = float_para_hhmm(h_val)

        return True, hist_id, obs_atual, horas_atual, ""

    # ==============================================================================
    # CB17: Fechar edit-log-modal (Cancelar)
    # ==============================================================================
    @app.callback(
        Output("edit-log-modal", "is_open", allow_duplicate=True),
        Output("edit-log-alert", "children"),
        Input("edit-log-cancel-btn", "n_clicks"),
        prevent_initial_call=True
    )
    def fechar_edit_log_modal(n_clicks):
        if not n_clicks:
            raise PreventUpdate
        return False, ""

    # ==============================================================================
    # CB18: Salvar relatório editado (texto + horas)
    # ==============================================================================
    @app.callback(
        Output("edit-log-modal", "is_open", allow_duplicate=True),
        Output("edit-log-alert", "children", allow_duplicate=True),
        Output("alert-container-workflow", "children", allow_duplicate=True),
        Output("container-tabela", "children", allow_duplicate=True),
        Output("store-pendencias", "data", allow_duplicate=True),
        Output("store-historico", "data", allow_duplicate=True),
        Input("edit-log-submit-btn", "n_clicks"),
        State("edit-log-hist-id", "data"),
        State("edit-log-obs", "value"),
        State("edit-log-horas-input", "value"),
        State("user-username-store", "data"),
        State("user-level-store", "data"),
        State("store-filtros-ativos", "data"),
        prevent_initial_call=True
    )
    def salvar_edit_log(n_clicks, hist_id, obs, horas, username, user_level, filtros):
        if not n_clicks or not hist_id:
            raise PreventUpdate

        if not obs or not obs.strip():
            return (True,
                    dbc.Alert("O relatório não pode estar vazio.", color="warning"),
                    no_update, no_update, no_update, no_update)

        horas_val = hhmm_para_float(horas) if horas else None

        sucesso, mensagem = editar_log(hist_id, horas_val, obs.strip())

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
