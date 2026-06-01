"""Callbacks Indicadores V2 — drilldown 4 níveis (planta → equipamento → mês → dia → tabela).

Cliques:
- Card KPI (n_clicks) → modal nível 'equipamentos'
- Pattern click {"type":"v2-eq","kpi":...,"equipment":...} → nível 'meses'
- Pattern click {"type":"v2-month",...} → nível 'dias'
- Pattern click {"type":"v2-day",...} → nível 'tabela'

Dados reais via zpp_kpi_calculator (V1, pós fix f102f3f); fallback mock graceful
quando MongoDB offline ou collections vazias.
"""

import random
import calendar
import logging
from datetime import datetime, timedelta

import dash
from dash import html, dcc, dash_table, no_update, ALL
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import numpy as np
import plotly.graph_objects as go

logger = logging.getLogger("indicators_v2")

# Imports lazy — protegidos contra import error em ambiente sem Mongo
try:
    from src.utils.zpp_kpi_calculator import (
        BREAKDOWN_CODES,
        fetch_zpp_kpi_data,
        fetch_zpp_production_data,
        fetch_zpp_breakdown_data,
        fetch_top_breakdowns_by_equipment,
        get_zpp_equipment_categories,
        get_zpp_equipment_names,
    )
    from src.utils.maintenance_demo_data import (
        get_kpi_targets,
        calculate_general_avg_by_month,
    )
    from src.database.connection import get_mongo_connection
    _HAS_REAL_DATA = True
except Exception as _imp_err:
    logger.warning("V2: import V1 modules failed (%s) — só mock disponível", _imp_err)
    _HAS_REAL_DATA = False

# Cadastro de gatilhos de duração por equipamento (independente de Mongo offline)
from src.utils.breakdown_thresholds import (
    DEFAULT_THRESHOLD_MIN,
    derive_threshold_2,
    get_all_thresholds,
    get_threshold,
    get_thresholds_pair,
    set_threshold,
    invalidate_cache as invalidate_thresholds_cache,
)

# Demo override — força mock mesmo com Mongo ativo (esconde estágio real do projeto).
# Set INDICATORS_V2_FORCE_MOCK=1 no env pra ativar.
import os as _os
if _os.environ.get("INDICATORS_V2_FORCE_MOCK", "").lower() in ("1", "true", "yes"):
    logger.warning("V2: INDICATORS_V2_FORCE_MOCK ativo — usando dados mock")
    _HAS_REAL_DATA = False


# DS-02 — mapping kpi_v2 → campo retornado por zpp_kpi_calculator
KPI_FIELD_MAP = {
    "breakdown": "breakdown_rate",
    "mtbf":      "mtbf",
    "mttr":      "mttr",
}

# DS-02 — target field em get_kpi_targets()
KPI_TARGET_FIELD = {
    "breakdown": "breakdown_rate",
    "mtbf":      "mtbf",
    "mttr":      "mttr",
}

# Ano default — TODO IM-11: substituir por valor do filtro V2
DEFAULT_YEAR = 2026


MESES_PT = [
    "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
]

EQUIPAMENTOS = [
    {"id": "LCT-08", "categoria": "Transversais"},
    {"id": "LCT-16", "categoria": "Transversais"},
    {"id": "LCT-2.5", "categoria": "Transversais"},
    {"id": "LCL-08", "categoria": "Longitudinais"},
    {"id": "LCL-4.5", "categoria": "Longitudinais"},
    {"id": "PRENSA-01", "categoria": "Prensas"},
    {"id": "PRENSA-02", "categoria": "Prensas"},
]

CAUSAS = [
    "Avaria mecânica",
    "Avaria elétrica",
    "Falta de material",
    "Setup",
    "Manutenção corretiva",
    "Quebra de ferramenta",
    "Ajuste de processo",
    "Vazamento hidráulico",
]

KPI_META = {
    "breakdown": {
        "label": "Taxa de Avaria",
        "unit": "%",
        "color": "#dc3545",
        "min": 1.5,
        "max": 9.0,
        "target": 3.0,         # alvo: ≤ 3%
        "direction": "lower",  # menor é melhor
    },
    "mtbf": {
        "label": "MTBF",
        "unit": "h",
        "color": "#198754",
        "min": 40,
        "max": 220,
        "target": 150.0,       # alvo: ≥ 150h
        "direction": "higher",
    },
    "mttr": {
        # MTTR display em MINUTOS (BR-02 convenção V1 — internamente em horas).
        "label": "MTTR",
        "unit": "min",
        "color": "#0d6efd",
        "min": 36,
        "max": 270,
        "target": 90.0,        # alvo: ≤ 90min (== 1.5h)
        "direction": "lower",
    },
}


def _to_display(kpi: str, value):
    """Converte valor interno (horas pra MTTR/MTBF) → unit de display da V2.
    MTTR especial: V1 retorna horas, V2 exibe em minutos (×60). Demais passam direto.
    """
    if value is None:
        return value
    try:
        v = float(value)
    except (TypeError, ValueError):
        return value
    if kpi == "mttr":
        return round(v * 60, 2)
    return round(v, 2)


# ==================== CACHE PROCESS-LEVEL (perf) ====================

import time as _time

_CACHE_TTL_SECONDS = 60  # 1 min — balanceia frescor vs perf
_CACHE_KPI: dict = {}     # key=(year, codes_tuple) → (timestamp, kpi_data)
_CACHE_AGG: dict = {}     # key=(year, codes_tuple) → (timestamp, agg)
_CACHE_NAMES: dict = {"ts": 0, "data": None}
_CACHE_CATS: dict = {"ts": 0, "data": None}
_CACHE_TARGETS: dict = {}  # key=equipment → (timestamp, targets_dict)


def _cache_get(d: dict, key) -> object:
    entry = d.get(key)
    if entry and (_time.time() - entry[0]) < _CACHE_TTL_SECONDS:
        return entry[1]
    return None


def _cache_set(d: dict, key, value) -> None:
    d[key] = (_time.time(), value)


_CACHE_FIG: dict = {}  # key=(kpi, eq, year, values_tuple, target) → (timestamp, fig_dict)


def cache_invalidate_all():
    """Limpa todos caches V2 — chamável por btn-refresh."""
    _CACHE_KPI.clear()
    _CACHE_AGG.clear()
    _CACHE_TARGETS.clear()
    _CACHE_FIG.clear()
    _CACHE_PERIOD.clear()
    _CACHE_NAMES["data"] = None
    _CACHE_CATS["data"] = None
    logger.info("V2 caches invalidados")


def _cached_compact_bar(kpi: str, eq_id: str, year: int, values: list, target: float,
                        color: str, unit: str, labels: list = None,
                        statuses: list = None):
    """Bar compact cacheado por valores (mini-cards equipment grid).

    labels: lista de strings pro eixo X (cobre cross-year). Default = MESES_PT
    quando há exatamente 12 valores; senão usa índices stringificados.
    statuses: lista paralela "in"|"partial"|"out" pra colorir barras (None=all "in").
    """
    if labels is None:
        labels = MESES_PT if len(values) == 12 else [str(i + 1) for i in range(len(values))]
    st_key = tuple(statuses) if statuses else None
    key = (kpi, eq_id, year, tuple(values), target, tuple(labels), st_key)
    hit = _cache_get(_CACHE_FIG, key)
    if hit is not None:
        return hit
    fig = _bar(labels, values, eq_id, color, unit,
               target=target, show_trend=False, compact=True,
               bar_statuses=statuses)
    fig.update_layout(margin=dict(l=30, r=10, t=40, b=30), height=220)
    _cache_set(_CACHE_FIG, key, fig)
    return fig


def _cached_fetch_kpi(start: datetime, end: datetime, codes: tuple,
                      lwb_simulate: bool = False) -> dict:
    """fetch_zpp_kpi_data com cache por (start_iso, end_iso, codes, lwb_simulate)."""
    key = (start.isoformat(), end.isoformat(), codes, bool(lwb_simulate))
    hit = _cache_get(_CACHE_KPI, key)
    if hit is not None:
        return hit
    data = fetch_zpp_kpi_data(start, end, list(codes), lwb_simulate=lwb_simulate)
    _cache_set(_CACHE_KPI, key, data)
    return data


def _resolve_equipment_internal_ids(equipment_filter, kpi_data: dict) -> list:
    """Filtra equipment_filter contra chaves de kpi_data (ambos internal).

    Dropdown V2 grava internal IDs no store desde o fix 2026-05-31; o store
    é memory-only (não persiste sessão), então não há mais necessidade de
    fallback friendly→internal.
    """
    if equipment_filter is None:
        return list(kpi_data.keys())
    if not equipment_filter:
        return []
    return [raw for raw in equipment_filter if raw in kpi_data]


def _cached_agg(kpi_data: dict, start: datetime, end: datetime, codes: tuple,
                equipment_filter=None, lwb_simulate: bool = False) -> dict:
    """calculate_general_avg_by_month com cache, propaga filtro de equipamento.

    equipment_filter=None significa toda planta (todos os equipamentos do kpi_data).
    Lista vazia [] significa intenção explícita ("zero equipamento").
    lwb_simulate entra na chave pra invalidar quando o switch alterna.
    """
    # eq_key distingue None (toda planta) de lista (mesmo vazia)
    eq_key = "ALL" if equipment_filter is None else tuple(sorted(equipment_filter))
    key = (start.isoformat(), end.isoformat(), codes, eq_key, bool(lwb_simulate))
    hit = _cache_get(_CACHE_AGG, key)
    if hit is not None:
        return hit
    eq_ids = _resolve_equipment_internal_ids(equipment_filter, kpi_data)
    # equipment_ids=None mantém compat V1 (planta inteira); lista (mesmo vazia)
    # ativa filter dentro de calculate_general_avg_by_month.
    eq_ids_param = None if equipment_filter is None else eq_ids
    agg = calculate_general_avg_by_month(
        data=kpi_data, equipment_ids=eq_ids_param,
        months=None, year=None,
        start_date=start, end_date=end,
        lwb_simulate=lwb_simulate,
        breakdown_codes=list(codes),
    )
    _cache_set(_CACHE_AGG, key, agg)
    return agg


def _cached_names() -> dict:
    if (_time.time() - _CACHE_NAMES["ts"]) < _CACHE_TTL_SECONDS and _CACHE_NAMES["data"]:
        return _CACHE_NAMES["data"]
    data = get_zpp_equipment_names()
    _CACHE_NAMES["data"] = data
    _CACHE_NAMES["ts"] = _time.time()
    return data


def _cached_categories() -> dict:
    if (_time.time() - _CACHE_CATS["ts"]) < _CACHE_TTL_SECONDS and _CACHE_CATS["data"]:
        return _CACHE_CATS["data"]
    data = get_zpp_equipment_categories()
    _CACHE_CATS["data"] = data
    _CACHE_CATS["ts"] = _time.time()
    return data


def _cached_targets(equipment: str) -> dict:
    hit = _cache_get(_CACHE_TARGETS, equipment)
    if hit is not None:
        return hit
    data = get_kpi_targets(equipment)
    _cache_set(_CACHE_TARGETS, equipment, data)
    return data


_CACHE_PERIOD = {}  # (year, codes) → (ts, {mtbf, mttr, breakdown_rate, ...})


def _period_agg(start: datetime, end: datetime, codes: tuple = None,
                equipment_filter=None, lwb_simulate: bool = False) -> dict:
    """Agregado dos totais brutos da planta no período (BR-11 paridade V1).
    Retorna {mtbf, mttr, breakdown_rate} em unit V1 (mttr em horas).

    Aceita range arbitrário (cross-year ok) e filtro de equipamento (None=toda planta).

    Mock mode (INDICATORS_V2_FORCE_MOCK=1): média simples dos 12 valores mensais
    mock (non-zero). MTTR mock está em minutos (display), divide por 60 pra
    respeitar contrato unit-interno que o caller espera (_to_display reaplica ×60).

    NOTA — dívida conhecida: mock IGNORA equipment_filter e codes; só é usado
    em dev/demo (modo real é o canônico). Honrar filtros no mock exigiria
    redesenhar o gerador mock — não vale o custo enquanto o uso é só decorativo.
    """
    if not _HAS_REAL_DATA:
        out = {}
        for kpi_v2, agg_key in (("mtbf", "mtbf"), ("mttr", "mttr"), ("breakdown", "breakdown_rate")):
            vals = _mock_planta_mes(kpi_v2)
            non_zero = [v for v in vals if v not in (0, None)]
            avg_display = sum(non_zero) / len(non_zero) if non_zero else 0
            avg_internal = avg_display / 60.0 if kpi_v2 == "mttr" else avg_display
            out[agg_key] = round(avg_internal, 4)
        return out
    if codes is None:
        codes = tuple(BREAKDOWN_CODES)
    # eq_key distingue None (toda planta) de lista (mesmo vazia)
    eq_key = "ALL" if equipment_filter is None else tuple(sorted(equipment_filter))
    key = (start.isoformat(), end.isoformat(), codes, eq_key, bool(lwb_simulate))
    hit = _cache_get(_CACHE_PERIOD, key)
    if hit is not None:
        return hit
    try:
        from src.utils.maintenance_demo_data import calculate_kpi_averages
        kpi_data = _cached_fetch_kpi(start, end, codes, lwb_simulate=lwb_simulate)
        eq_ids = _resolve_equipment_internal_ids(equipment_filter, kpi_data)
        months_in_range = sorted({m for _, _, _, _, m in _iter_months_in_range(start, end)})
        agg = calculate_kpi_averages(
            data=kpi_data,
            equipment_filter=eq_ids,
            month_filter=months_in_range,
            year=start.year,
            start_date=start,
            end_date=end,
            lwb_simulate=lwb_simulate,
        )
        _cache_set(_CACHE_PERIOD, key, agg)
        return agg
    except Exception as e:
        logger.warning("V2 _period_agg falhou: %s", e)
        return {"mtbf": 0, "mttr": 0, "breakdown_rate": 0}


def _seed(*parts):
    return sum(hash(str(p)) % 100_000 for p in parts)


# ==================== HELPERS DE FETCH REAL (com fallback mock) ====================

def _resolve_target(kpi: str, equipment: str = "GENERAL") -> float:
    """Pega target real de get_kpi_targets (com cache); fallback hardcoded."""
    if _HAS_REAL_DATA:
        try:
            targets = _cached_targets(equipment)
            raw = float(targets[KPI_TARGET_FIELD[kpi]])
            return _to_display(kpi, raw)
        except Exception as e:
            logger.debug("V2: target real falhou (%s), fallback hardcoded", e)
    return float(KPI_META[kpi]["target"])


def _year_range(year: int) -> tuple:
    """Janela semi-aberta [start, end) — BR-12 compliance.
    end_date = primeiro instante do ano seguinte.
    """
    return datetime(year, 1, 1), datetime(year + 1, 1, 1)


def _month_range(year: int, month: int) -> tuple:
    """Janela semi-aberta [start, end) pra 1 mês. BR-12."""
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return start, end


_MES_PT_SHORT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                 "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def _iter_months_in_range(start: datetime, end: datetime):
    """Itera meses dentro da janela [start, end), cross-year ok.

    Yield: (label "Mmm/yy", m_start, m_end, year, month). Inclui mês onde start
    cai (alinhado ao 1º dia) e até o último mês cujo primeiro dia é < end.
    """
    y, m = start.year, start.month
    while True:
        m_start = datetime(y, m, 1)
        if m_start >= end:
            break
        m_end = datetime(y + 1, 1, 1) if m == 12 else datetime(y, m + 1, 1)
        label = f"{_MES_PT_SHORT[m - 1]}/{y % 100:02d}"
        yield label, m_start, m_end, y, m
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1


