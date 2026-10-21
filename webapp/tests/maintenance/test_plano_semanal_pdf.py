# -*- coding: utf-8 -*-
"""Testes do modelo e render do relatório PDF do planejamento semanal (B1 / IM-05).

Exercita a camada PURA `montar_paginas` (recorte Σ>1min, ordem disciplina→técnico, ordens do
dia por nº, regra temporal por-dia, rodapé por-técnico) e o `gerar_pdf` (bytes de PDF válido),
sem Mongo — o quadro/cadastro/assignments são mocks.
"""
from datetime import timedelta

from src.utils import hh_data
from src.utils import plano_semanal_pdf as ps

SEMANA = "2026-W27"
_DATAS = hh_data.datas_da_semana(SEMANA)          # seg..dom (datetimes)
HOJE = _DATAS[2]                                    # quarta → seg/ter = passado; qua = hoje; qui+ = futuro


def _ordem(num, plan, real=0, parcela=None, linha_nome=None):
    ader = (real / plan) if plan else None
    return {"ordem": num, "descricao": f"ordem {num}", "planejado_min": plan,
            "realizado_min": real, "aderencia": ader, "parcela_min": parcela,
            "linha_nome": linha_nome}


def _tec(fid, nome, turno, dias):
    base = {d: [] for d in range(7)}
    base.update(dias)
    return {"funcionario_id": fid, "nome": nome, "turno": turno, "dias": base}


def _quadro(mec, ele):
    return {"semana": SEMANA, "eh_futura": False, "coletado_em": None,
            "disciplinas": {"Mecanica": {"tecnicos": mec}, "Eletrica": {"tecnicos": ele}}}


def _emp(fid, jornada=480, turno="A"):
    return {"_id": fid, "jornada_min": jornada, "turno_padrao": turno}


# ---- recorte SP-02.2 (Σ planejado > 1 min) -------------------------------------------

def test_recorte_exclui_placeholder_1min_e_vazio():
    mec = [_tec("m1", "Bruno", "A", {0: [_ordem("5000002", 120)]})]      # 120 > 1 → entra
    ele = [
        _tec("e2", "Ana", "B", {0: [_ordem("5000100", 1)]}),            # só 1 min → fora
        _tec("e3", "Diego", "B", {}),                                    # sem ordens → fora
        _tec("e1", "Carlos", "B", {0: [_ordem("5000050", 480)]}),       # 480 → entra
    ]
    emp = {"m1": _emp("m1"), "e1": _emp("e1", turno="B"),
           "e2": _emp("e2", turno="B"), "e3": _emp("e3", turno="B")}
    pags = ps.montar_paginas(_quadro(mec, ele), emp, {}, HOJE)
    nomes = [p["nome"] for p in pags]
    assert nomes == ["Bruno", "Carlos"]              # Ana/Diego cortados; Mec antes de Elé


def test_ordem_paginas_disciplina_depois_nome():
    mec = [_tec("m1", "Bruno", "A", {0: [_ordem("5000002", 120)]})]
    ele = [_tec("e1", "Carlos", "B", {0: [_ordem("5000050", 480)]})]
    pags = ps.montar_paginas(_quadro(mec, ele), {"m1": _emp("m1"), "e1": _emp("e1")}, {}, HOJE)
    assert [(p["disciplina"], p["nome"]) for p in pags] == [("Mecanica", "Bruno"), ("Eletrica", "Carlos")]


# ---- ordenação das ordens no dia por número (SP-03.4) --------------------------------

def test_ordens_do_dia_ordenadas_por_numero():
    mec = [_tec("m1", "Bruno", "A", {0: [_ordem("5000009", 60), _ordem("5000002", 60)]})]
    pags = ps.montar_paginas(_quadro(mec, []), {"m1": _emp("m1")}, {}, HOJE)
    nums = [o["ordem"] for o in pags[0]["dias"][0]["ordens"]]
    assert nums == ["5000002", "5000009"]


# ---- regra temporal por-dia (BR-04 / DS-05) -----------------------------------------

def test_temporalidade_passado_mostra_real_futuro_nao():
    # ordem na segunda (passado) e na quinta (futuro, índice 3)
    mec = [_tec("m1", "Bruno", "A", {0: [_ordem("5000002", 120, real=110)],
                                     3: [_ordem("5000003", 240, real=999)]})]
    pags = ps.montar_paginas(_quadro(mec, []), {"m1": _emp("m1")}, {}, HOJE)
    seg = pags[0]["dias"][0]
    qui = pags[0]["dias"][3]
    assert seg["passado"] is True and seg["ordens"][0]["realizado_min"] == 110
    assert seg["ordens"][0]["aderencia"] is not None
    assert qui["passado"] is False and qui["ordens"][0]["realizado_min"] is None
    assert qui["ordens"][0]["aderencia"] is None


