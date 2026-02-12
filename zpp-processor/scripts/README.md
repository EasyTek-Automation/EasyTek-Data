# Scripts de Configuração do ZPP Processor

Scripts para inicialização e validação do MongoDB.

## Scripts Disponíveis

### 1. init_mongodb.py

Inicializa o MongoDB com collections, índices e configuração padrão.

**Uso**:
```bash
cd zpp-processor
python scripts/init_mongodb.py
```

**O que faz**:
- ✅ Cria índices otimizados em `zpp_processing_logs`:
  - `idx_job_id_unique` - Único por job_id
  - `idx_started_at_desc` - Ordenação por data
  - `idx_status_started` - Filtro por status + data
  - `idx_trigger_started` - Filtro por tipo de trigger
  - `idx_triggered_by_started` - Filtro por usuário
- ✅ Cria configuração padrão em `zpp_processor_config`:
  - `auto_process: true`
  - `interval_minutes: 60`
  - `archive_enabled: true`
- ✅ Verifica que tudo foi criado corretamente

**Quando executar**:
- Primeira instalação do serviço
- Após atualização que modifica schemas
- Para recriar índices corrompidos

**Saída esperada**:
```
================================================================================
ZPP PROCESSOR - INICIALIZAÇÃO DO MONGODB
================================================================================

Conectando ao MongoDB...
  ✓ Conexão estabelecida

Criando índices para 'zpp_processing_logs'...
  ✓ Índice criado: idx_job_id_unique
  ✓ Índice criado: idx_started_at_desc
  ✓ Índice criado: idx_status_started
  ✓ Índice criado: idx_trigger_started
  ✓ Índice criado: idx_triggered_by_started
  Total: 5/5 índices criados

Verificando configuração padrão...
  ✓ Configuração padrão criada
    auto_process: True
    interval_minutes: 60

Verificando collections...
  ✓ zpp_processing_logs
  ✓ zpp_processor_config

✓ INICIALIZAÇÃO CONCLUÍDA COM SUCESSO
```

---

### 2. validate_mongodb.py

Valida se o MongoDB está configurado corretamente.

**Uso**:
```bash
cd zpp-processor
python scripts/validate_mongodb.py
```

**O que faz**:
- ✅ Testa conexão com MongoDB
- ✅ Verifica existência das collections
- ✅ Valida índices criados (propriedades UNIQUE, SPARSE)
- ✅ Valida configuração padrão (campos obrigatórios)
- ✅ Valida estrutura de documentos de log
- ✅ Mostra resumo estatístico

**Quando executar**:
- Após executar `init_mongodb.py`
- Para diagnosticar problemas
- Como parte de CI/CD
- Verificação periódica de integridade

**Saída esperada (sucesso)**:
```
================================================================================
ZPP PROCESSOR - VALIDAÇÃO DO MONGODB
================================================================================

1. Validando conexão com MongoDB...
  ✓ Conectado ao database: Cluster-EasyTek

2. Validando collections...
  ✓ zpp_processing_logs - Histórico de processamentos
      Documentos: 5
  ✓ zpp_processor_config - Configurações do serviço
      Documentos: 1

3. Validando índices de zpp_processing_logs...
  ✓ idx_job_id_unique (UNIQUE: True)
  ✓ idx_started_at_desc
  ✓ idx_status_started
  ✓ idx_trigger_started
  ✓ idx_triggered_by_started (SPARSE: True)

4. Validando configuração...
  ✓ auto_process: True
  ✓ interval_minutes: 60
  ✓ archive_enabled: True
  ✓ last_updated: 2026-02-12 10:00:00
  ✓ updated_by: system

5. Validando estrutura de logs...
  ✓ job_id: str
  ✓ status: str
  ✓ started_at: datetime
  ✓ trigger_type: str
  ✓ files_processed: list
  ✓ summary: dict
    ✓ summary.total_files: 2
    ✓ summary.total_uploaded_records: 23300

============================================================
RESUMO
============================================================
Logs de processamento:
  Total:       5
  Sucesso:     4
  Falhas:      1
  Em execução: 0

Configuração:
  Auto-process:     True
  Intervalo (min):  60
  Arquivamento:     True
  Última atualização: 2026-02-12 10:00:00

============================================================
RESULTADO DAS VALIDAÇÕES
============================================================
✓ PASS - Conexão
✓ PASS - Collections
✓ PASS - Índices
✓ PASS - Configuração
✓ PASS - Estrutura de Logs

✓ TODAS AS VALIDAÇÕES PASSARAM
```

