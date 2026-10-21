# -*- coding: utf-8 -*-
"""Testes das funções puras da coleta HH (B1) — parsing (BR-10) e agregação (BR-03).

Pacote do daemon tem hífen (`sap-scheduler`) → carregado via importlib com o parent
(`AMG_Data/`) no sys.path, igual a test_executor_retry.py. Sem SAP, sem Mongo: exercita
o parser PT, a exclusão da linha de total e a agregação (dedup planejado / soma realizado).
"""
import importlib
import sys
from datetime import datetime
from pathlib import Path

_PARENT = Path(__file__).resolve().parents[2]  # AMG_Data/
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

_parse = importlib.import_module("sap-scheduler.trabalhos.hh._parse")
_agg = importlib.import_module("sap-scheduler.trabalhos.hh._agg")
_coleta = importlib.import_module("sap-scheduler.trabalhos.hh._coleta")
hh = importlib.import_module("sap-scheduler.trabalhos.hh.hh")

_HORA = datetime(2026, 6, 30, 4, 0, 0)


# ---- parsing (BR-10) -----------------------------------------------------------------

def test_parse_num_milhar_e_decimal():
    assert _parse.parse_num("13.900,000") == 13900.0

def test_parse_num_negativo_no_fim():
    assert _parse.parse_num("11.000-") == -11000.0

def test_parse_num_ja_numerico():
    assert _parse.parse_num(105) == 105.0

def test_parse_num_vazio():
    assert _parse.parse_num("") is None
    assert _parse.parse_num(None) is None

def test_parse_min_arredonda():
    assert _parse.parse_min("59,6") == 60

def test_parse_data_pt():
    assert _parse.parse_data("05.05.2026") == datetime(2026, 5, 5)

def test_linha_total_detectada():
    assert _parse.eh_linha_total({"AUFNR": "", "VORNR": "", "ISMNW": "610"}) is True
    assert _parse.eh_linha_total({"AUFNR": "5018863", "VORNR": "0010"}) is False

def test_limpar_remove_total_e_ruido():
    rows = [
        {"AUFNR": "5018863", "VORNR": "0010", "ISMNW": "60"},
        {"AUFNR": "", "VORNR": "", "ISMNW": "60"},      # total
        {"AUFNR": "", "VORNR": "0020", "ISMNW": "1"},   # ruído (sem ordem)
    ]
    limpas, info = _parse.limpar_linhas(rows)
    assert len(limpas) == 1
    assert info["removidas"] == 2


# ---- agregação planejado (BR-03: dedup, não soma) ------------------------------------

def test_planejado_deduplica_nao_soma():
    docs, info = _agg.agregar_planejado(_coleta.mock_planejado(), "20260630.0400", _HORA)
    by = {d["ordem"]: d for d in docs}
    # 5018863 aparece 2x com ARBEI=120 → vale 120 (único), nunca 240
    assert by["5018863"]["planejado_min"] == 120
    assert by["5018901"]["planejado_min"] == 480
    assert info["total_planejado_min"] == 600   # 120 + 480 (não 720)
    assert info["operacoes"] == 2

def test_planejado_centro_e_data():
    docs, _ = _agg.agregar_planejado(_coleta.mock_planejado(), "c", _HORA)
    by = {d["ordem"]: d for d in docs}
    assert by["5018863"]["centro_planejado"] == "Z210"
    assert by["5018863"]["data_inicio_plan"] == datetime(2026, 6, 1)


# ---- agregação realizado (BR-03: soma das confirmações) ------------------------------

def test_realizado_soma_confirmacoes():
    docs, info = _agg.agregar_realizado(_coleta.mock_realizado(), "c", _HORA)
    by = {d["ordem"]: d for d in docs}
    # 5018863 tem 2 apontamentos (60+50) → 110
    assert by["5018863"]["realizado_min"] == 110
    assert by["5018901"]["realizado_min"] == 500
    assert info["total_realizado_min"] == 610   # bate com a linha de total do mock

def test_realizado_executores_distintos():
    docs, _ = _agg.agregar_realizado(_coleta.mock_realizado(), "c", _HORA)
    by = {d["ordem"]: d for d in docs}
    assert by["5018863"]["executores"] == ["CDAMASIO"]   # 2 apontamentos, 1 executor
    assert by["5018863"]["status_sap"] == "LIB ENCE"


# ---- sanidade BR-10 (soma bate com linha de total) -----------------------------------

def test_sanidade_realizado_bate():
    rows = _coleta.mock_realizado()
    _docs, info = _agg.agregar_realizado(rows, "c", _HORA)
    assert _agg.checar_sanidade_total(rows, info["total_realizado_min"], "ISMNW") is True

def test_sanidade_realizado_diverge():
    rows = _coleta.mock_realizado()
    # força divergência: total calculado errado
    assert _agg.checar_sanidade_total(rows, 999, "ISMNW") is False


# ---- B38/B39: coleta do realizado (união janela ∪ abertas) ----------------------------

def test_coletar_dirigido_mock_usa_mock_realizado():
    """B38/B39/B40: o caminho dirigido (multisseleção AUFNR→IW47) sob mock_sap devolve mock_realizado()."""
    from types import SimpleNamespace
    ctx = SimpleNamespace(cfg=SimpleNamespace(mock_sap=True))
    assert hh._coletar_dirigido(ctx) == _coleta.mock_realizado()


