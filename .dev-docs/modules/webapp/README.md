# 🌐 Webapp - Aplicação Dash

Documentação específica do módulo webapp (aplicação Dash principal para monitoramento industrial).

---

## 📋 Conteúdo

*(Arquivos a serem movidos aqui)*

- `demo-badges-overview.md` ← **MOVER** `webapp/DEMO_BADGES_README.md`
- `demo-badges-guide.md` ← **MOVER** `webapp/DEMO_BADGES_GUIDE.md`

---

## 📝 Tópicos Principais

### 1. Sistema de Badges Demo

Documentação sobre badges que indicam dados de demonstração vs produção.

- **Overview**: Visão geral do sistema
- **Guide**: Guia de uso e implementação

### 2. Componentes Reutilizáveis *(futuro)*

- Cards de KPI
- Gráficos
- Headers e filtros
- Sidebars

### 3. Sistema de Permissões *(futuro)*

- Controle de acesso matricial
- Níveis e perfis
- Rotas protegidas

### 4. Callbacks e Stores *(futuro)*

- Padrões de callbacks
- Gerenciamento de estado
- Stores compartilhados

---

## 🏗️ Estrutura do Módulo

```
webapp/
├── src/
│   ├── app.py                    # Inicialização
│   ├── index.py                  # Roteamento
│   ├── callbacks.py              # Registro de callbacks
│   ├── callbacks_registers/      # Callbacks modulares
│   ├── components/               # Componentes reutilizáveis
│   ├── config/                   # Configurações
│   ├── database/                 # MongoDB
│   ├── pages/                    # Páginas por domínio
│   └── utils/                    # Utilitários
├── assets/                       # CSS, imagens
└── run_local.py                  # Entrypoint desenvolvimento
```

---

## 📚 Links Úteis

- **Arquitetura Completa**: [../../architecture/webapp-architecture-ptbr.md](../../architecture/webapp-architecture-ptbr.md)
- **Guias**: [../../guides/](../../guides/)

---

**Criado em**: 2026-01-28
