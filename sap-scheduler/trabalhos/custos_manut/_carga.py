# -*- coding: utf-8 -*-
"""Carga idempotente no Mongo: delete fonte='sap' por mes_referencia (janela) + insert."""
from __future__ import annotations


def gravar(db, coll: str, docs: list) -> int:
    meses = sorted({d["mes_referencia"] for d in docs if d.get("mes_referencia")})
    db[coll].delete_many({"mes_referencia": {"$in": meses}, "fonte": "sap"})
    if docs:
        db[coll].insert_many(docs)
    return len(docs)
