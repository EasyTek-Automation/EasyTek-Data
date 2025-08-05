# down.ps1
param (
    [Parameter(Mandatory=$true)]
    [ValidateSet('local', 'dev', 'prod')]
    [string]$env
)

$envFile = ".\environments\$env\.env"
$overrideFile = ".\environments\$env\docker-compose.override.yml"

Write-Host "INFO: Parando o ambiente '$env'..."

# Passo 1: Derrubar a aplicação principal
docker compose --env-file $envFile -f docker-compose.yml -f $overrideFile down

# Passo 2: Derrubar o proxy
docker compose --env-file $envFile -f proxy-compose.yml down

Write-Host "SUCESSO: Ambiente '$env' parado."
