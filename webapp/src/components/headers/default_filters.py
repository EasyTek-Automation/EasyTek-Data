# src/components/headers/default_filters.py

"""
Filtros padrão para páginas que não possuem filtros específicos.
"""

from dash import html
import dash_bootstrap_components as dbc
from src.components.dropdown_footer import create_dropdown_footer


def create_default_filters():
    """
    Cria os filtros padrão para páginas sem filtro específico.
    
    Returns:
        html.Div: Componente com mensagem de filtro não disponível
    """
    return html.Div([
        html.Div([
            html.I(className="fas fa-filter fa-2x text-muted mb-3"),
            html.P("Nenhum filtro disponível para esta página.", className="text-muted small"),
        ], className="text-center py-4"),

        # Footer "Powered By"
        create_dropdown_footer()
    ], style={"padding": "1rem", "minWidth": "300px"}, id="default-filters-content")
