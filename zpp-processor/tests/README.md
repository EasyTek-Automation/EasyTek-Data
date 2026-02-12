# 🧪 Testes do ZPP Processor

Scripts de teste e validação para o serviço ZPP Processor.

---

## 📋 Scripts Disponíveis

### 1. test_api.py

**Propósito**: Testa todos os 8 endpoints REST da API

**Uso**:
```bash
cd zpp-processor
python tests/test_api.py
```

**O que testa**:
- ✅ Health check
- ✅ Obter configuração (GET)
- ✅ Atualizar configuração (PUT)
- ✅ Listar arquivos de input
- ✅ Listar arquivos de output
- ✅ Obter histórico
- ✅ Processar arquivos (POST) *se houver arquivos*
- ✅ Consultar status de job

**Saída esperada**:
```
================================================================================
ZPP PROCESSOR - TESTE DA API
================================================================================

URL Base: http://localhost:5002
Timestamp: 2026-02-12 10:30:00

================================================================================
TESTE 1: Health Check
================================================================================

✓ PASS - Health Check
       Status: healthy, MongoDB: connected

[... mais testes ...]

================================================================================
RESUMO DOS TESTES
================================================================================

✓ health
✓ get_config
✓ update_config
✓ list_input
✓ list_output
✓ history
✓ process
✓ job_status

Total: 8/8 testes passaram

✓ TODOS OS TESTES PASSARAM
```

---

### 2. validate_e2e.py

**Propósito**: Validação end-to-end (API + MongoDB + Volumes)

**Uso**:
```bash
cd zpp-processor
python tests/validate_e2e.py
```

**O que valida**:
- ✅ Conexão MongoDB
- ✅ Collections MongoDB criadas
- ✅ Índices MongoDB configurados
- ✅ API health check
- ✅ Todos os endpoints da API
- ✅ Configuração do serviço
- ✅ Logs de processamento

**Saída esperada**:
```
================================================================================
ZPP PROCESSOR - VALIDAÇÃO END-TO-END
================================================================================

Timestamp: 2026-02-12 10:30:00
API URL: http://localhost:5002
MongoDB: Cluster-EasyTek

[... validações ...]

================================================================================
RESUMO DAS VALIDAÇÕES
================================================================================

✓ Conexão MongoDB
✓ Collections MongoDB
✓ Índices MongoDB
✓ API Health
✓ Endpoints da API
✓ Configuração do Serviço
✓ Logs de Processamento

Total: 7/7 validações passaram

✓ TODAS AS VALIDAÇÕES PASSARAM

O sistema está funcionando corretamente!
```

---

### 3. VALIDATION_CHECKLIST.md

**Propósito**: Checklist manual completo para validação pré-produção

**Uso**: Abrir arquivo e marcar itens conforme validação

**Seções**:
- 📋 Pré-requisitos
- 🐳 Validação Docker
- 🗄️ Validação MongoDB
- 🔌 Validação da API
- 🌐 Validação da Interface Web
- 🔄 Validação de Processamento
- 🧪 Validação de Tipos de Arquivo
- 🔐 Validação de Permissões
- 📊 Validação de Dados
- ✅ Critérios de Aprovação

---

## 🚀 Execução Rápida

### Teste Completo (Todos os Scripts)

```bash
# 1. Validar MongoDB
cd zpp-processor
python scripts/validate_mongodb.py

# 2. Testar API
python tests/test_api.py

# 3. Validação End-to-End
python tests/validate_e2e.py

# 4. Checklist manual
# Abrir VALIDATION_CHECKLIST.md e preencher
```

### Teste Rápido (Apenas API)

```bash
cd zpp-processor
python tests/test_api.py
```

---

## 📦 Pré-requisitos

### Para Executar Testes

**Dependências Python**:
```bash
pip install requests pymongo python-dotenv
```

**Serviços Rodando**:
- MongoDB conectado
- Container `zpp-processor` rodando
- API acessível em `http://localhost:5002`

**Variáveis de Ambiente**:
Arquivo `.env` na raiz do projeto com:
```bash
MONGO_URI=mongodb+srv://...
DB_NAME=your_database
```

---

