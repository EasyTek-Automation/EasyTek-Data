"""KPIReport-v2 — componentes HTML reusáveis dos 5 blocos (DS-03, IM-05).

Cada `build_blocoN_html` recebe o dict do bloco (mesmo contrato que
`kpi_report_data._build_*` produz, mas serializável JSON — sunbursts viram
`plotly.graph_objects.Figure.to_dict()`) + `compare` opcional + `lang`.

Funções são puras (sem I/O), retornam `dbc.Card`. Modal de drilldown é construído
por `build_drilldown_modal(top10, lang)`.
"""
from __future__ import annotations

from typing import Any, Optional

import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html

from src.pages.maintenance.kpi_report_v2 import TRANS
from src.utils.kpi_report_config import fmt_numero
from src.utils.kpi_report_v2_bars import build_bar_figure


# ============================================================================
# Helpers internos
# ============================================================================

def _t(lang: str, key: str) -> str:
    """Lookup i18n com fallback PT e fallback exibindo a própria chave."""
    table = TRANS.get(lang) or TRANS.get("pt", {})
    return table.get(key, TRANS.get("pt", {}).get(key, key))


_KPI_UNIT: dict[str, str] = {
    "mtbf":        "h",
    "mttr":        "min",
    "taxa_avaria": "%",
}

# Mapeia chaves do bloco interno (taxa_avaria) → chave SDD/compare (breakdown_rate).
# `compare` usa nomes do SDD; KPI dict do bloco usa nomes legados (taxa_avaria).
_KPI_TO_COMPARE_KEY: dict[str, str] = {
    "mtbf":        "mtbf",
    "mttr":        "mttr",
    "taxa_avaria": "breakdown_rate",
}


# ============================================================================
# Badges
# ============================================================================

def render_kpi_badge(value: Optional[float], target: Optional[float],
                      kpi: str, color: Optional[str], lang: str) -> html.Span:
    """Badge com valor + meta inline. Cor ditada por `get_kpi_color` (v1)."""
    unit = _KPI_UNIT.get(kpi, "")
    val_str = fmt_numero(value, casas=1) if value is not None else "—"
    target_str = fmt_numero(target, casas=1) if target is not None else "—"

    swatch_color = color or "#6c757d"
    return html.Span(
        [
            html.Span(
                "",
                className="me-1",
                style={
                    "display": "inline-block",
                    "width": "10px", "height": "10px",
                    "borderRadius": "50%",
                    "backgroundColor": swatch_color,
                    "verticalAlign": "middle",
                },
            ),
            html.Strong(f"{val_str} {unit}".strip(),
                        className="me-1",
                        style={"fontSize": "1.05rem"}),
            html.Span(
                f"({_t(lang, 'target_label')}: {target_str} {unit})".strip(),
                className="text-muted",
                style={"fontSize": "0.78rem"},
            ),
        ],
        className="kpi-v2-kpi-badge d-inline-flex align-items-center",
    )


def render_compare_badge(compare_entry: Optional[dict], lang: str) -> Optional[html.Span]:
    """Badge ∆ vs período anterior. Cores: verde favorável / vermelho desfavorável / cinza neutro.

    `compare_entry` é a saída de `kpi_report_v2_compare.compute_period_delta`.
    Retorna `None` se compare_entry for None (não renderiza badge).
    """
    if compare_entry is None:
        return None

    direction = compare_entry.get("direction", "na")
    favorable = compare_entry.get("favorable")
    delta_abs = compare_entry.get("delta_abs")
    delta_pct = compare_entry.get("delta_pct")
    is_new = compare_entry.get("is_new", False)

    if direction == "na":
        label = _t(lang, "compare_na")
        bg, fg, arrow = "#e9ecef", "#6c757d", ""
    elif direction == "flat":
        label = _t(lang, "compare_flat")
        bg, fg, arrow = "#e9ecef", "#495057", "→"
    else:
        arrow = "↑" if direction == "up" else "↓"
        if favorable is True:
            bg, fg = "#d1f7e0", "#0a7d34"
        elif favorable is False:
            bg, fg = "#fde2e2", "#a72333"
        else:
            bg, fg = "#e9ecef", "#495057"

        if is_new:
            label = _t(lang, "compare_new")
        elif delta_pct is None:
            # protege contra é direction != na mas pct None (caso anterior=0 e atual=0 caiu antes)
            label = fmt_numero(delta_abs, casas=1) if delta_abs is not None else "—"
        else:
            sign = "+" if delta_pct > 0 else ""
            label = f"{sign}{fmt_numero(delta_pct, casas=1)}%"

    return html.Span(
        f"{arrow} {label}".strip(),
        className="kpi-v2-compare-badge ms-2",
        style={
            "backgroundColor": bg,
            "color": fg,
            "padding": "2px 8px",
            "borderRadius": "10px",
            "fontSize": "0.72rem",
            "fontWeight": "600",
            "whiteSpace": "nowrap",
        },
        title=_t(lang, "compare_vs_prev_month"),
    )


