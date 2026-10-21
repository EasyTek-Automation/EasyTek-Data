# -*- coding: utf-8 -*-
"""Testes da quebra POR DISCIPLINA do histórico semanal (SDD hh-historico, BR-16/17/18).

Lógica pura, sem Mongo. Exercita `_disc_bucket` e `_compute_por_disc` com docs sintéticos de
`hh_planejamento` (com snapshot `entrega`). Cobre:
- BR-16: 4 séries (Elé/Mec/Ter + Outras), fonte `disciplina_quadro or disciplina`, soma fecha com total.
- BR-17: horas planejado/realizado das entregues, por disciplina.
- BR-18: aderência ponderada por disciplina; disciplina sem entrega na semana = None (buraco, não zero).
"""
from src.utils import hh_data as hd
from src.utils import hh_historico_data as hh


def _fim_da_semana(semana: str):
    return hd.inicio_da_semana(semana)


def _doc(ordem, semana, disciplina="Mecanica", disciplina_quadro=None, entrega=None):
    d = {"ordem": ordem, "semana": semana, "disciplina": disciplina}
    if disciplina_quadro is not None:
        d["disciplina_quadro"] = disciplina_quadro
    if entrega is not None:
        d["entrega"] = entrega
    return d


def _entrega(status, plan_min, real_min, close_week):
    return {"status_saida": status, "planejado_min": plan_min, "realizado_min": real_min,
            "data_conclusao": _fim_da_semana(close_week)}


# ---- BR-16: bucketização --------------------------------------------------------------

def test_disc_bucket_reais_e_outras():
    assert hh._disc_bucket("Eletrica") == "Eletrica"
    assert hh._disc_bucket("Mecanica") == "Mecanica"
    assert hh._disc_bucket("Terceiros") == "Terceiros"
    # Gestão, Ferramentaria, Não classificado e ausente → Outras (BR-16)
    assert hh._disc_bucket("Gestao") == "Outras"
    assert hh._disc_bucket("Ferramentaria") == "Outras"
    assert hh._disc_bucket("NaoClassificado") == "Outras"
    assert hh._disc_bucket(None) == "Outras"


def test_disciplina_quadro_tem_precedencia():
    # ordem de Terceiros executada no quadro da Elétrica → conta na Elétrica (BR-16)
    ent = _entrega("encerrada", 120, 120, "2026-W02")
    docs = [_doc("F", "2026-W02", disciplina="Terceiros", disciplina_quadro="Eletrica", entrega=ent)]
    r = hh._compute_por_disc(docs, ["2026-W02"])
    assert r["2026-W02"]["Eletrica"]["entregues"] == 1
    assert r["2026-W02"]["Terceiros"]["entregues"] == 0


# ---- BR-16/17/18: cenário completo ----------------------------------------------------

def _cenario():
    # A: Elétrica, atribuída+fechada W1 (plan 360 / real 300 → 83.3%)
    # B: Mecânica, atribuída W1 e W2, fechada em W2 (plan 600 / real 660 → 110%)
    # C: Terceiros, atribuída W1, aberta
    # D: Gestão (→Outras), atribuída+fechada W1 (plan 120 / real 120 → 100%)
    # E: sem disciplina (→Outras), atribuída W1, aberta
    return [
        _doc("A", "2026-W01", "Eletrica", entrega=_entrega("encerrada", 360, 300, "2026-W01")),
        _doc("B", "2026-W01", "Mecanica"),
        _doc("B", "2026-W02", "Mecanica", entrega=_entrega("encerrada", 600, 660, "2026-W02")),
        _doc("C", "2026-W01", "Terceiros"),
        _doc("D", "2026-W01", "Gestao", entrega=_entrega("encerrada", 120, 120, "2026-W01")),
        _doc("E", "2026-W01", None),
    ]


def test_atribuidas_por_disciplina():
    r = hh._compute_por_disc(_cenario(), ["2026-W01", "2026-W02"])
    w1 = r["2026-W01"]
    assert w1["Eletrica"]["atribuidas"] == 1     # A
    assert w1["Mecanica"]["atribuidas"] == 1     # B
    assert w1["Terceiros"]["atribuidas"] == 1    # C
    assert w1["Outras"]["atribuidas"] == 2       # D (Gestao) + E (None)
    assert r["2026-W02"]["Mecanica"]["atribuidas"] == 1   # B de novo em W2


