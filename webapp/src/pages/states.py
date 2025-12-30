# pages/states.py (MANTER TEMPORARIAMENTE)
"""
DEPRECATED: Este arquivo será removido na fase 6.
Use pages/production/reports
"""
import warnings
warnings.warn(
    "pages/states.py está deprecated. Use pages/production/states.py",
    DeprecationWarning,
    stacklevel=2
)

# Importar tudo do novo local
from src.pages.production.states import *