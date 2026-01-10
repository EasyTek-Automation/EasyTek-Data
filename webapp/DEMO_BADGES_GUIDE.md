# Guia de Uso - Badges de Dados de Demonstração

Este documento explica como usar o sistema de badges para indicar quando os dados exibidos são fictícios/demonstração.

## 📋 Visão Geral

O sistema de badges permite:
- ✅ Indicar claramente quando dados são fictícios
- ✅ Fácil ativação/desativação por página ou componente
- ✅ Aplicação consistente em toda a aplicação
- ✅ Configuração centralizada

## 🎯 Configuração

### Ativar/Desativar Globalmente

Edite `webapp/src/config/demo_data_config.py`:

```python
# Desativar TODOS os badges
ENABLE_DEMO_BADGES = False

# Ativar TODOS os badges
ENABLE_DEMO_BADGES = True
```

### Ativar/Desativar por Página

```python
DEMO_PAGES = {
    "/production/oee": True,    # Badge ativo
    "/energy/overview": False,  # Badge desativado
}
```

### Ativar/Desativar por Componente

```python
DEMO_COMPONENTS = {
    "graphs": {
        "oee_graph": True,      # Badge ativo
        "energy_graph": False,  # Badge desativado
    }
}
```

## 🚀 Exemplos de Uso

### 1. Badge Simples em Card Header

```python
from dash import html
import dash_bootstrap_components as dbc
from src.utils.demo_helpers import add_demo_badge_to_card_header

# Uso básico
card = dbc.Card([
    dbc.CardHeader(
        add_demo_badge_to_card_header(
            "Consumo de Energia",
            page_path="/energy/overview"
        )
    ),
    dbc.CardBody([
        html.H3("1.234 kWh")
    ])
])
```

### 2. Card Completo com Badge Automático

```python
from src.utils.demo_helpers import create_demo_card

# Cria card com badge automático
card = create_demo_card(
    title="OEE Total",
    content=html.H2("85.5%"),
    page_path="/production/oee",
    color="primary"
)
```

### 3. Gráfico com Badge

```python
from dash import dcc
import plotly.graph_objects as go
from src.utils.demo_helpers import add_demo_badge_to_graph

# Criar figura
fig = go.Figure(data=[...])

# Criar gráfico
graph = dcc.Graph(figure=fig, id="my-graph")

# Adicionar badge
graph_with_badge = add_demo_badge_to_graph(
    graph,
    page_path="/energy/se03",
    position="top-right"  # Opções: top-right, top-left, bottom-right, bottom-left
)
```

### 4. Card com Gráfico (Solução Completa)

```python
import plotly.express as px
from src.utils.demo_helpers import create_demo_graph_card

# Criar figura
df = pd.DataFrame({...})
fig = px.line(df, x='date', y='value')

# Criar card completo
graph_card = create_demo_graph_card(
    title="Consumo por Hora",
    figure=fig,
    page_path="/energy/overview",
    component_name="consumption_graph",
    graph_id="consumption-graph-id"
)
```

### 5. Alerta de Página Inteira

```python
from dash import html
from src.utils.demo_helpers import add_page_demo_warning

# No layout da página
layout = html.Div([
    add_page_demo_warning("/production/oee"),

    # Resto do conteúdo
    html.H1("Dashboard OEE"),
    # ...
])

# Com mensagem customizada
layout = html.Div([
    add_page_demo_warning(
        "/production/oee",
        message="Esta página está em fase de testes com dados simulados."
    ),
    # ...
])
```

### 6. Badge em Tabela

```python
from src.utils.demo_helpers import add_demo_badge_to_table_header
import dash_table

columns = [
    {"name": "Data", "id": "date"},
    {"name": "Valor", "id": "value"}
]

# Adicionar badge ao header
cols, demo_header = add_demo_badge_to_table_header(
    columns,
    page_path="/maintenance/alarms"
)

# Layout com tabela
layout = html.Div([
    demo_header,  # Badge acima da tabela
    dash_table.DataTable(
        columns=cols,
        data=[...]
    )
])
```

### 7. Múltiplos Componentes em uma Página

