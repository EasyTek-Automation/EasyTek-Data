"""
EXEMPLO PRÁTICO: Como aplicar badges de demonstração em uma página existente

Este arquivo demonstra como modificar uma página para incluir badges
indicando dados fictícios. Use este exemplo como referência.
"""

# ==============================================================================
# EXEMPLO 1: Página Simples com Cards KPI
# ==============================================================================

# ANTES - Sem badges
def layout_before():
    from dash import html
    import dash_bootstrap_components as dbc

    return html.Div([
        html.H1("Dashboard OEE"),

        dbc.Row([
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader("OEE Total"),
                    dbc.CardBody(html.H2("85.5%"))
                ]),
                width=4
            ),
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader("Disponibilidade"),
                    dbc.CardBody(html.H2("92.0%"))
                ]),
                width=4
            ),
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader("Performance"),
                    dbc.CardBody(html.H2("88.5%"))
                ]),
                width=4
            ),
        ])
    ])


# DEPOIS - Com badges (RECOMENDADO)
def layout_after():
    from dash import html
    import dash_bootstrap_components as dbc
    from src.utils.demo_helpers import add_page_demo_warning, create_demo_card

    return html.Div([
        # Alerta no topo da página
        add_page_demo_warning("/production/oee"),

        html.H1("Dashboard OEE"),

        dbc.Row([
            dbc.Col(
                create_demo_card(
                    title="OEE Total",
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
        ])
    ])


# ==============================================================================
# EXEMPLO 2: Página com Gráficos
# ==============================================================================

# ANTES - Sem badges
def graph_page_before():
    from dash import html, dcc
    import plotly.graph_objects as go
    import dash_bootstrap_components as dbc

    fig = go.Figure(data=[go.Scatter(x=[1, 2, 3], y=[4, 5, 6])])

    return html.Div([
        html.H1("Consumo de Energia"),

        dbc.Card([
            dbc.CardHeader("Consumo por Hora"),
            dbc.CardBody(
                dcc.Graph(figure=fig, id="consumption-graph")
            )
        ])
    ])


# DEPOIS - Com badges (RECOMENDADO)
def graph_page_after():
    from dash import html, dcc
    import plotly.graph_objects as go
    import dash_bootstrap_components as dbc
    from src.utils.demo_helpers import create_demo_graph_card, add_page_demo_warning

    fig = go.Figure(data=[go.Scatter(x=[1, 2, 3], y=[4, 5, 6])])

    return html.Div([
        # Alerta no topo
        add_page_demo_warning("/energy/overview"),

        html.H1("Consumo de Energia"),

        # Card com gráfico e badge automático
        create_demo_graph_card(
            title="Consumo por Hora",
            figure=fig,
            page_path="/energy/overview",
            graph_id="consumption-graph"
        )
    ])


# ==============================================================================
# EXEMPLO 3: Múltiplos Gráficos
# ==============================================================================

def multi_graph_page():
    from dash import html, dcc
    import plotly.graph_objects as go
    import dash_bootstrap_components as dbc
    from src.utils.demo_helpers import create_demo_graph_card, wrap_components_with_demo_info

    # Criar figuras
    fig1 = go.Figure(data=[go.Scatter(x=[1, 2, 3], y=[4, 5, 6])])
    fig2 = go.Figure(data=[go.Bar(x=['A', 'B', 'C'], y=[10, 20, 15])])
    fig3 = go.Figure(data=[go.Pie(labels=['X', 'Y', 'Z'], values=[30, 40, 30])])

    # Criar componentes
    components = [
        html.H1("Análise de Energia - SE03"),

        dbc.Row([
            dbc.Col(
                create_demo_graph_card(
                    title="Consumo Total",
                    figure=fig1,
                    page_path="/energy/se03",
                    graph_id="graph-1"
                ),
                width=6
            ),
            dbc.Col(
                create_demo_graph_card(
                    title="Comparativo por Equipamento",
                    figure=fig2,
                    page_path="/energy/se03",
                    graph_id="graph-2"
                ),
                width=6
            ),
        ], className="mb-4"),

        dbc.Row([
            dbc.Col(
                create_demo_graph_card(
                    title="Distribuição de Consumo",
                    figure=fig3,
                    page_path="/energy/se03",
                    graph_id="graph-3"
                ),
                width=12
            ),
        ])
    ]

    # Adiciona alerta no topo automaticamente
    layout_components = wrap_components_with_demo_info(
        components,
        page_path="/energy/se03"
    )

    return html.Div(layout_components)


# ==============================================================================
# EXEMPLO 4: Badge Manual (Casos Especiais)
# ==============================================================================

def manual_badge_example():
    """
    Para casos onde você precisa de controle total sobre o badge
    """
    from dash import html
    import dash_bootstrap_components as dbc
    from src.components.demo_badge import demo_data_badge, demo_data_tooltip_badge
    from src.config.demo_data_config import should_show_demo_badge

    # Verificar se deve mostrar badge
    show_badge = should_show_demo_badge(page_path="/custom/page")

    return html.Div([
        html.H1("Página Customizada"),

        # Badge simples
        demo_data_badge(size="md") if show_badge else None,

        # Badge com tooltip
        demo_data_tooltip_badge(
            tooltip_id="custom-tooltip",
            tooltip_text="Dados simulados para teste",
            size="sm"
        ) if show_badge else None,

        # Seu conteúdo aqui
        html.Div([
            html.P("Conteúdo da página...")
        ])
    ])


# ==============================================================================
# EXEMPLO 5: Tabela com Badge
# ==============================================================================

def table_example():
    from dash import html
    import dash_bootstrap_components as dbc
    import dash_table
    from src.utils.demo_helpers import add_demo_badge_to_table_header

    columns = [
        {"name": "Data", "id": "date"},
        {"name": "Alarme", "id": "alarm"},
        {"name": "Severidade", "id": "severity"}
    ]

    data = [
        {"date": "2024-01-01", "alarm": "Sensor X", "severity": "Alta"},
        {"date": "2024-01-02", "alarm": "Sensor Y", "severity": "Média"},
    ]

    # Adicionar badge ao header
    cols, demo_header = add_demo_badge_to_table_header(
        columns,
        page_path="/maintenance/alarms"
    )

    return html.Div([
        html.H1("Alarmes de Manutenção"),

        dbc.Card([
            dbc.CardHeader("Histórico de Alarmes"),
            dbc.CardBody([
                demo_header,  # Badge acima da tabela
                dash_table.DataTable(
                    columns=cols,
                    data=data,
                    style_table={'overflowX': 'auto'}
                )
            ])
        ])
    ])


# ==============================================================================
# EXEMPLO 6: Layout Híbrido (Alguns componentes com badge, outros sem)
# ==============================================================================

def hybrid_layout():
    """
    Página onde alguns dados são reais e outros são fictícios
    """
    from dash import html, dcc
    import plotly.graph_objects as go
    import dash_bootstrap_components as dbc
    from src.utils.demo_helpers import add_demo_badge_to_card_header
    from src.components.demo_badge import demo_data_badge

    fig_real = go.Figure(data=[go.Scatter(x=[1, 2, 3], y=[4, 5, 6])])
    fig_demo = go.Figure(data=[go.Scatter(x=[1, 2, 3], y=[7, 8, 9])])

    return html.Div([
        html.H1("Dashboard Híbrido"),

        dbc.Row([
            # Card com dados REAIS - SEM badge
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader("Temperatura Atual (Real)"),
                    dbc.CardBody(
                        dcc.Graph(figure=fig_real, id="temp-real")
                    )
                ]),
                width=6
            ),

            # Card com dados DEMO - COM badge
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader(
                        add_demo_badge_to_card_header(
                            "Previsão de Consumo (Demo)",
                            page_path="/custom/hybrid"
                        )
                    ),
                    dbc.CardBody(
                        dcc.Graph(figure=fig_demo, id="forecast-demo")
                    )
                ]),
                width=6
            ),
        ])
    ])


