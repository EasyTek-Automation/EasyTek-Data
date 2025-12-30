# pages/reports.py (MANTER TEMPORARIAMENTE)
"""
DEPRECATED: Este arquivo será removido na fase 6.
Use pages/reports/reports
"""
import warnings
warnings.warn(
    "pages/reports.py está deprecated. Use pages/reports/reports.py",
    DeprecationWarning,
    stacklevel=2
)

# Importar tudo do novo local
from src.pages.reports.reports import *