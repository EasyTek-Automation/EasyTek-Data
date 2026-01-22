---
name: commit-changes
description: Cria commits seguindo o padrão Conventional Commits do projeto AMG_Data. Use quando precisar fazer commit das mudanças.
disable-model-invocation: true
allowed-tools: Bash(git:*)
---

# Commit Padronizado - AMG_Data

Crie commits seguindo o padrão Conventional Commits.

## Padrão de Commits

O projeto AMG_Data usa **Conventional Commits**:

```
<tipo>(<escopo>): <descrição>

[corpo opcional]

[rodapé opcional]
```

### Tipos Disponíveis

- `feat` - Nova funcionalidade
- `fix` - Correção de bug
- `refactor` - Refatoração de código
- `docs` - Documentação
- `style` - Formatação (sem mudança de código)
- `test` - Adição/correção de testes
- `chore` - Tarefas de manutenção
- `perf` - Melhorias de performance
- `ci` - Configuração de CI/CD
- `build` - Build system ou dependências

### Escopos Comuns

Para AMG_Data:

- `pages` - Páginas do webapp
- `components` - Componentes reutilizáveis
- `callbacks` - Callbacks do Dash
- `api` - Event Gateway API
- `auth` - Autenticação
- `energy` - Módulo de energia
- `production` - Módulo de produção
- `maintenance` - Módulo de manutenção
- `database` - MongoDB
- `config` - Configurações
- `sidebar` - Sistema de sidebar
- `header` - Sistema de header

## Processo de Commit

### 1. Verificar Status

```bash
git status
```

### 2. Ver Mudanças

```bash
git diff
```

### 3. Adicionar Arquivos

```bash
# Adicionar todos
git add .

# Adicionar específicos
git add arquivo1.py arquivo2.py
```

### 4. Ver Últimos Commits (para seguir estilo)

```bash
git log --oneline -5
```

### 5. Criar Commit

**Exemplos:**

```bash
# Nova funcionalidade
git commit -m "feat(energy): add water monitoring page"

# Correção de bug
git commit -m "fix(callbacks): fix energy cost calculation for SE03"

# Refatoração
git commit -m "refactor(sidebar): extract energy sidebar to separate file"

# Documentação
git commit -m "docs(readme): update installation instructions"

# Com corpo explicativo
git commit -m "feat(pages): add utilities dashboard

- Integrated view of all utilities
- Energy, water, gas, compressed air
- Real-time consumption data
- Cost analysis per utility"

# Com co-author (Claude)
git commit -m "feat(energy): implement SE03 cost breakdown

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

## Diretrizes

### ✅ Boas Práticas

- Use presente do imperativo: "add" não "added"
- Primeira linha com máximo 72 caracteres
- Descrição clara e concisa
- Um commit por funcionalidade/correção
- Commits atômicos (funcionam independentemente)

### ❌ Evite

- Mensagens genéricas: "fix", "update", "changes"
- Múltiplas funcionalidades em um commit
- Commits com código não funcionando
- Commits muito grandes

## Exemplos do Projeto

Baseado no histórico do AMG_Data:

```bash
# Commits recentes reais:
c23bf25 Returning AMG Logo
38b6cdc fix: Energy Costs calculation - New energy costs calculation revision
c80e623 Checkpoint: After refactoring plan
c6fb710 fix: Including demo badge on not real data visuals - Complete
02a0cbd fix(pages): Fixing reload procedure page issue - Complete
```

**Observação:** Nem todos seguem o padrão perfeitamente. Use o formato Conventional Commits para novos commits.

## Checklist Pré-Commit

Antes de fazer commit, verifique:

- [ ] Código funciona sem erros
- [ ] Não há credenciais hardcoded
- [ ] `.env` não está sendo commitado
- [ ] Arquivos desnecessários não estão incluídos
- [ ] Mudanças estão relacionadas (commit atômico)
- [ ] Mensagem de commit é descritiva

## Workflow Completo

```bash
# 1. Ver o que mudou
git status
git diff

# 2. Adicionar mudanças
git add .

# 3. Ver histórico recente (para seguir estilo)
git log --oneline -5

# 4. Fazer commit
git commit -m "feat(energy): add SE04 monitoring page"

# 5. Verificar
git log -1

# 6. Push (se necessário)
git push origin main
```

## Situações Especiais

### Múltiplos Arquivos, Mesmo Contexto

```bash
git commit -m "refactor(components): reorganize sidebar components

- Move energy sidebar to sidebars/energy_sidebar.py
- Move states sidebar to sidebars/states_sidebar.py
- Update imports in sidebar.py"
```

### Correção Urgente (Hotfix)

```bash
git commit -m "fix(auth)!: fix critical security vulnerability in login

BREAKING CHANGE: Users must re-login after update"
```

### Breaking Change

Use `!` ou `BREAKING CHANGE:` no corpo:

```bash
git commit -m "feat(api)!: change API endpoint structure"

# Ou

git commit -m "feat(api): change API endpoint structure

BREAKING CHANGE: All endpoints now use /v2/ prefix"
```

## Dicas

1. **Commits pequenos e frequentes** > Commits grandes e raros
2. **Descrição clara** > Descrição técnica demais
3. **Funcionalidade completa** > Trabalho pela metade
4. **Testes passando** antes do commit

## Amend (Corrigir Último Commit)

Se esqueceu algo no último commit:

```bash
# Adicionar arquivos esquecidos
git add arquivo_esquecido.py

# Emendar ao último commit (não muda mensagem)
git commit --amend --no-edit

# Emendar e mudar mensagem
git commit --amend -m "feat(energy): nova mensagem corrigida"
```

⚠️ **CUIDADO:** Só use `--amend` se ainda não fez push!

## Ver Co-Autores

Se trabalhou com Claude:

```bash
git commit -m "feat(pages): implement new dashboard

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

**Pronto!** Agora você tem commits padronizados e organizados.
