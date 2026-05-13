"""Testes unitários de `utils/kpi_report_data.py` — camada 2 (coleta).

Cobertura:
- BR-05 (`_aplicar_escopo` filtra DECAP001)
- SP-18 (`_construir_rotulo_periodo`)
- Helper `_date_range_to_year_months`

IM-06 do projeto SDD KPIReport.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from src.utils.kpi_report_data import (
    _aplicar_escopo,
    _construir_rotulo_periodo,
    _date_range_to_year_months,
)


class TestAplicarEscopo:
    """Após IM-07 (BR-05 item 3 desativada), `EQUIPAMENTOS_EXCLUIDOS = []` —
    nenhum equipamento é excluído. Testes refletem nova realidade.
    """

    def test_passa_lista_completa(self):
        sd = {"equipment_ids": ["LONGI001", "DECAP001", "PRENS002"]}
        assert _aplicar_escopo(sd) == ["LONGI001", "DECAP001", "PRENS002"]

    def test_lista_vazia(self):
        sd = {"equipment_ids": []}
        assert _aplicar_escopo(sd) == []

    def test_chave_ausente(self):
        assert _aplicar_escopo({}) == []

    def test_so_decap001_passa(self):
        """DECAP001 não é mais excluído (item 3 desativado em 2026-05-13)."""
        sd = {"equipment_ids": ["DECAP001"]}
        assert _aplicar_escopo(sd) == ["DECAP001"]

    def test_nao_muta_input(self):
        original = ["LONGI001", "DECAP001"]
        sd = {"equipment_ids": original}
        _ = _aplicar_escopo(sd)
        assert sd["equipment_ids"] == ["LONGI001", "DECAP001"]

    def test_filtragem_dinamica_se_lista_for_repopulada(self, monkeypatch):
        """Comportamento futuro: se algum equipamento entrar em EQUIPAMENTOS_EXCLUIDOS,
        a função volta a filtrar. Lista permanece editável.
        """
        from src.utils import kpi_report_config as cfg
        monkeypatch.setattr(cfg, "EQUIPAMENTOS_EXCLUIDOS", ["FOO"])
        sd = {"equipment_ids": ["LONGI001", "FOO", "PRENS002"]}
        assert _aplicar_escopo(sd) == ["LONGI001", "PRENS002"]


class TestConstruirRotuloPeriodo:
    def test_mes_corrente_exibe_ultimo_dia_incluso(self):
        """MES_CORRENTE — janela `[1/4, 29/4)` → exibe `01/04 a 28/04`."""
        ini = datetime(2026, 4, 1)
        fim = datetime(2026, 4, 29)
        rotulo = _construir_rotulo_periodo(ini, fim, "MES_CORRENTE")
        assert rotulo == "Período: 01/04/2026 a 28/04/2026 (horário de Brasília)"

    def test_ultimos_30_dias_exibe_fim_exato(self):
        ini = datetime(2026, 3, 30)
        fim = datetime(2026, 4, 29)
        rotulo = _construir_rotulo_periodo(ini, fim, "ULTIMOS_30_DIAS")
        assert "30/03/2026 a 29/04/2026" in rotulo

    def test_fuso_label_custom(self):
        ini = datetime(2026, 4, 1)
        fim = datetime(2026, 4, 29)
        rotulo = _construir_rotulo_periodo(ini, fim, "MES_CORRENTE", "horário UTC")
        assert "(horário UTC)" in rotulo


class TestDateRangeToYearMonths:
    def test_intervalo_um_mes(self):
        ini = datetime(2026, 4, 1)
        fim = datetime(2026, 4, 29)
        assert _date_range_to_year_months(ini, fim) == ["2026-04"]

    def test_intervalo_atravessa_meses(self):
        ini = datetime(2026, 3, 15)
        fim = datetime(2026, 5, 10)
        assert _date_range_to_year_months(ini, fim) == ["2026-03", "2026-04", "2026-05"]

    def test_intervalo_atravessa_ano(self):
        ini = datetime(2025, 12, 20)
        fim = datetime(2026, 2, 10)
        assert _date_range_to_year_months(ini, fim) == ["2025-12", "2026-01", "2026-02"]

    def test_intervalo_invertido(self):
        """Fim < início → lista vazia (sem crash)."""
        ini = datetime(2026, 4, 29)
        fim = datetime(2026, 4, 1)
        assert _date_range_to_year_months(ini, fim) == []

    def test_none(self):
        assert _date_range_to_year_months(None, datetime(2026, 1, 1)) == []
        assert _date_range_to_year_months(datetime(2026, 1, 1), None) == []