def _chart_months_with_status(start: datetime, end: datetime):
    """Retorna meses de contexto + status de cada mês vs [start, end).

    Política de expansão do range de display:
      - Range ≥12 meses → usa exato (contexto já é histórico amplo).
      - Range <12 meses, MESMO ano → expande pra Jan→Dez do start.year
        (12 barras de contexto histórico do ano calendário).
      - Range <12 meses, CROSS-YEAR → usa exato (evita expansão ambígua;
        cross-year curto não tem ano calendário óbvio pra escolher).

    Yield: (label, m_start, m_end, year, month, status)
      - status="in":      mês 100% dentro de [start, end)
      - status="partial": mês com overlap parcial
      - status="out":     mês 100% fora (sem overlap)
    """
    months_span = (end.year - start.year) * 12 + (end.month - start.month)
    # end pode cair em 01/<mês+1>; o mês "real" do end é mês anterior
    last_month_year = end.year if end.month > 1 else end.year - 1
    same_year = (start.year == last_month_year)
    if months_span >= 12 or not same_year:
        display_start, display_end = start, end
    else:
        display_start = datetime(start.year, 1, 1)
        display_end = datetime(start.year + 1, 1, 1)

    for label, m_start, m_end, y, m in _iter_months_in_range(display_start, display_end):
        if m_end <= start or m_start >= end:
            status = "out"
        elif m_start >= start and m_end <= end:
            status = "in"
        else:
            status = "partial"
        yield label, m_start, m_end, y, m, status


def _unpack_filters(filters: dict):
    """Extrai (start, end, codes_tuple, equipment_filter, year, lwb_simulate) do
    store-v2-filters.

    Default-safe: codes vazios → BREAKDOWN_CODES; equipment vazio → None (toda planta);
    lwb_simulate ausente → False (régua estrita do EasyTek).
    """
    f = filters or {}
    try:
        start = datetime.fromisoformat(f.get("start_iso") or f"{DEFAULT_YEAR}-01-01T00:00:00")
    except Exception:
        start = datetime(DEFAULT_YEAR, 1, 1)
    try:
        end = datetime.fromisoformat(f.get("end_iso") or f"{DEFAULT_YEAR + 1}-01-01T00:00:00")
    except Exception:
        end = datetime(DEFAULT_YEAR + 1, 1, 1)
    # Convenção pós-fix:
    #   None (chave ausente) → fallback (toda planta / BREAKDOWN_CODES) — legacy
    #   lista vazia          → intenção explícita ("nada selecionado")
    raw_codes = f.get("codes")
    codes = tuple(BREAKDOWN_CODES) if raw_codes is None else tuple(raw_codes)
    raw_eq = f.get("equipment")
    equipment_filter = None if raw_eq is None else list(raw_eq)
    year = start.year
    lwb_simulate = bool(f.get("lwb_simulate", False))
    return start, end, codes, equipment_filter, year, lwb_simulate


def _fetch_planta_monthly(kpi: str, start: datetime = None, end: datetime = None,
                          codes: tuple = None, equipment_filter=None,
                          lwb_simulate: bool = False) -> tuple:
    """Valores mensais agregados da planta no range — cobre cross-year.

    Retorna (labels, values, statuses) cobrindo SEMPRE 12 meses (ano de
    contexto) quando o filtro for menor que 1 ano. status por mês:
    "in"/"partial"/"out". equipment_filter=None significa toda planta.
    Usa CACHE process-level; 1ª chamada faz fetch+agg, subsequentes pegam cached.
    """
    if start is None or end is None:
        start, end = _year_range(DEFAULT_YEAR)
    if codes is None:
        codes = tuple(BREAKDOWN_CODES)
    months_meta = list(_chart_months_with_status(start, end))
    labels = [m[0] for m in months_meta]
    statuses = [m[5] for m in months_meta]

    # Range expandido pra cobrir TODOS os meses do display (incluindo "out").
    display_start = months_meta[0][1] if months_meta else start
    display_end = months_meta[-1][2] if months_meta else end

    if not _HAS_REAL_DATA:
        full = _mock_planta_mes(kpi)
        values = [full[(m[4] - 1) % 12] for m in months_meta]
        return labels, values, statuses
    try:
        kpi_data = _cached_fetch_kpi(display_start, display_end, codes, lwb_simulate=lwb_simulate)
        agg = _cached_agg(kpi_data, display_start, display_end, codes, equipment_filter,
                          lwb_simulate=lwb_simulate)
        field = KPI_FIELD_MAP[kpi]
        values = []
        for _, _, _, yy, mm, _st in months_meta:
            key = f"{yy}-{mm:02d}"
            entry = agg.get(key) or agg.get(mm) or {}
            raw = float(entry.get(field, 0) or 0)
            values.append(_to_display(kpi, raw))
        return labels, values, statuses
    except Exception as e:
        logger.warning("V2 planta %s falhou (%s) — retornando zeros", kpi, e)
        return labels, [0] * len(months_meta), statuses


def _fetch_equipment_monthly(kpi: str, equipment: str,
                             start: datetime = None, end: datetime = None,
                             codes: tuple = None,
                             lwb_simulate: bool = False) -> tuple:
    """Valores mensais do equipamento no range — cobre cross-year.

    Retorna (labels, values, statuses) cobrindo SEMPRE 12 meses (ano de contexto)
    quando filtro for menor que 1 ano. Status por mês: "in"/"partial"/"out".
    Loop sobre vários equipamentos no grid usa o MESMO cached kpi_data.
    """
    if start is None or end is None:
        start, end = _year_range(DEFAULT_YEAR)
    if codes is None:
        codes = tuple(BREAKDOWN_CODES)
    months_meta = list(_chart_months_with_status(start, end))
    labels = [m[0] for m in months_meta]
    statuses = [m[5] for m in months_meta]

    display_start = months_meta[0][1] if months_meta else start
    display_end = months_meta[-1][2] if months_meta else end

    if not _HAS_REAL_DATA:
        full = _mock_equipamento_mes(kpi, equipment)
        values = [full[(m[4] - 1) % 12] for m in months_meta]
        return labels, values, statuses
    try:
        kpi_data = _cached_fetch_kpi(display_start, display_end, codes, lwb_simulate=lwb_simulate)
        eq_data = kpi_data.get(equipment, [])
        if not eq_data:
            names = _cached_names()
            reverse = {v: k for k, v in names.items()}
            internal_id = reverse.get(equipment, equipment)
            eq_data = kpi_data.get(internal_id, [])
        field = KPI_FIELD_MAP[kpi]
        values = []
        for _, _, _, yy, mm, _st in months_meta:
            entry = next(
                (d for d in eq_data
                 if d.get("month") == mm and (d.get("year") in (None, yy))),
                None,
            )
            if entry:
                raw = float(entry.get(field, 0) or 0)
                values.append(_to_display(kpi, raw))
            else:
                values.append(0)
        return labels, values, statuses
    except Exception as e:
        logger.warning("V2 equip %s/%s falhou (%s) — retornando zeros", equipment, kpi, e)
        return labels, [0] * len(months_meta), statuses


def _fetch_daily_kpi(kpi: str, equipment: str, month: int,
                     year: int = DEFAULT_YEAR, codes: tuple = None) -> tuple:
    """Retorna (dias, valores) por dia do mês para o KPI/equipamento.
    codes default = BREAKDOWN_CODES (paridade V1). Fallback mock se erro.
    """
    if codes is None:
        codes = tuple(BREAKDOWN_CODES)
    if not _HAS_REAL_DATA:
        return _mock_dias(kpi, equipment, month)
    try:
        from src.utils.zpp_kpi_calculator import KPI_FORCE_ZERO_EQUIPMENTS
        start, end = _month_range(year, month)
        # Resolver id interno (equipment pode ser nome amigável "LCT-08")
        names = get_zpp_equipment_names()
        reverse = {v: k for k, v in names.items()}
        internal_id = reverse.get(equipment, equipment)
        # Short-circuit: equipamento do overlay tem KPI diário zerado direto.
        if internal_id in KPI_FORCE_ZERO_EQUIPMENTS:
            n_days = calendar.monthrange(year, month)[1]
            return list(range(1, n_days + 1)), [0] * n_days
        prod_df = fetch_zpp_production_data(start, end)
        brk_df = fetch_zpp_breakdown_data(start, end, breakdown_codes=list(codes))
        # Filtrar por equipamento
        if "linea" in prod_df.columns:
            prod_eq = prod_df[prod_df["linea"] == internal_id]
        else:
            prod_eq = prod_df.iloc[0:0]
        if "linea" in brk_df.columns:
            brk_eq = brk_df[brk_df["linea"] == internal_id]
        else:
            brk_eq = brk_df.iloc[0:0]
        n_days = calendar.monthrange(year, month)[1]
        dias = list(range(1, n_days + 1))
        values = []
        for d in dias:
            # Filtrar por dia (campo 'date' presente no DataFrame retornado)
            if "date" in prod_eq.columns and not prod_eq.empty:
                day_prod = prod_eq[prod_eq["date"].apply(lambda x: getattr(x, "day", None) == d)]
                active_h = day_prod["horasact"].sum() if "horasact" in day_prod.columns else 0
            else:
                active_h = 0
            if "date" in brk_eq.columns and not brk_eq.empty:
                day_brk = brk_eq[brk_eq["date"].apply(lambda x: getattr(x, "day", None) == d)]
                breakdown_h = day_brk["duracao_min"].sum() / 60 if "duracao_min" in day_brk.columns else 0
                num_failures = len(day_brk)
            else:
                breakdown_h = 0
                num_failures = 0
            # Calcula KPI do dia (internamente em horas pra MTBF/MTTR)
            if kpi == "mtbf":
                v = (active_h - breakdown_h) / num_failures if num_failures > 0 else active_h
            elif kpi == "mttr":
                v = breakdown_h / num_failures if num_failures > 0 else 0
            else:  # breakdown rate
                v = (breakdown_h / active_h * 100) if active_h > 0 else 0
            values.append(_to_display(kpi, v))  # MTTR: ×60 (h→min)
        return dias, values
    except Exception as e:
        logger.warning("V2 daily %s/%s/%s falhou (%s) — retornando zeros", equipment, month, kpi, e)
        n_days = calendar.monthrange(year, month)[1]
        return list(range(1, n_days + 1)), [0] * n_days


def _fetch_top_paradas_real(equipment: str, month: int, year: int = DEFAULT_YEAR,
                            top_n: int = 10, codes: tuple = None) -> list:
    """Top N paradas do mês — usa fetch_top_breakdowns_by_equipment da V1.
    Aplica BR-13 (agrupamento por dia+causa) já feito pela função V1.
    codes default = BREAKDOWN_CODES (paridade V1).
    """
    if codes is None:
        codes = tuple(BREAKDOWN_CODES)
    if not _HAS_REAL_DATA:
        return _mock_top_paradas_mes(equipment, month, top_n)
    try:
        start, end = _month_range(year, month)
        names = get_zpp_equipment_names()
        reverse = {v: k for k, v in names.items()}
        internal_id = reverse.get(equipment, equipment)
        items_v1 = fetch_top_breakdowns_by_equipment(
            internal_id, start, end, top_n=top_n, breakdown_codes=list(codes)
        )
        if not items_v1:
            return []
        items = []
        for it in items_v1:
            date_obj = it.get("date")
            if hasattr(date_obj, "strftime"):
                date_str = date_obj.strftime("%d/%m/%Y")
                day_int = date_obj.day
            else:
                date_str = str(date_obj)
                day_int = 0
            items.append({
                "day":         day_int,
                "date":        date_str or "—",
                "descricao":   it.get("descricao") or "—",
                "duracao_min": int(it.get("duracao_min") or 0),
                "count":       int(it.get("count") or 1),
                "codigo":      it.get("motivo") or "—",
            })
        return items
    except Exception as e:
        logger.warning("V2 top paradas %s/%s falhou (%s) — retornando vazio", equipment, month, e)
        return []


def _fetch_events_day_real(equipment: str, month: int, day: int,
                           year: int = DEFAULT_YEAR, codes: tuple = None) -> list:
    """Eventos (paradas) do dia para o equipamento.

    Filtra por `causa_do_desvio ∈ codes` (paridade V1). codes default =
    BREAKDOWN_CODES (códigos de manutenção). Revoga IM-05 do SDD indicators-v2
    que pedia "mostrar TODOS" — decisão sem apoio em BR/SP, contradiz V1.
    """
    if codes is None:
        codes = tuple(BREAKDOWN_CODES)
    if not _HAS_REAL_DATA:
        return _mock_eventos_dia(None, equipment, month, day)
    try:
        from src.utils.zpp_kpi_calculator import KPI_FORCE_ZERO_EQUIPMENTS
        names = get_zpp_equipment_names()
        reverse = {v: k for k, v in names.items()}
        internal_id = reverse.get(equipment, equipment)
        # Overlay KPI_FORCE_ZERO_EQUIPMENTS — não traz eventos (espelha SAP=0).
        if internal_id in KPI_FORCE_ZERO_EQUIPMENTS:
            return []
        start = datetime(year, month, day)
        end = start + timedelta(days=1)
        col = get_mongo_connection("ZPP_Paradas")
        if col is None:
            logger.warning("V2 eventos dia: collection ZPP_Paradas indisponivel — retornando vazio")
            return []
        query = {
            "centro_de_trabalho": internal_id,
            "inicio_execucao": {"$gte": start, "$lt": end},  # BR-12 semi-aberta
            "causa_do_desvio": {"$in": list(codes)},
        }
        cursor = col.find(
            query,
            {
                "_id": 0,
                "inicio_execucao": 1,
                "centro_de_trabalho": 1,
                "descricao": 1,
                "texto_de_confirmacao": 1,
                "duration_min": 1,
                "causa_do_desvio": 1,
            },
        ).sort("inicio_execucao", 1)
        eventos = []
        for doc in cursor:
            ts = doc.get("inicio_execucao")
            hora = ts.strftime("%H:%M") if hasattr(ts, "strftime") else "—"
            motivo = doc.get("causa_do_desvio", "—")
            # Prioridade igual à V1 fetch_top_breakdowns_by_equipment:
            # texto_de_confirmacao > descricao > fallback "Motivo {codigo}"
            causa = (doc.get("texto_de_confirmacao")
                     or doc.get("descricao")
                     or f"Motivo {motivo}")
            eventos.append({
                "Hora":          hora,
                "Equipamento":   equipment,
                "Causa":         causa,
                "Duração (min)": int(doc.get("duration_min", 0) or 0),
                "Código":        motivo,
            })
        return eventos
    except Exception as e:
        logger.warning("V2 eventos dia %s/%s/%s falhou (%s) — retornando vazio", equipment, month, day, e)
        return []


def _list_equipments_real() -> list:
    """Lista equipamentos reais com nome+categoria — usa CACHE de names e categories."""
    if not _HAS_REAL_DATA:
        return EQUIPAMENTOS
    try:
        names = _cached_names()
        categories = _cached_categories()
        eq_to_cat = {eq: cat for cat, eqs in categories.items() for eq in eqs}
        out = []
        for eq_id, friendly_name in names.items():
            out.append({
                "id":        friendly_name,
                "internal":  eq_id,
                "categoria": eq_to_cat.get(eq_id, "Outros"),
            })
        return out or EQUIPAMENTOS
    except Exception as e:
        logger.warning("V2 list equipments falhou (%s) — fallback mock", e)
        return EQUIPAMENTOS


