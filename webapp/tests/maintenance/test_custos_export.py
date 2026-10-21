"""Testes do export Excel dos modais da aba Custo (IM-40) — helpers puros de linhas flat.

Foco: regra de explosão do almoxarifado (Opção A + grupo explícito). Sem Dash — só as
funções que montam as linhas do DataFrame.
"""
from __future__ import annotations

import math
from datetime import datetime

from src.callbacks_registers import custo_callbacks as C


def _doc(**kw):
    """Doc de lançamento mínimo (defaults sensatos)."""
    base = {
        "data_lancamento": datetime(2026, 3, 15),
        "conta": "33102101", "centro_custo": "201300",
        "valor": 1000.0, "descritor": "peça X",
        "ordem_emissora": "", "pedido_compra": "", "usuario": "MAX",
        "familia": "",
    }
    base.update(kw)
    return base


# --------------------------------------------------------------------------- #
# _export_rows — explosão de liquidação
# --------------------------------------------------------------------------- #
def test_linha_normal_uma_linha_sem_item():
    rows = C._export_rows([_doc()], fetch_comps=lambda o: [])
    assert len(rows) == 1
    r = rows[0]
    assert r["Valor (R$)"] == 1000.0
    assert r["Item"] is None
    assert r["Material"] is None
    assert r["Data"] == "15/03/2026"


def test_liquidacao_explode_em_n_linhas():
    comps = [
        {"material": "M1", "material_desc": "Rolamento", "quantidade": 2, "unidade": "PC"},
        {"material": "M2", "material_desc": "Vedação", "quantidade": 5, "unidade": "PC"},
    ]
    doc = _doc(familia="liquidacao", ordem_emissora="4500123", valor=880.0)
    rows = C._export_rows([doc], fetch_comps=lambda o: comps)
    assert len(rows) == 2
    # Valor só na 1ª linha do grupo (Opção A)
    assert rows[0]["Valor (R$)"] == 880.0
    assert rows[1]["Valor (R$)"] is None
    # Item ordinal 1..N
    assert [r["Item"] for r in rows] == [1, 2]
    # Identidade repetida em todas as linhas (grupo explícito)
    assert all(r["Ordem"] == "4500123" for r in rows)
    assert all(r["Conta"] == "33102101" for r in rows)
    # Campos de item preenchidos
    assert rows[0]["Material"] == "M1" and rows[0]["Quantidade"] == 2
    assert rows[1]["Descrição do material"] == "Vedação" and rows[1]["Unidade"] == "PC"


def test_liquidacao_sem_componentes_cai_no_fallback():
    doc = _doc(familia="liquidacao", ordem_emissora="4500999", valor=500.0)
    rows = C._export_rows([doc], fetch_comps=lambda o: [])
    assert len(rows) == 1
    assert rows[0]["Valor (R$)"] == 500.0   # fallback = linha única, Valor preservado
    assert rows[0]["Item"] is None


def test_liquidacao_sem_ordem_nao_explode():
    # familia=liquidacao mas sem ordem → não busca componentes, 1 linha
    doc = _doc(familia="liquidacao", ordem_emissora="", valor=300.0)
    chamado = {"n": 0}

    def _fc(o):
        chamado["n"] += 1
        return [{"material": "X"}]

    rows = C._export_rows([doc], fetch_comps=_fc)
    assert len(rows) == 1
    assert chamado["n"] == 0            # fetch_comps não é chamado sem ordem


def test_docs_vazio():
    assert C._export_rows([], fetch_comps=lambda o: []) == []


def test_colunas_batem_com_constante():
    doc = _doc(familia="liquidacao", ordem_emissora="1", valor=10.0)
    comps = [{"material": "M", "material_desc": "d", "quantidade": 1, "unidade": "PC"}]
    rows = C._export_rows([doc, _doc()], fetch_comps=lambda o: comps)
    for r in rows:
        assert set(r.keys()) == set(C._EXPORT_COLS_LANC)


# --------------------------------------------------------------------------- #
# _export_comp_rows — mini-modal do almoxarifado
# --------------------------------------------------------------------------- #
def test_comp_rows_uma_linha_por_item_valor_repetido():
    comps = [
        {"material": "M1", "material_desc": "A", "quantidade": 2, "unidade": "PC"},
        {"material": "M2", "material_desc": "B", "quantidade": 3, "unidade": "KG"},
    ]
    rows = C._export_comp_rows("4500123", 880.0, fetch_comps=lambda o: comps)
    assert len(rows) == 2
    assert [r["Valor total da ordem (R$)"] for r in rows] == [880.0, 880.0]
    assert [r["Item"] for r in rows] == [1, 2]
    assert rows[1]["Material"] == "M2" and rows[1]["Unidade"] == "KG"


def test_comp_rows_sem_componentes_uma_linha():
    rows = C._export_comp_rows("4500999", 500.0, fetch_comps=lambda o: [])
    assert len(rows) == 1
    assert rows[0]["Ordem"] == "4500999"
    assert rows[0]["Valor total da ordem (R$)"] == 500.0
    assert rows[0]["Material"] is None


