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
    && rm -rf /var/lib/apt/lists/*

# ─── Chromium PINADO em 149.0.7827.155 — NÃO desfixar sem validar o render ───
# Incidente 2026-07-07: o CI rebuildou a imagem e o apt (não-pinado) puxou o
# chromium 150 do trixie-security. kaleido 1.3.0 é incompatível com o chrome 150
# → falha "browser seemed to close immediately after starting" (BrowserFailedError)
# → os PNGs dos gráficos (MTBF/MTTR/Avaria) não renderizam → o DOCX do KPIReport
# baixa SEM gráficos. Provado: chromium 149 renderiza PNG ok; 150 falha.
# Fix: instalar a versão exata via snapshot.debian.org (o repo corrente já não
# serve o 149) e travar com `apt-mark hold`. chromium é dep do kaleido>=1.0 para
# renderização Plotly→PNG dos sunbursts/barras do KPIReport (RV-05).
# DÍVIDA (migração futura): trocar por chrome-headless-shell gerenciado pelo próprio
# kaleido (`kaleido_get_chrome`) → desacopla do apt do Debian e imuniza contra este
# drift. Ver .dev-docs/technical-debt/kpi-report-chromium-pin-149.md
ARG CHROMIUM_VERSION=149.0.7827.155-1~deb13u1
ARG CHROMIUM_SNAPSHOT=20260622T000000Z
RUN echo "deb [check-valid-until=no] https://snapshot.debian.org/archive/debian-security/${CHROMIUM_SNAPSHOT}/ trixie-security main" \
      > /etc/apt/sources.list.d/snapshot-chromium.list \
    && apt-get -o Acquire::Check-Valid-Until=false update \
    && apt-get install -y --no-install-recommends \
       chromium=${CHROMIUM_VERSION} \
       chromium-common=${CHROMIUM_VERSION} \
       chromium-sandbox=${CHROMIUM_VERSION} \
    && apt-mark hold chromium chromium-common chromium-sandbox \
    && rm -f /etc/apt/sources.list.d/snapshot-chromium.list \
    && rm -rf /var/lib/apt/lists/*

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