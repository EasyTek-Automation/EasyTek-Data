"""KPIReport-v2 — Bar chart builder (refactor RF-01..RF-03).

Helper centralizado pra gerar bar charts mensais/diários alinhados ao
paradigma visual do Indicators-V2 (barras + meta + tendência polinomial).

Usado por:
- `kpi_report_v2_layout.py` → entrega Plotly Figure pro `dcc.Graph` (HTML interativo).
- `kpi_report_v2_pdf.py` → entrega Figure pra `renderizar_sunburst_png` (kaleido PNG).

Anti-pattern proibido: este módulo **não conecta no MongoDB** e **não recalcula
KPIs**. Recebe arrays prontos e devolve `go.Figure`.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import plotly.graph_objects as go


_UNIT: dict[str, str] = {
    "mtbf":        "h",
    "mttr":        "min",
    "taxa_avaria": "%",
    "breakdown_rate": "%",
}

_COLOR: dict[str, str] = {
    "mtbf":           "#198754",
    "mttr":           "#0d6efd",
    "taxa_avaria":    "#dc3545",
    "breakdown_rate": "#dc3545",
}

_DIRECTION: dict[str, str] = {
    # 'higher' = subir é bom (verde se ≥ meta), 'lower' = descer é bom
    "mtbf":           "higher",
    "mttr":           "lower",
    "taxa_avaria":    "lower",
    "breakdown_rate": "lower",
}


def build_bar_figure(
    labels: list[str],
    values: list[Optional[float]],
    kpi: str,
    target: Optional[float] = None,
    title: str = "",
    highlight_idx: Optional[int] = None,
    height: int = 240,
    show_trend: bool = True,
    show_meta_line: bool = True,
) -> go.Figure:
    """Bar chart canônico do KPIReport-v2.

    Args:
        labels: Categorias do eixo X (ex: ['Jan', 'Fev', ...] ou ['15/05', '16/05', ...]).
        values: Valores correspondentes. None vira 0.
        kpi: 'mtbf' | 'mttr' | 'taxa_avaria' | 'breakdown_rate'.
        target: Linha horizontal de meta. None oculta.
        title: Título exibido no topo.
        highlight_idx: Índice (0-based) destacado em laranja escuro (mês/dia corrente).
        height: Altura px.
        show_trend: Desenha curva polinomial tracejada se len(values) ≥ 3.
        show_meta_line: Desenha hline em `target`.
    """
    safe_vals = [float(v) if isinstance(v, (int, float)) else 0.0 for v in values]
    unit = _UNIT.get(kpi, "")
    color = _COLOR.get(kpi, "#0d6efd")
    direction = _DIRECTION.get(kpi, "higher")

    # Cor das barras: se valor cumpre meta → verde/cor base; senão → cor desfavorável
    bar_colors: list[str] = []
    for i, v in enumerate(safe_vals):
        c = color
        if target is not None and v != 0:
            cumpre = (v >= target) if direction == "higher" else (v <= target)
            c = "#198754" if cumpre else "#dc3545"
        if highlight_idx is not None and i == highlight_idx:
            # destaca com borda mais escura via marcador opaco
            c = "#fd7e14"
        bar_colors.append(c)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels,
        y=safe_vals,
        marker=dict(color=bar_colors, line=dict(color="rgba(0,0,0,0.3)", width=1)),
        text=[f"{v:.1f}{unit}" if v else "" for v in safe_vals],
        textposition="outside",
        cliponaxis=False,
        hovertemplate=f"<b>%{{x}}</b><br>%{{y:.2f}}{unit}<extra></extra>",
        name="Valor",
        showlegend=False,
    ))

    # Curva de tendência polinomial
    if show_trend and len([v for v in safe_vals if v]) >= 3:
        try:
            x_idx = np.arange(len(safe_vals), dtype=float)
            deg = 2 if len(safe_vals) >= 5 else 1
            coefs = np.polyfit(x_idx, safe_vals, deg)
            fig.add_trace(go.Scatter(
                x=labels,
                y=np.polyval(coefs, x_idx).tolist(),
                mode="lines",
                line=dict(color="#212529", width=2, dash="dot"),
                name="Tendência",
                hovertemplate="Tendência: %{y:.2f}" + unit + "<extra></extra>",
                showlegend=False,
            ))
        except Exception:
            pass

    # Linha de meta
    if show_meta_line and target is not None:
        fig.add_hline(
            y=target,
            line=dict(color="#6c757d", width=2, dash="dash"),
            annotation_text=f"Meta {target:.1f}{unit}",
            annotation_position="top right",
            annotation_font=dict(size=10, color="#6c757d"),
        )

    # Range Y com headroom pra rótulos outside
    y_candidates = [max(safe_vals)] if safe_vals else [0]
    if target is not None:
        y_candidates.append(target)
    y_top = max(y_candidates) * 1.25 if max(y_candidates) > 0 else 1.0
    y_bottom = 0

    fig.update_layout(
        title=dict(text=title, font=dict(size=12)) if title else None,
        margin=dict(l=35, r=15, t=40 if title else 25, b=30),
        plot_bgcolor="white",
        paper_bgcolor="rgba(0,0,0,0)",
        height=height,
        yaxis=dict(gridcolor="#eee", range=[y_bottom, y_top]),
        xaxis=dict(type="category"),
        showlegend=False,
        bargap=0.25,
    )
    return fig
