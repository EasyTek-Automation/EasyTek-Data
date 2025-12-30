# src/components/headers/__init__.py

"""
Módulo de filtros para o header da aplicação.
Cada página pode ter seu próprio conjunto de filtros.
"""

from .dashboard_filters import create_dashboard_filters
from .states_filters import create_states_filters
from .default_filters import create_default_filters

__all__ = [
    'create_dashboard_filters',
    'create_states_filters', 
    'create_default_filters'
]