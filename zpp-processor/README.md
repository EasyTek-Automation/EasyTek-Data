# ZPP Processor Service

Serviço containerizado para processamento de planilhas ZPP (SAP Production Data).

## Visão Geral

Este serviço processa automaticamente planilhas Excel ZPP, limpa os dados, e faz upload para MongoDB. Funciona de duas formas:

- **Manual**: Via API REST (botão na interface web)
- **Automático**: Agendamento configurável (padrão: a cada 60 minutos)

## Arquitetura

```
┌─────────────────────────────────────┐
│  API REST (Flask)                   │
│  ├─ POST /api/zpp/process           │
│  ├─ GET  /api/zpp/status/<job_id>  │
│  ├─ GET  /api/zpp/history           │
│  ├─ GET  /api/zpp/files/*           │
│  └─ GET/PUT /api/zpp/config         │
└────────────┬────────────────────────┘
             │
    ┌────────┴────────┐
    │                 │
    ▼                 ▼
┌─────────┐      ┌──────────┐
│ MongoDB │      │ Volumes  │
│         │      │ /input   │
│         │      │ /output  │
│         │      │ /logs    │
└─────────┘      └──────────┘
```

## Endpoints

### Health Check
```bash
GET /api/health
```

### Processar Planilhas (Manual)
```bash
POST /api/zpp/process
Content-Type: application/json

{
  "triggered_by": "admin@user"  # Opcional
}

Response:
{
  "status": "success",
  "job_id": "uuid-v4",
  "message": "Processamento iniciado"
}
```

### Consultar Status de Job
```bash
GET /api/zpp/status/<job_id>

Response:
{
  "job_id": "uuid",
  "status": "running" | "success" | "failed",
  "started_at": "2026-02-12T10:30:00",
  "completed_at": "2026-02-12T10:32:15",
  "files_processed": 2,
  "total_uploaded": 15000
}
```

### Histórico de Processamentos
```bash
GET /api/zpp/history?limit=50&offset=0

Response:
{
  "total": 100,
  "limit": 50,
  "offset": 0,
  "logs": [...]
}
```

### Listar Arquivos Pendentes
```bash
GET /api/zpp/files/input

Response:
{
  "count": 3,
  "files": [
    {
      "filename": "zppprd_202601.xlsx",
      "size_mb": 2.5,
      "modified_at": "2026-02-12T10:00:00"
    }
  ]
}
```

### Listar Arquivos Processados
```bash
GET /api/zpp/files/output
```

### Configurações
```bash
# Obter configuração
GET /api/zpp/config

# Atualizar configuração
PUT /api/zpp/config
Content-Type: application/json

{
  "auto_process": true,
  "interval_minutes": 60,
  "updated_by": "admin@user"
}
```

## Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `MONGO_URI` | - | URI de conexão MongoDB (obrigatório) |
| `DB_NAME` | - | Nome do banco de dados (obrigatório) |
| `PORT` | 5002 | Porta da API |
| `LOG_LEVEL` | INFO | Nível de log (DEBUG, INFO, WARNING, ERROR) |
| `BASE_DATA_DIR` | /data | Diretório base dos volumes |
| `BATCH_SIZE` | 1000 | Tamanho do lote para upload MongoDB |
| `AUTO_PROCESS` | true | Ativar processamento automático |
| `INTERVAL_MINUTES` | 60 | Intervalo entre processamentos automáticos |

## Estrutura de Volumes

```
/data/
├── input/      # Planilhas pendentes (colocar aqui para processar)
├── output/     # Planilhas processadas (arquivamento)
└── logs/       # Logs detalhados (opcional)
```

## Collections MongoDB

### `zpp_processing_logs`
Histórico de processamentos:

```json
{
  "_id": ObjectId("..."),
  "job_id": "uuid-v4",
  "status": "success",
  "started_at": ISODate("..."),
  "completed_at": ISODate("..."),
  "duration_seconds": 135,
  "trigger_type": "manual" | "automatic",
  "triggered_by": "user@email.com",
  "files_processed": [
    {
      "filename": "zppprd_202601.xlsx",
      "type": "zppprd",
      "collection_name": "ZPP_Producao_2025",
      "uploaded_rows": 15000,
      "status": "success"
    }
  ],
  "summary": {
    "total_files": 2,
    "total_uploaded_records": 23300
  }
}
```

