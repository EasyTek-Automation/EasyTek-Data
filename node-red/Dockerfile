# Usar a imagem oficial do Node-RED como base
FROM nodered/node-red:latest

# Copiar os arquivos de configuração e fluxo para o diretório de dados da imagem
# Esta é a etapa que estava faltando.
COPY flows.json /data/
COPY flows_cred.json /data/
COPY settings.js /data/
COPY package.json /data/

# Mudar TEMPORARIAMENTE para o diretório de dados para executar a instalação
WORKDIR /data

# Instalar os nós definidos no package.json
RUN npm install --unsafe-perm --only=production

# RESETAR o diretório de trabalho para o padrão da imagem.
# Isso garante que o entrypoint.sh seja encontrado na inicialização.
WORKDIR /usr/src/node-red