---

## Configuração Necessária

Ambos os scripts requerem arquivo `.env` na raiz do projeto com:

```bash
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/
DB_NAME=your_database_name
```

**Localização do .env**:
- Desenvolvimento local: `zpp-processor/.env`
- Produção (Docker): Variáveis passadas via `docker-compose.yml`

---

## Collections MongoDB

### zpp_processing_logs

**Propósito**: Histórico de todos os processamentos (manual e automático)

**Documento exemplo**:
```json
{
  "_id": ObjectId("..."),
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "success",
  "started_at": ISODate("2026-02-12T10:30:00Z"),
  "completed_at": ISODate("2026-02-12T10:32:15Z"),
  "duration_seconds": 135.5,
  "trigger_type": "manual",
  "triggered_by": "admin@example.com",
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
  },
  "error_message": null
}
```

**Índices**:
- `idx_job_id_unique` - Busca rápida por job_id (UNIQUE)
- `idx_started_at_desc` - Ordenação cronológica
- `idx_status_started` - Filtro por status + data
- `idx_trigger_started` - Filtro por tipo (manual/automatic)
- `idx_triggered_by_started` - Filtro por usuário

---

### zpp_processor_config

**Propósito**: Configurações do serviço (único documento com _id='global')

**Documento**:
```json
{
  "_id": "global",
  "auto_process": true,
  "interval_minutes": 60,
  "archive_enabled": true,
  "last_updated": ISODate("2026-02-12T10:00:00Z"),
  "updated_by": "admin@user",
  "created_at": ISODate("2026-02-12T09:00:00Z")
}
```

**Campos**:
- `auto_process` (bool) - Ativar processamento automático
- `interval_minutes` (int) - Intervalo entre processamentos (1-1440)
- `archive_enabled` (bool) - Mover arquivos para output após processar
- `last_updated` (datetime) - Última modificação
- `updated_by` (string) - Quem atualizou

---

## Troubleshooting

### Erro: "MONGO_URI não configurado"
**Solução**: Criar arquivo `.env` com variáveis corretas

### Erro: "Falha na autenticação"
**Solução**: Verificar credenciais no MONGO_URI

### Erro: "Índice já existe"
**Solução**: Normal se executar `init_mongodb.py` múltiplas vezes (índices não são recriados)

### Erro: "Collection não encontrada"
**Solução**: Executar `init_mongodb.py` primeiro

### Validação falha em "Estrutura de Logs"
**Solução**: Normal se não houver logs ainda (instalação nova)

---

## Comandos Úteis (MongoDB Shell)

```javascript
// Ver configuração atual
db.zpp_processor_config.findOne({_id: 'global'})

// Listar últimos 5 logs
db.zpp_processing_logs.find().sort({started_at: -1}).limit(5)

// Contar logs por status
db.zpp_processing_logs.aggregate([
  {$group: {_id: "$status", count: {$sum: 1}}}
])

// Ver logs com erros
db.zpp_processing_logs.find({status: "failed"})

// Total de registros processados (todos os tempos)
db.zpp_processing_logs.aggregate([
  {$group: {_id: null, total: {$sum: "$summary.total_uploaded_records"}}}
])

// Listar índices
db.zpp_processing_logs.getIndexes()

// Estatísticas da collection
db.zpp_processing_logs.stats()
```

---

## Integração com CI/CD

Exemplo de uso em pipeline:

```yaml
# .github/workflows/deploy.yml
- name: Initialize MongoDB
  run: |
    cd zpp-processor
    python scripts/init_mongodb.py

- name: Validate MongoDB
  run: |
    cd zpp-processor
    python scripts/validate_mongodb.py
```

---

## Manutenção

### Limpeza de Logs Antigos

Criar índice TTL para auto-limpeza (opcional):

```javascript
// Deletar logs após 90 dias
db.zpp_processing_logs.createIndex(
  {started_at: 1},
  {expireAfterSeconds: 7776000}  // 90 dias
)
```

### Backup de Configuração

```bash
# Exportar configuração
mongoexport --uri="$MONGO_URI" --db=$DB_NAME \
  --collection=zpp_processor_config --out=config_backup.json

# Importar configuração
mongoimport --uri="$MONGO_URI" --db=$DB_NAME \
  --collection=zpp_processor_config --file=config_backup.json
```

---

## Suporte

Em caso de problemas com scripts:
1. Verificar logs de erro
2. Validar credenciais MongoDB
3. Testar conexão manualmente
4. Consultar documentação do MongoDB
