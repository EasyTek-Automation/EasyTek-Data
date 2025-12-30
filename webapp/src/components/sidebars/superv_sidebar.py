# src/components/sidebars/superv_sidebar.py

"""
Conteúdo da sidebar específico para a página Supervisório.
"""

from dash import html
import dash_bootstrap_components as dbc


def create_superv_sidebar_content():
    """
    Cria o conteúdo da sidebar para a página Supervisório.
    
    Returns:
        html.Div: Componente com o conteúdo da sidebar do supervisório
    """
    return html.Div([
        # Título da seção
        html.H6("Supervisório", className="text-danger fw-bold mb-3"),
        
        # Aviso de acesso restrito
        dbc.Alert([
            html.I(className="fas fa-exclamation-triangle me-2"),
            "Área restrita - Nível 2/3"
        ], color="warning", className="py-2 small"),
        
        # Informações da página
        html.Div([
            html.P(
                "Controle de setpoints de temperatura.",
                className="text-muted small mb-3"
            ),
            
            # Instruções
            html.Div([
                html.Small("Instruções:", className="fw-bold d-block mb-2"),
                html.Ul([
                    html.Li(html.Small("Insira o valor desejado no campo", className="text-muted")),
                    html.Li(html.Small("Clique em 'Carregar Setpoint'", className="text-muted")),
                    html.Li(html.Small("Aguarde a confirmação do envio", className="text-muted")),
                ], className="ps-3 mb-0", style={"listStyleType": "disc"}),
            ], className="p-2 rounded", style={"backgroundColor": "var(--bs-light)"}),
        ]),
        
        html.Hr(className="my-3"),
        
        # Limites
        html.Div([
            html.Small("Limites de Temperatura:", className="fw-bold d-block mb-2"),
            html.Div([
                html.Small("Mínimo: ", className="text-muted"),
                html.Small("30°C", className="fw-bold text-info"),
            ]),
            html.Div([
                html.Small("Máximo: ", className="text-muted"),
                html.Small("100°C", className="fw-bold text-danger"),
            ]),
        ]),
        
    ], id="superv-sidebar-content", style={"padding": "10px"})
