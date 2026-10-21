"""Detecção de órfãos no boot (DS-04 + IM-D2). Wrapper sobre `mongo.detectar_orfaos`."""
from __future__ import annotations

import logging

from . import mongo

logger = logging.getLogger(__name__)


def detectar_e_logar(db, collection_name: str = "sap_jobs", idade_minima_horas: int = 1) -> int:
    """Chama OP-06 no boot: marca órfãos (`executando` há >N h) como `falhou` e loga (self-heal —
    revisado 2026-07-28, ver `mongo.detectar_orfaos`). Nome mantido por retrocompat do import."""
    return mongo.detectar_orfaos(db, idade_minima_horas=idade_minima_horas, collection_name=collection_name)
