---
name: git-workflow
description: Gerenciamento completo de Git workflow com comandos simplificados e sistema de help integrado
argument-hint: [comando] [argumentos]
allowed-tools: Bash(git:*)
---

# Git Workflow - AMG_Data

Gerenciamento completo do fluxo Git em comandos simples com sistema de help integrado.

## ⚙️ Configurações

```bash
# Caminho onde salvar checkpoints (personalizável)
CHECKPOINT_PATH="checkpoints"

# Alternativas sugeridas:
# CHECKPOINT_PATH=".git/checkpoints"
# CHECKPOINT_PATH="docs/project-checkpoints"
# CHECKPOINT_PATH="/tmp/git-checkpoints"

# Detecta branch padrão do repositório (main ou master)
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
DEFAULT_BRANCH=${DEFAULT_BRANCH:-main}  # fallback para main se não detectar
```

## 🛡️ Melhorias de Segurança v1.1

Esta versão corrige **5 bugs críticos** identificados por revisão de código:

1. **✅ Working tree limpa antes de `start`** - Evita capturar mudanças não intencionais
2. **✅ Tags com segundos** - Previne colisão de tags (checkpoint-YYYYMMDD-HHMMSS)
3. **✅ Arquivos sem colisão** - Usa nome completo (feature_water vs fix_water)
4. **✅ Auto-detecção main/master** - Compatível com qualquer repositório
5. **✅ Delete remoto tolerante** - Não falha em branches protegidas

**Impacto:** Workflow muito mais seguro e robusto para uso em equipe.

## 📚 Sistema de Help

### Ver Todos os Comandos

**Comando:** `help`

**Output:**
```
📚 GIT WORKFLOW - AMG_Data
Comandos disponíveis:

🚀 INICIAR TRABALHO
  1. start          - Criar branch + checkpoint inicial
  2. checkpoint     - Salvar checkpoint intermediário

💾 COMMITS
  3. quick-commit   - Commit automático (analisa mudanças)
  4. commit         - Commit manual especificando tipo/escopo

✅ FINALIZAR
  5. finish         - Merge + cleanup (mantém commits)
  6. finish-clean   - Merge com squash (1 commit limpo)
  7. abort          - Descartar tudo e voltar à main

🔙 RECUPERAÇÃO
  8. rollback       - Voltar a checkpoint específico
  9. rollback-list  - Listar checkpoints disponíveis

📊 INFORMAÇÕES
  10. status        - Ver estado atual do trabalho
  11. export-log    - Exportar histórico Git

Use: help [número] para ver detalhes e exemplos
Exemplo: help 1 ou help 3
```

### Ver Detalhes de Comando Específico

**Comando:** `help [número]`

---

## 🎯 Comandos Disponíveis

### 1. START - Iniciar Trabalho

**Sintaxe:**
```bash
start [tipo]/nome-descritivo
```

**Tipos disponíveis:**
- `feature` - Nova funcionalidade
- `fix` - Correção de bug
- `refactor` - Refatoração de código
- `test` - Testes e experimentos
- `hotfix` - Correção urgente
- `docs` - Documentação
- `chore` - Manutenção/tarefas
- `perf` - Melhorias de performance
- `style` - Apenas formatação/CSS

**O que faz:**
```bash
# 0. VALIDAÇÃO: Verifica se working tree está limpa
if [[ $(git status --porcelain) ]]; then
  echo "❌ ERRO: Você tem mudanças não commitadas!"
  echo ""
  git status --short
  echo ""
  echo "Por favor, resolva antes de criar nova branch:"
  echo "  git stash        → Guardar mudanças temporariamente"
  echo "  git commit -am   → Commitar mudanças"
  echo "  git reset --hard → Descartar mudanças (CUIDADO!)"
  echo ""
  echo "Depois rode 'start' novamente."
  exit 1
fi

# VALIDAÇÃO: Recomenda estar na branch padrão
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "$DEFAULT_BRANCH" ]; then
  echo "⚠️  ATENÇÃO: Você está em '$CURRENT_BRANCH'"
  echo "Recomendado: estar em '$DEFAULT_BRANCH' para criar branches"
  echo ""
  read -p "Continuar mesmo assim? (sim/não): " CONFIRM
  if [ "$CONFIRM" != "sim" ]; then
    echo "❌ Operação cancelada."
    echo "Para ir à $DEFAULT_BRANCH: git checkout $DEFAULT_BRANCH"
    exit 1
  fi
fi

# 1. Cria branch
git checkout -b [tipo]/[nome]

# 2. Checkpoint inicial (só se houver algo para commitar)
if [[ $(git status --porcelain) ]]; then
  git add .
  git commit -m "chore(checkpoint): before starting [nome]"
fi

# 3. Cria tag para recuperação fácil (COM SEGUNDOS para evitar colisão)
TAG="checkpoint-$(date +%Y%m%d-%H%M%S)"
git tag $TAG

# 4. Registra estado em arquivo (SEM COLISÃO - usa nome completo com _)
mkdir -p $CHECKPOINT_PATH
BRANCH_FULL=$(git branch --show-current | tr '/' '_')
echo "Branch: [tipo]/[nome]
Data: $(date)
Último commit: $(git log -1 --oneline)
Tag: $TAG" > $CHECKPOINT_PATH/checkpoint-$BRANCH_FULL.txt

# 5. Confirma
✅ Branch criada: [tipo]/[nome]
✅ Checkpoint salvo: $TAG
✅ Arquivo: $CHECKPOINT_PATH/checkpoint-$BRANCH_FULL.txt
🚀 Pronto para trabalhar!
```

**Exemplos:**
```bash
start feature/water-monitoring
# → Cria: feature/water-monitoring
# → Checkpoint: checkpoint-20250121-1430
# → Arquivo: checkpoints/checkpoint-water-monitoring.txt

start fix/energy-calculation-bug
# → Cria: fix/energy-calculation-bug
# → Checkpoint: checkpoint-20250121-1445

start test/new-sidebar-layout
# → Cria: test/new-sidebar-layout
# → Para experimentos sem comprometer main

start hotfix/login-security
# → Cria: hotfix/login-security
# → Para correções urgentes

start docs/api-documentation
# → Cria: docs/api-documentation
# → Para trabalho em documentação
```

**Help detalhado - help 1:**
```
📖 Comando #1: START

DESCRIÇÃO:
Cria uma nova branch e salva checkpoint inicial do estado atual.

SINTAXE:
  start [tipo]/[nome-descritivo]

TIPOS DISPONÍVEIS:
  - feature   : Nova funcionalidade
  - fix       : Correção de bug
  - refactor  : Refatoração de código
  - test      : Testes e experimentos
  - hotfix    : Correção urgente
  - docs      : Documentação
  - chore     : Manutenção/tarefas
  - perf      : Performance
  - style     : Formatação/CSS

EXEMPLO:
  start feature/water-monitoring
  start fix/energy-calculation-bug
  start test/new-sidebar-layout

O QUE FAZ:
  ✓ Cria branch: feature/water-monitoring
  ✓ Checkpoint: "chore(checkpoint): before starting water-monitoring"
  ✓ Tag: checkpoint-20250121-1430
  ✓ Registra estado em: checkpoints/checkpoint-water-monitoring.txt
  ✓ Pronto para trabalhar!
```

