# callbacks/states_switch_callback.py (ou adicione a um arquivo existente)
from dash import Input, Output, html
from src.components.occupancy_oee_graph import occupancy_oee_card_layout
from src.components.occupancy_oee_graph02 import occupancy_oee_card_layout02

def register_states_switch_callback(app):
    @app.callback(
        Output("graph-container", "children"),
        Input("graph-view-switch", "value")
    )
    def update_graph_view(switch_is_on):
        """
        Este callback renderiza o layout do gráfico apropriado com base no estado do switch.
        - Se o switch estiver LIGADO (True), mostra o primeiro gráfico (Linha do Tempo).
        - Se o switch estiver DESLIGADO (False), mostra o segundo gráfico (Indicador OEE).
        """
        if switch_is_on:
            # Retorna o layout do primeiro componente de gráfico
            return occupancy_oee_card_layout
        else:
            # Retorna o layout do segundo componente de gráfico
            return occupancy_oee_card_layout02
