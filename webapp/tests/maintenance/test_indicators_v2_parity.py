"""Testes IM-13 — paridade numérica V1 vs V2.

Garante que os helpers de fetch da V2 (`indicators_v2_callbacks._fetch_*`) usam as
mesmas funções V1 (`zpp_kpi_calculator.*`) e propagam os filtros do store correto
(`period_type`, `start_iso`/`end_iso`, `equipment`, `codes`).

API pós-fix `fix/indicators-v2-filters`: as funções de fetch aceitam
`(start, end, codes, equipment_filter)` em vez de `year`. `_unpack_filters`
extrai isso do `store-v2-filters` produzido por `apply_v2_filters`.

Mock pattern alinhado com `test_fetch_zpp_window.py`: patch.object em
`get_mongo_connection` retornando coleção fake com `find().sort()` controlado.
"""

from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _clear_v2_caches():
    """Caches process-level vazam estado entre testes. Limpa antes de cada um."""
    from src.callbacks_registers.indicators_v2_callbacks import cache_invalidate_all
    cache_invalidate_all()
    yield
    cache_invalidate_all()


# ==================== TESTE 1 — Cards top usam V1 ====================

@patch("src.callbacks_registers.indicators_v2_callbacks.calculate_general_avg_by_month")
@patch("src.callbacks_registers.indicators_v2_callbacks.fetch_zpp_kpi_data")
def test_planta_cards_use_v1_calc(mock_fetch, mock_avg):
    """V2._fetch_planta_monthly deve chamar fetch_zpp_kpi_data + calculate_general_avg_by_month."""
    from src.callbacks_registers.indicators_v2_callbacks import _fetch_planta_monthly

    mock_fetch.return_value = {
        "EQ1": [{"month": m, "year": 2026, "breakdown_rate": 1.0 + m * 0.1} for m in range(1, 13)]
    }
    mock_avg.return_value = {
        f"2026-{m:02d}": {"mtbf": 10.0, "mttr": 0.5, "breakdown_rate": 1.0 + m * 0.1}
        for m in range(1, 13)
    }

    start = datetime(2026, 1, 1)
    end = datetime(2027, 1, 1)
    labels, values, _ = _fetch_planta_monthly("breakdown", start, end)

    mock_fetch.assert_called_once()
    args_fetch = mock_fetch.call_args[0]
    assert args_fetch[0] == start, "start_date deve ser propagado direto"
    assert args_fetch[1] == end, "end_date deve ser propagado direto (BR-12)"

    mock_avg.assert_called_once()
    assert labels == ["Jan/26", "Fev/26", "Mar/26", "Abr/26", "Mai/26", "Jun/26",
                      "Jul/26", "Ago/26", "Set/26", "Out/26", "Nov/26", "Dez/26"]
    assert values == [round(1.0 + m * 0.1, 2) for m in range(1, 13)]


# ==================== TESTE 2 — Equipment monthly usa V1 ====================

@patch("src.callbacks_registers.indicators_v2_callbacks.fetch_zpp_kpi_data")
@patch("src.callbacks_registers.indicators_v2_callbacks.get_zpp_equipment_names",
       return_value={"LONGI001": "LCL-08"})
def test_equipment_monthly_uses_v1(mock_names, mock_fetch):
    from src.callbacks_registers.indicators_v2_callbacks import _fetch_equipment_monthly

    mock_fetch.return_value = {
        "LONGI001": [{"month": m, "year": 2026, "mtbf": 8.0 + m, "mttr": 0.5, "breakdown_rate": 2.0}
                     for m in range(1, 13)]
    }

    start = datetime(2026, 1, 1)
    end = datetime(2027, 1, 1)
    labels, values, _ = _fetch_equipment_monthly("mtbf", "LCL-08", start, end)

    from src.utils.zpp_kpi_calculator import BREAKDOWN_CODES
    mock_fetch.assert_called_once_with(start, end, list(BREAKDOWN_CODES), lwb_simulate=False)
    assert len(labels) == 12
    assert values == [round(8.0 + m, 2) for m in range(1, 13)]


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

    mock_fetch.assert_called_once()
    call_args = mock_fetch.call_args
    assert call_args[0][1] == datetime(2026, 5, 1)
    assert call_args[0][2] == datetime(2026, 6, 1)

    assert len(items) == 2
    assert items[0]["codigo"] == "201"
    assert items[0]["duracao_min"] == 120
    assert items[0]["count"] == 2
    assert items[0]["day"] == 15
    assert items[1]["count"] == 1


