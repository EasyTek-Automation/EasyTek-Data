"""Mongo helpers do sap-scheduler — webapp side.

Operacoes ativas:
- ensure_indexes                  -> boot (DS-02 refresh / DS-07: 3 indices, 1 unique)
- find_ultimo_concluido_por_tipo  -> OP-05 (callback do rodape — Bloco C, intocado)

Operacoes REMOVIDAS na expansao de escopo (DC-03-R-03):
- existe_doc_hoje      -> substituida por unique index `idx_dedup_agendamento` (DS-07)
- insert_job_pendente  -> substituida por `_tick_inserir_job_atomico` em cron.py (DS-07)

Reusa a conexao Mongo singleton do webapp via `database.connection.get_mongo_connection`
(DS-03 — RV-01 F-01-02). Nunca cria MongoClient proprio.
"""
from __future__ import annotations

import logging
from typing import Optional

try:
    from src.database.connection import get_mongo_connection
except ImportError:
    from database.connection import get_mongo_connection  # type: ignore

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION = "sap_jobs"


def get_db():
    """Retorna handle do database Mongo do webapp (singleton).

    Retorna `None` se Mongo estiver offline no boot — chamadores devem
    verificar e cair em fallback (DS-03: cron nao inicia; callback usa fallback).
    """
    coll = get_mongo_connection(DEFAULT_COLLECTION, silent=True)
    if coll is None:
        return None
    return coll.database


def ensure_indexes(db, collection_name: str = DEFAULT_COLLECTION) -> None:
    """Cria os 3 indices canonicos da `sap_jobs` (DS-02 refresh + DS-07).

    Idempotente — `create_index` nao duplica se ja existir com mesma definicao.
    Chamado no boot do webapp E do daemon (BR-09 #7 — defesa em profundidade).

    Indices:
    - idx_polling                 (status, agendado_para)     non-unique  -> daemon claim
    - idx_ultimo_por_tipo         (tipo, concluido_em desc)   non-unique  -> rodape webapp
    - idx_dedup_agendamento       (tipo, agendado_para)       UNIQUE       -> dedup atomico do insert (DS-07)

    O unique index resolve o bug A-06 (4 workers gunicorn x BackgroundScheduler -> 4x duplicacao).
    Idempotencia via unique index — caller (cron) faz try/except DuplicateKeyError.
    """
    coll = db[collection_name]
    coll.create_index(
        [("status", 1), ("agendado_para", 1)],
        name="idx_polling",
    )
    coll.create_index(
        [("tipo", 1), ("concluido_em", -1)],
        name="idx_ultimo_por_tipo",
    )
    coll.create_index(
        [("tipo", 1), ("agendado_para", 1)],
        name="idx_dedup_agendamento",
        unique=True,
    )
    logger.info(
        "sap_scheduler: 3 indices garantidos em '%s' (idx_polling, "
        "idx_ultimo_por_tipo, idx_dedup_agendamento unique)",
        collection_name,
    )


def find_ultimo_concluido_por_tipo(
    db,
    tipo: str,
    collection_name: str = DEFAULT_COLLECTION,
) -> Optional[dict]:
    """OP-05 (DS-02): retorna doc do ultimo `concluido` daquele `tipo`.

    Projecao minima — so `concluido_em` e `resultado.path_xlsx` (callback
    do rodape nao precisa do resto). Retorna `None` se nao houver doc.
    """
    return db[collection_name].find_one(
        {"tipo": tipo, "status": "concluido"},
        sort=[("concluido_em", -1)],
        projection={"concluido_em": 1, "resultado.path_xlsx": 1},
    )