### `zpp_processor_config`
Configurações do serviço:

```json
{
  "_id": "global",
  "auto_process": true,
  "interval_minutes": 60,
  "archive_enabled": true,
  "last_updated": ISODate("..."),
  "updated_by": "admin@user"
}
```

## Desenvolvimento Local

```bash
# Instalar dependências
pip install -r requirements.txt

# Configurar .env
cp .env.example .env
# Editar .env com suas credenciais

# Criar diretórios
mkdir -p /data/input /data/output /data/logs

# Executar
python api.py
```

## Build Docker

```bash
# Build local
docker build -t zpp-processor:latest .

# Build multi-arquitetura
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag ghcr.io/easytek-automation/easytek-data/zpp-processor:latest \
  --push \
  .
```

## Docker Compose

```yaml
services:
  zpp-processor:
    image: ghcr.io/easytek-automation/easytek-data/zpp-processor:latest
    container_name: zpp-processor
    restart: unless-stopped
    environment:
      - MONGO_URI=${MONGO_URI}
      - DB_NAME=${DB_NAME}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - AUTO_PROCESS=${ZPP_AUTO_PROCESS:-true}
      - INTERVAL_MINUTES=${ZPP_INTERVAL_MINUTES:-60}
    volumes:
      - ./volumes/zpp/input:/data/input:rw
      - ./volumes/zpp/output:/data/output:rw
      - ./volumes/zpp/logs:/data/logs:rw
    networks:
      - easytek-net
    depends_on:
      - mongo
    ports:
      - "5002:5002"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5002/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Fluxo de Processamento

1. **Detecção**: Detecta automaticamente tipo de planilha (zppprd ou zppparadas)
2. **Limpeza**: Remove linhas totalizadoras
3. **Preparação**: Normaliza nomes de colunas, converte tipos
4. **Filtragem**: Remove equipamentos EMBAL*
5. **Upload**: Insere em lotes no MongoDB (1000 registros por vez)
6. **Indexação**: Cria/atualiza índices otimizados
7. **Arquivamento**: Move arquivo para /data/output
8. **Log**: Registra estatísticas em `zpp_processing_logs`

## Integração com Webapp

A webapp AMG_Data consome esta API através do módulo `/maintenance/zpp-processor`:

- Botão "Processar Agora" → POST /api/zpp/process
- Polling de status → GET /api/zpp/status/{job_id}
- Tabela de histórico → GET /api/zpp/history
- Configurações → GET/PUT /api/zpp/config

## Logs

Logs são enviados para stdout/stderr (capturados pelo Docker):

```bash
# Ver logs do container
docker logs zpp-processor

# Seguir logs em tempo real
docker logs -f zpp-processor
```

## Troubleshooting

### Serviço não inicia
- Verificar variáveis de ambiente MONGO_URI e DB_NAME
- Verificar conectividade com MongoDB
- Verificar permissões nos volumes

### Processamento não funciona
- Verificar se há arquivos em /data/input
- Verificar logs do serviço
- Testar manualmente: `curl -X POST http://localhost:5002/api/zpp/process`

### Scheduler não executa automaticamente
- Verificar configuração: `curl http://localhost:5002/api/zpp/config`
- Verificar se `auto_process: true`
- Verificar `interval_minutes`
- Ver logs do scheduler no output do container

### Índices MongoDB desatualizados ou corrompidos
Se os índices das collections ZPP estiverem com problemas (ex: campos antigos, duplicatas):

**Ferramenta de correção**: `../fix_zpp_indexes.py`

```bash
# Executar da raiz do projeto AMG_Data
python fix_zpp_indexes.py
```

Este script:
1. Remove índices antigos das collections ZPP_Producao_YYYY e ZPP_Paradas_YYYY
2. Mantém apenas o índice _id_ obrigatório
3. Permite que o próximo processamento recrie os índices corretos

Após executar, processe arquivos novamente via interface web ou API para recriar os índices.

## Licença

Interno - EasyTek Automation