---

### 2. CHECKPOINT - Salvar Checkpoint Intermediário

**Sintaxe:**
```bash
checkpoint [descrição]
```

**O que faz:**
```bash
# 1. Adiciona todas as mudanças
git add .

# 2. Cria commit de checkpoint
git commit -m "chore(checkpoint): [descrição]"

# 3. Cria tag com timestamp (COM SEGUNDOS para evitar colisão)
TAG="checkpoint-$(date +%Y%m%d-%H%M%S)"
git tag $TAG

# 4. Registra em arquivo (SEM COLISÃO - nome completo com _)
BRANCH_FULL=$(git branch --show-current | tr '/' '_')
echo "
Checkpoint: [descrição]
Data: $(date)
Commit: $(git log -1 --oneline)
Tag: $TAG" >> $CHECKPOINT_PATH/checkpoint-$BRANCH_FULL.txt

# 5. Confirma
✅ Checkpoint salvo: $TAG
📝 Descrição: [descrição]
📍 Commit: $(git log -1 --oneline)
```

**Exemplos:**
```bash
checkpoint "layout básico funcionando"
# → Tag: checkpoint-20250121-1515
# → Para voltar: rollback checkpoint-20250121-1515

checkpoint "antes de mexer nos callbacks"
# → Salva estado antes de mudanças arriscadas

checkpoint "sidebar modular completa"
# → Marco de progresso importante

checkpoint "testes passando com 100% cobertura"
# → Estado validado e testado
```

**Help detalhado - help 2:**
```
📖 Comando #2: CHECKPOINT

DESCRIÇÃO:
Salva um checkpoint intermediário do seu trabalho atual.
Útil antes de mudanças arriscadas ou como marcos de progresso.

SINTAXE:
  checkpoint [descrição]

QUANDO USAR:
  ✓ Antes de mudanças arriscadas/experimentais
  ✓ Após completar parte importante do trabalho
  ✓ Antes de refatorações grandes
  ✓ Como marcos de progresso

EXEMPLO:
  checkpoint "layout básico funcionando"
  checkpoint "antes de mexer nos callbacks"
  checkpoint "testes passando"

O QUE FAZ:
  ✓ Commit: "chore(checkpoint): [descrição]"
  ✓ Tag: checkpoint-20250121-1515
  ✓ Registro: Adiciona ao arquivo de checkpoints
  ✓ Permite voltar com: rollback [tag ou número]
```

---

### 3. QUICK-COMMIT - Commit Automático

**Sintaxe:**
```bash
quick-commit
```

**Detecção Automática:**

| Situação | Tipo Detectado | Exemplo de Commit |
|----------|----------------|-------------------|
| Novo arquivo em `pages/` | `feat(pages)` | feat(pages): add water monitoring page |
| Novo arquivo em `components/` | `feat(components)` | feat(components): add demo badge |
| Modificação em `callbacks/` com bug | `fix(callbacks)` | fix(callbacks): correct energy calculation |
| Modificação em `callbacks/` (refactor) | `refactor(callbacks)` | refactor(callbacks): optimize query |
| Modificação em `*.css` | `style` | style: improve card spacing |
| Modificação em `*.md` | `docs` | docs: update installation guide |
| Modificação em `config/` | `chore(config)` | chore(config): update access control |
| Modificação em `sidebar.py` | `refactor(sidebar)` | refactor(sidebar): extract module |

**O que faz:**
```bash
# 1. Analisa mudanças
git status
git diff

# 2. Detecta tipo/escopo automaticamente
# [Lógica de detecção baseada na tabela acima]

# 3. Gera mensagem descritiva
# Analisa nomes de arquivos, conteúdo do diff

# 4. Commita
git add .
git commit -m "[tipo]([escopo]): [descrição]"

# 5. Confirma
✅ Commit criado: [mensagem completa]
📝 Arquivos: X modificados, Y novos
```

**Exemplos práticos:**

**Exemplo 1: Nova página criada**
```
Arquivos modificados:
  A  pages/energy/water.py
  M  index.py
  M  config/access_control.py

Análise:
  - Arquivo novo em pages/ → feat(pages)
  - Nome: water.py → "water monitoring page"

Commit gerado:
  feat(pages): add water monitoring page

Confirmação:
  ✅ Commit criado: feat(pages): add water monitoring page
  📝 Arquivos: 3 modificados (1 novo, 2 alterados)
```

**Exemplo 2: Bug corrigido**
```
Arquivos modificados:
  M  callbacks/energy_callbacks.py

Análise do diff:
  - Função: calculate_cost()
  - Mudança: Corrigiu fórmula de cálculo
  - Palavras-chave no diff: "fix", "correct", "bug"

Commit gerado:
  fix(callbacks): correct SE03 energy cost calculation

Confirmação:
  ✅ Commit criado: fix(callbacks): correct SE03 energy cost calculation
  📝 Arquivos: 1 modificado
```

**Exemplo 3: CSS alterado**
```
Arquivos modificados:
  M  assets/custom.css
  M  assets/theme-dark.css

Análise:
  - Apenas arquivos .css → style
  - Mudanças: padding, margin, colors

Commit gerado:
  style: improve dark theme card styling

Confirmação:
  ✅ Commit criado: style: improve dark theme card styling
  📝 Arquivos: 2 CSS modificados
```

**Exemplo 4: Refatoração de sidebar**
```
Arquivos modificados:
  A  components/sidebars/energy_sidebar.py
  M  sidebar.py

Análise:
  - Novo módulo em components/sidebars/
  - Modificação em sidebar.py
  - Padrão: extração de código → refactor

Commit gerado:
  refactor(sidebar): extract energy sidebar to separate module

Confirmação:
  ✅ Commit criado: refactor(sidebar): extract energy sidebar to separate module
  📝 Arquivos: 1 novo, 1 modificado
```

**Exemplo 5: Documentação atualizada**
```
Arquivos modificados:
  M  README.md
  M  docs/installation.md

Análise:
  - Apenas arquivos .md → docs
  
Commit gerado:
  docs: update installation instructions

Confirmação:
  ✅ Commit criado: docs: update installation instructions
  📝 Arquivos: 2 documentos modificados
```

