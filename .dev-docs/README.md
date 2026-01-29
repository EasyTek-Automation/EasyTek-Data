# 📚 Documentação Técnica - AMG_Data

> **Nota**: Este diretório contém documentação para **desenvolvedores** do projeto.
> Para procedimentos operacionais, veja `docs/` (feature da aplicação).

---

## 📂 Estrutura

```
.dev-docs/
├── README.md                    # 👈 Você está aqui
├── PLANO_REORGANIZACAO.md       # 📋 Plano completo de organização
├── technical-debt/              # ⚠️ Melhorias e débitos técnicos
├── architecture/                # 🏗️ Arquitetura e design decisions
├── guides/                      # 📖 Guias de desenvolvimento
├── plans/                       # 🗺️ Planos e roadmaps
├── operations/                  # ⚙️ Operações e infraestrutura
└── modules/                     # 📦 Docs de módulos específicos
    └── webapp/                  # Aplicação Dash
```

---

## ⚠️ [Dívida Técnica](./technical-debt/)

Melhorias identificadas que **não são bugs**, mas aumentam qualidade/manutenibilidade.

**➡️ [Ver lista completa](./technical-debt/README.md)**

### Resumo Rápido

| Módulo | Total | Alta | Média | Baixa |
|--------|-------|------|-------|-------|
| ZPP Processing | 9 | 3 | 3 | 3 |

---

## 🏗️ [Arquitetura](./architecture/)

Documentação de arquitetura, design decisions e padrões.

- **[webapp-architecture-ptbr.md](./architecture/webapp-architecture-ptbr.md)** - Arquitetura da webapp (PT-BR)

> **Nota**: `CLAUDE.md` fica na **raiz** (usado pelo CLI do Claude Code)

---

## 📖 Guias

*(Mover README_PROCESS_ZPP.md aqui)*

- Guia de processamento ZPP
- Como adicionar novas páginas
- Sistema de permissões

---

## 🗺️ Planos

*(Mover PLANO_TRIAGEM_AUTOMATICA.md aqui)*

- Roadmaps
- Funcionalidades planejadas
- Refatorações futuras

---

## ⚙️ [Operações](./operations/)

Documentação de infraestrutura, DevOps e configuração de serviços.

- **[node-red-persistence.md](./operations/node-red-persistence.md)** - Persistência do Node-RED

---

## 📦 [Módulos](./modules/)

Documentação específica de cada módulo/componente do projeto.

- **[webapp/](./modules/webapp/)** - Aplicação Dash principal
  - Sistema de badges demo
  - Componentes reutilizáveis

---

## 🚀 Início Rápido

### Para Novos Desenvolvedores

1. Leia **CLAUDE.md** na raiz (depois mover para `architecture/`)
2. Configure ambiente seguindo instruções
3. Veja **[Guia ZPP](./guides/zpp-processing.md)** se for trabalhar com processamento

### Para Contribuir com Melhorias

1. Verifique **[Dívida Técnica](./technical-debt/)** para itens priorizados
2. Escolha um item de **Alta** ou **Média** prioridade
3. Implemente e atualize o status no README

---

## 📝 Convenções

### Onde Colocar Documentação

| Tipo de Doc | Onde | Exemplo |
|-------------|------|---------|
| Procedimentos operacionais | `docs/` | Calibração de equipamentos |
| Arquitetura/Design | `.dev-docs/architecture/` | Estrutura da webapp |
| Débito técnico | `.dev-docs/technical-debt/` | Melhorias ZPP |
| Guias desenvolvimento | `.dev-docs/guides/` | Como processar ZPP |
| Planos/Roadmaps | `.dev-docs/plans/` | Sistema de triagem |

### Nomenclatura

- `README.md` - Índice da seção
- `nome-modulo-improvements.md` - Débitos técnicos
- `como-fazer-algo.md` - Guias práticos

---

## 🔄 Manutenção

Atualize esta documentação quando:

- ✅ Identificar novo débito técnico
- ✅ Resolver débito existente
- ✅ Mudança arquitetural significativa
- ✅ Novo guia de desenvolvimento necessário

---

**Criado em**: 2026-01-28
**Mantido por**: Equipe de Desenvolvimento
