FROM python:3.11-slim

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Definir diretório de trabalho
WORKDIR /app

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY . .

# Criar diretórios de trabalho (serão sobrescritos por volumes)
RUN mkdir -p /data/input /data/output /data/logs

# Expor porta da API
EXPOSE 5002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5002/api/health || exit 1

# Comando de inicialização
# NOTA: Usar apenas 1 worker porque o scheduler roda em background
# Múltiplos workers causariam processamentos duplicados
CMD ["gunicorn", "--workers", "1", "--bind", "0.0.0.0:5002", "--timeout", "600", "--preload", "api:app"]
