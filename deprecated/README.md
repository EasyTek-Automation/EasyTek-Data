# ⚠️ Scripts ZPP Descontinuados

**Status**: DEPRECATED - Não usar em produção

Estes scripts foram **migrados para o serviço containerizado `zpp-processor`** e não devem mais ser usados diretamente.

---

## 📦 Migração Realizada

**Data**: 2026-02-12
**Versão**: v3.0 → v4.0 (serviço containerizado)

### Scripts Descontinuados

| Script Antigo | Novo Equivalente | Status |
|---------------|------------------|--------|
| `process_zpp_quick.py` | Interface web `/maintenance/zpp-processor` | ✅ Migrado |
| `process_zpp_to_mongo.py` | `zpp-processor/processor.py` | ✅ Migrado |
| `clean_zpp_data.py` | `zpp-processor/cleaner.py` | ✅ Migrado |

---

## 🚀 Como Usar o Novo Sistema

### Processamento Manual

**Antes (script descontinuado)**:
```bash
# ❌ NÃO USAR MAIS
cd AMG_Data
python process_zpp_to_mongo.py zpp_input/
```

**Agora (interface web)**:
```
1. Acessar: http://localhost:8050/maintenance/zpp-processor
2. Colocar arquivos .xlsx em: AMG_Infra/volumes/zpp/input/
3. Clicar em "Processar Agora"
4. Acompanhar progresso em tempo real
5. Arquivos processados movidos para: volumes/zpp/output/
```

### Processamento Automático

**Configuração**:
```bash
# Em AMG_Infra/.env.common
ZPP_AUTO_PROCESS=true
ZPP_INTERVAL_MINUTES=60  # Processar a cada 60 minutos
```

**Interface web**:
```
1. Acessar: /maintenance/zpp-processor
2. Abrir painel "Configurações"
3. Ativar switch "Processamento Automático"
4. Definir intervalo (minutos)
5. Salvar
```

---

## 🔄 Tabela de Equivalências

### Funcionalidades Migradas

| Funcionalidade | Script Antigo | Serviço Novo |
|----------------|---------------|--------------|
| **Detecção de tipo** | `detect_file_type()` | `cleaner.py::detect_file_type()` |
| **Limpeza de dados** | `ZPPCleaner` | `cleaner.py::ZPPCleaner` |
| **Upload MongoDB** | `ZPPProcessor.process_file()` | `processor.py::ZPPProcessor.process_file()` |
| **Arquivamento** | Subdiretório `analisados/` | Volume externo `output/` |
| **Logging** | Console (stdout) | MongoDB `zpp_processing_logs` |
| **Agendamento** | Cron manual | Scheduler automático |

### Parâmetros de Linha de Comando → Configuração Web

| Parâmetro CLI (antigo) | Configuração Web (novo) |
|------------------------|-------------------------|
| `--no-archive` | Config: `archive_enabled` |
| Diretório como argumento | Volume: `/data/input` |
| Sem agendamento | Config: `auto_process` + `interval_minutes` |

---

## 📊 Comparação de Funcionalidades

### Melhorias no Novo Sistema

| Feature | Script Antigo | Serviço Novo | Melhoria |
|---------|---------------|--------------|----------|
| **Interface** | CLI apenas | Web + API REST | ✅ UX moderna |
| **Monitoramento** | Logs em console | Dashboard web + histórico | ✅ Visibilidade |
| **Agendamento** | Cron manual | Automático configurável | ✅ Conveniência |
| **Status** | Sem feedback em tempo real | Polling de status | ✅ Transparência |
| **Arquivamento** | Local (pasta do código) | Volume externo | ✅ Separação dados/código |
| **Histórico** | Apenas logs de texto | MongoDB + interface web | ✅ Rastreabilidade |
| **Multi-usuário** | Não suportado | Jobs simultâneos | ✅ Escalabilidade |
| **Permissões** | Sem controle | Nível 2+ / Perfil Manutenção | ✅ Segurança |
| **Deploy** | Código Python local | Container Docker | ✅ Portabilidade |

---

## 🏗️ Arquitetura Antiga vs Nova

### Arquitetura Antiga (Descontinuada)

```
┌─────────────────────────────────────┐
│  Script Python (local)              │
│  ├─ process_zpp_to_mongo.py         │
│  ├─ clean_zpp_data.py               │
│  └─ process_zpp_quick.py            │
└────────────┬────────────────────────┘
             │
    ┌────────┴────────┐
    │                 │
    ▼                 ▼
┌─────────┐      ┌──────────┐
│ MongoDB │      │ zpp_input│
│         │      │ (código) │
└─────────┘      └──────────┘

❌ Problemas:
- Planilhas embutidas no código
- Sem interface web
- Sem agendamento automático
- Sem histórico persistente
- Deploy manual
```

### Arquitetura Nova (Atual)

