# Dockerfile (Versão Final e Robusta)

# 1. Imagem Base
FROM python:3.11-slim

# 2. Definir o diretório de trabalho
WORKDIR /app

# 3. Instalar dependências do sistema operacional
#    - build-essential: Para compilação de pacotes.
#    - dnsutils: Para a resolução de nomes SRV do MongoDB Atlas.
#    - libgssapi-krb5-2: Dependência para autenticação GSSAPI do pymongo.
RUN apt-get update && apt-get install -y build-essential dnsutils libgssapi-krb5-2 libkrb5-dev && rm -rf /var/lib/apt/lists/*

# 4. Copiar o arquivo de dependências
COPY requirements.txt .

# 5. Instalar as dependências Python
#    - Instala dnspython e gssapi para pymongo se conectar ao Atlas.
#    - Instala as dependências do seu requirements.txt.
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copiar o código da aplicação
COPY . .

# 7. Expor a porta
EXPOSE 8050

# 8. Comando para rodar a aplicação
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:8050", "src.run:server"]
