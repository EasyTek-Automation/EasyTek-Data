# event-gateway/api.py
from flask import Flask, request, jsonify
import paho.mqtt.publish as publish
import os

app = Flask(__name__)

# --- Configurações do Broker MQTT (lidas das variáveis de ambiente) ---
MQTT_BROKER_ADDRESS = os.getenv("MQTT_BROKER_ADDRESS")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", 1883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

# Monta o dicionário de autenticação, se as credenciais existirem
auth_dict = None
if MQTT_USERNAME and MQTT_PASSWORD:
    auth_dict = {'username': MQTT_USERNAME, 'password': MQTT_PASSWORD}
    print("Autenticação MQTT configurada.")

@app.route('/api/command', methods=['POST'])
def send_command():
    if not MQTT_BROKER_ADDRESS:
        return jsonify({"status": "error", "message": "Configuração do broker MQTT não encontrada."}), 500

    data = request.get_json()
    if not data or 'topic' not in data or 'payload' not in data:
        return jsonify({"status": "error", "message": "JSON inválido. 'topic' e 'payload' são obrigatórios."}), 400

    topic = data['topic']
    payload = str(data['payload'])

    try:
        print(f"Publicando no tópico '{topic}' via broker '{MQTT_BROKER_ADDRESS}:{MQTT_BROKER_PORT}'")
        publish.single(
            topic,
            payload=payload,
            hostname=MQTT_BROKER_ADDRESS,
            port=MQTT_BROKER_PORT,
            auth=auth_dict,  # <-- Adiciona a autenticação aqui
            tls={'tls_version': 2} # Necessário para HiveMQ Cloud (TLSv1.2)
        )
        return jsonify({"status": "success", "message": "Comando publicado com sucesso."}), 200
    except Exception as e:
        print(f"Erro ao publicar no MQTT: {e}")
        return jsonify({"status": "error", "message": f"Falha ao conectar ao broker MQTT: {e}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
