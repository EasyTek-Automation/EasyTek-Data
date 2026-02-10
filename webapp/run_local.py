# webapp/run_local.py
"""
Script para rodar a aplicação localmente em modo de desenvolvimento.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Adiciona o diretório atual ao PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

# Carrega variáveis de ambiente do arquivo .env
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Configura logging ANTES de qualquer importação da aplicação
from src.config.logging_config import setup_logging
setup_logging()

# Verifica variáveis obrigatórias
required_vars = ['MONGO_URI', 'DB_NAME', 'SECRET_KEY']
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    print("[ERRO] Variaveis de ambiente faltando:")
    for var in missing_vars:
        print(f"   - {var}")
    print("\nCrie um arquivo .env na raiz do projeto com as variaveis necessarias")
    exit(1)

print("[OK] Variaveis de ambiente carregadas com sucesso!")
print(f"   - MongoDB: {os.getenv('MONGO_URI')}")
print(f"   - Database: {os.getenv('DB_NAME')}")
print(f"   - Gateway: {os.getenv('GATEWAY_URL', 'http://localhost:5001')}")

# Importa e roda a aplicação
if __name__ == '__main__':
    from src.run import app, server

    port = int(os.environ.get("PORT", 8050))
    print(f"\n[START] Iniciando servidor em http://localhost:{port}")
    print("   Pressione CTRL+C para parar\n")
    
    # MUDANÇA AQUI: run() ao invés de run_server()
    app.run(
        debug=False,
        host='0.0.0.0',
        port=port,
        dev_tools_hot_reload=True
    )