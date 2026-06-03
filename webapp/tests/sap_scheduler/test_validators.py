"""Testes do validators.py (DS-06 / SP-07 RF-07-08..13).

Cobre DT-06-09..13 do SDD sap-scheduler.
"""
from __future__ import annotations

import pytest

from src.sap_scheduler.validators import (
    HORA_REGEX,
    TIPOS_VALIDOS,
    validar_agendamentos,
    validar_item,
)


class TestValidarItem:
    """validar_item levanta ValueError com mensagem especifica."""

    def test_aceita_item_valido(self):
        validar_item({"tipo": "zppprd", "hora": "03:30", "ativo": True})
        validar_item({"tipo": "zpp_nt0001", "hora": "23:59", "ativo": False})

    def test_rejeita_nao_dict(self):
        with pytest.raises(ValueError, match="dict"):
            validar_item("nao-e-dict")
        with pytest.raises(ValueError, match="dict"):
            validar_item(None)

    def test_dt_06_09_tipo_invalido(self):
        with pytest.raises(ValueError, match="tipo invalido"):
            validar_item({"tipo": "abc", "hora": "03:30", "ativo": True})

    def test_tipo_ausente(self):
        with pytest.raises(ValueError, match="tipo invalido"):
            validar_item({"hora": "03:30", "ativo": True})

    def test_dt_06_10_hora_invalida(self):
        with pytest.raises(ValueError, match="hora invalida"):
            validar_item({"tipo": "zppprd", "hora": "25:00", "ativo": True})
        with pytest.raises(ValueError, match="hora invalida"):
            validar_item({"tipo": "zppprd", "hora": "12:60", "ativo": True})
        with pytest.raises(ValueError, match="hora invalida"):
            validar_item({"tipo": "zppprd", "hora": "abc", "ativo": True})

    def test_dt_06_11_ativo_invalido_string(self):
        with pytest.raises(ValueError, match="ativo invalido"):
            validar_item({"tipo": "zppprd", "hora": "03:30", "ativo": "true"})

    def test_ativo_invalido_int(self):
        # bool sao subclasses de int em Python; 1 e True isinstance(int, bool)
        # mas isinstance(1, bool) e False — int puro e rejeitado
        with pytest.raises(ValueError, match="ativo invalido"):
            validar_item({"tipo": "zppprd", "hora": "03:30", "ativo": 1})

    def test_hora_regex_extremos(self):
        # 00:00 ate 23:59 sao validos
        assert HORA_REGEX.match("00:00")
        assert HORA_REGEX.match("23:59")
        assert HORA_REGEX.match("12:34")
        assert not HORA_REGEX.match("24:00")
        assert not HORA_REGEX.match("12:60")
        assert not HORA_REGEX.match("3:30")  # falta zero a esquerda

    def test_tipos_validos_e_frozenset(self):
        assert isinstance(TIPOS_VALIDOS, frozenset)
        assert "zppprd" in TIPOS_VALIDOS
        assert "zpp_nt0001" in TIPOS_VALIDOS
        assert "iw47" not in TIPOS_VALIDOS  # tipo futuro fica fora


class TestValidarAgendamentos:
    """validar_agendamentos: lista + dedup + strip."""

    def test_aceita_lista_valida(self):
        novos = [
            {"tipo": "zppprd", "hora": "03:30", "ativo": True},
            {"tipo": "zpp_nt0001", "hora": "04:00", "ativo": True},
        ]
        validar_agendamentos(novos)

    def test_aceita_lista_vazia(self):
        # lista vazia = todos pausados; comportamento valido (BR-12)
        validar_agendamentos([])

    def test_rejeita_nao_lista(self):
        with pytest.raises(ValueError, match="list"):
            validar_agendamentos("nao-lista")
        with pytest.raises(ValueError, match="list"):
            validar_agendamentos({"tipo": "zppprd"})

    def test_dt_06_12_tipo_duplicado(self):
        novos = [
            {"tipo": "zppprd", "hora": "03:30", "ativo": True},
            {"tipo": "zppprd", "hora": "04:00", "ativo": True},
        ]
        with pytest.raises(ValueError, match="duplicado"):
            validar_agendamentos(novos)

    def test_dt_06_13_strip_whitespace(self):
        novos = [
            {"tipo": "zppprd", "hora": " 03:30 ", "ativo": True},
        ]
        validar_agendamentos(novos)
        # MUTA o dict — hora final stripada
        assert novos[0]["hora"] == "03:30"

    def test_strip_so_aplica_se_hora_for_string(self):
        # Se hora nao for string, validar_item levanta antes
        novos = [{"tipo": "zppprd", "hora": 123, "ativo": True}]
        with pytest.raises(ValueError, match="hora invalida"):
            validar_agendamentos(novos)

    def test_falha_propaga_mensagem_de_validar_item(self):
        novos = [{"tipo": "invalido", "hora": "03:30", "ativo": True}]
        with pytest.raises(ValueError, match="tipo invalido"):
            validar_agendamentos(novos)
