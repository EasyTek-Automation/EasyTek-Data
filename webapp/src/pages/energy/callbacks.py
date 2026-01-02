# src/pages/energy/callbacks.py

"""
Callbacks para a página de visão geral de energia
"""

from dash import Input, Output
from src.app import app
from src.pages.energy.overview import get_se03_content, get_under_development_content


@app.callback(
    Output("energy-tab-content", "children"),
    Input("energy-tabs", "active_tab")
)
def update_energy_tab_content(active_tab):
    """
    Atualiza o conteúdo da página baseado na tab ativa
    
    Args:
        active_tab (str): ID da tab ativa (se00, se01, se02, se03, se04, all)
        
    Returns:
        html.Div: Conteúdo correspondente à tab
    """
    # SE03 - já está implementada
    if active_tab == "se03":
        return get_se03_content()
    
    # Outras tabs - Em Desenvolvimento
    else:
        return get_under_development_content(active_tab)