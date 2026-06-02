"""Mongo helpers do sap-scheduler — webapp side (DS-03 + IM-A2).

Contém as 3 operações que o webapp executa contra a collection `sap_jobs`:
- ensure_indexes  → boot (DS-02 RF-02-17..19)
- insert_job_pendente → OP-01 (tick do APScheduler em cron.py)
- find_ultimo_concluido_por_tipo → OP-05 (callback do rodapé)

Reusa a conexão Mongo singleton do webapp via `database.connection.get_mongo_connection`
(DS-03 — RV-01 F-01-02). Nunca cria MongoClient próprio.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import pytz

try:
    from src.database.connection import get_mongo_connection
except ImportError:
    from database.connection import get_mongo_connection

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION = "sap_jobs"


def get_db():
    """Retorna handle do database Mongo do webapp (singleton).

    Retorna `None` se Mongo estiver offline no boot — chamadores devem
    verificar e cair em fallback (DS-03: cron não inicia; callback usa fallback).
    """
    coll = get_mongo_connection(DEFAULT_COLLECTION, silent=True)
    if coll is None:
        return None
    return coll.database


def ensure_indexes(db, collection_name: str = DEFAULT_COLLECTION) -> None:
    """Cria os 2 índices canônicos da `sap_jobs` (DS-02 / IM-A1).

    Idempotente — pymongo `create_index` não duplica se já existir com mesma definição.
    Chamado no boot do webapp E do daemon (defesa em profundidade).
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
    logger.info("sap_scheduler: indices garantidos em '%s'", collection_name)


def insert_job_pendente(
    db,
    tipo: str,
    agendado_para_utc: datetime,
    collection_name: str = DEFAULT_COLLECTION,
) -> str:
    """OP-01 (DS-02): insere doc novo em estado `pendente`.

    Retorna o `_id` (string) do doc inserido. Cron usa pra log de auditoria.
    Não verifica idempotência aqui — chamador (cron `_existe_doc_hoje`) faz.
    """
    agora_utc = datetime.now(tz=pytz.UTC)
    doc = {
        "tipo": tipo,
        "parametros": {},
        "status": "pendente",
        "agendado_para": agendado_para_utc,
        "criado_em": agora_utc,
        "iniciado_em": None,
        "concluido_em": None,
        "resultado": None,
        "erro": None,
    }
    result = db[collection_name].insert_one(doc)
    return str(result.inserted_id)


def find_ultimo_concluido_por_tipo(
    db,
    tipo: str,
    collection_name: str = DEFAULT_COLLECTION,
) -> Optional[dict]:
    """OP-05 (DS-02): retorna doc do último `concluido` daquele `tipo`.

    Projeção mínima — só `concluido_em` e `resultado.path_xlsx` (callback
    do rodapé não precisa do resto). Retorna `None` se não houver doc.
    """
    return db[collection_name].find_one(
        {"tipo": tipo, "status": "concluido"},
        sort=[("concluido_em", -1)],
        projection={"concluido_em": 1, "resultado.path_xlsx": 1},
    )


def existe_doc_hoje(
    db,
    tipo: str,
    dia_inicio_utc: datetime,
    dia_fim_utc: datetime,
    collection_name: str = DEFAULT_COLLECTION,
) -> bool:
    """Defesa anti duplo-insert (DS-03 — cron tick).

    Verifica se já existe doc daquele `tipo` com `agendado_para` na janela do dia.
    Cobre o cenário de tick disparar 2× na mesma janela (restart no instante errado).
    """
    return (
        db[collection_name].find_one(
            {
                "tipo": tipo,
                "agendado_para": {"$gte": dia_inicio_utc, "$lt": dia_fim_utc},
            },
            projection={"_id": 1},
        )
        is not None
    )
