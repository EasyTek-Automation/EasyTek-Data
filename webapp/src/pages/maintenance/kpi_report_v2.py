"""KPIReport-v2 — relatório de KPIs de manutenção redesenhado.

Rota `/maintenance/kpi-report-v2`. Apresentação drilldown sobre as mesmas BRs
do KPIReport v1 (janelas, escopo, top 5, metas, fuso, latência). 5 blocos
clicáveis em grid + comparação período-vs-período + multi-formato (HTML/PDF/DOCX).

SDD: `.dev-docs/projects/KPIReport-v2/` — IM-03 (esqueleto + layout).
"""
from __future__ import annotations

import base64
import os

import dash_bootstrap_components as dbc
from dash import dcc, html


# ============================================================================
# i18n — TRANS dict (chaves canônicas — SP-15)
# ============================================================================
TRANS: dict[str, dict[str, str]] = {
    "pt": {
        "page_title":             "Relatório de KPIs v2",
        "page_subtitle":          "Drilldown progressivo — clique em qualquer bloco para detalhar.",
        "beta_badge":             "BETA · Dados ao vivo",
        "beta_tooltip":           "Página em validação. Use a v1 (/maintenance/indicators) como referência canônica.",
        "block_1_title":          "Bloco 1 — KPIs do Mês (Planta)",
        "block_2_title":          "Bloco 2 — Top 5 Paradas do Mês",
        "block_3_title":          "Bloco 3 — KPIs Últimas 24h (Planta)",
        "block_4_title":          "Bloco 4 — Detalhamento por Equipamento",
        "block_5_title":          "Bloco 5 — Paradas das Últimas 24h",
        "block_toggle_label":     "Blocos visíveis:",
        "kpi_mtbf":               "MTBF",
        "kpi_mttr":               "MTTR",
        "kpi_breakdown_rate":     "Taxa de Avaria",
        "btn_export_pdf":         "Exportar PDF",
        "btn_export_docx":        "Exportar DOCX",
        "btn_share_link":         "Copiar Link",
        "btn_refresh":            "Atualizar",
        "compare_vs_prev_month":  "vs. mês anterior",
        "compare_vs_prev_24h":    "vs. 24h anteriores",
        "compare_na":             "n/d",
        "compare_new":            "novo",
        "compare_flat":           "estável",
        "drilldown_open":         "Ver Top 10",
        "drilldown_close":        "Fechar",
        "drilldown_title_b2":     "Top 10 Paradas do Mês",
        "drilldown_title_b5":     "Detalhe do Evento",
        "no_data":                "Sem dados no período",
        "loading":                "Carregando…",
        "share_toast_success":    "Link copiado para a área de transferência",
        "share_toast_error":      "Não foi possível copiar o link",
        "export_pending":         "Gerando…",
        "export_pending_slow":    "Gerando… (pode demorar)",
        "export_error":           "Falha ao gerar arquivo. Tente novamente.",
        "col_equipment":          "Equipamento",
        "col_cause":              "Causa",
        "col_datetime":           "Data/Hora",
        "col_duration":           "Duração (min)",
        "col_status":             "Status",
        "status_no_data":         "Sem dados",
        "target_label":           "Meta",
        "value_label":            "Valor",
    },
    "es": {
        "page_title":             "Informe de KPIs v2",
        "page_subtitle":          "Drilldown progresivo — haga clic en cualquier bloque para detallar.",
        "beta_badge":             "BETA · Datos en vivo",
        "beta_tooltip":           "Página en validación. Use la v1 (/maintenance/indicators) como referencia canónica.",
        "block_1_title":          "Bloque 1 — KPIs del Mes (Planta)",
        "block_2_title":          "Bloque 2 — Top 5 Paradas del Mes",
        "block_3_title":          "Bloque 3 — KPIs Últimas 24h (Planta)",
        "block_4_title":          "Bloque 4 — Detalle por Equipo",
        "block_5_title":          "Bloque 5 — Paradas de las Últimas 24h",
        "block_toggle_label":     "Bloques visibles:",
        "kpi_mtbf":               "MTBF",
        "kpi_mttr":               "MTTR",
        "kpi_breakdown_rate":     "Tasa de Avería",
        "btn_export_pdf":         "Exportar PDF",
        "btn_export_docx":        "Exportar DOCX",
        "btn_share_link":         "Copiar enlace",
        "btn_refresh":            "Actualizar",
        "compare_vs_prev_month":  "vs. mes anterior",
        "compare_vs_prev_24h":    "vs. 24h anteriores",
        "compare_na":             "n/d",
        "compare_new":            "nuevo",
        "compare_flat":           "estable",
        "drilldown_open":         "Ver Top 10",
        "drilldown_close":        "Cerrar",
        "drilldown_title_b2":     "Top 10 Paradas del Mes",
        "drilldown_title_b5":     "Detalle del Evento",
        "no_data":                "Sin datos en el período",
        "loading":                "Cargando…",
        "share_toast_success":    "Enlace copiado al portapapeles",
        "share_toast_error":      "No se pudo copiar el enlace",
        "export_pending":         "Generando…",
        "export_pending_slow":    "Generando… (puede tardar)",
        "export_error":           "Error al generar archivo. Reintente.",
        "col_equipment":          "Equipo",
        "col_cause":              "Causa",
        "col_datetime":           "Fecha/Hora",
        "col_duration":           "Duración (min)",
        "col_status":             "Estado",
        "status_no_data":         "Sin datos",
        "target_label":           "Meta",
        "value_label":            "Valor",
    },
    "en": {
        "page_title":             "KPI Report v2",
        "page_subtitle":          "Progressive drilldown — click any block to expand.",
        "beta_badge":             "BETA · Live data",
        "beta_tooltip":           "Page under validation. Use v1 (/maintenance/indicators) as the canonical reference.",
        "block_1_title":          "Block 1 — Monthly KPIs (Plant)",
        "block_2_title":          "Block 2 — Top 5 Monthly Breakdowns",
        "block_3_title":          "Block 3 — Last 24h KPIs (Plant)",
        "block_4_title":          "Block 4 — Detail by Equipment",
        "block_5_title":          "Block 5 — Last 24h Breakdowns",
        "block_toggle_label":     "Visible blocks:",
        "kpi_mtbf":               "MTBF",
        "kpi_mttr":               "MTTR",
        "kpi_breakdown_rate":     "Breakdown Rate",
        "btn_export_pdf":         "Export PDF",
        "btn_export_docx":        "Export DOCX",
        "btn_share_link":         "Copy Link",
        "btn_refresh":            "Refresh",
        "compare_vs_prev_month":  "vs. prev. month",
        "compare_vs_prev_24h":    "vs. prev. 24h",
        "compare_na":             "n/a",
        "compare_new":            "new",
        "compare_flat":           "flat",
        "drilldown_open":         "View Top 10",
        "drilldown_close":        "Close",
        "drilldown_title_b2":     "Top 10 Monthly Breakdowns",
        "drilldown_title_b5":     "Event Detail",
        "no_data":                "No data in period",
        "loading":                "Loading…",
        "share_toast_success":    "Link copied to clipboard",
        "share_toast_error":      "Could not copy link",
        "export_pending":         "Generating…",
        "export_pending_slow":    "Generating… (may take a while)",
        "export_error":           "Failed to generate file. Try again.",
        "col_equipment":          "Equipment",
        "col_cause":              "Cause",
        "col_datetime":           "Date/Time",
        "col_duration":           "Duration (min)",
        "col_status":             "Status",
        "status_no_data":         "No data",
        "target_label":           "Target",
        "value_label":            "Value",
    },
}