# ============================================================================
# Bloco placeholder (sem dados)
# ============================================================================

def _placeholder_card(block_id: int, title: str, lang: str) -> dbc.Card:
    return dbc.Card(
        [
            dbc.CardHeader(html.H5(title, className="mb-0")),
            dbc.CardBody(
                html.Div(
                    [
                        html.I(className="bi bi-database-x text-muted",
                               style={"fontSize": "2rem"}),
                        html.P(_t(lang, "no_data"),
                               className="text-muted mt-2 mb-0"),
                    ],
                    className="text-center py-4",
                ),
            ),
        ],
        id=f"kpi-v2-card-block-{block_id}",
        className="h-100 kpi-v2-block-card",
    )


# ============================================================================
# Blocos 1 e 3 — KPIs planta + sunbursts
# ============================================================================

def _build_kpi_planta_card(block_id: int, title_key: str,
                            dados: dict, compare: Optional[dict],
                            lang: str,
                            compare_label_key: str) -> dbc.Card:
    """Lógica compartilhada dos blocos 1 e 3 (mês e 24h)."""
    title = _t(lang, title_key)
    if not dados or not isinstance(dados, dict):
        return _placeholder_card(block_id, title, lang)

    kpis = dados.get("kpis_planta") or {}
    metas = dados.get("metas") or {}
    cores = dados.get("cores_kpis") or {}
    # Refactor RF: prefere `monthly_series` (bloco 1) / `daily_series` (bloco 3).
    # Fallback pra `sunburst_figures` legado caso esteja presente (retrocompat).
    series_key = "monthly_series" if block_id == 1 else "daily_series" if block_id == 3 else None
    series = dados.get(series_key) if series_key else None

    # 3 KPIs (MTBF / MTTR / Taxa Avaria) — header inalterado, badge ∆ continua
    kpi_rows = []
    for kpi_key, label_key in [("mtbf", "kpi_mtbf"),
                                ("mttr", "kpi_mttr"),
                                ("taxa_avaria", "kpi_breakdown_rate")]:
        compare_entry = None
        if compare:
            compare_entry = compare.get(_KPI_TO_COMPARE_KEY.get(kpi_key, kpi_key))
        kpi_rows.append(
            html.Div(
                [
                    html.Div(
                        _t(lang, label_key),
                        className="text-muted fw-semibold",
                        style={"fontSize": "0.72rem", "textTransform": "uppercase",
                               "letterSpacing": "0.5px"},
                    ),
                    html.Div(
                        [
                            render_kpi_badge(
                                kpis.get(kpi_key),
                                metas.get(kpi_key),
                                kpi_key,
                                cores.get(kpi_key),
                                lang,
                            ),
                            render_compare_badge(compare_entry, lang) or html.Span(),
                        ],
                        className="d-flex align-items-center flex-wrap",
                    ),
                ],
                className="mb-2",
            )
        )

    # Bar charts (3 colunas) — paradigma Indicators-V2 (RF-01/RF-02).
    chart_cols = []
    for kpi_key, label_key in [("mtbf", "kpi_mtbf"),
                                ("mttr", "kpi_mttr"),
                                ("taxa_avaria", "kpi_breakdown_rate")]:
        if series and isinstance(series, dict):
            labels = series.get("labels") or []
            values = series.get(kpi_key) or []
            highlight = series.get("current_idx")
            target = metas.get(kpi_key)
            if labels and values:
                fig = build_bar_figure(
                    labels=labels, values=values, kpi=kpi_key,
                    target=target, title="",
                    highlight_idx=highlight, height=220,
                )
                content = dcc.Graph(
                    figure=fig,
                    config={"displayModeBar": False, "staticPlot": False,
                            "responsive": True},
                    style={"height": "220px", "width": "100%"},
                )
            else:
                content = html.Div(
                    _t(lang, "no_data"),
                    className="text-muted text-center small py-3",
                )
        else:
            content = html.Div(
                _t(lang, "no_data"),
                className="text-muted text-center small py-3",
            )

        chart_cols.append(
            dbc.Col(
                [
                    html.Div(_t(lang, label_key),
                             className="text-center text-muted small mb-1"),
                    content,
                ],
                md=4, xs=12,
            )
        )

    return dbc.Card(
        [
            dbc.CardHeader(
                html.Div(
                    [
                        html.H5(title, className="mb-0"),
                        html.Small(_t(lang, compare_label_key),
                                   className="text-muted"),
                    ],
                    className="d-flex justify-content-between align-items-center flex-wrap",
                ),
            ),
            dbc.CardBody(
                [
                    *kpi_rows,
                    html.Hr(),
                    dbc.Row(chart_cols, className="g-2"),
                ],
            ),
        ],
        id=f"kpi-v2-card-block-{block_id}",
        className="h-100 kpi-v2-block-card",
    )


