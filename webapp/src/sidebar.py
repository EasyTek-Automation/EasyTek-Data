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
    
    IMPORTANTE: Esta função recebe o pathname JÁ RESOLVIDO após os aliases.
    Por exemplo, se o usuário acessa /dashboard, esta função recebe /production/oee
    
    Args:
        pathname (str): O caminho da URL atual (já resolvido após aliases)
        
    Returns:
        html.Div: Componente com o conteúdo apropriado para a página
    """
    # ========================================
    # CORRIGIDO: Reconhece rotas NOVAS (após resolução de aliases)
    # ========================================
    
    # Dashboard / Production OEE
    if pathname in ["/", "/production/oee"]:
        return create_dashboard_sidebar_content()
    
    # Production States
    elif pathname == "/production/states":
        return create_states_sidebar_content()
    
    # Supervision
    elif pathname == "/supervision":
        return create_superv_sidebar_content()
    
    # Fallback para qualquer outra rota (reports, energy, alarms, etc)
    else:
        return create_default_sidebar_content()


def create_sidebar_layout(app_instance, pathname="/", sidebar_content_style=None):
    """
    Cria o layout da sidebar com logo e container para conteúdo dinâmico.
    
    Args:
        app_instance: Instância da aplicação Dash
        pathname (str): O caminho da URL atual para determinar o conteúdo inicial
        sidebar_content_style (dict): Estilo para o Card da sidebar. Se None, usa padrão (hidden).
        
    Returns:
        dbc.Card: Componente Card contendo a sidebar completa
    """
    # Obtém o conteúdo inicial para a página atual
    initial_content = get_sidebar_content_for_page(pathname)
    
    # Define estilo padrão se não fornecido (collapsed/hidden)
    if sidebar_content_style is None:
        sidebar_content_style = {
            "height": "100%",
            "visibility": "hidden",
            "opacity": 0,
            "overflow": "hidden",
            "transition": "opacity 0.2s ease, visibility 0s linear 0.2s"
        }
    
    return dbc.Card([
        dbc.CardBody([
            # Logo (sempre presente)
            html.Div([
                html.Img(
                    src="/assets/LogoAMG.png",
                    style={
                        "width": "100%",
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
    ], id="sidebar-content", style=sidebar_content_style)