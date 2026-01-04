# src/pages/common/access_denied.py

"""
Página de Acesso Negado
=======================

Exibida quando um usuário tenta acessar uma rota sem permissão.
Mostra informações úteis sobre o motivo da negação.
"""

from dash import html
import dash_bootstrap_components as dbc


def layout(pathname=None, reason=None, user=None):
    """
    Cria o layout da página de acesso negado.
    
    Args:
        pathname (str): Rota que o usuário tentou acessar
        reason (str): Motivo da negação de acesso
        user: Objeto User (para mostrar informações do usuário)
        
    Returns:
        dbc.Container: Layout da página de acesso negado
    """
    # Informações do usuário para debug (se disponível)
    user_info = None
    if user and hasattr(user, 'username'):
        user_info = html.Div([
            html.Hr(),
            html.P([
                html.Strong("Usuário: "), 
                user.username
            ], className="mb-1 small"),
            html.P([
                html.Strong("Nível: "), 
                str(getattr(user, 'level', 'N/A'))
            ], className="mb-1 small"),
            html.P([
                html.Strong("Perfil: "), 
                getattr(user, 'perfil', 'N/A')
            ], className="mb-0 small"),
        ], className="text-muted")
    
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        # Ícone de acesso negado
                        html.Div([
                            html.I(
                                className="bi bi-shield-lock-fill text-danger", 
                                style={"fontSize": "5rem"}
                            )
                        ], className="text-center mb-4"),
                        
                        # Título
                        html.H2(
                            "Acesso Negado", 
                            className="text-center text-danger mb-3"
                        ),
                        
                        # Mensagem principal
                        html.P(
                            "Você não tem permissão para acessar esta página.",
                            className="text-center text-muted mb-4",
                            style={"fontSize": "1.1rem"}
                        ),
                        
                        # Detalhes do erro (se disponíveis)
                        html.Div([
                            # Rota tentada
                            dbc.Alert([
                                html.Div([
                                    html.I(className="bi bi-link-45deg me-2"),
                                    html.Strong("Rota: "),
                                    html.Code(pathname or "N/A")
                                ], className="mb-2"),
                                
                                # Motivo
                                html.Div([
                                    html.I(className="bi bi-info-circle me-2"),
                                    html.Strong("Motivo: "),
                                    reason or "Permissão insuficiente"
                                ]),
                            ], color="light", className="mb-4"),
                        ]) if pathname or reason else None,
                        
                        # Informações do usuário (debug)
                        user_info,
                        
                        # Ações
                        html.Div([
                            dbc.Button([
                                html.I(className="bi bi-house-door me-2"),
                                "Voltar ao Início"
                            ], href="/", color="primary", size="lg", className="me-2"),
                            
                            dbc.Button([
                                html.I(className="bi bi-arrow-left me-2"),
                                "Voltar"
                            ], id="btn-access-denied-back", color="secondary", size="lg", outline=True),
                        ], className="text-center mt-4"),
                        
                        # Mensagem de contato
                        html.P([
                            "Se você acredita que deveria ter acesso a esta página, ",
                            "entre em contato com o administrador do sistema."
                        ], className="text-center text-muted mt-4 small")
                        
                    ], className="p-5")
                ], className="shadow border-0")
            ], width={"size": 6, "offset": 3})
        ], className="mt-5")
    ], fluid=True, style={
        "minHeight": "70vh", 
        "display": "flex", 
        "alignItems": "center"
    })


def layout_simple(message="Você não tem permissão para acessar esta página."):
    """
    Versão simplificada da página de acesso negado.
    Para uso em casos onde não há informações detalhadas.
    
    Args:
        message (str): Mensagem a ser exibida
        
    Returns:
        html.Div: Layout simplificado
    """
    return html.Div([
        dbc.Alert([
            html.H4([
                html.I(className="bi bi-shield-lock me-2"),
                "Acesso Negado"
            ], className="alert-heading"),
            html.Hr(),
            html.P(message, className="mb-0")
        ], color="danger", className="m-4")
    ])