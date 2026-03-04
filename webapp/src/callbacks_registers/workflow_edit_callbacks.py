"""Callbacks para edição de pendências."""
from dash import Input, Output, State, callback_context, no_update, ALL
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from dash import html
import json

from src.utils.workflow_db import (
    editar_pendencia,
    get_usuarios_por_perfil,
    get_usuarios_nivel3_por_perfil,
    carregar_pendencias,
    deletar_pendencia,
    TIPOS_REQUEREM_APROVACAO
)


def register_edit_callbacks(app):
    """Registra callbacks de edição de pendências."""

    # CALLBACK 1: Abrir Modal de Edição (Pattern Matching)
    @app.callback(
        [
            Output("edit-pend-modal", "is_open"),
            Output("edit-pend-id-display", "children"),
            Output("edit-pend-descricao", "value"),
            Output("edit-pend-responsavel", "value"),
            Output("edit-pend-status", "value"),
            Output("edit-pend-tipo-evento", "value"),
            Output("edit-pend-observacoes", "value"),
            Output("edit-pend-horas", "value"),
            Output("edit-pend-aprovador-dropdown", "value"),
            Output("edit-pend-original-data", "data"),
            Output("edit-pend-alert", "children"),
            Output("edit-pend-nota-gam", "value")
        ],
        [
            Input({"type": "btn-edit-pend", "index": ALL}, "n_clicks"),
            Input("edit-pend-cancel-btn", "n_clicks"),
        ],
        [
            State("user-level-store", "data"),
            State("user-username-store", "data"),
            State("store-historico", "data")
        ],
        prevent_initial_call=True
    )
    def toggle_edit_modal(edit_clicks, cancel_clicks,
                         user_level, username, historico_data):
        """Abre/fecha modal de edição."""
        ctx = callback_context

        if not ctx.triggered:
            raise PreventUpdate

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # Fechar modal e limpar campos apenas no cancelamento
        if "cancel" in trigger_id:
            return False, "", "", None, None, None, "", None, None, None, "", ""

        # Verificar se é um clique válido nos botões de editar
        # (n_clicks deve ser > 0 e não None)
        if "btn-edit-pend" in trigger_id:
            # Verificar se algum botão foi realmente clicado
            if not any(clicks for clicks in edit_clicks if clicks):
                raise PreventUpdate
            button_data = json.loads(trigger_id)
            pend_id = button_data["index"]

            # Carregar pendência
            df_pend = carregar_pendencias()
            pend = df_pend[df_pend['id'] == pend_id]

            if pend.empty:
                return False, "", "", None, None, None, "", None, None, None, dbc.Alert(
                    "Pendência não encontrada", color="danger"
                ), ""

            pend = pend.iloc[0].to_dict()

            # VALIDAÇÃO RBAC: Qualquer usuário autenticado pode editar
            # (Apenas criação e exclusão são restritas a nível 3)

            # Popula dados originais
            original_data = {
                "id": pend['id'],
                "descricao": pend['descricao'],
                "responsavel": pend['responsavel'],
                "status": pend['status']
            }

            # Buscar último tipo de evento do histórico (precarregar dropdown)
            ultimo_tipo_evento = None
            if historico_data:
                import pandas as pd
                df_hist = pd.DataFrame(historico_data)
                hist_pend = df_hist[df_hist['pendencia_id'] == pend_id]
                if not hist_pend.empty:
                    # Ordenar por data e pegar o último (exceto criação)
                    hist_pend = hist_pend.sort_values('data', ascending=False)
                    hist_pend = hist_pend[hist_pend['tipo_evento'] != 'criacao']
                    if not hist_pend.empty:
                        ultimo_tipo_evento = hist_pend.iloc[0]['descricao']

            return (
                True,           # Modal abre
                pend['id'],
                pend['descricao'],
                pend['responsavel'],
                pend['status'],
                ultimo_tipo_evento,  # Precarregar último tipo de evento
                "",             # Observações sempre vazio ao abrir
                None,           # Horas sempre vazio ao abrir
                None,           # Aprovador sempre vazio ao abrir
                original_data,
                "",
                pend.get('nota_gam') or ""  # Nota GAM atual
            )

        return no_update


    # CALLBACK 1.5: Mostrar/Ocultar campo de aprovador baseado no tipo de evento
    @app.callback(
        Output("edit-pend-aprovador-container", "style"),
        Output("edit-pend-aprovador-dropdown", "options"),
        Input("edit-pend-tipo-evento", "value"),
        State("user-perfil-store", "data"),
        prevent_initial_call=True
    )
    def toggle_campo_aprovador(tipo_evento, user_perfil):
        """Mostra campo de aprovador quando tipo de evento requer aprovação."""
        if tipo_evento in TIPOS_REQUEREM_APROVACAO:
            aprovadores = get_usuarios_nivel3_por_perfil(user_perfil or "admin")
            return {"display": "block"}, aprovadores
        return {"display": "none"}, []


    # CALLBACK 2: Popular dropdown de responsáveis no modal de edição
    @app.callback(
        [
            Output("edit-pend-responsavel", "options"),
            Output("edit-pend-responsavel-help", "children")
        ],
        Input("edit-pend-modal", "is_open"),
        State("user-perfil-store", "data")
    )
    def populate_edit_responsavel_dropdown(is_open, user_perfil):
        """Popula dropdown com usuários do departamento."""
        if not is_open:
            return no_update, no_update

        if user_perfil == "admin":
            help_text = "Você pode atribuir para qualquer usuário (admin TI)"
        else:
            help_text = f"Você pode atribuir apenas para usuários do departamento {user_perfil}"

        usuarios = get_usuarios_por_perfil(user_perfil)

        if not usuarios:
            return [], "Nenhum usuário disponível"

        return usuarios, help_text


    # CALLBACK 3: Salvar Edições
    @app.callback(
        [
            Output("edit-pend-modal", "is_open", allow_duplicate=True),
            Output("edit-pend-alert", "children", allow_duplicate=True),
            Output("alert-container-workflow", "children", allow_duplicate=True),
            Output("container-tabela", "children", allow_duplicate=True),
            Output("store-pendencias", "data", allow_duplicate=True),
            Output("store-historico", "data", allow_duplicate=True)
        ],
        Input("edit-pend-submit-btn", "n_clicks"),
        [
            State("edit-pend-descricao", "value"),
            State("edit-pend-responsavel", "value"),
            State("edit-pend-status", "value"),
            State("edit-pend-tipo-evento", "value"),
            State("edit-pend-observacoes", "value"),
            State("edit-pend-horas", "value"),
            State("edit-pend-aprovador-dropdown", "value"),
            State("edit-pend-nota-gam", "value"),
            State("edit-pend-original-data", "data"),
            State("user-level-store", "data"),
            State("user-perfil-store", "data"),
            State("user-username-store", "data")
        ],
        prevent_initial_call=True
    )
    def salvar_edicao_pendencia(n_clicks, nova_desc, novo_resp, novo_status, tipo_evento, observacoes,
                                horas, aprovador, nota_gam, original_data, user_level, user_perfil, username):
        """Valida e salva edições da pendência."""
        if not n_clicks or not original_data:
            return no_update, no_update, no_update, no_update, no_update, no_update

        pend_id = original_data["id"]

        # VALIDAÇÃO 0: Bloquear edição baseada em status_aceite e nível
        from src.utils.workflow_db import carregar_pendencias as _cp
        _df = _cp()
        _pend = _df[_df['id'] == pend_id]
        if not _pend.empty:
            _status_aceite = str(_pend.iloc[0].get('status_aceite') or 'pendente')
            _responsavel = str(_pend.iloc[0].get('responsavel') or '')

            if _status_aceite == 'pendente':
                if _responsavel == username:
                    # Responsável pendente (qualquer nível): deve aceitar antes de editar
                    return (
                        True,
                        dbc.Alert([
                            html.I(className="fas fa-lock me-2"),
                            "Aceite a tarefa antes de editá-la."
                        ], color="warning", dismissable=True),
                        no_update, no_update, no_update, no_update
                    )
                elif user_level < 3:
                    # Não-responsável nível < 3: sem permissão
                    return (
                        True,
                        dbc.Alert([
                            html.I(className="fas fa-lock me-2"),
                            "Esta tarefa ainda não foi aceita pelo responsável."
                        ], color="warning", dismissable=True),
                        no_update, no_update, no_update, no_update
                    )
                # Nível 3 não-responsável: pode redesignar (prossegue)

            elif _status_aceite == 'rejeitado':
                if user_level < 3:
                    # Nível < 3 não pode editar tarefa rejeitada
                    return (
                        True,
                        dbc.Alert([
                            html.I(className="fas fa-lock me-2"),
                            "Tarefa rejeitada. Aguardando redesignação por nível 3."
                        ], color="warning", dismissable=True),
                        no_update, no_update, no_update, no_update
                    )
                # Nível 3 (qualquer, inclusive responsável): pode redesignar (prossegue)

        # VALIDAÇÃO 1: Campos obrigatórios (incluindo tipo_evento e observações)
        if not all([nova_desc, novo_resp, novo_status, tipo_evento, observacoes]):
            campos_faltantes = []
            if not nova_desc: campos_faltantes.append("Descrição")
            if not novo_resp: campos_faltantes.append("Responsável")
            if not novo_status: campos_faltantes.append("Status")
            if not tipo_evento: campos_faltantes.append("Tipo de Evento")
            if not observacoes or not observacoes.strip(): campos_faltantes.append("Observações")

            return (
                True,  # Modal continua aberto
                dbc.Alert([
                    html.I(className="fas fa-exclamation-triangle me-2"),
                    f"Campos obrigatórios faltando: {', '.join(campos_faltantes)}"
                ], color="warning", dismissable=True),
                no_update, no_update, no_update, no_update
            )

        # VALIDAÇÃO 2: Aprovador obrigatório quando tipo requer aprovação
        if tipo_evento in TIPOS_REQUEREM_APROVACAO and not aprovador:
            return (
                True,  # Modal continua aberto
                dbc.Alert([
                    html.I(className="fas fa-exclamation-triangle me-2"),
                    f"O tipo '{tipo_evento}' requer a seleção de um aprovador (nível 3)."
                ], color="warning", dismissable=True),
                no_update, no_update, no_update, no_update
            )

        # VALIDAÇÃO 3: Departamento (se mudou responsável)
        if novo_resp != original_data["responsavel"]:
            from src.database.connection import get_mongo_connection
            usuarios = get_mongo_connection("usuarios")
            resp_user = usuarios.find_one({"username": novo_resp})

            if not resp_user:
                return (
                    True,  # Modal continua aberto
                    dbc.Alert([
                        html.I(className="fas fa-user-slash me-2"),
                        f"Usuário '{novo_resp}' não encontrado"
                    ], color="danger", dismissable=True),
                    no_update, no_update, no_update, no_update
                )

            if user_perfil != "admin" and resp_user.get("perfil") != user_perfil:
                return (
                    True,  # Modal continua aberto
                    dbc.Alert([
                        html.I(className="fas fa-shield-x me-2"),
                        "PERMISSÃO NEGADA: Só pode atribuir para seu departamento"
                    ], color="danger", dismissable=True),
                    no_update, no_update, no_update, no_update
                )

        # Converter horas para float se fornecido
        horas_valor = float(horas) if horas is not None else None

        # EDITAR PENDÊNCIA
        sucesso, mensagem = editar_pendencia(
            pend_id=pend_id,
            nova_descricao=nova_desc if nova_desc != original_data["descricao"] else None,
            novo_responsavel=novo_resp if novo_resp != original_data["responsavel"] else None,
            novo_status=novo_status if novo_status != original_data["status"] else None,
            descricao_original=original_data["descricao"],
            responsavel_original=original_data["responsavel"],
            status_original=original_data["status"],
            editado_por=username,
            tipo_evento=tipo_evento,
            observacoes=observacoes.strip(),
            horas=horas_valor,
            aprovador=aprovador if tipo_evento in TIPOS_REQUEREM_APROVACAO else None,
            nota_gam=nota_gam if nota_gam is not None else None
        )

        if sucesso:
            # Recarregar tabela E histórico
            from src.pages.workflow.dashboard import carregar_dados_csv, criar_tabela_pendencias
            df_pend, df_hist = carregar_dados_csv()
            nova_tabela = criar_tabela_pendencias(df_pend, df_hist,
                                                  user_level=user_level or 1,
                                                  username_atual=username)

            return (
                False,  # Fechar modal
                "",     # Limpar alerta do modal
                dbc.Alert([  # Mostrar alerta no topo da página
                    html.I(className="fas fa-check-circle me-2"),
                    mensagem
                ], color="success", dismissable=True, duration=7000),
                nova_tabela,
                df_pend.to_dict('records'),
                df_hist.to_dict('records')  # Atualizar histórico também
            )
        else:
            return (
                True,  # Modal continua aberto
                dbc.Alert([
                    html.I(className="fas fa-times-circle me-2"),
                    f"Erro: {mensagem}"
                ], color="danger", dismissable=True),
                no_update, no_update, no_update, no_update
            )


    # ==================================================================================
    # CALLBACK 4: Controlar visibilidade do botão deletar (apenas nível 3)
    # ==================================================================================
    @app.callback(
        Output("edit-pend-delete-btn", "style"),
        Input("edit-pend-modal", "is_open"),
        State("user-level-store", "data")
    )
    def toggle_delete_button_visibility(is_open, user_level):
        """Mostra botão deletar apenas para nível 3."""
        if user_level == 3:
            return {"display": "inline-block"}
        else:
            return {"display": "none"}


    # ==================================================================================
    # CALLBACK 5: Abrir modal de confirmação de exclusão
    # ==================================================================================
    @app.callback(
        [
            Output("delete-confirm-modal", "is_open"),
            Output("delete-confirm-id", "children")
        ],
        [
            Input("edit-pend-delete-btn", "n_clicks"),
            Input("delete-confirm-cancel-btn", "n_clicks"),
            Input("delete-confirm-submit-btn", "n_clicks")
        ],
        State("edit-pend-id-display", "children"),
        prevent_initial_call=True
    )
    def toggle_delete_confirm_modal(delete_clicks, cancel_clicks, submit_clicks, pend_id):
        """Abre/fecha modal de confirmação de exclusão."""
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # Abrir modal de confirmação
        if "delete-btn" in trigger_id:
            return True, pend_id

        # Fechar modal
        if "cancel" in trigger_id or "submit" in trigger_id:
            return False, ""

        return no_update, no_update


    # ==================================================================================
    # CALLBACK 6: Deletar pendência (após confirmação)
    # ==================================================================================
    @app.callback(
        [
            Output("edit-pend-modal", "is_open", allow_duplicate=True),
            Output("delete-confirm-modal", "is_open", allow_duplicate=True),
            Output("alert-container-workflow", "children", allow_duplicate=True),
            Output("container-tabela", "children", allow_duplicate=True),
            Output("store-pendencias", "data", allow_duplicate=True),
            Output("store-historico", "data", allow_duplicate=True)
        ],
        Input("delete-confirm-submit-btn", "n_clicks"),
        State("edit-pend-id-display", "children"),
        prevent_initial_call=True
    )
    def deletar_pendencia_callback(n_clicks, pend_id):
        """Deleta a pendência após confirmação."""
        if not n_clicks:
            return no_update, no_update, no_update, no_update, no_update, no_update

        # Deletar pendência
        sucesso, mensagem = deletar_pendencia(pend_id)

        if sucesso:
            # Recarregar tabela e histórico
            from src.pages.workflow.dashboard import carregar_dados_csv, criar_tabela_pendencias
            from src.database.connection import get_mongo_connection as _get_mc
            from flask_login import current_user as _cu
            df_pend, df_hist = carregar_dados_csv()
            _ul = _cu.level if _cu.is_authenticated else 1
            _un = _cu.username if _cu.is_authenticated else None
            nova_tabela = criar_tabela_pendencias(df_pend, df_hist,
                                                  user_level=_ul,
                                                  username_atual=_un)

            return (
                False,  # Fechar modal de edição
                False,  # Fechar modal de confirmação
                dbc.Alert([
                    html.I(className="fas fa-check-circle me-2"),
                    mensagem
                ], color="success", dismissable=True, duration=7000),
                nova_tabela,
                df_pend.to_dict('records') if df_pend is not None else [],
                df_hist.to_dict('records') if df_hist is not None else []
            )
        else:
            return (
                no_update,
                False,  # Fechar modal de confirmação
                dbc.Alert([
                    html.I(className="fas fa-times-circle me-2"),
                    f"Erro ao deletar: {mensagem}"
                ], color="danger", dismissable=True, duration=7000),
                no_update, no_update, no_update
            )