# ==================== TESTE 4 — Year/month range BR-12 ====================

def test_year_range_semi_open():
    from src.callbacks_registers.indicators_v2_callbacks import _year_range
    start, end = _year_range(2026)
    assert start == datetime(2026, 1, 1)
    assert end == datetime(2027, 1, 1), "end_date deve ser primeiro instante do ano seguinte (BR-12)"


def test_month_range_semi_open():
    from src.callbacks_registers.indicators_v2_callbacks import _month_range
    s, e = _month_range(2026, 3)
    assert s == datetime(2026, 3, 1)
    assert e == datetime(2026, 4, 1)
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
    assert _resolve_target("mttr") == 48.0
    assert _resolve_target("breakdown") == 4.2


@patch("src.callbacks_registers.indicators_v2_callbacks.get_kpi_targets",
       side_effect=Exception("Mongo offline"))
def test_resolve_target_fallback(mock_get):
    from src.callbacks_registers.indicators_v2_callbacks import _resolve_target, KPI_META
    assert _resolve_target("mtbf") == KPI_META["mtbf"]["target"]
    assert _resolve_target("mttr") == KPI_META["mttr"]["target"]
    assert _resolve_target("breakdown") == KPI_META["breakdown"]["target"]


def test_to_display_mttr_converts_hours_to_minutes():
    from src.callbacks_registers.indicators_v2_callbacks import _to_display
    assert _to_display("mttr", 1.5) == 90.0
    assert _to_display("mttr", 0.62) == 37.2
    assert _to_display("mttr", 0) == 0
    assert _to_display("mttr", None) is None
    assert _to_display("mtbf", 23.8) == 23.8
    assert _to_display("breakdown", 5.01) == 5.01


# ==================== NOVOS — paridade total com filtros V1 ====================

# --- N1 — _unpack_filters extrai e default-fila o store ---

def test_unpack_filters_with_all_fields():
    """Filtros completos do store viram (start, end, codes_tuple, equipment_filter, year)."""
    from src.callbacks_registers.indicators_v2_callbacks import _unpack_filters
    filters = {
        "period_type": "custom",
        "year":        2026,
        "start_iso":   "2025-08-01T00:00:00",
        "end_iso":     "2026-03-01T00:00:00",
        "equipment":   ["LCL-08", "LCT-16"],
        "codes":       ["201", "S201"],
    }
    start, end, codes, eq_filter, year, lwb_sim = _unpack_filters(filters)
    assert start == datetime(2025, 8, 1)
    assert end == datetime(2026, 3, 1)
    assert codes == ("201", "S201")
    assert eq_filter == ["LCL-08", "LCT-16"]
    assert year == 2025  # year = start.year (não o field "year" do store)
    assert lwb_sim is False


def test_unpack_filters_with_missing_keys_defaults():
    """Chave ausente (None) → fallback para defaults (toda planta, BREAKDOWN_CODES).
    Distinto de lista vazia explícita, que significa 'zero selecionado'."""
    from src.callbacks_registers.indicators_v2_callbacks import _unpack_filters
    from src.utils.zpp_kpi_calculator import BREAKDOWN_CODES

    filters = {
        "period_type": "year",
        "year":        2026,
        "start_iso":   "2026-01-01T00:00:00",
        "end_iso":     "2027-01-01T00:00:00",
        # equipment e codes ausentes do dict
    }
    start, end, codes, eq_filter, year, lwb_sim = _unpack_filters(filters)
    assert start == datetime(2026, 1, 1)
    assert end == datetime(2027, 1, 1)
    assert codes == tuple(BREAKDOWN_CODES)
    assert eq_filter is None
    assert year == 2026
    assert lwb_sim is False


def test_unpack_filters_empty_lists_are_explicit_zero():
    """Lista vazia no store significa intenção explícita 'zero selecionado'
    (não fallback). Convenção pós-fix indicators-v2 empty filter."""
    from src.callbacks_registers.indicators_v2_callbacks import _unpack_filters

    filters = {
        "period_type": "year",
        "year":        2026,
        "start_iso":   "2026-01-01T00:00:00",
        "end_iso":     "2027-01-01T00:00:00",
        "equipment":   [],
        "codes":       [],
    }
    start, end, codes, eq_filter, year, lwb_sim = _unpack_filters(filters)
    assert codes == ()
    assert eq_filter == []


