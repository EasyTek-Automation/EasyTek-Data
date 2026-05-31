"""Callback de renderização da aba '📋 Dados' do indicators-v2.

Reusa o **layout V1** completo da aba Dados (`/maintenance/indicators` →
Tab Dados Brutos): cobertura ZPP, tabela mensal debug, cards de resumo,
motivos de parada, tabela detalhada por equipamento.

Estratégia: V2 monta um `stored_data` equivalente ao que
`process_filters_and_load_data` (callback V1) produz, e renderiza o mesmo
DOM. Helpers canônicos compartilhados são reusados (`_build_raw_table_internal`,
`aggregate_breakdown_by_cause`, `get_zpp_data_coverage`).

Trigger: `tabs-indicators-v2.active_tab == 'tab-v2-data'`.
"""
from __future__ import annotations

import logging
from datetime import datetime

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, dash_table, html

from src.utils.maintenance_demo_data import (
    _build_raw_table_internal,
    calculate_general_avg_by_month,
    get_all_equipment_targets,
)
from src.utils.zpp_kpi_calculator import (
    BREAKDOWN_CODES,
    aggregate_breakdown_by_cause,
    fetch_zpp_kpi_data,
    get_zpp_data_coverage,
    get_zpp_equipment_categories,
    get_zpp_equipment_names,
)

logger = logging.getLogger(__name__)

_MN = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
       "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


# ============================================================================
# Carregador de stored_data (espelha process_filters_and_load_data V1)
# ============================================================================

def _iter_year_months(start: datetime, end: datetime) -> list[str]:
    """Lista de "YYYY-MM" cobrindo [start, end) — suporta cross-year.

    Inclui o mês `(y, m)` se seu primeiro dia `< end`; caller passa `end` como
    primeiro instante do mês seguinte (convenção BR-12).
    """
    out = []
    y, m = start.year, start.month
    while datetime(y, m, 1) < end:
        out.append(f"{y}-{m:02d}")
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return out


def _build_full_stored_data_v2(
    start: datetime,
    end: datetime,
    codes: list[str] | None = None,
    equipment_filter: list[str] | None = None,
) -> dict:
    """Carrega janela [start, end) para a aba Dados V2, respeitando filtros.

    Reusa funções canônicas v1 (fetch_zpp_kpi_data, get_zpp_equipment_*,
    calculate_general_avg_by_month, get_zpp_data_coverage). Não recalcula KPI.

    Args:
        start: início da janela (datetime naïve, inclusivo)
        end: fim da janela (datetime naïve, exclusivo — primeiro instante do mês seguinte)
        codes: códigos de avaria a considerar (default: BREAKDOWN_CODES)
        equipment_filter: lista de equipamentos a incluir (default: todos os retornados)
    """
    codes = list(codes) if codes else list(BREAKDOWN_CODES)

    data: dict = {}
    has_data = False
    try:
        data = fetch_zpp_kpi_data(start, end, breakdown_codes=codes)
        has_data = bool(data)
    except Exception:
        logger.exception("KPI v2 data tab: fetch_zpp_kpi_data falhou")
        data = {}

    # Aplica filtro de equipamento (preserva apenas os solicitados que existem nos dados)
    if has_data and equipment_filter:
        filtered = {k: v for k, v in data.items() if k in equipment_filter}
        if filtered:
            data = filtered
        # se filtro não bateu com nenhum equipamento retornado, mantém todos (fallback graceful)

    try:
        names = get_zpp_equipment_names() if has_data else {}
    except Exception:
        names = {}
    try:
        categories = get_zpp_equipment_categories() if has_data else {}
    except Exception:
        categories = {}
    try:
        equipment_targets = get_all_equipment_targets() or {}
    except Exception:
        equipment_targets = {}

    monthly_aggregates = None
    if has_data:
        try:
            monthly_aggregates = calculate_general_avg_by_month(
                data, list(data.keys()), start_date=start, end_date=end,
            )
        except Exception:
            logger.exception("KPI v2 data tab: monthly_aggregates falhou")

    data_coverage = {}
    if has_data:
        try:
            data_coverage = get_zpp_data_coverage(
                start, end, breakdown_codes=codes,
            ) or {}
        except Exception:
            logger.exception("KPI v2 data tab: data_coverage falhou")

    year_months = _iter_year_months(start, end)
    months = sorted({int(ym.split("-")[1]) for ym in year_months})

    return {
        "year":              start.year,
        "months":            months,
        "year_months":       year_months,
        "equipment_ids":     list(data.keys()),
        "data":              data,
        "names":             names,
        "categories":        categories,
        "equipment_targets": equipment_targets,
        "monthly_aggregates": monthly_aggregates,
        "data_coverage":     data_coverage,
        "period_start":      start.isoformat(),
        "period_end":        end.isoformat(),
        "has_data":          has_data,
    }