def test_entregues_por_disciplina():
    r = hh._compute_por_disc(_cenario(), ["2026-W01", "2026-W02"])
    w1, w2 = r["2026-W01"], r["2026-W02"]
    assert w1["Eletrica"]["entregues"] == 1      # A fecha W1
    assert w1["Outras"]["entregues"] == 1        # D fecha W1
    assert w1["Mecanica"]["entregues"] == 0      # B só fecha em W2
    assert w2["Mecanica"]["entregues"] == 1      # B fecha W2


def test_horas_por_disciplina_das_entregues():
    r = hh._compute_por_disc(_cenario(), ["2026-W01", "2026-W02"])
    assert r["2026-W01"]["Eletrica"]["planejado_min"] == 360
    assert r["2026-W01"]["Eletrica"]["realizado_min"] == 300
    assert r["2026-W02"]["Mecanica"]["planejado_min"] == 600
    assert r["2026-W02"]["Mecanica"]["realizado_min"] == 660


def test_aderencia_por_disciplina_e_buraco():
    r = hh._compute_por_disc(_cenario(), ["2026-W01", "2026-W02"])
    assert r["2026-W01"]["Eletrica"]["aderencia_pct"] == 83.3
    assert r["2026-W01"]["Outras"]["aderencia_pct"] == 100.0
    assert r["2026-W02"]["Mecanica"]["aderencia_pct"] == 110.0   # >100 mostra real (BR-18)
    # BR-18: disciplina sem entrega na semana = None (buraco), não 0
    assert r["2026-W01"]["Mecanica"]["aderencia_pct"] is None    # B não fechou em W1
    assert r["2026-W02"]["Eletrica"]["aderencia_pct"] is None    # nada fechou em W2 na Elétrica


def test_entregues_origem_plano_vs_carry():
    # A: atribuída+fechada W1 → "no plano" em W1
    # G: atribuída SÓ em W1, fecha em W2 → "carry-over (atrasada)" em W2
    docs = [
        _doc("A", "2026-W01", "Eletrica", entrega=_entrega("encerrada", 60, 60, "2026-W01")),
        _doc("G", "2026-W01", "Mecanica", entrega=_entrega("encerrada", 60, 60, "2026-W02")),
    ]
    r = hh._compute_por_disc(docs, ["2026-W01", "2026-W02"])
    assert r["2026-W01"]["Eletrica"]["entregues_plano"] == 1
    assert r["2026-W01"]["Eletrica"]["entregues_carry"] == 0
    assert r["2026-W02"]["Mecanica"]["entregues_carry"] == 1
    assert r["2026-W02"]["Mecanica"]["entregues_plano"] == 0
    # soma das 3 origens == entregues total
    for W, b in [("2026-W01", "Eletrica"), ("2026-W02", "Mecanica")]:
        c = r[W][b]
        assert c["entregues_plano"] + c["entregues_carry"] + c["entregues_fora"] == c["entregues"]


def test_soma_das_4_series_fecha_com_total():
    # a soma das 4 séries = total da planta (nada perdido no recorte — BR-16)
    docs = _cenario()
    weeks = ["2026-W01", "2026-W02"]
    r = hh._compute_por_disc(docs, weeks)
    fluxo = {x["semana"]: x for x in hh._compute_fluxo(docs, weeks)}
    for W in weeks:
        soma_atrib = sum(r[W][b]["atribuidas"] for b in hh.DISC_BUCKETS)
        soma_entreg = sum(r[W][b]["entregues"] for b in hh.DISC_BUCKETS)
        soma_carry = sum(r[W][b]["carry_over"] for b in hh.DISC_BUCKETS)
        assert soma_atrib == fluxo[W]["atribuidas"]
        assert soma_entreg == fluxo[W]["entregues"]
        assert soma_carry == fluxo[W]["carry_over"]     # carry-over por disciplina fecha com o total
