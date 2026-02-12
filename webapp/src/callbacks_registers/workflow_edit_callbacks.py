"""Callbacks para edição de pendências."""
from dash import Input, Output, State, callback_context, no_update, ALL
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from dash import html
import json

from src.utils.workflow_csv import (
    editar_pendencia,
    get_usuarios_por_perfil,
    carregar_pendencias
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
            Output("edit-pend-original-data", "data"),
            Output("edit-pend-alert", "children")
        ],
        [
            Input({"type": "btn-edit-pend", "index": ALL}, "n_clicks"),
            Input("edit-pend-cancel-btn", "n_clicks"),
            Input("edit-pend-submit-btn", "n_clicks")
        ],
        [
            State("user-level-store", "data"),
            State("user-username-store", "data")
        ],
        prevent_initial_call=True
    )
    def toggle_edit_modal(edit_clicks, cancel_clicks, submit_clicks,
                         user_level, username):
        """Abre/fecha modal de edição."""
        ctx = callback_context

        if not ctx.triggered:
            raise PreventUpdate

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # Fechar modal (limpar todos os campos)
        if "cancel" in trigger_id or "submit" in trigger_id:
            return False, "", "", None, None, None, "", None, ""

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
                return False, "", "", None, None, None, "", None, dbc.Alert(
                    "Pendência não encontrada", color="danger"
                )

            pend = pend.iloc[0].to_dict()

            # VALIDAÇÃO RBAC: Responsável ou Nível 3
            if pend['responsavel'] != username and user_level != 3:
                return False, "", "", None, None, None, "", None, dbc.Alert([
                    html.I(className="fas fa-shield-x me-2"),
                    "PERMISSÃO NEGADA: Apenas o responsável ou admins podem editar"
                ], color="danger", dismissable=True)

            # Popula dados originais
            original_data = {
                "id": pend['id'],
                "descricao": pend['descricao'],
                "responsavel": pend['responsavel'],
                "status": pend['status']
            }

            return (
                True,  # Modal abre
                pend['id'],
                pend['descricao'],
                pend['responsavel'],
                pend['status'],
                None,  # Tipo evento sempre vazio ao abrir
                "",    # Observações sempre vazio ao abrir
                original_data,
                ""
            )

        return no_update


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
            State("edit-pend-original-data", "data"),
            State("user-level-store", "data"),
            State("user-perfil-store", "data"),
            State("user-username-store", "data")
        ],
        prevent_initial_call=True
    )
    def salvar_edicao_pendencia(n_clicks, nova_desc, novo_resp, novo_status, tipo_evento, observacoes,
                                original_data, user_level, user_perfil, username):
        """Valida e salva edições da pendência."""
        if not n_clicks or not original_data:
            return no_update, no_update, no_update, no_update, no_update, no_update

        pend_id = original_data["id"]

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
                no_update,  # Sem alerta no container principal
                no_update,  # Tabela não muda
                no_update,  # Store pendências não muda
                no_update   # Store histórico não muda
            )

        # VALIDAÇÃO 2: Departamento (se mudou responsável)
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
            observacoes=observacoes.strip()
        )

        if sucesso:
            # Recarregar tabela E histórico
            from src.pages.workflow.dashboard import carregar_dados_csv, criar_tabela_pendencias
            df_pend, df_hist = carregar_dados_csv()
            nova_tabela = criar_tabela_pendencias(df_pend)

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
