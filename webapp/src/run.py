# src/run.py (Versão Simplificada)

# PASSO 1: INICIALIZAÇÃO DO TEMPLATE (Correto e essencial)
from dash_bootstrap_templates import load_figure_template
load_figure_template("darkly")

# PASSO 2: CONFIGURAÇÃO DE LOGGING (antes de importar app)
from src.config.logging_config import setup_logging
setup_logging()

# PASSO 3: IMPORTAÇÕES PADRÃO
import os
from src.app import app, server
from src import index # Esta importação dispara o registro dos callbacks

# PASSO 3: LÓGICA DE EXECUÇÃO
if __name__ == '__main__':
    # O Gunicorn não executa este bloco. É apenas para debug local.
    port = int(os.environ.get("PORT", 8050))
    # A flag debug=True já recarrega o servidor em caso de erro,
    # então a verificação explícita da conexão aqui não é estritamente necessária.
    app.run_server(debug=True, host='0.0.0.0', port=port)
