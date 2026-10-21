# -*- coding: utf-8 -*-
"""Carga idempotente no Mongo: delete fonte='sap' por mes_referencia (janela) + insert."""
from __future__ import annotations


def gravar(db, coll: str, docs: list) -> int:
    meses = sorted({d["mes_referencia"] for d in docs if d.get("mes_referencia")})
    db[coll].delete_many({"mes_referencia": {"$in": meses}, "fonte": "sap"})
    if docs:
        db[coll].insert_many(docs)
    return len(docs)


def gravar_componentes(db, coll: str, docs: list, ordens: list) -> int:
    """Carga idempotente dos componentes de ordem (BR-15). Idempotente **por ordem** (não por
    mês): apaga os componentes das ordens do lote (`fonte='sap'`) e reinsere. O mini-modal busca
    por ordem, e uma ordem tem o mesmo conjunto de itens baixados independente do mês da coleta.
    """
    ordens = sorted({(o or "").strip() for o in (ordens or []) if (o or "").strip()})
    if ordens:
        db[coll].delete_many({"ordem": {"$in": ordens}, "fonte": "sap"})
    if docs:
        db[coll].insert_many(docs)
    return len(docs)


def upsert_depara(db, coll: str, mapping: dict) -> int:
    """Upsert do de/para código→nome (1 doc por código, `_id`=código). Idempotente.

    Usado p/ AMG_CustoCentros / AMG_CustoContas: um rename no SAP atualiza a única linha
    do código → reflete em toda a tela (inclusive meses antigos). Só grava nome não-vazio.
    """
    n = 0
    for code, nome in (mapping or {}).items():
        if not code or not nome:
            continue
        db[coll].update_one({"_id": code}, {"$set": {"nome": nome}}, upsert=True)
        n += 1
    return n
