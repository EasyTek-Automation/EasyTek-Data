# Módulo Workflow - Sistema CRUD de Gestão de Pendências

**Status:** ✅ Completo e Estável
**Data:** 10 de Fevereiro de 2026
**Rota Principal:** `/workflow/dashboard`

---

## 📋 Visão Geral

Sistema completo de gestão de pendências (CRUD) com controle de acesso baseado em perfil e nível, rastreabilidade total de mudanças, e interface moderna com histórico expansível.

### Principais Funcionalidades

- ✅ **Criar Pendências** (apenas nível 3/admin)
- ✅ **Editar Pendências** (responsável ou nível 3)
- ✅ **Visualizar Histórico** (todos os usuários)
- ✅ **Rastreabilidade Completa** (quem, quando, o quê, por quê)
- ✅ **Controle de Acesso RBAC** (nível + perfil/departamento)
- ✅ **Observações Contextuais** (justificativa de mudanças)

---

## 🏗️ Arquitetura

### Estrutura de Arquivos

```
webapp/src/
├── pages/workflow/
│   └── dashboard.py              # Dashboard principal com tabela expansível
├── components/workflow/
│   ├── create_modal.py           # Modal de criação de pendências
│   └── edit_modal.py             # Modal de edição com observações
├── callbacks_registers/
│   ├── workflow_callbacks.py     # Callbacks de visualização e histórico
│   ├── workflow_create_callbacks.py  # Callbacks de criação
│   └── workflow_edit_callbacks.py    # Callbacks de edição
├── utils/
│   └── workflow_csv.py           # Funções de manipulação CSV
├── data/
│   ├── workflow_pendencias.csv   # Dados de pendências
│   └── workflow_historico.csv    # Dados de histórico
└── scripts/
    ├── generate_workflow_csv.py  # Gerador de dados fictícios
    └── update_workflow_csv.py    # Migração de schema CSV
```

---

## 📊 Estrutura de Dados

### workflow_pendencias.csv

| Campo                 | Tipo      | Descrição                                    |
|-----------------------|-----------|----------------------------------------------|
| `id`                  | String    | PEND-XXX (gerado automaticamente)            |
| `descricao`           | String    | Descrição da pendência                       |
| `responsavel`         | String    | Username do responsável (FK: usuarios)       |
| `status`              | Enum      | Pendente, Em Andamento, Bloqueado, Concluído |
| `data_criacao`        | Timestamp | Data/hora de criação                         |
| `ultima_atualizacao`  | Timestamp | Data/hora da última modificação              |
| `criado_por`          | String    | Username do criador                          |
| `criado_por_perfil`   | String    | Perfil/departamento do criador               |
| `ultima_edicao_por`   | String    | Username da última edição                    |
| `ultima_edicao_data`  | Timestamp | Data/hora da última edição                   |

### workflow_historico.csv

| Campo          | Tipo      | Descrição                                        |
|----------------|-----------|--------------------------------------------------|
| `pendencia_id` | String    | FK para workflow_pendencias.id                   |
| `descricao`    | String    | Descrição do evento (inclui observações)         |
| `data`         | Timestamp | Data/hora do evento                              |
| `responsavel`  | String    | Responsável na época do evento (snapshot)        |
| `tipo_evento`  | Enum      | criacao, status_mudanca, responsavel_mudanca, etc|
| `editado_por`  | String    | Username de quem executou a ação                 |

**Tipos de Evento:**
- `criacao`: Pendência foi criada
- `status_mudanca`: Status foi alterado
- `responsavel_mudanca`: Responsável foi alterado
- `edicao_descricao`: Descrição foi editada
- `atualizacao_manual`: Atualização manual do histórico

---

## 🔐 Controle de Acesso (RBAC)

### Criar Pendência

**Quem:** Apenas nível 3 (Admin)

**Regras:**
- ✅ Admin pode criar para seu departamento
- ✅ Admin TI (`perfil="admin"`) pode criar para qualquer departamento
- ❌ Níveis 1-2 não podem criar

**Validações:**
```python
if user.level != 3:
    return "PERMISSÃO NEGADA"

if user.perfil != "admin" and responsavel_perfil != user.perfil:
    return "PERMISSÃO NEGADA: Só pode atribuir para seu departamento"
```

### Editar Pendência

**Quem:** Responsável atual OU nível 3

