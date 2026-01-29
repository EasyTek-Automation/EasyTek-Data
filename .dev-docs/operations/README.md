# ⚙️ Operações e Infraestrutura

Documentação de infraestrutura, DevOps, configuração de serviços e manutenção operacional.

---

## 📋 Conteúdo

*(Arquivos a serem movidos aqui)*

- `node-red-persistence.md` ← **MOVER** `docs/NODE-RED-PERSISTENCE.md`

---

## 📝 O que Colocar Aqui

### ✅ Incluir

- **Configuração de Serviços**
  - MongoDB, nginx, Node-RED
  - Configurações de produção

- **DevOps e Deploy**
  - Processos de deploy
  - CI/CD pipelines
  - Scripts de automação

- **Infraestrutura**
  - Docker/Docker Compose
  - Volumes e persistência
  - Redes e comunicação

- **Manutenção**
  - Backup e recuperação
  - Monitoramento e logs
  - Troubleshooting de serviços

### ❌ Não Incluir

- Arquitetura da aplicação → `architecture/`
- Guias de desenvolvimento → `guides/`
- Procedimentos de manutenção industrial → `docs/procedures/` (feature da app)

---

## 📚 Template para Novos Documentos

```markdown
# [Nome do Serviço/Sistema] - Configuração

## 🎯 Objetivo
O que este serviço faz.

## ⚙️ Configuração

### Variáveis de Ambiente
| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `VAR_1` | ... | ... |

### Volumes
- `/path/to/volume` - Propósito

### Portas
- `8080` - HTTP
- `27017` - MongoDB

## 🚀 Deploy

### Desenvolvimento
\`\`\`bash
docker-compose up service-name
\`\`\`

### Produção
\`\`\`bash
# Comandos específicos
\`\`\`

## 🔧 Manutenção

### Backup
Como fazer backup dos dados.

### Logs
Como acessar e analisar logs.

### Troubleshooting
Problemas comuns e soluções.

## 📚 Referências
Links para documentação oficial, etc.
```

---

**Criado em**: 2026-01-28
