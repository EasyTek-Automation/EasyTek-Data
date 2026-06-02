"""Detecção de órfãos no boot (DS-04 + IM-D2). Wrapper sobre `mongo.detectar_orfaos`."""
from __future__ import annotations

import logging

from . import mongo

logger = logging.getLogger(__name__)


def detectar_e_logar(db, collection_name: str = "sap_jobs", idade_minima_horas: int = 1) -> int:
    """Chama OP-06 e retorna contagem. Logs WARN por doc (na própria `mongo.detectar_orfaos`)."""
    return mongo.detectar_orfaos(db, idade_minima_horas=idade_minima_horas, collection_name=collection_name)
