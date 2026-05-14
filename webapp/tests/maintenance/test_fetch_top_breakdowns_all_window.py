"""Testes da janela temporal em `fetch_top_breakdowns_all`.

Captura regressão do bug reportado pelo PCM em 2026-05-13:
- Sintoma: filtro "11 ao 12" retornava igual a "11 só" (contagem duplicada do dia 12).
- Causa: `$lte` (inclusivo) capturava registros com `inicio_execucao == end_date`,
  que sempre cai em meia-noite do dia seguinte (campo no Mongo é só a DATA).
- Fix (commit 963689d): `$lt` no fim — janela SEMI-ABERTA `[start, end)`.

IM-07 do projeto SDD KPIReport. Cumpre regra CLAUDE.md AMG_Data: teste retroativo
captura comportamento pós-fix; impede regressão futura para `$lte`.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest


class TestFetchTopBreakdownsAllWindow:
    """Valida que a query Mongo usa janela semi-aberta `[start, end)`."""

    @pytest.fixture
    def mock_collection(self):
        """MagicMock de pymongo collection com `.aggregate()` retornando lista vazia."""
        mock = MagicMock()
        mock.aggregate.return_value = iter([])
        return mock

    def _extract_match_stage(self, mock_collection):
        """Extrai o `$match` do primeiro estágio do pipeline passado a `aggregate()`."""
        assert mock_collection.aggregate.called, "aggregate() não foi chamado"
        pipeline = mock_collection.aggregate.call_args[0][0]
        assert isinstance(pipeline, list) and len(pipeline) >= 1
        assert "$match" in pipeline[0], "primeiro estágio do pipeline deve ser $match"
        return pipeline[0]["$match"]

    def test_window_usa_lt_no_fim_nao_lte(self, mock_collection):
        """Regressão: o fim da janela é `$lt` (exclusivo), nunca `$lte`."""
        from src.utils import zpp_kpi_calculator

        start = datetime(2026, 5, 11)
        end = datetime(2026, 5, 12)

        with patch.object(zpp_kpi_calculator, "get_mongo_connection", return_value=mock_collection):
            zpp_kpi_calculator.fetch_top_breakdowns_all(start, end, top_n=None)

        match_stage = self._extract_match_stage(mock_collection)
        window = match_stage["inicio_execucao"]

        assert "$lt" in window, "fim da janela deve usar $lt (semi-aberta)"
        assert "$lte" not in window, "fim da janela NUNCA deve usar $lte (bug 2026-05-13)"
        assert window["$lt"] == end

    def test_window_usa_gte_no_inicio(self, mock_collection):
        """Início da janela é inclusivo (`$gte`)."""
        from src.utils import zpp_kpi_calculator

        start = datetime(2026, 5, 11)
        end = datetime(2026, 5, 12)

        with patch.object(zpp_kpi_calculator, "get_mongo_connection", return_value=mock_collection):
            zpp_kpi_calculator.fetch_top_breakdowns_all(start, end)

        window = self._extract_match_stage(mock_collection)["inicio_execucao"]
        assert "$gte" in window
        assert window["$gte"] == start

    def test_match_stage_estrutura_completa(self, mock_collection):
        """Estrutura do `$match` preserva filtros essenciais: codes, processed, exists."""
        from src.utils import zpp_kpi_calculator

        start = datetime(2026, 5, 11)
        end = datetime(2026, 5, 12)
        codes = ["201", "S201"]

        with patch.object(zpp_kpi_calculator, "get_mongo_connection", return_value=mock_collection):
            zpp_kpi_calculator.fetch_top_breakdowns_all(start, end, breakdown_codes=codes)

        match_stage = self._extract_match_stage(mock_collection)
        assert match_stage["_processed"] is True
        assert match_stage["causa_do_desvio"] == {"$in": codes}
        assert match_stage["inicio_execucao"]["$exists"] is True

    def test_borda_registro_no_fim_e_excluido(self, mock_collection):
        """Registro com `inicio_execucao == end_date` NÃO deve aparecer no resultado.

        Cenário do bug: paradas com `inicio_execucao=12/05 00:00` apareciam em queries
        com `end=12/05 00:00` por causa do `$lte`. Com `$lt`, o filtro do Mongo já as
        descarta — este teste valida o contrato esperado da janela.
        """
        from src.utils import zpp_kpi_calculator

        start = datetime(2026, 5, 11)
        end = datetime(2026, 5, 12)

        # Simula Mongo já tendo aplicado o $lt corretamente — retorna só dia 11.
        mock_collection.aggregate.return_value = iter([
            {
                "centro_de_trabalho": "LONGI001",
                "inicio_execucao": datetime(2026, 5, 11),
                "inicio_real_hora": "08:30:00",
                "causa_do_desvio": "201",
                "duration_min": 90,
                "descricao": "falha A",
                "texto_de_confirmacao": "",
            },
        ])

        with patch.object(zpp_kpi_calculator, "get_mongo_connection", return_value=mock_collection):
            result = zpp_kpi_calculator.fetch_top_breakdowns_all(start, end, top_n=None)

        # Janela do Mongo respeita $lt — o resultado é o que a collection retorna.
        # O assert real é estrutural: confirmar que a query enviada foi $lt (não $lte).
        window = self._extract_match_stage(mock_collection)["inicio_execucao"]
        assert window["$lt"] == end
        assert "$lte" not in window
        assert len(result) == 1
        assert result[0]["inicio_execucao"].day == 11

    def test_top_n_none_omite_limit(self, mock_collection):
        """Bloco 5 do KPIReport passa `top_n=None` — pipeline NÃO deve ter `$limit`."""
        from src.utils import zpp_kpi_calculator

        with patch.object(zpp_kpi_calculator, "get_mongo_connection", return_value=mock_collection):
            zpp_kpi_calculator.fetch_top_breakdowns_all(
                datetime(2026, 5, 1), datetime(2026, 5, 31), top_n=None
            )

        pipeline = mock_collection.aggregate.call_args[0][0]
        stages_with_limit = [s for s in pipeline if "$limit" in s]
        assert stages_with_limit == [], "top_n=None não deve adicionar $limit"

    def test_top_n_inteiro_adiciona_limit(self, mock_collection):
        """`top_n=5` adiciona `$limit: 5` ao pipeline."""
        from src.utils import zpp_kpi_calculator

        with patch.object(zpp_kpi_calculator, "get_mongo_connection", return_value=mock_collection):
            zpp_kpi_calculator.fetch_top_breakdowns_all(
                datetime(2026, 5, 1), datetime(2026, 5, 31), top_n=5
            )

        pipeline = mock_collection.aggregate.call_args[0][0]
        limit_stages = [s for s in pipeline if "$limit" in s]
        assert len(limit_stages) == 1
        assert limit_stages[0]["$limit"] == 5
