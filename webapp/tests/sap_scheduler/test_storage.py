"""Testes do storage.py (DS-06 / SP-07 RF-07-14..17).

Cobre DT-06-01..08 do SDD sap-scheduler.
Usa mock de pymongo.Collection via unittest.mock.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_coll():
    """MagicMock simulando pymongo.Collection."""
    return MagicMock()


@pytest.fixture
def patch_get_mongo_connection(mock_coll):
    """Patch get_mongo_connection retornando mock_coll."""
    with patch("src.sap_scheduler.storage.get_mongo_connection") as p:
        p.return_value = mock_coll
        yield p


class TestReadConfigSingleton:
    """OP-CONFIG-01 — read."""

    def test_dt_06_01_coll_vazia_retorna_none(self, patch_get_mongo_connection, mock_coll):
        from src.sap_scheduler.storage import read_config_singleton
        mock_coll.find_one.return_value = None

        assert read_config_singleton() is None
        mock_coll.find_one.assert_called_once_with({"_id": "singleton"})

    def test_dt_06_02_apos_bootstrap_retorna_doc(self, patch_get_mongo_connection, mock_coll):
        from src.sap_scheduler.storage import read_config_singleton
        doc_simulado = {
            "_id": "singleton",
            "agendamentos": [{"tipo": "zppprd", "hora": "03:30", "ativo": True}],
            "historico_alteracoes": [],
            "versao_schema": 1,
        }
        mock_coll.find_one.return_value = doc_simulado

        result = read_config_singleton()
        assert result == doc_simulado

    def test_mongo_offline_retorna_none(self):
        from src.sap_scheduler.storage import read_config_singleton
        with patch("src.sap_scheduler.storage.get_mongo_connection") as p:
            p.return_value = None
            assert read_config_singleton() is None


class TestBootstrapConfig:
    """OP-CONFIG-03 — bootstrap idempotente."""

    def test_dt_06_03_coll_vazia_cria_default(self, patch_get_mongo_connection, mock_coll):
        from src.sap_scheduler.storage import DEFAULT_AGENDAMENTOS, bootstrap_config
        bootstrap_config()

        mock_coll.update_one.assert_called_once()
        args, kwargs = mock_coll.update_one.call_args
        # filter
        assert args[0] == {"_id": "singleton"}
        # update operator
        update = args[1]
        assert "$setOnInsert" in update
        assert update["$setOnInsert"]["agendamentos"] == DEFAULT_AGENDAMENTOS
        assert update["$setOnInsert"]["historico_alteracoes"] == []
        assert update["$setOnInsert"]["versao_schema"] == 1
        # upsert=True (idempotente entre workers)
        assert kwargs.get("upsert") is True

    def test_dt_06_04_chamadas_consecutivas_sao_idempotentes(self, patch_get_mongo_connection, mock_coll):
        from src.sap_scheduler.storage import bootstrap_config
        bootstrap_config()
        bootstrap_config()
        # 2 chamadas pra update_one com $setOnInsert + upsert=True;
        # Mongo garante idempotencia real (so 1 doc nasce)
        assert mock_coll.update_one.call_count == 2

    def test_dt_06_05_seed_customizado(self, patch_get_mongo_connection, mock_coll):
        from src.sap_scheduler.storage import bootstrap_config
        seed = [{"tipo": "zppprd", "hora": "04:00", "ativo": True}]
        bootstrap_config(seed_agendamentos=seed)

        args, _ = mock_coll.update_one.call_args
        assert args[1]["$setOnInsert"]["agendamentos"] == seed

    def test_dt_06_06_seed_none_usa_default(self, patch_get_mongo_connection, mock_coll):
        from src.sap_scheduler.storage import DEFAULT_AGENDAMENTOS, bootstrap_config
        bootstrap_config(seed_agendamentos=None)

        args, _ = mock_coll.update_one.call_args
        assert args[1]["$setOnInsert"]["agendamentos"] == DEFAULT_AGENDAMENTOS

    def test_seed_lista_vazia_usa_default(self, patch_get_mongo_connection, mock_coll):
        # Lista vazia (falsy) cai no default — protege contra "boot zerou configuracao"
        from src.sap_scheduler.storage import DEFAULT_AGENDAMENTOS, bootstrap_config
        bootstrap_config(seed_agendamentos=[])

        args, _ = mock_coll.update_one.call_args
        assert args[1]["$setOnInsert"]["agendamentos"] == DEFAULT_AGENDAMENTOS

    def test_mongo_offline_levanta_runtime_error(self):
        from src.sap_scheduler.storage import bootstrap_config
        with patch("src.sap_scheduler.storage.get_mongo_connection") as p:
            p.return_value = None
            with pytest.raises(RuntimeError, match="Mongo indisponivel"):
                bootstrap_config()


class TestAtualizarAgendamento:
    """OP-CONFIG-02 — update."""

    def test_dt_06_07_grava_doc_e_push_historico(self, patch_get_mongo_connection, mock_coll):
        from src.sap_scheduler.storage import atualizar_agendamento

        novos = [{"tipo": "zppprd", "hora": "04:15", "ativo": True}]
        antes = [{"tipo": "zppprd", "hora": "03:30", "ativo": True}]
        atualizar_agendamento(novos, quem="rgust", antes=antes)

        mock_coll.update_one.assert_called_once()
        args, kwargs = mock_coll.update_one.call_args

        # filter
        assert args[0] == {"_id": "singleton"}
        # update
        update = args[1]
        assert "$set" in update
        assert update["$set"]["agendamentos"] == novos
        assert "atualizado_em" in update["$set"]

        assert "$push" in update
        push = update["$push"]["historico_alteracoes"]
        assert push["$position"] == 0
        assert push["$slice"] == 20  # FIFO 20
        entrada = push["$each"][0]
        assert entrada["quem"] == "rgust"
        assert entrada["antes"] == antes
        assert entrada["depois"] == novos
        assert "em" in entrada

        # upsert=False (bootstrap separado)
        assert kwargs.get("upsert") is False

    def test_dt_06_08_fifo_via_slice_20(self, patch_get_mongo_connection, mock_coll):
        """O $slice:20 do Mongo limita o array — testamos so o parametro,
        ja que a logica FIFO real e do engine Mongo."""
        from src.sap_scheduler.storage import atualizar_agendamento
        atualizar_agendamento([], quem="x", antes=[])

        args, _ = mock_coll.update_one.call_args
        assert args[1]["$push"]["historico_alteracoes"]["$slice"] == 20

    def test_quem_e_string(self, patch_get_mongo_connection, mock_coll):
        from src.sap_scheduler.storage import atualizar_agendamento
        atualizar_agendamento([], quem="user@email.com", antes=[])
        args, _ = mock_coll.update_one.call_args
        assert args[1]["$push"]["historico_alteracoes"]["$each"][0]["quem"] == "user@email.com"

    def test_mongo_offline_levanta_runtime_error(self):
        from src.sap_scheduler.storage import atualizar_agendamento
        with patch("src.sap_scheduler.storage.get_mongo_connection") as p:
            p.return_value = None
            with pytest.raises(RuntimeError, match="Mongo indisponivel"):
                atualizar_agendamento([], quem="x", antes=[])
