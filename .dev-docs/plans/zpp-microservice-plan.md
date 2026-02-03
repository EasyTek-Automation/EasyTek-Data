# Plano: Micro-serviço ZPP Processor com Agendamento Automático

## 🎯 Objetivo

Transformar o sistema de processamento de planilhas ZPP em um micro-serviço Docker independente com:
- ✅ Execução agendada automática (8:00, 12:00, 18:00)
- ✅ Execução manual via webapp
- ✅ Planilhas em volume externo (não no código)
- ✅ Código organizado em `zpp_input/` (não na raiz)

---

## 📂 Estrutura Final

### Diretório do Micro-serviço

```
E:\Projetos Python\AMG_Data\zpp_input\
├── src/
│   ├── api.py              # Flask REST API (porta 5002)
│   ├── scheduler.py        # APScheduler (agendamento 8h, 12h, 18h)
│   ├── processor.py        # ZPPProcessor (lógica principal)
│   ├── cleaner.py          # ZPPCleaner (limpeza de dados)
│   ├── detector.py         # Detecção de tipo (zppprd vs zppparadas)
│   ├── utils.py            # Funções auxiliares (normalize_column_name, indexes)
│   └── config.py           # Configurações centralizadas
├── Dockerfile
├── requirements.txt
├── supervisord.conf        # Gerencia API + Scheduler
├── .dockerignore
├── .env.example
└── README.md

# Arquivos de dados (não versionados, volume Docker)
├── input/                  # Planilhas para processar (montado via volume)
└── processed/              # Arquivos processados (montado via volume)
```

**Nota**: `input/` e `processed/` são criados/montados via volume Docker, **não** versionados no Git.

---

## 🏗️ Arquitetura do Micro-serviço

### 1. API Flask (`src/api.py`)

**Porta**: 5002
**Endpoints**:

```python
GET  /api/health
     Response: {"status": "healthy", "version": "1.0.0"}

GET  /api/status
     Response: {
         "pending_files": 3,
         "files": ["arquivo1.xlsx", "arquivo2.xlsx"],
         "last_run": "2026-01-29T08:00:00",
         "next_run": "2026-01-29T12:00:00"
     }

POST /api/process
     Response: {
         "status": "success|error",
         "processed": 2,
         "uploaded": 1500,
         "errors": []
     }

POST /api/process/file
     Body: {"filename": "arquivo.xlsx"}
     Response: {
         "status": "success|error",
         "file": "arquivo.xlsx",
         "uploaded": 750,
         "collection": "ZPP_Producao_2025"
     }
```

**Implementação Base**:
```python
from flask import Flask, request, jsonify
from processor import ZPPProcessor
import os

app = Flask(__name__)
processor = ZPPProcessor(
    mongo_uri=os.getenv('MONGO_URI'),
    db_name=os.getenv('DB_NAME'),
    input_dir='/app/data/input',
    processed_dir='/app/data/processed'
)

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "version": "1.0.0"})

@app.route('/api/process', methods=['POST'])
def process_all():
    result = processor.process_directory()
    return jsonify(result)

# ... outros endpoints
```

### 2. Scheduler (`src/scheduler.py`)

**Agendamento**: APScheduler com CronTrigger
**Horários**: 8:00, 12:00, 18:00 (timezone: America/Sao_Paulo)

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from processor import ZPPProcessor
import logging

logger = logging.getLogger(__name__)

def scheduled_job():
    """Job executado nos horários agendados"""
    logger.info("Iniciando processamento agendado...")
    processor = ZPPProcessor(...)
    result = processor.process_directory()
    logger.info(f"Processamento concluído: {result}")

def start_scheduler():
    scheduler = BackgroundScheduler(timezone='America/Sao_Paulo')

    # Adicionar jobs para 8:00, 12:00, 18:00
    scheduler.add_job(
        scheduled_job,
        CronTrigger(hour=8, minute=0),
        id='zpp_8am',
        max_instances=1,  # Prevenir execução paralela
        replace_existing=True
    )

    scheduler.add_job(
        scheduled_job,
        CronTrigger(hour=12, minute=0),
        id='zpp_12pm',
        max_instances=1
    )

    scheduler.add_job(
        scheduled_job,
        CronTrigger(hour=18, minute=0),
        id='zpp_6pm',
        max_instances=1
    )

    scheduler.start()
    logger.info("Scheduler iniciado com 3 jobs (8h, 12h, 18h)")
