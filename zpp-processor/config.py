"""
Configurações centralizadas do serviço ZPP Processor
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# MongoDB
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME    = os.getenv("DB_NAME")

# Serviço
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
PORT      = int(os.getenv("PORT", 5002))

# Diretórios de trabalho (volumes montados)
BASE_DATA_DIR = Path(os.getenv("BASE_DATA_DIR", "/data"))
INPUT_DIR    = BASE_DATA_DIR / "input"
OUTPUT_DIR   = BASE_DATA_DIR / "output"
REJECTED_DIR = BASE_DATA_DIR / "rejected"
LOGS_DIR     = BASE_DATA_DIR / "logs"

# Processamento
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 1000))

# Scheduler — intervalo em segundos (padrão: 1 hora)
SCHEDULER_INTERVAL_SECONDS = int(os.getenv("SCHEDULER_INTERVAL_SECONDS", 3600))

# Regra de campo de referência para cálculo do mês de referência
# "fim"    → zppprd usa ffinnotif,  zppparadas usa fim_execucao
# "inicio" → zppprd usa fininotif,  zppparadas usa inicio_execucao
MONTH_BOUNDARY_RULE = os.getenv("MONTH_BOUNDARY_RULE", "fim")

MONTH_BOUNDARY_RULE_FIELD = {
    "fim": {
        "zppprd":     "ffinnotif",
        "zppparadas": "fim_execucao",
    },
    "inicio": {
        "zppprd":     "fininotif",
        "zppparadas": "inicio_execucao",
    },
}

# Threshold mínimo de ratio do mês dominante na janela de tolerância (dia 1).
# Arquivos com menos que esse percentual no mês dominante são rejeitados.
MIN_REFERENCE_MONTH_RATIO = float(os.getenv("MIN_REFERENCE_MONTH_RATIO", "0.80"))

# URL interna do webapp para validação de sessão
WEBAPP_INTERNAL_URL = os.getenv("WEBAPP_INTERNAL_URL", "http://webapp:8050")

# Collection names
LOGS_COLLECTION = "zpp_processing_logs"


def get_reference_field(file_type: str) -> str:
    """Retorna o campo de referência para o tipo e regra configurada."""
    return MONTH_BOUNDARY_RULE_FIELD[MONTH_BOUNDARY_RULE][file_type]


def validate_config() -> list[str]:
    """Valida se as configurações essenciais estão presentes."""
    errors = []
    if not MONGO_URI:
        errors.append("MONGO_URI não configurado")
    if not DB_NAME:
        errors.append("DB_NAME não configurado")
    if MONTH_BOUNDARY_RULE not in MONTH_BOUNDARY_RULE_FIELD:
        errors.append(f"MONTH_BOUNDARY_RULE inválido: '{MONTH_BOUNDARY_RULE}' (valores aceitos: fim, inicio)")
    return errors
