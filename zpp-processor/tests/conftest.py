"""Adiciona o diretório do serviço ao sys.path para importar módulos diretamente."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
