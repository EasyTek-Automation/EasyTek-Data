# pages/dashboard.py (MANTER TEMPORARIAMENTE)
"""
DEPRECATED: Este arquivo será removido na fase 6.
Use pages/dashboards/production_oee
"""
import warnings
warnings.warn(
    "pages/dashboard.py está deprecated. Use pages/dashboards/production_oee.py",
    DeprecationWarning,
    stacklevel=2
)

# Importar tudo do novo local
from src.pages.dashboards.production_oee import *