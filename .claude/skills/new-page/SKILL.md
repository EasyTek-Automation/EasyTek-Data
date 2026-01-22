---
name: new-page
description: Cria uma nova página no aplicativo Dash do AMG_Data seguindo os padrões do projeto. Use quando precisar adicionar uma nova rota/página.
argument-hint: [caminho-da-rota nome-da-pagina]
allowed-tools: Read, Write, Edit, Grep, Glob
---

# Criador de Nova Página - AMG_Data

Crie uma nova página no aplicativo Dash: **$ARGUMENTS**

## Padrão de Argumentos

Formato esperado: `/caminho/da/rota "Nome da Página"`

Exemplo: `/utilities/water "Monitoramento de Água"`

## Checklist de Criação

### 1. Criar Arquivo de Layout

**Local:** `webapp/src/pages/[categoria]/[nome_arquivo].py`

Categorias disponíveis:
- `admin/` - Administração e usuários
- `auth/` - Autenticação
- `dashboards/` - Dashboards principais
- `energy/` - Energia
- `production/` - Produção
- `maintenance/` - Manutenção
- `supervision/` - Supervisão
- `reports/` - Relatórios
- `common/` - Páginas compartilhadas

**Template básico:**

```python
"""
Página de [Nome da Página]
"""
import dash_bootstrap_components as dbc
from dash import html, dcc
from src.components.demo_badge import demo_data_badge
from src.config.demo_data_config import should_show_demo_badge

def layout():
    """Layout para a página de [nome da página]"""

    # Badge de demo se configurado
    demo_badge = demo_data_badge() if should_show_demo_badge(page_path="/caminho/da/rota") else None

    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H1("[Nome da Página]", className="mb-2"),
                    demo_badge if demo_badge else None,
                ], className="mb-4"),

                # Seu conteúdo aqui
                dbc.Card([
                    dbc.CardBody([
                        html.P("Conteúdo da página")
                    ])
                ]),

            ], width=12)
        ])
    ], fluid=True, className="p-4")
```

### 2. Registrar Rota

**Arquivo:** `webapp/src/index.py`

Adicione ao dicionário `ROUTES`:

```python
ROUTES = {
    # ... rotas existentes ...
    '/seu/caminho': pages.categoria.arquivo.layout,
}
```

### 3. Configurar Controle de Acesso

**Arquivo:** `webapp/src/config/access_control.py`

Adicione ao dicionário `ROUTE_ACCESS`:

```python
ROUTE_ACCESS = {
    # ... rotas existentes ...
    '/seu/caminho': {
        'min_level': 1,  # 1=básico, 2=avançado, 3=admin
        'perfis': ['producao', 'admin'],  # Perfis permitidos
        'shared': False,  # True = todos os perfis (se nível ok)
        'display_name': 'Nome da Página'
    },
}
```

**Perfis disponíveis:**
- `admin` - Administradores
- `producao` - Produção
- `manutencao` - Manutenção
- `qualidade` - Qualidade
- `utilidades` - Utilidades
- `meio_ambiente` - Meio Ambiente
- `seguranca` - Segurança
- `engenharias` - Engenharias

### 4. Adicionar/Habilitar Link no Header

**Arquivo:** `webapp/src/header.py`

**Verifique primeiro se o link já existe:**
1. Procure pelo caminho da rota no arquivo `header.py` (ex: `/utilities/water`)
2. Se o link existir mas estiver comentado ou desabilitado, habilite-o
3. Se não existir, adicione o link ao menu apropriado

**Se precisar criar novo link no menu, adicione ao `MENU_ACCESS`:**

```python
MENU_ACCESS = {
    # ... menus existentes ...
    'nome_menu': {
        'min_level': 1,
        'perfis': ['producao', 'admin'],
        'shared': False
    }
}
```

**Exemplo de link no mega menu (Utilidades):**
```python
dbc.DropdownMenuItem(
    "💧 Água",
    href="/utilities/water",
    className="dropdown-item-custom"
),
```

### 5. Criar Sidebar Customizada (Opcional)

**Local:** `webapp/src/components/sidebars/[nome]_sidebar.py`

```python
"""
Sidebar para [Nome da Página]
"""
import dash_bootstrap_components as dbc
from dash import html

def create_[nome]_sidebar_content():
    return dbc.Container([
        html.H5("Filtros", className="mb-3"),

        # Seus controles aqui

    ], fluid=True, className="p-3")
```

Depois, registre em `webapp/src/sidebar.py`:

```python
def get_sidebar_content_for_page(pathname):
    # ... código existente ...
    elif pathname == '/seu/caminho':
        from components.sidebars.nome_sidebar import create_nome_sidebar_content
        return create_nome_sidebar_content()
```

