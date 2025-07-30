# Usar a imagem oficial do Node-RED como base
FROM nodered/node-red:latest

# Copiar o package.json para o diretório de dados do usuário DENTRO da imagem
COPY package.json /data/

# Mudar TEMPORARIAMENTE para o diretório de dados para executar a instalação
WORKDIR /data

# Instalar os nós definidos no package.json
RUN npm install --unsafe-perm --only=production

# RESETAR o diretório de trabalho para o padrão da imagem.
# Isso garante que o entrypoint.sh seja encontrado na inicialização.
WORKDIR /usr/src/node-red
