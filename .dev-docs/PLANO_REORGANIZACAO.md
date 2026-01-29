# 📋 Plano de Reorganização Completa - Arquivos .md

Análise e plano de ação para organizar **todos** os arquivos `.md` do projeto.

---

## 📊 Situação Atual (27 arquivos .md encontrados)

### Por Tamanho (Top 10)

| Arquivo | Linhas | Status |
|---------|--------|--------|
| `PLANO_TRIAGEM_AUTOMATICA.md` | 2.120 | ⚠️ MOVER |
| `.claude/skills/git-workflow/SKILL.md` | 1.836 | ✅ OK (config) |
| `docs/NODE-RED-PERSISTENCE.md` | 756 | ⚠️ MOVER |
| `.dev-docs/technical-debt/zpp-processing-improvements.md` | 632 | ✅ OK (novo) |
| `CLAUDE-PTBR.md` | 553 | ⚠️ MOVER |
| `CLAUDE.md` | 553 | ⚠️ MOVER |
| `README_PROCESS_ZPP.md` | 504 | ⚠️ MOVER |
| `webapp/DEMO_BADGES_GUIDE.md` | 353 | ⚠️ MOVER |
| `REFATORACAO_ARQUIVOS.md` | 310 | ⚠️ MOVER |
| `webapp/DEMO_BADGES_README.md` | 148 | ⚠️ MOVER |

---

## 🎯 Categorização Final

### ✅ **MANTER ONDE ESTÁ** (11 arquivos)

#### 1. Skills do Claude Code (6 arquivos)
```
.claude/skills/
├── commit-changes/SKILL.md       # Config de skill
├── energy-cost/SKILL.md          # Config de skill
├── git-workflow/SKILL.md         # Config de skill (1.836 linhas!)
├── new-page/SKILL.md             # Config de skill
├── setup-dev/SKILL.md            # Config de skill
└── test-api/SKILL.md             # Config de skill
```
**Motivo**: Configuração do CLI Claude Code, não é documentação do projeto.

#### 2. Procedimentos Operacionais (7 arquivos + index)
```
docs/procedures/
├── index.md                                      # Índice de procedimentos
├── AMG/IHM/Rockwell/comunicacaoIHM_Rockwell.md  # 428 linhas
├── AMG/LCT08/Calibracao/FolgaFaca.md            # 154 linhas
├── AMG/LCT08/Calibracao/FolgaFaca02.md          # 154 linhas
├── AMG/LCT16/Calibracao/TrocaMotor.md           # 121 linhas
├── AMG/Prensa_01/IHM/backup_proSave.md          # 95 linhas
└── AMG/Revisoes/LCT08/LCT08_Rev001.md           # 585 linhas
```
**Motivo**: **Feature da aplicação** - procedimentos renderizados dinamicamente na webapp.

#### 3. Estrutura Nova (7 arquivos)
```
.dev-docs/
├── README.md
├── ORGANIZACAO.md
├── architecture/README.md
├── guides/README.md
├── plans/README.md
├── technical-debt/README.md
└── technical-debt/zpp-processing-improvements.md
```
**Motivo**: Estrutura que acabamos de criar.

---

### ⚠️ **MOVER PARA .dev-docs** (9 arquivos)

#### A. Para `architecture/` (2 arquivos)

```bash
CLAUDE.md                   (553 linhas)
→ .dev-docs/architecture/webapp-architecture.md

CLAUDE-PTBR.md              (553 linhas)
→ .dev-docs/architecture/webapp-architecture-ptbr.md
```

#### B. Para `technical-debt/` (1 arquivo)

```bash
REFATORACAO_ARQUIVOS.md     (310 linhas)
→ .dev-docs/technical-debt/refatoracao-arquivos.md
```

#### C. Para `guides/` (1 arquivo)

```bash
README_PROCESS_ZPP.md       (504 linhas)
→ .dev-docs/guides/zpp-processing.md
```

#### D. Para `plans/` (1 arquivo)

```bash
PLANO_TRIAGEM_AUTOMATICA.md (2.120 linhas!)
→ .dev-docs/plans/triagem-automatica.md
```

#### E. Para `operations/` (1 arquivo - NOVA CATEGORIA)

```bash
docs/NODE-RED-PERSISTENCE.md (756 linhas)
→ .dev-docs/operations/node-red-persistence.md
```

#### F. Para `modules/webapp/` (2 arquivos - NOVA CATEGORIA)

