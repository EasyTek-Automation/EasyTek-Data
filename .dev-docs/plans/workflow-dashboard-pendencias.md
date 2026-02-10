# Plano: Dashboard de Pendências (Workflow)

## Contexto

O usuário solicitou a criação de um novo recurso no sistema AMG_Data: um Dashboard de Pendências acessível através de um novo menu "Workflow" na barra de navegação. Este dashboard deve permitir visualizar pendências em formato de tabela, onde cada linha pode ser expandida para revelar o histórico detalhado dessa pendência.

**Motivação**: Criar uma interface intuitiva para acompanhamento de tarefas e pendências do sistema, permitindo visualizar tanto o status atual quanto o histórico completo de cada item, facilitando a gestão e o acompanhamento de trabalhos.

**Abordagem**: Utilizar dados fictícios em CSV (simulação) para validar a UX e a interface antes de qualquer integração com banco de dados real. O sistema deve seguir os padrões arquiteturais já estabelecidos no projeto (Bootstrap components, pattern-matching callbacks, RBAC).

---

## Arquivos a Criar

### 1. Script Gerador de Dados
**`webapp/scripts/generate_workflow_csv.py`**
- Gera 50 pendências principais com IDs sequenciais (PEND-001 até PEND-050)
- Cada pendência possui 3-7 subpendências (histórico) distribuídas ao longo do tempo
- 5 responsáveis rotativos: João Silva, Maria Santos, Pedro Costa, Ana Oliveira, Carlos Souza
- 4 status possíveis: Pendente, Em Andamento, Bloqueado, Concluído
- Campos pendências: id, descricao, responsavel, status, data_criacao, ultima_atualizacao
- Campos histórico: pendencia_id, descricao, data, responsavel
- Saída: `webapp/src/data/workflow_pendencias.csv` e `webapp/src/data/workflow_historico.csv`

### 2. Módulo de Páginas
**`webapp/src/pages/workflow/__init__.py`**
- Arquivo de inicialização do módulo workflow
- Exporta o módulo dashboard

**`webapp/src/pages/workflow/dashboard.py`**
- Layout principal da página com:
  - Header (título "Dashboard de Pendências" + botões Atualizar/Exportar/Filtros)
  - 4 cards KPI (Total, Pendentes, Em Andamento, Concluídas)
  - Painel de filtros colapsável (responsável, status, busca por texto)
  - Tabela Bootstrap expansível com 50 pendências
  - Estrutura de linhas: cada pendência tem 2 `<tr>` (principal + collapse com histórico)
  - Botão chevron (>) em cada linha que rotaciona para (v) quando expandido
  - dcc.Store para cachear dados de histórico (evitar recarregar CSV)
  - Timeline visual do histórico quando linha expandida

### 3. Callbacks
**`webapp/src/callbacks_registers/workflow_callbacks.py`**
- **Callback 1**: Toggle do painel de filtros (Input: btn-toggle, Output: collapse-filters)
- **Callback 2**: Expansão/colapso individual de linhas com pattern-matching (MATCH)
  - Input: botão expandir com ID dinâmico `{"type": "btn-expand", "index": MATCH}`
  - Outputs: estado collapse, classe do chevron, conteúdo do histórico
  - Carrega histórico dinamicamente apenas quando expandido
- **Callback 3**: Aplicar filtros na tabela
  - Inputs: responsável, status (multi-select), busca por texto
  - Filtra DataFrame e reconstrói tabela
  - Fecha painel de filtros após aplicar
- **Callback 4**: Refresh de dados (recarrega CSVs)

---

## Arquivos a Modificar

### 1. Ícones
**`webapp/src/components/icons.py`**

Adicionar duas novas funções ao final do arquivo:
```python
def workflow_icon():
    """Ícone de workflow (diagrama-3 do Bootstrap Icons)"""
    # SVG bi-diagram-3

def checklist_icon():
    """Ícone de checklist (list-check do Bootstrap Icons)"""
    # SVG bi-list-check
```

### 2. Header (Menu)
**`webapp/src/header.py`**

**Linha ~44**: Adicionar imports
```python
from src.components.icons import (
    # ... existentes ...
    workflow_icon,
    checklist_icon,
)
```

**Linha ~370** (após config_dropdown, antes de "MONTAR NAVBAR"): Adicionar dropdown
```python
# 📋 WORKFLOW
workflow_dropdown = dbc.DropdownMenu(
    label=html.Div([
        html.Span(workflow_icon(), style={"marginRight": "8px"}),
        html.Span("Workflow", style={"fontWeight": "600"})
    ], className="d-flex align-items-center"),
    children=[
        html.Div([
            dbc.DropdownMenuItem(
                html.Div([
                    html.Span(checklist_icon(), style={"marginRight": "8px"}),
                    "Dashboard de Pendências"
                ], className="d-flex align-items-center"),
                href="/workflow/dashboard",
                active=(pathname == "/workflow/dashboard")
            ),

            dbc.DropdownMenuItem(divider=True),

            # Funcionalidades futuras (disabled)
            dbc.DropdownMenuItem(
                html.Div([
                    html.Span(html.I(className="bi bi-plus-circle me-2")),
                    "Criar Nova Pendência"
                ], className="d-flex align-items-center"),
                href="/workflow/create",
                disabled=True,
                style={"opacity": "0.5"}
            ),

            create_dropdown_footer()
        ], className="simple-dropdown-menu dropdown-menu-with-footer")
    ],
    nav=True, in_navbar=True,
    toggle_style={"display": "inline-flex", "alignItems": "center", "gap": "4px", "fontWeight": "600"}
)
```

