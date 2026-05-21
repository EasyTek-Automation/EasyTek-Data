"""Testes do módulo `utils/kpi_report_v2_compare.py` (DS-05, IM-04).

Cobre:
- is_favorable: 3 KPIs × 5 direções (up/down/flat/na/unknown)
- compute_period_delta: casos normais + edge (anterior=0, atual=0, None, flat)
- fetch_anterior_monthly_window / fetch_anterior_last24h_window: boundary
- build_compare_dict: contrato store-kpi-v2-compare
"""
from __future__ import annotations

from datetime import datetime

import pytest

from src.utils.kpi_report_v2_compare import (
    FLAT_THRESHOLD_PCT,
    KPI_NAMES,
    build_compare_dict,
    compute_period_delta,
    fetch_anterior_last24h_window,
    fetch_anterior_monthly_window,
    is_favorable,
)


# ============================ is_favorable ============================

class TestIsFavorable:
    @pytest.mark.parametrize("kpi,direction,expected", [
        # MTBF — subir é bom
        ("mtbf", "up", True),
        ("mtbf", "down", False),
        ("mtbf", "flat", None),
        ("mtbf", "na", None),
        # MTTR — descer é bom
        ("mttr", "up", False),
        ("mttr", "down", True),
        ("mttr", "flat", None),
        ("mttr", "na", None),
        # Breakdown Rate — descer é bom
        ("breakdown_rate", "up", False),
        ("breakdown_rate", "down", True),
        ("breakdown_rate", "flat", None),
        ("breakdown_rate", "na", None),
    ])
    def test_matriz_3kpis_x_direcoes(self, kpi, direction, expected):
        assert is_favorable(kpi, direction) is expected

    def test_kpi_desconhecido_retorna_none(self):
        assert is_favorable("foo", "up") is None
        assert is_favorable("oee", "down") is None


# ============================ compute_period_delta ============================

class TestComputePeriodDelta:
    def test_mtbf_aumentou_favoravel(self):
        out = compute_period_delta(120.0, 100.0, "mtbf")
        assert out["delta_abs"] == 20.0
        assert out["delta_pct"] == pytest.approx(20.0)
        assert out["direction"] == "up"
        assert out["favorable"] is True
        assert out["anterior_value"] == 100.0
        assert out["atual_value"] == 120.0
        assert out["is_new"] is False

    def test_mttr_aumentou_desfavoravel(self):
        out = compute_period_delta(15.0, 10.0, "mttr")
        assert out["delta_abs"] == 5.0
        assert out["delta_pct"] == pytest.approx(50.0)
        assert out["direction"] == "up"
        assert out["favorable"] is False

    def test_breakdown_rate_diminuiu_favoravel(self):
        out = compute_period_delta(2.0, 5.0, "breakdown_rate")
        assert out["delta_abs"] == -3.0
        assert out["delta_pct"] == pytest.approx(-60.0)
        assert out["direction"] == "down"
        assert out["favorable"] is True

    def test_atual_zero_anterior_positivo_da_menos_100(self):
        out = compute_period_delta(0.0, 50.0, "mtbf")
        assert out["delta_abs"] == -50.0
        assert out["delta_pct"] == pytest.approx(-100.0)
        assert out["direction"] == "down"
        # MTBF descer é desfavorável
        assert out["favorable"] is False

    def test_anterior_zero_atual_positivo_marca_novo(self):
        out = compute_period_delta(10.0, 0.0, "mtbf")
        assert out["delta_abs"] == 10.0
        assert out["delta_pct"] is None
        assert out["direction"] == "up"
        assert out["is_new"] is True
        assert out["favorable"] is True

    def test_anterior_zero_atual_negativo_marca_novo_down(self):
        # Caso teórico (KPI normalmente não é negativo, mas defensivo)
        out = compute_period_delta(-5.0, 0.0, "mtbf")
        assert out["direction"] == "down"
        assert out["is_new"] is True
        # MTBF descer é desfavorável
        assert out["favorable"] is False

    def test_anterior_zero_atual_zero_eh_flat(self):
        out = compute_period_delta(0.0, 0.0, "mtbf")
        assert out["delta_abs"] == 0.0
        assert out["direction"] == "flat"
        assert out["favorable"] is None
        assert out["is_new"] is False

    def test_atual_none_retorna_na(self):
        out = compute_period_delta(None, 50.0, "mtbf")
        assert out["direction"] == "na"
        assert out["favorable"] is None
        assert out["delta_abs"] is None
        assert out["delta_pct"] is None

    def test_anterior_none_retorna_na(self):
        out = compute_period_delta(50.0, None, "mtbf")
        assert out["direction"] == "na"
        assert out["delta_abs"] is None

    def test_ambos_none_retorna_na(self):
        out = compute_period_delta(None, None, "mttr")
        assert out["direction"] == "na"

    def test_variacao_menor_que_threshold_eh_flat(self):
        # 0.5% < FLAT_THRESHOLD_PCT (1.0) → flat
        atual = 100.0
        anterior = 100.5
        out = compute_period_delta(atual, anterior, "mtbf")
        assert abs(out["delta_pct"]) < FLAT_THRESHOLD_PCT
        assert out["direction"] == "flat"
        assert out["favorable"] is None

    def test_variacao_exatamente_no_threshold_nao_eh_flat(self):
        # |Δ%| == 1.0 (não menor que threshold) → direction != flat
        out = compute_period_delta(101.0, 100.0, "mtbf")
        assert out["delta_pct"] == pytest.approx(1.0)
        # threshold é `<`, então 1.0 não é flat
        assert out["direction"] == "up"

    def test_anterior_negativo_usa_abs_no_denominador(self):
        # Valor negativo não deve quebrar — usa abs() no denominador
        out = compute_period_delta(-50.0, -100.0, "mtbf")
        # Δ_abs = -50 - (-100) = 50; Δ% = 50 / 100 = 50
        assert out["delta_abs"] == 50.0
        assert out["delta_pct"] == pytest.approx(50.0)
        assert out["direction"] == "up"


