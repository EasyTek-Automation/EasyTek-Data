"""Testes de `custos/figuras.py` — figura de custo mensal sem Dash (SP-16 / DS-11, IM-15)."""
from __future__ import annotations

import plotly.graph_objects as go

from src.custos import figuras


# Linhas de exemplo no contrato de `fetch_contas_geral`
_GERAL_ZERO = {"code": "__GERAL__", "label": "GERAL", "orcado": 0, "executado": 0, "pct": None}
_GERAL_CHEIO = {"code": "__GERAL__", "label": "GERAL", "orcado": 100.0, "executado": 80.0, "pct": 80.0}
_CONTA = {"code": "15", "label": "Manutenção de Máquinas", "orcado": 50.0, "executado": 40.0, "pct": 80.0}


class TestSemDados:
    def test_lista_vazia_e_sem_dados(self):
        assert figuras._sem_dados([]) is True
        assert figuras._sem_dados(None) is True

    def test_so_geral_zerado_e_sem_dados(self):
        assert figuras._sem_dados([_GERAL_ZERO]) is True

    def test_geral_com_executado_tem_dados(self):
        assert figuras._sem_dados([_GERAL_CHEIO]) is False

    def test_com_contas_tem_dados(self):
        assert figuras._sem_dados([_GERAL_ZERO, _CONTA]) is False


class TestFiguraCustoMensal:
    def test_sem_dados_retorna_none(self, monkeypatch):
        """Mês sem carga → fetch só GERAL zerado → figura omitida (None)."""
        monkeypatch.setattr(figuras.L, "fetch_contas_geral", lambda ano, mes, centros=None: [_GERAL_ZERO])
        assert figuras.figura_custo_mensal(2026, "2026-06") is None

    def test_com_dados_retorna_figura(self, monkeypatch):
        """Com contas → invoca `_fig_barras` (eixo duplo, modo pct) e devolve a Figure."""
        monkeypatch.setattr(figuras.L, "fetch_contas_geral",
                            lambda ano, mes, centros=None: [_GERAL_CHEIO, _CONTA])

        captured = {}

        def _fake_fig_barras(rows, com_orcado, titulo, h=380, mini=False, modo="valor"):
            captured.update(rows=rows, com_orcado=com_orcado, titulo=titulo, h=h, modo=modo)
            return go.Figure()

        import src.callbacks_registers.custo_callbacks as cc
        monkeypatch.setattr(cc, "_fig_barras", _fake_fig_barras)

        fig = figuras.figura_custo_mensal(2026, "2026-06", h=460)
        assert isinstance(fig, go.Figure)
        assert captured["com_orcado"] is True
        assert captured["modo"] == "pct"
        assert captured["h"] == 460
        assert "2026-06" in captured["titulo"]
        assert len(captured["rows"]) == 2


class TestTabelaResumoRosca:
    """`_tabela_resumo` — quebra de uma fatia da rosca por conta/centro (modal da rosca)."""

    def test_vazio_retorna_none(self):
        import src.callbacks_registers.custo_callbacks as cc
        assert cc._tabela_resumo([], 100.0, "Conta") is None
        assert cc._tabela_resumo(None, 100.0, "Conta") is None

    def test_codigo_oculto_quando_igual_ao_nome(self):
        """Centro sem de/para (nome == código) → não repete '(209710)' redundante."""
        import dash_bootstrap_components as dbc
        import src.callbacks_registers.custo_callbacks as cc
        tab = cc._tabela_resumo([{"code": "209710", "nome": "209710", "executado": 50.0}],
                                100.0, "Centro de custo")
        assert isinstance(tab, dbc.Table)
        txt = str(tab)
        # o código aparece uma vez só (no nome), sem o sufixo "(209710)"
        assert "(209710)" not in txt

    def test_codigo_visivel_quando_ha_nome_proprio(self):
        """Conta com de/para → mostra nome amigável + código entre parênteses."""
        import src.callbacks_registers.custo_callbacks as cc
        tab = cc._tabela_resumo(
            [{"code": "33102260", "nome": "Manutenção de Máquinas e Equipamentos",
              "executado": 723767.0}], 2243118.0, "Conta")
        txt = str(tab)
        assert "Manutenção de Máquinas e Equipamentos" in txt
        assert "(33102260)" in txt
