# pages/register.py (MANTER TEMPORARIAMENTE)
"""
DEPRECATED: Este arquivo será removido na fase 6.
Use src.pages.auth.register
"""
import warnings
warnings.warn(
    "pages/register.py está deprecated. Use pages/auth/register.py",
    DeprecationWarning,
    stacklevel=2
)

# Importar tudo do novo local
from src.pages.auth.register import *