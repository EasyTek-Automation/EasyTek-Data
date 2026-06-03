"""Testes do cron.py refresh (DS-03 refresh + DS-07).

Cobre DT-07-07..14 do SDD sap-scheduler.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import pytz
from pymongo.errors import DuplicateKeyError, PyMongoError

from src.sap_scheduler.config import SapSchedulerConfig
from src.sap_scheduler.cron import (
    _FALLBACK_AGENDAMENTOS,
    _calcular_agendado_para_hoje,
    _resolver_agendamentos_do_mongo,
    _tick,
    _tick_inserir_job_atomico,
)


# ---------- Fixtures ----------

def _cfg(**overrides) -> SapSchedulerConfig:
    """SapSchedulerConfig com defaults sas pros testes."""
    defaults = dict(
        habilitado=True,
        agendados=[],
        janela_tick_segundos=60,
        timezone="America/Sao_Paulo",
        frescor_horas_limite=26,
        collection="sap_jobs",
    )
    defaults.update(overrides)
    return SapSchedulerConfig(**defaults)


# ---------- _calcular_agendado_para_hoje ----------

class TestCalcularAgendadoParaHoje:
    """DT-07-07 + extras: arredondamento + timezone."""

    def test_dt_07_07_retorna_naive_utc_segundo_zero(self):
        result = _calcular_agendado_para_hoje("03:30", "America/Sao_Paulo")
        assert result.tzinfo is None
        assert result.second == 0
        assert result.microsecond == 0

    def test_brt_para_utc_offset_correto(self):
        """03:30 BRT (UTC-3) -> 06:30 UTC."""
        result = _calcular_agendado_para_hoje("03:30", "America/Sao_Paulo")
        assert result.hour == 6
        assert result.minute == 30

    def test_meia_noite_brt(self):
        result = _calcular_agendado_para_hoje("00:00", "America/Sao_Paulo")
        # 00:00 BRT = 03:00 UTC (mesmo dia ou seguinte dependendo do dia)
        assert result.hour == 3
        assert result.minute == 0

    def test_2_workers_mesmo_minuto_geram_mesma_chave(self):
        """Garante que 2 chamadas geram a mesma chave — base do dedup."""
        r1 = _calcular_agendado_para_hoje("03:30", "America/Sao_Paulo")
        r2 = _calcular_agendado_para_hoje("03:30", "America/Sao_Paulo")
        assert r1 == r2


# ---------- _tick_inserir_job_atomico ----------

class TestTickInserirJobAtomico:
    """DT-07-08..10: insert OK / DuplicateKeyError / outras PyMongoError."""

    def test_dt_07_08_insert_em_coll_vazia(self, caplog):
        db = MagicMock()
        result = MagicMock(inserted_id="abc123")
        db["sap_jobs"].insert_one.return_value = result

        agendado = datetime(2026, 6, 4, 6, 30, 0)
        with caplog.at_level("INFO"):
            _tick_inserir_job_atomico(db, "zppprd", agendado)

        db["sap_jobs"].insert_one.assert_called_once()
        doc = db["sap_jobs"].insert_one.call_args[0][0]
        assert doc["tipo"] == "zppprd"
        assert doc["status"] == "pendente"
        assert doc["agendado_para"] == agendado
        assert doc["iniciado_em"] is None
        assert doc["concluido_em"] is None
        assert doc["resultado"] is None
        assert doc["erro"] is None
        # Log INFO de sucesso
        assert "job inserido" in caplog.text

    def test_dt_07_09_duplicate_key_logada_como_info(self, caplog):
        db = MagicMock()
        db["sap_jobs"].insert_one.side_effect = DuplicateKeyError("E11000")

        agendado = datetime(2026, 6, 4, 6, 30, 0)
        with caplog.at_level("INFO"):
            _tick_inserir_job_atomico(db, "zppprd", agendado)

        # DuplicateKeyError nao levanta — comportamento esperado (DC-07-04)
        assert "dedup" in caplog.text
        # Nao deve ter "ERROR" no log pra esse caso
        assert not any(r.levelname == "ERROR" for r in caplog.records)

    def test_dt_07_10_outras_pymongoerror_sobem(self):
        db = MagicMock()
        db["sap_jobs"].insert_one.side_effect = PyMongoError("connection lost")

        with pytest.raises(PyMongoError):
            _tick_inserir_job_atomico(db, "zppprd", datetime(2026, 6, 4, 6, 30))


# ---------- _resolver_agendamentos_do_mongo ----------

class TestResolverAgendamentosDoMongo:
    """3 niveis de fallback: Mongo error / None / schema corrompido."""

    def test_doc_valido_retorna_agendamentos(self):
        with patch("src.sap_scheduler.cron.read_config_singleton") as p:
            p.return_value = {
                "_id": "singleton",
                "agendamentos": [{"tipo": "zppprd", "hora": "03:30", "ativo": True}],
            }
            result = _resolver_agendamentos_do_mongo()
        assert result == [{"tipo": "zppprd", "hora": "03:30", "ativo": True}]

    def test_dt_07_12_doc_deletado_retorna_lista_vazia(self, caplog):
        with patch("src.sap_scheduler.cron.read_config_singleton") as p:
            p.return_value = None
            with caplog.at_level("WARNING"):
                result = _resolver_agendamentos_do_mongo()

        assert result == []
        assert "nao encontrado" in caplog.text

    def test_dt_07_13_schema_corrompido_usa_fallback(self, caplog):
        with patch("src.sap_scheduler.cron.read_config_singleton") as p:
            p.return_value = {"_id": "singleton", "agendamentos": "string-invalida"}
            with caplog.at_level("ERROR"):
                result = _resolver_agendamentos_do_mongo()

        assert result == _FALLBACK_AGENDAMENTOS
        assert "fallback" in caplog.text

    def test_pymongo_error_retorna_vazio(self, caplog):
        with patch("src.sap_scheduler.cron.read_config_singleton") as p:
            p.side_effect = PyMongoError("connection")
            with caplog.at_level("ERROR"):
                result = _resolver_agendamentos_do_mongo()
        assert result == []
        assert "erro lendo" in caplog.text


# ---------- _tick ----------

class TestTick:
    """DT-07-11..14: kill switch / fallbacks / race 4 workers."""

    def test_dt_07_11_kill_switch_false_no_op(self):
        db = MagicMock()
        with patch("src.sap_scheduler.cron.read_config_singleton") as p:
            _tick(_cfg(habilitado=False), db)
            # Nao leu config nem inseriu nada
            p.assert_not_called()
            db.__getitem__.assert_not_called()

    def test_doc_deletado_no_op(self):
        db = MagicMock()
        with patch("src.sap_scheduler.cron.read_config_singleton") as p:
            p.return_value = None
            _tick(_cfg(), db)
            # Nao inseriu
            db["sap_jobs"].insert_one.assert_not_called()

    def test_item_ativo_falso_pulado(self):
        db = MagicMock()
        with patch("src.sap_scheduler.cron.read_config_singleton") as p:
            # Hora ja passou ha minutos (fora da janela) mas ativo=False
            agora = datetime.now(tz=pytz.timezone("America/Sao_Paulo"))
            hora_str = agora.strftime("%H:%M")
            p.return_value = {
                "agendamentos": [{"tipo": "zppprd", "hora": hora_str, "ativo": False}],
            }
            _tick(_cfg(), db)
        db["sap_jobs"].insert_one.assert_not_called()

    def test_item_dentro_janela_chama_insert(self):
        db = MagicMock()
        with patch("src.sap_scheduler.cron.read_config_singleton") as p:
            tz = pytz.timezone("America/Sao_Paulo")
            agora_local = datetime.now(tz=tz)
            hora_str = agora_local.strftime("%H:%M")
            p.return_value = {
                "agendamentos": [{"tipo": "zppprd", "hora": hora_str, "ativo": True}],
            }
            _tick(_cfg(janela_tick_segundos=120), db)
        # Inseriu
        assert db["sap_jobs"].insert_one.called

    def test_item_fora_janela_nao_insere(self):
        db = MagicMock()
        with patch("src.sap_scheduler.cron.read_config_singleton") as p:
            # Hora 12 horas atras
            tz = pytz.timezone("America/Sao_Paulo")
            from datetime import timedelta
            distante = datetime.now(tz=tz) - timedelta(hours=12)
            hora_str = distante.strftime("%H:%M")
            p.return_value = {
                "agendamentos": [{"tipo": "zppprd", "hora": hora_str, "ativo": True}],
            }
            _tick(_cfg(janela_tick_segundos=60), db)
        db["sap_jobs"].insert_one.assert_not_called()

    def test_dt_07_14_race_4_workers_simulada(self, caplog):
        """4 workers tickam simultaneo. 1 vence; 3 logam dedup."""
        db = MagicMock()
        # Primeiro insert OK; demais sao DuplicateKeyError
        results = [MagicMock(inserted_id="x")] + [DuplicateKeyError("E11000")] * 3

        def side(*args, **kwargs):
            r = results.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

        db["sap_jobs"].insert_one.side_effect = side

        agendado = datetime(2026, 6, 4, 6, 30, 0)
        with caplog.at_level("INFO"):
            for _ in range(4):
                _tick_inserir_job_atomico(db, "zppprd", agendado)

        # 1 sucesso + 3 dedup
        assert caplog.text.count("job inserido") == 1
        assert caplog.text.count("dedup") == 3
