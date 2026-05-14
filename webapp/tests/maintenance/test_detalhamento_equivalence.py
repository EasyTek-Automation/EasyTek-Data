"""Teste de equivalência — `build_detalhamento_table` (KPIReport) vs
`_build_raw_table_internal` (extraída de `update_raw_data_tab`).

Mitiga RR-01 da RV-02 + atende RV-07 item 3.a:
ambas funções consomem os mesmos insumos e devem produzir os mesmos números
brutos. `build_detalhamento_table` apenas adiciona colunas de cor e renomeia
campos para o contrato DS-03 — números numéricos crus devem bater 1:1.

IM-06 do projeto SDD KPIReport.
"""
from __future__ import annotations

import pytest

from src.utils.kpi_report_data import build_detalhamento_table
from src.utils.maintenance_demo_data import _build_raw_table_internal


@pytest.fixture
def dados_fixture():
    """3 equipamentos, 1 mês, valores conhecidos."""
    data = {
        "EQ01": [
            {"month": 4, "year_month": "2026-04",
             "num_failures": 3, "num_orders": 50,
             "total_active_hours": 200.0, "total_breakdown_minutes": 180.0},
        ],
        "EQ02": [
            {"month": 4, "year_month": "2026-04",
             "num_failures": 0, "num_orders": 30,
             "total_active_hours": 150.0, "total_breakdown_minutes": 0.0},
        ],
        "EQ03": [
            {"month": 4, "year_month": "2026-04",
             "num_failures": 5, "num_orders": 80,
             "total_active_hours": 300.0, "total_breakdown_minutes": 600.0},
        ],
    }
    names = {"EQ01": "Equipamento 01", "EQ02": "Equipamento 02", "EQ03": "Equipamento 03"}
    targets = {
        "GENERAL": {"mtbf": 50.0, "mttr": 30.0, "breakdown_rate": 5.0, "alert_range": 3.0},
        "EQ01": {"mtbf": 60.0},
    }
    return {"data": data, "names": names, "targets": targets, "eq_ids": ["EQ01", "EQ02", "EQ03"]}


class TestEquivalencia:
    def test_mesma_quantidade_de_linhas(self, dados_fixture):
        rows, _ = _build_raw_table_internal(
            dados_fixture["data"], dados_fixture["eq_ids"], dados_fixture["names"],
            months=[4], year_months=["2026-04"],
        )
        tabela = build_detalhamento_table(
            dados_fixture["eq_ids"], dados_fixture["data"], dados_fixture["names"],
            months=[4], year_months=["2026-04"], targets=dados_fixture["targets"],
        )
        assert len(rows) == len(tabela["linhas"])

    def test_mtbf_bate_para_cada_equipamento(self, dados_fixture):
        rows, _ = _build_raw_table_internal(
            dados_fixture["data"], dados_fixture["eq_ids"], dados_fixture["names"],
            months=[4], year_months=["2026-04"],
        )
        tabela = build_detalhamento_table(
            dados_fixture["eq_ids"], dados_fixture["data"], dados_fixture["names"],
            months=[4], year_months=["2026-04"], targets=dados_fixture["targets"],
        )
        for r, t in zip(rows, tabela["linhas"]):
            assert r["mtbf_h"] == t["mtbf"], f"MTBF divergente em {r['eq_id']}: {r['mtbf_h']} != {t['mtbf']}"

    def test_mttr_bate(self, dados_fixture):
        rows, _ = _build_raw_table_internal(
            dados_fixture["data"], dados_fixture["eq_ids"], dados_fixture["names"],
            months=[4], year_months=["2026-04"],
        )
        tabela = build_detalhamento_table(
            dados_fixture["eq_ids"], dados_fixture["data"], dados_fixture["names"],
            months=[4], year_months=["2026-04"], targets=dados_fixture["targets"],
        )
        for r, t in zip(rows, tabela["linhas"]):
            assert r["mttr_min"] == t["mttr"], f"MTTR divergente em {r['eq_id']}"

    def test_taxa_avaria_bate(self, dados_fixture):
        rows, _ = _build_raw_table_internal(
            dados_fixture["data"], dados_fixture["eq_ids"], dados_fixture["names"],
            months=[4], year_months=["2026-04"],
        )
        tabela = build_detalhamento_table(
            dados_fixture["eq_ids"], dados_fixture["data"], dados_fixture["names"],
            months=[4], year_months=["2026-04"], targets=dados_fixture["targets"],
        )
        for r, t in zip(rows, tabela["linhas"]):
            assert r["taxa_avaria"] == t["taxa_avaria"], f"Taxa divergente em {r['eq_id']}"

    def test_totais_planta_batem(self, dados_fixture):
        _, totals = _build_raw_table_internal(
            dados_fixture["data"], dados_fixture["eq_ids"], dados_fixture["names"],
            months=[4], year_months=["2026-04"],
        )
        tabela = build_detalhamento_table(
            dados_fixture["eq_ids"], dados_fixture["data"], dados_fixture["names"],
            months=[4], year_months=["2026-04"], targets=dados_fixture["targets"],
        )
        total = tabela["total"]
        assert totals["num_ordens"] == total["num_ordens"]
        assert totals["num_paradas"] == total["num_paradas"]
        assert totals["mtbf_h"] == total["mtbf"]
        assert totals["mttr_min"] == total["mttr"]
        assert totals["taxa_avaria"] == total["taxa_avaria"]

    def test_tabela_carrega_cores(self, dados_fixture):
        """build_detalhamento_table deve adicionar cor_mtbf/mttr/taxa_avaria."""
        tabela = build_detalhamento_table(
            dados_fixture["eq_ids"], dados_fixture["data"], dados_fixture["names"],
            months=[4], year_months=["2026-04"], targets=dados_fixture["targets"],
        )
        for linha in tabela["linhas"]:
            assert "cor_mtbf" in linha
            assert "cor_mttr" in linha
            assert "cor_taxa_avaria" in linha
        assert "cor_mtbf" in tabela["total"]

    def test_vazio_para_eq_ids_vazio(self):
        tabela = build_detalhamento_table([], {}, {}, [4], None, {})
        assert tabela["vazio"] is True
        assert tabela["linhas"] == []