## 🧪 Cenários de Teste

### Cenário 1: Instalação Nova

**Passos**:
1. Subir containers: `docker-compose up -d`
2. Inicializar MongoDB: `python scripts/init_mongodb.py`
3. Validar MongoDB: `python scripts/validate_mongodb.py`
4. Testar API: `python tests/test_api.py`
5. Validar E2E: `python tests/validate_e2e.py`

**Resultado Esperado**: Todos os testes passam

---

### Cenário 2: Após Atualização

**Passos**:
1. Rebuild containers: `docker-compose up -d --build`
2. Validar MongoDB: `python scripts/validate_mongodb.py`
3. Testar API: `python tests/test_api.py`

**Resultado Esperado**: Nenhuma regressão

---

### Cenário 3: Processamento Real

**Passos**:
1. Colocar arquivo `.xlsx` em `volumes/zpp/input/`
2. Executar: `python tests/test_api.py`
3. Verificar: Teste de processamento executa e passa

**Resultado Esperado**:
- Job criado
- Arquivo processado
- Dados no MongoDB
- Arquivo movido para `output/`

---

## 🐛 Troubleshooting

### Erro: "Connection refused"

**Causa**: Serviço não está rodando

**Solução**:
```bash
docker ps | grep zpp-processor
docker logs zpp-processor
docker-compose up -d zpp-processor
```

---

### Erro: "MONGO_URI não configurado"

**Causa**: Arquivo `.env` não encontrado

**Solução**:
```bash
cd zpp-processor
cp .env.example .env
# Editar .env com credenciais corretas
```

---

### Testes Falham: "Timeout"

**Causa**: Processamento muito lento ou MongoDB offline

**Solução**:
- Verificar health do MongoDB
- Verificar tamanho dos arquivos
- Aumentar timeout nos scripts (se necessário)

---

## 📊 Interpretação de Resultados

### ✓ PASS - Teste Passou

**Ação**: Nenhuma ação necessária

---

### ✗ FAIL - Teste Falhou

**Ação**:
1. Ler detalhes do erro
2. Verificar logs: `docker logs zpp-processor`
3. Verificar MongoDB
4. Corrigir problema
5. Re-executar teste

---

### ⚠ SKIP - Teste Pulado

**Causa**: Condições não atendidas (ex: sem arquivos para processar)

**Ação**: Normal se esperado, investigar se não esperado

---

## 🔄 Integração CI/CD

### GitHub Actions (Exemplo)

```yaml
# .github/workflows/test-zpp-processor.yml
name: Test ZPP Processor

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      mongodb:
        image: mongo:6
        ports:
          - 27017:27017

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd zpp-processor
          pip install -r requirements.txt
          pip install requests

      - name: Start service
        run: |
          cd zpp-processor
          python api.py &
          sleep 5

      - name: Run tests
        run: |
          cd zpp-processor
          python tests/test_api.py
```

---

## 📝 Relatório de Testes

### Template de Relatório

```markdown
# Relatório de Testes - ZPP Processor

**Data**: 2026-02-12
**Versão**: 1.0
**Testado por**: Nome

## Resumo

- Total de testes: 15
- Passaram: 15
- Falharam: 0
- Pulados: 0

## Detalhes

### test_api.py
✓ Todos os 8 testes passaram

### validate_e2e.py
✓ Todas as 7 validações passaram

### Checklist Manual
✓ 45/45 itens validados

## Observações

Nenhum problema encontrado.

## Aprovação

☑ Aprovado para produção
```

---

## 📚 Referências

- **API Documentation**: `../README.md`
- **MongoDB Setup**: `../scripts/README.md`
- **Deployment Guide**: `../../AMG_Infra/docker-compose.yml`
- **User Guide**: Interface web `/maintenance/zpp-processor`

---

## 🆘 Suporte

**Problemas com testes?**

1. Verificar pré-requisitos
2. Consultar logs: `docker logs zpp-processor`
3. Verificar MongoDB: `python scripts/validate_mongodb.py`
4. Verificar API: `curl http://localhost:5002/api/health`
5. Abrir issue no repositório

---

**Última atualização**: 2026-02-12
**Versão**: 1.0