# Bandeiras inline reusadas do indicators-v2 (mantém coerência visual).
_FLAG_SVGS: dict[str, str] = {
    "pt": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 42">
        <rect width="60" height="42" fill="#009c3b"/>
        <polygon points="30,4 56,21 30,38 4,21" fill="#ffdf00"/>
        <circle cx="30" cy="21" r="8" fill="#002776"/>
    </svg>''',
    "es": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 42">
        <rect width="60" height="10.5" fill="#aa151b"/>
        <rect y="10.5" width="60" height="21" fill="#f1bf00"/>
        <rect y="31.5" width="60" height="10.5" fill="#aa151b"/>
    </svg>''',
    "en": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 42">
        <rect width="60" height="42" fill="#bd3d44"/>
        <rect y="6" width="60" height="6" fill="#fff"/>
        <rect y="18" width="60" height="6" fill="#fff"/>
        <rect y="30" width="60" height="6" fill="#fff"/>
        <rect y="0" width="60" height="6" fill="#bd3d44"/>
        <rect y="12" width="60" height="6" fill="#bd3d44"/>
        <rect y="24" width="60" height="6" fill="#bd3d44"/>
        <rect y="36" width="60" height="6" fill="#bd3d44"/>
        <rect width="24" height="22.5" fill="#192f5d"/>
    </svg>''',
}


def _is_enabled() -> bool:
    """Lê env `KPI_REPORT_V2_ENABLED`. Default `true`. False → layout placeholder."""
    return os.environ.get("KPI_REPORT_V2_ENABLED", "true").strip().lower() == "true"


def _lang_switcher() -> html.Div:
    """3 bandeiras SVG inline para troca de idioma — pattern alinhado a indicators-v2."""
    flags = [("pt", "Português"), ("es", "Español"), ("en", "English")]
    return html.Div(
        [
            html.Button(
                html.Img(
                    src="data:image/svg+xml;base64,"
                        + base64.b64encode(_FLAG_SVGS[code].encode()).decode(),
                    alt=title,
                    style={"width": "28px", "height": "20px", "borderRadius": "3px",
                           "boxShadow": "0 1px 3px rgba(0,0,0,0.2)"},
                ),
                id={"type": "kpi-v2-lang-btn", "lang": code},
                title=title,
                n_clicks=0,
                className="v2-lang-flag",
            )
            for code, title in flags
        ],
        className="d-flex align-items-center gap-2 v2-lang-switcher",
    )


def _beta_badge() -> html.Span:
    """Badge BETA pulsante (CSS em evocon_transitions.css)."""
    return html.Span(
        [
            html.I(className="bi bi-exclamation-triangle-fill me-2"),
            html.Span("BETA · Dados ao vivo", id="kpi-v2-i18n-beta-badge"),
        ],
        id="kpi-v2-beta-badge",
        className="v2-beta-badge ms-3 align-middle",
        title="Página em validação.",
    )


def _blocks_toggle_default() -> dict[str, bool]:
    """Padrão de visibilidade — todos os 5 blocos ligados."""
    return {str(i): True for i in range(1, 6)}


def _block_toggle_checkboxes() -> dbc.Checklist:
    """5 checkboxes pra ligar/desligar blocos. Persistência via store-kpi-v2-blocks-toggle."""
    return dbc.Checklist(
        id="kpi-v2-block-toggle",
        options=[
            {"label": "Bloco 1", "value": "1"},
            {"label": "Bloco 2", "value": "2"},
            {"label": "Bloco 3", "value": "3"},
            {"label": "Bloco 4", "value": "4"},
            {"label": "Bloco 5", "value": "5"},
        ],
        value=["1", "2", "3", "4", "5"],
        inline=True,
        switch=True,
        className="kpi-v2-block-toggle",
    )


def _stores() -> list[dcc.Store]:
    """5 stores de estado conforme DS-07."""
    return [
        dcc.Store(id="store-kpi-v2-lang", storage_type="local", data="pt"),
        dcc.Store(id="store-kpi-v2-blocks-toggle", storage_type="local",
                  data=_blocks_toggle_default()),
        dcc.Store(id="store-kpi-v2-data", storage_type="memory"),
        dcc.Store(id="store-kpi-v2-compare", storage_type="memory"),
        dcc.Store(id="store-kpi-v2-drilldown-ctx", storage_type="memory"),
    ]


def _footer_buttons() -> html.Div:
    """Botões de export (PDF/DOCX/link) + refresh. Habilitação controlada por C11."""
    return html.Div(
        [
            dbc.Button(
                [html.I(className="bi bi-arrow-clockwise me-2"), "Atualizar"],
                id="btn-kpi-v2-refresh",
                color="secondary",
                outline=True,
                size="sm",
                className="me-2",
            ),
            dbc.Button(
                [html.I(className="bi bi-filetype-pdf me-2"),
                 html.Span("Exportar PDF", id="kpi-v2-i18n-btn-pdf")],
                id="btn-kpi-v2-export-pdf",
                color="primary",
                size="sm",
                disabled=True,
                className="me-2",
            ),
            dbc.Button(
                [html.I(className="bi bi-file-earmark-word me-2"),
                 html.Span("Exportar DOCX", id="kpi-v2-i18n-btn-docx")],
                id="btn-kpi-v2-export-docx",
                color="secondary",
                size="sm",
                disabled=True,
                className="me-2",
            ),
            dbc.Button(
                [html.I(className="bi bi-link-45deg me-2"),
                 html.Span("Copiar Link", id="kpi-v2-i18n-btn-share")],
                id="btn-kpi-v2-share",
                color="info",
                outline=True,
                size="sm",
                disabled=True,
            ),
        ],
        className="d-flex align-items-center justify-content-end flex-wrap gap-2 mt-4",
    )


def _drilldown_modal() -> dbc.Modal:
    """Modal placeholder pra drilldown bloco 2/5. Content preenchido pelo C6."""
    return dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle(id="kpi-v2-drilldown-title")),
            dbc.ModalBody(id="kpi-v2-drilldown-body"),
            dbc.ModalFooter(
                dbc.Button(
                    "Fechar",
                    id={"type": "kpi-v2-drilldown-close", "index": "btn"},
                    color="secondary",
                    n_clicks=0,
                ),
            ),
        ],
        id="kpi-v2-drilldown-modal",
        is_open=False,
        size="xl",
        scrollable=True,
    )


def _disabled_layout() -> dbc.Container:
    """Render quando KPI_REPORT_V2_ENABLED=false — feature flag desligada (DS-10)."""
    return dbc.Container(
        [
            dbc.Alert(
                [
                    html.H4("KPI Report v2 desabilitado", className="alert-heading"),
                    html.P("A flag KPI_REPORT_V2_ENABLED está em false. "
                           "Use a v1 em /maintenance/indicators."),
                ],
                color="warning",
                className="mt-4",
            )
        ],
        fluid=True,
    )


def layout() -> dbc.Container:
    """Layout principal — header + toggles + grid placeholder + footer + stores + modal."""
    if not _is_enabled():
        return _disabled_layout()

    header_row = dbc.Row(
        [
            dbc.Col(
                [
                    html.Div(
                        [
                            html.H2(
                                "Relatório de KPIs v2",
                                id="kpi-v2-i18n-page-title",
                                className="mb-0",
                            ),
                            _beta_badge(),
                        ],
                        className="d-flex align-items-center flex-wrap mb-1",
                    ),
                    html.P(
                        "Drilldown progressivo — clique em qualquer bloco para detalhar.",
                        id="kpi-v2-i18n-page-subtitle",
                        className="text-muted mb-0",
                    ),
                ],
                md=8, xs=12,
            ),
            dbc.Col(
                _lang_switcher(),
                md=4, xs=12,
                className="d-flex align-items-center justify-content-md-end justify-content-start mt-3 mt-md-0",
            ),
        ],
        className="mb-3 align-items-start",
    )

    toggle_row = dbc.Row(
        [
            dbc.Col(
                [
                    html.Span("Blocos visíveis:",
                              id="kpi-v2-i18n-toggle-label",
                              className="me-3 fw-semibold"),
                    _block_toggle_checkboxes(),
                ],
                className="d-flex align-items-center flex-wrap gap-2",
            )
        ],
        className="mb-3",
    )

    # Container onde os blocos são renderizados pelo callback C3 (render_blocks).
    blocks_container = html.Div(
        [
            dbc.Spinner(
                html.Div(id="kpi-v2-blocks-container",
                         children=html.Div(className="text-center text-muted py-5",
                                           children="Carregando…")),
                color="primary",
                type="border",
            )
        ],
    )

    # Trigger de carga inicial — Interval com max_intervals=1.
    load_trigger = dcc.Interval(
        id="kpi-v2-load-once",
        interval=200,
        n_intervals=0,
        max_intervals=1,
    )

    # Downloads (PDF/DOCX) + clipboard helper.
    downloads = html.Div(
        [
            dcc.Download(id="download-kpi-v2-pdf"),
            dcc.Download(id="download-kpi-v2-docx"),
            dcc.Clipboard(id="kpi-v2-share-clipboard", target_id=None,
                          style={"display": "none"}),
            dcc.Location(id="kpi-v2-share-location", refresh=False),
        ]
    )

    # Toast de feedback (compartilhar link, erros de export).
    share_toast = dbc.Toast(
        id="kpi-v2-share-toast",
        header="KPI Report v2",
        is_open=False,
        dismissable=True,
        duration=4000,
        icon="info",
        style={"position": "fixed", "top": 66, "right": 10, "width": 350, "zIndex": 9999},
    )

    return dbc.Container(
        [
            header_row,
            toggle_row,
            load_trigger,
            blocks_container,
            _footer_buttons(),
            downloads,
            share_toast,
            _drilldown_modal(),
            *_stores(),
        ],
        fluid=True,
        className="py-3 kpi-v2-page",
    )