def build_bloco1_html(dados: dict, compare: Optional[dict], lang: str) -> dbc.Card:
    """Bloco 1 — KPIs do mês corrente + sunbursts + ∆ vs mês anterior."""
    return _build_kpi_planta_card(1, "block_1_title", dados, compare, lang,
                                    "compare_vs_prev_month")


def build_bloco3_html(dados: dict, compare: Optional[dict], lang: str) -> dbc.Card:
    """Bloco 3 — KPIs últimas 24h + sunbursts + ∆ vs 24h anteriores."""
    return _build_kpi_planta_card(3, "block_3_title", dados, compare, lang,
                                    "compare_vs_prev_24h")


# ============================================================================
# Blocos 2 e 5 — Top paradas
# ============================================================================

def _build_paradas_table(paradas: list[dict], lang: str,
                          row_clickable: bool = False) -> html.Table:
    """Tabela leve (sem dash_table) — controle visual fino + IDs por linha."""
    if not paradas:
        return html.Div(_t(lang, "no_data"),
                        className="text-muted text-center py-3")

    header = html.Thead(
        html.Tr([
            html.Th("#", style={"width": "3rem"}),
            html.Th(_t(lang, "col_equipment")),
            html.Th(_t(lang, "col_cause")),
            html.Th(_t(lang, "col_datetime")),
            html.Th(_t(lang, "col_duration"), className="text-end"),
        ]),
    )

    rows = []
    for p in paradas:
        row_props: dict[str, Any] = {"className": ""}
        if row_clickable:
            row_props["id"] = {"type": "kpi-v2-row-trigger", "block": 5,
                                "idx": p.get("posicao", 0)}
            row_props["n_clicks"] = 0
            row_props["style"] = {"cursor": "pointer"}
            row_props["className"] = "kpi-v2-row-clickable"
        rows.append(
            html.Tr(
                [
                    html.Td(p.get("posicao", "")),
                    html.Td(p.get("equipamento", "")),
                    html.Td([
                        html.Span(p.get("causa", ""), className="me-1 fw-semibold"),
                        html.Small(p.get("descricao", ""), className="text-muted"),
                    ]),
                    html.Td(p.get("data_hora", "")),
                    html.Td(p.get("duracao_min", ""), className="text-end fw-semibold"),
                ],
                **row_props,
            )
        )

    return html.Table(
        [header, html.Tbody(rows)],
        className="table table-sm table-hover mb-0 kpi-v2-paradas-table",
    )