# ============================================================================
# Componentes de render (copy adaptado do callback V1 update_raw_data_tab)
# ============================================================================

def _fv(v, dec=1) -> str:
    return f"{v:.{dec}f}" if v is not None else "—"


def _stat_card(icon, label, value, color):
    return dbc.Col([
        dbc.Card([dbc.CardBody([
            html.Div([
                html.I(className=f"bi {icon}",
                       style={"fontSize": "1.3rem", "color": color}),
                html.Div([
                    html.Small(label, className="text-muted d-block",
                                style={"fontSize": "0.75rem"}),
                    html.Strong(value, style={"fontSize": "1.05rem"}),
                ], className="ms-3"),
            ], className="d-flex align-items-center"),
        ])], className="shadow-sm h-100"),
    ], xs=6, sm=4, md=3, lg=2, className="mb-3")


def _td(content, bold=False, bg=None, align="center"):
    style = {"textAlign": align, "padding": "6px 10px", "fontSize": "0.82rem"}
    if bold:
        style["fontWeight"] = "bold"
    if bg:
        style["backgroundColor"] = bg
    return html.Td(content, style=style)


def _render_summary_cards(totals: dict) -> dbc.Row:
    p_fail   = totals["num_paradas"]
    p_bd_min = totals["avaria_min"]
    p_bd_h   = totals["avaria_h"]
    p_act_h  = totals["atividade_h"]
    p_up_h   = totals["uptime_h"]
    p_mtbf   = totals["mtbf_h"]
    p_mttr   = totals["mttr_min"]
    p_bd_rate = totals["taxa_avaria"]
    return dbc.Row([
        _stat_card("bi-exclamation-circle-fill", "Nº Paradas",      str(p_fail),       "#dc3545"),
        _stat_card("bi-hourglass-split",         "Avaria (min)",    f"{p_bd_min:.1f}", "#fd7e14"),
        _stat_card("bi-hourglass-split",         "Avaria (h)",      f"{p_bd_h:.2f}",   "#fd7e14"),
        _stat_card("bi-lightning-charge-fill",   "Atividade (h)",   f"{p_act_h:.2f}",  "#0d6efd"),
        _stat_card("bi-arrow-up-circle-fill",    "Uptime (h)",      f"{p_up_h:.2f}",   "#198754"),
        _stat_card("bi-clock-history",           "MTBF (h)",        _fv(p_mtbf, 3),    "#20c997"),
        _stat_card("bi-tools",                   "MTTR (min)",      _fv(p_mttr, 3),    "#6f42c1"),
        _stat_card("bi-graph-down",              "Taxa Avaria (%)", _fv(p_bd_rate, 3), "#ffc107"),
    ], className="g-2")