# ============== HEATMAP DE FALHAS ==============
# Cores (4 bins + cinza pra sem produção).
_HEATMAP_COLOR_NO_PROD  = "#e9ecef"  # cinza claro
_HEATMAP_COLOR_GREEN    = "#d4edda"  # verde       — ≤ Y% da mediana (inclui 0)
_HEATMAP_COLOR_YELLOW   = "#fff3cd"  # amarelo     — entre Y% e X%
_HEATMAP_COLOR_RED      = "#f8a5ad"  # vermelho    — entre X% e Z%
_HEATMAP_COLOR_RED_DARK = "#c82333"  # vermelho forte — > Z%


def _heatmap_color_by_duration(duration_min: float, has_prod: bool,
                               median_min: float,
                               y_pct: int, x_pct: int, z_pct: int) -> tuple:
    """(cor_hex, label_status) por dia.

    BR de cor:
      sem produção       → cinza
      duration ≤ Y%      → verde (inclui duration=0)
      Y% < duration ≤ X% → amarelo
      X% < duration ≤ Z% → vermelho
      duration > Z%      → vermelho forte

    Sem mediana (median=0 — sem paradas no escopo), todo dia com
    produção vira verde.
    """
    if not has_prod:
        return _HEATMAP_COLOR_NO_PROD, "Sem produção"
    if median_min <= 0:
        return _HEATMAP_COLOR_GREEN, "Sem falhas (período sem mediana)"
    y_thr = median_min * (y_pct / 100.0)
    x_thr = median_min * (x_pct / 100.0)
    z_thr = median_min * (z_pct / 100.0)
    if duration_min <= y_thr:
        return _HEATMAP_COLOR_GREEN, ("Sem falhas" if duration_min == 0
                                      else f"{int(duration_min)}min")
    if duration_min <= x_thr:
        return _HEATMAP_COLOR_YELLOW, f"{int(duration_min)}min"
    if duration_min <= z_thr:
        return _HEATMAP_COLOR_RED, f"{int(duration_min)}min"
    return _HEATMAP_COLOR_RED_DARK, f"{int(duration_min)}min"


def _fetch_breakdown_duration_by_day(equipment_ids, start: datetime, end: datetime,
                                     codes: tuple) -> dict:
    """Retorna {date_str_YYYY-MM-DD: total_duration_min}.

    Soma duration_min agrupada por dia (formato YYYY-MM-DD).
    equipment_ids: lista de internal IDs OU None (planta inteira excluindo
    KPI_FORCE_ZERO_EQUIPMENTS, paridade com V1 que zera o overlay).
    codes: tupla de códigos de avaria; ausente → BREAKDOWN_CODES; vazia → {}.
    """
    if not _HAS_REAL_DATA:
        return {}
    if codes is not None and len(codes) == 0:
        return {}
    try:
        from src.utils.zpp_kpi_calculator import (
            ZPP_PARADAS_COLLECTION, KPI_FORCE_ZERO_EQUIPMENTS,
        )
        col = get_mongo_connection(ZPP_PARADAS_COLLECTION)
        if col is None:
            return {}
        match = {
            "_processed": True,
            "inicio_execucao": {"$gte": start, "$lt": end},
            "causa_do_desvio": {"$in": list(codes if codes is not None else BREAKDOWN_CODES)},
        }
        if equipment_ids is None:
            excluded = list(KPI_FORCE_ZERO_EQUIPMENTS)
            if excluded:
                match["centro_de_trabalho"] = {"$nin": excluded}
        else:
            if not equipment_ids:
                return {}
            match["centro_de_trabalho"] = {"$in": list(equipment_ids)}
        pipeline = [
            {"$match": match},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$inicio_execucao"}},
                "duration_total": {"$sum": "$duration_min"},
            }},
        ]
        return {doc["_id"]: float(doc.get("duration_total") or 0.0)
                for doc in col.aggregate(pipeline)}
    except Exception as e:
        logger.warning("V2 heatmap durações falhou (%s)", e)
        return {}


def _fetch_production_days(equipment_ids, start: datetime, end: datetime) -> set:
    """Retorna set de date_str_YYYY-MM-DD onde houve produção."""
    if not _HAS_REAL_DATA:
        return set()
    try:
        from src.utils.zpp_kpi_calculator import (
            ZPP_PRODUCAO_COLLECTION, KPI_FORCE_ZERO_EQUIPMENTS,
        )
        col = get_mongo_connection(ZPP_PRODUCAO_COLLECTION)
        if col is None:
            return set()
        match = {
            "_processed": True,
            "fininotif": {"$gte": start, "$lt": end},
        }
        if equipment_ids is None:
            excluded = list(KPI_FORCE_ZERO_EQUIPMENTS)
            if excluded:
                match["pto_trab"] = {"$nin": excluded}
        else:
            if not equipment_ids:
                return set()
            match["pto_trab"] = {"$in": list(equipment_ids)}
        pipeline = [
            {"$match": match},
            {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$fininotif"}}}},
        ]
        return {doc["_id"] for doc in col.aggregate(pipeline)}
    except Exception as e:
        logger.warning("V2 heatmap produção falhou (%s)", e)
        return set()


def _fetch_breakdown_durations_list(equipment_ids, start: datetime, end: datetime,
                                    codes: tuple) -> list:
    """Lista de duration_min por parada individual no período.

    Usado pra estatísticas (média/mediana das paradas vs contagem/soma
    acima/abaixo). equipment_ids=None → planta inteira (exclui overlay
    zerado). codes vazia → lista vazia. Filtra duration_min > 0.
    """
    if not _HAS_REAL_DATA:
        return []
    if codes is not None and len(codes) == 0:
        return []
    try:
        from src.utils.zpp_kpi_calculator import (
            ZPP_PARADAS_COLLECTION, KPI_FORCE_ZERO_EQUIPMENTS,
        )
        col = get_mongo_connection(ZPP_PARADAS_COLLECTION)
        if col is None:
            return []
        match = {
            "_processed": True,
            "inicio_execucao": {"$gte": start, "$lt": end},
            "causa_do_desvio": {"$in": list(codes if codes is not None else BREAKDOWN_CODES)},
        }
        if equipment_ids is None:
            excluded = list(KPI_FORCE_ZERO_EQUIPMENTS)
            if excluded:
                match["centro_de_trabalho"] = {"$nin": excluded}
        else:
            if not equipment_ids:
                return []
            match["centro_de_trabalho"] = {"$in": list(equipment_ids)}
        cursor = col.find(match, {"_id": 0, "duration_min": 1})
        durations = []
        for doc in cursor:
            d = doc.get("duration_min")
            if d is None:
                continue
            try:
                d = float(d)
            except (TypeError, ValueError):
                continue
            if d > 0:
                durations.append(d)
        return durations
    except Exception as e:
        logger.warning("V2 fetch durations falhou (%s)", e)
        return []


def _fetch_breakdown_by_day_by_equip(equipment_ids, start: datetime, end: datetime,
                                     codes: tuple) -> dict:
    """{date_str: [(equip_friendly, duration_min), ...]} ordenado desc por duração.

    Usado pra tooltip da planta — mostra contribuição de cada máquina.
    equipment_ids=None → planta (exclui KPI_FORCE_ZERO_EQUIPMENTS).
    """
    if not _HAS_REAL_DATA:
        return {}
    if codes is not None and len(codes) == 0:
        return {}
    try:
        from src.utils.zpp_kpi_calculator import (
            ZPP_PARADAS_COLLECTION, KPI_FORCE_ZERO_EQUIPMENTS,
        )
        col = get_mongo_connection(ZPP_PARADAS_COLLECTION)
        if col is None:
            return {}
        match = {
            "_processed": True,
            "inicio_execucao": {"$gte": start, "$lt": end},
            "causa_do_desvio": {"$in": list(codes if codes is not None else BREAKDOWN_CODES)},
        }
        if equipment_ids is None:
            excluded = list(KPI_FORCE_ZERO_EQUIPMENTS)
            if excluded:
                match["centro_de_trabalho"] = {"$nin": excluded}
        else:
            if not equipment_ids:
                return {}
            match["centro_de_trabalho"] = {"$in": list(equipment_ids)}
        pipeline = [
            {"$match": match},
            {"$group": {
                "_id": {
                    "date":      {"$dateToString": {"format": "%Y-%m-%d", "date": "$inicio_execucao"}},
                    "equipment": "$centro_de_trabalho",
                },
                "duration_total": {"$sum": "$duration_min"},
            }},
        ]
        names = _cached_names() or {}  # internal → friendly
        by_day: dict = {}
        for doc in col.aggregate(pipeline):
            ds = doc["_id"]["date"]
            internal = doc["_id"]["equipment"]
            dur = float(doc.get("duration_total") or 0.0)
            if dur <= 0:
                continue
            friendly = names.get(internal, internal)
            by_day.setdefault(ds, []).append((friendly, dur))
        for ds in by_day:
            by_day[ds].sort(key=lambda x: x[1], reverse=True)
        return by_day
    except Exception as e:
        logger.warning("V2 heatmap by_equip falhou (%s)", e)
        return {}


def _format_top_machines_until_median(items, median_min: float) -> str:
    """'PRENSA-01: 45min<br>LCT-08: 25min' até cumsum atingir mediana."""
    if not items or median_min <= 0:
        return ""
    cumsum = 0.0
    parts = []
    for name, dur in items:
        parts.append(f"• {name}: {int(dur)}min")
        cumsum += dur
        if cumsum >= median_min:
            break
    return "<br>".join(parts)


def _build_heatmap(start: datetime, end: datetime, codes: tuple,
                   equipment_ids=None, title: str = "Planta", compact: bool = False,
                   y_pct: int = None, x_pct: int = None, z_pct: int = None,
                   override_median_min: float = None):
    """Heatmap calendário (semana × dia da semana) das falhas POR DURAÇÃO.

    Retorna (fig, stats) onde stats inclui median_min, mean_min, y_thr_min,
    x_thr_min, z_thr_min, n_dias_falha.

    compact=True: mini-card (sem título interno, mais compacto).
      Tooltip mostra data + duração total do dia (escopo é o equipamento).
    compact=False (planta): tooltip mostra data + total + máquinas em
      ordem desc até a soma ultrapassar a mediana (uma por linha).

    override_median_min: se != None, usa esse valor como mediana de
    referência para as cores E para os limites Y/X/Z. Mean e mediana
    no dict stats continuam refletindo o escopo local (pra mostrar no
    header). Usado pelo modo 'visão geral' dos mini-cards (comparar
    com mediana da planta inteira).
    """
    import plotly.graph_objects as go
    from datetime import timedelta as _td
    import statistics as _stats

    if codes is None:
        codes = tuple(BREAKDOWN_CODES)
    if y_pct is None or x_pct is None or z_pct is None:
        from src.utils.breakdown_thresholds import get_heatmap_pcts
        cfg_y, cfg_x, cfg_z = get_heatmap_pcts()
        y_pct = cfg_y if y_pct is None else y_pct
        x_pct = cfg_x if x_pct is None else x_pct
        z_pct = cfg_z if z_pct is None else z_pct

    # Janela de DISPLAY (sempre cobre 12 meses quando filtro <1 ano). Dias
    # fora do filtro selecionado [start, end) aparecem com opacity baixa
    # ('disabled') — mesma lógica do eixo das barras mensais (IM-18).
    months_meta_disp = list(_chart_months_with_status(start, end))
    if months_meta_disp:
        display_start = months_meta_disp[0][1]
        display_end = months_meta_disp[-1][2]
    else:
        display_start, display_end = start, end

    duracoes = _fetch_breakdown_duration_by_day(equipment_ids, display_start, display_end, codes)
    producao = _fetch_production_days(equipment_ids, display_start, display_end)
    # Breakdown por máquina só pra heatmap da planta (mais de 1 equipamento).
    breakdown_by_machine = (
        _fetch_breakdown_by_day_by_equip(equipment_ids, display_start, display_end, codes)
        if not compact else {}
    )

    # Stats (média/mediana) refletem APENAS o filtro [start, end).
    def _in_filter_range(date_str: str) -> bool:
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            return False
        return start <= d < end

    nonzero_durations = [
        v for ds, v in duracoes.items()
        if _in_filter_range(ds) and ds in producao and v and v > 0
    ]
    median_min_local = _stats.median(nonzero_durations) if nonzero_durations else 0.0
    mean_min = (_stats.mean(nonzero_durations) if nonzero_durations else 0.0)
    # Mediana de comparação (override domina se passada e > 0)
    median_min_cmp = (override_median_min
                     if (override_median_min is not None and override_median_min > 0)
                     else median_min_local)
    y_thr_min = median_min_cmp * (y_pct / 100.0)
    x_thr_min = median_min_cmp * (x_pct / 100.0)
    z_thr_min = median_min_cmp * (z_pct / 100.0)

    weeks, days_of_week, colors, opacities, hover_texts = [], [], [], [], []
    cur = datetime(display_start.year, display_start.month, display_start.day)
    end_day = datetime(display_end.year, display_end.month, display_end.day)
    base_iso_week = cur.isocalendar()[1]
    base_year = cur.year
    while cur < end_day:
        ds = cur.strftime("%Y-%m-%d")
        in_filter = start <= cur < end
        has_prod = ds in producao
        duration = float(duracoes.get(ds, 0)) if has_prod else 0.0
        color, _status = _heatmap_color_by_duration(
            duration, has_prod, median_min_cmp, y_pct, x_pct, z_pct
        )
        iso_yr, iso_wk, _ = cur.isocalendar()
        week_idx = iso_wk - base_iso_week + (52 if iso_yr > base_year else 0)
        weeks.append(week_idx)
        days_of_week.append(cur.weekday())
        colors.append(color)
        opacities.append(1.0 if in_filter else 0.22)
        # Tooltip — planta lista máquinas, mini só mostra duração.
        if not in_filter:
            txt = (
                f"<b>{cur.strftime('%d/%m/%Y')}</b><br>"
                f"<i>Fora do filtro selecionado</i>"
            )
        elif not has_prod:
            txt = f"<b>{cur.strftime('%d/%m/%Y')}</b><br>Sem produção"
        elif duration <= 0:
            txt = f"<b>{cur.strftime('%d/%m/%Y')}</b><br>Sem paradas"
        else:
            txt = (
                f"<b>{cur.strftime('%d/%m/%Y')}</b><br>"
                f"Total: {int(duration)}min"
            )
            if not compact:
                top_str = _format_top_machines_until_median(
                    breakdown_by_machine.get(ds, []), median_min_cmp
                )
                if top_str:
                    txt += f"<br>{top_str}"
        hover_texts.append(txt)
        cur += _td(days=1)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=weeks,
        y=days_of_week,
        mode="markers",
        marker=dict(
            size=22,
            color=colors,
            opacity=opacities,
            symbol="square",
            line=dict(color="rgba(0,0,0,0.08)", width=1),
        ),
        text=hover_texts,
        hovertemplate="%{text}<extra></extra>",
        showlegend=False,
    ))

    weekday_labels = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    fig.update_layout(
        title=None if compact else dict(text=title, font=dict(size=13)),
        margin=dict(l=40 if compact else 50, r=10, t=10 if compact else 36, b=20),
        height=200 if compact else 260,
        plot_bgcolor="white",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, range=[-0.5, (max(weeks) if weeks else 0) + 0.5]),
        yaxis=dict(
            tickmode="array",
            tickvals=list(range(7)),
            ticktext=weekday_labels,
            autorange="reversed",
            tickfont=dict(size=9 if compact else 11),
        ),
    )
    stats = {
        "median_min":        median_min_local,
        "median_min_cmp":    median_min_cmp,
        "mean_min":          mean_min,
        "y_thr_min":         y_thr_min,
        "x_thr_min":         x_thr_min,
        "z_thr_min":         z_thr_min,
        "y_pct":             y_pct,
        "x_pct":             x_pct,
        "z_pct":             z_pct,
        "n_dias_falha":      len(nonzero_durations),
        "is_override":       override_median_min is not None and override_median_min > 0,
    }
    return fig, stats


