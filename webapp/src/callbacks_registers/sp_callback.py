# webapp/src/callbacks_registers/sp_callback.py (VERSÃO FINAL)

from dash import Input, Output, State, callback, no_update, ctx
import requests
import os

# A URL do nosso novo serviço será lida da variável de ambiente
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:5001" )
COMMAND_ENDPOINT = f"{GATEWAY_URL}/api/command"

# --- DEFINA OS TÓPICOS DIRETAMENTE AQUI ---
# O frontend sabe em qual "caixa de correio" (tópico) ele quer postar a mensagem.
# Isso não requer a biblioteca paho-mqtt.
MQTT_TOPIC_01 = "supervisorio/setpoint01"
MQTT_TOPIC_02 = "supervisorio/setpoint02"
MQTT_TOPIC_03 = "supervisorio/setpoint03"
MQTT_TOPIC_04 = "supervisorio/setpoint04"

def register_sp_callback(app):
    @callback(
        Output('toast-mqtt-status', 'is_open'),
        Output('toast-mqtt-status', 'children'),
        Output('toast-mqtt-status', 'icon'),
        
        Input('botao-carregar-valor-01', 'n_clicks'),
        Input('botao-carregar-valor-02', 'n_clicks'),
        Input('botao-carregar-valor-03', 'n_clicks'),
        Input('botao-carregar-valor-04', 'n_clicks'),
        
        State('input-valor-supervisorio-01', 'value'),
        State('input-valor-supervisorio-02', 'value'),
        State('input-valor-supervisorio-03', 'value'),
        State('input-valor-supervisorio-04', 'value'),
        
        prevent_initial_call=True
    )
    def atualizar_setpoint_e_publicar(n_clicks1, n_clicks2, n_clicks3, n_clicks4, 
                                      valor1, valor2, valor3, valor4):
        triggered_id = ctx.triggered_id
        if not triggered_id:
            return no_update, no_update, no_update

        button_map = {
            'botao-carregar-valor-01': (valor1, MQTT_TOPIC_01),
            'botao-carregar-valor-02': (valor2, MQTT_TOPIC_02),
            'botao-carregar-valor-03': (valor3, MQTT_TOPIC_03),
            'botao-carregar-valor-04': (valor4, MQTT_TOPIC_04),
        }

        valor_inserido, mqtt_topic = button_map.get(triggered_id, (None, None))

        if valor_inserido is None or mqtt_topic is None:
            return no_update, no_update, no_update

        try:
            payload = {
                "topic": mqtt_topic,
                "payload": f"{float(valor_inserido):.1f}"
            }
            
            response = requests.post(COMMAND_ENDPOINT, json=payload, timeout=5)
            response.raise_for_status() 
            
            api_response = response.json()
            toast_message = api_response.get("message", "Comando enviado com sucesso!")
            toast_icon = "success"

        except requests.exceptions.RequestException as e:
            print(f"Erro de comunicação com o Gateway: {e}")
            toast_message = "Erro: Falha ao conectar com o serviço de gateway."
            toast_icon = "danger"
        except Exception as e:
            print(f"Erro inesperado: {e}")
            toast_message = f"Ocorreu um erro inesperado: {e}"
            toast_icon = "danger"

        return True, toast_message, toast_icon