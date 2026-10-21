# -*- coding: utf-8 -*-
"""Baseline de retrocompatibilidade do cadastro de funcionários do GanttManagement (B4/BR-11.1).

Prova ANTES × DEPOIS que estender `gantt_employees` (campos siglas_sap/jornada_min do
hh-management) NÃO quebra o GanttManagement. Os testes de "comportamento preservado" têm de
passar nas DUAS versões (antes e depois da extensão). Os testes de "capacidade nova" só
passam depois. Mocka a collection (sem Mongo real).

Alinhado ao princípio "rodar baseline ANTES de editar": prova pass/fail, não infere.
"""
from unittest.mock import MagicMock, patch

from src.utils import gantt_db


def _fake_col():
    col = MagicMock()
    col.insert_one.return_value = MagicMock(inserted_id="newid123")
    col.update_one.return_value = MagicMock(modified_count=1)
    return col


# ---- comportamento PRESERVADO (verde antes E depois da extensão) ---------------------

def test_create_employee_campos_core_preservados():
    col = _fake_col()
    with patch.object(gantt_db, "_col", return_value=col):
        gantt_db.create_employee({"nome": "Carlos", "turno_padrao": "B"})
    doc = col.insert_one.call_args[0][0]
    assert doc["nome"] == "Carlos"
    assert doc["turno_padrao"] == "B"
    assert doc["ativo"] is True
    assert "criado_em" in doc and "atualizado_em" in doc

def test_update_employee_atualiza_nome_e_turno():
    col = _fake_col()
    with patch.object(gantt_db, "_col", return_value=col):
        ok = gantt_db.update_employee("507f1f77bcf86cd799439011", {"nome": "Novo", "turno_padrao": "C"})
    assert ok is True
    setdoc = col.update_one.call_args[0][1]["$set"]
    assert setdoc["nome"] == "Novo"
    assert setdoc["turno_padrao"] == "C"
    assert "atualizado_em" in setdoc

def test_update_employee_ignora_campo_desconhecido():
    """Campo realmente desconhecido (não whitelisted) continua descartado — segurança preservada."""
    col = _fake_col()
    with patch.object(gantt_db, "_col", return_value=col):
        gantt_db.update_employee("507f1f77bcf86cd799439011", {"nome": "X", "hacker": "drop table"})
    setdoc = col.update_one.call_args[0][1]["$set"]
    assert "hacker" not in setdoc
    assert setdoc["nome"] == "X"

def test_get_all_employees_exclui_foto_bytes_e_deriva_has_photo():
    col = MagicMock()
    cursor = MagicMock()
    cursor.sort.return_value = [
        {"_id": "a", "nome": "Carlos", "turno_padrao": "B", "foto_mime": "image/jpeg"},
        {"_id": "b", "nome": "Ana", "turno_padrao": "A"},
    ]
    col.find.return_value = cursor
    with patch.object(gantt_db, "_col", return_value=col):
        out = gantt_db.get_all_employees()
    # projeção exclui foto_bytes
    assert col.find.call_args[0][1] == {"foto_bytes": 0}
    assert out[0]["_has_photo"] is True
    assert out[1]["_has_photo"] is False


# ---- capacidade NOVA (só passa DEPOIS da extensão — B4) ------------------------------

def test_create_employee_aceita_siglas_e_jornada():
    col = _fake_col()
    with patch.object(gantt_db, "_col", return_value=col):
        gantt_db.create_employee({"nome": "Carlos", "turno_padrao": "B",
                                  "siglas_sap": ["CDAMASIO"], "jornada_min": 480})
    doc = col.insert_one.call_args[0][0]
    assert doc.get("siglas_sap") == ["CDAMASIO"]
    assert doc.get("jornada_min") == 480

def test_create_employee_defaults_siglas_quando_ausente():
    col = _fake_col()
    with patch.object(gantt_db, "_col", return_value=col):
        gantt_db.create_employee({"nome": "Ana", "turno_padrao": "A"})
    doc = col.insert_one.call_args[0][0]
    assert doc.get("siglas_sap") == []        # default aditivo
    assert doc.get("jornada_min") is None

def test_update_employee_grava_siglas_e_jornada():
    col = _fake_col()
    with patch.object(gantt_db, "_col", return_value=col):
        gantt_db.update_employee("507f1f77bcf86cd799439011", {"siglas_sap": ["JSILVA", "J.SILVA"], "jornada_min": 360})
    setdoc = col.update_one.call_args[0][1]["$set"]
    assert setdoc["siglas_sap"] == ["JSILVA", "J.SILVA"]
    assert setdoc["jornada_min"] == 360


# ---- mão de obra temporária (GantManagement BR-25 / DS-18 §6) -------------------------

def test_create_employee_fixo_nao_grava_campos_de_temporario():
    col = _fake_col()
    with patch.object(gantt_db, "_col", return_value=col):
        gantt_db.create_employee({"nome": "Ana", "turno_padrao": "A"})
    doc = col.insert_one.call_args[0][0]
    assert "temporario" not in doc and "periodos_quadro" not in doc   # retrocompat: doc idêntico

def test_create_employee_temporario_nasce_fora_do_quadro():
    col = _fake_col()
    with patch.object(gantt_db, "_col", return_value=col):
        gantt_db.create_employee({"nome": "Empresa X", "turno_padrao": "B", "temporario": True})
    doc = col.insert_one.call_args[0][0]
    assert doc["temporario"] is True
    assert doc["periodos_quadro"] == []

def test_update_employee_grava_temporario_e_periodos():
    col = _fake_col()
    ps = [{"de": "2026-W42", "ate": None}]
    with patch.object(gantt_db, "_col", return_value=col):
        gantt_db.update_employee("507f1f77bcf86cd799439011", {"temporario": True, "periodos_quadro": ps})
    setdoc = col.update_one.call_args[0][1]["$set"]
    assert setdoc["temporario"] is True
    assert setdoc["periodos_quadro"] == ps



# ---- funcionário novo conta a partir da semana do cadastro (GantManagement BR-26 / DS-20) --

def test_create_employee_fixo_com_semana_grava_periodo_aberto():
    col = _fake_col()
    with patch.object(gantt_db, "_col", return_value=col):
        gantt_db.create_employee({"nome": "João", "turno_padrao": "A", "semana_cadastro": "2026-W41"})
    doc = col.insert_one.call_args[0][0]
    assert doc["periodos_quadro"] == [{"de": "2026-W41", "ate": None}]
    assert "temporario" not in doc and "semana_cadastro" not in doc

def test_create_employee_temporario_com_semana_continua_fora_do_quadro():
    col = _fake_col()
    with patch.object(gantt_db, "_col", return_value=col):
        gantt_db.create_employee({"nome": "Empresa Y", "turno_padrao": "B", "temporario": True,
                                  "semana_cadastro": "2026-W41"})
    doc = col.insert_one.call_args[0][0]
    assert doc["temporario"] is True
    assert doc["periodos_quadro"] == []
