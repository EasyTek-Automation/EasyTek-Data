"""Testes IM-13 — paridade numérica V1 vs V2.

Garante que os helpers de fetch da V2 (`indicators_v2_callbacks._fetch_*`) usam as
mesmas funções V1 (`zpp_kpi_calculator.*`) e produzem resultados idênticos.

Mock pattern alinhado com `test_fetch_zpp_window.py`: patch.object em
`get_mongo_connection` retornando coleção fake com `find().sort()` controlado.

Limitação: estes testes validam contrato (mesmas funções V1 são chamadas com
mesmos args), não comparação numeric end-to-end com dados reais — esses ficam
pra suite de integração futura.
"""

from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest


# ==================== TESTE 1 — Cards top usam V1 ====================

@patch("src.callbacks_registers.indicators_v2_callbacks.calculate_general_avg_by_month")
@patch("src.callbacks_registers.indicators_v2_callbacks.fetch_zpp_kpi_data")
def test_planta_cards_use_v1_calc(mock_fetch, mock_avg):
    """V2._fetch_planta_monthly deve chamar fetch_zpp_kpi_data + calculate_general_avg_by_month."""
    from src.callbacks_registers.indicators_v2_callbacks import _fetch_planta_monthly

    mock_fetch.return_value = {"EQ1": [{"month": m, "breakdown_rate": 1.0 + m * 0.1} for m in range(1, 13)]}
    mock_avg.return_value = {
        f"2026-{m:02d}": {"mtbf": 10.0, "mttr": 0.5, "breakdown_rate": 1.0 + m * 0.1}
        for m in range(1, 13)
    }

    result = _fetch_planta_monthly("breakdown", year=2026)

    # Confirma chamada V1
    mock_fetch.assert_called_once()
    args_fetch = mock_fetch.call_args[0]
    assert args_fetch[0] == datetime(2026, 1, 1), "start_date deve ser primeiro instante do ano"
    assert args_fetch[1] == datetime(2027, 1, 1), "end_date deve ser primeiro instante do ano seguinte (BR-12)"

    mock_avg.assert_called_once()
    # Confirma resultado numérico
    assert result == [round(1.0 + m * 0.1, 2) for m in range(1, 13)]


# ==================== TESTE 2 — Equipment monthly usa V1 ====================

@patch("src.callbacks_registers.indicators_v2_callbacks.fetch_zpp_kpi_data")
@patch("src.callbacks_registers.indicators_v2_callbacks.get_zpp_equipment_names",
       return_value={"LONGI001": "LCL-08"})
def test_equipment_monthly_uses_v1(mock_names, mock_fetch):
    from src.callbacks_registers.indicators_v2_callbacks import _fetch_equipment_monthly

    mock_fetch.return_value = {
        "LONGI001": [{"month": m, "mtbf": 8.0 + m, "mttr": 0.5, "breakdown_rate": 2.0}
                     for m in range(1, 13)]
    }

    # Passando nome amigável — V2 resolve via reverse lookup
    result = _fetch_equipment_monthly("mtbf", "LCL-08", year=2026)

    mock_fetch.assert_called_once_with(datetime(2026, 1, 1), datetime(2027, 1, 1), pytest.importorskip("src.utils.zpp_kpi_calculator").BREAKDOWN_CODES)
    assert result == [round(8.0 + m, 2) for m in range(1, 13)]


# ==================== TESTE 3 — Top paradas usa V1 ====================

@patch("src.callbacks_registers.indicators_v2_callbacks.fetch_top_breakdowns_by_equipment")
@patch("src.callbacks_registers.indicators_v2_callbacks.get_zpp_equipment_names",
       return_value={"PRENS001": "PRENSA-01"})
