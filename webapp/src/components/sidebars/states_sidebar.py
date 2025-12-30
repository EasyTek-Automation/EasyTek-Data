# src/components/sidebars/states_sidebar.py

"""
Conteúdo da sidebar específico para a página States.
"""

from dash import html
import dash_bootstrap_components as dbc


def create_states_sidebar_content():
    """
    Cria o conteúdo da sidebar para a página States.
    
    Returns:
        html.Div: Componente com o conteúdo da sidebar da página states
    """
    return html.Div([
        # Título da seção
        html.H6("Estados OEE", className="text-primary fw-bold mb-3"),
        
        # Informações da página
        html.Div([
            html.P(
                "Visualização de estados e performance do OEE.",
                className="text-muted small mb-3"
            ),
            
            # Legenda de cores do OEE
            html.Div([
                html.Small("Legenda de Performance:", className="fw-bold d-block mb-2"),
                html.Div([
                    html.Span("●", style={"color": "green", "fontSize": "1.2rem", "marginRight": "5px"}),
                    html.Small("OEE ≥ 80% (Bom)", className="text-muted"),
                ], className="d-flex align-items-center mb-1"),
                html.Div([
                    html.Span("●", style={"color": "yellow", "fontSize": "1.2rem", "marginRight": "5px"}),
                    html.Small("50% ≤ OEE < 80% (Médio)", className="text-muted"),
                ], className="d-flex align-items-center mb-1"),
                html.Div([
                    html.Span("●", style={"color": "red", "fontSize": "1.2rem", "marginRight": "5px"}),
                    html.Small("OEE < 50% (Ruim)", className="text-muted"),
                ], className="d-flex align-items-center"),
            ], className="p-2 rounded", style={"backgroundColor": "var(--bs-light)"}),
        ]),
        
        html.Hr(className="my-3"),
        
        # Dica de uso
        html.Div([
            html.Small([
                html.I(className="fas fa-lightbulb me-1"),
                "Use o switch para alternar entre visualizações do gráfico."
            ], className="text-muted"),
        ]),
        
    ], id="states-sidebar-content", style={"padding": "10px"})
