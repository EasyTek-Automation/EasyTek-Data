# -*- coding: utf-8 -*-
"""Testes do retry in-run do executor (Bloco K, portado pro core refatorado).

O pacote do daemon tem nome com hífen (`sap-scheduler`), então é carregado via
`importlib.import_module` com o parent (`AMG_Data/`) no `sys.path`. Os testes
exercitam `core.executor._rodar_com_retry` isoladamente, com o script (run_fn)
substituído por stubs — sem SAP GUI real, sem Mongo. Cobre: sucesso direto,
sucesso após retry (fase transiente), esgotamento de tentativas (fase transiente)
e falha imediata (fase determinística, sem retry).
"""
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_PARENT = Path(__file__).resolve().parents[2]  # AMG_Data/
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

executor = importlib.import_module("sap-scheduler.core.executor")
contracts = importlib.import_module("sap-scheduler.core.contracts")
Result = contracts.Result


def _cfg(max_tentativas=3):
    """Config mínima pro retry — só o campo que `_rodar_com_retry` lê."""
    return SimpleNamespace(max_tentativas_job=max_tentativas, collection="sap_jobs")


def _ctx():
    """Ctx dummy — o run_fn stub não toca SAP nem Mongo."""
    return SimpleNamespace(cfg=_cfg(), db=None)


@pytest.fixture(autouse=True)
def _neutraliza_io(monkeypatch):
    """Zera efeitos colaterais reais (kill_excel, sleep) em todos os testes."""
    monkeypatch.setattr(executor.kill_excel, "kill_preventivo", lambda *a, **k: None)
    monkeypatch.setattr(executor.time, "sleep", lambda *_: None)


def _run_sempre_ok(job, ctx):
    return Result.sucesso(tamanho_bytes=123)


def _run_falha(fase):
    """Fabrica um run_fn que sempre falha na fase dada."""
    def _run(job, ctx):
        return Result.falha(fase, RuntimeError(f"falha {fase}"))
    return _run


def _run_falha_depois_ok(fase, falhas):
    """run_fn que falha `falhas` vezes na fase dada, depois devolve sucesso."""
    estado = {"n": 0}

    def _run(job, ctx):
        estado["n"] += 1
        if estado["n"] <= falhas:
            return Result.falha(fase, RuntimeError("transiente"))
        return Result.sucesso(tamanho_bytes=1)
    return _run


def test_sucesso_direto():
    r = executor._rodar_com_retry(_run_sempre_ok, {"_id": 1}, _ctx(), _cfg())
    assert r.ok
    assert r.dados["tentativas"] == 1


def test_sucesso_apos_retry_transiente():
    cfg = _cfg(max_tentativas=3)
    run = _run_falha_depois_ok("export_alv", falhas=2)
    r = executor._rodar_com_retry(run, {"_id": 1}, _ctx(), cfg)
    assert r.ok
    assert r.dados["tentativas"] == 3  # falhou 2x, sucesso na 3a


def test_esgota_tentativas_em_fase_transiente():
    cfg = _cfg(max_tentativas=3)
    run = _run_falha("conexao_sap")  # transiente, sempre falha
    chamadas = {"n": 0}

    def _conta(job, ctx):
        chamadas["n"] += 1
        return run(job, ctx)

    r = executor._rodar_com_retry(_conta, {"_id": 1}, _ctx(), cfg)
    assert not r.ok
    assert r.fase == "conexao_sap"
    assert chamadas["n"] == 3  # tentou todas as 3


def test_falha_deterministica_nao_faz_retry():
    cfg = _cfg(max_tentativas=3)
    chamadas = {"n": 0}

    def _run(job, ctx):
        chamadas["n"] += 1
        return Result.falha("validacao_arquivo", RuntimeError("layout errado"))

    r = executor._rodar_com_retry(_run, {"_id": 1}, _ctx(), cfg)
    assert not r.ok
    assert r.fase == "validacao_arquivo"
    assert chamadas["n"] == 1  # fase NÃO transiente → não retenta
