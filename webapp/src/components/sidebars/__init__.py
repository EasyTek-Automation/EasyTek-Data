# src/components/sidebars/__init__.py

"""
Módulo de conteúdos para a sidebar da aplicação.
Cada página pode ter seu próprio conjunto de itens na sidebar.
"""

from .dashboard_sidebar import create_dashboard_sidebar_content
from .states_sidebar import create_states_sidebar_content
from .superv_sidebar import create_superv_sidebar_content
from .default_sidebar import create_default_sidebar_content
from .energy_sidebar import (
    create_se03_cost_sidebar_content,
    create_energy_sidebar_no_config,
    create_default_energy_sidebar_content
)

__all__ = [
    'create_dashboard_sidebar_content',
    'create_states_sidebar_content',
    'create_superv_sidebar_content',
    'create_default_sidebar_content',
    'create_se03_cost_sidebar_content',
    'create_energy_sidebar_no_config',
    'create_default_energy_sidebar_content'
]