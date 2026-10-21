"""Testes do filtro de conta valendo para o total (BR-17 / IM-44).

Desmarcar uma conta tira o dinheiro dela de tudo que é total: a barra GERAL vira
"GERAL (filtrado)" com a soma só das contas marcadas, a rosca soma só elas e o modal da
fatia abre com o dropdown "Conta" pré-preenchido. Sem Dash — só os helpers puros.
"""
from __future__ import annotations

from src.callbacks_registers import custo_callbacks as C
from src.custos import leitura as L


def _row(code, orcado, executado, label=None):
    return {"code": code, "label": label or code, **L.calcular_metricas(orcado, executado)}


def _rows():
    """GERAL oficial (soma das 3) + 3 contas. 33102102 = Edifícios."""
    contas = [_row("33102101", 600.0, 500.0),
              _row("33102260", 300.0, 200.0),
              _row("33102102", 100.0, 80.0)]
    geral = _row("__GERAL__", 1000.0, 780.0, label="GERAL")
    return [geral] + contas


# --------------------------------------------------------------------------- #
# _filtra_por_contas — GERAL do recorte
# --------------------------------------------------------------------------- #
def test_sem_filtro_devolve_intacto():
    rows = _rows()
    assert C._filtra_por_contas(rows, None) is rows


def test_nenhuma_conta_deixa_so_o_geral_zerado():
    out = C._filtra_por_contas(_rows(), [])
    assert [r["code"] for r in out] == ["__GERAL__"]
    assert out[0]["executado"] == 0.0 and out[0]["label"] == C.GERAL_FILTRADO


def test_recorte_recalcula_geral_e_rotulo():
    out = C._filtra_por_contas(_rows(), ["33102101", "33102260"])  # tira Edifícios
    geral = out[0]
    assert geral["code"] == "__GERAL__"
    assert geral["label"] == C.GERAL_FILTRADO
    assert geral["orcado"] == 900.0
    assert geral["executado"] == 700.0
    assert geral["saldo"] == 200.0
    assert geral["pct"] == round(700 / 900 * 100, 2)  # soma ÷ soma (BR-05), não média de %
    assert [r["code"] for r in out[1:]] == ["33102101", "33102260"]


def test_recorte_nao_muta_a_linha_original():
    rows = _rows()
    C._filtra_por_contas(rows, ["33102101"])
    assert rows[0]["label"] == "GERAL" and rows[0]["executado"] == 780.0  # memo intacto


def test_conta_desmarcada_ausente_no_nivel_mantem_rotulo_filtrado():
    # nível "contas do dia": Edifícios nem aparece, mas o filtro global está ativo
    rows = [_row("__GERAL__", 0.0, 700.0, label="GERAL"),
            _row("33102101", 0.0, 500.0), _row("33102260", 0.0, 200.0)]
    out = C._filtra_por_contas(rows, ["33102101", "33102260"])
    assert out[0]["label"] == C.GERAL_FILTRADO
    assert out[0]["executado"] == 700.0


def test_slider_depois_do_filtro_nao_mexe_no_geral():
    # ordem do _prep: contas → valor. O slider esconde barras, mas o GERAL fica.
    rows = C._filtra_por_contas(_rows(), ["33102101", "33102260"])
    out = C._filtra_por_exec(rows, [300.0, 10_000.0])  # some com a 33102260 (200)
    assert [r["code"] for r in out] == ["__GERAL__", "33102101"]
    assert out[0]["executado"] == 700.0


# --------------------------------------------------------------------------- #
# _contas_efetivas — normalização da seleção
# --------------------------------------------------------------------------- #
def _mock_contas(monkeypatch):
    monkeypatch.setattr(L, "fetch_contas_geral", lambda ano, mes=None, centros=None: _rows())


