# -*- coding: utf-8 -*-
"""Testes de `montar_doc` (backlog/_classifica): propagação dos campos crus da coleta ao doc Mongo.

Regressão B30: `status_usuario` (USTXT) era coletado em `coletar_ordens` mas o `montar_doc` não o
copiava pro doc → `sap_backlog.status_usuario` sempre null → quadro mostrava tudo "Pendente".
"""
import importlib
import sys
from datetime import datetime
from pathlib import Path

_PARENT = Path(__file__).resolve().parents[2]  # AMG_Data/
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

_classifica = importlib.import_module("sap-scheduler.trabalhos.backlog._classifica")


def test_montar_doc_propaga_status_usuario():
    ordem = {"ordem": "5012522", "tipo": "YPM1", "descricao": "TROCA ROLAMENTO",
             "local_instalacao": "BR02-0100-1600", "centro_operacao_0010": "Z10",
             "status_usuario": "ENTR"}
    doc = _classifica.montar_doc(ordem, "20260715.0900", datetime(2026, 7, 15))
    assert doc["status_usuario"] == "ENTR"        # <- o campo tem que chegar no doc final


def test_montar_doc_status_usuario_none_quando_ausente():
    ordem = {"ordem": "5012522", "tipo": "YPM1", "centro_operacao_0010": "Z10"}
    doc = _classifica.montar_doc(ordem, "20260715.0900", datetime(2026, 7, 15))
    assert doc["status_usuario"] is None          # ausente na coleta → None (não KeyError)


# ---- derivar_disciplina: centros com destino próprio (B34, 2026-07-17) ----------------

def test_derivar_disciplina_z1_z2_mantem():
    assert _classifica.derivar_disciplina("Z10") == "Mecanica"
    assert _classifica.derivar_disciplina("Z15") == "Mecanica"
    assert _classifica.derivar_disciplina("MEC") == "Mecanica"
    assert _classifica.derivar_disciplina("Z20") == "Eletrica"
    assert _classifica.derivar_disciplina("Z23") == "Eletrica"


def test_derivar_disciplina_z03_terceiros_z01_gestao():
    # B34: Z03 e Z01 deixam de cair em NaoClassificado
    assert _classifica.derivar_disciplina("Z03") == "Terceiros"
    assert _classifica.derivar_disciplina("Z01") == "Gestao"
    assert _classifica.derivar_disciplina(" z03 ") == "Terceiros"   # trim + case


def test_derivar_disciplina_z04_ferramentaria():
    # B37: Z04 (ferramentaria/matrizes) deixa de cair em NaoClassificado
    assert _classifica.derivar_disciplina("Z04") == "Ferramentaria"
    assert _classifica.derivar_disciplina(" z04 ") == "Ferramentaria"   # trim + case


def test_derivar_disciplina_resto_segue_naoclassificado():
    # Z02 = pendência real; MAN/sem-centro = fora da fila (B37) — todos NaoClassificado no daemon
    for c in ("Z02", "MAN", "", None):
        assert _classifica.derivar_disciplina(c) == "NaoClassificado"
