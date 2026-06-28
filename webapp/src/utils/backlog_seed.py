# -*- coding: utf-8 -*-
"""Bootstrap das collections do Backlog no boot do webapp (SDD Backlog).

Semeia `sap_ativos` (dimensão de ativos) e `sap_backlog` (snapshot inicial) a partir de
arquivos empacotados na imagem — só se as collections estiverem vazias. Garante que, após
`up.sh prod <tag>`, a página /maintenance/backlog funcione já com dado, sem passo manual.
Depois, a coleta do daemon (job `backlog`, 04:00 ou "Atualizar agora") substitui o snapshot,
e o job de refresh atualiza `sap_ativos`.

Race-safe entre os 4 workers gunicorn via claim atômico (`find_one_and_update` upsert).
Bootstrap-only: se já houver dado (ou o claim já existir), não toca.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime

from pymongo import ReturnDocument
from pymongo.errors import PyMongoError

try:
    from src.database.connection import get_mongo_connection
except ImportError:
    from database.connection import get_mongo_connection

logger = logging.getLogger(__name__)
_DATA = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_LOCK_COLL = "sap_seed_lock"


def _iso(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _claim(marcador: str) -> bool:
    """Claim atômico: True só para o worker que cria o marcador (semeia); demais → False."""
    lock = get_mongo_connection(_LOCK_COLL, silent=True)
    if lock is None:
        return False
    anterior = lock.find_one_and_update(
        {"_id": marcador}, {"$setOnInsert": {"em": datetime.utcnow()}},
        upsert=True, return_document=ReturnDocument.BEFORE)
    return anterior is None


def seed_sap_ativos():
    coll = get_mongo_connection("sap_ativos", silent=True)
    if coll is None:
        return
    try:
        if coll.estimated_document_count() > 0:
            return
        if not _claim("sap_ativos"):
            return
        path = os.path.join(_DATA, "sap_ativos_BR02.json")
        nodes = json.load(open(path, encoding="utf-8"))
        coll.insert_many([{"id": n["id"], "nivel": n["nivel"], "pai": n["pai"],
                           "descricao": n["descricao"], "tplnr": n["tplnr"],
                           "equnr": n["equnr"]} for n in nodes], ordered=False)
        coll.create_index([("id", 1)])
        coll.create_index([("tplnr", 1)])
        coll.create_index([("nivel", 1)])
        logger.info("seed sap_ativos: %d nós (bootstrap)", len(nodes))
    except (PyMongoError, OSError, ValueError) as e:
        logger.warning("seed sap_ativos falhou (segue boot): %s", e)


def seed_sap_backlog():
    coll = get_mongo_connection("sap_backlog", silent=True)
    if coll is None:
        return
    try:
        if coll.estimated_document_count() > 0:
            return
        if not _claim("sap_backlog"):
            return
        payload = json.load(open(os.path.join(_DATA, "sap_backlog_seed.json"), encoding="utf-8"))
        docs = []
        for d in payload.get("docs", []):
            d = dict(d)
            d["data_inicio"] = _iso(d.get("data_inicio"))
            d["coletado_em"] = _iso(d.get("coletado_em"))
            docs.append(d)
        if not docs:
            return
        coll.insert_many(docs, ordered=False)
        coll.update_one({"_id": "meta"}, {"$set": {
            "coleta_id_atual": payload.get("coleta_id"),
            "coletado_em": _iso(payload.get("coletado_em")),
            "total": len(docs)}}, upsert=True)
        for f in ("coleta_id", "categoria", "disciplina", "subclassificacao", "data_inicio", "ordem"):
            coll.create_index([(f, 1)])
        logger.info("seed sap_backlog: %d ordens (bootstrap)", len(docs))
    except (PyMongoError, OSError, ValueError) as e:
        logger.warning("seed sap_backlog falhou (segue boot): %s", e)


def bootstrap_backlog():
    """Semeia as duas collections do Backlog (idempotente). Chamado no boot do webapp."""
    seed_sap_ativos()
    seed_sap_backlog()