**Linha ~422** (após `supervision_dropdown`, antes de `config_dropdown`): Adicionar ao nav_items
```python
if can_see_menu(user, "supervisorio"):
    nav_items.append(supervision_dropdown)
if can_see_menu(user, "workflow"):  # ← NOVO
    nav_items.append(workflow_dropdown)
if can_see_menu(user, "configuracoes"):
    nav_items.append(config_dropdown)
```

### 3. Roteamento
**`webapp/src/index.py`**

**Linha ~38** (após imports de maintenance): Adicionar import
```python
# Workflow
from src.pages.workflow import dashboard as workflow_dashboard
```

**Linha ~95** (após rotas de maintenance, antes de Supervisório): Adicionar rota
```python
# Workflow
"/workflow/dashboard": workflow_dashboard.layout,
```

### 4. Permissões
**`webapp/src/config/access_control.py`**

**Linha ~316** (após rotas de Utilities, antes de Supervisório): Adicionar em ROUTE_ACCESS
```python
# ========================================
# WORKFLOW
# ========================================
"/workflow/dashboard": {
    "shared": True,
    "min_level": 1,
    "description": "Dashboard de Pendências"
},
```

**Linha ~393** (após menu supervisorio): Adicionar em MENU_ACCESS
```python
# Menu Workflow
"workflow": {
    "shared": True,
    "min_level": 1,
    "description": "Menu Workflow"
},
```

### 5. Callbacks Centrais
**`webapp/src/callbacks.py`**

**Linha ~36** (após outros imports de callbacks): Adicionar import
```python
from src.callbacks_registers.workflow_callbacks import register_workflow_callbacks
```

**Linha ~112** (antes do final de `register_callbacks()`): Adicionar registro
```python
# Workflow callbacks
register_workflow_callbacks(app)
```

---

## Passo a Passo da Implementação

### Fase 1: Preparação de Dados
1. Criar diretório `webapp/src/data/` (se não existir)
2. Criar script `webapp/scripts/generate_workflow_csv.py` com lógica de geração
3. Executar script: `cd webapp && python scripts/generate_workflow_csv.py`
4. Verificar arquivos criados: `workflow_pendencias.csv` (50 registros) e `workflow_historico.csv` (~250-350 registros)

### Fase 2: Componentes Básicos
5. Adicionar `workflow_icon()` e `checklist_icon()` em `components/icons.py`
6. Criar diretório `webapp/src/pages/workflow/`
7. Criar `pages/workflow/__init__.py` (módulo vazio com export)

### Fase 3: Layout da Página
8. Criar `pages/workflow/dashboard.py` com:
   - Função `carregar_dados_csv()` para ler CSVs
   - Função `criar_cards_kpi()` para 4 cards de estatísticas
   - Função `criar_linha_pendencia()` para gerar linhas com botão expand
   - Função `criar_tabela_pendencias()` para montar tabela Bootstrap
   - Função `layout()` principal com estrutura completa

### Fase 4: Callbacks
9. Criar `callbacks_registers/workflow_callbacks.py` com:
   - Função `criar_conteudo_historico()` helper para timeline
   - Callback 1: Toggle filtros
   - Callback 2: Expand/collapse linha (pattern-matching MATCH)
   - Callback 3: Aplicar filtros
   - Callback 4: Refresh dados
   - Função `register_workflow_callbacks(app)` exportada

### Fase 5: Integração
10. Modificar `header.py`:
    - Adicionar imports dos ícones
    - Criar `workflow_dropdown` seguindo padrão
    - Adicionar ao `nav_items` com permissão
11. Modificar `index.py`:
    - Importar `workflow_dashboard`
    - Adicionar rota em `ROUTES`
12. Modificar `access_control.py`:
    - Adicionar `/workflow/dashboard` em `ROUTE_ACCESS`
    - Adicionar `workflow` em `MENU_ACCESS`
13. Modificar `callbacks.py`:
    - Importar `register_workflow_callbacks`
    - Chamar função de registro

