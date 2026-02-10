"""Callbacks para criação de pendências."""
from dash import Input, Output, State, callback_context, no_update
import dash_bootstrap_components as dbc
from dash import html
from flask_login import current_user

from src.utils.workflow_csv import (
    criar_pendencia,
    get_usuarios_por_perfil
)


def register_create_callbacks(app):
    """Registra callbacks de criação de pendências."""

    # CALLBACK 1: Abrir/Fechar Modal de Criação
    @app.callback(
        [
            Output("create-pend-modal", "is_open"),
            Output("create-pend-descricao", "value"),
            Output("create-pend-status", "value"),
            Output("create-pend-alert", "children")
        ],
        [
            Input("btn-nova-pendencia", "n_clicks"),
            Input("create-pend-cancel-btn", "n_clicks"),
            Input("create-pend-submit-btn", "n_clicks")
        ],
        prevent_initial_call=True
    )
    def toggle_create_modal(open_clicks, cancel_clicks, submit_clicks):
        """Abre/fecha modal de criação."""
        ctx = callback_context
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # Fechar modal
        if "cancel" in trigger_id or "submit" in trigger_id:
            return False, "", "Pendente", ""

        # Abrir modal
        if "nova-pendencia" in trigger_id:
            return True, "", "Pendente", ""

        return no_update


    # CALLBACK 2: Popular dropdown de responsáveis
    @app.callback(
        [
            Output("create-pend-responsavel", "options"),
            Output("create-pend-responsavel-help", "children")
        ],
        Input("create-pend-modal", "is_open"),
        State("user-perfil-store", "data")
    )
    def populate_responsavel_dropdown(is_open, user_perfil):
        """Popula dropdown com usuários do mesmo departamento."""
        if not is_open:
            return no_update, no_update

        if user_perfil == "admin":
            help_text = "Você pode atribuir para qualquer usuário (admin TI)"
        else:
            help_text = f"Você pode atribuir apenas para usuários do departamento {user_perfil}"

        # Buscar usuários
        usuarios = get_usuarios_por_perfil(user_perfil)

        if not usuarios:
            return [], "Nenhum usuário disponível neste departamento"

        return usuarios, help_text


    # CALLBACK 3: Criar Pendência (Submit)
    @app.callback(
        [
            Output("create-pend-alert", "children", allow_duplicate=True),
            Output("container-tabela", "children", allow_duplicate=True),
            Output("store-pendencias", "data", allow_duplicate=True)
        ],
        Input("create-pend-submit-btn", "n_clicks"),
        [
            State("create-pend-descricao", "value"),
            State("create-pend-responsavel", "value"),
            State("create-pend-status", "value"),
            State("user-level-store", "data"),
            State("user-perfil-store", "data"),
            State("user-username-store", "data")
        ],
        prevent_initial_call=True
    )
    def criar_nova_pendencia(n_clicks, descricao, responsavel, status,
                             user_level, user_perfil, username):
        """Valida e cria nova pendência."""
        if not n_clicks:
            return no_update, no_update, no_update

        # VALIDAÇÃO 1: Nível 3
        if user_level != 3:
            return dbc.Alert([
                html.I(className="fas fa-shield-x me-2"),
                "PERMISSÃO NEGADA: Apenas usuários nível 3 podem criar pendências"
            ], color="danger", dismissable=True), no_update, no_update

        # VALIDAÇÃO 2: Campos obrigatórios
        if not all([descricao, responsavel]):
            return dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                "Descrição e Responsável são obrigatórios"
            ], color="warning", dismissable=True), no_update, no_update

        # VALIDAÇÃO 3: Departamento (responsável deve ser do mesmo dept)
        from src.database.connection import get_mongo_connection
        usuarios = get_mongo_connection("usuarios")
        resp_user = usuarios.find_one({"username": responsavel})

        if not resp_user:
            return dbc.Alert([
                html.I(className="fas fa-user-slash me-2"),
                f"Usuário '{responsavel}' não encontrado"
            ], color="danger", dismissable=True), no_update, no_update

        if user_perfil != "admin" and resp_user.get("perfil") != user_perfil:
            return dbc.Alert([
                html.I(className="fas fa-shield-x me-2"),
                "PERMISSÃO NEGADA: Você só pode atribuir para usuários do seu departamento"
            ], color="danger", dismissable=True), no_update, no_update

        # CRIAR PENDÊNCIA
        sucesso, resultado = criar_pendencia(
            descricao=descricao.strip(),
            responsavel=responsavel,
            status=status,
            criado_por=username,
            criado_por_perfil=user_perfil
        )

        if sucesso:
            # Recarregar tabela
            from src.pages.workflow.dashboard import carregar_dados_csv, criar_tabela_pendencias
            df_pend, _ = carregar_dados_csv()
            nova_tabela = criar_tabela_pendencias(df_pend)

            return (
                dbc.Alert([
                    html.I(className="fas fa-check-circle me-2"),
                    f"Pendência {resultado} criada com sucesso!"
                ], color="success", dismissable=True, duration=4000),
                nova_tabela,
                df_pend.to_dict('records')
            )
        else:
            return dbc.Alert([
                html.I(className="fas fa-times-circle me-2"),
                f"Erro ao criar pendência: {resultado}"
            ], color="danger", dismissable=True), no_update, no_update
