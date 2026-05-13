"""Testes unitários de `utils/kpi_report_figures.py` — camada 3 (renderização).

Cobertura:
- SP-13 caminho feliz (Plotly figure válida → PNG real)
- SP-13 fallback (kaleido falha → placeholder PNG válido)
- SP-13 placeholder direto via Pillow

IM-06 do projeto SDD KPIReport.
"""
from __future__ import annotations

from unittest.mock import patch

import plotly.graph_objects as go
import pytest

from src.utils.kpi_report_figures import (
    SunburstRenderError,
    _gerar_placeholder_png,
    renderizar_sunburst_png,
)


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class TestRenderizarSunburstPng:
    def test_caminho_feliz_retorna_png_valido(self):
        fig = go.Figure(data=[go.Sunburst(labels=["A", "B"], parents=["", "A"], values=[1, 1])])
        png = renderizar_sunburst_png(fig, "MTBF", width=400, height=300)
        assert isinstance(png, bytes)
        assert len(png) > 0
        assert png[:8] == PNG_SIGNATURE

    def test_fallback_em_runtimeerror(self, caplog):
        """SP-13: kaleido lança exception → placeholder PNG retornado, log WARNING."""
        fig = go.Figure()
        with patch("plotly.io.to_image", side_effect=RuntimeError("kaleido boom")):
            png = renderizar_sunburst_png(fig, "MTBF")
        assert png[:8] == PNG_SIGNATURE
        # log emitido com nome do KPI
        assert any("MTBF" in rec.message for rec in caplog.records)

    def test_fallback_em_importerror(self):
        """SP-13: kaleido ausente (ImportError) também cai em placeholder."""
        fig = go.Figure()
        with patch("plotly.io.to_image", side_effect=ImportError("kaleido missing")):
            png = renderizar_sunburst_png(fig, "MTTR")
        assert png[:8] == PNG_SIGNATURE


class TestGerarPlaceholderPng:
    def test_dimensoes_e_signature(self):
        png = _gerar_placeholder_png("MTBF", 400, 300, 1)
        assert png[:8] == PNG_SIGNATURE
        assert len(png) > 100  # placeholder real (não o fallback 1×1)

    def test_label_diferente(self):
        """Labels distintos → PNGs distintos (texto incorporado)."""
        png_mtbf = _gerar_placeholder_png("MTBF", 200, 150, 1)
        png_mttr = _gerar_placeholder_png("MTTR", 200, 150, 1)
        assert png_mtbf != png_mttr

    def test_fallback_final_se_pillow_falha(self, caplog):
        """Se Pillow falhar, retorna PNG 1×1 hardcoded — não quebra docxtpl."""
        with patch("PIL.Image.new", side_effect=OSError("disk full")):
            png = _gerar_placeholder_png("MTBF", 200, 150, 1)
        assert png[:8] == PNG_SIGNATURE
        # PNG 1×1 hardcoded é pequeno (~70 bytes)
        assert len(png) < 200