### Fase 6: Testes
14. Iniciar aplicação: `cd webapp && python run_local.py`
15. Login no sistema
16. Verificar menu "Workflow" aparece no header
17. Clicar em "Dashboard de Pendências"
18. Validar:
    - Cards KPI exibem contagens corretas
    - Tabela mostra 50 pendências
    - Clicar em chevron expande linha
    - Histórico aparece em formato timeline
    - Chevron rotaciona visualmente
    - Recolher linha funciona
    - Filtros abrem/fecham
    - Aplicar filtros atualiza tabela
    - Botão refresh recarrega dados

---

## Padrões Técnicos Utilizados

### Pattern-Matching Callbacks
IDs dinâmicos para múltiplas linhas:
```python
{"type": "btn-expand", "index": 0}
{"type": "btn-expand", "index": 1}
# ...
```

Callback com MATCH (afeta apenas a linha clicada):
```python
@app.callback(
    Output({"type": "collapse-historico", "index": MATCH}, "is_open"),
    Input({"type": "btn-expand", "index": MATCH}, "n_clicks"),
    State({"type": "collapse-historico", "index": MATCH}, "is_open"),
)
```

### Componentes Bootstrap
- `dbc.Table` com `bordered=True, hover=True, responsive=True`
- `dbc.Collapse` para áreas expansíveis
- `dbc.Badge` para status coloridos
- `dbc.Card` para cards KPI e container de histórico
- `dbc.ButtonGroup` para grupo de botões de ação

### Estrutura de Tabela Expansível
Cada pendência = 2 linhas (`<tr>`):
1. **Linha principal**: botão chevron + dados da pendência
2. **Linha collapse**: `<td>` com `colSpan=7` contendo `dbc.Collapse`

### Timeline de Histórico
Layout flexbox horizontal com:
- Coluna esquerda: bolinha + linha vertical
- Coluna direita: descrição + responsável + data
- Última item sem linha vertical (terminador)

---

## Arquivos Críticos

1. **`webapp/src/pages/workflow/dashboard.py`** (~350 linhas)
   - Layout completo com tabela expansível, cards KPI, filtros

2. **`webapp/src/callbacks_registers/workflow_callbacks.py`** (~250 linhas)
   - Lógica de expansão/colapso com pattern-matching
   - Filtros dinâmicos de responsável, status e busca

3. **`webapp/scripts/generate_workflow_csv.py`** (~150 linhas)
   - Gera dados fictícios realistas para 50 pendências

4. **`webapp/src/header.py`** (modificar 3 locais)
   - Adicionar dropdown workflow ao mega menu

5. **`webapp/src/config/access_control.py`** (modificar 2 locais)
   - Configurar permissões RBAC

---

## Verificação da Implementação

### Checklist Funcional
- [ ] Menu "Workflow" visível no header (entre Supervisório e Configurações)
- [ ] Clicar em "Dashboard de Pendências" navega para `/workflow/dashboard`
- [ ] Página carrega sem erros no console
- [ ] 4 cards KPI mostram: Total (50), Pendentes, Em Andamento, Concluídas
- [ ] Tabela exibe 50 linhas de pendências
- [ ] Chevron (>) visível em cada linha
- [ ] Clicar no chevron expande a linha
- [ ] Histórico aparece em formato timeline (bolinha + linha + conteúdo)
- [ ] Chevron rotaciona para (v) quando expandido
- [ ] Clicar novamente recolhe a linha
- [ ] Chevron volta para (>)
- [ ] Badges de status com cores corretas (amarelo, azul, vermelho, verde)
- [ ] Botão "Filtros" abre painel colapsável
- [ ] Dropdown de responsável funciona
- [ ] Dropdown de status (multi-select) funciona
- [ ] Campo de busca funciona (ID e descrição)
- [ ] Botão "Aplicar" filtra a tabela
- [ ] Painel fecha após aplicar filtros
- [ ] Botão "Atualizar" recarrega dados dos CSVs
- [ ] Botão "Exportar" existe (callback opcional, não implementado)

### Checklist de Performance
- [ ] Tempo de carregamento inicial < 2s
- [ ] Expansão de linha < 200ms
- [ ] Aplicar filtros < 500ms
- [ ] Store de histórico evita recarregar CSV a cada expansão

### Checklist de Permissões
- [ ] Todos os perfis com nível 1+ podem acessar
- [ ] Menu aparece para usuários autorizados
- [ ] Rota protegida por RBAC

---

## Notas Importantes

1. **Dados Simulados**: Sistema usa CSVs para simular dados. Não há integração com MongoDB nesta fase.

2. **Expansão Individual**: Cada linha expande/colapsa independentemente usando pattern-matching callbacks.

3. **Performance**: Histórico é carregado em `dcc.Store` uma vez, evitando ler CSV a cada expansão.

4. **Filtros**: Implementados com pandas filtering no DataFrame antes de reconstruir a tabela.

5. **Extensibilidade**: Estrutura preparada para futuras funcionalidades (criar pendência, editar, exportar).

6. **Responsividade**: Layout usa Bootstrap grid system (responsivo por padrão).

7. **Padrão do Projeto**: Segue arquitetura existente (dbc.Table, pattern-matching, RBAC, modularização).
