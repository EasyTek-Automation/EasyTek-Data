# -*- coding: utf-8 -*-
"""Eixo 'data_criacao' (ERDAT) com fallback p/ 'data_inicio' (GSTRP) quando a criação
está ausente — caso do backlog sintetizado da IW37, que não traz ERDAT. Garante que as
barras mensais e os insights não ficam vazios e batem com a regra de idade do HH."""
from datetime import datetime

from src.utils import backlog_data as bd


def _ord(ordem, di, dc):
    return {"ordem": ordem, "data_inicio": di, "data_criacao": dc,
            "tipo": "Corretiva", "disciplina": "Mecanica"}


def test_data_eixo_fallback_criacao_ausente():
    o = _ord("1", datetime(2026, 3, 10), None)
    # eixo criação sem ERDAT → cai para início
    assert bd._data_eixo(o, "data_criacao") == datetime(2026, 3, 10)
    # eixo início nunca faz fallback
    assert bd._data_eixo(_ord("2", None, datetime(2026, 1, 1)), "data_inicio") is None


def test_data_eixo_usa_criacao_quando_presente():
    o = _ord("1", datetime(2026, 3, 10), datetime(2026, 1, 5))
    assert bd._data_eixo(o, "data_criacao") == datetime(2026, 1, 5)


def test_barras_nao_vazia_com_criacao_ausente():
    ordens = [_ord("1", datetime(2026, 3, 10), None),
              _ord("2", datetime(2026, 3, 20), None)]
    labels, vals = bd.dados_barras_mes(ordens, eixo="data_criacao")
    assert labels == ["03/2026"]
    assert vals == [2]


def test_insights_mais_antiga_com_fallback():
    hoje = datetime(2026, 4, 1)
    ordens = [_ord("ANTIGA", datetime(2026, 1, 1), None),
              _ord("NOVA", datetime(2026, 3, 25), None)]
    res = bd.insights(ordens, hoje=hoje, eixo="data_criacao")
    assert res["mais_antiga_ordem"] == "ANTIGA"
    assert res["mais_antiga_dias"] == 90
