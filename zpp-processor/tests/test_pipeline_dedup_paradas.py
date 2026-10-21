"""Regressão do bug 2026-10-16: parada descartada por dedup sem o dia.

Ordem 10624555 (LONGI001) atravessou dois dias com causa 201 começando às 06:15
em 06/10 (345 min) e 07/10 (405 min). A chave de dedup e o índice único não
tinham inicio_execucao, então a parada de 07/10 era descartada sem aviso.
"""
from datetime import datetime

import pytest

from pipeline import _dedup_records, ensure_indexes


def _parada(dia: int, duracao: int) -> dict:
    return {
        "centro_de_trabalho": "LONGI001",
        "ordem": "10624555",
        "inicio_execucao": datetime(2026, 10, dia, 6, 15),
        "inicio_real_hora": "06:15:00",
        "causa_do_desvio": "201",
        "duration_min": duracao,
    }


def test_dedup_mantem_mesma_parada_em_dias_diferentes():
    records, duplicatas = _dedup_records([_parada(6, 345), _parada(7, 405)], "zppparadas")
    assert duplicatas == 0
    assert sorted(r["duration_min"] for r in records) == [345, 405]


def test_dedup_remove_duplicata_do_mesmo_dia_mantendo_ultima():
    records, duplicatas = _dedup_records([_parada(7, 400), _parada(7, 405)], "zppparadas")
    assert duplicatas == 1
    assert [r["duration_min"] for r in records] == [405]


def test_indice_unico_aceita_dias_diferentes_e_barra_mesmo_dia():
    mongomock = pytest.importorskip("mongomock")
    db = mongomock.MongoClient()["db"]
    ensure_indexes(db, "ZPP_Paradas", "zppparadas")
    col = db["ZPP_Paradas"]

    idx = col.index_information()["idx_unique_paradas_v2"]
    assert idx["unique"]
    assert [k for k, _ in idx["key"]] == [
        "centro_de_trabalho", "ordem", "inicio_execucao", "inicio_real_hora", "causa_do_desvio",
    ]

    col.insert_many([_parada(6, 345), _parada(7, 405)])
    assert col.count_documents({}) == 2

    from pymongo.errors import DuplicateKeyError
    with pytest.raises(DuplicateKeyError):
        col.insert_one(_parada(7, 405))
