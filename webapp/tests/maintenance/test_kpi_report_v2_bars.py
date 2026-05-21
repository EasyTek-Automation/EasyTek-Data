"""Testes do módulo `utils/kpi_report_v2_bars.py` (refactor RF-01..RF-03).

Cobre:
- build_bar_figure: estrutura Plotly retornada (Bar trace + tendência + linha meta)
- highlight_idx: cor da barra destacada
- show_trend / show_meta_line toggles
- KPI direction: cor da barra (cumpre meta vs não) muda corretamente
- Empty values: gera figura válida sem quebrar
"""
from __future__ import annotations

import pytest
from plotly.graph_objects import Figure

from src.utils.kpi_report_v2_bars import build_bar_figure


class TestBuildBarFigure:
    def test_retorna_figure_plotly(self):
        fig = build_bar_figure(
            labels=["Jan", "Fev", "Mar"], values=[10.0, 12.0, 15.0],
            kpi="mtbf",
        )
        assert isinstance(fig, Figure)
        bar_traces = [t for t in fig.data if t.type == "bar"]
        assert len(bar_traces) == 1
        assert list(bar_traces[0].x) == ["Jan", "Fev", "Mar"]
        assert list(bar_traces[0].y) == [10.0, 12.0, 15.0]

    def test_unidade_mtbf_h(self):
        fig = build_bar_figure(
            labels=["A"], values=[5.0], kpi="mtbf",
        )
        # text contém "h" (unidade MTBF)
        text = list(fig.data[0].text)
        assert any("h" in t for t in text if t)

    def test_unidade_mttr_min(self):
        fig = build_bar_figure(labels=["A"], values=[5.0], kpi="mttr")
        text = list(fig.data[0].text)
        assert any("min" in t for t in text if t)

    def test_unidade_taxa_avaria_pct(self):
        fig = build_bar_figure(labels=["A"], values=[2.5], kpi="taxa_avaria")
        text = list(fig.data[0].text)
        assert any("%" in t for t in text if t)

    def test_trendline_aparece_quando_ge_3_pontos(self):
        fig = build_bar_figure(
            labels=["Jan", "Fev", "Mar", "Abr"], values=[10, 12, 15, 14],
            kpi="mtbf", show_trend=True,
        )
        scatter = [t for t in fig.data if t.type == "scatter"]
        assert len(scatter) == 1

    def test_trendline_omite_quando_menos_de_3_pontos(self):
        fig = build_bar_figure(
            labels=["Jan", "Fev"], values=[10, 12], kpi="mtbf", show_trend=True,
        )
        scatter = [t for t in fig.data if t.type == "scatter"]
        assert len(scatter) == 0

    def test_meta_line_aparece(self):
        fig = build_bar_figure(
            labels=["A"], values=[10], kpi="mtbf", target=8.0,
        )
        # hlines viram shapes no layout
        shapes = fig.layout.shapes or []
        assert any(s.type == "line" for s in shapes)

    def test_meta_line_omite(self):
        fig = build_bar_figure(
            labels=["A"], values=[10], kpi="mtbf", target=None,
        )
        shapes = fig.layout.shapes or []
        assert not any(s.type == "line" for s in shapes)

    def test_highlight_idx_aplica_cor_destacada(self):
        fig = build_bar_figure(
            labels=["A", "B", "C"], values=[10, 12, 15], kpi="mtbf",
            highlight_idx=1,
        )
        marker_colors = list(fig.data[0].marker.color)
        # idx 1 deve ter cor laranja (destaque)
        assert marker_colors[1] == "#fd7e14"

    def test_kpi_higher_cumpre_meta_fica_verde(self):
        # MTBF higher: valor >= meta → verde
        fig = build_bar_figure(
            labels=["A"], values=[15.0], kpi="mtbf", target=10.0,
        )
        colors_used = list(fig.data[0].marker.color)
        assert colors_used[0] == "#198754"

    def test_kpi_higher_nao_cumpre_meta_fica_vermelho(self):
        fig = build_bar_figure(
            labels=["A"], values=[5.0], kpi="mtbf", target=10.0,
        )
        colors_used = list(fig.data[0].marker.color)
        assert colors_used[0] == "#dc3545"

    def test_kpi_lower_cumpre_meta(self):
        # MTTR lower: valor <= meta → verde
        fig = build_bar_figure(
            labels=["A"], values=[5.0], kpi="mttr", target=10.0,
        )
        assert list(fig.data[0].marker.color)[0] == "#198754"

    def test_kpi_lower_nao_cumpre_meta(self):
        fig = build_bar_figure(
            labels=["A"], values=[15.0], kpi="mttr", target=10.0,
        )
        assert list(fig.data[0].marker.color)[0] == "#dc3545"

    def test_breakdown_rate_lower_cumpre(self):
        fig = build_bar_figure(
            labels=["A"], values=[2.0], kpi="breakdown_rate", target=3.0,
        )
        assert list(fig.data[0].marker.color)[0] == "#198754"

    def test_valor_zero_nao_aplica_cor_de_meta(self):
        # valor 0 → cor base (não comparada contra meta)
        fig = build_bar_figure(
            labels=["A"], values=[0.0], kpi="mtbf", target=10.0,
        )
        # cor 0 não é vermelha — fica cor base
        assert list(fig.data[0].marker.color)[0] == "#198754"

    def test_values_none_viram_zero(self):
        fig = build_bar_figure(
            labels=["A", "B"], values=[None, 10.0], kpi="mtbf",
        )
        assert list(fig.data[0].y) == [0.0, 10.0]

    def test_lista_vazia_gera_fig_valida(self):
        fig = build_bar_figure(labels=[], values=[], kpi="mtbf")
        assert isinstance(fig, Figure)

    def test_title_aplicado(self):
        fig = build_bar_figure(
            labels=["A"], values=[10], kpi="mtbf", title="MTBF Planta",
        )
        assert fig.layout.title.text == "MTBF Planta"

    def test_height_aplicado(self):
        fig = build_bar_figure(
            labels=["A"], values=[10], kpi="mtbf", height=400,
        )
        assert fig.layout.height == 400

    def test_kpi_desconhecido_usa_default(self):
        fig = build_bar_figure(labels=["A"], values=[10], kpi="oee")
        assert isinstance(fig, Figure)
        # cor padrão azul (sem mapping pra "oee")
        assert list(fig.data[0].marker.color)[0] == "#0d6efd"