def _mock_planta_mes(kpi):
    """12 valores mensais da planta inteira pro KPI."""
    rng = random.Random(_seed("planta", kpi))
    meta = KPI_META[kpi]
    return [round(rng.uniform(meta["min"], meta["max"]), 2) for _ in range(12)]


def _mock_equipamento_mes(kpi, equipment):
    rng = random.Random(_seed("eq", kpi, equipment))
    meta = KPI_META[kpi]
    return [round(rng.uniform(meta["min"] * 0.7, meta["max"] * 1.2), 2) for _ in range(12)]


def _mock_dias(kpi, equipment, month):
    rng = random.Random(_seed("dia", kpi, equipment, month))
    # ano fixo 2026 pra POC
    n_days = calendar.monthrange(2026, month)[1]
    meta = KPI_META[kpi]
    return list(range(1, n_days + 1)), [
        round(rng.uniform(meta["min"] * 0.5, meta["max"] * 1.4), 2) for _ in range(n_days)
    ]


def _mock_top_paradas_mes(equipment, month, top_n=10):
    """Top paradas do mês, agrupadas por (dia, causa). Determinístico por seed."""
    from collections import defaultdict
    rng = random.Random(_seed("top", equipment, month))
    n_days = calendar.monthrange(2026, month)[1]
    grouped = defaultdict(lambda: {"duracao_min": 0, "count": 0, "codigo": ""})
    for d in range(1, n_days + 1):
        n = rng.randint(0, 4)
        for _ in range(n):
            causa = rng.choice(CAUSAS)
            key = (d, causa)
            grouped[key]["duracao_min"] += rng.randint(15, 240)
            grouped[key]["count"] += 1
            grouped[key]["codigo"] = rng.choice(["201", "S201", "202", "S202", "203", "S203"])

    items = []
    for (d, causa), v in grouped.items():
        items.append({
            "day": d,
            "date": f"{d:02d}/{month:02d}/2026",
            "descricao": causa,
            "duracao_min": v["duracao_min"],
            "count": v["count"],
            "codigo": v["codigo"],
        })
    items.sort(key=lambda x: x["duracao_min"], reverse=True)
    return items[:top_n]


def _top_paradas_h_bar(items, equipment, month, td=None,
                       threshold_1=None, threshold_2=None):
    """Barras horizontais top 5 (gradient vermelho→verde por intensidade).

    threshold_1 / threshold_2: linhas verticais (amarela / rosa) em min do
    gatilho cadastrado pro equipamento. Se None, não desenha.
    td: dict TRANS[lang] pra title/axis i18n.
    """
    td = td or {}
    if not items:
        fig = go.Figure()
        fig.add_annotation(text="Nenhuma parada no mês.", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False)
        fig.update_layout(height=300, plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)")
        return fig

    top5 = items[:5]

    def wrap(text, max_chars=22):
        if not text:
            text = "—"
        words, lines, cur, ln = str(text).split(), [], [], 0
        for w in words:
            wl = len(w) + (1 if cur else 0)
            if ln + wl > max_chars and cur:
                lines.append(" ".join(cur)); cur, ln = [w], len(w)
            else:
                cur.append(w); ln += wl
        if cur: lines.append(" ".join(cur))
        return "<br>".join(lines)

    # Y posicional (0..N-1) com tickvals/ticktext separados — evita Plotly empilhar
    # barras com mesmo label (caso de itens agrupados com data+descrição idênticas
    # mas códigos diferentes; ex: PRENSA-02 mar/2026, LCL-4,5 fev/2026).
    y_pos = list(range(len(top5)))
    y_ticktext = [f"{(bd.get('date') or '—')[:5]}<br>{wrap(bd.get('descricao'))}" for bd in top5]
    x_values = [bd.get("duracao_min") or 0 for bd in top5]
    counts = [bd.get("count") or 1 for bd in top5]
    max_d = max(x_values) if x_values else 1
    colors = []
    for d in x_values:
        r = d / max_d
        if r > 0.8: colors.append("#8b0000")
        elif r > 0.6: colors.append("#dc3545")
        elif r > 0.4: colors.append("#fd7e14")
        elif r > 0.2: colors.append("#ffc107")
        else: colors.append("#20c997")

    text_vals = [f"{x}min ({c}x)" if c > 1 else f"{x}min" for x, c in zip(x_values, counts)]
    # customdata pra hover mostrar label completo (label real, não índice)
    custom = [[lbl, bd.get("codigo", "—"), bd.get("count", 1)] for lbl, bd in zip(y_ticktext, top5)]

    fig = go.Figure(go.Bar(
        x=x_values,
        y=y_pos,  # posicional — sem colisão
        orientation="h",
        marker=dict(color=colors, line=dict(color="rgba(0,0,0,0.3)", width=1), cornerradius=4),
        text=text_vals,
        textposition="outside",
        textfont=dict(size=11),
        customdata=custom,
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            f"{td.get('chart_codigo','Código')}: %{{customdata[1]}}<br>"
            f"{td.get('chart_duracao_min','Duração (min)')}: %{{x}} min<br>"
            f"{td.get('chart_eventos','Eventos')}: %{{customdata[2]}}"
            "<extra></extra>"
        ),
    ))
    top_title_tpl = td.get("chart_top_n_paradas", "Top {n} Paradas")
    # Linha vertical só do gatilho_1. gatilho_2 fica reservado pra animação
    # das células (style_data_conditional da tabela), não polui o gráfico.
    extra_x_for_axis = max_d
    if threshold_1 is not None:
        extra_x_for_axis = max(extra_x_for_axis, threshold_1)
        fig.add_vline(
            x=threshold_1,
            line=dict(color="#cc9a06", width=2, dash="dash"),
            annotation_text=f"Gatilho 1: {threshold_1}min",
            annotation_position="top",
            annotation=dict(font=dict(size=10, color="#cc9a06"), bgcolor="rgba(255,243,205,0.9)"),
        )

    fig.update_layout(
        title=dict(
            text=f"{top_title_tpl.format(n=len(top5))} — {equipment} — {MESES_PT[month-1]}/2026",
            x=0.5, xanchor="center", font=dict(size=13),
        ),
        xaxis=dict(title=dict(text=td.get("chart_duracao_min","Duração (min)"), font=dict(size=10)),
                   range=[0, extra_x_for_axis + 50]),
        yaxis=dict(
            autorange="reversed",
            tickmode="array",
            tickvals=y_pos,
            ticktext=y_ticktext,
            tickfont=dict(size=10),
        ),
        margin=dict(l=140, r=40, t=60, b=40),
        plot_bgcolor="white",
        paper_bgcolor="rgba(0,0,0,0)",
        height=380,
        showlegend=False,
        bargap=0.35,
    )
    return fig


def _mock_eventos_dia(kpi, equipment, month, day):
    rng = random.Random(_seed("evt", kpi, equipment, month, day))
    n = rng.randint(0, 8)
    eventos = []
    for _ in range(n):
        h = rng.randint(0, 23)
        m = rng.randint(0, 59)
        dur = rng.randint(5, 360)
        eventos.append({
            "Hora": f"{h:02d}:{m:02d}",
            "Equipamento": equipment,
            "Causa": rng.choice(CAUSAS),
            "Duração (min)": dur,
            "Código": rng.choice(["201", "S201", "202", "S202", "203", "S203"]),
        })
    eventos.sort(key=lambda e: e["Hora"])
    return eventos


def _bar_rich(x, y, title, color, unit="", target=None, direction="higher",
              td=None, bar_statuses=None):
    """Wrap _bar adicionando hovertemplate enriquecido (valor, meta, delta, status).

    td: dict TRANS[lang] pra i18n labels.
    bar_statuses: lista paralela a y com "in"|"partial"|"out" (propaga p/ _bar).
    """
    td = td or {}
    fig = _bar(x, y, title, color, unit, target=target, show_trend=True,
               compact=False, td=td, bar_statuses=bar_statuses)
    if target is not None:
        # Customdata: [target, delta_abs, status_emoji]
        custom = []
        for v in y:
            if v in (None, 0):
                custom.append([target, 0, "—"])
                continue
            delta = v - target
            if direction == "lower":
                emoji = "✅" if v <= target else ("⚠️" if v <= target * 1.1 else "🔴")
            else:
                emoji = "✅" if v >= target else ("⚠️" if v >= target * 0.9 else "🔴")
            custom.append([target, delta, emoji])
        bar_trace = fig.data[0]
        bar_trace.customdata = custom
        l_val = td.get("chart_value", "Valor")
        l_meta = td.get("chart_target", "Meta")
        l_delta = td.get("chart_delta", "Δ")
        l_status = td.get("chart_status", "Status")
        bar_trace.hovertemplate = (
            "<b>%{x}</b><br>"
            "━━━━━━━━━━━━━<br>"
            f"<b>{l_val}:</b> %{{y}}{unit}<br>"
            f"<b>{l_meta}:</b>  %{{customdata[0]}}{unit}<br>"
            f"<b>{l_delta}:</b>     %{{customdata[1]:+.2f}}{unit}<br>"
            f"<b>{l_status}:</b> %{{customdata[2]}}"
            "<extra></extra>"
        )
    return fig


def _empty_state(icon="bi-emoji-smile", title="Nada por aqui", desc="Sem registros no período selecionado."):
    """Empty state ilustrado uniforme (substitui Alert simples)."""
    return html.Div(
        [
            html.I(className=f"bi {icon} v2-empty-icon"),
            html.Div(title, className="v2-empty-title"),
            html.Div(desc, className="v2-empty-desc"),
        ],
        className="v2-empty-state",
    )


_PARTIAL_COLOR = "#fd7e14"   # laranja — mês com overlap parcial do filtro
_OUT_COLOR = "#d6d8db"       # cinza claro — mês fora do filtro selecionado


def _bar(x, y, title, color, unit="", target=None, show_trend=True, compact=False,
         td=None, bar_statuses=None):
    """Bar chart com overlay opcional de meta (linha tracejada) e tendência (poly grau 2).

    target: valor da linha de meta horizontal; None oculta.
    show_trend: True desenha tendência sobre as barras (só pelos pontos "in").
    compact: True reduz fontes/margens pra mini-cards.
    td: dict de traduções (TRANS[lang]) pra labels "Tendência"/"Meta"/"Valor"; default PT.
    bar_statuses: lista paralela a y, cada item "in"|"partial"|"out". None=tudo "in".
    """
    td = td or {}
    bar_color = color
    target_color = "#6c757d"
    trend_color = "#212529"

    fig = go.Figure()

    # Cor por barra quando statuses fornecidos
    if bar_statuses and len(bar_statuses) == len(y):
        marker_color = [
            _OUT_COLOR if s == "out" else (_PARTIAL_COLOR if s == "partial" else color)
            for s in bar_statuses
        ]
        marker_opacity = [0.45 if s == "out" else 1.0 for s in bar_statuses]
    else:
        marker_color = bar_color
        marker_opacity = 1.0
        bar_statuses = None

    fig.add_trace(
        go.Bar(
            x=x,
            y=y,
            marker_color=marker_color,
            marker_opacity=marker_opacity,
            text=[f"{v}{unit}" for v in y] if not compact else None,
            textposition="outside",
            cliponaxis=False,  # texto outside não corta no topo
            hovertemplate=f"<b>%{{x}}</b><br>%{{y}}{unit}<extra></extra>",
            name=td.get("chart_value", "Valor"),
            showlegend=False,
        )
    )

    if show_trend and len(y) >= 3:
        x_idx = np.arange(len(y))
        try:
            deg = 2 if len(y) >= 5 else 1
            coefs = np.polyfit(x_idx, y, deg)
            x_dense = np.linspace(0, len(y) - 1, 60)
            y_trend = np.polyval(coefs, x_dense)
            # mapeia x_dense de volta pra labels só nos pontos inteiros — mas Plotly aceita categórico
            # truque: usar os mesmos x labels via interpolação inteira
            x_trend_labels = []
            for xi in x_dense:
                idx_left = int(np.floor(xi))
                idx_right = min(idx_left + 1, len(x) - 1)
                frac = xi - idx_left
                x_trend_labels.append(x[idx_left] if frac < 0.5 else x[idx_right])
            # Plotly não interpola categóricos — usa modo numérico
            fig.add_trace(
                go.Scatter(
                    x=list(x_idx),
                    y=np.polyval(coefs, x_idx),
                    mode="lines",
                    line=dict(color=trend_color, width=2, dash="dot"),
                    name=td.get("chart_trend", "Tendência"),
                    hovertemplate=td.get("chart_trend", "Tendência") + ": %{y:.2f}" + unit + "<extra></extra>",
                    xaxis="x2",
                    showlegend=not compact,
                )
            )
        except Exception:
            pass

    if target is not None:
        meta_label = td.get("chart_target", "Meta")
        fig.add_hline(
            y=target,
            line=dict(color=target_color, width=2, dash="dash"),
            annotation_text=f"{meta_label} {target}{unit}" if not compact else f"{target}{unit}",
            annotation_position="top right",
            annotation_font=dict(size=10 if compact else 12, color=target_color),
        )

    # Range Y explícito: max(barras, target) * 1.22 — espaço pro texto outside + meta label
    y_top_candidates = [max(y)] if y else [0]
    if target is not None:
        y_top_candidates.append(target)
    y_top = max(y_top_candidates) * 1.22
    y_bottom = min(0, (min(y) if y else 0) * 1.05)

    fig.update_layout(
        title=dict(text=title, font=dict(size=12 if compact else 14)),
        margin=dict(l=30 if compact else 40, r=15 if compact else 20,
                    t=55 if compact else 70, b=30 if compact else 40),
        plot_bgcolor="white",
        paper_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(gridcolor="#eee", range=[y_bottom, y_top]),
        xaxis=dict(title="", type="category"),
        # eixo paralelo numérico oculto pra desenhar a tendência sobre categorias
        xaxis2=dict(
            overlaying="x",
            range=[-0.5, len(y) - 0.5],
            visible=False,
            matches=None,
        ),
        showlegend=False if compact else (show_trend and target is not None),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    font=dict(size=10)),
    )
    return fig