def test_passado_sem_apontamento_aderencia_zero():
    # planejado sem realizado num dia passado → aderência da ordem = 0.0 (não None)
    mec = [_tec("m1", "Bruno", "A", {0: [_ordem("5000002", 120, real=0)]})]
    pags = ps.montar_paginas(_quadro(mec, []), {"m1": _emp("m1")}, {}, HOJE)
    o = pags[0]["dias"][0]["ordens"][0]
    assert o["aderencia"] == 0.0


# ---- rodapé por-técnico (RV-04 / DS-04) ---------------------------------------------

def test_rodape_por_tecnico_disponivel_e_programado():
    mec = [_tec("m1", "Bruno", "A", {0: [_ordem("5000002", 120, real=110)]})]
    pags = ps.montar_paginas(_quadro(mec, []), {"m1": _emp("m1", jornada=480)}, {}, HOJE)
    cap = pags[0]["dias"][0]["cap"]
    assert cap["disponivel"] == 480
    assert cap["programado"] == 120
    assert cap["executado"] == 110                 # dia passado
    assert round(cap["pct_programado"], 4) == round(120 / 480, 4)


def test_rodape_indisponivel_zera_disponivel():
    # técnico com alocação (férias/folga) sobrepondo a segunda → disponível 0 naquele dia
    seg = _DATAS[0]
    assigns = {"m1": [{"data_hora_entrada": seg, "data_hora_saida": seg + timedelta(days=1)}]}
    mec = [_tec("m1", "Bruno", "A", {0: [_ordem("5000002", 120)]})]
    pags = ps.montar_paginas(_quadro(mec, []), {"m1": _emp("m1")}, assigns, HOJE)
    assert pags[0]["dias"][0]["cap"]["disponivel"] == 0


def test_disponivel_none_sem_jornada():
    mec = [_tec("m1", "Bruno", "", {0: [_ordem("5000002", 120)]})]
    pags = ps.montar_paginas(_quadro(mec, []), {"m1": {"_id": "m1"}}, {}, HOJE)  # sem jornada/turno
    assert pags[0]["dias"][0]["cap"]["disponivel"] is None


# ---- linha do trabalho na célula da ordem (onde vai ser feito) ----------------------

def test_ordem_view_propaga_linha_nome():
    mec = [_tec("m1", "Bruno", "A", {0: [_ordem("5000002", 120, linha_nome="Laminação 3")]})]
    pags = ps.montar_paginas(_quadro(mec, []), {"m1": _emp("m1")}, {}, HOJE)
    assert pags[0]["dias"][0]["ordens"][0]["linha"] == "Laminação 3"


def test_ordem_view_linha_ausente_vira_string_vazia():
    # ordem sem linha_nome (None) → campo "linha" == "" (sublinha omitida no render)
    mec = [_tec("m1", "Bruno", "A", {0: [_ordem("5000002", 120)]})]
    pags = ps.montar_paginas(_quadro(mec, []), {"m1": _emp("m1")}, {}, HOJE)
    assert pags[0]["dias"][0]["ordens"][0]["linha"] == ""


# ---- render gerar_pdf ---------------------------------------------------------------

def test_gerar_pdf_bytes_validos():
    mec = [_tec("m1", "Bruno", "A", {0: [_ordem("5000002", 120, real=110)]})]
    pags = ps.montar_paginas(_quadro(mec, []), {"m1": _emp("m1")}, {}, HOJE)
    pdf = ps.gerar_pdf(pags, SEMANA, coletado_em=None, hoje=HOJE)
    assert isinstance(pdf, bytes) and pdf[:4] == b"%PDF" and len(pdf) > 1000


def test_gerar_pdf_com_linha_gera_bytes_validos():
    # célula com sublinha de Linha não quebra o render (reportlab/Latin-1, sem emoji)
    mec = [_tec("m1", "Bruno", "A", {0: [_ordem("5000002", 120, real=110, linha_nome="Laminação 3")]})]
    pags = ps.montar_paginas(_quadro(mec, []), {"m1": _emp("m1")}, {}, HOJE)
    pdf = ps.gerar_pdf(pags, SEMANA, coletado_em=None, hoje=HOJE)
    assert pdf[:4] == b"%PDF" and len(pdf) > 1000


def test_gerar_pdf_nada_a_imprimir_ainda_gera_folha():
    pdf = ps.gerar_pdf([], SEMANA)
    assert pdf[:4] == b"%PDF"