def test_contas_efetivas_none_e_todas_viram_none(monkeypatch):
    _mock_contas(monkeypatch)
    assert C._contas_efetivas(None, 2026) is None
    assert C._contas_efetivas(["33102101", "33102260", "33102102"], 2026) is None


def test_contas_efetivas_nenhuma_marcada_e_lista_vazia(monkeypatch):
    # desmarcar tudo NÃO é "todas": vira [] e a tela mostra o aviso
    _mock_contas(monkeypatch)
    assert C._contas_efetivas([], 2026) == []


def test_contas_efetivas_recorte(monkeypatch):
    _mock_contas(monkeypatch)
    assert C._contas_efetivas(["33102101"], 2026) == ["33102101"]


# --------------------------------------------------------------------------- #
# _fconta_inicial — dropdown "Conta" do modal da rosca
# --------------------------------------------------------------------------- #
def test_fconta_inicial():
    opts = [{"label": "a", "value": "33102101"}, {"label": "b", "value": "33102102"}]
    assert C._fconta_inicial(opts, None) == []
    assert C._fconta_inicial(opts, ["33102101", "33102260"]) == ["33102101"]


# --------------------------------------------------------------------------- #
# leitura — rosca e resumos respeitam `contas`
# --------------------------------------------------------------------------- #
class _FakeColl:
    """Captura o $match de cada aggregate e devolve uma resposta fixa."""

    def __init__(self, resposta):
        self.resposta = resposta
        self.matches = []

    def aggregate(self, pipe):
        self.matches.append(pipe[0]["$match"])
        return list(self.resposta)


def _mock_mongo(monkeypatch, lanc, resumo):
    L.limpar_cache()
    colls = {L.COLL_LANCAMENTOS: lanc, L.COLL_RESUMO: resumo}
    monkeypatch.setattr(L, "get_mongo_connection", lambda c: colls[c])


def test_rosca_filtra_conta_nos_lancamentos_e_no_nao_atribuido(monkeypatch):
    lanc = _FakeColl([{"_id": "209000", "executado": 600.0}])
    resumo = _FakeColl([{"_id": None, "v": 650.0}])
    _mock_mongo(monkeypatch, lanc, resumo)
    out = L.fetch_por_equipamento(2026, None, contas=["33102101"])
    assert lanc.matches[0]["conta"] == {"$in": ["33102101"]}
    assert resumo.matches[0]["conta"] == {"$in": ["33102101"]}
    assert out[-1] == {"equip": "Não atribuído", "executado": 50.0, "centros": []}


def test_rosca_sem_contas_nao_filtra(monkeypatch):
    lanc = _FakeColl([{"_id": "209000", "executado": 600.0}])
    resumo = _FakeColl([{"_id": None, "v": 600.0}])
    _mock_mongo(monkeypatch, lanc, resumo)
    L.fetch_por_equipamento(2026, None)
    assert "conta" not in lanc.matches[0]
    assert "conta" not in resumo.matches[0]


def test_rosca_cache_separa_por_contas(monkeypatch):
    lanc = _FakeColl([{"_id": "209000", "executado": 600.0}])
    resumo = _FakeColl([{"_id": None, "v": 600.0}])
    _mock_mongo(monkeypatch, lanc, resumo)
    L.fetch_por_equipamento(2026, None)
    L.fetch_por_equipamento(2026, None, contas=["33102101"])
    assert len(lanc.matches) == 2  # 2ª chamada não reaproveitou o memo da 1ª


def test_resumos_da_fatia_filtram_conta(monkeypatch):
    lanc = _FakeColl([{"_id": "33102101", "executado": 10.0}])
    _mock_mongo(monkeypatch, lanc, None)
    monkeypatch.setattr(L, "carregar_depara", lambda: None)
    L.fetch_contas_resumo(2026, ["209000"], contas=["33102101"])
    L.fetch_centros_resumo(2026, ["209000"], contas=["33102101"])
    assert all(m["conta"] == {"$in": ["33102101"]} for m in lanc.matches)
