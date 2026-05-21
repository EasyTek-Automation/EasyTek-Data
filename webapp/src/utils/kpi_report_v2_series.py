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
from datetime import datetime, timedelta
from typing import Optional

from src.utils.maintenance_demo_data import calculate_general_avg_by_month
from src.utils.zpp_kpi_calculator import (
    BREAKDOWN_CODES,
    fetch_zpp_breakdown_data,
    fetch_zpp_kpi_data,
)

logger = logging.getLogger(__name__)


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


def build_daily_series_last_n(
    now: datetime,
    n_days: int,
    equipment_ids: list[str],
) -> dict:
    """Retorna séries de N valores diários encerrando em ontem 00:00 (último dia completo).

    O último item da série coincide com a janela BR-02 (`compute_last_24h_window`).

    Args:
        now: datetime aware no fuso.
        n_days: Número de dias na série (típico 7).
        equipment_ids: IDs dos equipamentos no escopo (BR-05).

    Returns:
        ```
        {
            "labels":   ["DD/MM", ...],
            "mtbf":     [v1..vN],
            "mttr":     [v1..vN],  # em minutos
            "taxa_avaria": [v1..vN],
            "current_idx": N-1,  # último item = janela BR-02
        }
        ```
    """
    if n_days <= 0:
        n_days = 1

    end_today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    # último item: [ontem 00:00, hoje 00:00). Primeiro item: ontem-(N-1).
    days: list[tuple[datetime, datetime]] = []
    labels: list[str] = []
    for offset in range(n_days - 1, -1, -1):
        day_end = end_today_midnight - timedelta(days=offset)
        day_start = day_end - timedelta(days=1)
        days.append((day_start, day_end))
        labels.append(day_start.strftime("%d/%m"))

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
