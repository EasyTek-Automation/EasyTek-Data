#!/bin/bash
set -e

if [ -z "$1" ]; then
  echo "ERRO: Forneça um ambiente (local, dev, prod)."
  exit 1
fi

ENV=$1
ENV_FILE="./environments/$ENV/.env"
OVERRIDE_FILE="./environments/$ENV/docker-compose.override.yml"

echo "INFO: Parando o ambiente '$ENV'..."

# Derruba na ordem inversa
docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f "$OVERRIDE_FILE" down
docker compose --env-file "$ENV_FILE" -f proxy-compose.yml down

echo "SUCESSO: Ambiente '$ENV' parado."