# --- N2 — period_type=last12 cross-year ---

@patch("src.callbacks_registers.indicators_v2_callbacks.calculate_general_avg_by_month")
@patch("src.callbacks_registers.indicators_v2_callbacks.fetch_zpp_kpi_data")
def test_planta_monthly_respects_custom_range_cross_year(mock_fetch, mock_avg):
    """Range custom cruzando ano → fetch chamado com (start, end) exatos do store;
    labels cobrem todos os meses do range em ordem cronológica."""
    from src.callbacks_registers.indicators_v2_callbacks import _fetch_planta_monthly

    start = datetime(2025, 11, 1)
    end = datetime(2026, 3, 1)  # nov/25, dez/25, jan/26, fev/26

    mock_fetch.return_value = {"EQ1": [{"month": 1, "year": 2026, "breakdown_rate": 5.0}]}
    mock_avg.return_value = {
        "2025-11": {"mtbf": 10.0, "mttr": 0.5, "breakdown_rate": 4.0},
        "2025-12": {"mtbf": 11.0, "mttr": 0.6, "breakdown_rate": 4.5},
        "2026-01": {"mtbf": 12.0, "mttr": 0.7, "breakdown_rate": 5.0},
        "2026-02": {"mtbf": 13.0, "mttr": 0.8, "breakdown_rate": 5.5},
    }
    labels, values, _ = _fetch_planta_monthly("breakdown", start, end)

    args_fetch = mock_fetch.call_args[0]
    assert args_fetch[0] == start
    assert args_fetch[1] == end

    assert labels == ["Nov/25", "Dez/25", "Jan/26", "Fev/26"]
    assert values == [4.0, 4.5, 5.0, 5.5]


# --- N3 — equipment_filter aplicado no agg ---

@patch("src.callbacks_registers.indicators_v2_callbacks.calculate_general_avg_by_month")
@patch("src.callbacks_registers.indicators_v2_callbacks.fetch_zpp_kpi_data")
def test_planta_monthly_filters_equipment_subset(mock_fetch, mock_avg):
    """equipment_filter restringe equipment_ids passado ao calculate_general_avg_by_month."""
    from src.callbacks_registers.indicators_v2_callbacks import _fetch_planta_monthly

    mock_fetch.return_value = {
        "LCL-08": [{"month": m, "year": 2026, "breakdown_rate": 2.0} for m in range(1, 13)],
        "PRENSA-01": [{"month": m, "year": 2026, "breakdown_rate": 7.0} for m in range(1, 13)],
        "LCT-16": [{"month": m, "year": 2026, "breakdown_rate": 3.0} for m in range(1, 13)],
    }
    mock_avg.return_value = {
        f"2026-{m:02d}": {"mtbf": 10.0, "mttr": 0.5, "breakdown_rate": 2.5}
        for m in range(1, 13)
    }

    start = datetime(2026, 1, 1)
    end = datetime(2027, 1, 1)
    labels, values, _ = _fetch_planta_monthly(
        "breakdown", start, end, equipment_filter=["LCL-08", "LCT-16"]
    )

    # equipment_ids passado ao agg deve ser SUBSET, não todos
    avg_kwargs = mock_avg.call_args[1]
    assert avg_kwargs["equipment_ids"] == ["LCL-08", "LCT-16"], (
        "agg deve receber só os equipamentos selecionados, não todos do dict"
    )
    assert len(values) == 12


# --- N4 — codes subset propagado ---

@patch("src.callbacks_registers.indicators_v2_callbacks.calculate_general_avg_by_month")
@patch("src.callbacks_registers.indicators_v2_callbacks.fetch_zpp_kpi_data")
def test_fetch_kpi_propagates_codes_subset(mock_fetch, mock_avg):
    """codes do store substitui BREAKDOWN_CODES default no fetch_zpp_kpi_data."""
    from src.callbacks_registers.indicators_v2_callbacks import _fetch_planta_monthly

    mock_fetch.return_value = {"EQ1": [{"month": 1, "year": 2026, "breakdown_rate": 5.0}]}
    mock_avg.return_value = {
        f"2026-{m:02d}": {"mtbf": 10.0, "mttr": 0.5, "breakdown_rate": 1.0}
        for m in range(1, 13)
    }

    start = datetime(2026, 1, 1)
    end = datetime(2027, 1, 1)
    codes_subset = ("201", "S201")
    _fetch_planta_monthly("breakdown", start, end, codes=codes_subset)

    args_fetch = mock_fetch.call_args[0]
    assert args_fetch[2] == list(codes_subset), "fetch deve receber codes do store"