**Help detalhado - help 3:**
```
📖 Comando #3: QUICK-COMMIT

DESCRIÇÃO:
Analisa automaticamente suas mudanças e cria commit com mensagem apropriada.
Detecta tipo e escopo baseado nos arquivos modificados.

SINTAXE:
  quick-commit

DETECÇÃO AUTOMÁTICA:
  📁 Arquivos                    → Tipo detectado
  ─────────────────────────────────────────────
  pages/energy/water.py (novo)  → feat(pages)
  callbacks/energy_cb.py        → refactor(callbacks)
  components/card.py            → refactor(components)
  assets/style.css              → style
  README.md                     → docs
  Bug em production_cb.py       → fix(callbacks)

EXEMPLOS:

Exemplo 1: Criou nova página
  Arquivos: pages/energy/gas.py (novo), index.py
  Commit: "feat(pages): add gas monitoring page"

Exemplo 2: Corrigiu bug
  Arquivos: callbacks/energy_callbacks.py
  Commit: "fix(callbacks): correct SE03 calculation"

Exemplo 3: Mudou CSS
  Arquivos: assets/custom.css
  Commit: "style: improve card spacing and layout"

Exemplo 4: Refatorou sidebar
  Arquivos: components/sidebars/energy_sidebar.py, sidebar.py
  Commit: "refactor(sidebar): extract energy sidebar to module"

O QUE FAZ:
  ✓ Analisa: git status + git diff
  ✓ Detecta: tipo, escopo, e descrição
  ✓ Executa: git add . && git commit -m "..."
  ✓ Confirma: Mostra mensagem gerada
```

---

### 4. COMMIT - Commit Manual

**Sintaxe:**
```bash
commit [tipo] [escopo] [mensagem]
```

**O que faz:**
```bash
# 1. Adiciona mudanças
git add .

# 2. Cria commit com formato Conventional Commits
git commit -m "[tipo]([escopo]): [mensagem]"

# 3. Confirma
✅ Commit criado: [tipo]([escopo]): [mensagem]
```

**Exemplos:**
```bash
commit feat pages add water monitoring dashboard
# → Commit: "feat(pages): add water monitoring dashboard"

commit fix callbacks correct SE03 calculation
# → Commit: "fix(callbacks): correct SE03 calculation"

commit refactor sidebar extract energy filters
# → Commit: "refactor(sidebar): extract energy filters"

commit docs readme update installation instructions
# → Commit: "docs(readme): update installation instructions"

commit style improve card spacing and colors
# → Commit: "style: improve card spacing and colors"

commit chore config update access control matrix
# → Commit: "chore(config): update access control matrix"
```

**Help detalhado - help 4:**
```
📖 Comando #4: COMMIT

DESCRIÇÃO:
Commit manual onde você especifica o tipo, escopo e mensagem.
Para quando você quer controle total sobre a mensagem.

SINTAXE:
  commit [tipo] [escopo] [mensagem]

TIPOS DISPONÍVEIS:
  - feat      : Nova funcionalidade
  - fix       : Correção de bug
  - refactor  : Refatoração
  - docs      : Documentação
  - style     : Formatação
  - chore     : Manutenção
  - perf      : Performance
  - test      : Testes

EXEMPLO:
  commit feat pages add water monitoring dashboard
  commit fix callbacks correct energy calculation
  commit refactor sidebar extract filters module

O QUE FAZ:
  ✓ Formata: [tipo]([escopo]): [mensagem]
  ✓ Executa: git add . && git commit
  ✓ Segue: Conventional Commits
```

---

### 5. FINISH - Finalizar com Sucesso

**Sintaxe:**
```bash
finish [mensagem-final]
```

**O que faz:**
```bash
# 1. Commit final se houver mudanças não commitadas
if [[ $(git status --porcelain) ]]; then
  git add .
  git commit -m "feat: complete $(git branch --show-current | sed 's/.*\///') - [mensagem-final]"
fi

# 2. Push da branch atual
BRANCH=$(git branch --show-current)
git push origin $BRANCH

# 3. Volta para branch padrão (main ou master)
git checkout $DEFAULT_BRANCH
git pull

# 4. Merge (mantém histórico de commits)
git merge $BRANCH

# 5. Push branch padrão
git push origin $DEFAULT_BRANCH

# 6. Deleta branch local
git branch -d $BRANCH

# 7. Deleta branch remote (TOLERANTE a falhas - branch protection, permissões, etc.)
git push origin --delete $BRANCH 2>/dev/null || {
  echo "⚠️  Não foi possível deletar branch remota (pode estar protegida ou sem permissão)"
  echo "Delete manualmente se necessário: git push origin --delete $BRANCH"
}

# 8. Confirma
✅ Merge completo!
✅ Branch $BRANCH integrada à $DEFAULT_BRANCH
✅ Branch local deletada
📊 Commits preservados no histórico
```

**Exemplos:**
```bash
finish "water monitoring system with real-time data"
# → Commit final: "feat: complete water-monitoring - water monitoring system with real-time data"
# → Merge mantém todos os commits da branch
# → Branch deletada após merge

finish "sidebar refactor with modular components"
# → Merge preserva histórico de refatoração
# → Útil quando commits intermediários são importantes
```

**Help detalhado - help 5:**
```
📖 Comando #5: FINISH

DESCRIÇÃO:
Finaliza trabalho e faz merge na main mantendo o histórico de commits.
Todos os commits da branch ficam visíveis no histórico da main.

SINTAXE:
  finish [mensagem-final]

QUANDO USAR:
  ✓ Commits intermediários são importantes
  ✓ Quer rastrear evolução do trabalho
  ✓ Feature tem marcos significativos
  ✓ Trabalho em equipe (outros veem progresso)

EXEMPLO:
  finish "water monitoring with real-time data"

O QUE FAZ:
  ✓ Commit final (se houver mudanças)
  ✓ Push branch
  ✓ Checkout main
  ✓ Merge (preserva commits)
  ✓ Push main
  ✓ Deleta branch local e remote

RESULTADO:
  Main terá todos os commits da branch visíveis
```

---

### 6. FINISH-CLEAN - Finalizar com Squash

**Sintaxe:**
```bash
finish-clean [mensagem-final]
```

**O que faz:**
```bash
# 1. Guarda nome da branch
BRANCH=$(git branch --show-current)
BRANCH_NAME=$(echo $BRANCH | sed 's/.*\///')

# 2. Volta para branch padrão (main ou master)
git checkout $DEFAULT_BRANCH
git pull

# 3. Squash merge (todos commits viram 1)
git merge --squash $BRANCH

# 4. Commit único com mensagem limpa
# Detecta tipo da branch (feature/ → feat, fix/ → fix, etc.)
TYPE=$(echo $BRANCH | cut -d'/' -f1)
case $TYPE in
  feature) TYPE="feat";;
  hotfix) TYPE="fix";;
  *) TYPE=$TYPE;;
esac

git commit -m "$TYPE: [mensagem-final]"

# 5. Push branch padrão
git push origin $DEFAULT_BRANCH

# 6. Deleta branch local (força)
git branch -D $BRANCH

# 7. Deleta branch remote (TOLERANTE a falhas)
git push origin --delete $BRANCH 2>/dev/null || true

# 8. Confirma
✅ Merge com squash completo!
✅ X commits da branch viraram 1 commit
✅ Commit em $DEFAULT_BRANCH: "$TYPE: [mensagem-final]"
✅ Branch deletada
📝 Histórico limpo
```

