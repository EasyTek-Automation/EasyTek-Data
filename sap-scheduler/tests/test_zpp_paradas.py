# -*- coding: utf-8 -*-
"""Testes do job `zpp_paradas_pendentes` (KPIReport-v2 BR-14 / DS-17).

Usa grade inteiramente sintética (310 paradas + 28 subtotais + total geral) — sem SAP e
sem Mongo real. A navegação/export no SAP GUI é validada no cliente (IM-32).
"""
import importlib
import inspect
import json
import sys
from datetime import date, datetime, time
from pathlib import Path
from types import SimpleNamespace

_PARENT = Path(__file__).resolve().parents[2]  # AMG_Data/
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

zp = importlib.import_module("sap-scheduler.trabalhos.kpis_manut.zpp_paradas")
registry = importlib.import_module("sap-scheduler.core.registry")

_FIX = json.loads((Path(__file__).parent / "fixtures" / "zppparadas_grade_20261007.json").read_text("utf-8"))
_ROWS = [tuple(_FIX["header"])] + [tuple(r) for r in _FIX["rows"]]
_AGORA = datetime(2026, 10, 7, 12, 26)


def _docs():
    return zp.normalizar_linhas(_ROWS, "20261007.1226", _AGORA)


def test_le_310_paradas_descarta_subtotais_e_total():
    docs = _docs()
    assert len(docs) == 310
    assert all(d["linha"] and d["ordem"] for d in docs)
    # total de referência sintético = 7.490 min (coluna arredondada); fim−início fica a menos de 1 min/linha
    assert abs(sum(d["duracao_min"] for d in docs) - 7490) < 310


def test_avaria_pendente_do_longi001_lida_certa():
    alvo = [d for d in _docs() if d["linha"] == "LONGI001" and d["ordem"] == 90000001 and d["causa"] == "201"]
    inicios = sorted(d["inicio"] for d in alvo)
    assert inicios == [datetime(2026, 10, 6, 6, 15), datetime(2026, 10, 6, 13, 0, 10)]
    d = min(alvo, key=lambda x: x["inicio"])
    assert d["fim"] == datetime(2026, 10, 6, 12, 0)
    assert d["duracao_min"] == 345.0
    assert "redutor" in d["texto_operador"].lower()


def test_propaga_motivo_quando_grade_agrupada_so_traz_na_primeira_linha():
    rows = [
        ("LINEA", "Ordem", "DATA INICIO", "DATA FIM", "HORA INICIO", "HORA FIM", "MOTIVO"),
        ("PRENS001", "000010631342", "07.10.2026", "07.10.2026", "12:31:00", "13:06:00", "201"),
        ("PRENS002", "000010629406", "07.10.2026", "07.10.2026", "10:31:00", "10:59:00", ""),
        ("", "", "", "", "", "", "201"),          # subtotal do grupo
        ("SOLDA001", "000010631992", "07.10.2026", "07.10.2026", "08:00:00", "08:10:00", "304"),
        ("", "", "", "", "", "", ""),             # total geral
    ]
    docs = zp.normalizar_linhas(rows, "x", _AGORA)
    assert [(d["linha"], d["causa"]) for d in docs] == [("PRENS001", "201"), ("PRENS002", "201"), ("SOLDA001", "304")]


def test_aceita_tipos_nativos_do_excel_e_cabecalho_abaixo_do_titulo():
    rows = [
        ("Paradas por linha", None, None),
        (None,),
        ("Línea", "Ordem", "Data início", "Data fim", "Hora início", "Hora fim", "Motivo", "Descripção do motivo", "Observação de notificação"),
        ("LONGI001", 90000001.0, datetime(2026, 10, 6), date(2026, 10, 6), time(6, 15), 0.5, "201", "Quebra", "redutor"),
    ]
    (d,) = zp.normalizar_linhas(rows, "x", _AGORA)
    assert d["ordem"] == 90000001
    assert d["inicio"] == datetime(2026, 10, 6, 6, 15)
    assert d["fim"] == datetime(2026, 10, 6, 12, 0)
    assert d["descricao_motivo"] == "Quebra" and d["texto_operador"] == "redutor"


def test_sem_cabecalho_levanta():
    import pytest
    with pytest.raises(ValueError):
        zp.normalizar_linhas([("a", "b"), ("c", "d")], "x", _AGORA)


def test_janela_cobre_mes_de_ontem_ate_hoje():
    ini, fim = zp._janela(datetime(2026, 11, 1, 6, 30))
    assert ini.date() == date(2026, 10, 1) and fim.date() == date(2026, 11, 1)
    ini, fim = zp._janela(datetime(2026, 10, 8, 10, 0))
    assert ini.date() == date(2026, 10, 1) and fim.date() == date(2026, 10, 8)


def test_args_nunca_usa_pasta_do_zpp_processor_e_so_seleciona():
    a = zp._args("/tmp/zppparadas_x/ZPPPARADAS_1.xlsx", datetime(2026, 10, 8, 6, 30))
    assert a.tx == "ZPPPARADAS" and a.ctx_code == "&XXL"
    assert a.save_dir == "/tmp/zppparadas_x"
    assert "wnd[0]/usr/ctxtCENTRO=BR02" in a.set
    assert "wnd[0]/usr/ctxtFECHA-LOW=01.10.2026" in a.set


def test_script_sem_tecla_de_gravacao():
    """⚠ F6 = Mark Reviewed e Ctrl+S/Ctrl+F10 = Save gravam no SAP (RESULTADO §2)."""
    fonte = inspect.getsource(zp)
    codigo = "\n".join(l for l in fonte.splitlines() if not l.strip().startswith("#"))
    for proibido in ("sendVKey(6)", "sendVKey(11)", "sendVKey(30)", "sendVKey(34)", "pressToolbarButton"):
        assert proibido not in codigo


def test_registrado_no_registry():
    assert registry.REGISTRY["zpp_paradas_pendentes"] is zp.run


class _FakeColl:
    def __init__(self):
        self.docs = []

    def insert_many(self, docs):
        self.docs.extend(dict(d) for d in docs)

    def delete_many(self, q):
        keep = q["coleta_id"]["$ne"]
        self.docs = [d for d in self.docs if d.get("_id") == "meta" or d.get("coleta_id") == keep]

    def update_one(self, q, upd, upsert=False):
        meta = next((d for d in self.docs if d.get("_id") == "meta"), None)
        if meta is None:
            meta = {"_id": "meta"}
            self.docs.append(meta)
        meta.update(upd["$set"])

    def create_index(self, *a, **k):
        pass


def test_run_mock_grava_retrato_e_substitui_o_anterior(tmp_path, monkeypatch):
    coll = _FakeColl()
    coll.docs.append({"linha": "VELHO", "coleta_id": "antigo"})
    db = {zp.COLL: coll}
    monkeypatch.setattr(zp, "_mock_rows", lambda ctx: _ROWS)
    ctx = SimpleNamespace(cfg=SimpleNamespace(mock_sap=True), db=db)
    res = zp.run({}, ctx)
    assert res.ok, res.erro
    paradas = [d for d in coll.docs if d.get("_id") != "meta"]
    assert len(paradas) == 310 and all(d["linha"] != "VELHO" for d in paradas)
    meta = next(d for d in coll.docs if d.get("_id") == "meta")
    assert meta["total"] == 310 and meta["coletado_em"]
