# src/run.py
"""
Ponto de entrada da aplicação.
Este arquivo é usado tanto pelo Gunicorn (produção) quanto pelo run_local.py (desenvolvimento).
"""

# PASSO 1: INICIALIZAÇÃO DO TEMPLATE
from dash_bootstrap_templates import load_figure_template
load_figure_template("minty")

# PASSO 2: IMPORTAÇÕES
import os
from src.app import app, server
from src import index  # Registra os callbacks

# PASSO 3: EXECUÇÃO (apenas para debug direto, não usado com run_local.py)
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8050))
    app.run_server(debug=True, host='0.0.0.0', port=port)