```

### 3. Processor (`src/processor.py`)

**Refatoração de**: `process_zpp_to_mongo.py`

```python
class ZPPProcessor:
    def __init__(self, mongo_uri, db_name, input_dir, processed_dir):
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.input_dir = Path(input_dir)
        self.processed_dir = Path(processed_dir)
        self.processed_dir.mkdir(exist_ok=True)

    def process_directory(self):
        """Processa todos os arquivos Excel no diretório de entrada"""
        excel_files = self._find_excel_files()
        results = []

        for file_path in excel_files:
            result = self.process_file(file_path)
            results.append(result)

        return {
            'total': len(results),
            'success': sum(1 for r in results if r['success']),
            'errors': [r for r in results if not r['success']]
        }

    def process_file(self, file_path):
        """Processa um arquivo (5 etapas + arquivamento)"""
        # 1. Detectar tipo
        # 2. Limpar dados
        # 3. Preparar para MongoDB
        # 4. Upload em lotes
        # 5. Criar índices
        # 6. Mover para processed/
        pass
```

**Migração**:
- `process_zpp_to_mongo.py` (608 linhas) → `processor.py` (manter lógica completa)
- Adaptar para receber `input_dir` e `processed_dir` como parâmetros
- Manter todas as funcionalidades: detecção, limpeza, normalização, upload, índices

### 4. Cleaner (`src/cleaner.py`)

**Refatoração de**: `clean_zpp_data.py`

```python
class ZPPCleaner:
    """Move classe ZPPCleaner completa de clean_zpp_data.py"""
    CRITICAL_COLUMNS = {
        'zppprd': {
            'identifier': 'Pto.Trab.',
            'required': ['Pto.Trab.', 'FIniNotif', 'FFinNotif', 'Ordem'],
            'description': 'ZPP PRD - Produção'
        },
        'zppparadas': {
            'identifier': 'LINEA',
            'required': ['LINEA', 'Ordem', 'DATA INICIO', 'DATA FIM'],
            'description': 'ZPP PARADAS - Paradas de Linha'
        }
    }
    # ... resto da implementação
```

### 5. Detector (`src/detector.py`)

```python
def detect_file_type(file_path: str) -> Optional[str]:
    """
    Detecta automaticamente o tipo de arquivo ZPP

    Returns:
        'zppprd', 'zppparadas' ou None se não reconhecido
    """
    # Move função detect_file_type de clean_zpp_data.py
    pass
```

### 6. Utils (`src/utils.py`)

```python
def normalize_column_name(col_name: str) -> str:
    """
    Normaliza nome de coluna para MongoDB-friendly

    'DURAÇÃO(min)' → 'duracao_min'
    'DATA INÍCIO' → 'data_inicio'
    """
    pass

def create_indexes_producao(collection):
    """Cria índices otimizados para Produção"""
    pass

def create_indexes_paradas(collection):
    """Cria índices otimizados para Paradas"""
    pass
```

### 7. Config (`src/config.py`)

```python
import os

class Config:
    # MongoDB
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
    DB_NAME = os.getenv('DB_NAME', 'Cluster-EasyTek')

    # Diretórios
    INPUT_DIR = os.getenv('ZPP_INPUT_DIR', '/app/data/input')
    PROCESSED_DIR = os.getenv('ZPP_PROCESSED_DIR', '/app/data/processed')

    # Agendamento
    SCHEDULE_ENABLED = os.getenv('ZPP_SCHEDULE_ENABLED', 'true').lower() == 'true'
    SCHEDULE_HOURS = [8, 12, 18]  # Horários fixos

    # API
    API_PORT = int(os.getenv('ZPP_API_PORT', 5002))

    # Processamento
    BATCH_SIZE = int(os.getenv('ZPP_BATCH_SIZE', 1000))
```

---

## 🐳 Containerização

### Dockerfile

```dockerfile
FROM python:3.11-slim

