# -*- coding: utf-8 -*-
"""Snapshot atômico do backlog no Mongo (DS-02).

Estratégia: insere todos os docs da coleta nova (carimbados com `coleta_id`),
depois remove os docs de coletas anteriores, e por fim atualiza o doc de controle
`_id="meta"`. A página nunca lê um snapshot pela metade (insere antes de apagar).
"""
from __future__ import annotations

META_ID = "meta"


def gravar_snapshot(db, coll: str, docs: list, coleta_id: str, coletado_em) -> int:
    """Substitui o snapshot do backlog de forma atômica-na-prática.

    1. insere os docs novos (coleta_id atual);
    2. remove docs de coletas antigas (preserva o doc meta);
    3. atualiza o doc meta de controle (frescor / ponteiro do snapshot atual).

    Retorna a quantidade de ordens gravadas.
    """
    c = db[coll]
    if docs:
        c.insert_many(docs)
    # remove snapshots anteriores; nunca apaga o doc de controle
    c.delete_many({"_id": {"$ne": META_ID}, "coleta_id": {"$ne": coleta_id}})
    # ponteiro + frescor (DS-11)
    c.update_one(
        {"_id": META_ID},
        {"$set": {"coleta_id_atual": coleta_id, "coletado_em": coletado_em, "total": len(docs)}},
        upsert=True,
    )
    return len(docs)


def ensure_indexes(db, coll: str) -> None:
    """Índices da `sap_backlog` (DS-02). Idempotente — chamável no boot/coleta."""
    c = db[coll]
    c.create_index([("coleta_id", 1)], name="idx_coleta")
    c.create_index([("categoria", 1)], name="idx_categoria")
    c.create_index([("disciplina", 1)], name="idx_disciplina")
    c.create_index([("subclassificacao", 1)], name="idx_subclass")
    c.create_index([("data_inicio", 1)], name="idx_data_inicio")
    c.create_index([("ordem", 1)], name="idx_ordem")