def build_bloco2_html(dados: dict, lang: str) -> dbc.Card:
    """Bloco 2 — Top 5 paradas do mês + botão drilldown."""
    title = _t(lang, "block_2_title")
    if not dados or not isinstance(dados, dict):
        return _placeholder_card(2, title, lang)

    paradas = dados.get("paradas") or []
    drilldown_btn = dbc.Button(
        [html.I(className="bi bi-zoom-in me-1"),
         html.Span(_t(lang, "drilldown_open"),
                   id="kpi-v2-i18n-drilldown-open-b2")],
        id={"type": "kpi-v2-drilldown-trigger", "block": 2},
        color="link",
        size="sm",
        className="text-decoration-none p-0",
        n_clicks=0,
    )
    return dbc.Card(
        [
            dbc.CardHeader(
                html.Div(
                    [html.H5(title, className="mb-0"), drilldown_btn],
                    className="d-flex justify-content-between align-items-center",
                ),
            ),
            dbc.CardBody(_build_paradas_table(paradas, lang, row_clickable=False)),
        ],
        id="kpi-v2-card-block-2",
        className="h-100 kpi-v2-block-card",
    )


def build_bloco5_html(dados: dict, lang: str) -> dbc.Card:
    """Bloco 5 — Todas paradas das 24h. Linhas clicáveis → modal de detalhe."""
    title = _t(lang, "block_5_title")
    if not dados or not isinstance(dados, dict):
        return _placeholder_card(5, title, lang)

    paradas = dados.get("paradas") or []
    return dbc.Card(
        [
            dbc.CardHeader(html.H5(title, className="mb-0")),
            dbc.CardBody(_build_paradas_table(paradas, lang, row_clickable=True)),
        ],
        id="kpi-v2-card-block-5",
        className="h-100 kpi-v2-block-card",
    )


# ============================================================================
# Bloco 4 — Detalhamento por equipamento
# ============================================================================

def build_bloco4_html(dados: dict, lang: str) -> dbc.Card:
    """Bloco 4 — DataTable detalhada com cores por meta."""
    title = _t(lang, "block_4_title")
    if not dados or not isinstance(dados, dict):
        return _placeholder_card(4, title, lang)

    linhas = dados.get("linhas") or []
    total = dados.get("total") or {}
    if not linhas:
        return _placeholder_card(4, title, lang)

    def _val(row, k):
        v = row.get(k)
        return fmt_numero(v, casas=1) if isinstance(v, (int, float)) else (v or "—")

    columns = [
        {"name": _t(lang, "col_equipment"), "id": "equipamento"},
        {"name": _t(lang, "kpi_mtbf"), "id": "mtbf"},
        {"name": _t(lang, "kpi_mttr"), "id": "mttr"},
        {"name": _t(lang, "kpi_breakdown_rate"), "id": "taxa_avaria"},
        {"name": _t(lang, "col_status"), "id": "status"},
    ]

    data_rows = []
    style_data_conditional = []
    for idx, r in enumerate(linhas):
        row_id = r.get("equipamento") or f"row-{idx}"
        sem_dados = (
            r.get("mtbf") is None and r.get("mttr") is None and r.get("taxa_avaria") is None
        )
        data_rows.append({
            "equipamento": r.get("equipamento", ""),
            "mtbf": _val(r, "mtbf"),
            "mttr": _val(r, "mttr"),
            "taxa_avaria": _val(r, "taxa_avaria"),
            "status": _t(lang, "status_no_data") if sem_dados else "OK",
            "_id": row_id,
        })
        for col_id, cor_key in [("mtbf", "cor_mtbf"),
                                ("mttr", "cor_mttr"),
                                ("taxa_avaria", "cor_taxa_avaria")]:
            cor = r.get(cor_key)
            if cor:
                style_data_conditional.append({
                    "if": {"row_index": idx, "column_id": col_id},
                    "color": cor,
                    "fontWeight": "600",
                })

    # Linha de total (planta)
    if total:
        data_rows.append({
            "equipamento": total.get("equipamento", "TOTAL"),
            "mtbf": _val(total, "mtbf"),
            "mttr": _val(total, "mttr"),
            "taxa_avaria": _val(total, "taxa_avaria"),
            "status": "—",
            "_id": "row-total",
        })
        style_data_conditional.append({
            "if": {"row_index": len(linhas)},
            "backgroundColor": "#f8f9fa",
            "fontWeight": "700",
            "borderTop": "2px solid #adb5bd",
        })

    table = dash_table.DataTable(
        id="kpi-v2-block4-datatable",
        columns=columns,
        data=data_rows,
        style_cell={"fontSize": "0.85rem", "padding": "0.4rem 0.6rem"},
        style_header={"backgroundColor": "#f1f3f5", "fontWeight": "700"},
        style_data_conditional=style_data_conditional,
        page_size=20,
        sort_action="native",
    )

    return dbc.Card(
        [
            dbc.CardHeader(html.H5(title, className="mb-0")),
            dbc.CardBody(table, style={"overflowX": "auto"}),
        ],
        id="kpi-v2-card-block-4",
        className="h-100 kpi-v2-block-card",
    )