# Instalar supervisor para gerenciar API + Scheduler
RUN apt-get update && apt-get install -y supervisor && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar requirements e instalar dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código-fonte
COPY src/ ./src/
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Criar diretórios de dados (serão montados via volume)
RUN mkdir -p /app/data/input /app/data/processed

EXPOSE 5002

# Iniciar supervisord (gerencia Flask API + APScheduler)
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
```

### supervisord.conf

```ini
[supervisord]
nodaemon=true
user=root

[program:api]
command=gunicorn --workers 2 --bind 0.0.0.0:5002 --chdir /app/src api:app
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0

[program:scheduler]
command=python -m src.scheduler
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
```

### requirements.txt

```
flask==3.1.1
gunicorn==21.2.0
pymongo==4.13.2
pandas==2.3.1
openpyxl==3.1.2
python-dotenv==1.1.1
APScheduler==3.10.4
requests==2.32.4
```

### .dockerignore

```
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.so
.env
.venv
venv/
*.log
.git/
.gitignore
README.md
.dev-docs/
input/
processed/
*.xlsx
*.xls
```

---

## 🔧 Integração Docker-Compose

### AMG_Infra/docker-compose.yml

```yaml
services:
  # ... serviços existentes (webapp, event-gateway, node-red)

  zpp-processor:
    image: ghcr.io/easytek-automation/easytek-data/zpp-processor:${TAG:-latest}
    container_name: zpp-processor
    ports:
      - "5002:5002"
    env_file:
      - .env.common
    environment:
      - MONGO_URI=${MONGO_URI}
      - DB_NAME=${DB_NAME}
      - ZPP_INPUT_DIR=/app/data/input
      - ZPP_PROCESSED_DIR=/app/data/processed
      - ZPP_SCHEDULE_ENABLED=true
      - ZPP_API_PORT=5002
    volumes:
      # Volume para planilhas de entrada e processados
      - ${ZPP_INPUT_PATH}:/app/data/input
      - ${ZPP_PROCESSED_PATH}:/app/data/processed
    networks:
      - easytek-net
    depends_on:
      - database
    restart: unless-stopped
```

### Variáveis de Ambiente por Ambiente

**AMG_Infra/environments/local/.env**:
```env
# ZPP Processor
ZPP_INPUT_PATH=E:/Projetos Python/AMG_Data/zpp_input/input
ZPP_PROCESSED_PATH=E:/Projetos Python/AMG_Data/zpp_input/processed
```

**AMG_Infra/environments/dev/.env**:
```env
ZPP_INPUT_PATH=/mnt/data/zpp/input
ZPP_PROCESSED_PATH=/mnt/data/zpp/processed
```

**AMG_Infra/environments/prod/.env**:
```env
ZPP_INPUT_PATH=/mnt/production/zpp/input
ZPP_PROCESSED_PATH=/mnt/production/zpp/processed
```

---

## 🌐 Integração com Webapp

### 1. Callback: `webapp/src/callbacks_registers/zpp_processor_callbacks.py`

```python
import requests
import os
from dash import Input, Output, html
import dash_bootstrap_components as dbc

ZPP_SERVICE_URL = os.getenv('ZPP_SERVICE_URL', 'http://zpp-processor:5002')

def register_zpp_processor_callbacks(app):

    @app.callback(
        Output('zpp-status-content', 'children'),
        Input('zpp-status-interval', 'n_intervals')
    )
    def update_zpp_status(n):
        """Atualiza status do processador ZPP"""
        try:
            response = requests.get(
                f"{ZPP_SERVICE_URL}/api/status",
                timeout=5
            )
            response.raise_for_status()
            data = response.json()

            return dbc.Card([
                dbc.CardBody([
                    html.H5("Status ZPP Processor"),
                    html.P(f"Arquivos pendentes: {data['pending_files']}"),
                    html.P(f"Último processamento: {data.get('last_run', 'N/A')}"),
                    html.P(f"Próximo agendado: {data.get('next_run', 'N/A')}")
                ])
            ])
        except Exception as e:
            return dbc.Alert(f"Erro ao conectar: {str(e)}", color="danger")

    @app.callback(
        Output('zpp-process-result', 'children'),
        Input('zpp-process-button', 'n_clicks'),
        prevent_initial_call=True
    )
    def trigger_manual_process(n_clicks):
        """Executa processamento manual"""
        try:
            response = requests.post(
                f"{ZPP_SERVICE_URL}/api/process",
                timeout=300  # 5 minutos
            )
            response.raise_for_status()
            data = response.json()

            if data['status'] == 'success':
                return dbc.Alert(
                    f"✓ Processados: {data['processed']} | Carregados: {data['uploaded']} docs",
                    color="success"
                )
            else:
                return dbc.Alert(
                    f"Erros: {len(data['errors'])}",
                    color="warning"
                )
        except Exception as e:
            return dbc.Alert(f"Erro: {str(e)}", color="danger")
