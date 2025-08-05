#!/bin/bash
set -e # Encerra o script se qualquer comando falhar

# --- Validação ---
if [ -z "$1" ] || ! [[ "$1" =~ ^(local|dev|prod)$ ]]; then
  echo "ERRO: Forneça um ambiente válido (local, dev, prod) como primeiro argumento."
  echo "Uso: ./scripts/up.sh <ambiente>"
  exit 1
fi

ENV=$1
ENV_FILE="./environments/$ENV/.env"
OVERRIDE_FILE="./environments/$ENV/docker-compose.override.yml"

echo "INFO: Validando ambiente '$ENV'..."
if [ ! -f "$ENV_FILE" ]; then
    echo "ERRO: Arquivo de ambiente '$ENV_FILE' não encontrado."
    exit 1
fi
if [ ! -f "$OVERRIDE_FILE" ]; then
    echo "ERRO: Arquivo de override '$OVERRIDE_FILE' não encontrado."
    exit 1
fi

# --- Execução ---
echo "INFO: Iniciando a infraestrutura de proxy para o ambiente '$ENV'..."
docker compose --env-file "$ENV_FILE" -f proxy-compose.yml up -d --wait

echo "INFO: Iniciando a aplicação principal para o ambiente '$ENV'..."
docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f "$OVERRIDE_FILE" up -d --build

echo "SUCESSO: Ambiente '$ENV' iniciado."