### 6. Criar Header Filters (Opcional)

**Local:** `webapp/src/components/headers/[nome]_filters.py`

```python
"""
Filtros de header para [Nome da Página]
"""
import dash_bootstrap_components as dbc
from dash import html, dcc

def create_[nome]_filters():
    return html.Div([
        # Seus filtros aqui
    ], className="d-flex align-items-center gap-2")
```

Registre em `webapp/src/header.py`:

```python
def get_filters_for_page(pathname):
    # ... código existente ...
    elif pathname == '/seu/caminho':
        from components.headers.nome_filters import create_nome_filters
        return create_nome_filters()
```

### 7. Criar Callbacks (Se Necessário)

**Local:** `webapp/src/callbacks_registers/[nome]_callbacks.py`

```python
"""
Callbacks para [Nome da Página]
"""
from dash import Input, Output, State

def register_[nome]_callbacks(app):
    @app.callback(
        Output('[componente]-output', 'children'),
        Input('[componente]-input', 'value')
    )
    def update_[nome](value):
        # Sua lógica aqui
        return f"Valor: {value}"
```

Registre em `webapp/src/callbacks.py`:

```python
from callbacks_registers.[nome]_callbacks import register_[nome]_callbacks

def register_callbacks(app):
    # ... registros existentes ...
    register_[nome]_callbacks(app)
```

### 8. Configurar Demo Badge (Obrigatório para Dados de Demonstração)

**Arquivo:** `webapp/src/config/demo_data_config.py`

Se a página exibe dados de demonstração/simulados, adicione ao dicionário `DEMO_PAGES`:

```python
DEMO_PAGES = {
    # ... páginas existentes ...
    "/seu/caminho": True,  # Ativa badge de demo para esta página
}
```

**Importações necessárias no layout da página:**

```python
from src.components.demo_badge import demo_data_badge
from src.config.demo_data_config import should_show_demo_badge

# No layout:
demo_badge = demo_data_badge() if should_show_demo_badge(page_path="/seu/caminho") else None
```

**Funções disponíveis:**
- `demo_data_badge(size="sm")` - Badge básico
- `demo_data_tooltip_badge(tooltip_id, tooltip_text, size)` - Badge com tooltip
- `with_demo_badge(component, position)` - Envolve componente com badge

## Exemplo Completo

Para criar `/utilities/water` "Monitoramento de Água":

1. **Criar layout:** `webapp/src/pages/energy/water.py`
2. **Registrar rota:** `ROUTES['/utilities/water'] = pages.energy.water.layout` em `index.py`
3. **Configurar acesso:** `ROUTE_ACCESS['/utilities/water'] = {...}` em `access_control.py`
4. **Habilitar link:** Verificar e habilitar/criar link no `header.py`
5. **Criar sidebar (opcional):** `webapp/src/components/sidebars/water_sidebar.py` e registrar em `sidebar.py`
6. **Configurar demo badge:** Adicionar `/utilities/water` ao `DEMO_PAGES` em `demo_data_config.py`

## Notas Importantes

- Sempre siga a estrutura de pastas existente
- Use Bootstrap components (dbc) para consistência
- Mantenha o padrão de nomenclatura snake_case
- **Importações corretas:** Use `demo_data_badge` (não `create_demo_badge`)
- Teste com diferentes perfis de usuário
- Verifique se a página carrega corretamente após criar
- Adicione ao CLAUDE.md se a página estiver completa

## Troubleshooting Comum

### Página não carrega ao clicar no menu

**Possíveis causas:**
1. **Erro de importação** - Verifique se todas as importações estão corretas
   - ✅ Correto: `from src.components.demo_badge import demo_data_badge`
   - ❌ Errado: `from src.components.demo_badge import create_demo_badge`

2. **Rota não registrada** - Confirme que a rota está em `ROUTES` no `index.py`
   ```python
   "/utilities/gas": gas.layout,  # Correto
   ```

3. **Erro no callback** - Se a página tem callbacks, verifique se foram registrados corretamente em `callbacks.py`

4. **Erro de sintaxe** - Verifique o console do navegador e os logs do servidor para mensagens de erro

### Badge de demo não aparece

**Verifique:**
1. Importações corretas: `demo_data_badge` e `should_show_demo_badge`
2. Rota adicionada ao `DEMO_PAGES` em `demo_data_config.py`
3. `ENABLE_DEMO_BADGES = True` no `demo_data_config.py`
4. Path correto no `should_show_demo_badge(page_path="/sua/rota")`
