"""Renderização Plotly → PNG bytes com fallback gracioso (SP-13).

Camada 3 — isolada para que falha de kaleido/Chromium não derrube a geração do DOCX.
Usa `plotly.io.to_image` (kaleido v1 >= 1.0 conforme RV-05).

Origem: projeto SDD KPIReport (DS-02 / DS-05) — implementado em IM-03.
"""
from __future__ import annotations

import logging
from io import BytesIO

import plotly.graph_objects as go
import plotly.io as pio

logger = logging.getLogger(__name__)


class SunburstRenderError(Exception):
    """Reservada para futura evolução em que falha de imagem aborte a geração.

    Caminho atual nunca propaga ao chamador — `renderizar_sunburst_png` captura
    tudo e devolve placeholder.
    """


def renderizar_sunburst_png(
    fig: go.Figure,
    kpi_label: str,
    width: int = 900,
    height: int = 700,
    scale: int = 2,
) -> bytes:
    """Renderiza Plotly Figure como PNG via `pio.to_image` (kaleido v1).

    Em falha, devolve placeholder PNG cinza com texto "Sunburst {kpi_label} indisponível"
    e emite log WARNING (sem stack trace — SP-17 L5). Nunca lança ao chamador (BR-10).
    """
    try:
        return pio.to_image(fig, format="png", width=width, height=height, scale=scale)
    except Exception as exc:
        logger.warning(
            "Falha ao renderizar sunburst %s: %s",
            kpi_label, type(exc).__name__,
        )
        return _gerar_placeholder_png(kpi_label, width, height, scale)


def _gerar_placeholder_png(
    kpi_label: str,
    width: int,
    height: int,
    scale: int,
) -> bytes:
    """Gera PNG cinza com texto "Sunburst {kpi_label} indisponível" centralizado.

    Implementação via Pillow (DS-05): fundo `#CCCCCC` cinza neutro, texto preto centralizado.
    Dimensões idênticas ao sunburst real para preservar layout do template.

    Fallback do fallback (SP-13 / DS-03): se Pillow também falhar, devolve PNG 1×1
    transparente hardcoded — garante que `docxtpl.InlineImage` não quebre.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont

        # Aplica scale para resolução compatível com o sunburst real
        w = width * scale
        h = height * scale

        img = Image.new("RGB", (w, h), color="#CCCCCC")
        draw = ImageDraw.Draw(img)

        texto = f"Sunburst {kpi_label} indisponível"
        # Fonte: tenta DejaVuSans (instalada via fonts-liberation no Dockerfile), cai para default
        try:
            font_size = max(int(24 * scale), 12)
            font = ImageFont.truetype("DejaVuSans.ttf", font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

        # Centraliza texto
        bbox = draw.textbbox((0, 0), texto, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pos = ((w - tw) // 2, (h - th) // 2)
        draw.text(pos, texto, fill="#000000", font=font)

        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    except Exception as exc:
        logger.warning(
            "Falha ao gerar placeholder PNG para %s: %s — usando PNG 1×1 hardcoded",
            kpi_label, type(exc).__name__,
        )
        # PNG 1×1 transparente hardcoded — não quebra docxtpl.InlineImage
        return (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8"
            b"\x0f\x00\x00\x01\x01\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