**Exemplos detalhados:**

**Exemplo 1: Feature com muitos commits**
```
Situação:
  Branch: feature/water-monitoring
  Commits na branch: 15
    - chore(checkpoint): before starting
    - feat(pages): add water page
    - style: fix typo
    - refactor: improve layout
    - feat(components): add charts
    - style: chart colors
    - chore(checkpoint): before callbacks
    - feat(callbacks): add water callbacks
    - fix: callback bug
    - refactor: optimize queries
    - docs: add comments
    - style: formatting
    - test: add tests
    - fix: test edge case
    - feat: finalize water module

Comando:
  finish-clean "complete water monitoring with charts and real-time data"

Resultado na main:
  1 único commit: "feat: complete water monitoring with charts and real-time data"
  
  ✅ Histórico limpo (15 commits → 1)
  ✅ Branch feature/water-monitoring deletada
  ✅ Main tem apenas o resultado final
```

**Exemplo 2: Refatoração grande**
```
Situação:
  Branch: refactor/sidebar-modules
  Commits: 12
    - chore(checkpoint): before refactor
    - refactor: extract energy sidebar
    - refactor: extract production sidebar
    - refactor: extract maintenance sidebar
    - refactor: update imports
    - fix: import paths
    - refactor: centralize sidebar logic
    - refactor: improve sidebar state
    - style: formatting
    - docs: add sidebar docs
    - test: sidebar tests
    - fix: test failures

Comando:
  finish-clean "modular sidebar system with component separation"

Resultado:
  1 commit: "refactor: modular sidebar system with component separation"
  
  ✅ 12 commits viraram 1
  ✅ Histórico da main está limpo
```

**Exemplo 3: Hotfix urgente**
```
Situação:
  Branch: hotfix/login-security
  Commits: 5
    - chore(checkpoint): before hotfix
    - fix: security vulnerability
    - fix: add validation
    - test: security tests
    - docs: security notes

Comando:
  finish-clean "critical security fix in login validation"

Resultado:
  1 commit: "fix: critical security fix in login validation"
  
  ✅ Hotfix aplicado com 1 commit limpo
```

**Help detalhado - help 6:**
```
📖 Comando #6: FINISH-CLEAN

DESCRIÇÃO:
Finaliza trabalho com histórico limpo. Todos os commits da branch
viram um único commit descritivo na main.

SINTAXE:
  finish-clean [mensagem-final]

QUANDO USAR:
  ✓ Fez muitos commits pequenos/bagunçados
  ✓ Quer histórico limpo na main
  ✓ Commits intermediários não importam
  ✓ Checkpoints e WIP não devem aparecer

EXEMPLOS:

Exemplo 1: Feature com 15 commits
  Branch: feature/water-monitoring (15 commits)
  Comando: finish-clean "complete water monitoring with charts"
  Resultado: 1 commit na main

Exemplo 2: Refatoração com 12 commits
  Branch: refactor/sidebar-modules (12 commits)
  Comando: finish-clean "modular sidebar system"
  Resultado: 1 commit limpo

O QUE FAZ:
  ✓ Volta à main
  ✓ Squash merge (X commits → 1)
  ✓ Commit: "feat: [mensagem]"
  ✓ Push main
  ✓ Deleta branch

RESULTADO:
  Histórico limpo com apenas resultado final
```

---

### 7. ABORT - Descartar Tudo

**Sintaxe:**
```bash
abort
```

**O que faz:**
```bash
# 1. Confirma ação destrutiva
echo "⚠️  ATENÇÃO: Isso vai descartar TODAS as mudanças da branch atual!"
echo "Branch: $(git branch --show-current)"
echo "Commits que serão perdidos:"
git log $DEFAULT_BRANCH..HEAD --oneline
echo ""
read -p "Tem certeza? (sim/não): " CONFIRM

if [ "$CONFIRM" != "sim" ]; then
  echo "❌ Operação cancelada."
  exit 0
fi

# 2. Guarda nome da branch
BRANCH=$(git branch --show-current)

# 3. Volta para branch padrão
git checkout $DEFAULT_BRANCH

# 4. Deleta branch local (força)
git branch -D $BRANCH

# 5. Deleta branch remote (se existir)
git push origin --delete $BRANCH 2>/dev/null || true

# 6. Confirma
✅ Mudanças descartadas
✅ Branch $BRANCH deletada
✅ Voltou à $DEFAULT_BRANCH (estado estável)
```

**Exemplo:**
```bash
abort

# Output:
⚠️  ATENÇÃO: Isso vai descartar TODAS as mudanças da branch atual!
Branch: test/new-layout
Commits que serão perdidos:
  abc1234 feat: new layout experiment
  def5678 chore(checkpoint): before layout
  
Tem certeza? (sim/não): sim

✅ Mudanças descartadas
✅ Branch test/new-layout deletada
✅ Voltou à main (ou master, dependendo do repo)
```

**Help detalhado - help 7:**
```
📖 Comando #7: ABORT

DESCRIÇÃO:
Descarta TODAS as mudanças da branch atual e volta para main.
Ação destrutiva - pede confirmação.

SINTAXE:
  abort

QUANDO USAR:
  ✓ Experimento que não deu certo
  ✓ Mudanças que não servem mais
  ✓ Quer recomeçar do zero

⚠️  ATENÇÃO:
  • Ação IRREVERSÍVEL
  • Todos os commits da branch serão perdidos
  • Branch será deletada (local e remote)
  • Sempre pede confirmação

EXEMPLO:
  abort
  
  → Mostra commits que serão perdidos
  → Pede confirmação: (sim/não)
  → Se "sim": deleta tudo e volta à main
  → Se "não": cancela operação

O QUE FAZ:
  ✓ Mostra o que será perdido
  ✓ Pede confirmação
  ✓ Volta à main
  ✓ Deleta branch (local + remote)
```

---

### 8. ROLLBACK - Voltar a Checkpoint

**Sintaxe:**
```bash
rollback [checkpoint-id ou "last" ou número]
```