# --- N5 — _fetch_events_day_real filtra codes (paridade V1, contradiz IM-05) ---

def test_events_day_filters_by_codes_paridade_v1():
    """Drilldown nível 'tabela' deve filtrar por codes — paridade V1.
    Decisão revoga IM-05 do SDD indicators-v2 que dizia 'mostra TODOS'."""
    from src.callbacks_registers.indicators_v2_callbacks import _fetch_events_day_real

    fake_col = MagicMock()
    sort_mock = MagicMock()
    sort_mock.__iter__ = lambda self: iter([])
    fake_col.find.return_value.sort.return_value = sort_mock

    with patch("src.callbacks_registers.indicators_v2_callbacks.get_mongo_connection",
               return_value=fake_col), \
         patch("src.callbacks_registers.indicators_v2_callbacks.get_zpp_equipment_names",
               return_value={"LONGI001": "LCL-08"}), \
         patch("src.callbacks_registers.indicators_v2_callbacks._mock_eventos_dia",
               return_value=[{"placeholder": True}]):
        _fetch_events_day_real(
            "LCL-08", month=5, day=15, year=2026, codes=("201", "S201")
        )

    fake_col.find.assert_called_once()
    query = fake_col.find.call_args[0][0]
    assert query.get("causa_do_desvio") == {"$in": ["201", "S201"]}, (
        "query Mongo deve restringir causa_do_desvio aos codes passados"
    )


def test_events_day_uses_breakdown_codes_default_when_no_codes():
    """Sem codes explícito → usa BREAKDOWN_CODES (paridade V1)."""
    from src.callbacks_registers.indicators_v2_callbacks import _fetch_events_day_real
    from src.utils.zpp_kpi_calculator import BREAKDOWN_CODES

    fake_col = MagicMock()
    sort_mock = MagicMock()
    sort_mock.__iter__ = lambda self: iter([])
    fake_col.find.return_value.sort.return_value = sort_mock

    with patch("src.callbacks_registers.indicators_v2_callbacks.get_mongo_connection",
               return_value=fake_col), \
         patch("src.callbacks_registers.indicators_v2_callbacks.get_zpp_equipment_names",
               return_value={"LONGI001": "LCL-08"}), \
         patch("src.callbacks_registers.indicators_v2_callbacks._mock_eventos_dia",
               return_value=[{"placeholder": True}]):
        _fetch_events_day_real("LCL-08", month=5, day=15, year=2026)

    query = fake_col.find.call_args[0][0]
    assert query.get("causa_do_desvio") == {"$in": list(BREAKDOWN_CODES)}


# --- N6 — _iter_months_in_range helper ---

def test_iter_months_in_range_simple_year():
    from src.callbacks_registers.indicators_v2_callbacks import _iter_months_in_range
    months = list(_iter_months_in_range(datetime(2026, 1, 1), datetime(2027, 1, 1)))
    assert len(months) == 12
    assert months[0] == ("Jan/26", datetime(2026, 1, 1), datetime(2026, 2, 1), 2026, 1)
    assert months[11] == ("Dez/26", datetime(2026, 12, 1), datetime(2027, 1, 1), 2026, 12)


def test_iter_months_in_range_cross_year():
    from src.callbacks_registers.indicators_v2_callbacks import _iter_months_in_range
    months = list(_iter_months_in_range(datetime(2025, 11, 1), datetime(2026, 3, 1)))
    assert [m[0] for m in months] == ["Nov/25", "Dez/25", "Jan/26", "Fev/26"]


def test_iter_months_in_range_single_month():
    from src.callbacks_registers.indicators_v2_callbacks import _iter_months_in_range
    months = list(_iter_months_in_range(datetime(2026, 5, 1), datetime(2026, 6, 1)))
    assert len(months) == 1
    assert months[0][0] == "Mai/26"
