# 📦 Módulos do Projeto

Documentação específica de cada módulo/componente do sistema AMG_Data.

---

## 📂 Estrutura

```
modules/
├── webapp/              # Aplicação Dash principal
├── event-gateway/       # (futuro) Gateway MQTT
└── scripts/             # (futuro) Scripts de processamento
```

---

## 📋 Módulos Documentados

### 🌐 [Webapp](./webapp/)

Aplicação Dash principal com interface web para monitoramento industrial.

**Conteúdo**:
- Sistema de badges demo
- Componentes reutilizáveis
- Configurações específicas

---

## 📝 O que Colocar Aqui

### ✅ Incluir

- **Documentação específica de módulo**
  - APIs internas
  - Componentes e suas props
  - Configurações do módulo

- **Guias específicos**
  - Como adicionar features ao módulo
  - Padrões internos do módulo
  - HOWTOs específicos

- **Referências internas**
  - Estrutura de pastas do módulo
  - Dependências específicas
  - Convenções de código

### ❌ Não Incluir

- Arquitetura geral → `architecture/`
- Guias que atravessam módulos → `guides/`
- Operações/Deploy → `operations/`

---

## 🆕 Adicionar Novo Módulo

### 1. Criar Estrutura

```bash
mkdir -p .dev-docs/modules/nome-modulo
```

### 2. Criar README

```markdown
# [Nome do Módulo]

Descrição breve do módulo.

## 📁 Estrutura

## 🚀 Como Usar

## 📝 APIs / Componentes

## ⚙️ Configuração
```

### 3. Adicionar ao Índice

Edite este README para incluir o novo módulo.

---

**Criado em**: 2026-01-28
