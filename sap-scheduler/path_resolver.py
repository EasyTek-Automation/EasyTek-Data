"""Cálculo de `path_xlsx` + validação da pasta destino (DS-04 + IM-E2)."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path


def calcular(tipo: str, agora_brt: datetime, pasta_input: Path) -> str:
    """SP-04 RF-04-13: `<PASTA>\\<tipo>_<YYYYMMDD>_<HHMMSS>.xlsx`.

    Windows: separadores `\\` no retorno. Linux: `/`. Path nativo.
    """
    fname = f"{tipo}_{agora_brt.strftime('%Y%m%d_%H%M%S')}.xlsx"
    return str(pasta_input / fname)


def validar_pasta(pasta: Path) -> None:
    """SP-04 RF-04-14: pasta existe E é gravável.

    Levanta `OSError` se inválida — executor classifica como `salvamento`.
    """
    if not pasta.exists():
        raise OSError(f"pasta destino nao existe: {pasta}")
    if not pasta.is_dir():
        raise OSError(f"caminho nao e diretorio: {pasta}")
    if not os.access(str(pasta), os.W_OK):
        raise OSError(f"pasta sem permissao de escrita: {pasta}")