```

### 2. Página Admin: `webapp/src/pages/admin/zpp_processor.py`

```python
from dash import html, dcc
import dash_bootstrap_components as dbc

def layout():
    """Página de administração do ZPP Processor"""
    return dbc.Container([
        html.H2("⚙️ Administração ZPP Processor"),

        # Status Card
        dbc.Row([
            dbc.Col([
                html.Div(id='zpp-status-content'),
                dcc.Interval(
                    id='zpp-status-interval',
                    interval=30*1000,  # Atualiza a cada 30s
                    n_intervals=0
                )
            ])
        ]),

        # Botão de Processamento Manual
        dbc.Row([
            dbc.Col([
                dbc.Button(
                    "▶️ Processar Agora",
                    id='zpp-process-button',
                    color="primary",
                    size="lg",
                    className="mt-3"
                ),
                html.Div(id='zpp-process-result', className="mt-3")
            ])
        ])
    ], fluid=True, className="p-4")
```

### 3. Roteamento: Adicionar em `webapp/src/index.py`

```python
# Nas importações
from src.pages.admin import zpp_processor

# No dicionário ROUTES
ROUTES = {
    # ... rotas existentes
    '/admin/zpp-processor': zpp_processor.layout,
}
```

### 4. Permissões: Adicionar em `webapp/src/config/access_control.py`

```python
ROUTE_ACCESS = {
    # ... permissões existentes
    '/admin/zpp-processor': {
        'min_level': 3,
        'perfis': ['admin'],
        'shared': False
    },
}
```

### 5. Registrar Callbacks: `webapp/src/callbacks.py`

```python
# Importar
from src.callbacks_registers.zpp_processor_callbacks import register_zpp_processor_callbacks

# Registrar
def register_callbacks(app):
    # ... callbacks existentes
    register_zpp_processor_callbacks(app)
```

---

## 🔄 Migração dos Scripts

### Passos de Movimentação

```bash
# 1. Criar estrutura no zpp_input/
mkdir -p zpp_input/src
mkdir -p zpp_input/input
mkdir -p zpp_input/processed

# 2. Mover scripts (serão refatorados depois)
# NÃO mover ainda - apenas marcar como deprecated
```

### Mapeamento de Código

| Arquivo Atual | Destino | Ação |
|---------------|---------|------|
| `process_zpp_quick.py` (raiz) | **DEPRECAR** | Lógica vai para `api.py` endpoint |
| `process_zpp_to_mongo.py` (raiz) | `zpp_input/src/processor.py` | Refatorar classe ZPPProcessor |
| `clean_zpp_data.py` (raiz) | `zpp_input/src/cleaner.py` | Mover classe ZPPCleaner |
| `fix_zpp_indexes.py` (raiz) | `zpp_input/src/utils.py` | Integrar como função |

### Estratégia de Transição

**Fase 1: Criação (sem remover antigos)**
1. Criar `zpp_input/src/` com código refatorado
2. Testar novo micro-serviço
3. Validar integração com webapp

**Fase 2: Deprecação (após validação)**
4. Adicionar warning nos scripts da raiz:
```python
# process_zpp_quick.py
import warnings
warnings.warn(
    "Este script está deprecated. Use o micro-serviço zpp-processor.",
    DeprecationWarning
)
```

**Fase 3: Remoção (após 2 sprints)**
5. Remover scripts da raiz
6. Atualizar .gitignore
7. Atualizar documentação

---

## 📝 Documentação

### Arquivos a Criar/Atualizar

#### 1. `zpp_input/README.md` (NOVO)

```markdown
# ZPP Processor - Micro-serviço de Processamento de Planilhas