```
┌─────────────────────────────────────────┐
│  WEBAPP (Interface Web)                 │
│  └─ /maintenance/zpp-processor          │
└────────────┬────────────────────────────┘
             │ HTTP/REST
             ▼
┌─────────────────────────────────────────┐
│  ZPP-PROCESSOR (Container)              │
│  ├─ API REST (8 endpoints)              │
│  ├─ Processor (lógica migrada)          │
│  ├─ Cleaner (lógica migrada)            │
│  └─ Scheduler (novo)                    │
└────────────┬────────────────────────────┘
             │
    ┌────────┴────────┐
    │                 │
    ▼                 ▼
┌─────────┐      ┌──────────┐
│ MongoDB │      │ Volumes  │
│ - Logs  │      │ /input   │
│ - Config│      │ /output  │
└─────────┘      └──────────┘

✅ Benefícios:
- Separação dados/código
- Interface moderna
- Agendamento automático
- Histórico rastreável
- Deploy via Docker
```

---

## 🔧 Manutenção dos Scripts Antigos

### Por Que Manter na Pasta `deprecated/`?

1. **Referência histórica**: Documentação do código legado
2. **Análise comparativa**: Verificar lógica original se necessário
3. **Debugging**: Comparar resultados em caso de discrepâncias
4. **Rollback temporário**: Uso emergencial (não recomendado)

### ⚠️ Avisos Importantes

- ✋ **NÃO USAR** estes scripts em produção
- ✋ **NÃO CRIAR** novos workflows baseados neles
- ✋ **NÃO MODIFICAR** (código congelado)
- ✋ **NÃO ADICIONAR** ao PATH ou automation

### Quando Usar (Excepcional)

**Situações válidas**:
- 🔍 **Debugging**: Comparar output com serviço novo
- 📚 **Referência**: Consultar lógica original
- 🧪 **Testes**: Validar migração

**Nunca usar para**:
- ❌ Processamento em produção
- ❌ Integração com outros sistemas
- ❌ Agendamento via cron

---

## 📋 Checklist de Migração

### Para Usuários Finais

- [ ] Remover cron jobs dos scripts antigos
- [ ] Atualizar documentação interna
- [ ] Treinar usuários na interface web
- [ ] Mover planilhas de `zpp_input/` para `volumes/zpp/input/`
- [ ] Configurar processamento automático

### Para Desenvolvedores

- [ ] Remover imports dos scripts descontinuados
- [ ] Atualizar testes que referenciam scripts antigos
- [ ] Verificar dependências (nenhuma outra parte do código deve usar)
- [ ] Atualizar CI/CD pipelines
- [ ] Atualizar CLAUDE.md com informações do serviço novo

### Para DevOps

- [ ] Subir serviço `zpp-processor` em produção
- [ ] Configurar volumes externos
- [ ] Validar health checks
- [ ] Monitorar logs iniciais
- [ ] Backup de configuração MongoDB

---

## 🐛 Troubleshooting

### Script Antigo Ainda em Uso?

**Identificar usos**:
```bash
# Buscar referências no código
cd AMG_Data
grep -r "process_zpp" --exclude-dir=deprecated
grep -r "clean_zpp" --exclude-dir=deprecated

# Buscar cron jobs
crontab -l | grep zpp
```

**Substituir por**:
- CLI → Interface web `/maintenance/zpp-processor`
- Automation → Configurar processamento automático
- Scripts → API REST do serviço

### Precisa Reverter Temporariamente?

**Somente em emergência**:
```bash
cd AMG_Data/deprecated

# Instalar dependências (se necessário)
pip install -r ../requirements.txt

# Executar (NÃO RECOMENDADO)
python process_zpp_to_mongo.py ../volumes/zpp/input/

# Reportar problema e migrar de volta ASAP
```

---

## 📞 Suporte

**Problemas com migração?**

1. Verificar documentação: `zpp-processor/README.md`
2. Consultar logs: `docker logs zpp-processor`
3. Testar API: `curl http://localhost:5002/api/health`
4. Ver histórico web: `/maintenance/zpp-processor`

**Contato**: Equipe de TI / Manutenção

---

## 🗑️ Cronograma de Remoção

| Data | Ação |
|------|------|
| **2026-02-12** | Scripts movidos para `deprecated/` |
| **2026-03-12** | Aviso de descontinuação (30 dias) |
| **2026-04-12** | Remoção final da pasta `deprecated/` |

**Prazo para migração**: 60 dias

---

## 📚 Documentação Relacionada

- **Serviço novo**: `zpp-processor/README.md`
- **Scripts de setup**: `zpp-processor/scripts/README.md`
- **Infraestrutura**: `AMG_Infra/docker-compose.yml`
- **Interface web**: `/maintenance/zpp-processor`
- **Configuração**: `AMG_Infra/.env.common`

---

**Última atualização**: 2026-02-12
**Versão do documento**: 1.0
