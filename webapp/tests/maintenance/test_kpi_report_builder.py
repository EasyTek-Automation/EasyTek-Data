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
