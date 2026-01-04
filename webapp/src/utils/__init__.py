# src/utils/__init__.py
"""
Módulo de utilitários da aplicação.
"""

from .permissions import (
    can_access_route,
    can_see_menu,
    get_accessible_routes,
    get_visible_menus,
    check_access
)

__all__ = [
    'can_access_route',
    'can_see_menu',
    'get_accessible_routes',
    'get_visible_menus',
    'check_access'
]