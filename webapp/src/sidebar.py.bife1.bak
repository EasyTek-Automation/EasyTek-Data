# src/sidebar.py

"""
Componente de barra lateral (sidebar) principal da aplicação.
Responsável por montar a sidebar com logo e conteúdo dinâmico baseado na página.
"""

from dash import html
import dash_bootstrap_components as dbc

# Importações dos conteúdos específicos de cada página
from src.components.sidebars import (
    create_dashboard_sidebar_content,
    create_states_sidebar_content,
    create_superv_sidebar_content,
    create_default_sidebar_content
)


def get_sidebar_content_for_page(pathname):
    """
    Retorna o conteúdo da sidebar baseado na página atual.
    
    Args:
        pathname (str): O caminho da URL atual
        
    Returns:
        html.Div: Componente com o conteúdo apropriado para a página
    """
    if pathname == "/" or pathname == "/dashboard":
        return create_dashboard_sidebar_content()
    elif pathname == "/states":
        return create_states_sidebar_content()
    elif pathname == "/superv":
        return create_superv_sidebar_content()
    else:
        return create_default_sidebar_content()


def create_sidebar_layout(app_instance, pathname="/"):
    """
    Cria o layout da sidebar com logo e container para conteúdo dinâmico.
    
    Args:
        app_instance: Instância da aplicação Dash
        pathname (str): O caminho da URL atual para determinar o conteúdo inicial
        
    Returns:
        dbc.Card: Componente Card contendo a sidebar completa
    """
    # Obtém o conteúdo inicial para a página atual
    initial_content = get_sidebar_content_for_page(pathname)
    
    return dbc.Card([
        dbc.CardBody([
            # Logo (sempre presente)
            html.Div([
                html.Img(
                    src="/assets/LogoAMG.png",
                    style={
                        "width": "80%",
                        "max-height": "120px",
                        "object-fit": "contain",
                        "margin": "0 auto 20px",
                        "display": "block"
                    }
                ),
                html.Hr(),
            ], style={"width": "100%"}),

            # Container para conteúdo dinâmico (será atualizado via callback)
            html.Div(
                children=initial_content,
                id="sidebar-dynamic-content"
            ),

        ], style={"height": "calc(100% - 2rem)", "margin": "0"})
    ], id="sidebar-content", style={
        "flex": "1",
        "height": "100%",
        "visibility": "visible",
        "opacity": 1,
        "overflowY": "auto",
        "transition": "opacity 0.3s ease, visibility 0s linear 0.5s"
    })