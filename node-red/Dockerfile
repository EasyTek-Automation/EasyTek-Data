# Usar a imagem oficial do Node-RED como base.
FROM nodered/node-red:latest

# Copiar o package.json para o diretório de dados do usuário.
COPY package.json /data/

# Mudar TEMPORARIAMENTE para o diretório de dados para executar a instalação.
WORKDIR /data

# Instalar os nós. Isso criará a pasta /data/node_modules.
RUN npm install --unsafe-perm

# RESETAR o diretório de trabalho para o padrão da imagem.
# Isso garante que o entrypoint.sh seja encontrado na inicialização.
WORKDIR /usr/src/node-red
