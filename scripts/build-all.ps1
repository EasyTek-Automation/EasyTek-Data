# build-all.ps1
param (
    # Define um parâmetro obrigatório para a tag da versão.
    [Parameter(Mandatory=$true)]
    [string]$tag
)

Write-Host "INFO: Iniciando build multi-arquitetura para a versão '$tag'..."

# Lista de serviços a serem construídos
$services = @("webapp", "event-gateway", "node-red")

# Loop para construir e enviar cada serviço
foreach ($service in $services) {
    $imageName = "ghcr.io/easytek-automation/easytek-data/$service`:$tag"
    $contextPath = "./$service"

    Write-Host "--------------------------------------------------"
    Write-Host "Construindo e enviando $imageName..."
    Write-Host "--------------------------------------------------"

    docker buildx build --platform linux/amd64,linux/arm64 -t $imageName --push $contextPath

    # Verifica se o último comando falhou
    if ($LASTEXITCODE -ne 0) {
        Write-Error "ERRO: Falha ao construir a imagem para o serviço '$service'. Abortando."
        # Sai do script com um código de erro
        exit 1
    }
}

Write-Host "--------------------------------------------------"
Write-Host "SUCESSO: Todas as imagens foram construídas e enviadas com a tag '$tag'."
Write-Host "--------------------------------------------------"
