"""Cadastro de gatilhos de duração de parada por equipamento.

Coleção Mongo `maintenance_breakdown_thresholds`:
- equipment_id: nome amigável do equipamento (ex: "LCL-08", "PRENSA-01")
- threshold_min: int, gatilho_1 em minutos
- updated_at: datetime
- updated_by: username

gatilho_2 é derivado: gatilho_1 × 1.20 (não persiste).

Pintura na UI (mes-top + tabela do dia):
- duração ≥ gatilho_1 → amarelo
- duração ≥ gatilho_2 → rosa (sobrescreve amarelo)

Quando equipment não cadastrado: usa DEFAULT_THRESHOLD_MIN.
"""
from __future__ import annotations

import logging
import time as _time
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger("breakdown_thresholds")

COLLECTION = "maintenance_breakdown_thresholds"
DEFAULT_THRESHOLD_MIN = 200
TOOL_MULT = 1.20  # gatilho_2 = gatilho_1 × 1.20

_CACHE_TTL_SECONDS = 60
_cache: Dict[str, tuple] = {"all": (0, None)}


def _get_collection():
    """Retorna a coleção Mongo ou None se offline."""
    try:
        from src.database.connection import get_mongo_connection
        return get_mongo_connection(COLLECTION)
    except Exception as e:
        logger.warning("Mongo offline pra thresholds: %s", e)
        return None


def derive_threshold_2(threshold_1: float) -> int:
    """gatilho_2 = gatilho_1 × 1.20, arredondado pra int."""
    return int(round(threshold_1 * TOOL_MULT))


def get_all_thresholds() -> Dict[str, int]:
    """Retorna dict {equipment_id: threshold_min} de tudo cadastrado.

    Com cache process-level (TTL 60s). Fallback: dict vazio.
    """
    entry = _cache.get("all")
    if entry and entry[0] and (_time.time() - entry[0]) < _CACHE_TTL_SECONDS:
        return entry[1]
    col = _get_collection()
    if col is None:
        _cache["all"] = (_time.time(), {})
        return {}
    try:
        docs = col.find({}, {"_id": 0, "equipment_id": 1, "threshold_min": 1})
        out = {d["equipment_id"]: int(d["threshold_min"]) for d in docs if "equipment_id" in d}
        _cache["all"] = (_time.time(), out)
        return out
    except Exception as e:
        logger.warning("get_all_thresholds falhou: %s", e)
        _cache["all"] = (_time.time(), {})
        return {}


def get_threshold(equipment_id: str) -> int:
    """Retorna gatilho_1 do equipamento; default se ausente."""
    return get_all_thresholds().get(equipment_id, DEFAULT_THRESHOLD_MIN)


def get_thresholds_pair(equipment_id: str) -> tuple:
    """Retorna (gatilho_1, gatilho_2) — gatilho_2 derivado."""
    t1 = get_threshold(equipment_id)
    return t1, derive_threshold_2(t1)


def set_threshold(equipment_id: str, threshold_min: int, updated_by: Optional[str] = None) -> bool:
    """Cria/atualiza gatilho do equipamento. Invalida cache."""
    if not equipment_id or threshold_min is None:
        return False
    try:
        threshold_int = int(threshold_min)
    except (TypeError, ValueError):
        return False
    if threshold_int < 1:
        return False
    col = _get_collection()
    if col is None:
        return False
    try:
        col.update_one(
            {"equipment_id": equipment_id},
            {"$set": {
                "equipment_id": equipment_id,
                "threshold_min": threshold_int,
                "updated_at": datetime.utcnow(),
                "updated_by": updated_by or "unknown",
            }},
            upsert=True,
        )
        invalidate_cache()
        return True
    except Exception as e:
        logger.warning("set_threshold(%s, %s) falhou: %s", equipment_id, threshold_int, e)
        return False


def invalidate_cache() -> None:
    """Limpa o cache. Chamar após set_threshold ou ao botão refresh."""
    _cache["all"] = (0, None)
