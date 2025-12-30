# src/components/headers/states_filters.py

"""
Filtros específicos para a página States.
Pode ser customizado conforme necessário.
"""

from dash import html
import dash_bootstrap_components as dbc


def create_states_filters():
    """
    Cria os filtros específicos para a página States.
    Atualmente em desenvolvimento.
    
    Returns:
        html.Div: Componente com os filtros da página states
    """
    return html.Div([
        html.Div([
            html.I(className="fas fa-cog fa-2x text-muted mb-3"),
            html.P("Filtros da página States", className="fw-bold mb-1"),
            html.P("Em desenvolvimento...", className="text-muted small"),
        ], className="text-center py-4")
    ], style={"padding": "1rem", "minWidth": "300px"}, id="states-filters-content")
