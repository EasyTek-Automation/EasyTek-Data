# pages/login.py (MANTER TEMPORARIAMENTE)
"""
DEPRECATED: Este arquivo será removido na fase 6.
Use src.pages.auth.login
"""
import warnings
warnings.warn(
    "pages/login.py está deprecated. Use pages/auth/login.py",
    DeprecationWarning,
    stacklevel=2
)

# Importar tudo do novo local
from src.pages.auth.login import *