"""
Configurações centralizadas do serviço ZPP Processor
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configurações MongoDB
MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DB_NAME')

# Configurações do serviço
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
PORT = int(os.getenv('PORT', 5002))

# Diretórios de trabalho (volumes montados)
BASE_DATA_DIR = Path(os.getenv('BASE_DATA_DIR', '/data'))
INPUT_DIR = BASE_DATA_DIR / 'input'
OUTPUT_DIR = BASE_DATA_DIR / 'output'
LOGS_DIR = BASE_DATA_DIR / 'logs'

# Configurações de processamento
BATCH_SIZE = int(os.getenv('BATCH_SIZE', 1000))
ARCHIVE_DIR_NAME = 'output'  # Arquivos processados vão para /data/output

# Configurações de agendamento automático
AUTO_PROCESS = os.getenv('AUTO_PROCESS', 'true').lower() == 'true'
INTERVAL_MINUTES = int(os.getenv('INTERVAL_MINUTES', 60))

# Validação de configuração essencial
def validate_config():
    """Valida se as configurações essenciais estão presentes"""
    errors = []

    if not MONGO_URI:
        errors.append("MONGO_URI não configurado")
    if not DB_NAME:
        errors.append("DB_NAME não configurado")

    return errors

# Collection names para configurações
CONFIG_COLLECTION = 'zpp_processor_config'
LOGS_COLLECTION = 'zpp_processing_logs'
