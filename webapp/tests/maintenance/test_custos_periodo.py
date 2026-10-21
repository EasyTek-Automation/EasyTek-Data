"""Testes do filtro de período da aba de custo (BR-18 / IM-45).

O período é sempre em meses inteiros (orçado do SAP é mensal). "Ano inteiro" resolve em
`None` — o caminho segue passando o `int` do ano, como antes. Os demais viram lista de meses.
"""
from __future__ import annotations

from datetime import date

from src.callbacks_registers import custo_callbacks as C
from src.custos import leitura as L
from src.custos import periodo as P

HOJE = date(2026, 10, 5)


# --------------------------------------------------------------------------- #
# resolver_meses
# --------------------------------------------------------------------------- #
def test_ano_inteiro_e_none():
    assert P.resolver_meses(2026, P.ANO_INTEIRO, hoje=HOJE) is None
    assert P.resolver_meses(2026, None, hoje=HOJE) is None


def test_trimestres_e_semestres():
    assert P.resolver_meses(2026, "T1", hoje=HOJE) == ["2026-01", "2026-02", "2026-03"]
    assert P.resolver_meses(2026, "T4", hoje=HOJE) == ["2026-10", "2026-11", "2026-12"]
    assert P.resolver_meses(2025, "S2", hoje=HOJE) == [f"2025-{m:02d}" for m in range(7, 13)]


def test_acumulado_ano_corrente_inclui_mes_atual():
    assert P.resolver_meses(2026, P.ACUMULADO, hoje=HOJE) == [f"2026-{m:02d}" for m in range(1, 11)]


def test_acumulado_ano_passado_e_ano_inteiro():
    assert P.resolver_meses(2025, P.ACUMULADO, hoje=HOJE) is None


def test_personalizado_cruza_o_ano():
    meses = P.resolver_meses(2026, P.PERSONALIZADO, "2025-11", "2026-02", hoje=HOJE)
    assert meses == ["2025-11", "2025-12", "2026-01", "2026-02"]


def test_personalizado_invertido_e_corrigido():
    assert P.resolver_meses(2026, P.PERSONALIZADO, "2026-03", "2026-01", hoje=HOJE) == \
        ["2026-01", "2026-02", "2026-03"]


def test_personalizado_incompleto_cai_no_ano_inteiro():
    assert P.resolver_meses(2026, P.PERSONALIZADO, "2026-03", None, hoje=HOJE) is None


# --------------------------------------------------------------------------- #
# rotulo
# --------------------------------------------------------------------------- #
def test_rotulos():
    assert P.rotulo(2026, None) == "2026"
    assert P.rotulo(2026, ["2026-03"]) == "mar/2026"
    assert P.rotulo(2026, ["2026-01", "2026-02", "2026-03"]) == "jan–mar/2026"
    assert P.rotulo(2026, ["2025-11", "2025-12", "2026-01"]) == "nov/2025–jan/2026"


# --------------------------------------------------------------------------- #
# janela nos callbacks e na leitura
# --------------------------------------------------------------------------- #
def test_jan_converte_store():
    assert C._jan({"ano": 2026, "meses": None}) == 2026
    assert C._jan({"ano": 2026, "meses": ["2026-01", "2026-02"]}) == ("2026-01", "2026-02")
    assert C._jan(2025) == 2025          # valor legado da sessão (int)
    assert C._jan(None) == 2026


def test_rotulo_e_eh_periodo():
    j = {"ano": 2026, "meses": ["2026-01", "2026-03"], "rotulo": "jan–mar/2026"}
    assert C._rotulo(j) == "jan–mar/2026" and C._eh_periodo(j)
    assert C._rotulo({"ano": 2026, "meses": None, "rotulo": "2026"}) == "2026"
    assert not C._eh_periodo({"ano": 2026, "meses": None})


def test_janela_match():
    assert L._janela_match(2026) == {"$regex": "^2026-"}
    assert L._janela_match(("2025-12", "2026-01")) == {"$in": ["2025-12", "2026-01"]}
    assert L._filtro_ano(("2026-01",), mes="2026-05") == {"mes_referencia": "2026-05"}


def test_nome_do_export_com_periodo_e_ascii():
    assert C._rosca_fname(["209000"], "jan–mar/2026").endswith("_jan-mar-2026.xlsx")


class _FakeFind:
    def __init__(self):
        self.match = None

    def find(self, match):
        self.match = match
        return self

    def sort(self, *_a, **_k):
        return self

    def limit(self, _n):
        return []


def test_fetch_lancamentos_com_periodo(monkeypatch):
    coll = _FakeFind()
    monkeypatch.setattr(L, "get_mongo_connection", lambda _c: coll)
    monkeypatch.setattr(L, "carregar_depara", lambda: None)
    L.fetch_lancamentos(("2026-01", "2026-02"), centros=["209000"])
    assert coll.match["mes_referencia"] == {"$in": ["2026-01", "2026-02"]}