# ==============================================================================
# CONFIGURAÇÃO NECESSÁRIA
# ==============================================================================

"""
IMPORTANTE: Depois de criar sua página, adicione-a em config/demo_data_config.py:

DEMO_PAGES = {
    # Suas páginas
    "/production/oee": True,
    "/energy/overview": True,
    "/energy/se03": True,
    "/custom/page": True,
    "/custom/hybrid": True,
    # ...
}
"""


# ==============================================================================
# PASSO A PASSO PARA IMPLEMENTAR
# ==============================================================================

"""
1. ADICIONAR IMPORTAÇÕES:
   from src.utils.demo_helpers import (
       add_page_demo_warning,
       create_demo_card,
       create_demo_graph_card,
       wrap_components_with_demo_info
   )

2. CONFIGURAR PÁGINA:
   Em config/demo_data_config.py, adicionar:
   "/sua/pagina": True

3. APLICAR BADGES:
   - Para cards: use create_demo_card()
   - Para gráficos: use create_demo_graph_card()
   - Para alerta de página: use add_page_demo_warning()
   - Para múltiplos componentes: use wrap_components_with_demo_info()

4. TESTAR:
   - Verificar que badges aparecem quando ENABLE_DEMO_BADGES = True
   - Verificar que badges desaparecem quando = False

5. QUANDO DADOS REAIS ESTIVEREM PRONTOS:
   Em config/demo_data_config.py, mudar para:
   "/sua/pagina": False
"""
