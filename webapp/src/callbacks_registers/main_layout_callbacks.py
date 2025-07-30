# src/callbacks_registers/main_layout_callbacks.py

from dash import Input, Output, State
from dash.exceptions import PreventUpdate

# O ícone é usado para atualizar o botão no callback
from src.components.icons import hamburger_icon

def register_main_layout_callbacks(app):
    """
    Registra todos os callbacks relacionados ao layout principal da aplicação,
    como o controle da sidebar.

    Args:
        app: A instância da aplicação Dash.
    """

    @app.callback(
        [Output("sidebar-column", "style"), 
         Output("content-column", "style"), 
         Output("sidebar-content", "style"), 
         Output("collapse-sidebar-btn", "children"), 
         Output("sidebar-state", "data")],
        [Input("collapse-sidebar-btn", "n_clicks")],
        [State("sidebar-state", "data")],
        prevent_initial_call=True
    )
    def toggle_sidebar(n_clicks, current_state):
        """
        Este callback controla a expansão e o recolhimento da sidebar
        quando o botão de hambúrguer é clicado.
        """
        if not n_clicks:
            raise PreventUpdate

        # Estilos para a sidebar expandida
        sidebar_style_expanded = {
            "width": "25%", "height": "100%", "transition": "width 0.5s ease", 
            "padding": "8px", "overflow": "hidden"
        }
        content_style_expanded = {
            "width": "75%", "height": "100%", "transition": "width 0.5s ease", 
            "overflowY": "auto"
        }
        sidebar_content_style_visible = {
            "height": "100%", "visibility": "visible", "opacity": 1, 
            "overflowY": "auto", "transition": "opacity 0.3s ease, visibility 0s linear 0.5s"
        }

        # Estilos para a sidebar recolhida
        sidebar_style_collapsed = {
            "width": "0%", "height": "100%", "transition": "width 0.5s ease", 
            "padding": "8px", "overflow": "hidden"
        }
        content_style_collapsed = {
            "width": "100%", "height": "100%", "transition": "width 0.5s ease", 
            "overflowY": "auto"
        }
        sidebar_content_style_hidden = {
            "height": "100%", "visibility": "hidden", "opacity": 0, 
            "overflow": "hidden", "transition": "opacity 0.2s ease, visibility 0s linear 0.2s"
        }

        if current_state == "expanded":
            # Se estava expandido, recolhe
            return (sidebar_style_collapsed, content_style_collapsed, 
                    sidebar_content_style_hidden, hamburger_icon(), "collapsed")
        else:
            # Se estava recolhido, expande
            return (sidebar_style_expanded, content_style_expanded, 
                    sidebar_content_style_visible, hamburger_icon(), "expanded")