def _render_equipment_table(rows: list[dict], totals: dict) -> dbc.Card:
    table_data = []
    for r in sorted(rows, key=lambda x: x["equipamento"]):
        table_data.append({
            "equipamento":  r["equipamento"],
            "num_ordens":   r["num_ordens"],
            "num_paradas":  r["num_paradas"],
            "avaria_min":   r["avaria_min"],
            "avaria_h":     r["avaria_h"],
            "atividade_h":  r["atividade_h"],
            "uptime_h":     r["uptime_h"],
            "mtbf_h":       r["mtbf_h"],
            "mttr_min":     r["mttr_min"],
            "taxa_avaria":  r["taxa_avaria"],
        })
    table_data.append({
        "equipamento":  "TOTAL DA PLANTA",
        "num_ordens":   totals["num_ordens"],
        "num_paradas":  totals["num_paradas"],
        "avaria_min":   round(totals["avaria_min"], 3),
        "avaria_h":     round(totals["avaria_h"], 3),
        "atividade_h":  round(totals["atividade_h"], 3),
        "uptime_h":     round(totals["uptime_h"], 3),
        "mtbf_h":       totals["mtbf_h"],
        "mttr_min":     totals["mttr_min"],
        "taxa_avaria":  totals["taxa_avaria"],
    })

    def _col(name, col_id, dec=None):
        c = {"name": name, "id": col_id, "type": "numeric"}
        if dec is not None:
            c["format"] = {"specifier": f".{dec}f"}
        return c

    columns = [
        {"name": "Equipamento",     "id": "equipamento"},
        _col("Nº Ordens",       "num_ordens",   0),
        _col("Nº Paradas",      "num_paradas",  0),
        _col("Avaria (min)",    "avaria_min",   3),
        _col("Avaria (h)",      "avaria_h",     3),
        _col("Atividade (h)",   "atividade_h",  3),
        _col("Uptime (h)",      "uptime_h",     3),
        _col("MTBF (h)",        "mtbf_h",       3),
        _col("MTTR (min)",      "mttr_min",     3),
        _col("Taxa Avaria (%)", "taxa_avaria",  3),
    ]
    table = dash_table.DataTable(
        columns=columns,
        data=table_data,
        sort_action="native",
        style_table={"overflowX": "auto"},
        style_cell={
            "textAlign": "center", "padding": "8px 14px",
            "fontFamily": "inherit", "fontSize": "0.85rem",
            "borderBottom": "1px solid #dee2e6",
        },
        style_cell_conditional=[
            {"if": {"column_id": "equipamento"}, "textAlign": "left",
             "fontWeight": "500", "minWidth": "130px"},
        ],
        style_header={
            "backgroundColor": "#f8f9fa", "fontWeight": "bold",
            "borderBottom": "2px solid #dee2e6", "fontSize": "0.8rem",
            "textAlign": "center",
        },
        style_data_conditional=[
            {"if": {"filter_query": '{equipamento} = "TOTAL DA PLANTA"'},
             "backgroundColor": "#e9ecef", "fontWeight": "bold",
             "borderTop": "2px solid #6c757d"},
            {"if": {"row_index": "odd"}, "backgroundColor": "#fafafa"},
        ],
    )
    return dbc.Card([dbc.CardBody(table)], className="shadow-sm")


def _render_monthly_debug(data: dict, equipment_ids: list[str],
                            year_months: list[str], months: list[int]) -> dbc.Card:
    monthly_rows = []
    for ym in year_months:
        month = int(ym.split("-")[1])
        m_act_h = sum(m.get("total_active_hours", 0.0)
                      for eq in equipment_ids if eq in data
                      for m in data[eq] if m.get("year_month") == ym)
        m_bd_min = sum(m.get("total_breakdown_minutes", 0.0)
                       for eq in equipment_ids if eq in data
                       for m in data[eq] if m.get("year_month") == ym)
        m_fail = sum(m.get("num_failures", 0)
                     for eq in equipment_ids if eq in data
                     for m in data[eq] if m.get("year_month") == ym)
        m_bd_h = m_bd_min / 60.0
        if m_fail > 0 and m_act_h > 0:
            m_mtbf = (m_act_h - m_bd_h) / m_fail
            m_mttr_min = m_bd_min / m_fail
            m_bd_rate = (m_bd_h / m_act_h) * 100
        elif m_act_h > 0:
            m_mtbf = m_act_h
            m_mttr_min = 0.0
            m_bd_rate = 0.0
        else:
            m_mtbf = m_mttr_min = m_bd_rate = None
        _y = ym.split("-")[0]
        # Year list (anos distintos) — sempre 1 ano em V2 (ano corrente)
        years_set = {ym2.split("-")[0] for ym2 in year_months}
        label = f"{_MN[month - 1]}/{_y[2:]}" if len(years_set) > 1 else _MN[month - 1]
        monthly_rows.append({
            "mes": label, "falhas": m_fail,
            "act_h": round(m_act_h, 2), "bd_h": round(m_bd_h, 2),
            "mtbf": round(m_mtbf, 1) if m_mtbf is not None else None,
            "mttr_min": round(m_mttr_min, 1) if m_mttr_min is not None else None,
            "bd_rate": round(m_bd_rate, 2) if m_bd_rate is not None else None,
        })

    valid_mtbf = [r["mtbf"] for r in monthly_rows if r["mtbf"] is not None]
    valid_mttr = [r["mttr_min"] for r in monthly_rows if r["mttr_min"] is not None]
    valid_bdr = [r["bd_rate"] for r in monthly_rows if r["bd_rate"] is not None]
    avg_mtbf = round(sum(valid_mtbf) / len(valid_mtbf), 1) if valid_mtbf else None
    avg_mttr = round(sum(valid_mttr) / len(valid_mttr), 1) if valid_mttr else None
    avg_bdr = round(sum(valid_bdr) / len(valid_bdr), 2) if valid_bdr else None

    header = html.Thead(html.Tr([
        html.Th("Mês", style={"textAlign": "center", "padding": "6px 10px",
                                "fontSize": "0.8rem"}),
        html.Th("Nº Falhas", style={"textAlign": "center", "padding": "6px 10px",
                                       "fontSize": "0.8rem"}),
        html.Th("Atividade (h)", style={"textAlign": "center", "padding": "6px 10px",
                                          "fontSize": "0.8rem"}),
        html.Th("Avaria (h)", style={"textAlign": "center", "padding": "6px 10px",
                                       "fontSize": "0.8rem"}),
        html.Th("MTBF mensal (h)", style={"textAlign": "center", "padding": "6px 10px",
                                            "fontSize": "0.8rem"}),
        html.Th("MTTR mensal (min)", style={"textAlign": "center", "padding": "6px 10px",
                                              "fontSize": "0.8rem"}),
        html.Th("Taxa Avaria (%)", style={"textAlign": "center", "padding": "6px 10px",
                                            "fontSize": "0.8rem"}),
    ], style={"backgroundColor": "#f8f9fa", "borderBottom": "2px solid #dee2e6"}))

    body = []
    for r in monthly_rows:
        body.append(html.Tr([
            _td(r["mes"], bold=True, align="left"),
            _td(str(r["falhas"])),
            _td(_fv(r["act_h"], 2)),
            _td(_fv(r["bd_h"], 2)),
            _td(_fv(r["mtbf"], 1)),
            _td(_fv(r["mttr_min"], 1)),
            _td(_fv(r["bd_rate"], 2)),
        ]))
    n = len(monthly_rows)
    body.append(html.Tr([
        _td(f"Média ({n} meses) → Cards topo", bold=True, bg="#fff3cd", align="left"),
        _td("—", bg="#fff3cd"), _td("—", bg="#fff3cd"), _td("—", bg="#fff3cd"),
        _td(_fv(avg_mtbf, 1), bold=True, bg="#fff3cd"),
        _td(_fv(avg_mttr, 1), bold=True, bg="#fff3cd"),
        _td(_fv(avg_bdr, 2),  bold=True, bg="#fff3cd"),
    ]))

    return dbc.Card([
        dbc.CardBody(
            dbc.Table([header, html.Tbody(body)],
                       bordered=True, hover=True, size="sm", className="mb-0"),
            style={"padding": "0.5rem"},
        )
    ], className="shadow-sm")