def test_comp_rows_colunas():
    comps = [{"material": "M", "material_desc": "d", "quantidade": 1, "unidade": "PC"}]
    for r in C._export_comp_rows("1", 1.0, fetch_comps=lambda o: comps):
        assert set(r.keys()) == set(C._EXPORT_COLS_COMP)


# --------------------------------------------------------------------------- #
# _resumo_export_rows — abas Por conta / Por centro
# --------------------------------------------------------------------------- #
def test_resumo_rows_pct_da_fatia():
    resumo = [{"code": "33102101", "nome": "Peças", "executado": 250.0},
              {"code": "33102102", "nome": "Serviços", "executado": 750.0}]
    rows = C._resumo_export_rows(resumo, 1000.0, "Conta")
    assert rows[0] == {"Conta": "33102101", "Nome": "Peças",
                       "Valor (R$)": 250.0, "% da fatia": 25.0}
    assert rows[1]["% da fatia"] == 75.0


def test_resumo_rows_total_zero_sem_divisao():
    rows = C._resumo_export_rows([{"code": "X", "nome": "X", "executado": 0}], 0, "Conta")
    assert rows[0]["% da fatia"] == 0


def test_resumo_rows_vazio():
    assert C._resumo_export_rows([], 100.0, "Conta") == []


# --------------------------------------------------------------------------- #
# Slider de valor da fatia (IM-41) — o default NÃO pode dropar linha negativa
# (estorno / crédito RE). Bug: piso do slider abria em 0 → tabela e export
# inflavam vs. o donut (que soma positivos + negativos).
# --------------------------------------------------------------------------- #
def test_opcoes_filtro_devolve_vmin_com_negativo():
    docs = [_doc(valor=1000.0), _doc(valor=-977.19), _doc(valor=52820.85)]
    opt_conta, opt_centro, vmin, vmax = C._opcoes_filtro(docs)
    assert vmin == -977.19      # piso real inclui o estorno
    assert vmax == 52820.85


def test_opcoes_filtro_vmin_zero_quando_so_positivo():
    _, _, vmin, vmax = C._opcoes_filtro([_doc(valor=10.0), _doc(valor=30.0)])
    assert vmin == 10.0 and vmax == 30.0


def test_faixa_cheia_preserva_estorno():
    # faixa cheia [floor(vmin), ceil(vmax)] = o novo default → mantém o negativo,
    # somando igual ao donut (net dos estornos).
    docs = [_doc(valor=1000.0), _doc(valor=-977.19)]
    _, _, vmin, vmax = C._opcoes_filtro(docs)
    lo, hi = min(math.floor(vmin), 0), max(math.ceil(vmax), 1)
    out = C._filtra_lancamentos(docs, [], [], "", [lo, hi])
    assert len(out) == 2
    assert round(sum(d["valor"] for d in out), 2) == 22.81   # 1000 - 977.19


def test_piso_zero_ainda_corta_negativo_quando_usuario_escolhe():
    # o filtro em si não muda: se o usuário arrastar o piso p/ 0 de propósito, o
    # negativo sai. O fix é só o DEFAULT de abertura, não a semântica do filtro.
    docs = [_doc(valor=1000.0), _doc(valor=-977.19)]
    out = C._filtra_lancamentos(docs, [], [], "", [0, 2000])
    assert len(out) == 1 and out[0]["valor"] == 1000.0


# --------------------------------------------------------------------------- #
# _sanitize_fname
# --------------------------------------------------------------------------- #
def test_sanitize_fname_remove_barras():
    assert "/" not in C._sanitize_fname("custo_2026-03-15.xlsx")
    assert C._sanitize_fname("a/b:c*d.xlsx") == "a-b-c-d.xlsx"


def test_sanitize_fname_trunca_preservando_extensao():
    # IM-43: nome gigante precisa caber e manter .xlsx
    longo = "custo_rosca_" + "-".join([f"20{n:04d}" for n in range(40)]) + "_2026.xlsx"
    out = C._sanitize_fname(longo, max_len=120)
    assert len(out) <= 120
    assert out.endswith(".xlsx")


def test_rosca_fname_usa_nome_do_equipamento_nao_centros():
    # IM-43: 'Apoio/Admin' = 29 centros → antes o nome juntava todos e estourava.
    apoio = ["209002", "209800", "209300", "203602", "209902", "205000", "209004",
             "209001", "209015", "203603", "209100", "209013", "209751", "209706"]
    fn = C._rosca_fname(apoio, 2026)
    assert len(fn) <= 120
    assert "/" not in fn and "\\" not in fn      # 'Apoio/Admin' saneado
    assert fn.endswith("_2026.xlsx")
    # nome de equipamento conhecido (208401 = PRENSA-01) entra legível
    assert C._rosca_fname(["208401"], 2026) == "custo_rosca_PRENSA-01_2026.xlsx"