**Regras:**
- ✅ Responsável pode editar sua própria pendência
- ✅ Qualquer nível 3 pode editar qualquer pendência
- ✅ Ao mudar responsável, validar departamento (exceto admin TI)
- ❌ Outros usuários não podem editar

**Validações:**
```python
if user.username != pendencia.responsavel and user.level != 3:
    return "PERMISSÃO NEGADA"

if novo_responsavel and user.perfil != "admin":
    if novo_responsavel_perfil != user.perfil:
        return "PERMISSÃO NEGADA"
```

### Visualizar

**Quem:** Todos os usuários (nível 1+, todos os perfis)

---

## 💡 Funcionalidades Implementadas

### 1. Criação de Pendências

**Modal:** `create_modal.py`

**Campos:**
- Descrição (textarea, obrigatório)
- Responsável (dropdown dinâmico filtrado por departamento)
- Status inicial (dropdown: Pendente, Em Andamento)

**Fluxo:**
1. Admin nível 3 clica "Nova Pendência"
2. Modal abre com dropdown filtrado por departamento
3. Preenche formulário e salva
4. Validações RBAC no servidor
5. Gera ID sequencial (PEND-XXX)
6. Salva em CSV com metadata completa
7. Cria entrada no histórico: "Pendência criada"
8. Modal fecha automaticamente
9. Banner de sucesso aparece no topo (7 segundos)

### 2. Edição de Pendências

**Modal:** `edit_modal.py`

**Campos:**
- ID (read-only, visual)
- Descrição (textarea, editável)
- Responsável (dropdown dinâmico)
- Status (dropdown: Pendente, Em Andamento, Bloqueado, Concluído)
- **Observações** (textarea opcional, 3 linhas) ⭐ **NOVO**

**Fluxo:**
1. Usuário clica "Editar" na linha
2. Validação RBAC (responsável ou nível 3)
3. Modal abre com dados pré-preenchidos
4. Usuário altera campos e adiciona observações (opcional)
5. Clica "Salvar Alterações"
6. Callback detecta mudanças (descrição, responsável, status)
7. Para cada mudança, cria entrada no histórico com observações
8. Atualiza CSV e store de histórico
9. Modal fecha automaticamente
10. Banner de sucesso no topo (7 segundos)

**Exemplo de Histórico com Observações:**
```
Status alterado de 'Pendente' para 'Em Andamento' por admin.user: Aguardando peça do fornecedor
Responsável alterado de 'João Silva' para 'Maria Santos' por admin.user: João em férias
```

### 3. Visualização de Histórico

**Componente:** Timeline expansível com chevron

**Recursos:**
- Expansão/colapso por linha (pattern-matching callbacks)
- Timeline visual com bolinhas e linhas verticais
- Exibe TODAS as entradas de histórico para a pendência
- Inclui observações quando fornecidas
- Atualização automática após salvar edição
- Dados carregados do `store-historico` (performance otimizada)

---

## 🎨 Interface e UX

### Dashboard Principal

**Layout:**
- Header com título e botões (Nova, Atualizar, Exportar, Filtros)
- Container de alertas (banners de sucesso/erro)
- 4 Cards KPI (Total, Pendentes, Em Andamento, Concluídas)
- Painel de filtros colapsável
- Tabela responsiva com colunas:
  - Chevron (expansão)
  - ID
  - Descrição
  - Responsável
  - Status (badge colorido)
  - Criação
  - Atualização
  - Ações (botão Editar)

### Feedback Visual

**Banners de Sucesso:**
- Aparecem no topo da página (fora do modal)
- Duração: 7 segundos
- Auto-dismiss
- Cor verde com ícone check-circle

**Alertas de Erro:**
- Permanecem dentro do modal
- Dismissable manualmente
- Cores: vermelho (erro), amarelo (warning)
- Mantém modal aberto para correção

**Badges de Status:**
- Pendente: Amarelo (warning)
- Em Andamento: Azul (primary)
- Bloqueado: Vermelho (danger)
- Concluído: Verde (success)

---

## 🐛 Bugs Corrigidos (10/02/2026)

### 1. Parse de Timestamps com Microsegundos

**Problema:**
```
ValueError: unconverted data remains when parsing with format "%Y-%m-%dT%H:%M:%S": ".524300"
```

**Causa:** Novas entradas criadas com `datetime.now()` incluem microsegundos, mas parse não esperava.

**Solução:**
```python
# Antes
df['data'] = pd.to_datetime(df['data'])

# Depois
df['data'] = pd.to_datetime(df['data'], format='mixed')
```

