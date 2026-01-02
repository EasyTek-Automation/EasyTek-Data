# src/callbacks_registers/alarms_callbacks.py

from dash.dependencies import Input, Output, State

def register_alarms_callbacks(app):
    """Callbacks para página de alarmes"""
    
    @app.callback(
        Output("collapse-alarm-filters", "is_open"),
        Input("btn-toggle-alarm-filters", "n_clicks"),
        State("collapse-alarm-filters", "is_open"),
        prevent_initial_call=True
    )
    def toggle_alarm_filters(n_clicks, is_open):
        """Toggle do painel de filtros"""
        if n_clicks:
            return not is_open
        return is_open