# ---- B40: AUFNR-alvo = abertas do IW39 ∪ atribuídas no quadro (hh_planejamento) --------

def test_aufnr_alvo_une_abertas_e_atribuidas():
    from types import SimpleNamespace
    from unittest.mock import patch
    _blc = importlib.import_module("sap-scheduler.trabalhos.backlog._coleta")

    class _Coll:
        def distinct(self, campo):
            return ["5014864", "5016851", "5000001", None]   # atribuídas (2 fora das abertas) + None
    class _DB:
        def __getitem__(self, nome):
            assert nome == "hh_planejamento"
            return _Coll()

    ctx = SimpleNamespace(db=_DB())
    with patch.object(_blc, "_iw39_ordens", return_value={"5000001": {}, "5000002": {}}):
        alvo = set(hh._aufnr_alvo(ctx, session=object()))
    # união das abertas (5000001/2) com as atribuídas (5014864/5016851/5000001); None descartado
    assert alvo == {"5000001", "5000002", "5014864", "5016851"}

def test_aufnr_alvo_degrada_para_abertas_se_mongo_falha():
    from types import SimpleNamespace
    from unittest.mock import patch
    _blc = importlib.import_module("sap-scheduler.trabalhos.backlog._coleta")

    class _DBboom:
        def __getitem__(self, nome):
            raise RuntimeError("mongo indisponível")

    ctx = SimpleNamespace(db=_DBboom())
    with patch.object(_blc, "_iw39_ordens", return_value={"A": {}, "B": {}}):
        alvo = set(hh._aufnr_alvo(ctx, session=object()))
    assert alvo == {"A", "B"}   # degradação graciosa: só as abertas


# ---- realizado_por_dia (BR-13/DS-13 — quebra por dia de execução ISDD) ---------------

def test_realizado_por_dia_multidia():
    """Operação apontada em 2 dias → soma por data; total inalterado (Σ por-dia == total)."""
    rows = [
        {"AUFNR": "5019000", "VORNR": "0010", "ISMNW": "60", "ISMNE": "MIN",
         "ISDD": "21.07.2026", "PERNR": "A"},
        {"AUFNR": "5019000", "VORNR": "0010", "ISMNW": "30", "ISMNE": "MIN",
         "ISDD": "21.07.2026", "PERNR": "A"},
        {"AUFNR": "5019000", "VORNR": "0010", "ISMNW": "90", "ISMNE": "MIN",
         "ISDD": "22.07.2026", "PERNR": "A"},
    ]
    docs, _ = _agg.agregar_realizado(rows, "c", _HORA)
    d = docs[0]
    assert d["realizado_min"] == 180
    assert d["realizado_por_dia"] == {"2026-07-21": 90, "2026-07-22": 90}
    assert sum(d["realizado_por_dia"].values()) == d["realizado_min"]


def test_realizado_por_dia_fallback_budat():
    """ISDD vazio → usa BUDAT como data do apontamento."""
    rows = [
        {"AUFNR": "5019001", "VORNR": "0010", "ISMNW": "45", "ISMNE": "MIN",
         "ISDD": "", "BUDAT": "23.07.2026", "PERNR": "B"},
    ]
    docs, _ = _agg.agregar_realizado(rows, "c", _HORA)
    assert docs[0]["realizado_por_dia"] == {"2026-07-23": 45}


def test_realizado_por_dia_sem_data_fica_fora_do_por_dia():
    """Confirmação sem ISDD nem BUDAT conta no total mas NÃO no por-dia (Σ por-dia < total)."""
    rows = [
        {"AUFNR": "5019002", "VORNR": "0010", "ISMNW": "40", "ISMNE": "MIN",
         "ISDD": "24.07.2026", "PERNR": "C"},
        {"AUFNR": "5019002", "VORNR": "0010", "ISMNW": "10", "ISMNE": "MIN",
         "ISDD": "", "BUDAT": "", "PERNR": "C"},
    ]
    docs, _ = _agg.agregar_realizado(rows, "c", _HORA)
    d = docs[0]
    assert d["realizado_min"] == 50
    assert d["realizado_por_dia"] == {"2026-07-24": 40}
    assert sum(d["realizado_por_dia"].values()) <= d["realizado_min"]


def test_realizado_por_dia_linha_total_ignorada():
    """A linha de total do ALV (AUFNR/VORNR vazios) não vira operação nem entra no por-dia."""
    rows = [
        {"AUFNR": "5019003", "VORNR": "0010", "ISMNW": "70", "ISMNE": "MIN",
         "ISDD": "25.07.2026", "PERNR": "D"},
        {"AUFNR": "", "VORNR": "", "ISMNW": "70", "ISMNE": "MIN"},  # linha de total
    ]
    docs, _ = _agg.agregar_realizado(rows, "c", _HORA)
    assert len(docs) == 1
    assert docs[0]["realizado_por_dia"] == {"2026-07-25": 70}


def test_realizado_por_dia_retrocompat_mock_sem_isdd():
    """Mock legado (sem ISDD/BUDAT): realizado_por_dia vazio, realizado_min intacto."""
    docs, info = _agg.agregar_realizado(_coleta.mock_realizado(), "c", _HORA)
    by = {d["ordem"]: d for d in docs}
    assert by["5018863"]["realizado_min"] == 110          # inalterado
    assert by["5018863"]["realizado_por_dia"] == {}        # sem data → vazio
    assert info["total_realizado_min"] == 610              # sanidade intacta
