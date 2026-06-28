"""Testes unitários de `utils/kpi_report_builder.py` — camada 4 (DOCX).

Cobertura:
- SP-06 `_resolve_template_path` 3 cenários
- SP-14 `TemplateLoadError` em template ausente

IM-06 do projeto SDD KPIReport.
"""
from __future__ import annotations

import os

import pytest

from src.utils import kpi_report_config as cfg
from src.utils.kpi_report_builder import (
    TemplateLoadError,
    _load_template,
    _resolve_template_path,
)


class TestResolveTemplatePath:
    def test_sem_env_var_usa_default(self, monkeypatch):
        """CA-6.1 — sem `KPI_REPORT_TEMPLATE_PATH` → default."""
        monkeypatch.delenv("KPI_REPORT_TEMPLATE_PATH", raising=False)
        assert _resolve_template_path() == cfg.TEMPLATE_PATH_DEFAULT

    def test_env_var_inexistente_fallback_default(self, monkeypatch):
        """CA-6.2 — `KPI_REPORT_TEMPLATE_PATH` aponta para arquivo inexistente → default."""
        monkeypatch.setenv("KPI_REPORT_TEMPLATE_PATH", "/nao/existe.docx")
        assert _resolve_template_path() == cfg.TEMPLATE_PATH_DEFAULT

    def test_env_var_valida_retorna_override(self, monkeypatch, tmp_path):
        """CA-6.3 — `KPI_REPORT_TEMPLATE_PATH` aponta para arquivo existente → usa override."""
        override = tmp_path / "custom.docx"
        override.write_bytes(b"PK\x03\x04dummy")
        monkeypatch.setenv("KPI_REPORT_TEMPLATE_PATH", str(override))
        assert _resolve_template_path() == str(override)

    def test_env_var_vazia_usa_default(self, monkeypatch):
        """Env var presente mas vazia → tratado como ausente."""
        monkeypatch.setenv("KPI_REPORT_TEMPLATE_PATH", "")
        assert _resolve_template_path() == cfg.TEMPLATE_PATH_DEFAULT


class TestLoadTemplate:
    def test_arquivo_existe_carrega(self):
        """CA-6.4 — template default existe → DocxTemplate carregado."""
        tpl = _load_template()
        # DocxTemplate é o tipo esperado de docxtpl
        from docxtpl import DocxTemplate
        assert isinstance(tpl, DocxTemplate)

    def test_arquivo_ausente_lanca_template_load_error(self, monkeypatch):
        """CA-6.5 — template inexistente → `TemplateLoadError`.

        Adaptação IM-06: `DocxTemplate` é lazy (não valida no constructor), então
        `_load_template` faz check `os.path.isfile` eager para falhar cedo.
        """
        # Override aponta para arquivo inexistente — mas _resolve_template_path
        # vai cair em fallback default. Para forçar falha, mockamos _resolve_template_path.
        from src.utils import kpi_report_builder as builder

        def _fake_resolve():
            return "/caminho/nao/existe.docx"

        monkeypatch.setattr(builder, "_resolve_template_path", _fake_resolve)

        with pytest.raises(TemplateLoadError) as exc_info:
            _load_template()
        assert "nao/existe.docx" in exc_info.value.path
        assert isinstance(exc_info.value.original, FileNotFoundError)


class TestMesCorrenteDoRelatorio:
    def test_deriva_de_periodo_inicio_mensal(self):
        """IM-15 — usa a janela mensal já calculada no dict (mesmo mês dos demais blocos)."""
        from datetime import datetime
        from src.utils.kpi_report_builder import _mes_corrente_do_relatorio
        dados = {"periodo": {"inicio_mensal": datetime(2026, 6, 1)}}
        assert _mes_corrente_do_relatorio(dados) == (2026, "2026-06")

    def test_fallback_compute_monthly_window(self, monkeypatch):
        """IM-15 — sem `periodo` → cai em compute_monthly_window sobre o agora do fuso."""
        from datetime import datetime
        from src.utils import kpi_report_builder as builder
        from src.utils import kpi_report_config as cfg
        monkeypatch.setattr(cfg, "_now_in_report_timezone", lambda: datetime(2026, 3, 15, 10, 0))
        assert builder._mes_corrente_do_relatorio({}) == (2026, "2026-03")


