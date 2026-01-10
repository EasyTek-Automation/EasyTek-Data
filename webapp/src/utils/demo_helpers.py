"""
Funções helper para aplicar badges de dados de demonstração em componentes.

Este módulo fornece funções utilitárias que facilitam a adição de badges
de demonstração em diferentes tipos de componentes (gráficos, cards, tabelas).
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
from src.components.demo_badge import demo_data_badge, demo_data_tooltip_badge, with_demo_badge
from src.config.demo_data_config import should_show_demo_badge


# ======================================================================================
# APLICAR BADGE EM CARDS
# ======================================================================================

def add_demo_badge_to_card_header(title, page_path=None, component_name=None, size="sm"):
    """
    Adiciona badge de demonstração ao header de um card.

    Args:
        title (str ou componente): Título do card
        page_path (str): Caminho da página para verificar configuração
        component_name (str): Nome do componente para verificar configuração
        size (str): Tamanho do badge

    Returns:
        list: Lista com título e badge (se ativo)

    Example:
        >>> dbc.CardHeader(
        ...     add_demo_badge_to_card_header(
        ...         "Consumo de Energia",
        ...         page_path="/energy/overview"
        ...     )
        ... )
    """
    elements = [title] if not isinstance(title, list) else title

    # Verificar se deve mostrar badge
    if should_show_demo_badge(page_path=page_path, component_name=component_name):
        elements.append(
            html.Span(
                demo_data_badge(size=size),
                className="ms-2"
            )
        )

    return elements


def create_demo_card(title, content, page_path=None, color="primary", **kwargs):
    """
    Cria um card com badge de demonstração automático.

    Args:
        title (str): Título do card
        content: Conteúdo do card
        page_path (str): Caminho da página
        color (str): Cor do card
        **kwargs: Argumentos adicionais para dbc.Card

    Returns:
        dbc.Card: Card com badge se configurado

    Example:
        >>> create_demo_card(
        ...     title="OEE Total",
        ...     content=html.H2("85.5%"),
        ...     page_path="/production/oee"
        ... )
    """
    header_content = add_demo_badge_to_card_header(title, page_path=page_path)

    return dbc.Card([
        dbc.CardHeader(header_content),
        dbc.CardBody(content)
    ], color=color, **kwargs)


# ======================================================================================
# APLICAR BADGE EM GRÁFICOS
# ======================================================================================

def add_demo_badge_to_graph(graph, page_path=None, component_name=None, position="top-right", size="sm"):
    """
    Adiciona badge de demonstração a um gráfico.

    Args:
        graph: Componente dcc.Graph
        page_path (str): Caminho da página
        component_name (str): Nome do componente
        position (str): Posição do badge
        size (str): Tamanho do badge

    Returns:
        html.Div ou dcc.Graph: Gráfico com badge se ativo, ou gráfico original

    Example:
        >>> fig = go.Figure(...)
        >>> graph = dcc.Graph(figure=fig)
        >>> add_demo_badge_to_graph(
        ...     graph,
        ...     page_path="/energy/overview",
        ...     position="top-right"
        ... )
    """
    # Verificar se deve mostrar badge
    if should_show_demo_badge(page_path=page_path, component_name=component_name):
        return with_demo_badge(graph, position=position, size=size)

    return graph


def create_demo_graph_card(title, figure, page_path=None, component_name=None, graph_id=None):
    """
    Cria um card com gráfico e badge de demonstração.

    Args:
        title (str): Título do gráfico
        figure: Figura do Plotly
        page_path (str): Caminho da página
        component_name (str): Nome do componente
        graph_id (str): ID do componente dcc.Graph

    Returns:
        dbc.Card: Card completo com header, badge e gráfico

    Example:
        >>> fig = px.line(df, x='date', y='value')
        >>> create_demo_graph_card(
        ...     title="Consumo por Hora",
        ...     figure=fig,
        ...     page_path="/energy/se03",
        ...     graph_id="consumption-graph"
        ... )
    """
    # Criar header com badge
    header_content = add_demo_badge_to_card_header(title, page_path=page_path, component_name=component_name)

    # Criar gráfico
    graph_config = {"id": graph_id} if graph_id else {}
    graph = dcc.Graph(figure=figure, **graph_config)

    return dbc.Card([
        dbc.CardHeader(header_content),
        dbc.CardBody(graph, className="p-0")
    ])


# ======================================================================================
# APLICAR BADGE EM LAYOUTS DE PÁGINA
# ======================================================================================

def add_page_demo_warning(page_path, message=None):
    """
    Adiciona um alerta de demonstração no topo de uma página.

    Args:
        page_path (str): Caminho da página
        message (str): Mensagem customizada. Se None, usa mensagem padrão

    Returns:
        dbc.Alert ou None: Alerta se configurado, None caso contrário

    Example:
        >>> layout = html.Div([
        ...     add_page_demo_warning("/production/oee"),
        ...     # resto do conteúdo da página
        ... ])
    """
    if not should_show_demo_badge(page_path=page_path):
        return None

    if message is None:
        message = (
            "Os dados exibidos nesta página são fictícios e servem apenas "
            "para demonstração da interface e funcionalidades do sistema."
        )

    return dbc.Alert([
        html.I(className="bi bi-info-circle-fill me-2"),
        message
    ], color="warning", className="mb-3", dismissable=True)


# ======================================================================================
# APLICAR BADGE EM TABELAS
# ======================================================================================

def add_demo_badge_to_table_header(columns, page_path=None, component_name=None):
    """
    Adiciona informação de demonstração ao header de uma tabela.

    Args:
        columns (list): Lista de colunas da tabela
        page_path (str): Caminho da página
        component_name (str): Nome do componente

    Returns:
        tuple: (columns, additional_header) - Colunas e header adicional se necessário

    Example:
        >>> columns = [{"name": "Data", "id": "date"}, {"name": "Valor", "id": "value"}]
        >>> cols, header = add_demo_badge_to_table_header(
        ...     columns,
        ...     page_path="/maintenance/alarms"
        ... )
    """
    additional_header = None

    if should_show_demo_badge(page_path=page_path, component_name=component_name):
        additional_header = html.Div([
            demo_data_badge(size="sm"),
            html.Span(" Dados de Demonstração", className="ms-2 text-muted small")
        ], className="mb-2")

    return columns, additional_header


# ======================================================================================
# HELPER PARA MÚLTIPLOS COMPONENTES
# ======================================================================================

def wrap_components_with_demo_info(components, page_path):
    """
    Envolve uma lista de componentes com informação de demonstração.

    Args:
        components (list): Lista de componentes
        page_path (str): Caminho da página

    Returns:
        list: Componentes com alerta no topo se configurado

    Example:
        >>> components = [graph1, graph2, table1]
        >>> layout_components = wrap_components_with_demo_info(
        ...     components,
        ...     page_path="/production/oee"
        ... )
    """
    warning = add_page_demo_warning(page_path)

    if warning:
        return [warning] + components

    return components
