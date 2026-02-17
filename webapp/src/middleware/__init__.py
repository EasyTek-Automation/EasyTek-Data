# src/middleware/__init__.py
"""
Middlewares customizados para o Flask
"""

from .mobile_detection import mobile_redirect_middleware

__all__ = ['mobile_redirect_middleware']
