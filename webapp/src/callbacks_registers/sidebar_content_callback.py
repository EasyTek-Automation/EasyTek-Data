# src/callbacks_registers/sidebar_content_callback.py

"""
Callback para atualizar o conteúdo da sidebar dinamicamente
baseado na página atual (pathname).
"""

from dash import Input, Output
from src.sidebar import get_sidebar_content_for_page


def register_sidebar_content_callback(app):
    """
    Registra o callback que atualiza o conteúdo da sidebar
    quando o usuário navega entre páginas.
    
    Args:
        app: A instância da aplicação Dash.
    """
    
    @app.callback(
        Output("sidebar-dynamic-content", "children"),
        Input("url", "pathname")
    )
    def update_sidebar_content(pathname):
        """
        Atualiza o conteúdo da sidebar baseado na página atual.
        
        Args:
            pathname (str): O caminho da URL atual
            
        Returns:
            html.Div: O conteúdo apropriado para a sidebar
        """
        return get_sidebar_content_for_page(pathname)
