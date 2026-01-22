---
name: setup-dev
description: Configura o ambiente de desenvolvimento do AMG_Data. Use quando precisar iniciar o desenvolvimento ou resolver problemas de ambiente.
disable-model-invocation: true
allowed-tools: Read, Bash, Glob
---

# Setup do Ambiente de Desenvolvimento - AMG_Data

Configure o ambiente de desenvolvimento seguindo estes passos:

## 1. Verificar Python

Verifique se Python está instalado:
```bash
python --version
```
Versão recomendada: Python 3.8+

## 2. Virtual Environment

```bash
python -m venv venv
```

**Ativar:**
- Windows: `venv\Scripts\activate`
- Linux/Mac: `source venv/bin/activate`

## 3. Instalar Dependências

**Webapp:**
```bash
cd webapp
pip install -r requirements.txt
cd ..
```

**Event Gateway:**
```bash
cd event-gateway
pip install -r requirements.txt
cd ..
```

## 4. Configurar Variáveis de Ambiente

Crie arquivo `.env` na raiz do projeto com:

```env
# MongoDB
MONGO_URI=mongodb://usuario:senha@host:27017
DB_NAME=amg_database

# Flask
SECRET_KEY=sua_chave_secreta_aqui

# MQTT
MQTT_BROKER_ADDRESS=broker.endereco.com
MQTT_BROKER_PORT=8883
MQTT_USERNAME=usuario_mqtt
MQTT_PASSWORD=senha_mqtt

# Gateway
GATEWAY_URL=http://localhost:5001
PORT=8050
LOG_LEVEL=DEBUG

# Documentação (opcional)
DOCS_PROCEDURES_PATH=/caminho/para/procedimentos
```

## 5. Testar Instalação

**Webapp:**
```bash
cd webapp
python run_local.py
```
Acesse: http://localhost:8050

**Event Gateway (novo terminal):**
```bash
cd event-gateway
python api.py
```
Acesse: http://localhost:5001

## 6. Verificar Setup

- [ ] Webapp carrega sem erros
- [ ] Consegue acessar http://localhost:8050
- [ ] Event Gateway responde em http://localhost:5001
- [ ] MongoDB está conectando
- [ ] Página de login aparece

## 7. Troubleshooting

**Erro de importação:** Verifique se virtual environment está ativado
**Erro MongoDB:** Verifique MONGO_URI e credenciais
**Porta em uso:** Mude PORT no .env
**MQTT erro:** Verifique credenciais e endereço do broker

Pronto! Ambiente configurado com sucesso.
