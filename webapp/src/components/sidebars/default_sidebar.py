# src/components/sidebars/default_sidebar.py

"""
Conteúdo padrão da sidebar para páginas sem sidebar específica.
"""

from dash import html
import dash_bootstrap_components as dbc


def create_default_sidebar_content():
    """
    Cria o conteúdo padrão da sidebar para páginas sem conteúdo específico.
    
    Returns:
        html.Div: Componente com o conteúdo padrão da sidebar
    """
    return html.Div([
        html.Div([
            html.I(className="fas fa-compass fa-2x text-muted mb-3"),
            html.P("Navegação", className="fw-bold mb-1"),
            html.P(
                "Selecione uma página no menu para ver opções específicas.",
                className="text-muted small"
            ),
        ], className="text-center py-4"),
    ], id="default-sidebar-content", style={"padding": "10px"})