# ============================================================================
# Modal de drilldown
# ============================================================================

def build_drilldown_modal_body(block: int, paradas: list[dict],
                                 lang: str) -> html.Div:
    """Conteúdo do modal de drilldown — bloco 2 (Top 10) ou bloco 5 (detalhe linha)."""
    if not paradas:
        return html.Div(_t(lang, "no_data"),
                         className="text-muted text-center py-3")

    if block == 2:
        # Top 10 paradas — tabela completa
        return html.Div(_build_paradas_table(paradas, lang, row_clickable=False))

    # Block 5 — esperado 1 evento (paradas[0]) com todos os campos
    evt = paradas[0] if isinstance(paradas, list) else paradas
    if not isinstance(evt, dict):
        return html.Div(_t(lang, "no_data"),
                         className="text-muted text-center py-3")

    field_rows = []
    for k_label, val in [
        (_t(lang, "col_equipment"), evt.get("equipamento", "—")),
        (_t(lang, "col_cause"), f"{evt.get('causa', '')} — {evt.get('descricao', '')}"),
        (_t(lang, "col_datetime"), evt.get("data_hora", "—")),
        (_t(lang, "col_duration"), evt.get("duracao_min", "—")),
    ]:
        field_rows.append(
            html.Tr([
                html.Th(k_label, style={"width": "28%"}),
                html.Td(val),
            ])
        )

    return html.Div(html.Table(html.Tbody(field_rows),
                                className="table table-sm mb-0"))


# ============================================================================
# Render orquestrado
# ============================================================================

def render_all_blocks(dados: dict, compare: Optional[dict],
                       lang: str, toggle: Optional[dict] = None) -> html.Div:
    """Monta grid 2x3 (md) / 1x5 (xs) com blocos ativos. `toggle` filtra visibilidade."""
    active = toggle or {str(i): True for i in range(1, 6)}

    cards = []
    for n, builder in [
        (1, lambda: build_bloco1_html((dados or {}).get("bloco1") or {},
                                       (compare or {}).get("mes"), lang)),
        (2, lambda: build_bloco2_html((dados or {}).get("bloco2") or {}, lang)),
        (3, lambda: build_bloco3_html((dados or {}).get("bloco3") or {},
                                       (compare or {}).get("24h"), lang)),
        (4, lambda: build_bloco4_html((dados or {}).get("bloco4") or {}, lang)),
        (5, lambda: build_bloco5_html((dados or {}).get("bloco5") or {}, lang)),
    ]:
        if not active.get(str(n), True):
            continue
        cards.append(dbc.Col(builder(), md=6, xs=12, className="mb-3"))

    if not cards:
        return html.Div(
            _t(lang, "no_data"),
            className="text-center text-muted py-5",
        )

    return dbc.Row(cards, className="g-3")