def _render_coverage(coverage: dict) -> dbc.Card:
    def _item(label, last_date, num_days, icon, color):
        return dbc.Col([
            html.Div([
                html.I(className=f"bi {icon} me-2",
                       style={"color": color, "fontSize": "1.1rem"}),
                html.Strong(label, className="me-2"),
                html.Span(
                    f"{num_days} dias  |  último: {last_date}" if last_date else "sem dados",
                    className="text-muted small",
                ),
            ], className="d-flex align-items-center py-1"),
        ], xs=12, md=6)

    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.I(className="bi bi-database-check me-2",
                       style={"color": "#0d6efd"}),
                html.Strong("Cobertura dos dados"),
            ], className="d-flex align-items-center mb-2"),
            dbc.Row([
                _item("ZPP Prod",
                       coverage.get("prod_last_date"),
                       coverage.get("prod_num_days", 0),
                       "bi-play-circle-fill", "#198754"),
                _item("ZPP Paradas",
                       coverage.get("paradas_last_date"),
                       coverage.get("paradas_num_days", 0),
                       "bi-exclamation-triangle-fill", "#dc3545"),
            ], className="g-0"),
        ], style={"padding": "0.75rem 1rem"}),
    ], className="shadow-sm mb-3 border-start border-primary border-3")


