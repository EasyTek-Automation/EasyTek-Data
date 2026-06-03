"""Storage do sap-scheduler — encapsula as 3 operacoes canonicas sobre
`sap_scheduler_config` (collection singleton no Mongo).

Operacoes (DS-06):
- OP-CONFIG-01: read_config_singleton  -> chamada pelo `_tick` a cada 60s
- OP-CONFIG-02: atualizar_agendamento  -> chamada pela UI admin (SP-09)
- OP-CONFIG-03: bootstrap_config       -> chamada no boot do webapp

Sem cache em memoria, sem retry, sem ORM — dicts crus. Custo de read e
desprezivel (1x por 60s) e simplifica raciocinio.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

try:
    from src.database.connection import get_mongo_connection
except ImportError:
    from database.connection import get_mongo_connection  # type: ignore

COLLECTION_NAME = "sap_scheduler_config"
SINGLETON_ID = "singleton"
HISTORICO_MAX = 20
VERSAO_SCHEMA = 1

DEFAULT_AGENDAMENTOS: list[dict] = [
    {"tipo": "zppprd", "hora": "03:30", "ativo": True},
    {"tipo": "zpp_nt0001", "hora": "03:30", "ativo": True},
]


def _coll(collection_name: str = COLLECTION_NAME):
    """Retorna a Collection do Mongo; usa o singleton de conexao do webapp."""
    return get_mongo_connection(collection_name)


def read_config_singleton(collection_name: str = COLLECTION_NAME) -> Optional[dict]:
    """OP-CONFIG-01 — chamada pelo `_tick` a cada 60s (RF-07-14).

    Retorna o doc completo ou None se collection vazia.
    Nao levanta excecao por absent — caller decide (cron usa fallback hardcoded).
    """
    coll = _coll(collection_name)
    if coll is None:
        return None
    return coll.find_one({"_id": SINGLETON_ID})


def atualizar_agendamento(
    novos: list[dict],
    quem: str,
    antes: list[dict],
    collection_name: str = COLLECTION_NAME,
) -> None:
    """OP-CONFIG-02 — chamada pela UI admin ao salvar (RF-07-15).

    Args:
        novos: lista validada de agendamentos (validators.py ja validou).
        quem: identificador do admin (vem do dcc.Store, NAO de current_user).
        antes: snapshot do agendamentos anterior (lido via read_config_singleton).
        collection_name: nome da collection (override em teste).

    NAO valida — caller (callback) ja validou via `validar_agendamentos`.
    Idempotencia via historico FIFO com `$slice: 20`.

    `upsert=False` proposital — bootstrap e responsabilidade separada
    (`bootstrap_config`); forca UI a ter doc existente.
    """
    coll = _coll(collection_name)
    if coll is None:
        raise RuntimeError("Mongo indisponivel — atualizar_agendamento abortado")

    agora = datetime.utcnow()
    coll.update_one(
        {"_id": SINGLETON_ID},
        {
            "$set": {
                "agendamentos": novos,
                "atualizado_em": agora,
            },
            "$push": {
                "historico_alteracoes": {
                    "$each": [
                        {
                            "em": agora,
                            "quem": quem,
                            "antes": antes,
                            "depois": novos,
                        }
                    ],
                    "$position": 0,
                    "$slice": HISTORICO_MAX,
                }
            },
        },
        upsert=False,
    )


def bootstrap_config(
    seed_agendamentos: Optional[list[dict]] = None,
    collection_name: str = COLLECTION_NAME,
) -> None:
    """OP-CONFIG-03 — chamada no boot do webapp antes de scheduler.start (RF-07-16).

    Idempotente: multiplos workers gunicorn correndo simultaneamente e seguro
    (`$setOnInsert` garante 1 doc nasce, demais viram no-op).

    Args:
        seed_agendamentos:
            - None  -> usa DEFAULT_AGENDAMENTOS hardcoded (03:30, ambos ativos).
            - lista -> usa como seed (vinda da env var antiga `SAP_JOBS_AGENDADOS`).
        collection_name: nome da collection (override em teste).

    NUNCA sobrescreve doc existente (RF-07-20).
    """
    coll = _coll(collection_name)
    if coll is None:
        raise RuntimeError("Mongo indisponivel — bootstrap_config abortado")

    seed = seed_agendamentos if seed_agendamentos else DEFAULT_AGENDAMENTOS
    coll.update_one(
        {"_id": SINGLETON_ID},
        {
            "$setOnInsert": {
                "agendamentos": seed,
                "historico_alteracoes": [],
                "atualizado_em": datetime.utcnow(),
                "versao_schema": VERSAO_SCHEMA,
            }
        },
        upsert=True,
    )
