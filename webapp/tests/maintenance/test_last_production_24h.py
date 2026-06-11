"""Testes do recorte 24h da home com fallback de fim de semana.

Cobre `find_last_production_day` e `build_last_production_24h_series`
(`kpi_report_v2_series.py`) — a regra nova "últimas 24h que houve produção":
numa 2ª de manhã, "ontem" é domingo sem produção → retrocede até a 6ª.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pandas as pd
import pytest

from src.utils import kpi_report_v2_series as series


@pytest.fixture(autouse=True)
def _clear_cache():
    """Zera o cache TTL entre testes (estado de módulo)."""
    series._CACHE_24H.clear()
    yield
    series._CACHE_24H.clear()


def _prod_df(hours: float) -> pd.DataFrame:
    return pd.DataFrame({"linea": ["L1"], "horasact": [hours]})


_EMPTY = pd.DataFrame({"linea": [], "horasact": []})


def _prod_only_on(production_days: set[int]):
    """Fábrica de fake `fetch_zpp_production_data`: produção só nos dias do set (day-of-month)."""
    def _fake(start, end):
        return _prod_df(8.0) if start.day in production_days else _EMPTY
    return _fake


class TestFindLastProductionDay:
    def test_segunda_de_manha_retrocede_ate_sexta(self):
        # Seg 08/06/2026 09:00. Ontem=Dom 07 (sem prod), Sáb 06 (sem prod),
        # Sex 05 (com prod) → deve retornar 05.
        now = datetime(2026, 6, 8, 9, 0)
        with patch("src.utils.zpp_kpi_calculator.fetch_zpp_production_data",
                   side_effect=_prod_only_on({5, 4, 3, 2, 1})):
            got = series.find_last_production_day(now)
        assert got == datetime(2026, 6, 5, 0, 0)

    def test_dia_normal_retorna_ontem(self):
        # Qua 10/06 → ontem=Ter 09 tem produção.
        now = datetime(2026, 6, 10, 14, 0)
        with patch("src.utils.zpp_kpi_calculator.fetch_zpp_production_data",
                   side_effect=_prod_only_on({9, 8})):
            got = series.find_last_production_day(now)
        assert got == datetime(2026, 6, 9, 0, 0)

    def test_sem_producao_em_lookback_cai_em_ontem(self):
        now = datetime(2026, 6, 8, 9, 0)
        with patch("src.utils.zpp_kpi_calculator.fetch_zpp_production_data",
                   side_effect=lambda s, e: _EMPTY):
            got = series.find_last_production_day(now, max_lookback=5)
        assert got == datetime(2026, 6, 7, 0, 0)  # ontem (fallback neutro)

    def test_horas_zero_nao_conta_como_producao(self):
        now = datetime(2026, 6, 10, 9, 0)
        def _fake(s, e):
            return _prod_df(0.0) if s.day == 9 else _prod_df(8.0)  # dia 9 tem registro mas 0h
        with patch("src.utils.zpp_kpi_calculator.fetch_zpp_production_data", side_effect=_fake):
            got = series.find_last_production_day(now)
        assert got == datetime(2026, 6, 8, 0, 0)  # pula o 9 (0h), pega o 8


class TestBuildLast24hSeries:
    def test_serie_termina_no_ultimo_dia_com_producao(self):
        now = datetime(2026, 6, 8, 9, 0)  # seg; último com prod = sex 05
        with patch("src.utils.zpp_kpi_calculator.fetch_zpp_production_data",
                   side_effect=_prod_only_on({5, 4, 3, 2, 1})), \
             patch.object(series, "_compute_plant_kpis_for_window",
                          return_value=(12.0, 30.0, 1.5)):
            out = series.build_last_production_24h_series(now, n_days=7)
        assert out["labels"][-1] == "05/06"          # última barra = dia destacado
        assert out["highlight_date"] == "05/06"
        assert out["current_idx"] == 6               # n_days-1
        assert len(out["labels"]) == 7
        assert out["mtbf"][-1] == 12.0

    def test_cache_evita_recomputo(self):
        now = datetime(2026, 6, 10, 9, 0)
        with patch("src.utils.zpp_kpi_calculator.fetch_zpp_production_data",
                   side_effect=_prod_only_on({9})), \
             patch.object(series, "_compute_plant_kpis_for_window",
                          return_value=(1.0, 1.0, 1.0)) as mock_compute:
            series.build_last_production_24h_series(now, n_days=7)
            calls_first = mock_compute.call_count
            series.build_last_production_24h_series(now, n_days=7)  # 2ª chamada → cache
            assert mock_compute.call_count == calls_first  # não recomputou
