# src/api/__init__.py
"""
API REST Blueprint para AMG_Data
Fornece endpoints JSON para consumo mobile
"""

from flask import Blueprint

# Blueprint principal da API v1
api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

# Importar rotas (isso registra os endpoints)
from . import auth, producao