```bash
webapp/DEMO_BADGES_GUIDE.md  (353 linhas)
→ .dev-docs/modules/webapp/demo-badges-guide.md

webapp/DEMO_BADGES_README.md (148 linhas)
→ .dev-docs/modules/webapp/demo-badges-overview.md
```

---

## 🏗️ Estrutura Final Proposta

```
.dev-docs/
├── README.md                              # Índice central
├── ORGANIZACAO.md                         # Guia de organização (manter)
├── PLANO_REORGANIZACAO.md                 # 👈 Este arquivo
│
├── architecture/                          # 🏗️ Arquitetura
│   ├── README.md
│   ├── webapp-architecture.md             # ← CLAUDE.md
│   └── webapp-architecture-ptbr.md        # ← CLAUDE-PTBR.md
│
├── technical-debt/                        # ⚠️ Dívidas técnicas
│   ├── README.md
│   ├── zpp-processing-improvements.md     # ✅ Já criado
│   └── refatoracao-arquivos.md            # ← REFATORACAO_ARQUIVOS.md
│
├── guides/                                # 📖 Guias
│   ├── README.md
│   └── zpp-processing.md                  # ← README_PROCESS_ZPP.md
│
├── plans/                                 # 🗺️ Planos
│   ├── README.md
│   └── triagem-automatica.md              # ← PLANO_TRIAGEM_AUTOMATICA.md
│
├── operations/                            # ⚙️ Operações e Infra (NOVO)
│   ├── README.md                          # A CRIAR
│   └── node-red-persistence.md            # ← docs/NODE-RED-PERSISTENCE.md
│
└── modules/                               # 📦 Docs de módulos específicos (NOVO)
    ├── README.md                          # A CRIAR
    └── webapp/
        ├── README.md                      # A CRIAR
        ├── demo-badges-overview.md        # ← webapp/DEMO_BADGES_README.md
        └── demo-badges-guide.md           # ← webapp/DEMO_BADGES_GUIDE.md
```

---

## 📝 Novas Categorias a Criar

### 1. `operations/` - Operações e Infraestrutura

**Propósito**: Documentação de infraestrutura, DevOps, deploy, configuração de serviços.

**Conteúdo típico**:
- Configuração de serviços (Node-RED, MongoDB, nginx)
- Processos de deploy
- Backup e recuperação
- Monitoramento
- Docker/Docker Compose

### 2. `modules/` - Documentação de Módulos

**Propósito**: Docs específicas de módulos/componentes do projeto.

**Estrutura**:
```
modules/
├── webapp/           # Docs do módulo webapp
├── event-gateway/    # Docs do event-gateway (futuro)
└── scripts/          # Docs de scripts (futuro)
```

---

## 🚀 Comandos para Executar

### Passo 1: Criar Novas Categorias

```powershell
# Criar diretórios
New-Item -ItemType Directory -Force -Path .dev-docs\operations
New-Item -ItemType Directory -Force -Path .dev-docs\modules\webapp

# Criar READMEs
# (Ver seção "Templates" abaixo)
```

### Passo 2: Mover Arquivos

```powershell
# Architecture
Move-Item -Path CLAUDE.md -Destination .dev-docs\architecture\webapp-architecture.md
Move-Item -Path CLAUDE-PTBR.md -Destination .dev-docs\architecture\webapp-architecture-ptbr.md

# Technical Debt
Move-Item -Path REFATORACAO_ARQUIVOS.md -Destination .dev-docs\technical-debt\refatoracao-arquivos.md

# Guides
Move-Item -Path README_PROCESS_ZPP.md -Destination .dev-docs\guides\zpp-processing.md

# Plans
Move-Item -Path PLANO_TRIAGEM_AUTOMATICA.md -Destination .dev-docs\plans\triagem-automatica.md

# Operations (NOVO)
Move-Item -Path docs\NODE-RED-PERSISTENCE.md -Destination .dev-docs\operations\node-red-persistence.md

# Modules (NOVO)
Move-Item -Path webapp\DEMO_BADGES_README.md -Destination .dev-docs\modules\webapp\demo-badges-overview.md
Move-Item -Path webapp\DEMO_BADGES_GUIDE.md -Destination .dev-docs\modules\webapp\demo-badges-guide.md
```

### Passo 3: Atualizar README Central

Atualizar `.dev-docs/README.md` para incluir novas seções.

### Passo 4: Commit

```bash
git add .dev-docs/
git add -u  # Remove arquivos movidos
git commit -m "docs: reorganizar toda documentação em .dev-docs"
```

---

