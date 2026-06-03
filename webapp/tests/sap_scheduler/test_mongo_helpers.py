"""Testes do mongo_helpers.py refresh (DS-02 refresh + DS-07).

Cobre DT-07-01..02 do SDD sap-scheduler.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from src.sap_scheduler.mongo_helpers import ensure_indexes, find_ultimo_concluido_por_tipo


class TestEnsureIndexes:
    """3 indices criados; idempotente."""

    def test_dt_07_01_cria_3_indices(self):
        db = MagicMock()
        ensure_indexes(db)

        coll = db["sap_jobs"]
        # 3 chamadas a create_index
        assert coll.create_index.call_count == 3

        chamadas = coll.create_index.call_args_list
        # Indice 1: idx_polling
        args0, kw0 = chamadas[0]
        assert args0[0] == [("status", 1), ("agendado_para", 1)]
        assert kw0["name"] == "idx_polling"
        assert kw0.get("unique") is None  # non-unique

        # Indice 2: idx_ultimo_por_tipo
        args1, kw1 = chamadas[1]
        assert args1[0] == [("tipo", 1), ("concluido_em", -1)]
        assert kw1["name"] == "idx_ultimo_por_tipo"
        assert kw1.get("unique") is None

        # Indice 3: idx_dedup_agendamento UNIQUE (NOVO em DS-07)
        args2, kw2 = chamadas[2]
        assert args2[0] == [("tipo", 1), ("agendado_para", 1)]
        assert kw2["name"] == "idx_dedup_agendamento"
        assert kw2["unique"] is True

    def test_dt_07_02_idempotente(self):
        """2x ensure_indexes nao falha — pymongo create_index e idempotente."""
        db = MagicMock()
        ensure_indexes(db)
        ensure_indexes(db)
        # 3 indices x 2 chamadas = 6 calls; create_index real deduplicaria
        assert db["sap_jobs"].create_index.call_count == 6

    def test_collection_name_customizado(self):
        db = MagicMock()
        ensure_indexes(db, collection_name="other_coll")
        assert db.__getitem__.call_args_list[-1] == (("other_coll",),)


class TestFindUltimoConcluidoPorTipo:
    """OP-05 — rodape Bloco C (intocado)."""

    def test_retorna_doc_quando_existe(self):
        db = MagicMock()
        doc = {"concluido_em": "x", "resultado": {"path_xlsx": "y"}}
        db["sap_jobs"].find_one.return_value = doc

        result = find_ultimo_concluido_por_tipo(db, "zppprd")

        assert result == doc
        args, kwargs = db["sap_jobs"].find_one.call_args
        assert args[0] == {"tipo": "zppprd", "status": "concluido"}
        assert kwargs["sort"] == [("concluido_em", -1)]
        assert kwargs["projection"] == {"concluido_em": 1, "resultado.path_xlsx": 1}

    def test_retorna_none_quando_sem_doc(self):
        db = MagicMock()
        db["sap_jobs"].find_one.return_value = None

        result = find_ultimo_concluido_por_tipo(db, "zppprd")

        assert result is None
