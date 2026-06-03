"""Testes do migrations.py (DS-07 / SP-08 RF-08-08..11).

Cobre DT-07-03..05 do SDD sap-scheduler.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from src.sap_scheduler.migrations import migracao_dedup_sap_jobs


class TestMigracaoDedupSapJobs:
    """Idempotencia + mantem-primeiro + log."""

    def test_dt_06_05_coll_sem_duplicatas_retorna_zero(self):
        db = MagicMock()
        # aggregate retorna iteravel vazio
        db["sap_jobs"].aggregate.return_value = iter([])

        result = migracao_dedup_sap_jobs(db)

        assert result == 0
        db["sap_jobs"].delete_many.assert_not_called()

    def test_dt_07_03_dedup_8_zumbis_retorna_seis(self):
        """Cenario real cliente 03/06: 4 zppprd + 4 zpp_nt0001 com mesma chave."""
        db = MagicMock()
        from bson import ObjectId

        # 4 zppprd duplicados
        ids_zppprd = [ObjectId() for _ in range(4)]
        # 4 zpp_nt0001 duplicados
        ids_nt0001 = [ObjectId() for _ in range(4)]

        db["sap_jobs"].aggregate.return_value = iter([
            {
                "_id": {"tipo": "zppprd", "agendado_para": "2026-06-04T03:30:00Z"},
                "ids": ids_zppprd,
                "count": 4,
            },
            {
                "_id": {"tipo": "zpp_nt0001", "agendado_para": "2026-06-04T03:30:00Z"},
                "ids": ids_nt0001,
                "count": 4,
            },
        ])
        # delete_many retorna mock com deleted_count=3 (cada grupo tem 4-1=3 pra deletar)
        delete_result = MagicMock()
        delete_result.deleted_count = 3
        db["sap_jobs"].delete_many.return_value = delete_result

        result = migracao_dedup_sap_jobs(db)

        # 4-1 + 4-1 = 6 deletados
        assert result == 6
        # Mantem o primeiro `_id` de cada grupo (delete pega ids[1:])
        chamadas = db["sap_jobs"].delete_many.call_args_list
        assert len(chamadas) == 2
        # Primeira chamada — zppprd
        deletar_zppprd = chamadas[0][0][0]["_id"]["$in"]
        assert deletar_zppprd == ids_zppprd[1:]
        assert ids_zppprd[0] not in deletar_zppprd
        # Segunda chamada — zpp_nt0001
        deletar_nt0001 = chamadas[1][0][0]["_id"]["$in"]
        assert deletar_nt0001 == ids_nt0001[1:]
        assert ids_nt0001[0] not in deletar_nt0001

    def test_dt_07_04_chamadas_consecutivas_idempotentes(self):
        """2a chamada em ambiente limpo retorna 0 e nao chama delete."""
        db = MagicMock()
        # Primeira chamada: aggregate vazio (ja limpo)
        db["sap_jobs"].aggregate.return_value = iter([])

        result_1 = migracao_dedup_sap_jobs(db)
        result_2 = migracao_dedup_sap_jobs(db)

        assert result_1 == 0
        assert result_2 == 0
        db["sap_jobs"].delete_many.assert_not_called()

    def test_collection_name_customizado(self):
        db = MagicMock()
        db["custom_coll"].aggregate.return_value = iter([])

        migracao_dedup_sap_jobs(db, collection_name="custom_coll")

        # Verifica acesso a coll custom (db.__getitem__)
        db.__getitem__.assert_called_with("custom_coll")

    def test_grupo_de_apenas_2_docs(self):
        """Edge: grupo com 2 docs duplicados — mantem 1, deleta 1."""
        db = MagicMock()
        from bson import ObjectId
        ids = [ObjectId(), ObjectId()]

        db["sap_jobs"].aggregate.return_value = iter([
            {
                "_id": {"tipo": "zppprd", "agendado_para": "x"},
                "ids": ids,
                "count": 2,
            },
        ])
        delete_result = MagicMock()
        delete_result.deleted_count = 1
        db["sap_jobs"].delete_many.return_value = delete_result

        result = migracao_dedup_sap_jobs(db)

        assert result == 1
        # Deletou apenas o segundo (mantem o primeiro)
        chamada = db["sap_jobs"].delete_many.call_args[0][0]
        assert chamada["_id"]["$in"] == [ids[1]]
