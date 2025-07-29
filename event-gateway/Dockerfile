# event-gateway/Dockerfile

# 1. Imagem Base
FROM python:3.11-slim

# 2. Definir o diretório de trabalho
WORKDIR /app

# 3. Copiar o arquivo de dependências
COPY requirements.txt .

# 4. Instalar as dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiar o código da aplicação
COPY . .

# 6. Expor a porta que o Flask vai usar
EXPOSE 5001

# 7. Comando para rodar a aplicação
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5001", "api:app"]