class TestInjectCustoMensal:
    """IM-15 — injeção defensiva do gráfico de custo no contexto do template (DS-11)."""

    def _template(self):
        return _load_template()

    def test_com_dados_cria_inline_image(self, monkeypatch):
        from datetime import datetime
        from docxtpl import InlineImage
        import plotly.graph_objects as go
        from src.utils import kpi_report_builder as builder
        import src.custos.figuras as figuras
        from src.utils import kpi_report_figures as figs

        monkeypatch.setattr(figuras, "figura_custo_mensal", lambda ano, mes, h=460: go.Figure())
        monkeypatch.setattr(figs, "renderizar_sunburst_png",
                            lambda fig, kpi_label, width, height, scale: b"\x89PNG\r\n\x1a\n_fake")

        dados = {"periodo": {"inicio_mensal": datetime(2026, 6, 1)}}
        builder._inject_custo_mensal(self._template(), dados)
        assert isinstance(dados["custo_mensal_img"], InlineImage)
        assert dados["custo_mensal_titulo"] == "Custo de Manutenção — 2026-06"

    def test_sem_dados_deixa_none(self, monkeypatch):
        from datetime import datetime
        from src.utils import kpi_report_builder as builder
        import src.custos.figuras as figuras

        monkeypatch.setattr(figuras, "figura_custo_mensal", lambda ano, mes, h=460: None)
        dados = {"periodo": {"inicio_mensal": datetime(2026, 6, 1)}}
        builder._inject_custo_mensal(self._template(), dados)
        assert dados["custo_mensal_img"] is None
        assert "custo_mensal_titulo" not in dados

    def test_falha_na_camada_de_custo_nao_propaga(self, monkeypatch):
        """Erro de fetch/figura → bloco omitido (img None), sem exceção (export não quebra)."""
        from datetime import datetime
        from src.utils import kpi_report_builder as builder
        import src.custos.figuras as figuras

        def _boom(ano, mes, h=460):
            raise RuntimeError("Mongo de custos indisponível")

        monkeypatch.setattr(figuras, "figura_custo_mensal", _boom)
        dados = {"periodo": {"inicio_mensal": datetime(2026, 6, 1)}}
        builder._inject_custo_mensal(self._template(), dados)  # não deve lançar
        assert dados["custo_mensal_img"] is None


class TestFmtLinhaLanc:
    """IM-16 — formatação de linha de lançamento de custo (SP-17 / DS-12)."""

    def test_data_e_valor_pt_br(self):
        from datetime import datetime
        from src.utils.kpi_report_builder import _fmt_linha_lanc
        linha = _fmt_linha_lanc({"data": datetime(2026, 6, 18), "equipamento": "PRENSA-01",
                                 "conta_nome": "Consumo de Material", "descritor": "rolamento",
                                 "valor": 1234.56})
        assert linha["data"] == "18/06/2026"
        assert linha["valor"] == "R$ 1.234,56"
        assert linha["equipamento"] == "PRENSA-01"
        assert linha["conta_nome"] == "Consumo de Material"
        assert linha["descritor"] == "rolamento"

    def test_descritor_vazio_e_data_ausente(self):
        from src.utils.kpi_report_builder import _fmt_linha_lanc
        linha = _fmt_linha_lanc({"data": None, "valor": 0})
        assert linha["data"] == ""
        assert linha["descritor"] == ""
        assert linha["valor"] == "R$ 0,00"


class TestInjectCustoTabelas:
    """IM-16 — injeção defensiva das tabelas de custo (DS-12)."""

    def test_com_dados_formata_listas(self, monkeypatch):
        from datetime import datetime
        from src.utils import kpi_report_builder as builder
        import src.custos.leitura as leitura

        rec = [{"data": datetime(2026, 6, 18), "equipamento": "L1", "conta_nome": "C",
                "descritor": "d", "valor": 10.0}]
        mai = [{"data": datetime(2026, 6, 1), "equipamento": "L2", "conta_nome": "C2",
                "descritor": "", "valor": 999.9}]
        monkeypatch.setattr(leitura, "fetch_lancamentos_recentes", lambda ano, mes, limit=10: rec)
        monkeypatch.setattr(leitura, "fetch_lancamentos_maiores", lambda ano, mes, limit=5: mai)

        dados = {"periodo": {"inicio_mensal": datetime(2026, 6, 1)}}
        builder._inject_custo_tabelas(dados)
        assert len(dados["custo_recentes"]) == 1 and dados["custo_recentes"][0]["valor"] == "R$ 10,00"
        assert len(dados["custo_maiores"]) == 1 and dados["custo_maiores"][0]["valor"] == "R$ 999,90"

    def test_vazio_deixa_listas_vazias(self, monkeypatch):
        from datetime import datetime
        from src.utils import kpi_report_builder as builder
        import src.custos.leitura as leitura
        monkeypatch.setattr(leitura, "fetch_lancamentos_recentes", lambda ano, mes, limit=10: [])
        monkeypatch.setattr(leitura, "fetch_lancamentos_maiores", lambda ano, mes, limit=5: [])
        dados = {"periodo": {"inicio_mensal": datetime(2026, 6, 1)}}
        builder._inject_custo_tabelas(dados)
        assert dados["custo_recentes"] == [] and dados["custo_maiores"] == []

    def test_falha_na_camada_nao_propaga(self, monkeypatch):
        from datetime import datetime
        from src.utils import kpi_report_builder as builder
        import src.custos.leitura as leitura

        def _boom(ano, mes, limit=10):
            raise RuntimeError("Mongo custos indisponível")

        monkeypatch.setattr(leitura, "fetch_lancamentos_recentes", _boom)
        monkeypatch.setattr(leitura, "fetch_lancamentos_maiores", _boom)
        dados = {"periodo": {"inicio_mensal": datetime(2026, 6, 1)}}
        builder._inject_custo_tabelas(dados)  # não deve lançar
        assert dados["custo_recentes"] == [] and dados["custo_maiores"] == []