## 📚 Templates para Novos READMEs

### `.dev-docs/operations/README.md`

```markdown
# ⚙️ Operações e Infraestrutura

Documentação de infraestrutura, DevOps e configuração de serviços.

## 📋 Conteúdo

- **[node-red-persistence.md](./node-red-persistence.md)** - Persistência do Node-RED

## 📝 O que Colocar Aqui

### ✅ Incluir
- Configuração de serviços (MongoDB, nginx, Node-RED, etc.)
- Processos de deploy e CI/CD
- Backup e recuperação de dados
- Monitoramento e logs
- Docker/Docker Compose
- Scripts de manutenção

### ❌ Não Incluir
- Arquitetura da aplicação (vai em `architecture/`)
- Guias de desenvolvimento (vão em `guides/`)
```

### `.dev-docs/modules/README.md`

```markdown
# 📦 Módulos do Projeto

Documentação específica de cada módulo/componente.

## 📂 Estrutura

- **[webapp/](./webapp/)** - Aplicação Dash principal
- *(outros módulos no futuro)*

## 📝 O que Colocar Aqui

### ✅ Incluir
- Documentação específica de um módulo
- APIs internas do módulo
- Componentes e suas props
- Configurações específicas
- HOWTOs do módulo

### ❌ Não Incluir
- Arquitetura geral (vai em `architecture/`)
- Guias que atravessam módulos (vão em `guides/`)
```

### `.dev-docs/modules/webapp/README.md`

```markdown
# 🌐 Webapp - Aplicação Dash

Documentação específica do módulo webapp (aplicação Dash principal).

## 📋 Conteúdo

- **[demo-badges-overview.md](./demo-badges-overview.md)** - Visão geral do sistema de badges
- **[demo-badges-guide.md](./demo-badges-guide.md)** - Guia de uso de badges demo

## 📝 Tópicos

- Sistema de permissões
- Componentes reutilizáveis
- Callbacks e stores
- Sistema de badges demo
- Temas e estilos
```

---

## 🎯 Benefícios da Reorganização

### Antes (Situação Atual)

```
AMG_Data/
├── CLAUDE.md                          # ❌ Raiz bagunçada
├── CLAUDE-PTBR.md                     # ❌ Raiz bagunçada
├── PLANO_TRIAGEM_AUTOMATICA.md        # ❌ Raiz bagunçada
├── README_PROCESS_ZPP.md              # ❌ Raiz bagunçada
├── REFATORACAO_ARQUIVOS.md            # ❌ Raiz bagunçada
├── docs/
│   └── NODE-RED-PERSISTENCE.md        # ❌ Misturado com procedures
└── webapp/
    ├── DEMO_BADGES_GUIDE.md           # ❌ Isolado no módulo
    └── DEMO_BADGES_README.md          # ❌ Isolado no módulo
```

### Depois (Estrutura Organizada)

```
AMG_Data/
├── .dev-docs/                         # ✅ Tudo centralizado
│   ├── architecture/
│   ├── technical-debt/
│   ├── guides/
│   ├── plans/
│   ├── operations/                    # ✅ NOVO
│   └── modules/                       # ✅ NOVO
│       └── webapp/
├── docs/                              # ✅ Apenas procedures (feature)
│   └── procedures/
└── webapp/                            # ✅ Apenas código
```

---

## ✅ Checklist de Execução

- [ ] Criar `.dev-docs/operations/`
- [ ] Criar `.dev-docs/modules/webapp/`
- [ ] Criar READMEs das novas categorias
- [ ] Mover arquivos (9 arquivos)
- [ ] Atualizar `.dev-docs/README.md`
- [ ] Testar links (se houver)
- [ ] Commit e push

---

## 📊 Resumo Final

| Categoria | Total Arquivos | Ação |
|-----------|----------------|------|
| **Skills (.claude/)** | 6 | ✅ Manter |
| **Procedures (docs/)** | 8 | ✅ Manter (feature da app) |
| **Dev-docs (.dev-docs/)** | 7 | ✅ Manter (novo) |
| **Raiz do projeto** | 5 | ⚠️ **MOVER** |
| **docs/ (não-procedures)** | 1 | ⚠️ **MOVER** |
| **webapp/** | 2 | ⚠️ **MOVER** |
| **TOTAL** | **27** | - |
| **A MOVER** | **9** | ⚠️ |

---

**Data**: 2026-01-28
**Autor**: Claude Code (Análise Automatizada)
**Status**: 📋 Plano Pronto para Execução