**O que faz:**
```bash
# Caso 1: "last" - Volta ao último checkpoint
if [ "$1" = "last" ]; then
  HASH=$(git log --grep="checkpoint" --format="%H" | head -1)
  DESCRIPTION=$(git log --grep="checkpoint" --format="%s" | head -1)
  
# Caso 2: Número (da rollback-list)
elif [[ "$1" =~ ^[0-9]+$ ]]; then
  # Busca checkpoint por índice
  HASH=$(git log --grep="checkpoint" --format="%H" | sed -n "${1}p")
  DESCRIPTION=$(git log --grep="checkpoint" --format="%s" | sed -n "${1}p")
  
# Caso 3: Tag de checkpoint
elif [[ "$1" =~ ^checkpoint- ]]; then
  HASH=$(git rev-parse $1)
  DESCRIPTION=$(git log -1 --format="%s" $1)
  
# Caso 4: Hash direto
else
  HASH=$1
  DESCRIPTION=$(git log -1 --format="%s" $1)
fi

# Confirma ação destrutiva
echo "⚠️  ATENÇÃO: Isso vai DESCARTAR mudanças não commitadas!"
echo "Voltando para: $DESCRIPTION"
echo "Hash: $HASH"
echo ""
read -p "Tem certeza? (sim/não): " CONFIRM

if [ "$CONFIRM" != "sim" ]; then
  echo "❌ Operação cancelada."
  exit 0
fi

# Executa rollback
git reset --hard $HASH

# Confirma
✅ Estado restaurado!
📍 Checkpoint: $DESCRIPTION
📅 Data: $(git log -1 --format="%ad" --date=format:"%d/%m/%Y %H:%M")
🔖 Hash: $HASH
```

**Exemplos:**
```bash
rollback last
# → Volta ao checkpoint mais recente

rollback 2
# → Volta ao checkpoint #2 da lista (rollback-list)

rollback checkpoint-20250121-1515
# → Volta usando a tag específica

rollback abc1234
# → Volta usando hash direto
```

**Help detalhado - help 8:**
```
📖 Comando #8: ROLLBACK

DESCRIÇÃO:
Volta o código para um checkpoint anterior.
Descarta mudanças não commitadas.

SINTAXE:
  rollback [checkpoint-id ou "last" ou número]

FORMAS DE USO:
  rollback last                     → Último checkpoint
  rollback 2                        → Checkpoint #2 (veja rollback-list)
  rollback checkpoint-20250121-1515 → Via tag
  rollback abc1234                  → Via hash

⚠️  ATENÇÃO:
  • Descarta mudanças NÃO commitadas
  • Usa git reset --hard
  • Pede confirmação antes

EXEMPLO:
  rollback 2
  
  → Mostra qual checkpoint
  → Pede confirmação
  → Restaura estado

O QUE FAZ:
  ✓ Identifica checkpoint
  ✓ Mostra informações
  ✓ Pede confirmação
  ✓ git reset --hard [checkpoint]
  ✓ Confirma restauração

RECUPERAÇÃO DE EMERGÊNCIA:
  Se algo deu muito errado:
  1. rollback-list  → Ver checkpoints
  2. rollback 1     → Voltar ao primeiro (mais antigo)
```

---

### 9. ROLLBACK-LIST - Listar Checkpoints

**Sintaxe:**
```bash
rollback-list
```

**O que faz:**
```bash
# 1. Busca todos commits de checkpoint
git log --grep="checkpoint" --pretty=format:"%H|%ad|%s" --date=format:"%d/%m %H:%M"

# 2. Formata output numerado
echo "📋 CHECKPOINTS DISPONÍVEIS:"
echo ""
echo "ID    Data/Hora    Tag                       Descrição"
echo "──────────────────────────────────────────────────────────────────────"

# 3. Lista numerada
INDEX=1
git log --grep="checkpoint" --pretty=format:"%H|%ad|%s" --date=format:"%d/%m %H:%M" | while IFS='|' read HASH DATE MSG; do
  # Busca tag se existir
  TAG=$(git tag --points-at $HASH | grep "checkpoint-" || echo "---")
  
  # Extrai descrição (remove "chore(checkpoint): ")
  DESC=$(echo $MSG | sed 's/chore(checkpoint): //')
  
  echo "$INDEX.    $DATE    $TAG    $DESC"
  INDEX=$((INDEX + 1))
done

echo ""
echo "💡 Para voltar: rollback [ID ou Tag ou 'last']"
echo ""
echo "Exemplos:"
echo "  rollback 2                        → Volta ao checkpoint #2"
echo "  rollback checkpoint-20250121-1515 → Volta usando tag"
echo "  rollback last                     → Volta ao mais recente"
```

**Output exemplo:**
```
📋 CHECKPOINTS DISPONÍVEIS:

ID    Data/Hora    Tag                       Descrição
──────────────────────────────────────────────────────────────────────
1.    21/01 14:30  checkpoint-20250121-1430  before starting water-monitoring
2.    21/01 15:15  checkpoint-20250121-1515  layout básico funcionando  
3.    21/01 16:00  checkpoint-20250121-1600  antes de mexer callbacks
4.    21/01 16:45  checkpoint-20250121-1645  callbacks implementados
5.    21/01 17:20  checkpoint-20250121-1720  before finishing feature

💡 Para voltar: rollback [ID ou Tag ou "last"]

Exemplos:
  rollback 2                        → Volta ao checkpoint #2
  rollback checkpoint-20250121-1515 → Volta usando tag
  rollback last                     → Volta ao mais recente (#5)
```

**Help detalhado - help 9:**
```
📖 Comando #9: ROLLBACK-LIST

DESCRIÇÃO:
Lista todos os checkpoints disponíveis para recuperação.
Mostra ID, data, tag e descrição de cada checkpoint.

SINTAXE:
  rollback-list

EXEMPLO DE OUTPUT:
  
  ID    Data/Hora    Tag                       Descrição
  ───────────────────────────────────────────────────────────
  1.    21/01 14:30  checkpoint-20250121-1430  before starting
  2.    21/01 15:15  checkpoint-20250121-1515  layout funcionando
  3.    21/01 16:00  checkpoint-20250121-1600  antes callbacks

INTEGRAÇÃO:
  Use com: rollback [ID]
  
  Exemplo:
    rollback-list      → Vê a lista
    rollback 2         → Volta ao checkpoint #2
    rollback last      → Volta ao mais recente

O QUE MOSTRA:
  ✓ Número sequencial (ID)
  ✓ Data e hora
  ✓ Tag do checkpoint
  ✓ Descrição
  ✓ Instruções de uso
```

---

### 10. STATUS - Ver Estado Atual

**Sintaxe:**
```bash
status
```