Serviço Docker para processamento automático e manual de planilhas ZPP (SAP).

## Funcionalidades

- ✅ Processamento agendado (8:00, 12:00, 18:00)
- ✅ Execução manual via API REST
- ✅ Detecção automática de tipo (Produção vs Paradas)
- ✅ Limpeza de dados (remove totalizadores)
- ✅ Upload para MongoDB com índices otimizados
- ✅ Arquivamento automático

## Uso Local

### Desenvolvimento
\`\`\`bash
cd zpp_input
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
pip install -r requirements.txt
python src/api.py
\`\`\`

### Docker
\`\`\`bash
docker build -t zpp-processor .
docker run -p 5002:5002 --env-file .env zpp-processor
\`\`\`

## API Endpoints

- GET /api/health
- GET /api/status
- POST /api/process
- POST /api/process/file

## Configuração

Ver `.env.example` para variáveis necessárias.
```

#### 2. `.dev-docs/modules/zpp-processor/README.md` (NOVO)

```markdown
# ZPP Processor - Documentação Técnica

## Arquitetura

### Componentes
- API Flask (porta 5002)
- APScheduler (agendamento)
- ZPPProcessor (lógica de negócio)
- ZPPCleaner (limpeza de dados)

### Fluxo de Processamento
1. Detectar tipo de arquivo
2. Limpar dados
3. Normalizar colunas
4. Upload MongoDB (lotes de 1000)
5. Criar índices
6. Arquivar arquivo

## Detecção de Tipo

### Assinaturas
- **zppprd**: Pto.Trab., Kg.Proc., HorasAct., FIniNotif, FFinNotif
- **zppparadas**: LINEA, DATA INICIO, DATA FIM, MOTIVO, DURAÇÃO(min)

## Normalização de Colunas

Exemplos:
- 'DURAÇÃO(min)' → 'duracao_min'
- 'DATA INÍCIO' → 'data_inicio'
- 'Pto.Trab.' → 'pto_trab'

## Índices MongoDB

### Produção (5 índices)
- idx_equipamento_data
- idx_ordem_unique (UNIQUE)
- idx_range_datas
- idx_year
- idx_equipamento_producao

### Paradas (7 índices)
- idx_linha_data
- idx_ordem
- idx_parada_unique (UNIQUE)
- idx_motivo
- idx_range_datas
- idx_year
- idx_duracao
```

#### 3. Atualizar `CLAUDE.md` (raiz)

Adicionar seção:

```markdown
## ZPP Processor Microservice

Micro-serviço para processamento de planilhas ZPP.

**Localização**: `zpp_input/`

**Documentação**:
- Técnica: `.dev-docs/modules/zpp-processor/`
- README: `zpp_input/README.md`

**API**: http://localhost:5002/api/
```

#### 4. `.dev-docs/operations/zpp-processor-deployment.md` (NOVO)

```markdown
# Deploy ZPP Processor

## Build e Push

\`\`\`bash
cd zpp_input
docker build -t ghcr.io/easytek-automation/easytek-data/zpp-processor:1.0.0 .
docker push ghcr.io/easytek-automation/easytek-data/zpp-processor:1.0.0
\`\`\`

## Deploy em Ambiente

\`\`\`bash
cd AMG_Infra
TAG=1.0.0 ./scripts/up.sh prod
\`\`\`

## Verificação

1. Healthcheck: `curl http://localhost:5002/api/health`
2. Status: `curl http://localhost:5002/api/status`
3. Logs: `docker logs zpp-processor`
```

---

## 🧪 Verificação e Testes

### Checklist Pré-Deploy

#### Testes Locais (Sem Docker)

```bash
cd zpp_input
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate no Windows
pip install -r requirements.txt

# Testar API
python src/api.py
# Acessar: http://localhost:5002/api/health

# Testar processamento
python -c "from src.processor import ZPPProcessor; p = ZPPProcessor(...); p.process_directory()"
```

- [ ] API Flask inicia sem erros
- [ ] Endpoint `/api/health` retorna 200
- [ ] Endpoint `/api/status` retorna JSON correto
- [ ] `ZPPProcessor` processa arquivo de teste
- [ ] Arquivos são movidos para `processed/`
- [ ] Dados são carregados no MongoDB
- [ ] Índices são criados corretamente

#### Testes Docker (Local)

```bash
cd zpp_input
docker build -t zpp-processor:test .
docker run -p 5002:5002 --env-file .env.test zpp-processor:test

