"""
Callbacks para componentes de erro de banco de dados
"""

from dash import Input, Output, State, html
from dash.exceptions import PreventUpdate
from src.database.connection import reconnect_mongodb, get_connection_status


def register_database_error_callbacks(app):
    """
    Registra callbacks para os componentes de erro de banco de dados.

    Args:
        app: Instância do aplicativo Dash
    """

    # Callback para toggle de detalhes técnicos
    @app.callback(
        Output("collapse-db-error-details", "is_open"),
        Input("btn-toggle-db-error-details", "n_clicks"),
        State("collapse-db-error-details", "is_open"),
        prevent_initial_call=True
    )
    def toggle_error_details(n_clicks, is_open):
        """Toggle dos detalhes técnicos do erro."""
        if n_clicks:
            return not is_open
        return is_open


    # Callback para botão "Tentar Novamente"
    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Output("store-db-reconnect-status", "data"),
        Input("btn-retry-database", "n_clicks"),
        State("url", "pathname"),
        prevent_initial_call=True
    )
    def retry_database_connection(n_clicks, current_path):
        """
        Tenta reconectar ao MongoDB e recarrega a página se bem-sucedido.
        """
        if not n_clicks:
            raise PreventUpdate

        print("🔄 Usuário solicitou reconexão ao MongoDB...")

        # Tentar reconectar
        success = reconnect_mongodb()
        status = get_connection_status()

        if success:
            print("✅ Reconexão bem-sucedida! Recarregando página...")
            # Força reload da página atual (trigger update no pathname)
            return current_path, {"success": True, "timestamp": n_clicks}
        else:
            print(f"❌ Reconexão falhou: {status['error']}")
            raise PreventUpdate


    print("✅ Callbacks de erro de banco de dados registrados")
