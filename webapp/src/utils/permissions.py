# src/utils/permissions.py

"""
Funções Utilitárias de Verificação de Permissões
================================================

Este módulo fornece funções para verificar permissões de acesso
baseadas na matriz de controle (nível × perfil).

Exemplo de uso:
    from src.utils.permissions import can_access_route, can_see_menu
    
    if can_access_route(current_user, "/maintenance/alarms"):
        # Usuário pode acessar
    
    if can_see_menu(current_user, "manutencao"):
        # Mostrar menu de manutenção
"""

from src.config.access_control import (
    get_route_config, 
    get_menu_config, 
    ROUTE_ACCESS, 
    MENU_ACCESS,
    is_public_route
)


def can_access_route(user, pathname):
    """
    Verifica se um usuário pode acessar uma determinada rota.
    
    Regras:
    1. Se a rota é pública (min_level=0), qualquer um pode acessar
    2. Se a rota é shared, verifica apenas o nível
    3. Se a rota não é shared, verifica nível E perfil
    
    Args:
        user: Objeto User do Flask-Login (ou None se não autenticado)
        pathname (str): Caminho da rota a verificar
        
    Returns:
        bool: True se o usuário pode acessar a rota
    """
    config = get_route_config(pathname)
    
    # Rotas públicas (login, register)
    if config.get("min_level", 1) == 0:
        return True
    
    # Se não há usuário autenticado, não pode acessar rotas protegidas
    if user is None or not hasattr(user, 'level'):
        return False
    
    # Verificar nível mínimo
    user_level = getattr(user, 'level', 0)
    min_level = config.get("min_level", 1)
    
    if user_level < min_level:
        return False
    
    # Se é shared, só precisava verificar o nível (já passou)
    if config.get("shared", False):
        return True
    
    # Não é shared: verificar perfil
    user_perfil = getattr(user, 'perfil', None)
    allowed_perfis = config.get("perfis", [])
    
    if user_perfil not in allowed_perfis:
        return False
    
    return True


def can_see_menu(user, menu_key):
    """
    Verifica se um usuário pode ver um determinado menu.
    
    Regras:
    1. Se o menu é shared, verifica apenas o nível
    2. Se o menu não é shared, verifica nível E perfil
    
    Args:
        user: Objeto User do Flask-Login
        menu_key (str): Chave do menu (ex: "manutencao", "producao")
        
    Returns:
        bool: True se o usuário pode ver o menu
    """
    config = get_menu_config(menu_key)
    
    # Se não há usuário, não pode ver menus protegidos
    if user is None or not hasattr(user, 'level'):
        return False
    
    # Verificar nível mínimo
    user_level = getattr(user, 'level', 0)
    min_level = config.get("min_level", 1)
    
    if user_level < min_level:
        return False
    
    # Se é shared, só precisava verificar o nível (já passou)
    if config.get("shared", False):
        return True
    
    # Não é shared: verificar perfil
    user_perfil = getattr(user, 'perfil', None)
    allowed_perfis = config.get("perfis", [])
    
    return user_perfil in allowed_perfis


def get_accessible_routes(user):
    """
    Retorna lista de todas as rotas que o usuário pode acessar.
    
    Args:
        user: Objeto User do Flask-Login
        
    Returns:
        list: Lista de pathnames acessíveis
    """
    accessible = []
    
    for pathname in ROUTE_ACCESS.keys():
        if can_access_route(user, pathname):
            accessible.append(pathname)
    
    return accessible


def get_visible_menus(user):
    """
    Retorna lista de todos os menus visíveis para o usuário.
    
    Args:
        user: Objeto User do Flask-Login
        
    Returns:
        list: Lista de menu_keys visíveis
    """
    visible = []
    
    for menu_key in MENU_ACCESS.keys():
        if can_see_menu(user, menu_key):
            visible.append(menu_key)
    
    return visible


def get_access_info(user, pathname):
    """
    Retorna informações detalhadas sobre o acesso a uma rota.
    Útil para debugging e logs.
    
    Args:
        user: Objeto User do Flask-Login
        pathname (str): Caminho da rota
        
    Returns:
        dict: Informações detalhadas sobre o acesso
    """
    config = get_route_config(pathname)
    
    user_level = getattr(user, 'level', 0) if user else 0
    user_perfil = getattr(user, 'perfil', None) if user else None
    
    return {
        "pathname": pathname,
        "config": config,
        "user_level": user_level,
        "user_perfil": user_perfil,
        "can_access": can_access_route(user, pathname),
        "reason": _get_denial_reason(user, pathname, config)
    }


def _get_denial_reason(user, pathname, config):
    """
    Retorna o motivo da negação de acesso (para mensagens de erro).
    
    Args:
        user: Objeto User
        pathname (str): Caminho da rota
        config (dict): Configuração da rota
        
    Returns:
        str: Motivo da negação ou None se o acesso é permitido
    """
    if config.get("min_level", 1) == 0:
        return None  # Rota pública
    
    if user is None:
        return "Usuário não autenticado"
    
    user_level = getattr(user, 'level', 0)
    min_level = config.get("min_level", 1)
    
    if user_level < min_level:
        return f"Nível insuficiente (seu nível: {user_level}, requerido: {min_level})"
    
    if config.get("shared", False):
        return None  # Acesso permitido (shared)
    
    user_perfil = getattr(user, 'perfil', None)
    allowed_perfis = config.get("perfis", [])
    
    if user_perfil not in allowed_perfis:
        return f"Perfil não autorizado (seu perfil: {user_perfil}, permitidos: {', '.join(allowed_perfis)})"
    
    return None  # Acesso permitido


def check_access(user, pathname):
    """
    Verifica acesso e retorna tupla (permitido, motivo).
    Função conveniente para uso em callbacks.
    
    Args:
        user: Objeto User do Flask-Login
        pathname (str): Caminho da rota
        
    Returns:
        tuple: (bool, str) - (acesso_permitido, motivo_se_negado)
    """
    config = get_route_config(pathname)
    reason = _get_denial_reason(user, pathname, config)
    
    return (reason is None, reason)