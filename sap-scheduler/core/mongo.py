"""Mongo helpers do daemon sap-scheduler — Windows side (DS-04 + IM-A3).

Implementa as operações que o daemon executa contra `sap_jobs`:
- connect          → boot
- ensure_indexes   → boot (defesa em profundidade com webapp)
- claim_atomico    → OP-02 (loop principal)
- update_concluido → OP-03 (fim de exec OK)
- update_falhou    → OP-04 (fim de exec KO)
- detectar_orfaos  → OP-06 (boot — marca órfãos 'executando' antigos como 'falhou'; self-heal)

Conexão própria via `MongoClient` (daemon não compartilha MongoClient com webapp —
deploy independente). Tipo `Database` retornado pra ser passado adiante.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Iterable, Optional

import pytz
from pymongo import MongoClient, ReturnDocument
from pymongo.database import Database
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)


def connect(mongo_uri: str, db_name: str, timeout_ms: int = 30000) -> Database:
    """Abre conexão Mongo + força ping pra falhar rápido se offline.

    Levanta `PyMongoError` (subclasse `ServerSelectionTimeoutError`) se Mongo
    inacessível no boot — `daemon.py` captura e faz `sys.exit(1)` (SP-03 RF-03-06).
    """
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=timeout_ms)
    client.admin.command("ping")
    logger.info("daemon: conexao Mongo OK | db=%s", db_name)
    return client[db_name]


def ensure_indexes(db: Database, collection_name: str = "sap_jobs") -> None:
    """Cria os 2 índices canônicos da `sap_jobs` (IM-A1).

    Idempotente — mesma definição literal do webapp (`mongo_helpers.ensure_indexes`).
    Chamado no boot do daemon como defesa em profundidade.
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
    logger.info("daemon: indices garantidos em '%s'", collection_name)


def claim_atomico(
    db: Database,
    tipos_suportados: Iterable[str],
    collection_name: str = "sap_jobs",
) -> Optional[dict]:
    """OP-02 (DS-02): claim atômico via `find_one_and_update`.

    Filtra docs `pendente` com `agendado_para` no passado E `tipo` na whitelist;
    marca como `executando` + `iniciado_em` agora UTC; retorna doc atualizado.
    `sort=[("agendado_para", 1)]` garante FIFO (SP-03 RF-03-10).
    Retorna `None` se fila vazia.
    """
    agora_utc = datetime.now(tz=pytz.UTC)
    return db[collection_name].find_one_and_update(
        filter={
            "status": "pendente",
            "agendado_para": {"$lte": agora_utc},
            "tipo": {"$in": list(tipos_suportados)},
        },
        update={"$set": {"status": "executando", "iniciado_em": agora_utc}},
        sort=[("agendado_para", 1)],
        return_document=ReturnDocument.AFTER,
    )


def update_concluido(
    db: Database,
    _id,
    resultado: dict,
    collection_name: str = "sap_jobs",
) -> bool:
    """OP-03 (DS-02): transita `executando → concluido` com filtro defensivo.

    Filtro `{_id, status:"executando"}` defende contra writeback em doc fora
    do estado esperado (DS-02 — transitions table). Retorna `True` se 1 doc
    foi modificado; `False` se filtro não bateu (loga WARNING — diagnóstico).
    """
    agora_utc = datetime.now(tz=pytz.UTC)
    result = db[collection_name].update_one(
        filter={"_id": _id, "status": "executando"},
        update={
            "$set": {
                "status": "concluido",
                "concluido_em": agora_utc,
                "resultado": resultado,
            }
        },
    )
    if result.modified_count == 0:
        logger.warning(
            "daemon: update_concluido nao bateu filtro | _id=%s "
            "(doc fora de 'executando' ou nao existe)",
            _id,
        )
        return False
    return True