**Arquivos Corrigidos:**
- `workflow_callbacks.py` (linha 148)
- `dashboard.py` (linhas 41-43)
- `workflow_csv.py` (linhas 22-25, 38)

### 2. Modal de Edição Reabrindo

**Problema:** Modal reabre automaticamente após salvar ou clicar em "Atualizar".

**Causa:** Callback de toggle detecta recriação dos botões quando tabela recarrega.

**Solução:**
```python
# Verificar cliques válidos
if "btn-edit-pend" in trigger_id:
    if not any(clicks for clicks in edit_clicks if clicks):
        raise PreventUpdate
```

**Arquivo:** `workflow_edit_callbacks.py` (linhas 57-60)

### 3. Histórico Não Atualizando

**Problema:** Após salvar edição, precisava clicar "Atualizar" para ver novas entradas no histórico.

**Causa:** Store de histórico não era atualizado junto com store de pendências.

**Solução:**
```python
# Adicionar Output store-historico
Output("store-historico", "data", allow_duplicate=True)

# Retornar histórico atualizado
df_pend, df_hist = carregar_dados_csv()
return (..., df_hist.to_dict('records'))
```

**Arquivos:** `workflow_edit_callbacks.py`, `workflow_create_callbacks.py`

---

## 🔧 Configuração e Uso

### Requisitos

- MongoDB com collection `usuarios` (validação de responsáveis)
- Estrutura de diretórios `webapp/src/data/`
- Permissões de escrita em CSVs

### Inicialização

```bash
# Gerar dados de exemplo
cd webapp/scripts
python generate_workflow_csv.py

# Atualizar schema (se migrando de versão anterior)
python update_workflow_csv.py
```

### Acesso às Rotas

```python
# Definido em config/access_control.py
ROUTE_ACCESS = {
    '/workflow/dashboard': {
        'min_level': 1,
        'perfis': [],
        'shared': True
    }
}
```

---

## 📈 Próximos Passos (Fase 2)

### Migração para MongoDB

**Benefícios:**
- Performance em grandes volumes
- Queries complexas
- Relacionamentos mais robustos
- Transações ACID

**Collections Planejadas:**
```javascript
// workflow_pendencias
{
  _id: ObjectId,
  id: "PEND-001",  // Mantém formato legível
  descricao: String,
  responsavel: String,  // FK: usuarios.username
  status: String,
  data_criacao: ISODate,
  ultima_atualizacao: ISODate,
  criado_por: String,
  criado_por_perfil: String,
  ultima_edicao_por: String,
  ultima_edicao_data: ISODate
}

// workflow_historico
{
  _id: ObjectId,
  pendencia_id: String,  // FK: workflow_pendencias.id
  descricao: String,
  data: ISODate,
  responsavel: String,
  tipo_evento: String,
  editado_por: String
}
```

### Funcionalidades Futuras

- [ ] Notificações por email ao atribuir responsável
- [ ] Anexos em pendências (upload de arquivos)
- [ ] Comentários (chat thread por pendência)
- [ ] Dashboard de métricas (tempo médio, taxa de conclusão)
- [ ] Filtros avançados (por período, responsável, status)
- [ ] Exportação para Excel/PDF
- [ ] Tags/categorias de pendências
- [ ] Prioridades (Baixa, Média, Alta, Urgente)
- [ ] Lembretes automáticos (pendências atrasadas)

---

## 📚 Referências

### Arquivos Relacionados

- **Plano Original:** `.dev-docs/plans/workflow-dashboard-pendencias.md`
- **Controle de Acesso:** `webapp/src/config/access_control.py`
- **Conexão MongoDB:** `webapp/src/database/connection.py`

### Padrões Seguidos

- **RBAC:** Sistema de controle de acesso de 2 dimensões (nível + perfil)
- **Pattern-Matching Callbacks:** Para botões dinâmicos (editar, expandir)
- **Stores:** Cache client-side para performance
- **Validação em 4 Camadas:** UI, Callback, RBAC, Data
- **Rastreabilidade:** Audit trail completo de mudanças

---

## 👥 Contribuidores

- **Desenvolvimento:** Claude Sonnet 4.5
- **Validação e Testes:** Equipe AMG_Data

---

**Última Atualização:** 10 de Fevereiro de 2026
**Versão:** 1.0.0 (CSV-based)