def register_indicators_v2_callbacks(app):
    # Import TRANS uma vez (usado por callbacks i18n e render_modal)
    from src.pages.maintenance.indicators_v2 import TRANS as _TRANS

    # ==================== i18n ====================
    # 1. Click bandeira → store-v2-lang
    @app.callback(
        Output("store-v2-lang", "data"),
        Input({"type": "v2-lang-btn", "lang": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def set_lang(_clicks):
        trig = dash.callback_context.triggered_id
        if isinstance(trig, dict) and trig.get("type") == "v2-lang-btn":
            return trig.get("lang", "pt")
        return no_update

    # 2. store-v2-lang → active class nas 3 bandeiras
    @app.callback(
        Output({"type": "v2-lang-btn", "lang": ALL}, "className"),
        Input("store-v2-lang", "data"),
        State({"type": "v2-lang-btn", "lang": ALL}, "id"),
    )
    def highlight_active_flag(lang, ids):
        base = "v2-lang-flag"
        return [f"{base} active" if (i or {}).get("lang") == (lang or "pt") else base for i in ids]

    # 3. store-v2-lang → todos textos i18n
    I18N_OUTPUTS = [
        ("v2-i18n-page-title",     "page_title"),
        ("v2-i18n-page-subtitle",  "page_subtitle"),
        ("v2-i18n-btn-refresh",    "btn_refresh"),
        ("v2-i18n-btn-filters",    "btn_filters"),
        ("v2-i18n-btn-export",     "btn_export"),
        ("v2-i18n-btn-apply",      "btn_apply"),
        ("v2-i18n-btn-back",       "mdl_back"),
        ("v2-i18n-btn-close",      "mdl_close"),
        ("v2-i18n-filter-period",  "filter_period"),
        ("v2-i18n-filter-year",    "filter_year"),
        ("v2-i18n-filter-range",   "filter_range"),
        ("v2-i18n-filter-equip",   "filter_equip"),
        ("v2-i18n-filter-codes",   "filter_codes"),
        ("v2-i18n-kpi-sub-mtbf",   "kpi_mtbf_sub"),
        ("v2-i18n-kpi-sub-mttr",   "kpi_mttr_sub"),
        ("v2-i18n-kpi-sub-breakdown", "kpi_br_sub"),
        ("v2-i18n-kpi-title-mtbf",      "kpi_mtbf_title"),
        ("v2-i18n-kpi-title-mttr",      "kpi_mttr_title"),
        ("v2-i18n-kpi-title-breakdown", "kpi_br_title"),
        ("v2-i18n-tl-title",       "tl_title"),
        ("v2-i18n-tl-focus",       "tl_focus"),
        ("v2-i18n-tl-scale",       "tl_scale"),
        ("v2-i18n-tl-nav",         "tl_nav"),
        ("v2-i18n-tl-btn-hours",   "tl_hours"),
        ("v2-i18n-tl-btn-days",    "tl_days"),
        ("v2-i18n-tl-btn-today",   "tl_today"),
        ("v2-i18n-lg-producao",    "lg_producao"),
        ("v2-i18n-lg-avaria",      "lg_avaria"),
        ("v2-i18n-lg-setup",       "lg_setup"),
        ("v2-i18n-lg-logistica",   "lg_logistica"),
        ("v2-i18n-lg-refeicao",    "lg_refeicao"),
        ("v2-i18n-lg-mtto",        "lg_mtto"),
        ("v2-i18n-lg-processo",    "lg_processo"),
        ("v2-i18n-beta-badge",     "beta_badge"),
    ]

    @app.callback(
        [Output(eid, "children") for eid, _ in I18N_OUTPUTS] + [
            Output("switch-v2-mtto-only", "label"),
            Output("tab-v2-general-component", "label"),
            Output("tab-v2-data-component", "label"),
            Output("tab-v2-report-component", "label"),
            Output("filter-v2-period-type", "options"),
            Output("filter-v2-equipment", "placeholder"),
            Output("v2-beta-tooltip", "children"),
        ],
        Input("store-v2-lang", "data"),
    )
    def translate_all(lang):
        lang = lang or "pt"
        d = _TRANS.get(lang, _TRANS["pt"])
        results = [d.get(key, key) for _, key in I18N_OUTPUTS]
        results.append(d.get("tl_only_av", "Só avaria"))
        results.append(d.get("tab_general", "📊 Geral"))
        results.append(d.get("tab_data", "📋 Dados"))
        results.append(d.get("tab_report", "📅 Relatório"))
        results.append([
            {"label": d.get("period_year", "Ano completo"), "value": "year"},
            {"label": d.get("period_last12", "Últimos 12 meses"), "value": "last12"},
            {"label": d.get("period_custom", "Personalizado"), "value": "custom"},
        ])
        results.append(f"({'all' if lang == 'en' else ('todos' if lang == 'pt' else 'todos')})")
        results.append(d.get("beta_tooltip", "Página em validação. Dados sintéticos."))
        return results

    # IM-11 — Toggle do collapse de filtros + condicional visibilidade ano/range
    @app.callback(
        Output("collapse-v2-filters", "is_open"),
        Input("btn-filters-indicators-v2", "n_clicks"),
        State("collapse-v2-filters", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_v2_filters(n, is_open):
        return not bool(is_open)

    @app.callback(
        Output("col-filter-v2-year", "style"),
        Output("col-filter-v2-range", "style"),
        Input("filter-v2-period-type", "value"),
    )
    def toggle_period_fields(ptype):
        if ptype == "custom":
            return {"display": "none"}, {"display": "block"}
        return {"display": "block"}, {"display": "none"}

    # Toggle "Sem ferramentaria" — segue padrão sync/hydrate do switch mtto-only.
    # OFF (default) = inclui códigos 202/S202; ON = filtra eles dos painéis de paradas
    # (níveis mes-top e tabela do drilldown).
    @app.callback(
        Output("store-v2-hide-tooling", "data"),
        Input("switch-v2-hide-tooling", "value"),
        prevent_initial_call=True,
    )
    def sync_hide_tooling(value):
        return bool(value)

    @app.callback(
        Output("switch-v2-hide-tooling", "value"),
        Input("modal-v2", "is_open"),
        State("store-v2-hide-tooling", "data"),
    )
    def hydrate_hide_tooling(is_open, stored):
        # Hidrata o switch com o último valor persistido sempre que o modal abre.
        if not is_open:
            from dash.exceptions import PreventUpdate
            raise PreventUpdate
        return bool(stored)

    @app.callback(
        Output("wrap-v2-hide-tooling", "style"),
        Input("store-v2-level", "data"),
    )
    def toggle_hide_tooling_visibility(level):
        # Switch só aparece nos níveis que listam paradas individuais.
        if level in ("mes-top", "tabela"):
            return {"display": "block"}
        return {"display": "none"}

    # ============== Modal de cadastro de gatilhos por equipamento ==============

    @app.callback(
        Output("modal-v2-thresholds", "is_open"),
        Input("btn-thresholds-v2", "n_clicks"),
        Input("btn-thresholds-cancel", "n_clicks"),
        Input("btn-thresholds-save", "n_clicks"),
        State("modal-v2-thresholds", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_thresholds_modal(open_n, cancel_n, save_n, is_open):
        trig = dash.callback_context.triggered_id
        if trig == "btn-thresholds-v2":
            return True
        if trig in ("btn-thresholds-cancel", "btn-thresholds-save"):
            return False
        return is_open

    @app.callback(
        Output("modal-thresholds-table", "children"),
        Output("modal-thresholds-status", "children", allow_duplicate=True),
        Input("modal-v2-thresholds", "is_open"),
        prevent_initial_call=True,
    )
    def populate_thresholds_table(is_open):
        if not is_open:
            from dash.exceptions import PreventUpdate
            raise PreventUpdate
        from flask_login import current_user
        # Determina se o usuário pode editar (level 2+ — perfil manutencao/admin)
        try:
            can_edit = current_user.is_authenticated and getattr(current_user, "level", 0) >= 2
        except Exception:
            can_edit = False
        eq_list = _list_equipments_real()
        cadastro = get_all_thresholds()
        rows = []
        for eq in eq_list:
            eq_id = eq["id"]
            t1 = cadastro.get(eq_id, DEFAULT_THRESHOLD_MIN)
            t2 = derive_threshold_2(t1)
            rows.append({
                "Equipamento": eq_id,
                "Categoria":   eq.get("categoria", "—"),
                "Gatilho 1 (min)": t1,
                "Gatilho 2 (min)": t2,
            })
        editable_cols = ["Gatilho 1 (min)"] if can_edit else []
        table = dash_table.DataTable(
            id="thresholds-datatable",
            data=rows,
            columns=[
                {"name": "Equipamento", "id": "Equipamento", "editable": False},
                {"name": "Categoria", "id": "Categoria", "editable": False},
                {"name": "Gatilho 1 (min)", "id": "Gatilho 1 (min)",
                 "editable": can_edit, "type": "numeric"},
                {"name": "Gatilho 2 (min) — auto ×1,20", "id": "Gatilho 2 (min)",
                 "editable": False, "type": "numeric"},
            ],
            editable=can_edit,
            style_table={"overflowX": "auto"},
            style_cell={"padding": "8px", "fontFamily": "system-ui", "fontSize": "13px"},
            style_header={
                "backgroundColor": "#f1f3f5",
                "fontWeight": "600",
                "borderBottom": "2px solid #dee2e6",
            },
            style_data_conditional=[
                {"if": {"column_id": "Gatilho 1 (min)"},
                 "backgroundColor": "#fff8e1" if can_edit else "transparent",
                 "fontWeight": "600"},
                {"if": {"column_id": "Gatilho 2 (min)"},
                 "backgroundColor": "#fde4e7", "color": "#6c757d"},
            ],
            page_size=20,
            sort_action="native",
        )
        if can_edit:
            status = html.Span(
                "✏️ Edite os valores na coluna Gatilho 1. Gatilho 2 recalcula automaticamente. "
                "Clique em Salvar pra persistir.",
                className="text-muted small",
            )
        else:
            status = html.Span(
                "🔒 Sem permissão pra editar (requer nível 2+). Visualização somente.",
                className="text-muted small",
            )
        return table, status

    @app.callback(
        Output("thresholds-datatable", "data", allow_duplicate=True),
        Input("thresholds-datatable", "data_timestamp"),
        State("thresholds-datatable", "data"),
        State("thresholds-datatable", "data_previous"),
        prevent_initial_call=True,
    )
    def recompute_threshold_2(_ts, data, data_prev):
        # Sempre que gatilho_1 muda, recalcula gatilho_2 ao vivo.
        if not data:
            from dash.exceptions import PreventUpdate
            raise PreventUpdate
        changed = False
        for row in data:
            try:
                t1 = int(float(row.get("Gatilho 1 (min)", DEFAULT_THRESHOLD_MIN) or DEFAULT_THRESHOLD_MIN))
            except (TypeError, ValueError):
                t1 = DEFAULT_THRESHOLD_MIN
            new_t2 = derive_threshold_2(t1)
            if row.get("Gatilho 2 (min)") != new_t2:
                row["Gatilho 2 (min)"] = new_t2
                changed = True
        if not changed:
            from dash.exceptions import PreventUpdate
            raise PreventUpdate
        return data

    @app.callback(
        Output("modal-thresholds-status", "children", allow_duplicate=True),
        Input("btn-thresholds-save", "n_clicks"),
        State("thresholds-datatable", "data"),
        State("input-heatmap-y-pct", "value"),
        State("input-heatmap-x-pct", "value"),
        State("input-heatmap-z-pct", "value"),
        prevent_initial_call=True,
    )
    def save_thresholds_callback(n, data, hm_y, hm_x, hm_z):
        if not n:
            from dash.exceptions import PreventUpdate
            raise PreventUpdate
        from flask_login import current_user
        try:
            if not current_user.is_authenticated or getattr(current_user, "level", 0) < 2:
                return html.Span("🔒 Sem permissão pra salvar (requer nível 2+).",
                                 className="text-danger small")
        except Exception:
            return html.Span("🔒 Sem permissão pra salvar.", className="text-danger small")
        username = getattr(current_user, "username", "unknown")
        cadastro_atual = get_all_thresholds()
        saved = 0
        for row in data or []:
            eq_id = row.get("Equipamento")
            try:
                t1 = int(float(row.get("Gatilho 1 (min)", DEFAULT_THRESHOLD_MIN)))
            except (TypeError, ValueError):
                continue
            if t1 < 1:
                continue
            if cadastro_atual.get(eq_id) == t1:
                continue  # sem mudança
            if set_threshold(eq_id, t1, updated_by=username):
                saved += 1
        # Limites do heatmap (Y/X/Z — % da mediana)
        from src.utils.breakdown_thresholds import (
            get_heatmap_pcts, set_heatmap_pcts,
        )
        hm_saved = False
        if hm_y is not None and hm_x is not None and hm_z is not None:
            cur_y, cur_x, cur_z = get_heatmap_pcts()
            try:
                hy, hx, hz = int(hm_y), int(hm_x), int(hm_z)
            except (TypeError, ValueError):
                hy, hx, hz = cur_y, cur_x, cur_z
            if (hy, hx, hz) != (cur_y, cur_x, cur_z):
                hm_saved = set_heatmap_pcts(hy, hx, hz, updated_by=username)
        invalidate_thresholds_cache()
        msg = f"✅ {saved} gatilho(s) atualizado(s) por {username}"
        if hm_saved:
            msg += " · limites Y/X/Z do heatmap salvos"
        return html.Span(msg + ". Modal fechará.", className="text-success small")

    # Hidrata os inputs Y/X/Z sempre que o modal abrir
    @app.callback(
        Output("input-heatmap-y-pct", "value"),
        Output("input-heatmap-x-pct", "value"),
        Output("input-heatmap-z-pct", "value"),
        Input("modal-v2-thresholds", "is_open"),
    )
    def hydrate_heatmap_pcts(is_open):
        if not is_open:
            return no_update, no_update, no_update
        from src.utils.breakdown_thresholds import get_heatmap_pcts
        y, x, z = get_heatmap_pcts()
        return y, x, z

    @app.callback(
        Output("filter-v2-equipment", "options"),
        Output("filter-v2-equipment", "value"),
        Input("url", "pathname"),
    )
    def populate_equipment_filter(pathname):
        if pathname != "/maintenance/indicators-v2":
            return no_update, no_update
        eq_list = _list_equipments_real()
        # Value usa internal ID (canonical) pra evitar dependência da cache de
        # names em conversões friendly→internal. Label mostra o friendly.
        options = [
            {"label": eq["id"], "value": eq.get("internal") or eq["id"]}
            for eq in eq_list
        ]
        value = [eq.get("internal") or eq["id"] for eq in eq_list]
        return options, value

    # IM-11 — Apply filters → escreve store-v2-filters
    @app.callback(
        Output("store-v2-filters", "data"),
        Input("btn-apply-v2-filters", "n_clicks"),
        Input("btn-refresh-indicators-v2", "n_clicks"),
        Input("url", "pathname"),
        Input("switch-v2-lwb-simulate", "value"),
        State("filter-v2-period-type", "value"),
        State("filter-v2-reference-year", "value"),
        State("filter-v2-date-range", "start_date"),
        State("filter-v2-date-range", "end_date"),
        State("filter-v2-equipment", "value"),
        State("filter-v2-breakdown-codes", "value"),
        prevent_initial_call=False,
    )
    def apply_v2_filters(apply_n, refresh_n, pathname, lwb_sim, ptype, year, sdate, edate, equip, codes):
        # Invalida cache se user clicou "Atualizar" — força refetch
        trig = dash.callback_context.triggered_id
        if trig == "btn-refresh-indicators-v2":
            cache_invalidate_all()
        # default filters quando ainda não houve apply (entrada inicial na página)
        from datetime import datetime as _dt
        year = year or DEFAULT_YEAR
        if ptype == "custom" and sdate and edate:
            # BR-12: end_date = primeiro instante do mês seguinte ao end
            try:
                e = _dt.fromisoformat(edate[:10])
                start = _dt.fromisoformat(sdate[:10])
                end = _dt(e.year + 1, 1, 1) if e.month == 12 else _dt(e.year, e.month + 1, 1)
            except Exception:
                start, end = _year_range(year)
        elif ptype == "last12":
            now = _dt.now()
            end = _dt(now.year, now.month, 1)
            start_year = end.year - 1 if end.month > 1 else end.year - 1
            start = _dt(start_year, end.month if end.month > 1 else 1, 1)
        else:
            start, end = _year_range(year)
        # Convenção pós-fix:
        #   - explicit (Apply clicado): respeita lista vazia como intenção
        #     ("zero selecionado"); equip/codes viram [] no store.
        #   - non-explicit (load url / refresh / lwb): se State estiver vazio
        #     (populate ainda não rodou), salva None no store → unpack trata como
        #     "toda planta / todos os códigos" sem depender de cache de names.
        explicit = (trig == "btn-apply-v2-filters")
        if explicit:
            equip_out = list(equip) if equip is not None else []
            codes_out = list(codes) if codes is not None else []
        else:
            equip_out = list(equip) if equip else None
            codes_out = list(codes) if codes else None
        return {
            "period_type":  ptype or "year",
            "year":         year,
            "start_iso":    start.isoformat(),
            "end_iso":      end.isoformat(),
            "equipment":    equip_out,
            "codes":        codes_out,
            "lwb_simulate": bool(lwb_sim),
        }

    def _heat_kpi_card(title: str, icon: str, ref_label: str, ref_val: str,
                       below_label: str, below_val: str,
                       above_label: str, above_val: str,
                       accent: str = "#0d6efd",
                       below_color: str = "#198754",
                       above_color: str = "#dc3545") -> dbc.Card:
        """Mini KPI card mostrando 'abaixo/acima' de uma referência (média/mediana).

        accent: cor do borderTop (alinha visual com o resto dos cards V2).
        """
        return dbc.Card(
            dbc.CardBody(
                [
                    html.Div(
                        [
                            html.I(
                                className=f"bi {icon} me-2",
                                style={"color": accent, "fontSize": "1rem"},
                            ),
                            html.Strong(title, style={"fontSize": "0.85rem"}),
                        ],
                        className="d-flex align-items-center mb-2",
                    ),
                    html.Div(
                        [
                            html.Span(ref_label + " ", className="small text-muted"),
                            html.Span(ref_val, className="small fw-semibold"),
                        ],
                        className="mb-2",
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                html.Div(
                                    [
                                        html.Div(below_label, className="text-muted",
                                                 style={"fontSize": "0.7rem"}),
                                        html.Div(below_val,
                                                 style={"fontSize": "1.35rem",
                                                        "fontWeight": "700",
                                                        "color": below_color,
                                                        "letterSpacing": "-0.5px"}),
                                    ],
                                    className="text-center",
                                ),
                                xs=6,
                            ),
                            dbc.Col(
                                html.Div(
                                    [
                                        html.Div(above_label, className="text-muted",
                                                 style={"fontSize": "0.7rem"}),
                                        html.Div(above_val,
                                                 style={"fontSize": "1.35rem",
                                                        "fontWeight": "700",
                                                        "color": above_color,
                                                        "letterSpacing": "-0.5px"}),
                                    ],
                                    className="text-center",
                                ),
                                xs=6,
                            ),
                        ],
                        className="g-2",
                    ),
                ],
                className="py-2 px-3",
            ),
            className="shadow-sm h-100 indicator-v2-card",
            style={"borderTop": f"4px solid {accent}"},
        )

    def _format_minutes(value: float) -> str:
        """'120min', '1.2k min', '12.5k min' — compacta valores grandes."""
        value = int(round(value))
        if value < 1000:
            return f"{value}min"
        if value < 1_000_000:
            return f"{value/1000:.1f}k min".replace(".0k", "k")
        return f"{value/1_000_000:.2f}M min"

    def _heatmap_legend(stats: dict) -> list:
        """Legenda em minutos (4 bins + cinza pra sem produção)."""
        if not stats or stats.get("median_min", 0) <= 0:
            return [
                html.Span("⬜ sem produção  ", className="me-2 small text-muted"),
                html.Span("🟢 sem paradas no período", className="me-2 small text-muted"),
            ]
        y_thr = int(round(stats["y_thr_min"]))
        x_thr = int(round(stats["x_thr_min"]))
        z_thr = int(round(stats["z_thr_min"]))
        return [
            html.Span("⬜ sem produção  ", className="me-2 small text-muted"),
            html.Span(f"🟢 ≤ {y_thr}min  ", className="me-2 small text-muted"),
            html.Span(f"🟡 {y_thr}–{x_thr}min  ", className="me-2 small text-muted"),
            html.Span(f"🟥 {x_thr}–{z_thr}min  ", className="me-2 small text-muted"),
            html.Span(f"🔴 > {z_thr}min  ", className="me-2 small text-muted"),
        ]

    def _heatmap_stats_str(stats: dict) -> str:
        """'Média 45min · Mediana 30min' (dias com produção e parada > 0).

        Em modo override (vs mediana da planta), adiciona '· vs planta Wmin'
        pra deixar claro qual referência colore o heatmap.
        """
        if not stats or stats.get("n_dias_falha", 0) == 0:
            return "Sem paradas no período"
        base = (
            f"Média {int(round(stats['mean_min']))}min · "
            f"Mediana {int(round(stats['median_min']))}min"
        )
        if stats.get("is_override"):
            ref = int(round(stats.get("median_min_cmp", 0)))
            base += f" · vs planta {ref}min"
        return base

    # 0. Heatmap de Falhas — Planta (1 grande) + grid 3-col por equipamento + 4 KPIs
    @app.callback(
        Output("v2-heatmap-planta", "figure"),
        Output("v2-heatmap-planta-stats", "children"),
        Output("v2-heatmap-planta-legend", "children"),
        Output("v2-heatmap-grid", "children"),
        Output("v2-heat-kpi-dist-mean", "children"),
        Output("v2-heat-kpi-dist-median", "children"),
        Output("v2-heat-kpi-sum-mean", "children"),
        Output("v2-heat-kpi-sum-median", "children"),
        Input("url", "pathname"),
        Input("store-v2-filters", "data"),
        Input("modal-v2-thresholds", "is_open"),
        Input("v2-heatmap-mini-mode", "value"),
    )
    def render_v2_heatmaps(pathname, filters, _modal_open, mini_mode):
        if pathname != "/maintenance/indicators-v2":
            return tuple([no_update] * 8)
        start, end, codes, equipment_filter, _year, _lwb = _unpack_filters(filters)
        from src.utils.breakdown_thresholds import get_heatmap_pcts
        import statistics as _stats
        y_pct, x_pct, z_pct = get_heatmap_pcts()
        mini_mode = mini_mode or "self"

        # ===== Heatmap PLANTA =====
        # equipment_filter já vem com internal IDs (vide populate_equipment_filter).
        planta_eq = list(equipment_filter) if equipment_filter is not None else None
        fig_planta, stats_planta = _build_heatmap(
            start, end, codes, equipment_ids=planta_eq,
            title="Planta", compact=False,
            y_pct=y_pct, x_pct=x_pct, z_pct=z_pct,
        )
        planta_median_for_override = (
            stats_planta.get("median_min", 0.0)
            if mini_mode == "planta" else None
        )

        # ===== 4 KPIs de distribuição/soma =====
        durations = _fetch_breakdown_durations_list(planta_eq, start, end, codes)
        total = len(durations)
        if total == 0:
            empty_msg = dbc.Card(
                dbc.CardBody(
                    [html.Strong("Sem paradas no período",
                                 className="small text-muted")],
                    className="py-3 text-center",
                ),
                className="shadow-sm h-100",
            )
            kpi_dist_mean = empty_msg
            kpi_dist_median = empty_msg
            kpi_sum_mean = empty_msg
            kpi_sum_median = empty_msg
        else:
            mean = _stats.mean(durations)
            median = _stats.median(durations)
            below_mean = [d for d in durations if d < mean]
            above_mean = [d for d in durations if d >= mean]
            below_median = [d for d in durations if d < median]
            above_median = [d for d in durations if d >= median]

            kpi_dist_mean = _heat_kpi_card(
                title="Distribuição vs Média",
                icon="bi-bar-chart-steps",
                ref_label="Média:",
                ref_val=_format_minutes(mean),
                below_label="Paradas abaixo",
                below_val=f"{len(below_mean)} ({len(below_mean)*100//total}%)",
                above_label="Paradas acima",
                above_val=f"{len(above_mean)} ({len(above_mean)*100//total}%)",
                accent="#0d6efd",
            )
            kpi_dist_median = _heat_kpi_card(
                title="Distribuição vs Mediana",
                icon="bi-bullseye",
                ref_label="Mediana:",
                ref_val=_format_minutes(median),
                below_label="Paradas abaixo",
                below_val=f"{len(below_median)} ({len(below_median)*100//total}%)",
                above_label="Paradas acima",
                above_val=f"{len(above_median)} ({len(above_median)*100//total}%)",
                accent="#6f42c1",
            )
            sum_total = sum(durations)
            sum_below_mean = sum(below_mean)
            sum_above_mean = sum(above_mean)
            sum_below_median = sum(below_median)
            sum_above_median = sum(above_median)
            kpi_sum_mean = _heat_kpi_card(
                title="Tempo total vs Média",
                icon="bi-hourglass-split",
                ref_label="Total:",
                ref_val=_format_minutes(sum_total),
                below_label="Min abaixo",
                below_val=(f"{_format_minutes(sum_below_mean)} "
                           f"({sum_below_mean*100//sum_total}%)") if sum_total else "0min",
                above_label="Min acima",
                above_val=(f"{_format_minutes(sum_above_mean)} "
                           f"({sum_above_mean*100//sum_total}%)") if sum_total else "0min",
                accent="#20c997",
            )
            kpi_sum_median = _heat_kpi_card(
                title="Tempo total vs Mediana",
                icon="bi-stopwatch",
                ref_label="Total:",
                ref_val=_format_minutes(sum_total),
                below_label="Min abaixo",
                below_val=(f"{_format_minutes(sum_below_median)} "
                           f"({sum_below_median*100//sum_total}%)") if sum_total else "0min",
                above_label="Min acima",
                above_val=(f"{_format_minutes(sum_above_median)} "
                           f"({sum_above_median*100//sum_total}%)") if sum_total else "0min",
                accent="#fd7e14",
            )

        # ===== Grid POR EQUIPAMENTO =====
        eq_list = _list_equipments_real()
        if equipment_filter is not None:
            _set = set(equipment_filter)
            eq_list = [
                e for e in eq_list
                if (e.get("internal") or e["id"]) in _set
            ]
        cards = []
        for eq in eq_list:
            internal = eq.get("internal") or eq["id"]
            fig_eq, stats_eq = _build_heatmap(
                start, end, codes, equipment_ids=[internal],
                title=eq["id"], compact=True,
                y_pct=y_pct, x_pct=x_pct, z_pct=z_pct,
                override_median_min=planta_median_for_override,
            )
            cards.append(
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                html.Div(
                                                    [
                                                        html.I(
                                                            className="bi bi-hdd-stack me-1",
                                                            style={"color": "#6c757d",
                                                                   "fontSize": "0.85rem"},
                                                        ),
                                                        html.Strong(eq["id"],
                                                                    style={"fontSize": "0.85rem"}),
                                                    ],
                                                    className="d-flex align-items-center",
                                                ),
                                                html.Small(eq.get("categoria", "—"),
                                                           className="text-muted",
                                                           style={"fontSize": "0.7rem"}),
                                            ]
                                        ),
                                        html.Div(
                                            _heatmap_stats_str(stats_eq),
                                            className="ms-auto small text-muted text-end",
                                            style={"fontSize": "0.72rem", "lineHeight": "1.2"},
                                        ),
                                    ],
                                    className="d-flex align-items-center",
                                ),
                                className="py-2",
                            ),
                            dbc.CardBody(
                                [
                                    dcc.Graph(
                                        figure=fig_eq,
                                        config={"displayModeBar": False,
                                                "staticPlot": False,
                                                "responsive": True},
                                        style={"height": "200px"},
                                    ),
                                    html.Div(
                                        _heatmap_legend(stats_eq),
                                        className="mt-1",
                                    ),
                                ],
                                className="p-2",
                            ),
                        ],
                        className="shadow-sm h-100 indicator-v2-card",
                        style={"borderTop": "3px solid #e9ecef"},
                    ),
                    xs=12, sm=6, md=4, lg=4, xl=4,
                    className="mb-3",
                )
            )
        grid = dbc.Row(cards, className="g-3") if cards else html.Div()
        return (
            fig_planta,
            _heatmap_stats_str(stats_planta),
            _heatmap_legend(stats_planta),
            grid,
            kpi_dist_mean,
            kpi_dist_median,
            kpi_sum_mean,
            kpi_sum_median,
        )

    # 1. Renderiza cards KPI + deltas + sparklines + pulse + ring + animated value
    @app.callback(
        Output("kpi-graph-breakdown", "figure"),
        Output("kpi-graph-mtbf", "figure"),
        Output("kpi-graph-mttr", "figure"),
        Output("trend-delta-breakdown", "children"),
        Output("trend-delta-mtbf", "children"),
        Output("trend-delta-mttr", "children"),
        Output("sparkline-breakdown", "children"),
        Output("sparkline-mtbf", "children"),
        Output("sparkline-mttr", "children"),
        Output("kpi-card-breakdown", "className"),
        Output("kpi-card-mtbf", "className"),
        Output("kpi-card-mttr", "className"),
        Output("value-anim-breakdown", "data-v2-anim"),
        Output("value-anim-mtbf", "data-v2-anim"),
        Output("value-anim-mttr", "data-v2-anim"),
        Output("value-anim-breakdown", "data-v2-unit"),
        Output("value-anim-mtbf", "data-v2-unit"),
        Output("value-anim-mttr", "data-v2-unit"),
        Output("ring-breakdown", "children"),
        Output("ring-mtbf", "children"),
        Output("ring-mttr", "children"),
        Input("url", "pathname"),
        Input("store-v2-filters", "data"),
        Input("store-v2-lang", "data"),
    )
    def render_planta_cards(pathname, filters, lang):
        if pathname != "/maintenance/indicators-v2":
            return tuple([no_update] * 21)
        start, end, codes, equipment_filter, year, lwb_sim = _unpack_filters(filters)
        lang = lang or "pt"
        td_lang = _TRANS.get(lang, _TRANS["pt"])
        title_planta = td_lang.get("tl_planta_mensal", "Planta — mensal")

        def _planta_fig(kpi, labels, values, target, statuses=None):
            fig = _bar_rich(labels, values, title_planta,
                            KPI_META[kpi]["color"], KPI_META[kpi]["unit"],
                            target=target, direction=KPI_META[kpi]["direction"],
                            td=td_lang, bar_statuses=statuses)
            fig.update_layout(height=280)  # reduzido pra acomodar valor+ring na linha topo
            return fig

        def _last_value(values):
            non_zero = [v for v in values if v not in (0, None)]
            return non_zero[-1] if non_zero else 0

        def _ring_progress(kpi, value, target):
            """Mini donut Plotly (60×60) mostrando % achievement da meta."""
            import plotly.graph_objects as go
            from dash import dcc as _dcc
            direction = KPI_META[kpi]["direction"]
            color = KPI_META[kpi]["color"]
            if not target or value is None:
                achievement = 0
            elif direction == "lower":
                achievement = min(1.0, target / value) if value > 0 else 1.0
            else:
                achievement = min(1.0, value / target) if target > 0 else 0
            pct = int(round(achievement * 100))
            # Cor do ring: verde se >= 95%, amarelo 70-95%, vermelho < 70%
            ring_color = "#198754" if achievement >= 0.95 else ("#ffc107" if achievement >= 0.7 else "#dc3545")
            fig = go.Figure(go.Pie(
                values=[achievement, max(0, 1 - achievement)],
                marker=dict(colors=[ring_color, "rgba(0,0,0,0.06)"], line=dict(width=0)),
                hole=0.72,
                textinfo="none",
                hoverinfo="skip",
                sort=False,
                direction="clockwise",
                rotation=0,
            ))
            fig.add_annotation(
                text=f"<b>{pct}%</b>",
                showarrow=False,
                font=dict(size=12, color=ring_color, family="Arial Black"),
                x=0.5, y=0.5,
            )
            fig.update_layout(
                margin=dict(l=0, r=0, t=0, b=0),
                showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=60, width=60,
            )
            return _dcc.Graph(
                figure=fig,
                config={"displayModeBar": False, "staticPlot": True, "responsive": False},
                style={"height": "60px", "width": "60px"},
            )

        def _hex_to_rgba(hex_color: str, alpha: float = 0.15) -> str:
            """Converte hex (#dc3545) → rgba(220,53,69,0.15). Robusto a hex 3/6 chars."""
            h = hex_color.lstrip("#")
            if len(h) == 3:
                h = "".join(c * 2 for c in h)
            try:
                r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
                return f"rgba({r},{g},{b},{alpha})"
            except Exception:
                return f"rgba(108,117,125,{alpha})"

        def _sparkline(kpi, values, color):
            """Mini line chart 90×28 — trunca zeros futuros (evita 'tendência de queda' falsa)."""
            # Trunca trailing zeros/None — só mostra dados reais (meses já fechados)
            cut = len(values)
            while cut > 0 and values[cut - 1] in (0, None):
                cut -= 1
            truncated = values[:cut]
            non_zero = [v for v in truncated if v not in (0, None)]
            if len(non_zero) < 2:
                return None
            import plotly.graph_objects as go
            fill = _hex_to_rgba(color, 0.18)
            fig = go.Figure(go.Scatter(
                x=list(range(len(truncated))),
                y=truncated,
                mode="lines",
                line=dict(color=color, width=2, shape="spline"),
                fill="tozeroy",
                fillcolor=fill,
                hoverinfo="skip",
            ))
            fig.update_layout(
                margin=dict(l=0, r=0, t=0, b=0),
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                height=28, width=90,
                showlegend=False,
            )
            from dash import dcc as _dcc
            return _dcc.Graph(figure=fig, config={"displayModeBar": False, "staticPlot": True},
                              style={"height": "28px", "width": "90px"})

        def _pulse_class(kpi, values, target):
            """Adiciona .v2-pulse-warning se último valor excede meta (ruim)."""
            non_zero = [v for v in values if v not in (0, None)]
            if not non_zero or target is None:
                return ""
            last = non_zero[-1]
            direction = KPI_META[kpi]["direction"]
            excedeu = (last > target) if direction == "lower" else (last < target)
            return " v2-pulse-warning" if excedeu else ""

        def _trend_delta(kpi, values):
            non_zero = [(i, v) for i, v in enumerate(values) if v not in (0, None)]
            if len(non_zero) < 2:
                return html.Span()
            last_v = non_zero[-1][1]
            prev_v = non_zero[-2][1]
            if prev_v == 0:
                return html.Span()
            delta_pct = ((last_v - prev_v) / prev_v) * 100
            direction = KPI_META[kpi]["direction"]
            improving = (delta_pct < 0) if direction == "lower" else (delta_pct > 0)
            if abs(delta_pct) < 1:
                cls_mod = "delta-neutral"
            else:
                cls_mod = "delta-good" if improving else "delta-bad"
            arrow = "↓" if delta_pct < 0 else ("↑" if delta_pct > 0 else "→")
            return html.Span(
                f"{arrow} {abs(delta_pct):.1f}%",
                className=f"kpi-trend-delta {cls_mod}",
                title=f"Último: {last_v}{KPI_META[kpi]['unit']} vs anterior: {prev_v}{KPI_META[kpi]['unit']}",
            )

        labels_br, v_br, st_br = _fetch_planta_monthly("breakdown", start, end, codes, equipment_filter, lwb_simulate=lwb_sim)
        labels_mt, v_mt, st_mt = _fetch_planta_monthly("mtbf", start, end, codes, equipment_filter, lwb_simulate=lwb_sim)
        labels_mtr, v_mtr, st_mtr = _fetch_planta_monthly("mttr", start, end, codes, equipment_filter, lwb_simulate=lwb_sim)
        t_br = _resolve_target("breakdown")
        t_mt = _resolve_target("mtbf")
        t_mtr = _resolve_target("mttr")

        base_class = "shadow-sm h-100 indicator-v2-card"  # mesmo que _kpi_card aplica
        # Mas precisamos voltar a className do html.Div pai (kpi-card-{kpi}):
        wrapper_class = ""  # html.Div wrapper só tem cursor+height inline

        # Card value = AGREGADO DO PERÍODO (totais brutos, BR-11 paridade V1)
        # Não é último mês — é planta inteira agregada (sum active_h, sum brk_h,
        # sum failures → recalcula KPI). Igual cards V1.
        agg = _period_agg(start, end, codes, equipment_filter, lwb_simulate=lwb_sim)
        last_br  = _to_display("breakdown", agg.get("breakdown_rate", 0))
        last_mt  = _to_display("mtbf",      agg.get("mtbf", 0))
        last_mtr = _to_display("mttr",      agg.get("mttr", 0))

        return (
            _planta_fig("breakdown", labels_br, v_br, t_br, statuses=st_br),
            _planta_fig("mtbf", labels_mt, v_mt, t_mt, statuses=st_mt),
            _planta_fig("mttr", labels_mtr, v_mtr, t_mtr, statuses=st_mtr),
            _trend_delta("breakdown", v_br),
            _trend_delta("mtbf", v_mt),
            _trend_delta("mttr", v_mtr),
            _sparkline("breakdown", v_br, KPI_META["breakdown"]["color"]),
            _sparkline("mtbf", v_mt, KPI_META["mtbf"]["color"]),
            _sparkline("mttr", v_mtr, KPI_META["mttr"]["color"]),
            wrapper_class + _pulse_class("breakdown", v_br, t_br),
            wrapper_class + _pulse_class("mtbf", v_mt, t_mt),
            wrapper_class + _pulse_class("mttr", v_mtr, t_mtr),
            # data-v2-anim (valores target pro counter JS animar)
            str(last_br),
            str(last_mt),
            str(last_mtr),
            # data-v2-unit (suffix) — JS lê e formata textContent
            KPI_META["breakdown"]["unit"],
            KPI_META["mtbf"]["unit"],
            KPI_META["mttr"]["unit"],
            # Ring progress (donuts)
            _ring_progress("breakdown", last_br, t_br),
            _ring_progress("mtbf", last_mt, t_mt),
            _ring_progress("mttr", last_mtr, t_mtr),
        )

    # IM-12 — Excel export
    @app.callback(
        Output("download-v2-xlsx", "data"),
        Input("btn-export-v2-xlsx", "n_clicks"),
        State("store-v2-filters", "data"),
        prevent_initial_call=True,
    )
    def export_v2_xlsx(n_clicks, filters):
        from datetime import datetime as _dt
        import io
        import pandas as pd
        start, end, codes, equipment_filter, year, lwb_sim = _unpack_filters(filters)
        # Tabela: equipamento × mês × {mtbf, mttr, breakdown_rate}
        rows = []
        try:
            eq_list = _list_equipments_real()
            if equipment_filter is not None:
                _set = set(equipment_filter)
                eq_list = [
                    e for e in eq_list
                    if (e.get("internal") or e["id"]) in _set
                ]
            for eq in eq_list:
                eq_id = eq["id"]
                cat = eq.get("categoria", "—")
                for kpi in ("mtbf", "mttr", "breakdown"):
                    labels, monthly, _ = _fetch_equipment_monthly(kpi, eq_id, start, end, codes, lwb_simulate=lwb_sim)
                    for label, v in zip(labels, monthly):
                        rows.append({
                            "Equipamento": eq_id,
                            "Categoria":   cat,
                            "Período":     label,
                            "KPI":         {"mtbf": "MTBF (h)", "mttr": "MTTR (min)", "breakdown": "Taxa Avaria (%)"}[kpi],
                            "Valor":       v,  # já em unit de display via _to_display nos fetchers
                            "Meta":        _resolve_target(kpi, eq.get("internal", eq_id)),
                        })
        except Exception as e:
            logger.warning("V2 export falhou (%s)", e)
        df = pd.DataFrame(rows)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Indicadores V2", index=False)
        buf.seek(0)
        range_tag = f"{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}"
        filename = f"indicators_v2_{range_tag}_{_dt.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        from dash import dcc as _dcc
        return _dcc.send_bytes(buf.read(), filename)

    # 2. Controle do modal — entrada (click card), drilldown (pattern), back, close
    # Limpa modal-v2-content/title imediatamente pra evitar flash de conteúdo velho
    # enquanto render_modal_content recalcula.
    @app.callback(
        Output("modal-v2", "is_open"),
        Output("store-v2-level", "data"),
        Output("store-v2-kpi", "data"),
        Output("store-v2-equipment", "data"),
        Output("store-v2-month", "data"),
        Output("store-v2-year", "data"),
        Output("store-v2-day", "data"),
        Output("modal-v2-content", "children", allow_duplicate=True),
        Output("modal-v2-title", "children", allow_duplicate=True),
        Output("modal-v2-breadcrumb", "children", allow_duplicate=True),
        Input("kpi-card-breakdown", "n_clicks"),
        Input("kpi-card-mtbf", "n_clicks"),
        Input("kpi-card-mttr", "n_clicks"),
        Input({"type": "v2-eq", "kpi": ALL, "equipment": ALL}, "n_clicks"),
        Input({"type": "v2-month", "kpi": ALL, "equipment": ALL, "month": ALL, "year": ALL}, "n_clicks"),
        Input({"type": "v2-day", "kpi": ALL, "equipment": ALL, "month": ALL, "year": ALL, "day": ALL}, "n_clicks"),
        Input({"type": "v2-bar-month", "kpi": ALL, "equipment": ALL}, "clickData"),
        Input({"type": "v2-bar-day", "kpi": ALL, "equipment": ALL, "month": ALL, "year": ALL}, "clickData"),
        Input("btn-v2-back", "n_clicks"),
        Input("btn-v2-close", "n_clicks"),
        State("store-v2-level", "data"),
        State("store-v2-kpi", "data"),
        State("store-v2-equipment", "data"),
        State("store-v2-month", "data"),
        State("store-v2-year", "data"),
        State("store-v2-filters", "data"),
        prevent_initial_call=True,
    )
    def control_modal(c_br, c_mtbf, c_mttr, eq_clicks, mo_clicks, dy_clicks,
                      bar_month_clicks, bar_day_clicks,
                      back, close, level, kpi, equipment, month, year, filters):
        trig = dash.callback_context.triggered_id

        # CLEAR = limpa content/title/breadcrumb. render_modal_content preenche depois.
        CLEAR = (None, "", None)
        NOOP = (no_update,) * 3
        # Output arity = 7 stores + 3 content (CLEAR) = 10. (no_update,)*7 + CLEAR
        NOOP10 = (no_update,) * 7 + NOOP

        if trig == "btn-v2-close":
            return (False, "planta", None, None, None, None, None) + CLEAR

        if trig == "btn-v2-back":
            if level == "tabela":
                return (True, "dias", kpi, equipment, month, year, None) + CLEAR
            if level == "dias":
                return (True, "meses", kpi, equipment, None, None, None) + CLEAR
            if level == "mes-top":
                return (True, "meses", kpi, equipment, None, None, None) + CLEAR
            if level == "meses":
                return (True, "equipamentos", kpi, None, None, None, None) + CLEAR
            if level == "equipamentos":
                return (False, "planta", None, None, None, None, None) + CLEAR
            return NOOP10

        # Click num card KPI (qualquer região do card) — trig é string id
        if isinstance(trig, str):
            kpi_map = {
                "kpi-card-breakdown": "breakdown",
                "kpi-card-mtbf": "mtbf",
                "kpi-card-mttr": "mttr",
            }
            if trig in kpi_map:
                return (True, "equipamentos", kpi_map[trig], None, None, None, None) + CLEAR

        # Pattern clicks — trig é AttributeDict (dict-like)
        if not isinstance(trig, str) and trig is not None:
            t = trig.get("type")
            if t == "v2-eq":
                return (True, "meses", trig["kpi"], trig["equipment"], None, None, None) + CLEAR
            if t == "v2-month":
                # Click no CARD do mês → top paradas mensais (barras horizontais + tabela)
                return (True, "mes-top", trig["kpi"], trig["equipment"],
                        trig["month"], trig["year"], None) + CLEAR
            if t == "v2-day":
                return (True, "tabela", trig["kpi"], trig["equipment"],
                        trig["month"], trig["year"], trig["day"]) + CLEAR

            # Click numa barra do gráfico grande
            if t in ("v2-bar-month", "v2-bar-day"):
                ctx_trig = dash.callback_context.triggered
                if not ctx_trig or ctx_trig[0].get("value") is None:
                    return NOOP10
                click = ctx_trig[0]["value"]
                x_val = click["points"][0]["x"]
                if t == "v2-bar-month":
                    # Label "Nov/25" → resolve (year, month) via _iter_months_in_range
                    f_start, f_end, _, _, _, _ = _unpack_filters(filters)
                    bm_year, bm_month = None, None
                    for lbl, _, _, yy, mm in _iter_months_in_range(f_start, f_end):
                        if lbl == x_val:
                            bm_year, bm_month = yy, mm
                            break
                    if bm_month is None:
                        return NOOP10
                    return (True, "dias", trig["kpi"], trig["equipment"],
                            bm_month, bm_year, None) + CLEAR
                if t == "v2-bar-day":
                    return (True, "tabela", trig["kpi"], trig["equipment"],
                            trig["month"], trig["year"], int(x_val)) + CLEAR

        return NOOP10

    # 3. Render conteúdo do modal por level (com i18n)
    # allow_duplicate porque control_modal também escreve nesses outputs (clear)
    @app.callback(
        Output("modal-v2-content", "children", allow_duplicate=True),
        Output("modal-v2-title", "children", allow_duplicate=True),
        Output("modal-v2-breadcrumb", "children", allow_duplicate=True),
        Output("btn-v2-back", "style"),
        Input("store-v2-level", "data"),
        Input("store-v2-kpi", "data"),
        Input("store-v2-equipment", "data"),
        Input("store-v2-month", "data"),
        Input("store-v2-year", "data"),
        Input("store-v2-day", "data"),
        Input("store-v2-lang", "data"),
        Input("store-v2-hide-tooling", "data"),
        State("store-v2-filters", "data"),
        prevent_initial_call=True,
    )
    def render_modal(level, kpi, equipment, month, drill_year, day, lang,
                     hide_tooling, filters):
        if not kpi:
            return None, "", None, {"display": "none"}

        lang = lang or "pt"
        td = _TRANS.get(lang, _TRANS["pt"])  # tradução por key
        meses_curtos = td.get("month_short", MESES_PT)
        # Filtros do store (paridade V1): range + codes + equipment_filter
        f_start, f_end, f_codes, f_eq_filter, f_year, f_lwb_sim = _unpack_filters(filters)
        # Year do mês clicado no drilldown (cross-year ok). Fallback = f_year.
        d_year = drill_year if drill_year else f_year
        # Label KPI traduzido
        KPI_LABEL_I18N = {
            "breakdown": td.get("mdl_kpi_avaria", "Taxa de Avaria"),
            "mtbf": td.get("mdl_kpi_mtbf", "MTBF"),
            "mttr": td.get("mdl_kpi_mttr", "MTTR"),
        }
        kpi_label = KPI_LABEL_I18N.get(kpi, kpi)

        meta = KPI_META[kpi]
        breadcrumb_items = [html.Span(kpi_label, className="text-primary fw-semibold")]

        # NÍVEL 1: equipamentos (grid de mini-gráficos) — IM-02
        if level == "equipamentos":
            cards = []
            eq_list = _list_equipments_real()
            if f_eq_filter is not None:
                _set = set(f_eq_filter)
                eq_list = [
                    e for e in eq_list
                    if (e.get("internal") or e["id"]) in _set
                ]
            for eq in eq_list:
                labels_eq, values, statuses_eq = _fetch_equipment_monthly(
                    kpi, eq["id"], f_start, f_end, f_codes, lwb_simulate=f_lwb_sim
                )
                eq_target = _resolve_target(kpi, eq.get("internal", eq["id"]))
                # Compact + figure cacheada por (kpi, eq, values, target, statuses)
                fig = _cached_compact_bar(kpi, eq["id"], f_year, values,
                                          eq_target, meta["color"], meta["unit"],
                                          labels=labels_eq, statuses=statuses_eq)
                card = dbc.Col(
                    html.Div(
                        dbc.Card(
                            [
                                dbc.CardHeader(
                                    html.Div(
                                        [
                                            html.Strong(eq["id"], style={"fontSize": "0.9rem"}),
                                            html.Br(),
                                            html.Small(eq["categoria"], className="text-muted"),
                                        ]
                                    )
                                ),
                                dbc.CardBody(
                                    dcc.Graph(
                                        figure=fig,
                                        config={"displayModeBar": False, "staticPlot": True, "responsive": True},
                                        style={"height": "220px"},  # bate com layout.height=220 (sem reflow)
                                    )
                                ),
                            ],
                            className="shadow-sm h-100",
                        ),
                        id={"type": "v2-eq", "kpi": kpi, "equipment": eq["id"]},
                        n_clicks=0,
                        style={"cursor": "pointer", "height": "100%"},
                    ),
                    xs=12, sm=6, md=4, xl=3,
                    className="mb-3",
                )
                cards.append(card)

            content = dbc.Row(cards, className="g-3")
            title = f"{kpi_label} — {td.get('mdl_equipamentos','Equipamentos')} ({len(eq_list)})"
            return content, title, breadcrumb_items, {}

        # NÍVEL 2: meses (gráfico grande + grid de mini-meses clicáveis) — IM-03
        if level == "meses" and equipment:
            labels_m, values, statuses_m = _fetch_equipment_monthly(
                kpi, equipment, f_start, f_end, f_codes, lwb_simulate=f_lwb_sim
            )
            # months_meta_full alinhado a labels_m/values/statuses_m (12 itens),
            # carrega (year, month) reais pra montar IDs dos mini-cards e
            # decidir clicabilidade por status.
            months_meta_full = list(_chart_months_with_status(f_start, f_end))
            eq_target = _resolve_target(kpi, equipment)
            main_fig = _bar(labels_m, values, f"{equipment} — {td.get('mdl_meses','12 meses')}",
                            meta["color"], meta["unit"],
                            target=eq_target, show_trend=True, td=td,
                            bar_statuses=statuses_m)
            main_fig.update_layout(height=380)

            # mini-cards por mês (clicáveis) abaixo do gráfico grande.
            # Meses "out" do filtro ficam visualmente apagados e não-clicáveis.
            mini_rows = []
            for label, val, (_, _, _, yy, mm, status) in zip(labels_m, values, months_meta_full):
                clickable = status in ("in", "partial")
                if status == "out":
                    card_style = {"opacity": 0.45}
                    val_color = "#adb5bd"
                    cursor = "default"
                elif status == "partial":
                    card_style = {"borderLeft": f"3px solid {_PARTIAL_COLOR}"}
                    val_color = _PARTIAL_COLOR
                    cursor = "pointer"
                else:
                    card_style = {}
                    val_color = meta["color"]
                    cursor = "pointer"
                card_div = html.Div(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.Div(label, className="text-muted small mb-1"),
                                html.Div(
                                    f"{val}{meta['unit']}",
                                    style={"fontSize": "1.2rem", "fontWeight": "bold",
                                           "color": val_color},
                                ),
                            ],
                            className="text-center py-2",
                        ),
                        className="shadow-sm",
                        style=card_style,
                    ),
                    n_clicks=0,
                    style={"cursor": cursor},
                )
                if clickable:
                    card_div.id = {"type": "v2-month", "kpi": kpi,
                                   "equipment": equipment, "month": mm, "year": yy}
                mini_rows.append(
                    dbc.Col(card_div, xs=6, sm=4, md=3, lg=2, className="mb-2")
                )

            content = html.Div(
                [
                    dcc.Graph(
                        id={"type": "v2-bar-month", "kpi": kpi, "equipment": equipment},
                        figure=main_fig,
                        config={"displayModeBar": False, "responsive": True},
                        style={"height": "380px", "cursor": "pointer"},
                    ),
                    html.Hr(),
                    html.H6(td.get("mdl_click_barra_mes","Clique numa barra ou num card pra ver os dias:"), className="v2-section-h6 text-muted"),
                    dbc.Row(mini_rows, className="g-2"),
                ]
            )
            breadcrumb_items += [
                html.Span(" › ", className="mx-1 text-muted"),
                html.Span(equipment, className="text-primary fw-semibold"),
            ]
            title = f"{kpi_label} — {equipment}"
            return content, title, breadcrumb_items, {}

        # NÍVEL 3: mes-top — IM-06
        if level == "mes-top" and equipment and month:
            items = _fetch_top_paradas_real(
                equipment, month, year=d_year, top_n=10, codes=f_codes
            )
            if hide_tooling:
                items = [it for it in items if it.get("codigo") not in ("202", "S202")]
            t1, t2 = get_thresholds_pair(equipment)
            h_bar = _top_paradas_h_bar(
                items, equipment, month, td=td,
                threshold_1=t1, threshold_2=t2,
            )

            if not items:
                table = _empty_state(
                    icon="bi-check2-circle",
                    title=td.get("mdl_no_paradas_mes","Mês limpo!"),
                    desc=td.get("mdl_no_paradas_mes_desc","Nenhuma parada registrada nesse período."),
                )
            else:
                # i18n column keys (mantém PT internamente como id, traduz só labels exibidas)
                col_num   = td.get("tbl_num", "#")
                col_data  = td.get("tbl_data", "Data")
                col_causa = td.get("tbl_causa", "Causa")
                col_dur   = td.get("tbl_duracao", "Duração (min)")
                col_evt   = td.get("tbl_eventos", "Eventos")
                col_cod   = td.get("tbl_codigo", "Código")
                table_rows = [
                    {
                        col_num:   i + 1,
                        col_data:  it["date"],
                        col_causa: it["descricao"],
                        col_dur:   it["duracao_min"],
                        col_evt:   it["count"],
                        col_cod:   it["codigo"],
                    }
                    for i, it in enumerate(items)
                ]
                table = dash_table.DataTable(
                    data=table_rows,
                    columns=[{"name": k, "id": k} for k in table_rows[0].keys()],
                    style_table={"overflowX": "auto"},
                    style_cell={"padding": "8px", "fontFamily": "system-ui", "fontSize": "13px"},
                    style_header={
                        "backgroundColor": "#f1f3f5",
                        "fontWeight": "600",
                        "borderBottom": "2px solid #dee2e6",
                    },
                    style_data_conditional=[
                        {"if": {"filter_query": f"{{{col_dur}}} >= {t1}"},
                         "backgroundColor": "#fff3cd"},
                        {"if": {"filter_query": f"{{{col_dur}}} >= {t2}"},
                         "backgroundColor": "#f8d7da"},
                    ],
                    sort_action="native",
                    page_size=10,
                )

            content = html.Div([
                dcc.Graph(
                    figure=h_bar,
                    config={"displayModeBar": False, "staticPlot": True, "responsive": True},
                    style={"height": "380px"},  # bate com layout.height=380 (sem reflow)
                ),
                html.Hr(),
                html.H6(td.get("mdl_top_10_paradas","Top 10 paradas — detalhe:"), className="v2-section-h6 text-muted"),
                table,
            ])
            breadcrumb_items += [
                html.Span(" › ", className="mx-1 text-muted"),
                html.Span(equipment, className="text-primary fw-semibold"),
                html.Span(" › ", className="mx-1 text-muted"),
                html.Span(meses_curtos[month - 1], className="text-primary fw-semibold"),
                html.Span(" › ", className="mx-1 text-muted"),
                html.Span(td.get("mdl_top_paradas","Top paradas"), className="text-primary fw-semibold"),
            ]
            title = f"{kpi_label} — {td.get('mdl_top_paradas','Top paradas')} — {equipment} — {meses_curtos[month-1]}/{d_year}"
            return content, title, breadcrumb_items, {}

        # NÍVEL 4: dias — IM-04
        if level == "dias" and equipment and month:
            dias, valores = _fetch_daily_kpi(
                kpi, equipment, month, year=d_year, codes=f_codes
            )
            eq_target = _resolve_target(kpi, equipment)
            main_fig = _bar(
                [f"{d:02d}" for d in dias],
                valores,
                f"{equipment} — {meses_curtos[month-1]}/{d_year}",
                meta["color"],
                meta["unit"],
                target=eq_target,
                show_trend=True,
                td=td,
            )
            main_fig.update_layout(height=380)

            mini_cards = []
            for d, v in zip(dias, valores):
                mini_cards.append(
                    dbc.Col(
                        html.Div(
                            dbc.Card(
                                dbc.CardBody(
                                    [
                                        html.Div(f"{d:02d}", className="text-muted small mb-1"),
                                        html.Div(
                                            f"{v}{meta['unit']}",
                                            style={"fontSize": "0.95rem", "fontWeight": "bold",
                                                   "color": meta["color"]},
                                        ),
                                    ],
                                    className="text-center py-1",
                                ),
                                className="shadow-sm",
                            ),
                            id={"type": "v2-day", "kpi": kpi, "equipment": equipment,
                                "month": month, "year": d_year, "day": d},
                            n_clicks=0,
                            style={"cursor": "pointer"},
                        ),
                        xs=3, sm=2, md=1,
                        className="mb-2",
                    )
                )

            content = html.Div(
                [
                    dcc.Graph(
                        id={"type": "v2-bar-day", "kpi": kpi, "equipment": equipment,
                            "month": month, "year": d_year},
                        figure=main_fig,
                        config={"displayModeBar": False, "responsive": True},
                        style={"height": "380px", "cursor": "pointer"},
                    ),
                    html.Hr(),
                    html.H6(td.get("mdl_click_barra_dia","Clique numa barra ou num card pra ver as paradas:"), className="v2-section-h6 text-muted"),
                    dbc.Row(mini_cards, className="g-1"),
                ]
            )
            breadcrumb_items += [
                html.Span(" › ", className="mx-1 text-muted"),
                html.Span(equipment, className="text-primary fw-semibold"),
                html.Span(" › ", className="mx-1 text-muted"),
                html.Span(meses_curtos[month - 1], className="text-primary fw-semibold"),
            ]
            title = f"{kpi_label} — {equipment} — {meses_curtos[month-1]}/{d_year}"
            return content, title, breadcrumb_items, {}

        # NÍVEL 5: tabela (paradas do dia)
        # Filtra por f_codes — paridade V1; revoga IM-05 ("mostra TODOS") do SDD indicators-v2.
        if level == "tabela" and equipment and month and day:
            eventos = _fetch_events_day_real(
                equipment, month, day, year=d_year, codes=f_codes
            )
            if hide_tooling:
                eventos = [e for e in eventos if e.get("Código") not in ("202", "S202")]
            t1_day, t2_day = get_thresholds_pair(equipment)

            # H-bar das paradas do dia (top 5 por duração) — mesma UX do nível mes-top.
            day_label = f"{day:02d}/{month:02d}/{d_year}"
            h_bar_items = sorted(
                [
                    {
                        "date":        day_label,
                        "descricao":   e.get("Causa", "—"),
                        "duracao_min": int(e.get("Duração (min)", 0) or 0),
                        "count":       1,
                        "codigo":      e.get("Código", "—"),
                    }
                    for e in eventos
                ],
                key=lambda x: x["duracao_min"],
                reverse=True,
            )
            day_h_bar = _top_paradas_h_bar(
                h_bar_items, equipment, month, td=td,
                threshold_1=t1_day, threshold_2=t2_day,
            )

            if not eventos:
                body = _empty_state(
                    icon="bi-emoji-sunglasses",
                    title=td.get("mdl_no_paradas_dia","Dia perfeito!"),
                    desc=td.get("mdl_no_paradas_dia_desc","Nenhuma parada registrada nesse dia."),
                )
            else:
                # i18n remap das chaves dos eventos (vêm em PT do _fetch_events_day_real)
                col_hora  = td.get("tbl_hora", "Hora")
                col_eq    = td.get("tbl_equipamento", "Equipamento")
                col_causa = td.get("tbl_causa", "Causa")
                col_dur   = td.get("tbl_duracao", "Duração (min)")
                col_cod   = td.get("tbl_codigo", "Código")
                eventos_i18n = [
                    {
                        col_hora:  e.get("Hora", "—"),
                        col_eq:    e.get("Equipamento", "—"),
                        col_causa: e.get("Causa", "—"),
                        col_dur:   e.get("Duração (min)", 0),
                        col_cod:   e.get("Código", "—"),
                    }
                    for e in eventos
                ]
                body = dash_table.DataTable(
                    data=eventos_i18n,
                    columns=[{"name": k, "id": k} for k in eventos_i18n[0].keys()],
                    style_table={"overflowX": "auto"},
                    style_cell={
                        "padding": "10px",
                        "fontFamily": "system-ui",
                        "fontSize": "14px",
                    },
                    style_header={
                        "backgroundColor": "#f1f3f5",
                        "fontWeight": "600",
                        "borderBottom": "2px solid #dee2e6",
                    },
                    style_data_conditional=[
                        {"if": {"filter_query": f"{{{col_dur}}} >= {t1_day}"},
                         "backgroundColor": "#fff3cd"},
                        {"if": {"filter_query": f"{{{col_dur}}} >= {t2_day}"},
                         "backgroundColor": "#f8d7da"},
                    ],
                    page_size=20,
                    sort_action="native",
                )

            content_children = [
                dbc.Alert(
                    [
                        html.I(className="bi bi-info-circle me-2"),
                        f"{td.get('mdl_paradas_em','Paradas em')} {equipment} — {day:02d}/{month:02d}/{d_year} — "
                        f"{len(eventos)} {td.get('mdl_eventos','eventos')}.",
                    ],
                    color="info",
                    className="mb-3",
                ),
            ]
            # H-bar só faz sentido quando há eventos.
            if eventos:
                content_children += [
                    dcc.Graph(
                        figure=day_h_bar,
                        config={"displayModeBar": False, "staticPlot": True, "responsive": True},
                        style={"height": "380px"},
                    ),
                    html.Hr(),
                    html.H6(
                        td.get("mdl_top_10_paradas", "Top 10 paradas — detalhe:"),
                        className="v2-section-h6 text-muted",
                    ),
                ]
            content_children.append(body)
            content = html.Div(content_children)
            breadcrumb_items += [
                html.Span(" › ", className="mx-1 text-muted"),
                html.Span(equipment, className="text-primary fw-semibold"),
                html.Span(" › ", className="mx-1 text-muted"),
                html.Span(meses_curtos[month - 1], className="text-primary fw-semibold"),
                html.Span(" › ", className="mx-1 text-muted"),
                html.Span(f"Dia {day:02d}", className="text-primary fw-semibold"),
            ]
            title = f"{td.get('mdl_paradas_em','Paradas em')} — {equipment} — {day:02d}/{month:02d}/{d_year}"
            return content, title, breadcrumb_items, {}

        return None, "", None, {"display": "none"}
