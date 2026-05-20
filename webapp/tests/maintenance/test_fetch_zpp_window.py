"""Testes da janela temporal em `fetch_zpp_production_data` e `fetch_zpp_breakdown_data`.

Captura três bugs identificados em 2026-05-20 na investigação cliente AMG:

Bug #1 — `$lte end_date` inclui dia 01 do mês seguinte
    Caller passa end_date = datetime(y, m+1, 1) (primeiro instante do mês seguinte).
    Filtro $lte inclui esse instante — registros datados em 01/abril vazam para o
    fetch de março. Em mar/2026: +109 registros produção (+107.69h) e +13 paradas.
    Fix: $lte → $lt (janela semi-aberta [start, end)).

Bug #2 — `ffinnotif >= start_date` sem teto superior (commit 45ca903)
    Filtro só limitava inferior. Registros com ffinnotif posterior ao end_date
    entravam no resultado. Fix: adicionar $lt end_date em ffinnotif.

Bug #3 — `fetch_zpp_breakdown_data` filtra por `inicio_execucao` em vez de
    `fim_execucao`. Viola BR-01 (campo de referência é fim_execucao) e BR-03
    (MONTH_BOUNDARY_RULE='fim'). Paradas cross-month iam pro mês de início.
    Fix: trocar campo do filtro pra fim_execucao + janela ampliada simétrica
    em inicio_execucao.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


class TestFetchProductionWindow:
    """Valida query Mongo de `fetch_zpp_production_data`."""

    @pytest.fixture
    def mock_collection(self):
        mock = MagicMock()
        mock.find.return_value = iter([])
        return mock

    def _extract_query(self, mock_collection):
        assert mock_collection.find.called, "find() não foi chamado"
        return mock_collection.find.call_args[0][0]

    def test_fininotif_usa_lt_no_fim_nao_lte(self, mock_collection):
        """Bug #1: fininotif deve usar $lt no end_date, nunca $lte."""
        from src.utils import zpp_kpi_calculator

        start = datetime(2026, 3, 1)
        end = datetime(2026, 4, 1)

        with patch.object(zpp_kpi_calculator, "get_mongo_connection", return_value=mock_collection):
            zpp_kpi_calculator.fetch_zpp_production_data(start, end)

        query = self._extract_query(mock_collection)
        fininotif = query["fininotif"]

        assert "$lt" in fininotif, "fim da janela em fininotif deve usar $lt"
        assert "$lte" not in fininotif, "fim da janela NUNCA deve usar $lte (Bug #1)"
        assert fininotif["$lt"] == end

    def test_ffinnotif_tem_teto_superior(self, mock_collection):
        """Bug #2: ffinnotif precisa ter teto $lt end_date além do $gte start_date."""
        from src.utils import zpp_kpi_calculator

        start = datetime(2026, 3, 1)
        end = datetime(2026, 4, 1)

        with patch.object(zpp_kpi_calculator, "get_mongo_connection", return_value=mock_collection):
            zpp_kpi_calculator.fetch_zpp_production_data(start, end)

        query = self._extract_query(mock_collection)
        ffinnotif = query["ffinnotif"]

        assert "$gte" in ffinnotif, "ffinnotif deve ter $gte start_date"
        assert ffinnotif["$gte"] == start
        assert "$lt" in ffinnotif, "ffinnotif deve ter $lt end_date (Bug #2)"
        assert ffinnotif["$lt"] == end
        assert "$lte" not in ffinnotif, "ffinnotif NUNCA deve usar $lte"

    def test_fininotif_mantem_janela_ampliada_retroativa(self, mock_collection):
        """Preserva intenção do 45ca903: janela retroativa 31 dias em fininotif."""
        from src.utils import zpp_kpi_calculator

        start = datetime(2026, 3, 1)
        end = datetime(2026, 4, 1)

        with patch.object(zpp_kpi_calculator, "get_mongo_connection", return_value=mock_collection):
            zpp_kpi_calculator.fetch_zpp_production_data(start, end)

        fininotif = self._extract_query(mock_collection)["fininotif"]
        assert "$gte" in fininotif
        assert fininotif["$gte"] == start - timedelta(days=31)

    def test_boundary_cross_month_aparece_no_mes_de_fim(self, mock_collection):
        """Registro cross-month (fininotif=fev, ffinnotif=mar) aparece em fetch(mar).

        MONTH_BOUNDARY_RULE='fim' → registro conta no mês em que ffinnotif cai.
        """
        from src.utils import zpp_kpi_calculator

        start = datetime(2026, 3, 1)
        end = datetime(2026, 4, 1)

        mock_collection.find.return_value = iter([
            {
                "pto_trab": "LONGI001",
                "fininotif": datetime(2026, 2, 28, 22, 0),
                "ffinnotif": datetime(2026, 3, 1, 2, 0),
                "horasact": 4.0,
            }
        ])

        with patch.object(zpp_kpi_calculator, "get_mongo_connection", return_value=mock_collection):
            df = zpp_kpi_calculator.fetch_zpp_production_data(start, end)

        assert len(df) == 1
        assert df.iloc[0]["year_month"] == "2026-03"
        assert bool(df.iloc[0]["boundary_case"]) is True

    def test_registro_finalizando_no_dia_01_proximo_mes_nao_entra(self, mock_collection):
        """Registro com ffinnotif=01/04 NÃO deve entrar em fetch(março).

        Mesmo se a query Mongo retornasse esse doc (não deveria após fix), o pós-fix
        Python descarta porque (fim.year, fim.month) != (target_year=3, target_month=3).
        """
        from src.utils import zpp_kpi_calculator

        start = datetime(2026, 3, 1)
        end = datetime(2026, 4, 1)

        mock_collection.find.return_value = iter([
            {
                "pto_trab": "LONGI001",
                "fininotif": datetime(2026, 3, 31, 22, 0),
                "ffinnotif": datetime(2026, 4, 1, 0, 0),
                "horasact": 2.0,
            }
        ])

        with patch.object(zpp_kpi_calculator, "get_mongo_connection", return_value=mock_collection):
            df = zpp_kpi_calculator.fetch_zpp_production_data(start, end)

        assert len(df) == 0, "registro com ffinnotif=01/abr não pode aparecer em fetch(março)"


