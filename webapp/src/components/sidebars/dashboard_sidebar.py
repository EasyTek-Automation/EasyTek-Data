# src/components/sidebars/dashboard_sidebar.py

"""
Conteúdo da sidebar específico para a página Dashboard.
"""

from dash import html
import dash_bootstrap_components as dbc


def create_dashboard_sidebar_content():
    """
    Cria o conteúdo da sidebar para a página Dashboard.
    
    Returns:
        html.Div: Componente com o conteúdo da sidebar do dashboard
    """
    return html.Div([
        # Título da seção
        html.H6("Dashboard", className="text-primary fw-bold mb-3"),
        
        # Informações ou ações específicas do dashboard
        html.Div([
            html.P(
                "Monitoramento de energia e consumo em tempo real.",
                className="text-muted small mb-3"
            ),
            
            # Legenda dos grupos (referência visual)
            html.Div([
                html.Small("Legenda dos Grupos:", className="fw-bold d-block mb-2"),
                html.Div([
                    html.Span("●", style={"color": "#1f77b4", "fontSize": "1.2rem", "marginRight": "5px"}),
                    html.Small("Transversais", className="text-muted"),
                ], className="d-flex align-items-center mb-1"),
                html.Div([
                    html.Span("●", style={"color": "#ff7f0e", "fontSize": "1.2rem", "marginRight": "5px"}),
                    html.Small("Longitudinais", className="text-muted"),
                ], className="d-flex align-items-center"),
            ], className="p-2 rounded", style={"backgroundColor": "var(--bs-light)"}),
        ]),
        
        html.Hr(className="my-3"),
        
        # Dica de uso
        html.Div([
            html.Small([
                html.I(className="fas fa-info-circle me-1"),
                "Use o menu 'Filtros' no header para selecionar equipamentos e período."
            ], className="text-muted"),
        ]),
        
    ], id="dashboard-sidebar-content", style={"padding": "10px"})
