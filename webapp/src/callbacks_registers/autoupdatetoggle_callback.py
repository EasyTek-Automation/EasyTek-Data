# callbacks/autoupdatetoggle_callback.py
from dash.dependencies import Input, Output, State # NOVO: Importar State
import logging
import dash

# Importe de 'metrics' aqui, pois esta lógica usa filtrar_dados_mongo
from src.metrics import filtrar_dados_mongo

logger = logging.getLogger(__name__)


def register_autoupdatetoggle_callbacks(app):
    @app.callback(
        Output('interval-component', 'disabled'),
        [
            # Mudar Inputs para o dcc.Store
            Input('store-auto-update-enabled', 'data'),
            Input('url', 'pathname')
        ]
    )
    def toggle_interval(is_auto_update_enabled, pathname):
        if pathname == "/reports-print":
            return True # Desabilita o dcc.Interval

        # Se o store-auto-update-enabled ainda não tem um valor (None), mantenha desabilitado
        if is_auto_update_enabled is None:
            raise dash.exceptions.PreventUpdate

        # Se o switch estiver ativado (is_auto_update_enabled é True),
        # o intervalo NÃO deve estar desabilitado (retorna False).
        # Se o switch estiver desativado (is_auto_update_enabled é False),
        # o intervalo DEVE estar desabilitado (retorna True).
        return not is_auto_update_enabled