def test_top_paradas_uses_v1(mock_names, mock_fetch):
    from src.callbacks_registers.indicators_v2_callbacks import _fetch_top_paradas_real
    from datetime import date

    mock_fetch.return_value = [
        {"date": date(2026, 5, 15), "motivo": "201", "duracao_min": 120.0,
         "duracao_horas": 2.0, "descricao": "Avaria mecânica", "count": 2},
        {"date": date(2026, 5, 20), "motivo": "S201", "duracao_min": 60.0,
         "duracao_horas": 1.0, "descricao": "Avaria elétrica"},
    ]

    items = _fetch_top_paradas_real("PRENSA-01", month=5, year=2026, top_n=10)

    # Confirma chamada V1 com BR-12 (janela semi-aberta)
    mock_fetch.assert_called_once()
    call_args = mock_fetch.call_args
    assert call_args[0][1] == datetime(2026, 5, 1)
    assert call_args[0][2] == datetime(2026, 6, 1)  # primeiro instante do mês seguinte

    # Confirma adaptação do schema
    assert len(items) == 2
    assert items[0]["codigo"] == "201"
    assert items[0]["duracao_min"] == 120
    assert items[0]["count"] == 2
    assert items[0]["day"] == 15
    assert items[1]["count"] == 1  # default quando ausente


# ==================== TESTE 4 — Year range respeita BR-12 ====================

def test_year_range_semi_open():
    from src.callbacks_registers.indicators_v2_callbacks import _year_range
    start, end = _year_range(2026)
    assert start == datetime(2026, 1, 1)
    assert end == datetime(2027, 1, 1), "end_date deve ser primeiro instante do ano seguinte (BR-12)"


def test_month_range_semi_open():
    from src.callbacks_registers.indicators_v2_callbacks import _month_range
    # Mês comum
    s, e = _month_range(2026, 3)
    assert s == datetime(2026, 3, 1)
    assert e == datetime(2026, 4, 1)
    # Mês de dezembro (boundary do ano)
    s, e = _month_range(2026, 12)
    assert s == datetime(2026, 12, 1)
    assert e == datetime(2027, 1, 1)


# ==================== TESTE 5 — Target fallback ====================

@patch("src.callbacks_registers.indicators_v2_callbacks.get_kpi_targets")
def test_resolve_target_real(mock_get):
    """V1 retorna mttr em HORAS; V2 expõe em MINUTOS (×60) — BR-02 convenção."""
    from src.callbacks_registers.indicators_v2_callbacks import _resolve_target
    mock_get.return_value = {"mtbf": 15.5, "mttr": 0.8, "breakdown_rate": 4.2}
    assert _resolve_target("mtbf") == 15.5
    assert _resolve_target("mttr") == 48.0  # 0.8h × 60 = 48min
    assert _resolve_target("breakdown") == 4.2


@patch("src.callbacks_registers.indicators_v2_callbacks.get_kpi_targets",
       side_effect=Exception("Mongo offline"))
def test_resolve_target_fallback(mock_get):
    """Mongo offline → fallback pros valores hardcoded em KPI_META.
    KPI_META["mttr"]["target"] já está em MINUTOS (90 == 1.5h)."""
    from src.callbacks_registers.indicators_v2_callbacks import _resolve_target, KPI_META
    assert _resolve_target("mtbf") == KPI_META["mtbf"]["target"]
    assert _resolve_target("mttr") == KPI_META["mttr"]["target"]  # 90 min
    assert _resolve_target("breakdown") == KPI_META["breakdown"]["target"]


def test_to_display_mttr_converts_hours_to_minutes():
    """Helper de conversão: MTTR h→min, demais passa direto."""
    from src.callbacks_registers.indicators_v2_callbacks import _to_display
    assert _to_display("mttr", 1.5) == 90.0
    assert _to_display("mttr", 0.62) == 37.2
    assert _to_display("mttr", 0) == 0
    assert _to_display("mttr", None) is None
    assert _to_display("mtbf", 23.8) == 23.8  # mtbf passa direto
    assert _to_display("breakdown", 5.01) == 5.01  # breakdown passa direto