**O que faz:**
```bash
# 1. Coleta informações
BRANCH=$(git branch --show-current)
BRANCH_TYPE=$(echo $BRANCH | cut -d'/' -f1)
BRANCH_NAME=$(echo $BRANCH | sed 's/.*\///')
COMMITS_AHEAD=$(git rev-list --count $DEFAULT_BRANCH..HEAD)
FILES_CHANGED=$(git status --porcelain | wc -l)
LAST_CHECKPOINT=$(git log --grep="checkpoint" --oneline | head -1)

# 2. Formata output
echo "📍 GIT STATUS - AMG_Data"
echo ""
echo "Branch Atual:     $BRANCH"
echo "Tipo:             $BRANCH_TYPE"
echo "Nome:             $BRANCH_NAME"
echo "Commits à frente: $COMMITS_AHEAD desde $DEFAULT_BRANCH"
echo "Mudanças:         $FILES_CHANGED arquivos"
echo ""

# 3. Último checkpoint
if [ -n "$LAST_CHECKPOINT" ]; then
  echo "⏮️  Último checkpoint:"
  echo "   $LAST_CHECKPOINT"
  echo ""
fi

# 4. Arquivos modificados
echo "📝 Arquivos modificados:"
git status --short
echo ""

# 5. Tags de checkpoint disponíveis
CHECKPOINT_TAGS=$(git tag | grep "checkpoint-" | tail -5)
if [ -n "$CHECKPOINT_TAGS" ]; then
  echo "🏷️  Tags de checkpoint (últimas 5):"
  echo "$CHECKPOINT_TAGS" | sed 's/^/   - /'
  echo ""
fi

# 6. Sugestões de próximos passos
echo "💡 Próximos passos:"
if [ $FILES_CHANGED -gt 0 ]; then
  echo "   - quick-commit      → Commit automático"
  echo "   - checkpoint [msg]  → Salvar checkpoint"
fi
if [ $COMMITS_AHEAD -gt 0 ]; then
  echo "   - finish [msg]      → Finalizar e merge"
  echo "   - finish-clean [msg]→ Merge com squash"
fi
echo "   - rollback-list     → Ver checkpoints disponíveis"
echo "   - abort             → Descartar tudo"
```

**Output:**
```
📍 GIT STATUS - AMG_Data

Branch Atual:     feature/water-monitoring
Tipo:             feature
Nome:             water-monitoring
Commits à frente: 5 desde main (ou master)
Mudanças:         3 arquivos

⏮️  Último checkpoint:
   abc1234 chore(checkpoint): layout básico funcionando

📝 Arquivos modificados:
 M pages/energy/water.py
 M callbacks/energy_callbacks.py
 A components/water_chart.py

🏷️  Tags de checkpoint (últimas 5):
   - checkpoint-20250121-143045
   - checkpoint-20250121-151523
   - checkpoint-20250121-160012

💡 Próximos passos:
   - quick-commit      → Commit automático
   - checkpoint [msg]  → Salvar checkpoint
   - finish [msg]      → Finalizar e merge
   - finish-clean [msg]→ Merge com squash
   - rollback-list     → Ver checkpoints disponíveis
   - abort             → Descartar tudo
```

**Help detalhado - help 10:**
```
📖 Comando #10: STATUS

DESCRIÇÃO:
Mostra visão completa do estado atual do seu trabalho.
Branch, commits, mudanças, checkpoints e próximos passos.

SINTAXE:
  status

O QUE MOSTRA:
  ✓ Branch atual e tipo
  ✓ Quantos commits à frente da main
  ✓ Arquivos modificados
  ✓ Último checkpoint
  ✓ Tags de checkpoint disponíveis
  ✓ Sugestões de próximos passos

QUANDO USAR:
  ✓ Perdeu o contexto do que estava fazendo
  ✓ Quer ver progresso
  ✓ Precisa decidir próximo passo
  ✓ Ver se há mudanças não commitadas

EXEMPLO DE OUTPUT:
  Branch: feature/water-monitoring
  Commits: 5 desde main
  Mudanças: 3 arquivos
  Último checkpoint: layout funcionando
  
  Próximos passos sugeridos
```

---

### 11. EXPORT-LOG - Exportar Histórico

**Sintaxe:**
```bash
export-log [nome-arquivo]
```

**O que faz:**
```bash
# 1. Cria diretório de logs se não existir
mkdir -p $CHECKPOINT_PATH/logs

# 2. Define nome do arquivo
if [ -z "$1" ]; then
  FILENAME="git-log-$(date +%Y%m%d-%H%M)"
else
  FILENAME="$1"
fi

# 3. Gera log formatado
git log --pretty=format:"%h | %an | %ad | %s" \
  --date=format:"%d/%m/%Y %H:%M:%S" \
  > $CHECKPOINT_PATH/logs/$FILENAME.txt

# 4. Gera log com diff completo
git log -p > $CHECKPOINT_PATH/logs/$FILENAME-diff.txt

# 5. Gera log apenas da branch atual (se não for main)
BRANCH=$(git branch --show-current)
if [ "$BRANCH" != "main" ]; then
  git log main..HEAD --pretty=format:"%h | %an | %ad | %s" \
    --date=format:"%d/%m/%Y %H:%M:%S" \
    > $CHECKPOINT_PATH/logs/$FILENAME-branch.txt
fi

# 6. Gera estatísticas
echo "Estatísticas do Git - $(date)" > $CHECKPOINT_PATH/logs/$FILENAME-stats.txt
echo "" >> $CHECKPOINT_PATH/logs/$FILENAME-stats.txt
echo "Total de commits: $(git rev-list --count HEAD)" >> $CHECKPOINT_PATH/logs/$FILENAME-stats.txt
echo "Autores:" >> $CHECKPOINT_PATH/logs/$FILENAME-stats.txt
git log --format='%an' | sort -u >> $CHECKPOINT_PATH/logs/$FILENAME-stats.txt
echo "" >> $CHECKPOINT_PATH/logs/$FILENAME-stats.txt
echo "Commits por autor:" >> $CHECKPOINT_PATH/logs/$FILENAME-stats.txt
git shortlog -sn >> $CHECKPOINT_PATH/logs/$FILENAME-stats.txt

# 7. Confirma
echo "✅ Relatórios salvos em: $CHECKPOINT_PATH/logs/"
echo ""
echo "Arquivos gerados:"
echo "  📄 $FILENAME.txt         → Histórico formatado"
echo "  📄 $FILENAME-diff.txt    → Histórico com diffs"
if [ "$BRANCH" != "main" ]; then
  echo "  📄 $FILENAME-branch.txt  → Apenas commits desta branch"
fi
echo "  📊 $FILENAME-stats.txt   → Estatísticas"
echo ""
echo "Total: $(ls -lh $CHECKPOINT_PATH/logs/$FILENAME* | wc -l) arquivos"
```

**Exemplos:**
```bash
export-log water-feature-history
# → Gera:
#   checkpoints/logs/water-feature-history.txt
#   checkpoints/logs/water-feature-history-diff.txt
#   checkpoints/logs/water-feature-history-branch.txt
#   checkpoints/logs/water-feature-history-stats.txt

export-log
# → Nome automático com timestamp:
#   checkpoints/logs/git-log-20250121-1445.txt
#   checkpoints/logs/git-log-20250121-1445-diff.txt
#   etc.
```

