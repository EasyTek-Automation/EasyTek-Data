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


def _cached_compact_bar(kpi: str, eq_id: str, year: int, values: list, target: float, color: str, unit: str):
    """Bar compact cacheado por valores (mini-cards equipment grid)."""
    key = (kpi, eq_id, year, tuple(values), target)
    hit = _cache_get(_CACHE_FIG, key)
    if hit is not None:
        return hit
    fig = _bar(MESES_PT, values, eq_id, color, unit,
               target=target, show_trend=False, compact=True)
    fig.update_layout(margin=dict(l=30, r=10, t=40, b=30), height=220)
    _cache_set(_CACHE_FIG, key, fig)
    return fig


def _cached_fetch_kpi(year: int, codes: tuple) -> dict:
    """fetch_zpp_kpi_data com cache (year, codes)."""
    key = (year, codes)
    hit = _cache_get(_CACHE_KPI, key)
    if hit is not None:
        return hit
    start, end = _year_range(year)
    data = fetch_zpp_kpi_data(start, end, list(codes))
    _cache_set(_CACHE_KPI, key, data)
    return data


def _cached_agg(kpi_data: dict, year: int, codes: tuple) -> dict:
    """calculate_general_avg_by_month com cache."""
    key = (year, codes)
    hit = _cache_get(_CACHE_AGG, key)
    if hit is not None:
        return hit
    start, end = _year_range(year)
    all_eq = list(kpi_data.keys())
    agg = calculate_general_avg_by_month(
        data=kpi_data, equipment_ids=all_eq,
        months=list(range(1, 13)), year=year,
        start_date=start, end_date=end,
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


def _period_agg(year: int) -> dict:
    """Agregado dos totais brutos da planta no período (BR-11 paridade V1).
    Retorna {mtbf, mttr, breakdown_rate} em unit V1 (mttr em horas).

    Mock mode: média simples dos 12 valores mensais mock (non-zero). MTTR mock
    está em minutos (display), divide por 60 pra respeitar contrato unit-interno
    que o caller espera (_to_display reaplica ×60).
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
    codes = tuple(BREAKDOWN_CODES)
    key = (year, codes)
    hit = _cache_get(_CACHE_PERIOD, key)
    if hit is not None:
        return hit
    try:
        from src.utils.maintenance_demo_data import calculate_kpi_averages
        kpi_data = _cached_fetch_kpi(year, codes)
        all_eq = list(kpi_data.keys())
        start, end = _year_range(year)
        agg = calculate_kpi_averages(
            data=kpi_data,
            equipment_filter=all_eq,
            month_filter=list(range(1, 13)),
            year=year,
            start_date=start,
            end_date=end,
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


def _fetch_planta_monthly(kpi: str, year: int = DEFAULT_YEAR) -> list:
    """12 valores mensais agregados da planta — usa CACHE process-level.
    1ª chamada (qualquer KPI) faz fetch+agg; subsequentes pegam cached.
    """
    if not _HAS_REAL_DATA:
        return _mock_planta_mes(kpi)
    try:
        codes = tuple(BREAKDOWN_CODES)
        kpi_data = _cached_fetch_kpi(year, codes)
        agg = _cached_agg(kpi_data, year, codes)
        field = KPI_FIELD_MAP[kpi]
        values = []
        for m in range(1, 13):
            key = f"{year}-{m:02d}"
            entry = agg.get(key) or agg.get(m) or {}
            raw = float(entry.get(field, 0) or 0)
            values.append(_to_display(kpi, raw))
        if all(v == 0 for v in values):
            return _mock_planta_mes(kpi)
        return values
    except Exception as e:
        logger.warning("V2 planta %s falhou (%s) — fallback mock", kpi, e)
        return _mock_planta_mes(kpi)


def _fetch_equipment_monthly(kpi: str, equipment: str, year: int = DEFAULT_YEAR) -> list:
    """12 valores mensais do equipamento — usa CACHE process-level.
    Loop sobre equipamentos no grid usa o MESMO cached kpi_data (1 query Mongo).
    """
    if not _HAS_REAL_DATA:
        return _mock_equipamento_mes(kpi, equipment)
    try:
        codes = tuple(BREAKDOWN_CODES)
        kpi_data = _cached_fetch_kpi(year, codes)
        eq_data = kpi_data.get(equipment, [])
        if not eq_data:
            names = _cached_names()
            reverse = {v: k for k, v in names.items()}
            internal_id = reverse.get(equipment, equipment)
            eq_data = kpi_data.get(internal_id, [])
        field = KPI_FIELD_MAP[kpi]
        values = []
        for m in range(1, 13):
            entry = next((d for d in eq_data if d.get("month") == m), None)
            if entry:
                raw = float(entry.get(field, 0) or 0)
                values.append(_to_display(kpi, raw))
            else:
                values.append(0)
        if all(v == 0 for v in values):
            return _mock_equipamento_mes(kpi, equipment)
        return values
    except Exception as e:
        logger.warning("V2 equip %s/%s falhou (%s)", equipment, kpi, e)
        return _mock_equipamento_mes(kpi, equipment)


def _fetch_daily_kpi(kpi: str, equipment: str, month: int, year: int = DEFAULT_YEAR) -> tuple:
    """Retorna (dias, valores) por dia do mês para o KPI/equipamento.
    Fallback mock se erro.
    """
    if not _HAS_REAL_DATA:
        return _mock_dias(kpi, equipment, month)
    try:
        start, end = _month_range(year, month)
        prod_df = fetch_zpp_production_data(start, end)
        brk_df = fetch_zpp_breakdown_data(start, end, breakdown_codes=BREAKDOWN_CODES)
        # Resolver id interno se necessário
        names = get_zpp_equipment_names()
        reverse = {v: k for k, v in names.items()}
        internal_id = reverse.get(equipment, equipment)
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
        if all(v == 0 for v in values):
            return _mock_dias(kpi, equipment, month)
        return dias, values
    except Exception as e:
        logger.warning("V2 daily %s/%s/%s falhou (%s)", equipment, month, kpi, e)
        return _mock_dias(kpi, equipment, month)


def _fetch_top_paradas_real(equipment: str, month: int, year: int = DEFAULT_YEAR, top_n: int = 10) -> list:
    """Top N paradas do mês — usa fetch_top_breakdowns_by_equipment da V1.
    Aplica BR-13 (agrupamento por dia+causa) já feito pela função V1.
    """
    if not _HAS_REAL_DATA:
        return _mock_top_paradas_mes(equipment, month, top_n)
    try:
        start, end = _month_range(year, month)
        names = get_zpp_equipment_names()
        reverse = {v: k for k, v in names.items()}
        internal_id = reverse.get(equipment, equipment)
        items_v1 = fetch_top_breakdowns_by_equipment(
            internal_id, start, end, top_n=top_n, breakdown_codes=BREAKDOWN_CODES
        )
        if not items_v1:
            return _mock_top_paradas_mes(equipment, month, top_n)
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
                "date":        date_str,
                "descricao":   it.get("descricao", "—"),
                "duracao_min": int(it.get("duracao_min", 0) or 0),
                "count":       int(it.get("count", 1) or 1),
                "codigo":      it.get("motivo", "—"),
            })
        return items
    except Exception as e:
        logger.warning("V2 top paradas %s/%s falhou (%s)", equipment, month, e)
        return _mock_top_paradas_mes(equipment, month, top_n)


def _fetch_events_day_real(equipment: str, month: int, day: int, year: int = DEFAULT_YEAR) -> list:
    """Eventos (paradas) do dia para o equipamento — SEM filtro de breakdown codes.
    Mostra TODOS os códigos (operador quer ver tudo que aconteceu).
    """
    if not _HAS_REAL_DATA:
        return _mock_eventos_dia(None, equipment, month, day)
    try:
        names = get_zpp_equipment_names()
        reverse = {v: k for k, v in names.items()}
        internal_id = reverse.get(equipment, equipment)
        start = datetime(year, month, day)
        end = start + timedelta(days=1)
        col = get_mongo_connection("ZPP_Paradas")
        if col is None:
            return _mock_eventos_dia(None, equipment, month, day)
        query = {
            "centro_de_trabalho": internal_id,
            "inicio_execucao": {"$gte": start, "$lt": end},  # BR-12 semi-aberta
        }
        cursor = col.find(
            query,
            {
                "_id": 0,
                "inicio_execucao": 1,
                "centro_de_trabalho": 1,
                "descricao": 1,
                "duration_min": 1,
                "causa_do_desvio": 1,
            },
        ).sort("inicio_execucao", 1)
        eventos = []
        for doc in cursor:
            ts = doc.get("inicio_execucao")
            hora = ts.strftime("%H:%M") if hasattr(ts, "strftime") else "—"
            eventos.append({
                "Hora":          hora,
                "Equipamento":   equipment,
                "Causa":         doc.get("descricao", "—"),
                "Duração (min)": int(doc.get("duration_min", 0) or 0),
                "Código":        doc.get("causa_do_desvio", "—"),
            })
        if not eventos:
            return _mock_eventos_dia(None, equipment, month, day)
        return eventos
    except Exception as e:
        logger.warning("V2 eventos dia %s/%s/%s falhou (%s)", equipment, month, day, e)
        return _mock_eventos_dia(None, equipment, month, day)


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


def _top_paradas_h_bar(items, equipment, month, td=None):
    """Barras horizontais top 5 (gradient vermelho→verde por intensidade).

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
        words, lines, cur, ln = text.split(), [], [], 0
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
    y_ticktext = [f"{bd['date'][:5]}<br>{wrap(bd['descricao'])}" for bd in top5]
    x_values = [bd["duracao_min"] for bd in top5]
    counts = [bd["count"] for bd in top5]
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
    fig.update_layout(
        title=dict(
            text=f"{top_title_tpl.format(n=len(top5))} — {equipment} — {MESES_PT[month-1]}/2026",
            x=0.5, xanchor="center", font=dict(size=13),
        ),
        xaxis=dict(title=dict(text=td.get("chart_duracao_min","Duração (min)"), font=dict(size=10)),
                   range=[0, max_d + 50]),
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


def _bar_rich(x, y, title, color, unit="", target=None, direction="higher", td=None):
    """Wrap _bar adicionando hovertemplate enriquecido (valor, meta, delta, status).

    td: dict TRANS[lang] pra i18n labels.
    """
    td = td or {}
    fig = _bar(x, y, title, color, unit, target=target, show_trend=True, compact=False, td=td)
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


def _bar(x, y, title, color, unit="", target=None, show_trend=True, compact=False, td=None):
    """Bar chart com overlay opcional de meta (linha tracejada) e tendência (poly grau 2).

    target: valor da linha de meta horizontal; None oculta.
    show_trend: True desenha tendência sobre as barras.
    compact: True reduz fontes/margens pra mini-cards.
    td: dict de traduções (TRANS[lang]) pra labels "Tendência"/"Meta"/"Valor"; default PT.
    """
    td = td or {}
    bar_color = color
    target_color = "#6c757d"
    trend_color = "#212529"

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=x,
            y=y,
            marker_color=bar_color,
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
    ]

    @app.callback(
        [Output(eid, "children") for eid, _ in I18N_OUTPUTS] + [
            Output("switch-v2-mtto-only", "label"),
            Output("tab-v2-general-component", "label"),
            Output("tab-v2-data-component", "label"),
            Output("tab-v2-report-component", "label"),
            Output("filter-v2-period-type", "options"),
            Output("filter-v2-equipment", "placeholder"),
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

    @app.callback(
        Output("filter-v2-equipment", "options"),
        Input("url", "pathname"),
    )
    def populate_equipment_filter(pathname):
        if pathname != "/maintenance/indicators-v2":
            return no_update
        eq_list = _list_equipments_real()
        return [{"label": eq["id"], "value": eq["id"]} for eq in eq_list]

    # IM-11 — Apply filters → escreve store-v2-filters
    @app.callback(
        Output("store-v2-filters", "data"),
        Input("btn-apply-v2-filters", "n_clicks"),
        Input("btn-refresh-indicators-v2", "n_clicks"),
        Input("url", "pathname"),
        State("filter-v2-period-type", "value"),
        State("filter-v2-reference-year", "value"),
        State("filter-v2-date-range", "start_date"),
        State("filter-v2-date-range", "end_date"),
        State("filter-v2-equipment", "value"),
        State("filter-v2-breakdown-codes", "value"),
        prevent_initial_call=False,
    )
    def apply_v2_filters(apply_n, refresh_n, pathname, ptype, year, sdate, edate, equip, codes):
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
        return {
            "period_type": ptype or "year",
            "year":        year,
            "start_iso":   start.isoformat(),
            "end_iso":     end.isoformat(),
            "equipment":   equip or [],
            "codes":       codes or list(BREAKDOWN_CODES) if _HAS_REAL_DATA else codes,
        }

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
        year = (filters or {}).get("year", DEFAULT_YEAR)
        lang = lang or "pt"
        td_lang = _TRANS.get(lang, _TRANS["pt"])
        title_planta = td_lang.get("tl_planta_mensal", "Planta — mensal")

        def _planta_fig(kpi, values, target):
            fig = _bar_rich(MESES_PT, values, title_planta,
                            KPI_META[kpi]["color"], KPI_META[kpi]["unit"],
                            target=target, direction=KPI_META[kpi]["direction"],
                            td=td_lang)
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

        v_br = _fetch_planta_monthly("breakdown", year)
        v_mt = _fetch_planta_monthly("mtbf", year)
        v_mtr = _fetch_planta_monthly("mttr", year)
        t_br = _resolve_target("breakdown")
        t_mt = _resolve_target("mtbf")
        t_mtr = _resolve_target("mttr")

        base_class = "shadow-sm h-100 indicator-v2-card"  # mesmo que _kpi_card aplica
        # Mas precisamos voltar a className do html.Div pai (kpi-card-{kpi}):
        wrapper_class = ""  # html.Div wrapper só tem cursor+height inline

        # Card value = AGREGADO DO PERÍODO (totais brutos, BR-11 paridade V1)
        # Não é último mês — é planta inteira agregada (sum active_h, sum brk_h,
        # sum failures → recalcula KPI). Igual cards V1.
        agg = _period_agg(year)
        last_br  = _to_display("breakdown", agg.get("breakdown_rate", 0))
        last_mt  = _to_display("mtbf",      agg.get("mtbf", 0))
        last_mtr = _to_display("mttr",      agg.get("mttr", 0))

        return (
            _planta_fig("breakdown", v_br, t_br),
            _planta_fig("mtbf", v_mt, t_mt),
            _planta_fig("mttr", v_mtr, t_mtr),
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
        year = (filters or {}).get("year", DEFAULT_YEAR)
        # Tabela: equipamento × mês × {mtbf, mttr, breakdown_rate}
        rows = []
        try:
            eq_list = _list_equipments_real()
            for eq in eq_list:
                eq_id = eq["id"]
                cat = eq.get("categoria", "—")
                for kpi in ("mtbf", "mttr", "breakdown"):
                    monthly = _fetch_equipment_monthly(kpi, eq_id, year)
                    for m, v in enumerate(monthly, start=1):
                        rows.append({
                            "Equipamento": eq_id,
                            "Categoria":   cat,
                            "Ano":         year,
                            "Mês":         m,
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
        filename = f"indicators_v2_{year}_{_dt.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
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
        Output("store-v2-day", "data"),
        Output("modal-v2-content", "children", allow_duplicate=True),
        Output("modal-v2-title", "children", allow_duplicate=True),
        Output("modal-v2-breadcrumb", "children", allow_duplicate=True),
        Input("kpi-card-breakdown", "n_clicks"),
        Input("kpi-card-mtbf", "n_clicks"),
        Input("kpi-card-mttr", "n_clicks"),
        Input({"type": "v2-eq", "kpi": ALL, "equipment": ALL}, "n_clicks"),
        Input({"type": "v2-month", "kpi": ALL, "equipment": ALL, "month": ALL}, "n_clicks"),
        Input({"type": "v2-day", "kpi": ALL, "equipment": ALL, "month": ALL, "day": ALL}, "n_clicks"),
        Input({"type": "v2-bar-month", "kpi": ALL, "equipment": ALL}, "clickData"),
        Input({"type": "v2-bar-day", "kpi": ALL, "equipment": ALL, "month": ALL}, "clickData"),
        Input("btn-v2-back", "n_clicks"),
        Input("btn-v2-close", "n_clicks"),
        State("store-v2-level", "data"),
        State("store-v2-kpi", "data"),
        State("store-v2-equipment", "data"),
        State("store-v2-month", "data"),
        prevent_initial_call=True,
    )
    def control_modal(c_br, c_mtbf, c_mttr, eq_clicks, mo_clicks, dy_clicks,
                      bar_month_clicks, bar_day_clicks,
                      back, close, level, kpi, equipment, month):
        trig = dash.callback_context.triggered_id

        # CLEAR = limpa content/title/breadcrumb. render_modal_content preenche depois.
        CLEAR = (None, "", None)
        NOOP = (no_update,) * 3

        if trig == "btn-v2-close":
            return (False, "planta", None, None, None, None) + CLEAR

        if trig == "btn-v2-back":
            if level == "tabela":
                return (True, "dias", kpi, equipment, month, None) + CLEAR
            if level == "dias":
                return (True, "meses", kpi, equipment, None, None) + CLEAR
            if level == "mes-top":
                return (True, "meses", kpi, equipment, None, None) + CLEAR
            if level == "meses":
                return (True, "equipamentos", kpi, None, None, None) + CLEAR
            if level == "equipamentos":
                return (False, "planta", None, None, None, None) + CLEAR
            return (no_update,) * 6 + NOOP

        # Click num card KPI (qualquer região do card) — trig é string id
        if isinstance(trig, str):
            kpi_map = {
                "kpi-card-breakdown": "breakdown",
                "kpi-card-mtbf": "mtbf",
                "kpi-card-mttr": "mttr",
            }
            if trig in kpi_map:
                return (True, "equipamentos", kpi_map[trig], None, None, None) + CLEAR

        # Pattern clicks — trig é AttributeDict (dict-like)
        if not isinstance(trig, str) and trig is not None:
            t = trig.get("type")
            if t == "v2-eq":
                return (True, "meses", trig["kpi"], trig["equipment"], None, None) + CLEAR
            if t == "v2-month":
                # Click no CARD do mês → top paradas mensais (barras horizontais + tabela)
                return (True, "mes-top", trig["kpi"], trig["equipment"], trig["month"], None) + CLEAR
            if t == "v2-day":
                return (True, "tabela", trig["kpi"], trig["equipment"], trig["month"], trig["day"]) + CLEAR

            # Click numa barra do gráfico grande
            if t in ("v2-bar-month", "v2-bar-day"):
                ctx_trig = dash.callback_context.triggered
                if not ctx_trig or ctx_trig[0].get("value") is None:
                    return (no_update,) * 6 + NOOP
                click = ctx_trig[0]["value"]
                x_val = click["points"][0]["x"]
                if t == "v2-bar-month":
                    return (True, "dias", trig["kpi"], trig["equipment"], MESES_PT.index(x_val) + 1, None) + CLEAR
                if t == "v2-bar-day":
                    return (True, "tabela", trig["kpi"], trig["equipment"], trig["month"], int(x_val)) + CLEAR

        return (no_update,) * 6 + NOOP

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
        Input("store-v2-day", "data"),
        Input("store-v2-lang", "data"),
        prevent_initial_call=True,
    )
    def render_modal(level, kpi, equipment, month, day, lang):
        if not kpi:
            return None, "", None, {"display": "none"}

        lang = lang or "pt"
        td = _TRANS.get(lang, _TRANS["pt"])  # tradução por key
        meses_curtos = td.get("month_short", MESES_PT)
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
            for eq in eq_list:
                values = _fetch_equipment_monthly(kpi, eq["id"])
                eq_target = _resolve_target(kpi, eq.get("internal", eq["id"]))
                # Compact + figure cacheada por (kpi, eq, values, target)
                fig = _cached_compact_bar(kpi, eq["id"], DEFAULT_YEAR, values,
                                          eq_target, meta["color"], meta["unit"])
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
            values = _fetch_equipment_monthly(kpi, equipment)
            eq_target = _resolve_target(kpi, equipment)
            main_fig = _bar(MESES_PT, values, f"{equipment} — {td.get('mdl_meses','12 meses')}",
                            meta["color"], meta["unit"],
                            target=eq_target, show_trend=True, td=td)
            main_fig.update_layout(height=380)

            # mini-cards por mês (clicáveis) abaixo do gráfico grande
            mini_rows = []
            for idx, (m_label, val) in enumerate(zip(MESES_PT, values), start=1):
                mini_rows.append(
                    dbc.Col(
                        html.Div(
                            dbc.Card(
                                dbc.CardBody(
                                    [
                                        html.Div(m_label, className="text-muted small mb-1"),
                                        html.Div(
                                            f"{val}{meta['unit']}",
                                            style={"fontSize": "1.2rem", "fontWeight": "bold",
                                                   "color": meta["color"]},
                                        ),
                                    ],
                                    className="text-center py-2",
                                ),
                                className="shadow-sm",
                            ),
                            id={"type": "v2-month", "kpi": kpi, "equipment": equipment, "month": idx},
                            n_clicks=0,
                            style={"cursor": "pointer"},
                        ),
                        xs=6, sm=4, md=3, lg=2,
                        className="mb-2",
                    )
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
            items = _fetch_top_paradas_real(equipment, month, top_n=10)
            h_bar = _top_paradas_h_bar(items, equipment, month, td=td)

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
                        {"if": {"filter_query": "{" + col_dur + "} >= 200"},
                         "backgroundColor": "#fff3cd"},
                        {"if": {"filter_query": "{" + col_dur + "} >= 400"},
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
            title = f"{kpi_label} — {td.get('mdl_top_paradas','Top paradas')} — {equipment} — {meses_curtos[month-1]}/2026"
            return content, title, breadcrumb_items, {}

        # NÍVEL 4: dias — IM-04
        if level == "dias" and equipment and month:
            dias, valores = _fetch_daily_kpi(kpi, equipment, month)
            eq_target = _resolve_target(kpi, equipment)
            main_fig = _bar(
                [f"{d:02d}" for d in dias],
                valores,
                f"{equipment} — {meses_curtos[month-1]}/2026",
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
                                "month": month, "day": d},
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
                        id={"type": "v2-bar-day", "kpi": kpi, "equipment": equipment, "month": month},
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
            title = f"{kpi_label} — {equipment} — {meses_curtos[month-1]}/2026"
            return content, title, breadcrumb_items, {}

        # NÍVEL 5: tabela (paradas do dia) — IM-05
        if level == "tabela" and equipment and month and day:
            eventos = _fetch_events_day_real(equipment, month, day)

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
                        {"if": {"filter_query": "{" + col_dur + "} >= 120"},
                         "backgroundColor": "#fff3cd"},
                        {"if": {"filter_query": "{" + col_dur + "} >= 240"},
                         "backgroundColor": "#f8d7da"},
                    ],
                    page_size=20,
                    sort_action="native",
                )

            content = html.Div(
                [
                    dbc.Alert(
                        [
                            html.I(className="bi bi-info-circle me-2"),
                            f"{td.get('mdl_paradas_em','Paradas em')} {equipment} — {day:02d}/{month:02d}/2026 — "
                            f"{len(eventos)} {td.get('mdl_eventos','eventos')}.",
                        ],
                        color="info",
                        className="mb-3",
                    ),
                    body,
                ]
            )
            breadcrumb_items += [
                html.Span(" › ", className="mx-1 text-muted"),
                html.Span(equipment, className="text-primary fw-semibold"),
                html.Span(" › ", className="mx-1 text-muted"),
                html.Span(meses_curtos[month - 1], className="text-primary fw-semibold"),
                html.Span(" › ", className="mx-1 text-muted"),
                html.Span(f"Dia {day:02d}", className="text-primary fw-semibold"),
            ]
            title = f"{td.get('mdl_paradas_em','Paradas em')} — {equipment} — {day:02d}/{month:02d}/2026"
            return content, title, breadcrumb_items, {}

        return None, "", None, {"display": "none"}
