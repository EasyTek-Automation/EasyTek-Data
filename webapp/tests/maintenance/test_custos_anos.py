"""Testes de `custos/leitura.fetch_anos_disponiveis` — filtro de ano dinâmico (fix)."""
from __future__ import annotations

from src.custos import leitura as L


class _FakeColl:
    def __init__(self, meses):
        self._meses = meses

    def distinct(self, campo, filtro=None):
        assert campo == "mes_referencia"
        return list(self._meses)


def _mock(monkeypatch, coll):
    L.limpar_cache()  # o memo TTL sobrevive entre testes — zerar antes de cada caso
    monkeypatch.setattr(L, "get_mongo_connection", lambda _c: coll)


def test_dois_anos_ordem_desc(monkeypatch):
    _mock(monkeypatch, _FakeColl(["2025-11", "2026-01", "2025-03", "2026-06"]))
    assert L.fetch_anos_disponiveis() == [2026, 2025]


def test_um_ano(monkeypatch):
    _mock(monkeypatch, _FakeColl(["2026-01", "2026-02"]))
    assert L.fetch_anos_disponiveis() == [2026]


def test_vazio(monkeypatch):
    _mock(monkeypatch, _FakeColl([]))
    assert L.fetch_anos_disponiveis() == []


def test_mongo_offline(monkeypatch):
    _mock(monkeypatch, None)
    assert L.fetch_anos_disponiveis() == []


def test_ignora_lixo(monkeypatch):
    _mock(monkeypatch, _FakeColl(["2026-01", None, "", "xx-01", "2025-12"]))
    assert L.fetch_anos_disponiveis() == [2026, 2025]
