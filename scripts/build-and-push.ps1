# build-and-push.ps1
param (
    [string]$tag = "latest"
)

Write-Host "INFO: Construindo imagens com a tag '$tag'..."
# O Docker Compose ainda precisa do arquivo original com a diretiva 'build' para saber COMO construir.
# Usamos um docker-compose.build.yml temporário ou um arquivo dedicado para isso.
# Por simplicidade agora, vamos usar um arquivo de override para build.

# Criamos um docker-compose.build.yml que aponta para os Dockerfiles
$buildComposeContent = @"
services:
  webapp:
    build: ./webapp
    image: ghcr.io/easytek-automation/easytek-data/webapp:$tag
  event-gateway:
    build: ./event-gateway
    image: ghcr.io/easytek-automation/easytek-data/event-gateway:$tag
  node-red:
    build: ./node-red
    image: ghcr.io/easytek-automation/easytek-data/node-red:$tag
"@
$buildComposeContent | Out-File -FilePath "docker-compose.build.yml" -Encoding utf8

try {
    # Constrói as imagens usando o arquivo de build
    docker compose -f "docker-compose.build.yml" build

    Write-Host "INFO: Enviando imagens para ghcr.io..."
    # Envia as imagens para o registro
    docker compose -f "docker-compose.build.yml" push

    Write-Host "SUCESSO: Imagens construídas e enviadas para o ghcr.io com a tag '$tag'."

} finally {
    # Limpa o arquivo temporário
    Remove-Item "docker-compose.build.yml"
}