# Verificar logs
docker logs -f <container_id>
```

- [ ] Imagem build sem erros
- [ ] Container inicia e mantém running
- [ ] Supervisord gerencia API + Scheduler
- [ ] Logs mostram "Scheduler iniciado com 3 jobs"
- [ ] Healthcheck funciona
- [ ] Volume montado corretamente

#### Testes de Integração (Docker-Compose)

```bash
cd AMG_Infra
./scripts/up.sh local
```

- [ ] Service `zpp-processor` sobe junto com stack
- [ ] Conecta ao MongoDB (`database` service)
- [ ] Rede `easytek-net` funciona
- [ ] Volumes persistem dados
- [ ] API acessível de outros containers

#### Testes de Agendamento

```bash
# Alterar horário para próximos 2 minutos e testar
# Modificar temporariamente em scheduler.py:
# CronTrigger(hour=14, minute=32)  # Horário atual + 2min
```

- [ ] Job executa no horário agendado
- [ ] Logs mostram "Iniciando processamento agendado..."
- [ ] Arquivos são processados automaticamente
- [ ] Não há execução paralela (max_instances=1)
- [ ] Próximo job é agendado corretamente

#### Testes de Integração Webapp

```bash
# Acessar webapp
http://localhost:8050/admin/zpp-processor
```

- [ ] Página carrega sem erros (permissão admin)
- [ ] Status atualiza a cada 30s
- [ ] Botão "Processar Agora" funciona
- [ ] Feedback de sucesso/erro aparece
- [ ] Contador de arquivos pendentes correto

#### Testes End-to-End

**Cenário 1: Processamento Manual**
1. Colocar arquivo Excel em `zpp_input/input/`
2. Acessar webapp → Admin → ZPP Processor
3. Clicar "Processar Agora"
4. Verificar arquivo movido para `processed/`
5. Verificar dados no MongoDB

**Cenário 2: Processamento Agendado**
1. Colocar arquivo Excel em `zpp_input/input/`
2. Aguardar próximo horário agendado
3. Verificar logs do container
4. Verificar arquivo processado
5. Verificar dados no MongoDB

**Cenário 3: Múltiplos Arquivos**
1. Colocar 5 arquivos Excel mistos (zppprd + zppparadas)
2. Processar via API ou agendamento
3. Verificar todos foram processados
4. Verificar collections corretas criadas (Producao_2025, Paradas_2025)

- [ ] Cenário 1 completo
- [ ] Cenário 2 completo
- [ ] Cenário 3 completo

---

## 📅 Fases de Implementação

### Fase 1: Desenvolvimento Local (3-5 dias)

**Objetivo**: Criar código-fonte refatorado e testar localmente.

1. **Criar estrutura de diretórios**
   ```bash
   mkdir -p zpp_input/src
   cd zpp_input
   ```

2. **Refatorar scripts existentes**
   - Copiar `process_zpp_to_mongo.py` → `src/processor.py`
   - Copiar `clean_zpp_data.py` → `src/cleaner.py`
   - Criar `src/detector.py` (extrair função `detect_file_type`)
   - Criar `src/utils.py` (funções auxiliares)
   - Criar `src/config.py` (configurações)

3. **Criar API Flask**
   - `src/api.py` com 4 endpoints
   - Testar com Postman/curl

4. **Criar Scheduler**
   - `src/scheduler.py` com APScheduler
   - Testar agendamento (alterar horário para 2min no futuro)

5. **Testes unitários locais**
   - Processar arquivo de teste
   - Verificar MongoDB
   - Validar arquivamento

**Entregável**: Código funcional rodando localmente sem Docker.

### Fase 2: Containerização (2-3 dias)

**Objetivo**: Criar imagem Docker e testar isoladamente.

6. **Criar Dockerfile**
   - Base: `python:3.11-slim`
   - Instalar supervisor
   - Copiar código

7. **Criar supervisord.conf**
   - Gerenciar API + Scheduler

8. **Criar requirements.txt**
   - Flask, gunicorn, pymongo, pandas, APScheduler

9. **Criar .dockerignore**

10. **Build e teste local**
    ```bash
    docker build -t zpp-processor:test .
    docker run -p 5002:5002 --env-file .env zpp-processor:test
    ```

11. **Validar volumes**
    ```bash
    docker run -v ./input:/app/data/input zpp-processor:test
    ```

**Entregável**: Imagem Docker funcional testada localmente.

### Fase 3: Integração AMG_Infra (2-3 dias)

**Objetivo**: Integrar no docker-compose e testar stack completo.

12. **Atualizar `AMG_Infra/docker-compose.yml`**
    - Adicionar service `zpp-processor`
    - Configurar volumes, networks, depends_on

13. **Configurar variáveis por ambiente**
    - `environments/local/.env`
    - `environments/dev/.env`
    - `environments/prod/.env`

14. **Testar stack completo**
    ```bash
    cd AMG_Infra
    ./scripts/up.sh local
    ```

15. **Validar comunicação entre serviços**
    - zpp-processor → database
    - webapp → zpp-processor (healthcheck)

**Entregável**: Stack completo funcionando em ambiente local.

### Fase 4: Integração Webapp (3-4 dias)

**Objetivo**: Criar interface de administração na webapp.

16. **Criar callback**
    - `webapp/src/callbacks_registers/zpp_processor_callbacks.py`
    - Registrar em `callbacks.py`

17. **Criar página admin**
    - `webapp/src/pages/admin/zpp_processor.py`
    - Adicionar rota em `index.py`
    - Configurar permissões em `access_control.py`

18. **Testar integração**
    - Login como admin
    - Acessar `/admin/zpp-processor`
    - Executar processamento manual
    - Verificar status

19. **Ajustar UI/UX**
    - Melhorar feedback visual
    - Adicionar loading states
    - Tratamento de erros

**Entregável**: Interface funcional integrada na webapp.

### Fase 5: Deploy e Validação (2-3 dias)

**Objetivo**: Deploy em dev/prod e validação completa.

20. **Build e push para registry**
    ```bash
    docker build -t ghcr.io/.../zpp-processor:1.0.0 .
    docker push ghcr.io/.../zpp-processor:1.0.0
    ```

21. **Deploy em dev**
    ```bash
    TAG=1.0.0 ./scripts/up.sh dev
    ```

22. **Validar agendamento em dev**
    - Colocar arquivos de teste
    - Aguardar horário agendado (ou ajustar temporariamente)
    - Verificar processamento automático

23. **Deploy em prod**
    ```bash
    TAG=1.0.0 ./scripts/up.sh prod
    ```

24. **Monitoramento pós-deploy**
    - Verificar logs diários
    - Confirmar execução nos 3 horários
    - Validar dados no MongoDB

**Entregável**: Serviço em produção funcionando com agendamento.

### Fase 6: Limpeza e Documentação (1-2 dias)

**Objetivo**: Deprecar scripts antigos e finalizar documentação.

25. **Marcar scripts como deprecated**
    - Adicionar warnings em `process_zpp_quick.py`
    - Adicionar warnings em `process_zpp_to_mongo.py`
    - Adicionar warnings em `clean_zpp_data.py`

26. **Atualizar documentação**
    - Criar `zpp_input/README.md`
    - Criar `.dev-docs/modules/zpp-processor/`
    - Atualizar `CLAUDE.md`

27. **Remover scripts antigos (após 2 sprints)**
    ```bash
    git rm process_zpp_quick.py
    git rm process_zpp_to_mongo.py
    git rm clean_zpp_data.py
    git rm fix_zpp_indexes.py
    ```

28. **Atualizar .gitignore**
    ```gitignore
    # ZPP Processor
    zpp_input/input/
    zpp_input/processed/
    zpp_input/**/*.xlsx
    zpp_input/**/*.xls
    ```

**Entregável**: Código limpo, documentado e scripts antigos removidos.

---

## ⚙️ Variáveis de Ambiente

### Necessárias (`.env.common` ou `.env`)

```env
# MongoDB
MONGO_URI=mongodb://database:27017
DB_NAME=Cluster-EasyTek