```python
from src.utils.demo_helpers import wrap_components_with_demo_info

# Seus componentes
components = [
    dbc.Row([graph1, graph2]),
    dbc.Row([table1]),
    dbc.Row([card1, card2, card3])
]

# Adiciona alerta no topo automaticamente
layout_components = wrap_components_with_demo_info(
    components,
    page_path="/production/oee"
)

layout = html.Div(layout_components)
```

### 8. Badge com Tooltip

```python
from src.components.demo_badge import demo_data_tooltip_badge

# Badge com tooltip explicativo
badge = demo_data_tooltip_badge(
    tooltip_id="graph-demo-tooltip",
    tooltip_text="Estes dados são simulados para demonstração",
    size="sm"
)

# Usar no header
header = dbc.CardHeader([
    html.H5("Meu Gráfico"),
    badge
])
```

## 🎨 Tamanhos de Badge Disponíveis

```python
# Pequeno (padrão)
demo_data_badge(size="sm")

# Médio
demo_data_badge(size="md")

# Grande
demo_data_badge(size="lg")
```

## 📍 Posições de Badge em Gráficos

```python
# Canto superior direito (padrão)
with_demo_badge(graph, position="top-right")

# Canto superior esquerdo
with_demo_badge(graph, position="top-left")

# Canto inferior direito
with_demo_badge(graph, position="bottom-right")

# Canto inferior esquerdo
with_demo_badge(graph, position="bottom-left")
```

## 🔧 Exemplo Completo de Página

```python
from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.express as px
from src.utils.demo_helpers import (
    add_page_demo_warning,
    create_demo_graph_card,
    create_demo_card
)

def layout():
    # Dados fictícios
    df = pd.DataFrame({...})
    fig1 = px.line(df, x='date', y='value')
    fig2 = px.bar(df, x='category', y='count')

    return html.Div([
        # Alerta no topo da página
        add_page_demo_warning("/production/oee"),

        # Título
        html.H1("Dashboard de Produção", className="mb-4"),

        # Row com KPI cards
        dbc.Row([
            dbc.Col(
                create_demo_card(
                    title="OEE",
                    content=html.H2("85.5%"),
                    page_path="/production/oee"
                ),
                width=4
            ),
            dbc.Col(
                create_demo_card(
                    title="Disponibilidade",
                    content=html.H2("92.0%"),
                    page_path="/production/oee"
                ),
                width=4
            ),
            dbc.Col(
                create_demo_card(
                    title="Performance",
                    content=html.H2("88.5%"),
                    page_path="/production/oee"
                ),
                width=4
            ),
        ], className="mb-4"),

        # Row com gráficos
        dbc.Row([
            dbc.Col(
                create_demo_graph_card(
                    title="Tendência OEE",
                    figure=fig1,
                    page_path="/production/oee",
                    graph_id="oee-trend"
                ),
                width=6
            ),
            dbc.Col(
                create_demo_graph_card(
                    title="Performance por Turno",
                    figure=fig2,
                    page_path="/production/oee",
                    graph_id="shift-performance"
                ),
                width=6
            ),
        ])
    ])
```

## ✅ Checklist para Implementação

Ao adicionar badges em uma nova página:

1. ✅ Adicionar a página em `DEMO_PAGES` no arquivo `config/demo_data_config.py`
2. ✅ Importar as funções necessárias de `utils.demo_helpers`
3. ✅ Aplicar badge nos componentes usando as funções helper
4. ✅ Testar a visualização com `ENABLE_DEMO_BADGES = True`
5. ✅ Quando os dados reais forem implementados, mudar para `False` na configuração

## 🎯 Boas Práticas

1. **Use as funções helper** em vez de criar badges manualmente
2. **Configure por página** para fácil gerenciamento
3. **Mantenha consistência** no tamanho e posição dos badges
4. **Atualize a configuração** assim que dados reais estiverem disponíveis
5. **Use tooltips** quando precisar de informações adicionais

## 🔄 Migração Gradual para Dados Reais

Quando uma página passar a usar dados reais:

```python
# Em config/demo_data_config.py
DEMO_PAGES = {
    "/production/oee": False,  # Mudou para dados reais ✅
    "/energy/overview": True,  # Ainda com dados fictícios
}
```

Os badges desaparecerão automaticamente da página `/production/oee`.