**Help detalhado - help 11:**
```
📖 Comando #11: EXPORT-LOG

DESCRIÇÃO:
Exporta histórico Git em múltiplos formatos para documentação.
Útil para relatórios, auditorias ou backup de histórico.

SINTAXE:
  export-log [nome-arquivo]
  
  Se não fornecer nome, usa timestamp automático.

ARQUIVOS GERADOS:
  📄 [nome].txt         → Histórico formatado
  📄 [nome]-diff.txt    → Com diffs completos
  📄 [nome]-branch.txt  → Apenas commits da branch
  📊 [nome]-stats.txt   → Estatísticas

ONDE SALVA:
  Pasta: $CHECKPOINT_PATH/logs/
  (configurável no topo da skill)

EXEMPLOS:
  export-log feature-water
  → Gera relatório da feature water
  
  export-log
  → Nome automático: git-log-20250121-1445

QUANDO USAR:
  ✓ Fim de feature (documentação)
  ✓ Relatórios de progresso
  ✓ Auditoria de mudanças
  ✓ Backup de histórico
```

---

## 🔒 Validações Automáticas

### Pré-Commit (Antes de Qualquer Commit)

```bash
# 1. Verifica credenciais hardcoded
if git diff --cached | grep -iE "(password|api_key|token|secret|credential)" > /dev/null; then
  echo "⚠️  ATENÇÃO: Possível credencial detectada!"
  echo "Revise as mudanças antes de commitar."
  git diff --cached | grep -iE "(password|api_key|token|secret|credential)" --color
  read -p "Continuar mesmo assim? (sim/não): " CONFIRM
  [ "$CONFIRM" != "sim" ] && exit 1
fi

# 2. Verifica .env
if git diff --cached --name-only | grep "\.env$" > /dev/null; then
  echo "❌ ERRO: Tentando commitar arquivo .env"
  echo "Remova .env do stage: git reset HEAD .env"
  exit 1
fi

# 3. Verifica arquivos desnecessários
UNWANTED=$(git diff --cached --name-only | grep -E "\.pyc$|__pycache__|\.DS_Store|\.idea/")
if [ -n "$UNWANTED" ]; then
  echo "⚠️  Arquivos desnecessários detectados:"
  echo "$UNWANTED"
  read -p "Remover do stage? (sim/não): " CONFIRM
  if [ "$CONFIRM" = "sim" ]; then
    echo "$UNWANTED" | xargs git reset HEAD
  fi
fi
```

### Pré-Merge (Antes de finish ou finish-clean)

```bash
# 1. Verifica se branch padrão existe
if ! git show-ref --verify --quiet refs/heads/$DEFAULT_BRANCH; then
  echo "❌ ERRO: Branch $DEFAULT_BRANCH não encontrada"
  exit 1
fi

# 2. Atualiza branch padrão e verifica conflitos
git checkout $DEFAULT_BRANCH
git pull
git checkout -

# Testa merge sem fazer
if ! git merge --no-commit --no-ff $DEFAULT_BRANCH > /dev/null 2>&1; then
  git merge --abort
  echo "❌ ERRO: Conflitos detectados com $DEFAULT_BRANCH"
  echo "Resolva conflitos antes de fazer merge:"
  echo "  1. git merge $DEFAULT_BRANCH"
  echo "  2. Resolva conflitos"
  echo "  3. git commit"
  echo "  4. Tente finish novamente"
  exit 1
fi
git merge --abort

# 3. Verifica se branch padrão está atualizada
LOCAL=$(git rev-parse $DEFAULT_BRANCH)
REMOTE=$(git rev-parse origin/$DEFAULT_BRANCH)
if [ "$LOCAL" != "$REMOTE" ]; then
  echo "⚠️  $DEFAULT_BRANCH local está desatualizada"
  echo "Atualizando..."
  git checkout $DEFAULT_BRANCH
  git pull
  git checkout -
fi
```

### Pré-Delete (Antes de abort)

```bash
# Mostra o que será perdido
echo "⚠️  ATENÇÃO: Esta ação é IRREVERSÍVEL!"
echo ""
echo "Branch: $(git branch --show-current)"
echo ""
echo "Commits que serão PERDIDOS:"
git log main..HEAD --oneline
echo ""
echo "Arquivos modificados que serão PERDIDOS:"
git status --short
echo ""

read -p "Tem ABSOLUTA CERTEZA? Digite 'DELETE' para confirmar: " CONFIRM
if [ "$CONFIRM" != "DELETE" ]; then
  echo "❌ Operação cancelada."
  exit 1
fi
```

### Pré-Rollback (Antes de Voltar a Checkpoint)

```bash
# Verifica mudanças não salvas
if [[ $(git status --porcelain) ]]; then
  echo "⚠️  ATENÇÃO: Você tem mudanças NÃO COMMITADAS!"
  echo ""
  git status --short
  echo ""
  echo "Essas mudanças serão PERDIDAS no rollback."
  echo ""
  read -p "Deseja criar checkpoint antes? (sim/não): " CREATE_CP
  
  if [ "$CREATE_CP" = "sim" ]; then
    read -p "Descrição do checkpoint: " DESC
    git add .
    git commit -m "chore(checkpoint): $DESC"
    git tag checkpoint-$(date +%Y%m%d-%H%M)
    echo "✅ Checkpoint criado!"
    echo ""
  fi
  
  read -p "Continuar com rollback? (sim/não): " CONFIRM
  [ "$CONFIRM" != "sim" ] && exit 1
fi
```

---

## 📊 Fluxos Completos de Trabalho

### Fluxo 1: Feature Simples

```bash
# 1. Inicia
start feature/water-monitoring
# → Branch criada + checkpoint inicial

# 2. Trabalha e faz commits
[... faz mudanças ...]
quick-commit
# → feat(pages): add water monitoring page

[... mais mudanças ...]
quick-commit
# → feat(components): add water chart

# 3. Finaliza
finish "water monitoring system with real-time data"
# → Merge na main + cleanup
```

### Fluxo 2: Feature Complexa com Checkpoints

```bash
# 1. Inicia
start feature/sidebar-refactor

# 2. Primeiro checkpoint
[... extrai energy sidebar ...]
checkpoint "energy sidebar extracted"
quick-commit

# 3. Segundo checkpoint
[... extrai production sidebar ...]
checkpoint "production sidebar extracted"
quick-commit

# 4. Terceiro checkpoint  
[... centraliza lógica ...]
checkpoint "sidebar logic centralized"
quick-commit

# 5. Finaliza com histórico limpo
finish-clean "modular sidebar system with component separation"
# → 1 commit limpo na main
```

### Fluxo 3: Teste que Deu Errado

```bash
# 1. Inicia teste
start test/new-layout

# 2. Checkpoint antes de mudanças arriscadas
checkpoint "before layout experiment"

# 3. Testa
[... implementa novo layout ...]
quick-commit

# 4. Não funcionou, volta ao checkpoint
rollback 1
# ou
rollback last

# 5. Tenta de novo
[... nova abordagem ...]

# 6. Ainda não funciona, desiste
abort
# → Descarta tudo, volta à main
```

### Fluxo 4: Hotfix Urgente

```bash
# 1. Cria hotfix
start hotfix/login-security

# 2. Corrige rapidamente
[... fix ...]
commit fix auth critical security vulnerability in login

# 3. Testa
[... testes ...]
commit test auth add security tests

# 4. Merge limpo e rápido
finish-clean "critical security fix in login validation"
# → 1 commit na main, hotfix aplicado
```

