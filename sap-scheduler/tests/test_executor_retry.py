"""Testes do retry in-run do executor SAP (Bloco K).

O pacote do daemon tem nome com hífen (`sap-scheduler`), então é carregado via
`importlib.import_module` com o parent (`AMG_Data/`) no `sys.path`. Os testes
exercitam `_executar_sap_com_retry` isoladamente, com as fases SAP monkeypatchadas
— sem SAP GUI real, sem Mongo. Cobre: sucesso direto, sucesso após retry,
esgotamento de tentativas (fase transiente) e falha imediata (fase determinística).
"""
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_PARENT = Path(__file__).resolve().parent.parent.parent  # AMG_Data/
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

esap = importlib.import_module("sap-scheduler.executor_sap")
ExcecaoClassificada = esap.ExcecaoClassificada


def _cfg(max_tentativas=3):
    """Config mínima pro retry — só os campos que `_executar_sap_com_retry` lê."""
    return SimpleNamespace(max_tentativas_job=max_tentativas, sap_gate_dir=Path("/tmp/sap-gate"))


def _factory(path, agora):
    """args_factory dummy — retorna namespace qualquer; export é monkeypatchado."""
    return SimpleNamespace(path=path)


@pytest.fixture(autouse=True)
def _neutraliza_io(monkeypatch):
    """Zera efeitos colaterais reais (kill_excel, sleep) em todos os testes."""
    monkeypatch.setattr(esap.kill_excel, "pids_atuais", lambda: set())
    monkeypatch.setattr(esap.kill_excel, "kill_preventivo", lambda: None)
    monkeypatch.setattr(esap.kill_excel, "kill_pos", lambda *a, **k: None)
    monkeypatch.setattr(esap.time, "sleep", lambda *_: None)
    # conexão sempre OK por padrão (engine fake); export é quem cada teste controla
    monkeypatch.setattr(esap, "_fase_conexao", lambda _dir: (object(), object()))
    monkeypatch.setattr(esap, "_fase_kill_pos", lambda _pids: None)


def test_sucesso_primeira_tentativa(monkeypatch):
    chamadas = {"export": 0}

    def _export_ok(_mod, _engine, _args):
        chamadas["export"] += 1

    monkeypatch.setattr(esap, "_fase_export", _export_ok)
    tentativa = esap._executar_sap_com_retry("/tmp/x.xlsx", _factory, None, _cfg())
    assert tentativa == 1
    assert chamadas["export"] == 1


def test_sucesso_apos_uma_falha_transiente(monkeypatch):
    chamadas = {"export": 0, "sleep": 0}
    monkeypatch.setattr(esap.time, "sleep", lambda *_: chamadas.__setitem__("sleep", chamadas["sleep"] + 1))

    def _export_flaky(_mod, _engine, _args):
        chamadas["export"] += 1
        if chamadas["export"] == 1:
            raise ExcecaoClassificada("export_alv", RuntimeError("selectContextMenuItem(&XXL) falhou: 613"))
        # 2ª tentativa passa

    monkeypatch.setattr(esap, "_fase_export", _export_flaky)
    tentativa = esap._executar_sap_com_retry("/tmp/x.xlsx", _factory, None, _cfg(max_tentativas=3))
    assert tentativa == 2
    assert chamadas["export"] == 2
    assert chamadas["sleep"] == 1  # 1 pausa entre as 2 tentativas


def test_esgota_tentativas_fase_transiente(monkeypatch):
    chamadas = {"export": 0}

    def _export_sempre_falha(_mod, _engine, _args):
        chamadas["export"] += 1
        raise ExcecaoClassificada("export_alv", RuntimeError("613 sempre"))

    monkeypatch.setattr(esap, "_fase_export", _export_sempre_falha)
    with pytest.raises(ExcecaoClassificada) as exc:
        esap._executar_sap_com_retry("/tmp/x.xlsx", _factory, None, _cfg(max_tentativas=3))
    assert exc.value.fase == "export_alv"
    assert chamadas["export"] == 3  # tentou as 3 antes de desistir


def test_falha_deterministica_nao_retenta(monkeypatch):
    chamadas = {"export": 0}

    def _export_salvamento(_mod, _engine, _args):
        chamadas["export"] += 1
        raise ExcecaoClassificada("salvamento", OSError("arquivo nao criado"))

    monkeypatch.setattr(esap, "_fase_export", _export_salvamento)
    with pytest.raises(ExcecaoClassificada) as exc:
        esap._executar_sap_com_retry("/tmp/x.xlsx", _factory, None, _cfg(max_tentativas=3))
    assert exc.value.fase == "salvamento"
    assert chamadas["export"] == 1  # fase determinística → falha na hora, sem retry


def test_max_tentativas_1_desabilita_retry(monkeypatch):
    chamadas = {"export": 0}

    def _export_transiente(_mod, _engine, _args):
        chamadas["export"] += 1
        raise ExcecaoClassificada("navegacao", RuntimeError("glitch"))

    monkeypatch.setattr(esap, "_fase_export", _export_transiente)
    with pytest.raises(ExcecaoClassificada):
        esap._executar_sap_com_retry("/tmp/x.xlsx", _factory, None, _cfg(max_tentativas=1))
    assert chamadas["export"] == 1  # max=1 → comportamento original (sem retry)
