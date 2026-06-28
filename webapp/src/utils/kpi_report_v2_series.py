"""KPIReport-v2 — agregação de séries temporais (refactor RF-04).

Wraps das funções canônicas v1 (`calculate_general_avg_by_month`,
`fetch_zpp_kpi_data`, `fetch_zpp_production_data`, `fetch_zpp_breakdown_data`)
para produzir séries prontas pro bar chart:

- **monthly_series**: 12 valores (Jan..Dez) do ano corrente — paradigma Indicators-V2.
- **daily_series**: N valores (últimos N dias) — janela 24h destacada (BR-02).

Anti-pattern proibido: **nunca recalcula KPI** (delega a v1). **Nunca define
próprios `BREAKDOWN_CODES` / janelas**. Apenas particiona janelas em buckets.
"""
from __future__ import annotations

import logging
import time as _time
from datetime import datetime, timedelta
from typing import Optional

from src.utils.maintenance_demo_data import calculate_general_avg_by_month
from src.utils.zpp_kpi_calculator import (
    BREAKDOWN_CODES,
    fetch_zpp_breakdown_data,
    fetch_zpp_kpi_data,
)

logger = logging.getLogger(__name__)

# Cache TTL para a série 24h da home (carrossel gira a cada 15s; sem cache,
# cada giro dispara até `max_lookback`+`n_days` queries ao Mongo). 60s = padrão v2.
_CACHE_TTL_SECONDS = 60
_CACHE_24H: dict = {}  # date_key (YYYY-MM-DD) → (ts, payload)


MESES_PT: tuple[str, ...] = (
    "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
)


def build_monthly_series_for_year(
    year: int,
    equipment_ids: list[str],
    current_month: int,
) -> dict:
    """Retorna séries de 12 valores (Jan..Dez) por KPI agregando dados da planta.

    Args:
        year: Ano a buscar.
        equipment_ids: IDs dos equipamentos no escopo (BR-05).
        current_month: Mês 1..12 a destacar (mês corrente).

    Returns:
        ```
        {
            "labels": ["Jan", "Fev", ...],
            "mtbf": [v1..v12],
            "mttr": [v1..v12],  # em minutos (conversão h→min como v1)
            "taxa_avaria": [v1..v12],
            "current_idx": int 0..11,
        }
        ```
    """
    base = {
        "labels":         list(MESES_PT),
        "mtbf":           [0.0] * 12,
        "mttr":           [0.0] * 12,
        "taxa_avaria":    [0.0] * 12,
        "current_idx":    max(0, min(11, current_month - 1)),
    }

    try:
        start = datetime(year, 1, 1)
        end = datetime(year + 1, 1, 1)
        # `data` legado fica vazio — o método principal usa start_date/end_date e busca brutos
        agg = calculate_general_avg_by_month(
            data={},
            equipment_ids=equipment_ids,
            months=list(range(1, 13)),
            year=year,
            start_date=start,
            end_date=end,
        )
    except Exception as exc:
        logger.warning("KPI v2 monthly series: falha agregação ano %d (%s)",
                       year, type(exc).__name__)
        return base

    for m in range(1, 13):
        key = f"{year}-{m:02d}"
        entry = agg.get(key) or {}
        mtbf = entry.get("mtbf")
        mttr_h = entry.get("mttr")
        br = entry.get("breakdown_rate")
        base["mtbf"][m - 1]        = float(mtbf) if isinstance(mtbf, (int, float)) else 0.0
        # v1 retorna MTTR em horas — converter pra minutos (consistente com KPIReport v1 SP-09)
        base["mttr"][m - 1]        = float(mttr_h) * 60.0 if isinstance(mttr_h, (int, float)) else 0.0
        base["taxa_avaria"][m - 1] = float(br) if isinstance(br, (int, float)) else 0.0

    return base


def build_daily_series_last_n_ending(
    end_day: datetime,
    n_days: int,
    equipment_ids: list[str],
) -> dict:
    """Variante de `build_daily_series_last_n` com `end_day` custom (BR-02b).

    `end_day` = dia destacado (naïve no fuso). Série cobre `[end_day - (N-1), end_day]`.
    Último item = janela `[end_day 00:00, end_day+1 00:00)`.
    """
    if n_days <= 0:
        n_days = 1
    end_day_midnight = end_day.replace(hour=0, minute=0, second=0,
                                        microsecond=0, tzinfo=None)
    # Cada item: janela [dia 00:00, dia+1 00:00)
    days: list[tuple[datetime, datetime]] = []
    labels: list[str] = []
    for offset in range(n_days - 1, -1, -1):
        d_start = end_day_midnight - timedelta(days=offset)
        d_end = d_start + timedelta(days=1)
        days.append((d_start, d_end))
        labels.append(d_start.strftime("%d/%m"))

    series = {
        "labels":      labels,
        "mtbf":        [0.0] * n_days,
        "mttr":        [0.0] * n_days,
        "taxa_avaria": [0.0] * n_days,
        "current_idx": n_days - 1,
    }
    for i, (d_start, d_end) in enumerate(days):
        try:
            mtbf, mttr_min, br = _compute_plant_kpis_for_window(d_start, d_end)
        except Exception as exc:
            logger.debug("KPI v2 daily series %s: sem dados (%s)",
                          d_start.date(), type(exc).__name__)
            continue
        series["mtbf"][i]        = mtbf
        series["mttr"][i]        = mttr_min
        series["taxa_avaria"][i] = br
    return series


