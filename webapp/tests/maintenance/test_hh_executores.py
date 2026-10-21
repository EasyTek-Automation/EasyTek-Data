# -*- coding: utf-8 -*-
"""Testes do de/para de executores (PERNR persona → nome real) — SP-06.6 / BR-14.

Lógica pura, sem Mongo: monkeypatcha o mapa código→nome. Cobre a tradução usada no modal de
detalhe da ordem (código cru do IW47 → nome) + a integridade do roster_executores.json.
"""
import json
import os
from unittest.mock import patch

from src.utils import hh_executores


_MAPA = {
    "89990001": "Pessoa de exemplo 22",
    "89990013": "Pessoa de exemplo 05",
    "89990018": "Pessoa de exemplo 06",
    "89990024": "Pessoa de exemplo 04",
    "89990000": hh_executores.LABEL_SEM_EXECUTOR,
}


# ---- tradução (o que o modal usa) ----------------------------------------------------

def test_nome_executor_tecnico():
    with patch.object(hh_executores, "mapa_executores", return_value=_MAPA):
        assert hh_executores.nome_executor("89990001") == "Pessoa de exemplo 22"

def test_nome_executor_terceiro():
    with patch.object(hh_executores, "mapa_executores", return_value=_MAPA):
        assert hh_executores.nome_executor("89990024") == "Pessoa de exemplo 04"

def test_nome_executor_sem_executor():
    with patch.object(hh_executores, "mapa_executores", return_value=_MAPA):
        assert hh_executores.nome_executor("89990000") == hh_executores.LABEL_SEM_EXECUTOR

def test_nome_executor_none():
    assert hh_executores.nome_executor(None) == hh_executores.LABEL_SEM_EXECUTOR

def test_nome_executor_zero_e_sem_executor():
    # IW47 usa "0"/vazio para ausência de executor → não pode virar código cru
    assert hh_executores.nome_executor("0") == hh_executores.LABEL_SEM_EXECUTOR
    assert hh_executores.nome_executor("") == hh_executores.LABEL_SEM_EXECUTOR

def test_nomes_executores_descarta_zero_da_lista():
    with patch.object(hh_executores, "mapa_executores", return_value=_MAPA):
        out = hh_executores.nomes_executores(["89990013", "0", "89990001"])
        assert out == ["Pessoa de exemplo 05", "Pessoa de exemplo 22"]  # "0" sumiu

def test_nome_executor_desconhecido_cai_no_codigo():
    # código fora do roster não pode sumir — fallback = o próprio código
    with patch.object(hh_executores, "mapa_executores", return_value=_MAPA):
        assert hh_executores.nome_executor("77777777") == "77777777"

def test_nomes_executores_lista_preserva_ordem_e_dedup():
    with patch.object(hh_executores, "mapa_executores", return_value=_MAPA):
        out = hh_executores.nomes_executores(["89990013", "89990018", "89990013"])
        assert out == ["Pessoa de exemplo 05", "Pessoa de exemplo 06"]

def test_nomes_executores_vazio():
    assert hh_executores.nomes_executores(None) == []
    assert hh_executores.nomes_executores([]) == []


# ---- integridade do roster (fonte autoritativa) --------------------------------------

def _roster():
    caminho = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "src", "data", "roster_executores.json",
    )
    with open(caminho, encoding="utf-8") as fh:
        return json.load(fh)

def test_roster_contagens_batem_com_meta():
    r = _roster()
    ex = r["executores"]
    tecnicos = [v for v in ex.values() if v.get("tipo") == "tecnico"]
    terceiros = [v for v in ex.values() if v.get("tipo") == "terceiro"]
    assert len(tecnicos) == r["_meta"]["total_tecnicos"] == 0
    assert len(terceiros) == r["_meta"]["total_terceiros"] == 0

def test_roster_tecnicos_validados_conferem_inicial():
    # crosscheck SAP: técnicos do lote original (com inicial_confere) batem 100%.
    # Os adicionados pós-crosscheck (campo add_em) são isentos — nome informado pelo PCM.
    ex = _roster()["executores"]
    for cod, v in ex.items():
        if v.get("tipo") == "tecnico" and "add_em" not in v:
            assert v.get("inicial_confere") is True, f"{cod} não confere"

def test_roster_sem_executor_tem_nome_nulo():
    ex = _roster()["executores"]
    assert ex["89990000"]["nome"] is None