# ZPP Processor
ZPP_INPUT_DIR=/app/data/input
ZPP_PROCESSED_DIR=/app/data/processed
ZPP_SCHEDULE_ENABLED=true
ZPP_API_PORT=5002
ZPP_BATCH_SIZE=1000

# ZPP Service URL (para webapp)
ZPP_SERVICE_URL=http://zpp-processor:5002
```

### Por Ambiente (`.env` em `environments/*/`)

```env
# Local
ZPP_INPUT_PATH=E:/Projetos Python/AMG_Data/zpp_input/input
ZPP_PROCESSED_PATH=E:/Projetos Python/AMG_Data/zpp_input/processed

# Dev
ZPP_INPUT_PATH=/mnt/data/zpp/input
ZPP_PROCESSED_PATH=/mnt/data/zpp/processed

# Prod
ZPP_INPUT_PATH=/mnt/production/zpp/input
ZPP_PROCESSED_PATH=/mnt/production/zpp/processed
```

---

## 🚨 Considerações Importantes

### Segurança
- ✅ Volume de planilhas **read-only** do ponto de vista do host
- ✅ API sem autenticação (protegida por rede interna `easytek-net`)
- ✅ Webapp valida permissões (admin level 3)

### Performance
- ✅ Upload em lotes (batch_size=1000)
- ✅ Índices otimizados criados automaticamente
- ✅ Verificação de duplicatas antes de inserir

### Escalabilidade
- ✅ Stateless (pode escalar horizontalmente se necessário)
- ✅ Volumes externos (dados persistem)
- ✅ Scheduler com `max_instances=1` previne concorrência

### Manutenção
- ✅ Logs via stdout (capturados por Docker)
- ✅ Healthcheck endpoint
- ✅ Status endpoint para monitoramento
- ✅ Supervisord reinicia processos em caso de falha

---

## 📊 Arquivos Críticos para Implementação

### 1. `E:\Projetos Python\AMG_Data\zpp_input\src\processor.py`
**Prioridade**: Alta
**Ação**: Refatorar `process_zpp_to_mongo.py` (608 linhas) para classe `ZPPProcessor`

### 2. `E:\Projetos Python\AMG_Data\zpp_input\src\api.py`
**Prioridade**: Alta
**Ação**: Criar Flask API com 4 endpoints (baseado em `event-gateway/api.py`)

### 3. `E:\Projetos Python\AMG_Data\zpp_input\src\scheduler.py`
**Prioridade**: Alta
**Ação**: Criar APScheduler com CronTrigger para 8h, 12h, 18h

### 4. `E:\Projetos Python\AMG_Data\zpp_input\Dockerfile`
**Prioridade**: Alta
**Ação**: Criar Dockerfile baseado em `python:3.11-slim` + supervisord

### 5. `E:\Projetos Python\AMG_Infra\docker-compose.yml`
**Prioridade**: Média
**Ação**: Adicionar service `zpp-processor` após webapp/event-gateway

### 6. `E:\Projetos Python\AMG_Data\webapp\src\callbacks_registers\zpp_processor_callbacks.py`
**Prioridade**: Média
**Ação**: Criar callbacks para integração manual (baseado em `sp_callback.py`)

### 7. `E:\Projetos Python\AMG_Data\webapp\src\pages\admin\zpp_processor.py`
**Prioridade**: Média
**Ação**: Criar página de administração (layout + botão processar)

---

## ✅ Resumo Executivo

**O Que Será Feito**:
- Transformar scripts Python da raiz em micro-serviço Docker
- Adicionar agendamento automático (8h, 12h, 18h)
- Criar interface de execução manual na webapp
- Organizar código em `zpp_input/src/`
- Volumes externos para planilhas (input/ e processed/)

**Tecnologias**:
- Flask + gunicorn (API REST)
- APScheduler (agendamento)
- Supervisord (gerenciamento de processos)
- Docker + docker-compose

**Estimativa Total**: 12-20 dias (2-3 sprints)

**Risco**: Baixo (padrão já estabelecido com event-gateway)

---

**Documentação a Criar**:
- `.dev-docs/modules/zpp-processor/` (técnica)
- `zpp_input/README.md` (uso)
- `.dev-docs/operations/zpp-processor-deployment.md` (deploy)

---

**Criado em**: 2026-01-29
