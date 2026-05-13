# Dockerfile (Versão Final e Robusta)

# 1. Imagem Base
FROM python:3.11-slim

# 2. Definir o diretório de trabalho
WORKDIR /app

# 3. Instalar dependências do sistema operacional
#    - build-essential: Para compilação de pacotes.
#    - dnsutils: Para a resolução de nomes SRV do MongoDB Atlas.
#    - libgssapi-krb5-2: Dependência para autenticação GSSAPI do pymongo.
#    - libpango*/libharfbuzz*/libfontconfig1: WeasyPrint (PDF server-side)
#    - fonts-liberation: fontes base para o PDF
RUN apt-get update && apt-get install -y \
    build-essential \
    dnsutils \
    libgssapi-krb5-2 \
    libkrb5-dev \
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libfontconfig1 \
    fonts-liberation \
    chromium \
    && rm -rf /var/lib/apt/lists/*
# chromium: dependência do kaleido>=1.0 para renderização Plotly→PNG dos sunbursts do KPIReport (RV-05).
# Substituir por chromium-headless-shell em ciclo futuro — dívida registrada em
# .dev-docs/technical-debt/kpi-report-chromium-headless-shell.md.

# 4. Copiar o arquivo de dependências
COPY requirements.txt .

# 5. Instalar as dependências Python
#    - Instala dnspython e gssapi para pymongo se conectar ao Atlas.
#    - Instala as dependências do seu requirements.txt.
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copiar o código da aplicação
# ARG CACHEBUST força invalidação desta camada sem afetar apt/pip acima
ARG CACHEBUST=1
COPY . .

# 7. Expor a porta
EXPOSE 8050

# 8. Comando para rodar a aplicação
# ... (todo o resto do Dockerfile) ...

# 8. Comando para rodar a aplicação
# Adiciona --chdir para mudar para o diretório 'src' antes de iniciar.
# Flags KPIReport (RV-03):
#  --max-requests / --jitter: reciclagem periódica de workers, mitiga hangs cumulativos do kaleido
#  --timeout 90:               margem para o timeout duro de 60s da SP-12 (default gunicorn era 30s)
CMD ["gunicorn", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8050", \
     "--max-requests", "200", \
     "--max-requests-jitter", "50", \
     "--timeout", "90", \
     "src.run:server"]