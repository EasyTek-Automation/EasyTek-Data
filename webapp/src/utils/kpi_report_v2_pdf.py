"""KPIReport-v2 — geração de PDF nativo via reportlab (DS-04, IM-10).

Renderiza A4 retrato com layout análogo ao DOCX v1 (5 blocos) — recebe o dict
de `coletar_dados_relatorio(..., as_png=True)` e devolve bytes prontos para
`dcc.send_bytes`.

Anti-pattern proibido: este módulo **não conecta no MongoDB** e **não recalcula
KPIs**. Apenas formata dados que chegam prontos.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.pages.maintenance.kpi_report_v2 import TRANS
from src.utils.kpi_report_config import fmt_numero

logger = logging.getLogger(__name__)


# ============================================================================
# Estilos
# ============================================================================

def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "kpi-v2-title", parent=base["Heading1"],
            fontSize=18, leading=22, alignment=TA_CENTER,
            textColor=colors.HexColor("#0d6efd"),
            spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "kpi-v2-subtitle", parent=base["Normal"],
            fontSize=10, leading=12, alignment=TA_CENTER,
            textColor=colors.HexColor("#6c757d"),
            spaceAfter=12,
        ),
        "block_title": ParagraphStyle(
            "kpi-v2-block-title", parent=base["Heading2"],
            fontSize=13, leading=16,
            textColor=colors.HexColor("#212529"),
            spaceBefore=8, spaceAfter=4,
        ),
        "kpi_line": ParagraphStyle(
            "kpi-v2-kpi-line", parent=base["Normal"],
            fontSize=11, leading=14, alignment=TA_LEFT,
        ),
        "small": ParagraphStyle(
            "kpi-v2-small", parent=base["Normal"],
            fontSize=8, leading=10, textColor=colors.HexColor("#6c757d"),
        ),
        "footer": ParagraphStyle(
            "kpi-v2-footer", parent=base["Normal"],
            fontSize=7, leading=9, alignment=TA_CENTER,
            textColor=colors.HexColor("#adb5bd"),
        ),
    }


def _t(lang: str, key: str) -> str:
    table = TRANS.get(lang) or TRANS.get("pt", {})
    return table.get(key, TRANS.get("pt", {}).get(key, key))


def _fmt(v: Optional[float], casas: int = 1) -> str:
    return fmt_numero(v, casas=casas) if v is not None else "—"


# ============================================================================
# Builders por bloco
# ============================================================================

def _bloco_planta_flowables(block_id: int, dados: Optional[dict], lang: str,
                              titulo_key: str, styles: dict,
                              title_suffix: str = "") -> list:
    """Bloco 1 ou 3 — KPIs planta + bar charts. `title_suffix` BR-02b: ' — DD/MM/YYYY'."""
    full_title = _t(lang, titulo_key) + (title_suffix or "")
    out: list = [Paragraph(full_title, styles["block_title"])]
    if not dados:
        out.append(Paragraph(_t(lang, "no_data"), styles["kpi_line"]))
        return out

    kpis = dados.get("kpis_planta") or {}
    metas = dados.get("metas") or {}

    rows = [
        [
            Paragraph(f"<b>{_t(lang, 'kpi_mtbf')}</b>", styles["kpi_line"]),
            Paragraph(f"{_fmt(kpis.get('mtbf'))} h", styles["kpi_line"]),
            Paragraph(f"{_t(lang, 'target_label')}: {_fmt(metas.get('mtbf'))} h", styles["small"]),
        ],
        [
            Paragraph(f"<b>{_t(lang, 'kpi_mttr')}</b>", styles["kpi_line"]),
            Paragraph(f"{_fmt(kpis.get('mttr'))} min", styles["kpi_line"]),
            Paragraph(f"{_t(lang, 'target_label')}: {_fmt(metas.get('mttr'))} min", styles["small"]),
        ],
        [
            Paragraph(f"<b>{_t(lang, 'kpi_breakdown_rate')}</b>", styles["kpi_line"]),
            Paragraph(f"{_fmt(kpis.get('taxa_avaria'))} %", styles["kpi_line"]),
            Paragraph(f"{_t(lang, 'target_label')}: {_fmt(metas.get('taxa_avaria'))} %", styles["small"]),
        ],
    ]
    tbl = Table(rows, colWidths=[4 * cm, 4 * cm, 6 * cm])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1),
         [colors.whitesmoke, colors.HexColor("#f8f9fa")]),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dee2e6")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#adb5bd")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    out.append(tbl)

    # Bar charts (PNG via kaleido) — paradigma Indicators-V2 (refactor RF-03).
    # Aceita 2 caminhos:
    #   (a) `*_series` dict pronto (preferido) → gera Figure aqui via build_bar_figure
    #       e renderiza PNG via renderizar_sunburst_png (kaleido).
    #   (b) `sunburst_figures` legado (retrocompat) → embed direto se PNG bytes.
    series_key = "monthly_series" if block_id == 1 else "daily_series" if block_id == 3 else None
    series = dados.get(series_key) if series_key else None
    legacy_imgs = dados.get("sunburst_figures") or {}

    chart_cells = []
    for kpi_key in ("mtbf", "mttr", "taxa_avaria"):
        png_bytes: Optional[bytes] = None
        if series and isinstance(series, dict):
            labels = series.get("labels") or []
            values = series.get(kpi_key) or []
            highlight = series.get("current_idx")
            target = (metas or {}).get(kpi_key)
            if labels and values:
                try:
                    from src.utils.kpi_report_v2_bars import build_bar_figure
                    from src.utils.kpi_report_figures import renderizar_sunburst_png
                    # Fontes 3x maiores no PDF (rótulos pequenos demais no HTML
                    # ao serem rasterizados via kaleido em alta resolução).
                    fig = build_bar_figure(
                        labels=labels, values=values, kpi=kpi_key,
                        target=target, title="",
                        highlight_idx=highlight, height=260,
                        bar_text_size=36, meta_text_size=30,
                        axis_tick_size=33,
                    )
                    # renderizar_sunburst_png aceita qualquer Plotly Figure (kaleido)
                    png_bytes = renderizar_sunburst_png(fig, kpi_key.upper())
                except Exception:
                    logger.exception(
                        "kpi-v2 pdf bloco %s: falha bar PNG %s", block_id, kpi_key,
                    )
        if png_bytes is None:
            # Fallback retrocompat: tenta legacy PNG
            cand = legacy_imgs.get(kpi_key)
            if isinstance(cand, (bytes, bytearray)):
                png_bytes = bytes(cand)

        if isinstance(png_bytes, (bytes, bytearray)):
            try:
                img = Image(io.BytesIO(bytes(png_bytes)), width=5.5 * cm,
                             height=4.4 * cm, kind="proportional")
                chart_cells.append(img)
            except Exception:
                logger.exception("kpi-v2 pdf bloco %s: falha embed PNG %s",
                                  block_id, kpi_key)
                chart_cells.append(Paragraph("—", styles["small"]))
        else:
            chart_cells.append(Paragraph("—", styles["small"]))

    out.append(Spacer(1, 4 * mm))
    chart_tbl = Table(
        [
            [Paragraph(_t(lang, k), styles["small"]) for k in
             ("kpi_mtbf", "kpi_mttr", "kpi_breakdown_rate")],
            chart_cells,
        ],
        colWidths=[5.5 * cm, 5.5 * cm, 5.5 * cm],
    )
    chart_tbl.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    out.append(chart_tbl)
    out.append(Spacer(1, 6 * mm))
    return out


def _bloco_paradas_flowables(block_id: int, dados: Optional[dict], lang: str,
                               titulo_key: str, styles: dict, top_n: Optional[int],
                               title_suffix: str = "") -> list:
    """Bloco 2 ou 5 — Top paradas. `title_suffix` BR-02b: ' — DD/MM/YYYY'."""
    full_title = _t(lang, titulo_key) + (title_suffix or "")
    out: list = [Paragraph(full_title, styles["block_title"])]
    if not dados or dados.get("vazio") or not dados.get("paradas"):
        out.append(Paragraph(_t(lang, "no_data"), styles["kpi_line"]))
        return out

    paradas = dados["paradas"]
    if top_n:
        paradas = paradas[:top_n]

    header = [
        Paragraph("#", styles["small"]),
        Paragraph(_t(lang, "col_equipment"), styles["small"]),
        Paragraph(_t(lang, "col_cause"), styles["small"]),
        Paragraph(_t(lang, "col_datetime"), styles["small"]),
        Paragraph(_t(lang, "col_duration"), styles["small"]),
    ]
    rows = [header]
    for p in paradas:
        rows.append([
            Paragraph(str(p.get("posicao", "")), styles["small"]),
            Paragraph(str(p.get("equipamento", "")), styles["small"]),
            Paragraph(f"{p.get('causa', '')} — {p.get('descricao', '')}",
                      styles["small"]),
            Paragraph(str(p.get("data_hora", "")), styles["small"]),
            Paragraph(str(p.get("duracao_min", "")), styles["small"]),
        ])

    tbl = Table(rows, colWidths=[0.8 * cm, 3.5 * cm, 6 * cm, 3.5 * cm, 2 * cm],
                  repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d6efd")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.whitesmoke, colors.HexColor("#f8f9fa")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dee2e6")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#adb5bd")),
    ]))
    out.append(tbl)
    out.append(Spacer(1, 6 * mm))
    return out


def _bloco4_flowables(dados: Optional[dict], lang: str, styles: dict) -> list:
    """Bloco 4 — tabela Detalhamento por equipamento."""
    out: list = [Paragraph(_t(lang, "block_4_title"), styles["block_title"])]
    if not dados or dados.get("vazio") or not dados.get("linhas"):
        out.append(Paragraph(_t(lang, "no_data"), styles["kpi_line"]))
        return out

    header = [
        Paragraph(_t(lang, "col_equipment"), styles["small"]),
        Paragraph(_t(lang, "kpi_mtbf"), styles["small"]),
        Paragraph(_t(lang, "kpi_mttr"), styles["small"]),
        Paragraph(_t(lang, "kpi_breakdown_rate"), styles["small"]),
        Paragraph(_t(lang, "col_status"), styles["small"]),
    ]
    rows = [header]
    for r in dados.get("linhas", []):
        sem_dados = (
            r.get("mtbf") is None and r.get("mttr") is None and r.get("taxa_avaria") is None
        )
        rows.append([
            Paragraph(str(r.get("equipamento", "")), styles["small"]),
            Paragraph(_fmt(r.get("mtbf")), styles["small"]),
            Paragraph(_fmt(r.get("mttr")), styles["small"]),
            Paragraph(_fmt(r.get("taxa_avaria")), styles["small"]),
            Paragraph(_t(lang, "status_no_data") if sem_dados else "OK",
                       styles["small"]),
        ])

    total = dados.get("total") or {}
    if total:
        rows.append([
            Paragraph(f"<b>{total.get('equipamento', 'TOTAL')}</b>", styles["small"]),
            Paragraph(f"<b>{_fmt(total.get('mtbf'))}</b>", styles["small"]),
            Paragraph(f"<b>{_fmt(total.get('mttr'))}</b>", styles["small"]),
            Paragraph(f"<b>{_fmt(total.get('taxa_avaria'))}</b>", styles["small"]),
            Paragraph("—", styles["small"]),
        ])

    tbl = Table(rows, colWidths=[4 * cm, 2.5 * cm, 2.5 * cm, 3.5 * cm, 3.5 * cm],
                  repeatRows=1)
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d6efd")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2),
         [colors.whitesmoke, colors.HexColor("#f8f9fa")]),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f1f3f5")),
        ("LINEABOVE", (0, -1), (-1, -1), 1.2, colors.HexColor("#adb5bd")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dee2e6")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#adb5bd")),
    ])
    tbl.setStyle(style)
    out.append(tbl)
    out.append(Spacer(1, 6 * mm))
    return out


# ============================================================================
# Página footer
# ============================================================================

def _on_page(canvas: rl_canvas.Canvas, doc: SimpleDocTemplate) -> None:
    """Footer com número de página + 'Gerado por KPIReport v2'."""
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#adb5bd"))
    width, _ = A4
    canvas.drawCentredString(
        width / 2.0, 1.0 * cm,
        f"Gerado por KPIReport v2 — página {canvas.getPageNumber()}",
    )
    canvas.restoreState()


# ============================================================================
# Entry point
# ============================================================================

def gerar_pdf(dados: dict, blocos_ativos: set[int] | list[int],
                lang: str = "pt",
                dia_24h_label: str = "") -> bytes:
    """Renderiza PDF A4 retrato — devolve bytes.

    Args:
        dados: dict retornado por `coletar_dados_relatorio(..., as_png=True)`.
        blocos_ativos: subset de {1, 2, 3, 4, 5}.
        lang: 'pt' | 'es' | 'en'.
        dia_24h_label: BR-02b — quando ≠ '' (ex: '15/05/2026'), anexa ao título
            dos blocos 3 e 5 indicando o dia escolhido pelo usuário.

    Raises:
        ValueError: se `dados` for inválido (nenhum bloco renderizável).
    """
    if not isinstance(dados, dict):
        raise ValueError("dados deve ser dict")

    active = {int(b) for b in (blocos_ativos or [])}
    if not active:
        active = {1, 2, 3, 4, 5}

    suffix_24h = f" — {dia_24h_label}" if dia_24h_label else ""

    styles = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title=_t(lang, "page_title"),
    )

    story: list = []

    # Cabeçalho
    story.append(Paragraph(_t(lang, "page_title"), styles["title"]))
    periodo_label = ""
    periodo = dados.get("periodo") or {}
    if isinstance(periodo, dict):
        periodo_label = periodo.get("rotulo", "")
    if periodo_label:
        story.append(Paragraph(periodo_label, styles["subtitle"]))
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    story.append(Paragraph(f"<i>{timestamp}</i>", styles["subtitle"]))

    if 1 in active:
        story.extend(_bloco_planta_flowables(
            1, dados.get("bloco1"), lang, "block_1_title", styles,
        ))
    if 2 in active:
        story.extend(_bloco_paradas_flowables(
            2, dados.get("bloco2"), lang, "block_2_title", styles, top_n=5,
        ))
    if 3 in active:
        story.extend(_bloco_planta_flowables(
            3, dados.get("bloco3"), lang, "block_3_title", styles,
            title_suffix=suffix_24h,
        ))
    if 4 in active:
        story.append(PageBreak())
        story.extend(_bloco4_flowables(dados.get("bloco4"), lang, styles))
    if 5 in active:
        story.extend(_bloco_paradas_flowables(
            5, dados.get("bloco5"), lang, "block_5_title", styles, top_n=None,
            title_suffix=suffix_24h,
        ))

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()
