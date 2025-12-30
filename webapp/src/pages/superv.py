# pages/superv.py (MANTER TEMPORARIAMENTE)
"""
DEPRECATED: Este arquivo será removido na fase 6.
Use pages/supervision/control
"""
import warnings
warnings.warn(
    "pages/superv.py está deprecated. Use pages/supervision/control.py",
    DeprecationWarning,
    stacklevel=2
)

# Importar tudo do novo local
from src.pages.supervision.control import *