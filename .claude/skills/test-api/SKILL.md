---
name: test-api
description: Testa endpoints da API do Event Gateway do AMG_Data. Use quando precisar verificar se a API está funcionando ou testar comandos MQTT.
argument-hint: [endpoint ou 'all']
allowed-tools: Bash(curl:*, python:*), Read
disable-model-invocation: true
---

# Testador de API - Event Gateway

Teste os endpoints da API do Event Gateway: **$ARGUMENTS**

## Pré-requisitos

1. Event Gateway deve estar rodando:
```bash
cd event-gateway
python api.py
```

2. URL padrão: `http://localhost:5001`

## Endpoints Disponíveis

### 1. Health Check

**GET** `/health` ou `/`

Verifica se a API está rodando.

```bash
curl http://localhost:5001/health
```

**Resposta esperada:**
```json
{
  "status": "ok",
  "service": "event-gateway",
  "version": "1.0"
}
```

### 2. Enviar Comando MQTT

**POST** `/api/command`

Publica um comando no broker MQTT.

**Payload:**
```json
{
  "topic": "amg/device/command",
  "payload": "START_MOTOR_01"
}
```

**Teste:**
```bash
curl -X POST http://localhost:5001/api/command \
  -H "Content-Type: application/json" \
  -d '{"topic":"amg/test/command","payload":"TEST_COMMAND"}'
```

**Resposta esperada:**
```json
{
  "status": "success",
  "message": "Command published",
  "topic": "amg/test/command"
}
```

### 3. Status do Broker

**GET** `/api/broker/status`

Verifica conexão com broker MQTT.

```bash
curl http://localhost:5001/api/broker/status
```

**Resposta esperada:**
```json
{
  "connected": true,
  "broker": "broker.address.com:8883"
}
```

## Testes Automatizados

Se $ARGUMENTS for "all", execute todos os testes:

### Script de Teste Completo

```bash
#!/bin/bash
echo "=== Testando Event Gateway API ==="

# 1. Health Check
echo -e "\n[1/3] Health Check..."
curl -s http://localhost:5001/health | python -m json.tool

# 2. Broker Status
echo -e "\n[2/3] Broker Status..."
curl -s http://localhost:5001/api/broker/status | python -m json.tool

# 3. Test Command
echo -e "\n[3/3] Enviando comando de teste..."
curl -s -X POST http://localhost:5001/api/command \
  -H "Content-Type: application/json" \
  -d '{"topic":"amg/test/command","payload":"PING"}' | python -m json.tool

echo -e "\n=== Testes Concluídos ==="
```

## Testes Específicos

Se $ARGUMENTS for um endpoint específico:

- `health` → Testa health check
- `command` → Testa envio de comando
- `broker` → Testa status do broker

## Variáveis de Ambiente

Verifique se estão configuradas corretamente:

```bash
# No arquivo .env do projeto
MQTT_BROKER_ADDRESS=broker.endereco.com
MQTT_BROKER_PORT=8883
MQTT_USERNAME=usuario
MQTT_PASSWORD=senha
GATEWAY_URL=http://localhost:5001
```

## Troubleshooting

**Erro: Connection Refused**
- Event Gateway não está rodando
- Porta incorreta (padrão: 5001)
- Verifique: `lsof -i :5001` (Linux/Mac) ou `netstat -ano | findstr :5001` (Windows)

**Erro: MQTT Connection Failed**
- Broker MQTT inacessível
- Credenciais incorretas
- Firewall bloqueando porta 8883
- Verifique variáveis de ambiente

**Erro: 404 Not Found**
- Endpoint incorreto
- Verifique rotas em `event-gateway/api.py`

**Erro: 500 Internal Server Error**
- Veja logs do Event Gateway
- Verifique configuração do MQTT client
- Valide formato do payload

## Verificar Logs

```bash
# No terminal onde Event Gateway está rodando
# Os logs aparecem em tempo real

# Ou verifique arquivo de log (se configurado)
tail -f event-gateway/logs/app.log
```

## Relatório de Teste

Após executar os testes, reporte:

✅ **Testes Bem-Sucedidos:**
- [ ] Health check responde
- [ ] Broker conectado
- [ ] Comando publicado com sucesso

❌ **Falhas:**
- [ ] Endpoint não responde
- [ ] Timeout de conexão
- [ ] Erro de autenticação

📊 **Métricas:**
- Tempo de resposta
- Status codes recebidos
- Erros encontrados

## Exemplo de Uso

```bash
# Testar tudo
/test-api all

# Testar endpoint específico
/test-api health
/test-api command
/test-api broker
```
