# ✅ Checklist de Validação - ZPP Processor

**Versão**: 1.0
**Data**: 2026-02-12

Use este checklist para validar que o sistema está funcionando corretamente antes de usar em produção.

---

## 📋 Pré-requisitos

### Infraestrutura

- [ ] Docker Desktop instalado e rodando
- [ ] Docker Compose versão 1.29+ ou 2.x
- [ ] Acesso ao MongoDB (credentials válidos)
- [ ] Acesso ao registry GHCR (para pull de imagens)
- [ ] Portas disponíveis: 5002 (ZPP Processor), 8050 (Webapp)

### Variáveis de Ambiente

- [ ] `.env.common` configurado em `AMG_Infra/`
- [ ] `MONGO_URI` definido e válido
- [ ] `DB_NAME` definido
- [ ] `ZPP_PROCESSOR_URL` definido (http://zpp-processor:5002)
- [ ] `ZPP_AUTO_PROCESS` definido (true/false)
- [ ] `ZPP_INTERVAL_MINUTES` definido (1-1440)

### Volumes

- [ ] Diretório `AMG_Infra/volumes/zpp/input/` existe
- [ ] Diretório `AMG_Infra/volumes/zpp/output/` existe
- [ ] Diretório `AMG_Infra/volumes/zpp/logs/` existe
- [ ] Permissões de escrita nos volumes

---

## 🐳 Validação Docker

### Build e Push

- [ ] Imagem `zpp-processor` construída com sucesso
- [ ] Imagem pushed para GHCR
- [ ] Imagem multi-arch (linux/amd64, linux/arm64)
- [ ] Tag `latest` atualizada

**Comando**:
```bash
cd AMG_Infra
./scripts/build-and-push.ps1 -tag latest
```

### Container

- [ ] Container `zpp-processor` iniciado
- [ ] Status: `running`
- [ ] Health check: `healthy`
- [ ] Logs sem erros críticos
- [ ] Porta 5002 exposta

**Comandos**:
```bash
docker ps | grep zpp-processor
docker logs zpp-processor
curl http://localhost:5002/api/health
```

---

## 🗄️ Validação MongoDB

### Collections

- [ ] Collection `zpp_processing_logs` criada
- [ ] Collection `zpp_processor_config` criada
- [ ] Documento de configuração global inserido

**Script**:
```bash
cd zpp-processor
python scripts/init_mongodb.py
```

### Índices

- [ ] `idx_job_id_unique` (UNIQUE) criado
- [ ] `idx_started_at_desc` criado
- [ ] `idx_status_started` criado
- [ ] `idx_trigger_started` criado
- [ ] `idx_triggered_by_started` (SPARSE) criado

**Validação**:
```bash
python scripts/validate_mongodb.py
```

### Dados

- [ ] Configuração padrão válida
- [ ] `auto_process` é booleano
- [ ] `interval_minutes` é inteiro (1-1440)
- [ ] `last_updated` é datetime

**MongoDB Shell**:
```javascript
db.zpp_processor_config.findOne({_id: 'global'})
```

---

## 🔌 Validação da API

### Health Check

- [ ] GET `/api/health` retorna 200
- [ ] `status: "healthy"`
- [ ] `mongodb: "connected"`
- [ ] `volumes: "ok"`

**Teste**:
```bash
curl http://localhost:5002/api/health | jq
```

### Endpoints REST

- [ ] GET `/api/zpp/config` retorna 200
- [ ] PUT `/api/zpp/config` aceita updates
- [ ] POST `/api/zpp/process` retorna 202
- [ ] GET `/api/zpp/status/<job_id>` retorna 200
- [ ] GET `/api/zpp/history` retorna 200
- [ ] GET `/api/zpp/files/input` retorna 200
- [ ] GET `/api/zpp/files/output` retorna 200

**Script**:
```bash
cd zpp-processor
python tests/test_api.py
```

### Processamento

- [ ] Job criado com `job_id` único
- [ ] Status inicial: `running`
- [ ] Polling funciona (atualização de status)
- [ ] Status final: `success` ou `failed`
- [ ] Log inserido no MongoDB
- [ ] Arquivo movido para `output/` (se sucesso)

---

## 🌐 Validação da Interface Web

### Acesso

- [ ] Rota `/maintenance/zpp-processor` acessível
- [ ] Página carrega sem erros
- [ ] Usuário nível 1 **bloqueado**
- [ ] Usuário nível 2+ (manutenção) **permitido**
- [ ] Outros perfis **bloqueados**
- [ ] Redirect para `/access-denied` quando bloqueado

### Layout

- [ ] Header com título e botões
- [ ] Card "Processar Agora" visível
- [ ] Card "Arquivos Pendentes" visível
- [ ] Card "Arquivos Processados" visível
- [ ] Painel de configurações (collapsible)
- [ ] Tabela de histórico visível

### Funcionalidades

- [ ] **Auto-load**: Dados carregam automaticamente ao entrar
- [ ] **Processar**: Botão inicia processamento
- [ ] **Polling**: Status atualiza em tempo real
- [ ] **Histórico**: Tabela atualiza após processamento
- [ ] **Configurações**: Switch e input funcionam
- [ ] **Salvar**: Configurações são salvas no MongoDB
- [ ] **Refresh**: Botão atualiza dados
- [ ] **Ajuda**: Toast exibe instruções

### Feedback Visual

- [ ] Spinner no botão durante processamento
- [ ] Badges com contadores atualizados
- [ ] Alerts de status (info/success/danger)
- [ ] Toasts de notificação aparecem
- [ ] Cores de status corretas (verde/amarelo/vermelho)

---

## 🔄 Validação de Processamento

### Processamento Manual

1. **Preparar**:
   - [ ] Colocar arquivo `.xlsx` em `volumes/zpp/input/`
   - [ ] Arquivo detectável via API

2. **Executar**:
   - [ ] Clicar em "Processar Agora"
   - [ ] Job iniciado com sucesso
   - [ ] Job ID exibido

3. **Acompanhar**:
   - [ ] Status atualiza automaticamente
   - [ ] Progresso visível em tempo real
   - [ ] Botão desabilitado durante processamento

4. **Verificar**:
   - [ ] Status final: `success`
   - [ ] Arquivo movido para `output/`
   - [ ] Dados inseridos no MongoDB
   - [ ] Histórico atualizado
   - [ ] Toast de sucesso exibido

### Processamento Automático

1. **Configurar**:
   - [ ] Ativar switch "Processamento Automático"
   - [ ] Definir intervalo (ex: 5 min para teste)
   - [ ] Salvar configuração

2. **Aguardar**:
   - [ ] Scheduler executa no intervalo definido
   - [ ] Log com `trigger_type: "automatic"` criado

3. **Verificar Logs**:
   - [ ] Scheduler logs no console do container
   - [ ] Jobs automáticos no histórico

**Comando**:
```bash
docker logs -f zpp-processor
```

---

## 🧪 Validação de Tipos de Arquivo

### ZPP PRD (Produção)

- [ ] Arquivo com colunas: `Pto.Trab.`, `Kg.Proc.`, `HorasAct.`, `FIniNotif`, `FFinNotif`
- [ ] Tipo detectado automaticamente: `zppprd`
- [ ] Collection destino: `ZPP_Producao_YYYY`
- [ ] Linhas totalizadoras removidas
- [ ] Equipamentos EMBAL* filtrados
- [ ] Índices criados

### ZPP Paradas

- [ ] Arquivo com colunas: `Centro de trabalho`, `Início execução`, `Fim execução`, `Causa do desvio`, `Duration (min)`
- [ ] Tipo detectado automaticamente: `zppparadas`
- [ ] Collection destino: `ZPP_Paradas_YYYY`
- [ ] Linhas totalizadoras removidas
- [ ] Equipamentos EMBAL* filtrados
- [ ] Índices criados

### Arquivos Inválidos

- [ ] Arquivo sem colunas reconhecidas → status `failed`
- [ ] Arquivo corrompido → status `failed`
- [ ] Erro registrado no log
- [ ] Mensagem de erro clara

---

## 🔐 Validação de Permissões

### Nível de Acesso

| Perfil | Nível 1 | Nível 2 | Nível 3 |
|--------|---------|---------|---------|
| **Manutenção** | ❌ Bloqueado | ✅ Acesso | ✅ Acesso |
| **Qualidade** | ❌ Bloqueado | ❌ Bloqueado | ❌ Bloqueado |
| **Produção** | ❌ Bloqueado | ❌ Bloqueado | ❌ Bloqueado |
| **Admin** | ❌ Bloqueado | ✅ Acesso | ✅ Acesso |

### Testes de Permissão

- [ ] Usuário nível 1 (manutenção) → **Bloqueado**
- [ ] Usuário nível 2 (manutenção) → **Permitido**
- [ ] Usuário nível 3 (admin) → **Permitido**
- [ ] Usuário qualidade → **Bloqueado**
- [ ] Mensagem de erro clara quando bloqueado

---

## 📊 Validação de Dados

### Após Processamento Bem-Sucedido

**Produção (ZPP_Producao_YYYY)**:
- [ ] Registros inseridos com `_processed: true`
- [ ] Colunas normalizadas (minúsculas, sem acentos)
- [ ] Datas como `datetime` Python
- [ ] Metadados presentes: `_uploaded_at`, `_source_file`, `_year`
- [ ] Sem registros de EMBAL*

**Paradas (ZPP_Paradas_YYYY)**:
- [ ] Registros inseridos com `_processed: true`
- [ ] Colunas normalizadas
- [ ] Datas como `datetime` Python
- [ ] Metadados presentes
- [ ] Sem registros de EMBAL*

### Log de Processamento

- [ ] `job_id` único gerado
- [ ] `status` correto (running/success/failed)
- [ ] `started_at` e `completed_at` presentes
- [ ] `duration_seconds` calculado
- [ ] `trigger_type` correto (manual/automatic)
- [ ] `files_processed` array populado
- [ ] `summary` com totais corretos

---

## 🔍 Troubleshooting

### Problemas Comuns

#### Container não inicia

- [ ] Verificar logs: `docker logs zpp-processor`
- [ ] Verificar variáveis de ambiente
- [ ] Verificar conectividade MongoDB
- [ ] Verificar permissões nos volumes

#### API não responde

- [ ] Health check: `curl http://localhost:5002/api/health`
- [ ] Verificar porta 5002 disponível
- [ ] Verificar firewall
- [ ] Verificar logs do container

#### Processamento falha

- [ ] Verificar estrutura do arquivo
- [ ] Verificar tipo detectado (zppprd/zppparadas)
- [ ] Verificar logs de erro no MongoDB
- [ ] Verificar permissões de escrita em volumes

#### Interface não carrega

- [ ] Verificar usuário tem permissão (nível 2+, perfil manutenção)
- [ ] Verificar variável `ZPP_PROCESSOR_URL` em `.env.common`
- [ ] Verificar conectividade webapp → zpp-processor
- [ ] Verificar logs do navegador (console F12)

---

## ✅ Critérios de Aprovação

Para considerar o sistema **pronto para produção**, todos os itens abaixo devem estar ✅:

### Mínimos Obrigatórios

- [ ] **Serviço**: Container rodando e saudável
- [ ] **MongoDB**: Collections e índices criados
- [ ] **API**: Todos os 8 endpoints funcionando
- [ ] **Interface**: Página carrega sem erros
- [ ] **Permissões**: Controle de acesso funcionando
- [ ] **Processamento**: Fluxo completo funcional
- [ ] **Histórico**: Logs persistidos corretamente

### Recomendados

- [ ] **Testes automatizados**: Scripts passam sem erros
- [ ] **Documentação**: README.md atualizado
- [ ] **Migração**: Scripts antigos deprecados
- [ ] **Backup**: Configuração MongoDB backup realizado
- [ ] **Monitoramento**: Logs sendo coletados

### Opcionais (Melhorias Futuras)

- [ ] Notificações push quando processamento completa
- [ ] Upload de arquivos via drag & drop
- [ ] Download de logs detalhados por job
- [ ] Gráficos de estatísticas de processamento
- [ ] Retry automático em caso de falha parcial

---

## 📝 Registro de Validação

**Validado por**: ___________________________
**Data**: ___/___/______
**Versão**: ___________________________
**Aprovado para produção**: ☐ Sim ☐ Não

**Observações**:
```
_____________________________________________________________
_____________________________________________________________
_____________________________________________________________
```

---

**Próximos Passos**:
1. Executar scripts de teste
2. Preencher checklist
3. Documentar problemas encontrados
4. Corrigir e re-validar
5. Aprovar para produção
