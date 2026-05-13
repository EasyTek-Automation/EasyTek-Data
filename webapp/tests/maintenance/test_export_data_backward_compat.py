"""Teste de regressão — callback Excel `export_data` após mudança de Input ID.

DS-06 trocou Input ID `btn-export-indicators` → `btn-export-indicators-xlsx`.
Output (`download-indicators-data`), corpo da função e comportamento permanecem.
Mitiga RR-02 da RV-02 (refactor quebra Excel).

IM-06 do projeto SDD KPIReport.
"""
from __future__ import annotations

import inspect

import pytest


def test_callback_excel_existe_e_é_importavel():
    """Smoke: módulo do callback Excel ainda importável após mudanças da IM-05."""
    from src.callbacks_registers import maintenance_kpi_callbacks  # noqa: F401


def test_grep_input_id_atualizado():
    """Verifica via inspeção do source code que o Input ID novo está presente."""
    from src.callbacks_registers import maintenance_kpi_callbacks
    src = inspect.getsource(maintenance_kpi_callbacks)

    # ID antigo NÃO deve aparecer mais (a não ser em comentários ou strings de teste)
    # Como há comentário "ID alterado", buscamos pelo padrão de uso como ID Dash
    assert '"btn-export-indicators"' not in src and "'btn-export-indicators'" not in src, \
        "ID antigo 'btn-export-indicators' ainda aparece — RR-02 risco"

    # ID novo deve estar presente
    assert '"btn-export-indicators-xlsx"' in src or "'btn-export-indicators-xlsx'" in src


def test_grep_zero_orfaos_no_indicators_layout():
    """Verifica que indicators.py não usa mais o ID antigo no layout."""
    from src.pages.maintenance import indicators
    src = inspect.getsource(indicators)
    assert '"btn-export-indicators"' not in src and "'btn-export-indicators'" not in src


def test_kpi_report_callbacks_module_carrega():
    """Smoke: novo módulo do KPIReport importável (SP-01 / SP-02)."""
    from src.callbacks_registers import kpi_report_callbacks  # noqa: F401
    from src.callbacks_registers.kpi_report_callbacks import (
        register_kpi_report_callbacks,
        _store_estrutura_valida,
    )
    assert callable(register_kpi_report_callbacks)
    assert callable(_store_estrutura_valida)
