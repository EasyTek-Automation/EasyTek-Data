# -*- coding: utf-8 -*-
"""Snapshot atômico das collections-fonte de HH no Mongo (mesma estratégia do backlog).

Insere os docs da coleta nova (carimbados com `coleta_id`), remove coletas antigas
(preserva o doc `_id="meta"`) e atualiza o doc meta (frescor/ponteiro). A leitura nunca
vê snapshot pela metade (insere antes de apagar).
"""
from __future__ import annotations

META_ID = "meta"


def gravar_snapshot(db, coll: str, docs: list, coleta_id: str, coletado_em) -> int:
    """Substitui o snapshot da collection de HH de forma atômica-na-prática. Retorna nº de docs."""
    c = db[coll]
    if docs:
        c.insert_many(docs)
    c.delete_many({"_id": {"$ne": META_ID}, "coleta_id": {"$ne": coleta_id}})
    c.update_one(
        {"_id": META_ID},
        {"$set": {"coleta_id_atual": coleta_id, "coletado_em": coletado_em, "total": len(docs)}},
        upsert=True,
    )
    return len(docs)


def ensure_indexes(db, coll: str) -> None:
    """Índices das collections de HH (idempotente). Chave de operação + coleta + ordem."""
    c = db[coll]
    c.create_index([("coleta_id", 1)], name="idx_coleta")
    c.create_index([("ordem", 1)], name="idx_ordem")
    c.create_index([("ordem", 1), ("operacao", 1)], name="idx_ordem_op")
