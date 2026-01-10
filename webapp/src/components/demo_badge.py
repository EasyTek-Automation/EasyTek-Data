"""
Componente de badge para indicar dados fictícios/demonstração.
Usado para sinalizar quando os dados exibidos não são reais.
"""

from dash import html
import dash_bootstrap_components as dbc


def demo_data_badge(size="sm", className=""):
    """
    Cria um badge para indicar dados fictícios/demonstração.

    Args:
        size (str): Tamanho do badge. Opções: "sm", "md", "lg". Default: "sm"
        className (str): Classes CSS adicionais para customização

    Returns:
        dbc.Badge: Badge com texto "DADOS DE DEMONSTRAÇÃO"

    Example:
        >>> # Em um gráfico
        >>> dbc.Card([
        ...     dbc.CardHeader([
        ...         html.H5("Consumo de Energia"),
        ...         demo_data_badge()
        ...     ]),
        ...     dbc.CardBody([graph])
        ... ])

        >>> # Em um KPI card
        >>> dbc.Card([
        ...     demo_data_badge(size="sm"),
        ...     html.H3("1.234 kWh"),
        ...     html.P("Consumo Total")
        ... ])
    """
    badge_sizes = {
        "sm": {"fontSize": "0.65rem", "padding": "0.15rem 0.4rem"},
        "md": {"fontSize": "0.75rem", "padding": "0.25rem 0.5rem"},
        "lg": {"fontSize": "0.85rem", "padding": "0.35rem 0.6rem"}
    }

    style = badge_sizes.get(size, badge_sizes["sm"])

    return dbc.Badge(
        [
            html.I(className="bi bi-exclamation-triangle-fill me-1"),
            "DADOS DE DEMONSTRAÇÃO"
        ],
        color="warning",
        className=f"demo-data-badge {className}",
        style={
            **style,
            "fontWeight": "600",
            "letterSpacing": "0.5px",
            "opacity": "0.9"
        }
    )


def demo_data_tooltip_badge(tooltip_id, tooltip_text=None, size="sm"):
    """
    Cria um badge com tooltip explicativo.

    Args:
        tooltip_id (str): ID único para o tooltip
        tooltip_text (str): Texto do tooltip. Se None, usa texto padrão
        size (str): Tamanho do badge. Opções: "sm", "md", "lg"

    Returns:
        html.Div: Container com badge e tooltip

    Example:
        >>> demo_data_tooltip_badge(
        ...     tooltip_id="graph-demo-badge",
        ...     tooltip_text="Os dados exibidos são simulados para fins de demonstração"
        ... )
    """
    if tooltip_text is None:
        tooltip_text = (
            "Os dados exibidos nesta seção são fictícios e servem "
            "apenas para demonstração da interface e funcionalidades."
        )

    return html.Div([
        html.Span(
            demo_data_badge(size=size),
            id=tooltip_id,
            style={"cursor": "help"}
        ),
        dbc.Tooltip(
            tooltip_text,
            target=tooltip_id,
            placement="top"
        )
    ])


def with_demo_badge(component, position="top-right", size="sm"):
    """
    Envolve um componente adicionando um badge de demonstração.

    Args:
        component: Componente Dash a ser envolvido
        position (str): Posição do badge. Opções: "top-left", "top-right", "bottom-left", "bottom-right"
        size (str): Tamanho do badge

    Returns:
        html.Div: Container com o componente e badge posicionado

    Example:
        >>> graph = dcc.Graph(figure=fig)
        >>> with_demo_badge(graph, position="top-right")
    """
    position_styles = {
        "top-right": {"top": "10px", "right": "10px"},
        "top-left": {"top": "10px", "left": "10px"},
        "bottom-right": {"bottom": "10px", "right": "10px"},
        "bottom-left": {"bottom": "10px", "left": "10px"}
    }

    badge_style = {
        "position": "absolute",
        "zIndex": "1000",
        **position_styles.get(position, position_styles["top-right"])
    }

    return html.Div([
        html.Div(
            demo_data_badge(size=size),
            style=badge_style
        ),
        component
    ], style={"position": "relative"})
