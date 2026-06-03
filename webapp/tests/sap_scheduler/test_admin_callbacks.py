"""Testes dos helpers da pagina admin (DS-08 / SP-09).

Cobre DT-08-13..15 + helpers _construir_*. Os 3 callbacks Dash em si
sao validados via QA Playwright (QA-09-01..07).
"""
from __future__ import annotations

from datetime import datetime

from src.callbacks_registers.sap_scheduler_config_callbacks import (
    _construir_historico,
    _construir_tabela,
    _construir_texto_ultima_alteracao,
    _formatar_em,
)


class TestConstruirTabela:
    """Tabela sempre mostra todos os TIPOS_VALIDOS — defaults pra ausentes."""

    def test_renderiza_2_linhas_em_lista_vazia(self):
        tabela = _construir_tabela([])
        # dbc.Table -> children = [thead, tbody]
        tbody = tabela.children[1]
        assert len(tbody.children) == 2  # zppprd + zpp_nt0001

    def test_renderiza_linha_por_tipo_existente(self):
        agendamentos = [
            {"tipo": "zppprd", "hora": "04:00", "ativo": True},
        ]
        tabela = _construir_tabela(agendamentos)
        tbody = tabela.children[1]
        # 2 linhas: zppprd (encontrado) + zpp_nt0001 (default inativo)
        assert len(tbody.children) == 2

    def test_renderiza_pattern_matching_ids(self):
        tabela = _construir_tabela([])
        tbody = tabela.children[1]
        primeira_linha = tbody.children[0]
        # Coluna 2 = input
        input_col = primeira_linha.children[1]
        input_widget = input_col.children
        # Dash pattern-matching id
        assert isinstance(input_widget.id, dict)
        assert input_widget.id["type"] == "sap-sched-input-hora"
        assert input_widget.id["tipo"] in {"zppprd", "zpp_nt0001"}


class TestFormatarEm:
    """Conversao ISODate -> 'DD/MM HH:MM'."""

    def test_dt_08_15_em_none_retorna_interrogacao(self):
        assert _formatar_em(None) == "?"

    def test_em_string_invalida_retorna_interrogacao(self):
        assert _formatar_em("nao-e-data") == "?"

    def test_em_datetime(self):
        result = _formatar_em(datetime(2026, 6, 3, 14, 22))
        assert result == "03/06 14:22"

    def test_em_iso_string(self):
        result = _formatar_em("2026-06-03T14:22:00")
        assert result == "03/06 14:22"


class TestConstruirTextoUltimaAlteracao:
    """Texto pequeno embaixo do botao salvar."""

    def test_doc_sem_historico_retorna_string_vazia(self):
        assert _construir_texto_ultima_alteracao({"historico_alteracoes": []}) == ""

    def test_doc_invalido_retorna_string_vazia(self):
        assert _construir_texto_ultima_alteracao(None) == ""  # type: ignore
        assert _construir_texto_ultima_alteracao("string") == ""  # type: ignore

    def test_doc_com_historico_retorna_texto(self):
        doc = {
            "historico_alteracoes": [
                {
                    "em": datetime(2026, 6, 3, 14, 22),
                    "quem": "rgust",
                    "antes": [],
                    "depois": [],
                }
            ]
        }
        assert _construir_texto_ultima_alteracao(doc) == "Ultima alteracao: 03/06 14:22 por rgust"


class TestConstruirHistorico:
    """Lista textual de alteracoes — max 20."""

    def test_dt_08_13_historico_vazio(self):
        result = _construir_historico([])
        # Retorna div com texto, nao Ul
        assert "Nenhuma alteracao" in result.children

    def test_dt_08_14_max_20_entradas(self):
        historico = [
            {
                "em": datetime(2026, 6, 3, 14, i, 0),
                "quem": "rgust",
                "antes": [],
                "depois": [],
            }
            for i in range(25)
        ]
        result = _construir_historico(historico)
        # html.Ul com 20 li
        assert len(result.children) == 20

    def test_diff_hora(self):
        historico = [
            {
                "em": datetime(2026, 6, 3, 14, 22),
                "quem": "rgust",
                "antes": [{"tipo": "zppprd", "hora": "03:30", "ativo": True}],
                "depois": [{"tipo": "zppprd", "hora": "04:15", "ativo": True}],
            }
        ]
        result = _construir_historico(historico)
        # html.Li com texto
        li_text = result.children[0].children
        assert "zppprd: 03:30 -> 04:15" in li_text

    def test_diff_ativado(self):
        historico = [
            {
                "em": datetime(2026, 6, 3, 14, 22),
                "quem": "rgust",
                "antes": [{"tipo": "zppprd", "hora": "03:30", "ativo": False}],
                "depois": [{"tipo": "zppprd", "hora": "03:30", "ativo": True}],
            }
        ]
        result = _construir_historico(historico)
        li_text = result.children[0].children
        assert "[ativado]" in li_text

    def test_diff_desativado(self):
        historico = [
            {
                "em": datetime(2026, 6, 3, 14, 22),
                "quem": "rgust",
                "antes": [{"tipo": "zppprd", "hora": "03:30", "ativo": True}],
                "depois": [{"tipo": "zppprd", "hora": "03:30", "ativo": False}],
            }
        ]
        result = _construir_historico(historico)
        li_text = result.children[0].children
        assert "[desativado]" in li_text

    def test_entrada_invalida_pulada(self):
        historico = ["nao-e-dict", None, {"em": datetime(2026, 6, 3, 14, 22), "quem": "x", "antes": [], "depois": []}]
        result = _construir_historico(historico)  # type: ignore
        # Apenas 1 entrada valida -> 1 li
        assert len(result.children) == 1