def update_falhou(
    db: Database,
    _id,
    erro: dict,
    collection_name: str = "sap_jobs",
) -> bool:
    """OP-04 (DS-02): transita `executando → falhou` com filtro defensivo.

    Mesma defesa de `update_concluido`. Doc `erro` deve estar conforme
    DS-02 subschema (`mensagem`, `tipo_excecao`, `fase`, `traceback_resumido?`)
    — validação contratual no chamador (`executor.executar_job`).
    """
    agora_utc = datetime.now(tz=pytz.UTC)
    result = db[collection_name].update_one(
        filter={"_id": _id, "status": "executando"},
        update={
            "$set": {
                "status": "falhou",
                "concluido_em": agora_utc,
                "erro": erro,
            }
        },
    )
    if result.modified_count == 0:
        logger.warning(
            "daemon: update_falhou nao bateu filtro | _id=%s "
            "(doc fora de 'executando' ou nao existe)",
            _id,
        )
        return False
    return True


def detectar_orfaos(
    db: Database,
    idade_minima_horas: int = 1,
    collection_name: str = "sap_jobs",
) -> int:
    """OP-06 (DS-02): detecta docs `executando` há mais de N horas (órfãos deixados por um
    reinício do daemon no meio de um job) e os marca como `falhou` — self-heal do boot.

    **Revisado 2026-07-28 (bug do backlog travado).** Antes esta função só logava (BR-02
    original: "boot não corrige"). Isso deixava um job órfão preso em `executando` para sempre,
    e o guard de deduplicação (`_existe_job_ativo`, no `manual_trigger`) bloqueava todo novo
    disparo daquele tipo — foi o que travou o backlog no "Atualizar agora". Agora ela **marca
    `falhou`** (via `update_falhou`, transição defensiva `executando → falhou`), liberando o tipo.

    Também corrige o `TypeError` de fuso: `iniciado_em` volta **naive** do Mongo (pymongo padrão),
    e era subtraído de um `now` **aware** — a subtração estourava e a detecção falhava toda vez.
    Passa a comparar em UTC-naive dos dois lados (com normalização defensiva se a conexão for
    tz-aware).

    Só age em jobs `executando` há mais de `idade_minima_horas` (default 1h). Uma coleta normal
    leva ~3min, então o limiar não pega job legítimo em andamento. Retorna a contagem de órfãos
    tratados (métrica).
    """
    agora = datetime.now(tz=pytz.UTC).replace(tzinfo=None)   # UTC-naive, como o Mongo devolve
    corte = agora - timedelta(hours=idade_minima_horas)
    cursor = db[collection_name].find(
        {"status": "executando", "iniciado_em": {"$lt": corte}},
        projection={"_id": 1, "tipo": 1, "iniciado_em": 1},
    )
    count = 0
    for doc in cursor:
        ini = doc["iniciado_em"]
        if getattr(ini, "tzinfo", None) is not None:        # defensivo (conexão tz_aware)
            ini = ini.astimezone(pytz.UTC).replace(tzinfo=None)
        idade_h = (agora - ini).total_seconds() / 3600
        erro = {
            "mensagem": (f"job órfão liberado no boot (status 'executando' há {idade_h:.1f}h — "
                         "o daemon reiniciou durante a execução)"),
            "tipo_excecao": "OrfaoReinicio",
            "fase": "boot_self_heal",
        }
        ok = update_falhou(db, doc["_id"], erro, collection_name)
        logger.warning(
            "daemon: orfao %s | _id=%s tipo=%s idade_h=%.2f",
            "marcado 'falhou'" if ok else "NAO liberado (não bateu filtro)",
            doc["_id"], doc.get("tipo", "?"), idade_h,
        )
        count += 1
    if count == 0:
        logger.info("daemon: nenhum orfao detectado (status='executando' antigo)")
    return count


def close(client: MongoClient) -> None:
    """Cleanup no shutdown gracioso (SP-03 RF-03-18)."""
    try:
        client.close()
    except PyMongoError:
        pass  # best-effort — saida em qualquer cenario
