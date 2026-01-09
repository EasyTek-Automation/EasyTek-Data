# src/callbacks_registers/procedures_collapse_callbacks.py

"""
Callbacks para expandir/colapsar seções na navegação de procedimentos.
"""

from dash import Input, Output, State, MATCH
from dash.exceptions import PreventUpdate


def register_procedures_collapse_callbacks(app):
    """
    Registra callbacks para colapsar/expandir seções de procedimentos.
    Usa pattern-matching callbacks para lidar com múltiplas pastas dinamicamente.

    Args:
        app: Instância do Dash app
    """

    # Callback para toggle do collapse e rotação do chevron
    @app.callback(
        Output({"type": "proc-collapse", "folder": MATCH}, "is_open"),
        Output({"type": "proc-chevron", "folder": MATCH}, "style"),
        Input({"type": "proc-toggle", "folder": MATCH}, "n_clicks"),
        State({"type": "proc-collapse", "folder": MATCH}, "is_open"),
        prevent_initial_call=True
    )
    def toggle_folder(n_clicks, is_open):
        """Toggle o estado de expansão de uma pasta e rotaciona o chevron."""
        if n_clicks is None:
            raise PreventUpdate

        new_is_open = not is_open
        chevron_style = {
            "fontSize": "0.65rem",
            "transition": "transform 0.2s ease",
            "transform": "rotate(0deg)" if new_is_open else "rotate(-90deg)"
        }

        return new_is_open, chevron_style