# ============================ janelas anteriores ============================

class TestFetchAnteriorMonthlyWindow:
    def test_mes_corrente_mid_month(self):
        # Janela mês corrente até dia 15
        atual = (datetime(2026, 5, 1), datetime(2026, 5, 15))
        ant_start, ant_end = fetch_anterior_monthly_window(atual)
        # 14 dias → end_ant = start_atual; start_ant = end_ant - 14d
        assert ant_end == datetime(2026, 5, 1)
        assert ant_start == datetime(2026, 4, 17)

    def test_mes_corrente_inicio_de_mes(self):
        # janela de 1 dia (mês recém-iniciado)
        atual = (datetime(2026, 6, 1), datetime(2026, 6, 2))
        ant_start, ant_end = fetch_anterior_monthly_window(atual)
        assert ant_end == datetime(2026, 6, 1)
        assert ant_start == datetime(2026, 5, 31)

    def test_invalida_quando_start_maior_que_end(self):
        with pytest.raises(ValueError):
            fetch_anterior_monthly_window(
                (datetime(2026, 5, 10), datetime(2026, 5, 1))
            )

    def test_duracao_eh_preservada(self):
        atual = (datetime(2026, 5, 1, 0, 0), datetime(2026, 5, 16, 12, 0))
        ant_start, ant_end = fetch_anterior_monthly_window(atual)
        duracao_atual = atual[1] - atual[0]
        duracao_anterior = ant_end - ant_start
        assert duracao_atual == duracao_anterior


class TestFetchAnteriorLast24hWindow:
    def test_caso_padrao(self):
        # 21/maio: ontem=20, hoje=21
        atual = (datetime(2026, 5, 20, 0, 0), datetime(2026, 5, 21, 0, 0))
        ant_start, ant_end = fetch_anterior_last24h_window(atual)
        # anterior: 19 → 20
        assert ant_start == datetime(2026, 5, 19, 0, 0)
        assert ant_end == datetime(2026, 5, 20, 0, 0)

    def test_atravessa_inicio_de_mes(self):
        # 1º junho: ontem=31/mai, hoje=1/jun
        atual = (datetime(2026, 5, 31, 0, 0), datetime(2026, 6, 1, 0, 0))
        ant_start, ant_end = fetch_anterior_last24h_window(atual)
        assert ant_start == datetime(2026, 5, 30, 0, 0)
        assert ant_end == datetime(2026, 5, 31, 0, 0)

    def test_invalida_start_maior_que_end(self):
        with pytest.raises(ValueError):
            fetch_anterior_last24h_window(
                (datetime(2026, 5, 21), datetime(2026, 5, 20))
            )


# ============================ build_compare_dict ============================

class TestBuildCompareDict:
    def test_tres_kpis_completos(self):
        atual = {"mtbf": 120.0, "mttr": 8.0, "breakdown_rate": 2.0}
        anterior = {"mtbf": 100.0, "mttr": 10.0, "breakdown_rate": 3.0}
        out = build_compare_dict(atual, anterior)
        assert set(out.keys()) == set(KPI_NAMES)
        assert out["mtbf"]["direction"] == "up"
        assert out["mtbf"]["favorable"] is True
        assert out["mttr"]["direction"] == "down"
        assert out["mttr"]["favorable"] is True
        assert out["breakdown_rate"]["direction"] == "down"
        assert out["breakdown_rate"]["favorable"] is True

    def test_kpis_ausentes_viram_none(self):
        out = build_compare_dict({}, {})
        for kpi in KPI_NAMES:
            assert out[kpi]["direction"] == "na"
            assert out[kpi]["delta_abs"] is None
            assert out[kpi]["favorable"] is None

    def test_kpi_parcial_so_atual(self):
        atual = {"mtbf": 100.0}
        anterior = {"mtbf": 50.0}
        out = build_compare_dict(atual, anterior)
        assert out["mtbf"]["direction"] == "up"
        assert out["mttr"]["direction"] == "na"
        assert out["breakdown_rate"]["direction"] == "na"
