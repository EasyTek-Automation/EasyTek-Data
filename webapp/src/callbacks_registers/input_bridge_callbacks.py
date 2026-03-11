# callbacks/input_bridge_callbacks.py
import dash
from dash.dependencies import Input, Output, State
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def register_input_bridge_callbacks(app):
    """
    Este callback serve como uma ponte, pegando os inputs dos filtros
    e armazenando-os em dcc.Store componentes, que estão sempre presentes.
    """
    @app.callback(
        [
            Output('store-start-date', 'data'),
            Output('store-end-date', 'data'),
            Output('store-start-hour', 'data'),
            Output('store-end-hour', 'data'),
            Output('store-auto-update-enabled', 'data')
        ],
        [
            Input('date-picker-range', 'start_date'),
            Input('date-picker-range', 'end_date'),
            Input('start-hour', 'value'),
            Input('end-hour', 'value'),
            State('url', 'pathname')  # Para saber qual página está ativa (State: URL não dispara o callback)
        ]
    )
    def update_global_stores(start_date, end_date, start_hour, end_hour, pathname):
        
        # Inicializar valores padrões, caso os inputs estejam vazios
        end_datetime = datetime.now()
        start_datetime = end_datetime - timedelta(days=7)
        default_start_date = start_datetime.strftime("%Y-%m-%d")
        default_end_date = end_datetime.strftime("%Y-%m-%d")
        default_start_hour = "00:00"
        default_end_hour = "23:59"
        
        # Auto-update desabilitado por padrão (removido o switch)
        default_auto_update = False

        # Verifica a página ativa
        if pathname == "/reports-print":
            logger.info(f"Acessando /reports-print, verificando valores.")

            # Se os valores atuais dos storages globais já existem, preserva-os
            if start_date and end_date and start_hour and end_hour:
                logger.info(f"Preservando valores existentes para impressão.")
                return start_date, end_date, start_hour, end_hour, default_auto_update

            # Caso contrário, inicializa com valores padrão
            logger.info(f"Usando valores padrões para impressão.")
            return default_start_date, default_end_date, default_start_hour, default_end_hour, default_auto_update

        # Se não é a página de impressão, usa os valores dos filtros normalmente
        if start_date is None or end_date is None or start_hour is None or end_hour is None:
            # Evita erro causado por valores ausentes
            raise dash.exceptions.PreventUpdate

        logger.info(f"Atualizando valores globais oriundos dos filtros para a página: {pathname}.")
        return start_date, end_date, start_hour, end_hour, default_auto_update