### Fluxo 5: Refatoração Grande

```bash
# 1. Inicia
start refactor/callback-optimization

# 2. Múltiplos checkpoints
checkpoint "before splitting callbacks"
[... split ...]
quick-commit

checkpoint "callbacks split, before optimization"
[... otimiza ...]
quick-commit

checkpoint "optimized, before tests"
[... testa ...]
quick-commit

# 3. Vê progresso
status
# → Mostra 3 checkpoints, 6 commits

# 4. Finaliza com histórico limpo
finish-clean "optimized callback system with better performance"
```

### Fluxo 6: Trabalho em Equipe

```bash
# 1. Inicia sua parte
start feature/water-api-integration

# 2. Trabalha normalmente
quick-commit
checkpoint "API client implemented"
quick-commit

# 3. Main foi atualizada por colega
# Antes de finalizar, atualiza
git checkout main
git pull
git checkout feature/water-api-integration

# 4. Testa se há conflitos
git merge main
[... resolve conflitos se houver ...]
git commit

# 5. Finaliza
finish "water monitoring API integration"
```

---

## 🆘 Troubleshooting

### Problema 1: Commit Recusado por Credenciais

```
Sintoma:
  ⚠️  ATENÇÃO: Possível credencial detectada!
  
Solução:
  1. git diff --cached    → Ver o que tem credencial
  2. Remover credenciais do código
  3. Usar variáveis de ambiente
  4. Commitar novamente
```

### Problema 2: Conflitos no Merge

```
Sintoma:
  ❌ ERRO: Conflitos detectados com main
  
Solução:
  1. git merge main       → Traz mudanças da main
  2. Resolver conflitos manualmente
  3. git add .
  4. git commit
  5. finish [msg]         → Tenta novamente
```

### Problema 3: Esqueceu de Fazer Checkpoint

```
Sintoma:
  Fez muitas mudanças sem checkpoint
  
Solução:
  checkpoint "estado atual antes de continuar"
  → Salva checkpoint agora mesmo
```

### Problema 4: Perdeu o Contexto

```
Sintoma:
  Não lembra o que estava fazendo
  
Solução:
  status                  → Ver estado completo
  rollback-list          → Ver histórico de checkpoints
  git log --oneline -10  → Ver últimos commits
```

### Problema 5: Quer Desfazer Último Commit

```
Sintoma:
  Commitou errado
  
Solução:
  # Se não fez push ainda:
  git reset --soft HEAD~1  → Desfaz commit, mantém mudanças
  
  # Se já fez push:
  commit fix ... "correct previous commit"  → Novo commit de correção
```

### Problema 6: Branch Acidental na Main

```
Sintoma:
  Commitou direto na main sem querer
  
Solução:
  # 1. Criar branch com esse commit
  git branch feature/acidental
  
  # 2. Voltar main ao commit anterior
  git reset --hard HEAD~1
  
  # 3. Ir para a branch criada
  git checkout feature/acidental
  
  # 4. Continuar trabalhando normalmente
```

---

## 🎓 Boas Práticas

### ✅ Faça

- **Checkpoints frequentes** antes de mudanças arriscadas
- **Commits pequenos** e focados
- **Mensagens descritivas** e claras
- **Teste antes de finish** para garantir que funciona
- **Use rollback-list** para ver onde pode voltar
- **Use status** quando perder contexto
- **Use finish-clean** para histórico limpo

### ❌ Evite

- Commits gigantes com muitas mudanças não relacionadas
- Mensagens vagas tipo "update" ou "fix"
- Merge sem testar antes
- Trabalhar direto na main
- Esquecer de criar checkpoints
- Commitar credenciais ou .env
- Fazer rollback sem ter certeza

---

## 📖 Resumo de Comandos

```
🚀 INICIAR
  start [tipo]/nome        - Nova branch + checkpoint
  
💾 TRABALHAR
  checkpoint [msg]         - Checkpoint intermediário
  quick-commit            - Commit automático
  commit [tipo] [esc] [msg] - Commit manual
  
✅ FINALIZAR
  finish [msg]            - Merge (mantém commits)
  finish-clean [msg]      - Merge squash (1 commit)
  abort                   - Descartar tudo
  
🔙 RECUPERAR
  rollback [id]           - Voltar checkpoint
  rollback-list          - Ver checkpoints
  
📊 INFO
  status                  - Estado atual
  export-log [nome]       - Exportar histórico
  
📚 AJUDA
  help                    - Ver todos comandos
  help [número]           - Detalhes de comando
```

---

## 🎯 Quando Usar Cada Comando

| Situação | Comando |
|----------|---------|
| Começar nova feature | `start feature/nome` |
| Começar correção | `start fix/nome` |
| Antes de mudança arriscada | `checkpoint "antes de..."` |
| Commitar mudanças | `quick-commit` |
| Commitar com controle | `commit tipo escopo msg` |
| Ver estado | `status` |
| Ver checkpoints | `rollback-list` |
| Voltar atrás | `rollback [id]` |
| Finalizar (preservar commits) | `finish "msg"` |
| Finalizar (histórico limpo) | `finish-clean "msg"` |
| Descartar tudo | `abort` |
| Gerar relatório | `export-log nome` |
| Ajuda geral | `help` |
| Ajuda específica | `help [número]` |

---

**Pronto! Agora você tem um workflow Git completo e profissional! 🚀**

---

## 📝 Changelog

### v1.1 (2025-01-22) - Correções Críticas de Segurança

**🔴 CRÍTICO - Correções de Bugs:**
1. ✅ **Validação de working tree antes de `start`** - Previne capturar mudanças não intencionais no checkpoint inicial
2. ✅ **Tags com segundos** - Evita colisão de tags quando múltiplos checkpoints são criados no mesmo minuto
3. ✅ **Arquivos de checkpoint sem colisão** - Usa nome completo da branch (feature_water, fix_water) em vez de só "water"
4. ✅ **Detecção automática de branch padrão** - Detecta `main` ou `master` automaticamente do repositório
5. ✅ **Delete remoto tolerante a falhas** - Comando `finish` não falha se branch estiver protegida ou sem permissão

**🟡 Melhorias:**
- Validação de branch atual antes de `start` (recomenda estar na branch padrão)
- Mensagens de erro mais claras e informativas
- Todos os comandos agora usam `$DEFAULT_BRANCH` em vez de hardcoded "main"

**Impacto:**
- Evita bugs silenciosos que poderiam corromper histórico
- Maior compatibilidade com diferentes configurações de repositório
- Workflow mais robusto em ambientes de equipe

### v1.0 (2025-01-22) - Release Inicial

**Features:**
- Sistema completo de gerenciamento Git
- 11 comandos com help integrado
- Sistema de checkpoints com tags
- Validações automáticas de segurança
- Suporte a múltiplos tipos de branch
- Conventional Commits automático