def build_daily_series_last_n(
    now: datetime,
    n_days: int,
    equipment_ids: list[str],
) -> dict:
    """Retorna séries de N valores diários encerrando em ontem (BR-02 padrão).

    Wrapper sobre `build_daily_series_last_n_ending` com `end_day = ontem`.
    """
    yesterday = now.replace(hour=0, minute=0, second=0, microsecond=0,
                              tzinfo=None) - timedelta(days=1)
    return build_daily_series_last_n_ending(yesterday, n_days, equipment_ids)


def _compute_plant_kpis_for_window(
    start: datetime, end: datetime,
) -> tuple[float, float, float]:
    """Agrega MTBF / MTTR (min) / Taxa Avaria (%) da planta em `[start, end)`.

    Fórmulas canônicas v1 (PRO017) — não diverge de `calculate_general_avg_by_month`:
        MTBF = (active_hours - breakdown_hours) / num_failures
        MTTR_min = breakdown_minutes / num_failures
        BR (%) = breakdown_hours / active_hours * 100

    Raises:
        Exception: propagado pra caller (interpretado como "sem dados").
    """
    from src.utils.zpp_kpi_calculator import fetch_zpp_production_data

    prod_df = fetch_zpp_production_data(start, end)
    brk_df = fetch_zpp_breakdown_data(start, end, breakdown_codes=BREAKDOWN_CODES)

    if prod_df.empty:
        return 0.0, 0.0, 0.0

    total_active_hours = float(prod_df["horasact"].sum())
    if total_active_hours <= 0:
        return 0.0, 0.0, 0.0

    if brk_df.empty:
        return 999.0, 0.0, 0.0

    num_failures = len(brk_df)
    total_breakdown_min = float(brk_df["duracao_min"].sum())
    total_breakdown_hours = total_breakdown_min / 60.0

    if num_failures <= 0:
        return 999.0, 0.0, 0.0

    mtbf = (total_active_hours - total_breakdown_hours) / num_failures
    mttr_min = total_breakdown_min / num_failures
    br_pct = (total_breakdown_hours / total_active_hours) * 100.0
    return round(mtbf, 1), round(mttr_min, 1), round(br_pct, 2)


def _day_has_production(day_midnight: datetime) -> bool:
    """True se o dia-calendário `[day 00:00, day+1 00:00)` teve produção (>0 h ativas)."""
    from src.utils.zpp_kpi_calculator import fetch_zpp_production_data
    d_start = day_midnight.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    d_end = d_start + timedelta(days=1)
    try:
        prod_df = fetch_zpp_production_data(d_start, d_end)
    except Exception as exc:
        logger.debug("find_last_production_day: falha probe %s (%s)",
                     d_start.date(), type(exc).__name__)
        return False
    return (not prod_df.empty) and float(prod_df["horasact"].sum()) > 0.0


def find_last_production_day(now: datetime, max_lookback: int = 14) -> datetime:
    """Retorna o último dia-calendário (à meia-noite) que teve produção.

    Começa em **ontem** e retrocede dia a dia até achar um dia com horas ativas > 0.
    Resolve o caso fim-de-semana/feriado: numa 2ª de manhã, "ontem" é domingo sem
    produção → retrocede até a 6ª. Se nenhum dos `max_lookback` dias tiver produção,
    cai em ontem (comportamento neutro, série virá zerada).

    Args:
        now: Instante de referência (naïve ou aware; normalizado a naïve).
        max_lookback: Máximo de dias a retroceder antes de desistir.

    Returns:
        `datetime` à meia-noite do dia destacado (naïve, tzinfo removido).
    """
    yesterday = now.replace(hour=0, minute=0, second=0, microsecond=0,
                            tzinfo=None) - timedelta(days=1)
    probe = yesterday
    for _ in range(max(1, max_lookback)):
        if _day_has_production(probe):
            return probe
        probe -= timedelta(days=1)
    logger.info("find_last_production_day: sem produção nos últimos %d dias até %s — "
                "usando ontem (%s) como fallback neutro.",
                max_lookback, yesterday.date(), yesterday.date())
    return yesterday


def build_last_production_24h_series(
    now: datetime,
    n_days: int = 7,
    equipment_ids: Optional[list[str]] = None,
    max_lookback: int = 14,
) -> dict:
    """Série de N dias encerrando no **último dia com produção** (home — recorte 24h).

    Acha o último dia-calendário com produção (`find_last_production_day`) e devolve a
    série diária de `n_days` terminando nele, com `current_idx` no último item (= o dia
    destacado, fonte do "número grande"). Mantém o anti-pattern do módulo: **não
    recalcula KPI**, só particiona janelas via `build_daily_series_last_n_ending`.

    Cacheado por `_CACHE_TTL_SECONDS` keyed pela data do dia destacado — o carrossel
    gira a cada 15s e não deve remartelar o Mongo.

    Returns:
        ```
        {
            "labels": ["31/05", ..., "06/06"],   # n_days rótulos dd/mm
            "mtbf":   [v1..vN],                  # h
            "mttr":   [v1..vN],                  # min
            "taxa_avaria": [v1..vN],             # %
            "current_idx": N-1,                  # dia destacado (último com produção)
            "highlight_date": "06/06",           # rótulo do dia destacado
        }
        ```
    """
    end_day = find_last_production_day(now, max_lookback=max_lookback)
    cache_key = end_day.strftime("%Y-%m-%d") + ":%d" % n_days
    hit = _CACHE_24H.get(cache_key)
    if hit and (_time.time() - hit[0]) < _CACHE_TTL_SECONDS:
        return hit[1]

    series = build_daily_series_last_n_ending(end_day, n_days, equipment_ids or [])
    series["highlight_date"] = end_day.strftime("%d/%m")
    _CACHE_24H[cache_key] = (_time.time(), series)
    return series
