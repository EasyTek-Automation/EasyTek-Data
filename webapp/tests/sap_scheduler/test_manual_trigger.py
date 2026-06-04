"""Testes do disparo manual de coleta SAP (Bloco L — botão "Rodar agora").

Cobre: gate de autorização por perfil/level, guard de job já ativo, mapeamento
de status do insert (inserido/dedup/erro) e visibilidade do componente.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pymongo.errors import DuplicateKeyError, PyMongoError

from src.sap_scheduler.manual_trigger import (
    _btn_id,
    build_rerun_controls,
    inserir_job_manual,
    pode_disparar_manual,
)


def _user(perfil="manutencao", level=1, auth=True):
    """Usuário fake com a interface que `pode_disparar_manual` lê."""
    return SimpleNamespace(is_authenticated=auth, perfil=perfil, level=level)


def _db_mock():
    """db subscriptável -> coll MagicMock (db[collection] sempre a mesma coll)."""
    db = MagicMock()
    coll = MagicMock()
    db.__getitem__.return_value = coll
    return db, coll


# ---------- pode_disparar_manual ----------

@pytest.mark.parametrize("perfil,level,esperado", [
    ("manutencao", 1, True),
    ("producao", 1, True),
    ("producao", 3, True),
    ("admin", 1, True),
    ("qualidade", 3, False),   # perfil fora da whitelist
    ("utilidades", 2, False),
    ("manutencao", 0, False),  # level abaixo do mínimo
])
def test_pode_disparar_manual_gate(perfil, level, esperado):
    assert pode_disparar_manual(_user(perfil, level)) is esperado


def test_pode_disparar_manual_anonimo():
    assert pode_disparar_manual(None) is False
    assert pode_disparar_manual(_user(auth=False)) is False


# ---------- build_rerun_controls (visibilidade) ----------

def test_controls_vazio_para_nao_autorizado():
    comp = build_rerun_controls(_user("qualidade", 3))
    assert comp.children is None  # html.Div() vazio — sem botões, sem ids


def test_controls_renderiza_para_autorizado():
    comp = build_rerun_controls(_user("manutencao", 1))
    # html.Div([ html.Div(botoes), dbc.Toast ]) — 2 filhos
    assert isinstance(comp.children, list) and len(comp.children) == 2
    botoes = comp.children[0].children
    ids = {b.id for b in botoes}
    assert _btn_id("zppprd") in ids
    assert _btn_id("zpp_nt0001") in ids


# ---------- inserir_job_manual ----------

def test_inserir_tipo_invalido():
    db, coll = _db_mock()
    assert inserir_job_manual(db, "tipo_inexistente", "America/Sao_Paulo") == "erro"
    coll.insert_one.assert_not_called()


def test_inserir_guard_job_ativo():
    db, coll = _db_mock()
    coll.find_one.return_value = {"_id": "x"}  # já há pendente/executando
    assert inserir_job_manual(db, "zppprd", "America/Sao_Paulo") == "ja_em_andamento"
    coll.insert_one.assert_not_called()


def test_inserir_sucesso():
    db, coll = _db_mock()
    coll.find_one.return_value = None
    coll.insert_one.return_value = SimpleNamespace(inserted_id="abc123")
    assert inserir_job_manual(db, "zpp_nt0001", "America/Sao_Paulo") == "inserido"
    doc = coll.insert_one.call_args[0][0]
    assert doc["tipo"] == "zpp_nt0001"
    assert doc["status"] == "pendente"
    assert doc["parametros"] == {"disparo_manual": True}
    assert doc["agendado_para"].second == 0  # arredondado pro minuto


def test_inserir_dedup_mesmo_minuto():
    db, coll = _db_mock()
    coll.find_one.return_value = None
    coll.insert_one.side_effect = DuplicateKeyError("dup")
    assert inserir_job_manual(db, "zppprd", "America/Sao_Paulo") == "dedup"


def test_inserir_erro_mongo():
    db, coll = _db_mock()
    coll.find_one.side_effect = PyMongoError("offline")
    assert inserir_job_manual(db, "zppprd", "America/Sao_Paulo") == "erro"
