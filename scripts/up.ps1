# up.ps1
param (
    [Parameter(Mandatory=$true)]
    [ValidateSet('local', 'dev', 'prod')]
    [string]$env
)

# Define os caminhos para os arquivos de configuração
$envFile = ".\environments\$env\.env"
$overrideFile = ".\environments\$env\docker-compose.override.yml"

# --- Validação ---
Write-Host "INFO: Validando ambiente '$env'..."
if (-not (Test-Path $envFile)) {
    Write-Error "ERRO: Arquivo de ambiente '$envFile' não encontrado."
    exit 1
}
if (-not (Test-Path $overrideFile)) {
    Write-Error "ERRO: Arquivo de override '$overrideFile' não encontrado."
    exit 1
}

# --- Execução ---
try {
    # Passo 1: Subir o proxy e a rede. O -Wait garante que o comando termine antes de prosseguir.
    Write-Host "INFO: Iniciando a infraestrutura de proxy para o ambiente '$env'..."
    docker compose --env-file $envFile -f proxy-compose.yml up -d --wait
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao iniciar o proxy-compose."
    }

    # Passo 2: Subir a aplicação principal.
    Write-Host "INFO: Iniciando a aplicação principal para o ambiente '$env'..."
    docker compose --env-file $envFile -f docker-compose.yml -f $overrideFile up -d --build
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao iniciar o docker-compose principal."
    }

    Write-Host "SUCESSO: Ambiente '$env' iniciado."

} catch {
    Write-Error "ERRO: Falha durante a inicialização do ambiente. $_"
    exit 1
}
