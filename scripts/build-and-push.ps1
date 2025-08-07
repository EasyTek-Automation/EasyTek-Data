# easytek-infra/scripts/build-and-push.ps1
[CmdletBinding()]
param (
    [Parameter(Mandatory=$true)]
    [string]$tag
)

Write-Host "INFO: Iniciando build multi-arquitetura para a versão '$tag'..."

# Validação de pré-requisitos
if (-not $env:GITHUB_USER -or -not $env:GITHUB_PAT) {
    Write-Error "ERRO: As variáveis de ambiente GITHUB_USER e GITHUB_PAT devem ser definidas."
    exit 1
}

# Autenticação
Write-Host "INFO: Autenticando no ghcr.io..."
$env:GITHUB_PAT | docker login ghcr.io -u $env:GITHUB_USER --password-stdin
if ($LASTEXITCODE -ne 0) { throw "Falha na autenticação com o ghcr.io." }

# Define o caminho para a pasta de código
$CodePath = Resolve-Path "..\..\EasyTek-Data"

# Lista de serviços a serem construídos
$services = @("webapp", "event-gateway", "node-red")

# Loop para construir e enviar cada serviço
foreach ($service in $services) {
    $imageName = "ghcr.io/easytek-automation/easytek-data/$service`:$tag"
    # Caminho do contexto ajustado para a nova localização do script
    $contextPath = Join-Path $CodePath $service

    Write-Host "--------------------------------------------------"
    Write-Host "Construindo e enviando $imageName..."
    Write-Host "Contexto: $contextPath"
    Write-Host "--------------------------------------------------"

    docker buildx build --platform linux/amd64,linux/arm64 -t $imageName --push $contextPath

    if ($LASTEXITCODE -ne 0) {
        Write-Error "ERRO: Falha ao construir a imagem para o serviço '$service'. Abortando."
        exit 1
    }
}

Write-Host "--------------------------------------------------"
Write-Host "SUCESSO: Todas as imagens foram construídas e enviadas com a tag '$tag'."
Write-Host "--------------------------------------------------"
