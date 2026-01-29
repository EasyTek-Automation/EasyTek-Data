# 📂 Organização da Documentação

Guia para organizar arquivos de documentação dispersos na raiz do projeto.

---

## 📍 Status Atual

Arquivos soltos na raiz:

```
AMG_Data/
├── CLAUDE.md                          # Instruções para Claude Code
├── CLAUDE-PTBR.md                     # Instruções em Português
├── REFATORACAO_ARQUIVOS.md            # Refatorações pendentes
├── PLANO_TRIAGEM_AUTOMATICA.md        # Plano de triagem
├── README_PROCESS_ZPP.md              # Guia processamento ZPP
└── ... (outros arquivos)
```

---

## 🎯 Estrutura Proposta

### Mover para `.dev-docs/`

```
.dev-docs/
├── README.md                          # ✅ Criado
├── ORGANIZACAO.md                     # ✅ Este arquivo
│
├── architecture/
│   ├── webapp-architecture.md         # ← Mover CLAUDE.md
│   └── webapp-architecture-ptbr.md    # ← Mover CLAUDE-PTBR.md
│
├── technical-debt/
│   ├── README.md                      # ✅ Criado
│   ├── zpp-processing-improvements.md # ✅ Criado (revisão ZPP)
│   └── refatoracao-arquivos.md        # ← Mover REFATORACAO_ARQUIVOS.md
│
├── guides/
│   └── zpp-processing.md              # ← Mover README_PROCESS_ZPP.md
│
└── plans/
    └── triagem-automatica.md          # ← Mover PLANO_TRIAGEM_AUTOMATICA.md
```

---

## 🚀 Comandos para Organizar

### Windows (PowerShell)

```powershell
# Criar subdiretórios
New-Item -ItemType Directory -Force -Path .dev-docs\architecture
New-Item -ItemType Directory -Force -Path .dev-docs\guides
New-Item -ItemType Directory -Force -Path .dev-docs\plans

# Mover arquivos (copia + remove original)
Move-Item -Path CLAUDE.md -Destination .dev-docs\architecture\webapp-architecture.md
Move-Item -Path CLAUDE-PTBR.md -Destination .dev-docs\architecture\webapp-architecture-ptbr.md
Move-Item -Path REFATORACAO_ARQUIVOS.md -Destination .dev-docs\technical-debt\refatoracao-arquivos.md
Move-Item -Path README_PROCESS_ZPP.md -Destination .dev-docs\guides\zpp-processing.md
Move-Item -Path PLANO_TRIAGEM_AUTOMATICA.md -Destination .dev-docs\plans\triagem-automatica.md
```

### Linux/Mac (Bash)

```bash
# Mover arquivos
mv CLAUDE.md .dev-docs/architecture/webapp-architecture.md
mv CLAUDE-PTBR.md .dev-docs/architecture/webapp-architecture-ptbr.md
mv REFATORACAO_ARQUIVOS.md .dev-docs/technical-debt/refatoracao-arquivos.md
mv README_PROCESS_ZPP.md .dev-docs/guides/zpp-processing.md
mv PLANO_TRIAGEM_AUTOMATICA.md .dev-docs/plans/triagem-automatica.md
```

---

## ⚠️ Importante

### Antes de Mover

1. ✅ **Commit atual** - Salve o estado antes de reorganizar
2. ✅ **Verifique links** - Outros arquivos podem referenciar esses .md
3. ✅ **Atualize README.md** - Adicione referência à nova estrutura

### Arquivos que NÃO devem ser movidos

- ❌ `docs/` - Feature da aplicação (procedimentos operacionais)
- ❌ `webapp/DEMO_*.md` - Documentação local do módulo webapp
- ❌ `.claude/skills/*/SKILL.md` - Configuração de skills

---

## 📝 Atualizar README.md

Adicione ao `README.md` da raiz:

```markdown
## 📚 Documentação

- **Para Desenvolvedores**: Veja [.dev-docs/](./.dev-docs/) para arquitetura, guias e débito técnico
- **Para Operação**: Veja `docs/` (procedimentos de manutenção renderizados na webapp)
```

---

## 🔄 Próximos Passos

Após organizar:

1. ✅ Commit a reorganização:
   ```bash
   git add .dev-docs/
   git add -u  # Remove arquivos movidos
   git commit -m "docs: reorganizar documentação em .dev-docs/"
   ```

2. ✅ Atualizar `.gitignore` se necessário:
   ```gitignore
   # Se quiser manter .dev-docs privado (local only)
   .dev-docs/
   !.dev-docs/README.md  # Mas mantém o índice
   ```

3. ✅ Comunicar time sobre nova estrutura

---

**Criado em**: 2026-01-28