class TestFetchBreakdownWindow:
    """Valida query Mongo de `fetch_zpp_breakdown_data`."""

    @pytest.fixture
    def mock_collection(self):
        mock = MagicMock()
        mock.find.return_value = iter([])
        return mock

    def _extract_query(self, mock_collection):
        assert mock_collection.find.called, "find() não foi chamado"
        return mock_collection.find.call_args[0][0]

    def test_filtra_por_fim_execucao_nao_inicio(self, mock_collection):
        """Bug #3: filtro de janela deve usar `fim_execucao` (BR-01/BR-03), não `inicio_execucao`.

        BR-01: campo de referência de ZPP_Paradas é `fim_execucao`.
        BR-03: MONTH_BOUNDARY_RULE='fim' → classificação por mês de fim.
        Filtrar a query por inicio_execucao desalinha webapp do zpp-processor.
        """
        from src.utils import zpp_kpi_calculator

        start = datetime(2026, 3, 1)
        end = datetime(2026, 4, 1)

        with patch.object(zpp_kpi_calculator, "get_mongo_connection", return_value=mock_collection):
            zpp_kpi_calculator.fetch_zpp_breakdown_data(start, end)

        query = self._extract_query(mock_collection)
        assert "fim_execucao" in query, "Bug #3: query deve filtrar por fim_execucao (BR-01)"
        fim = query["fim_execucao"]
        assert "$gte" in fim and fim["$gte"] == start
        assert "$lt" in fim and fim["$lt"] == end
        assert "$lte" not in fim, "fim_execucao NUNCA deve usar $lte (Bug #1)"

    def test_inicio_execucao_tem_janela_ampliada_simetrica(self, mock_collection):
        """`inicio_execucao` também precisa estar no filtro com janela ampliada.

        Permite capturar registros boundary (inicio em mês anterior, fim no atual)
        sem trazer histórico irrelevante. Espelha estratégia de fetch_production.
        """
        from src.utils import zpp_kpi_calculator

        start = datetime(2026, 3, 1)
        end = datetime(2026, 4, 1)

        with patch.object(zpp_kpi_calculator, "get_mongo_connection", return_value=mock_collection):
            zpp_kpi_calculator.fetch_zpp_breakdown_data(start, end)

        query = self._extract_query(mock_collection)
        assert "inicio_execucao" in query, "inicio_execucao deve continuar no filtro"
        inicio = query["inicio_execucao"]
        assert "$gte" in inicio
        assert inicio["$gte"] == start - timedelta(days=31)
        assert "$lt" in inicio and inicio["$lt"] == end
        assert "$lte" not in inicio

    def test_preserva_filtro_de_codigos_avaria(self, mock_collection):
        """`causa_do_desvio` $in BREAKDOWN_CODES e _processed True são preservados."""
        from src.utils import zpp_kpi_calculator

        start = datetime(2026, 3, 1)
        end = datetime(2026, 4, 1)
        codes = ["201", "S201"]

        with patch.object(zpp_kpi_calculator, "get_mongo_connection", return_value=mock_collection):
            zpp_kpi_calculator.fetch_zpp_breakdown_data(start, end, breakdown_codes=codes)

        query = self._extract_query(mock_collection)
        assert query["_processed"] is True
        assert query["causa_do_desvio"] == {"$in": codes}

    def test_parada_cross_month_aparece_no_mes_de_fim(self, mock_collection):
        """Parada com inicio=27/02 e fim=02/03 aparece em fetch(março), não em fev.

        Cenário do relatório: ordem 10413903 (causa 51, cross-month). Estruturalmente
        equivalente a uma avaria cross-month — testa que o pipeline atribui ao mês
        de fim, conforme BR-03 (MONTH_BOUNDARY_RULE='fim').
        """
        from src.utils import zpp_kpi_calculator

        start = datetime(2026, 3, 1)
        end = datetime(2026, 4, 1)

        mock_collection.find.return_value = iter([
            {
                "centro_de_trabalho": "PRENS002",
                "inicio_execucao": datetime(2026, 2, 27, 22, 0),
                "fim_execucao": datetime(2026, 3, 2, 4, 0),
                "causa_do_desvio": "201",
                "duration_min": 2954.0,
            }
        ])

        with patch.object(zpp_kpi_calculator, "get_mongo_connection", return_value=mock_collection):
            df = zpp_kpi_calculator.fetch_zpp_breakdown_data(start, end)

        assert len(df) == 1
        assert df.iloc[0]["year_month"] == "2026-03"
        assert bool(df.iloc[0]["boundary_case"]) is True

    def test_parada_iniciando_no_dia_01_proximo_mes_nao_entra(self, mock_collection):
        """Parada com inicio=01/04 e fim=01/04 NÃO deve entrar em fetch(março).

        Caso real reportado: 13 paradas com inicio_execucao=01/04 vazaram para o
        fetch de março antes do fix.
        """
        from src.utils import zpp_kpi_calculator

        start = datetime(2026, 3, 1)
        end = datetime(2026, 4, 1)

        mock_collection.find.return_value = iter([
            {
                "centro_de_trabalho": "LONGI001",
                "inicio_execucao": datetime(2026, 4, 1, 0, 30),
                "fim_execucao": datetime(2026, 4, 1, 1, 0),
                "causa_do_desvio": "201",
                "duration_min": 30.0,
            }
        ])

        with patch.object(zpp_kpi_calculator, "get_mongo_connection", return_value=mock_collection):
            df = zpp_kpi_calculator.fetch_zpp_breakdown_data(start, end)

        assert len(df) == 0, "parada em 01/abril não pode aparecer em fetch(março)"
