# src/components/headers/__init__.py

"""
Módulo de filtros para o header da aplicação.
Cada página pode ter seu próprio conjunto de filtros.
"""

from .energy_filters import create_energy_filters
from .states_filters import create_states_filters
from .default_filters import create_default_filters
from .maintenance_indicators_filters import create_maintenance_indicators_filters

__all__ = [
    'create_energy_filters',
    'create_states_filters',
    'create_default_filters',
    'create_maintenance_indicators_filters'
]