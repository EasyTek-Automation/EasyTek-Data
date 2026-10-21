# -*- coding: utf-8 -*-
"""Testes da janela de coleta de custo (BR-09, revisada em 25/09/2026).

Regra atual: **mês anterior + mês corrente INTEIROS** — `fim` é o ÚLTIMO dia do mês
corrente, não mais D-1. O corte em D-1 escondia do detalhe (KSB1, por BUDAT) a liquidação
de ordens (KO88), que o SAP lança com data no último dia do mês, enquanto o resumo
(ZBRCO019, por período) já a enxergava — gap de R$ 525.588,79 em set/2026.

Blindagem contra regressão: qualquer volta ao D-1 derruba `test_fim_e_ultimo_dia_do_mes`.
Sem SAP e sem Mongo (função pura).
"""
import calendar
import importlib
import sys
from datetime import datetime
from pathlib import Path

_PARENT = Path(__file__).resolve().parents[2]  # AMG_Data/
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

cc = importlib.import_module("sap-scheduler.trabalhos.custos_manut.custo_collect")


def _janela(aaaa, mm, dd, hora=4):
    return cc.janela_dois_meses(datetime(aaaa, mm, dd, hora))


# ---- fim = último dia do mês corrente (o que fecha o gap barra × detalhe) -------------

def test_fim_e_ultimo_dia_do_mes():
    _, fim = _janela(2026, 9, 25)
    assert (fim.year, fim.month, fim.day) == (2026, 9, 30)


def test_fim_nao_e_d_menos_1():
    # regressão: com D-1 o fim seria 24/09 e a liquidação de 30/09 sumiria do detalhe
    _, fim = _janela(2026, 9, 25)
    assert fim.day != 24


def test_fim_respeita_mes_de_30_e_de_31():
    assert _janela(2026, 4, 10)[1].day == 30
    assert _janela(2026, 7, 10)[1].day == 31


def test_fim_em_fevereiro():
    ano = 2026
    assert _janela(ano, 2, 15)[1].day == calendar.monthrange(ano, 2)[1]


# ---- início = 1º dia do mês anterior; âncora em `agora`, não em ontem ------------------

def test_inicio_e_primeiro_dia_do_mes_anterior():
    ini, _ = _janela(2026, 9, 25)
    assert (ini.year, ini.month, ini.day) == (2026, 8, 1)


def test_dia_primeiro_inclui_o_mes_novo():
    """Âncora em `agora` (não em ontem): no dia 1º o mês que começou tem de estar na janela.

    Com âncora em ontem + fim no último dia, 01/10 daria 01/08..30/09 — outubro ficaria
    de fora até o dia 2.
    """
    ini, fim = _janela(2026, 10, 1)
    assert (ini.month, fim.month) == (9, 10)
    assert fim.day == 31


def test_virada_de_ano():
    ini, fim = _janela(2027, 1, 1)
    assert (ini.year, ini.month, ini.day) == (2026, 12, 1)
    assert (fim.year, fim.month, fim.day) == (2027, 1, 31)


# ---- a janela cobre exatamente 2 períodos (o que o custo_orcado deriva) ---------------

def test_janela_cobre_exatamente_dois_meses():
    for data in [(2026, 9, 25), (2026, 10, 1), (2027, 1, 1), (2026, 2, 28), (2026, 3, 1)]:
        ini, fim = _janela(*data)
        meses = (fim.year - ini.year) * 12 + (fim.month - ini.month) + 1
        assert meses == 2, f"{data} -> {meses} meses"
