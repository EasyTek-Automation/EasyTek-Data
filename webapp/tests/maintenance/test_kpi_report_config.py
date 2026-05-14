"""Testes unitários de `utils/kpi_report_config.py` — funções puras + constantes.

Cobertura das SPs determinísticas:
- SP-03 (compute_monthly_window, compute_last_24h_window, _resolve_timezone)
- SP-05 (gerar_nome_arquivo)
- SP-19 (fmt_numero, fmt_data, fmt_data_hora)

IM-06 do projeto SDD KPIReport.
"""
from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.utils import kpi_report_config as cfg


# ============================== SP-03 — janelas ==============================

class TestComputeMonthlyWindow:
    def test_mes_corrente_2026_04_29(self):
        tz = ZoneInfo("America/Sao_Paulo")
        now = datetime(2026, 4, 29, 14, 32, 17, tzinfo=tz)
        ini, fim = cfg.compute_monthly_window(now, "MES_CORRENTE")
        assert ini == datetime(2026, 4, 1, 0, 0)
        assert fim == datetime(2026, 4, 29, 0, 0)
        assert ini.tzinfo is None
        assert fim.tzinfo is None

    def test_mes_corrente_clique_dia_1(self):
        """Caso de borda BR-01 — clique 1º do mês 00:00:01 produz janela vazia."""
        tz = ZoneInfo("America/Sao_Paulo")
        now = datetime(2026, 4, 1, 0, 0, 1, tzinfo=tz)
        ini, fim = cfg.compute_monthly_window(now, "MES_CORRENTE")
        assert ini == datetime(2026, 4, 1, 0, 0)
        assert fim == datetime(2026, 4, 1, 0, 0)

    def test_ultimos_30_dias(self):
        tz = ZoneInfo("America/Sao_Paulo")
        now = datetime(2026, 4, 29, 14, 32, 17, tzinfo=tz)
        ini, fim = cfg.compute_monthly_window(now, "ULTIMOS_30_DIAS")
        # Exatamente 30 × 86400 segundos de diferença
        assert (fim - ini).total_seconds() == 30 * 86400

    def test_modo_invalido_lanca_valueerror(self):
        tz = ZoneInfo("America/Sao_Paulo")
        now = datetime(2026, 4, 29, tzinfo=tz)
        with pytest.raises(ValueError, match="Modo inválido"):
            cfg.compute_monthly_window(now, "OUTRO")

    def test_modo_default_lê_constante(self):
        tz = ZoneInfo("America/Sao_Paulo")
        now = datetime(2026, 4, 29, tzinfo=tz)
        # Sem argumento modo — usa PERIODO_RELATORIO_MODO
        ini, fim = cfg.compute_monthly_window(now)
        # PERIODO_RELATORIO_MODO default é "MES_CORRENTE"
        assert ini == datetime(2026, 4, 1, 0, 0)


class TestComputeLast24hWindow:
    def test_clique_meio_da_tarde(self):
        tz = ZoneInfo("America/Sao_Paulo")
        now = datetime(2026, 4, 29, 14, 32, 17, tzinfo=tz)
        ini, fim = cfg.compute_last_24h_window(now)
        assert ini == datetime(2026, 4, 28, 0, 0)
        assert fim == datetime(2026, 4, 29, 0, 0)

    def test_clique_antes_da_meia_noite(self):
        """BR-02 itens 2.b/c/d — janela alinhada ao calendário, independente da hora."""
        tz = ZoneInfo("America/Sao_Paulo")
        now_cedo = datetime(2026, 4, 29, 0, 5, tzinfo=tz)
        now_tarde = datetime(2026, 4, 29, 23, 50, tzinfo=tz)
        assert cfg.compute_last_24h_window(now_cedo) == cfg.compute_last_24h_window(now_tarde)

    def test_retorno_naive(self):
        tz = ZoneInfo("America/Sao_Paulo")
        now = datetime(2026, 4, 29, tzinfo=tz)
        ini, fim = cfg.compute_last_24h_window(now)
        assert ini.tzinfo is None
        assert fim.tzinfo is None


# ============================== SP-03 — fuso ==============================

class TestResolveTimezone:
    def test_default_sem_env_var(self, monkeypatch):
        monkeypatch.delenv("TZ", raising=False)
        tz = cfg._resolve_timezone()
        assert tz.key == "America/Sao_Paulo"

    def test_env_var_valida(self, monkeypatch):
        monkeypatch.setenv("TZ", "America/Manaus")
        tz = cfg._resolve_timezone()
        assert tz.key == "America/Manaus"

    def test_env_var_invalida_fallback(self, monkeypatch, caplog):
        monkeypatch.setenv("TZ", "America/CidadeInexistente")
        tz = cfg._resolve_timezone()
        assert tz.key == "America/Sao_Paulo"


# ============================== SP-05 — nome arquivo ==============================

class TestGerarNomeArquivo:
    def test_mes_corrente(self):
        tz = ZoneInfo("America/Sao_Paulo")
        agora = datetime(2026, 4, 29, 14, 32, tzinfo=tz)
        nome = cfg.gerar_nome_arquivo(agora, "MES_CORRENTE")
        assert nome == "kpi-report_2026-04-29_mes-corrente.docx"

    def test_ultimos_30_dias(self):
        tz = ZoneInfo("America/Sao_Paulo")
        agora = datetime(2026, 5, 1, 8, 15, tzinfo=tz)
        nome = cfg.gerar_nome_arquivo(agora, "ULTIMOS_30_DIAS")
        assert nome == "kpi-report_2026-05-01_ultimos-30-dias.docx"

    def test_termina_com_docx(self):
        tz = ZoneInfo("America/Sao_Paulo")
        agora = datetime(2026, 4, 29, tzinfo=tz)
        assert cfg.gerar_nome_arquivo(agora).endswith(".docx")


# ============================== SP-19 — formatação ==============================

class TestFmtNumero:
    def test_inteiro_com_milhar(self):
        assert cfg.fmt_numero(1234.5) == "1.234,5"

    def test_decimal_pequeno(self):
        assert cfg.fmt_numero(0.05, casas=2) == "0,05"

    def test_none_vira_nd(self):
        assert cfg.fmt_numero(None) == "N/D"

    def test_nan_vira_nd(self):
        assert cfg.fmt_numero(float("nan")) == "N/D"

    def test_inf_vira_nd(self):
        assert cfg.fmt_numero(float("inf")) == "N/D"

    def test_zero(self):
        assert cfg.fmt_numero(0) == "0,0"

    def test_casas_zero(self):
        assert cfg.fmt_numero(42.7, casas=0) == "43"


class TestFmtData:
    def test_data_basica(self):
        assert cfg.fmt_data(datetime(2026, 4, 29)) == "29/04/2026"

    def test_data_com_hora_ignora_hora(self):
        assert cfg.fmt_data(datetime(2026, 4, 29, 14, 32)) == "29/04/2026"


class TestFmtDataHora:
    def test_basico(self):
        assert cfg.fmt_data_hora(datetime(2026, 4, 29, 14, 32)) == "29/04/2026 14:32"

    def test_meia_noite(self):
        assert cfg.fmt_data_hora(datetime(2026, 4, 29, 0, 0)) == "29/04/2026 00:00"
