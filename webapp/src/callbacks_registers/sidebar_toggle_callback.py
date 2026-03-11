# src/callbacks_registers/sidebar_toggle_callback.py

"""
Callback responsável por controlar o toggle (expandir/colapsar) da sidebar.

A sidebar é um overlay fixo (position: fixed) que desliza sobre o conteúdo
via transform: translateX. O conteúdo principal sempre ocupa 100% da largura.

Fecha a sidebar via:
- Botão hambúrguer no header (collapse-sidebar-btn)
- Clique no overlay semi-transparente (sidebar-overlay)
"""

from dash import Input, Output, State, callback_context
from dash.exceptions import PreventUpdate

_SIDEBAR_W = "280px"


def _estilos_expandido():
    sidebar_col = {
        "position": "fixed", "top": "60px", "left": "0", "bottom": "0",
        "width": _SIDEBAR_W, "zIndex": 901,
        "transform": "translateX(0)",
        "transition": "transform 0.3s ease",
        "overflowY": "auto",
    }
    sidebar_card = {
        "height": "100%", "visibility": "visible", "opacity": 1, "overflowY": "auto",
    }
    overlay = {
        "position": "fixed", "top": "60px", "left": "0", "right": "0", "bottom": "0",
        "backgroundColor": "rgba(255,255,255,0.55)",
        "backdropFilter": "blur(2px)", "WebkitBackdropFilter": "blur(2px)",
        "zIndex": 900, "cursor": "pointer",
        "visibility": "visible", "opacity": 1,
        "transition": "opacity 0.3s ease",
    }
    return sidebar_col, sidebar_card, overlay


def _estilos_colapsado():
    sidebar_col = {
        "position": "fixed", "top": "60px", "left": "0", "bottom": "0",
        "width": _SIDEBAR_W, "zIndex": 901,
        "transform": f"translateX(-{_SIDEBAR_W})",
        "transition": "transform 0.3s ease",
        "overflowY": "auto",
    }
    sidebar_card = {
        "height": "100%", "visibility": "visible", "opacity": 1, "overflowY": "auto",
    }
    overlay = {
        "position": "fixed", "top": "60px", "left": "0", "right": "0", "bottom": "0",
        "backgroundColor": "rgba(255,255,255,0.55)",
        "backdropFilter": "blur(2px)", "WebkitBackdropFilter": "blur(2px)",
        "zIndex": 900, "cursor": "pointer",
        "visibility": "hidden", "opacity": 0,
        "transition": "opacity 0.3s ease, visibility 0s linear 0.3s",
    }
    return sidebar_col, sidebar_card, overlay


def register_sidebar_toggle_callback(app):
    """Registra o callback de toggle da sidebar."""

    @app.callback(
        Output("sidebar-state", "data", allow_duplicate=True),
        Output("sidebar-column", "style", allow_duplicate=True),
        Output("sidebar-content", "style", allow_duplicate=True),
        Output("sidebar-overlay", "style"),
        Input("collapse-sidebar-btn", "n_clicks"),
        Input("sidebar-overlay", "n_clicks"),
        State("sidebar-state", "data"),
        prevent_initial_call=True
    )
    def toggle_sidebar(btn_clicks, overlay_clicks, current_state):
        if not btn_clicks and not overlay_clicks:
            raise PreventUpdate
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate

        trigger = ctx.triggered[0]["prop_id"].split(".")[0]

        # Clique no overlay sempre fecha
        if trigger == "sidebar-overlay":
            new_state = "collapsed"
        else:
            new_state = "expanded" if current_state == "collapsed" else "collapsed"

        if new_state == "expanded":
            sidebar_col, sidebar_card, overlay = _estilos_expandido()
        else:
            sidebar_col, sidebar_card, overlay = _estilos_colapsado()

        return new_state, sidebar_col, sidebar_card, overlay