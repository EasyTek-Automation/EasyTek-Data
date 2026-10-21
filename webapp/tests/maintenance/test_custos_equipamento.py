"""Testes de `custos/hierarquia.nome_equipamento` — de/para centro de custo → fatia da rosca.

Cobre a ponte KPI (linhas com MTBF/MTTR), o fallback 'Apoio/Admin' e a inclusão de linhas
de produção sem KPI próprio como fatia dedicada (ex: Decapado — centro 201300).
"""
from __future__ import annotations

from src.custos import hierarquia as H


def test_centro_kpi_vira_nome_do_equipamento():
    # 206001 = LCT-08 → TRANS001 → nome via EQUIPAMENTO_NOMES (fonte única dos KPIs)
    nome = H.nome_equipamento("206001")
    assert nome not in (H.EQUIP_APOIO, "206001")  # traduziu pra nome de equipamento real


def test_centro_administrativo_cai_em_apoio():
    # 209000 = DIREÇÃO DE UNIDADE → sem linha KPI, sem fatia extra → Apoio/Admin
    assert H.nome_equipamento("209000") == H.EQUIP_APOIO


def test_decapado_vira_fatia_propria():
    # 201300 = LINHA DECAPADO → linha de produção sem KPI, mas fatia própria (não Apoio/Admin)
    assert H.nome_equipamento("201300") == "Decapado"


def test_solda_laser_vira_fatia_propria():
    # 201000 = LINHA SOLDA LASER → sem KPI, promovido a fatia própria (não Apoio/Admin)
    assert H.nome_equipamento("201000") == "Solda Laser"


def test_centro_desconhecido_cai_em_apoio():
    assert H.nome_equipamento("999999") == H.EQUIP_APOIO
