# src/callbacks_registers/sidebar_toggle_callback.py

"""
Callback responsável por controlar o toggle (expandir/colapsar) da sidebar.
Gerencia o estado e os estilos das colunas sidebar e conteúdo.
"""

from dash import Input, Output, State
from dash.exceptions import PreventUpdate


def register_sidebar_toggle_callback(app):
    """
    Registra o callback que controla o toggle da sidebar.
    
    Atualiza:
    - O estado da sidebar (collapsed/expanded)
    - Os estilos da coluna sidebar (width, padding, overflow)
    - Os estilos da coluna de conteúdo (width)
    - Os estilos do card da sidebar (visibility, opacity)
    
    Args:
        app: A instância da aplicação Dash.
    """
    
    @app.callback(
        [
            Output("sidebar-state", "data", allow_duplicate=True),
            Output("sidebar-column", "style", allow_duplicate=True),
            Output("content-column", "style", allow_duplicate=True),
            Output("sidebar-content", "style", allow_duplicate=True),
        ],
        [Input("collapse-sidebar-btn", "n_clicks")],
        [State("sidebar-state", "data")],
        prevent_initial_call=True
    )
    def toggle_sidebar(n_clicks, current_state):
        """
        Alterna o estado da sidebar entre colapsada e expandida.
        
        Args:
            n_clicks (int): Número de cliques no botão de toggle
            current_state (str): Estado atual da sidebar ("collapsed" ou "expanded")
            
        Returns:
            tuple: (novo_estado, estilo_sidebar_col, estilo_content_col, estilo_sidebar_card)
        """
        if n_clicks is None:
            raise PreventUpdate
        
        # Alterna o estado
        new_state = "expanded" if current_state == "collapsed" else "collapsed"
        
        # ========================================
        # ESTILOS PARA SIDEBAR EXPANDIDA
        # ========================================
        if new_state == "expanded":
            sidebar_col_style = {
                "width": "20%",
                "minWidth": "250px",
                "height": "100%",
                "transition": "width 0.3s ease",
                "padding": "8px",
                "overflow": "hidden"
            }
            
            content_col_style = {
                "width": "80%",
                "height": "100%",
                "transition": "width 0.3s ease",
                "overflowY": "auto"
            }
            
            sidebar_card_style = {
                "flex": "1",
                "height": "100%",
                "visibility": "visible",
                "opacity": 1,
                "overflowY": "auto",
                "transition": "opacity 0.3s ease"
            }
        
        # ========================================
        # ESTILOS PARA SIDEBAR COLAPSADA
        # ========================================
        else:
            sidebar_col_style = {
                "width": "0%",
                "height": "100%",
                "transition": "width 0.3s ease",
                "padding": "0px",
                "overflow": "hidden"
            }
            
            content_col_style = {
                "width": "100%",
                "height": "100%",
                "transition": "width 0.3s ease",
                "overflowY": "auto"
            }
            
            sidebar_card_style = {
                "flex": "1",
                "height": "100%",
                "visibility": "hidden",
                "opacity": 0,
                "overflowY": "auto",
                "transition": "opacity 0.3s ease, visibility 0s linear 0.3s"
            }
        
        return new_state, sidebar_col_style, content_col_style, sidebar_card_style