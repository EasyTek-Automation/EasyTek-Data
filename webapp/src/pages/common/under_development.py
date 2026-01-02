# src/pages/common/under_development.py

"""
Página padrão para funcionalidades em desenvolvimento
"""

from dash import html
import dash_bootstrap_components as dbc

def layout(page_title="Funcionalidade em Desenvolvimento", custom_message=None):
    """
    Página padrão para exibir quando uma funcionalidade está em desenvolvimento.
    
    Args:
        page_title (str): Título da página
        custom_message (str): Mensagem customizada (opcional)
    
    Returns:
        dbc.Container: Layout da página
    """
    
    default_message = (
        "Esta funcionalidade está sendo desenvolvida e estará "
        "disponível em breve. Agradecemos sua compreensão!"
    )
    
    message = custom_message if custom_message else default_message
    
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                # Card principal
                dbc.Card([
                    dbc.CardBody([
                        # Ícone grande
                        html.Div([
                            html.I(
                                className="bi bi-cone-striped",
                                style={
                                    "fontSize": "6rem",
                                    "color": "#ffc107"
                                }
                            )
                        ], className="text-center mb-4"),
                        
                        # Título
                        html.H2(
                            page_title,
                            className="text-center mb-3",
                            style={"fontWeight": "600"}
                        ),
                        
                        # Mensagem
                        html.P(
                            message,
                            className="text-center text-muted mb-4",
                            style={"fontSize": "1.1rem"}
                        ),
                        
                        # Badge de status
                        html.Div([
                            dbc.Badge(
                                [
                                    html.I(className="bi bi-hourglass-split me-2"),
                                    "Em Desenvolvimento"
                                ],
                                color="warning",
                                className="px-4 py-2",
                                style={"fontSize": "0.9rem"}
                            )
                        ], className="text-center mb-4"),
                        
                        # Linha separadora
                        html.Hr(),
                        
                        # Informações adicionais
                        dbc.Row([
                            dbc.Col([
                                html.Div([
                                    html.I(className="bi bi-clock-history text-primary", 
                                          style={"fontSize": "1.5rem"}),
                                    html.P("Em breve", className="mt-2 mb-0 small text-muted")
                                ], className="text-center")
                            ], width=4),
                            dbc.Col([
                                html.Div([
                                    html.I(className="bi bi-code-slash text-success", 
                                          style={"fontSize": "1.5rem"}),
                                    html.P("Em construção", className="mt-2 mb-0 small text-muted")
                                ], className="text-center")
                            ], width=4),
                            dbc.Col([
                                html.Div([
                                    html.I(className="bi bi-rocket-takeoff text-info", 
                                          style={"fontSize": "1.5rem"}),
                                    html.P("Novidades chegando", className="mt-2 mb-0 small text-muted")
                                ], className="text-center")
                            ], width=4),
                        ], className="mt-4"),
                        
                        # Botão voltar
                        html.Div([
                            dbc.Button(
                                [
                                    html.I(className="bi bi-arrow-left me-2"),
                                    "Voltar ao Início"
                                ],
                                href="/",
                                color="primary",
                                size="lg",
                                className="mt-4"
                            )
                        ], className="text-center")
                        
                    ], className="p-5")
                ], className="shadow-lg", style={"borderRadius": "15px"})
                
            ], width={"size": 8, "offset": 2}, lg={"size": 6, "offset": 3})
        ], className="mt-5")
        
    ], fluid=True, className="p-4", style={"minHeight": "80vh", "display": "flex", "alignItems": "center"})


# ========================================
# VARIAÇÕES PRÉ-CONFIGURADAS
# ========================================

def states_development():
    """Página em desenvolvimento para Estados da Linha"""
    return layout(
        page_title="Estados da Linha - Em Desenvolvimento",
        custom_message="A visualização detalhada dos estados da linha está sendo desenvolvida. Em breve você poderá acompanhar em tempo real o status de cada equipamento."
    )

def alarms_development():
    """Página em desenvolvimento para Alarmes"""
    return layout(
        page_title="Sistema de Alarmes - Em Desenvolvimento",
        custom_message="O sistema completo de gerenciamento de alarmes está sendo implementado. Em breve você terá acesso ao histórico completo e filtros avançados."
    )

def reports_development():
    """Página em desenvolvimento para Relatórios"""
    return layout(
        page_title="Relatórios - Em Desenvolvimento",
        custom_message="O módulo de geração de relatórios personalizados está sendo desenvolvido. Em breve você poderá criar e exportar relatórios detalhados."
    )

def energy_overview_development():
    """Página em desenvolvimento para Visão Geral de Energia"""
    return layout(
        page_title="Energia - Visão Geral - Em Desenvolvimento",
        custom_message="O dashboard consolidado de todas as subestações está sendo desenvolvido. Em breve você terá uma visão completa do consumo energético."
    )

def maintenance_development():
    """Página em desenvolvimento para funcionalidades de Manutenção"""
    return layout(
        page_title="Manutenção - Em Desenvolvimento",
        custom_message="Os módulos de ordens de serviço, planos de manutenção e histórico estão sendo desenvolvidos. Em breve você terá um sistema completo de gestão de manutenção."
    )

def utilities_development():
    """Página em desenvolvimento para outras Utilidades"""
    return layout(
        page_title="Utilidades - Em Desenvolvimento",
        custom_message="Os módulos de monitoramento de água, gás natural e ar comprimido estão sendo desenvolvidos. Em breve você terá visibilidade completa de todas as utilidades."
    )

def config_development():
    """Página em desenvolvimento para Configurações"""
    return layout(
        page_title="Configurações - Em Desenvolvimento",
        custom_message="As configurações avançadas do sistema estão sendo desenvolvidas. Em breve você poderá personalizar ainda mais sua experiência."
    )