def _render_motivos(period_start: str, period_end: str) -> dbc.Card | html.P:
    if not period_start or not period_end:
        return html.P("Sem dados disponíveis.",
                       className="text-muted text-center py-3")
    try:
        ps = datetime.fromisoformat(period_start)
        pe = datetime.fromisoformat(period_end)
        motivos = aggregate_breakdown_by_cause(ps, pe)
    except Exception:
        logger.exception("KPI v2 data tab: aggregate_breakdown_by_cause falhou")
        motivos = []

    if not motivos:
        return html.P("Sem motivos registrados no período.",
                       className="text-muted text-center py-3")

    total_count = sum(r["count"] for r in motivos)
    total_min = sum(r["total_min"] for r in motivos)
    rows = []
    for r in motivos:
        rows.append({
            "motivo":    r["motivo"],
            "count":     r["count"],
            "pct_count": round((r["count"] / total_count * 100) if total_count else 0, 1),
            "total_min": r["total_min"],
            "pct_min":   round((r["total_min"] / total_min * 100) if total_min else 0, 1),
            "total_h":   r["total_h"],
        })
    rows.append({
        "motivo": "TOTAL", "count": total_count, "pct_count": 100.0,
        "total_min": round(total_min, 1), "pct_min": 100.0,
        "total_h": round(total_min / 60.0, 3),
    })

    table = dash_table.DataTable(
        columns=[
            {"name": "Motivo", "id": "motivo"},
            {"name": "Qtd. Paradas", "id": "count", "type": "numeric"},
            {"name": "% Qtd",   "id": "pct_count", "type": "numeric",
             "format": {"specifier": ".1f"}},
            {"name": "Tempo (min)", "id": "total_min", "type": "numeric",
             "format": {"specifier": ".1f"}},
            {"name": "% Tempo", "id": "pct_min", "type": "numeric",
             "format": {"specifier": ".1f"}},
            {"name": "Tempo (h)", "id": "total_h", "type": "numeric",
             "format": {"specifier": ".3f"}},
        ],
        data=rows, sort_action="native",
        style_table={"overflowX": "auto"},
        style_cell={
            "textAlign": "center", "padding": "8px 14px",
            "fontFamily": "inherit", "fontSize": "0.85rem",
            "borderBottom": "1px solid #dee2e6",
        },
        style_cell_conditional=[
            {"if": {"column_id": "motivo"}, "textAlign": "left",
             "fontWeight": "500", "minWidth": "100px"},
        ],
        style_header={
            "backgroundColor": "#f8f9fa", "fontWeight": "bold",
            "borderBottom": "2px solid #dee2e6",
            "fontSize": "0.8rem", "textAlign": "center",
        },
        style_data_conditional=[
            {"if": {"filter_query": '{motivo} = "TOTAL"'},
             "backgroundColor": "#e9ecef", "fontWeight": "bold",
             "borderTop": "2px solid #6c757d"},
            {"if": {"row_index": "odd"}, "backgroundColor": "#fafafa"},
        ],
    )
    return dbc.Card([dbc.CardBody(table)], className="shadow-sm")


# ============================================================================
# Registro
# ============================================================================

def register_kpi_report_v2_data_tab_callback(app: dash.Dash) -> None:
    """Popula a aba '📋 Dados' do indicators-v2 com layout V1 (Dados Brutos)."""

    @app.callback(
        Output("rd-v2-data-coverage", "children"),
        Output("rd-v2-data-monthly", "children"),
        Output("rd-v2-data-summary", "children"),
        Output("rd-v2-data-motivos", "children"),
        Output("rd-v2-data-table", "children"),
        Input("tabs-indicators-v2", "active_tab"),
        Input("store-v2-filters", "data"),
        prevent_initial_call=True,
    )
    def render_dados_v2(active_tab, filters):
        if active_tab != "tab-v2-data":
            raise dash.exceptions.PreventUpdate

        empty = html.P("Sem dados disponíveis para o período.",
                        className="text-muted text-center py-5")

        # Import lazy — evita ciclo entre indicators_v2_callbacks ↔ este módulo
        from src.callbacks_registers.indicators_v2_callbacks import _unpack_filters
        start, end, codes, equipment_filter, _year = _unpack_filters(filters)

        try:
            stored = _build_full_stored_data_v2(start, end, list(codes), equipment_filter)
        except Exception:
            logger.exception("KPI v2 data tab: _build_full_stored_data_v2 falhou")
            return [empty] * 5

        if not stored.get("has_data"):
            return [empty] * 5

        data = stored["data"]
        names = stored.get("names") or {}
        equipment_ids = stored.get("equipment_ids") or []
        months = stored.get("months") or []
        year_months = stored.get("year_months") or []

        try:
            rows, totals = _build_raw_table_internal(
                data, equipment_ids, names, months, year_months,
            )
        except Exception:
            logger.exception("KPI v2 data tab: _build_raw_table_internal falhou")
            return [empty] * 5

        if not rows:
            return [empty] * 5

        return (
            _render_coverage(stored.get("data_coverage") or {}),
            _render_monthly_debug(data, equipment_ids, year_months, months),
            _render_summary_cards(totals),
            _render_motivos(stored.get("period_start"), stored.get("period_end")),
            _render_equipment_table(rows, totals),
        )
