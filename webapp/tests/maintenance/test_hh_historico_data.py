# -*- coding: utf-8 -*-
"""Testes da camada de dados do HISTÓRICO SEMANAL (SDD hh-historico, fase 06 Bloco A).

Lógica pura, sem Mongo — exercita os núcleos `_compute_*` com docs sintéticos de `hh_planejamento`
(com snapshot `entrega`) e `hh_replanejamentos`. Cobre as BR fechadas na fase 02:
BR-01 (carry-over por semana), BR-02 (crônico consecutivo), BR-06 (aderência ponderada),
BR-07 (fluxo + mês por maioria), BR-08 (HH só entregues), BR-09 (replanejamento empurrar+cancelar).
"""
from src.utils import hh_data as hd
from src.utils import hh_historico_data as hh


def _fim_da_semana(semana: str):
    """Um datetime dentro da semana (segunda) — garante iso_semana igual à semana pedida no teste."""
    return hd.inicio_da_semana(semana)


def _doc(ordem, semana, disciplina="Mecanica", entrega=None):
    d = {"ordem": ordem, "semana": semana, "disciplina": disciplina}
    if entrega is not None:
        d["entrega"] = entrega
    return d


def _entrega(status, plan_min, real_min, close_week):
    return {"status_saida": status, "planejado_min": plan_min, "realizado_min": real_min,
            "aderencia": (round(real_min / plan_min * 100, 1) if plan_min else None),
            "data_conclusao": _fim_da_semana(close_week)}


# ---- helpers de semana ---------------------------------------------------------------

def test_semana_para_mes_maioria_dos_dias():
    # 2026-W27 = 29/jun a 5/jul → 2 dias junho, 5 julho → julho (BR-07)
    assert hh.semana_para_mes("2026-W27") == "2026-07"

def test_semanas_entre_inclusivo_e_ordenado():
    assert hh._semanas_entre("2026-W25", "2026-W28") == ["2026-W25", "2026-W26", "2026-W27", "2026-W28"]

def test_semanas_entre_invertido_vazio():
    assert hh._semanas_entre("2026-W28", "2026-W25") == []


# ---- BR-01: fluxo e carry-over por semana ---------------------------------------------

def test_fluxo_carry_over_e_entrega_no_fecho():
    # Ordem A: atribuída W28,W29,W30; encerra em W31. Ordem B: nova em W30, aberta.
    ent_a = _entrega("encerrada", 360, 360, "2026-W31")
    docs = [
        _doc("A", "2026-W28"), _doc("A", "2026-W29"), _doc("A", "2026-W30", entrega=ent_a),
        _doc("B", "2026-W30"),
    ]
    r = {x["semana"]: x for x in hh._compute_fluxo(docs, hh._semanas_entre("2026-W28", "2026-W31"))}
    # atribuídas = ordens com doc na própria semana
    assert r["2026-W28"]["atribuidas"] == 1      # só A
    assert r["2026-W30"]["atribuidas"] == 2      # A e B
    assert r["2026-W31"]["atribuidas"] == 0      # ninguém atribuído em W31
    # carry-over: A arrasta em W29 e W30 (veio de antes, aberta); some em W31 (encerrou dentro de W31)
    assert r["2026-W29"]["carry_over"] == 1       # só A (B ainda não existe)
    assert r["2026-W30"]["carry_over"] == 1       # A (de antes); B é nova em W30 → não conta
    # W31: A encerrou (sai do carry) mas B (nova em W30) agora veio de antes e segue aberta → carry=1
    assert r["2026-W31"]["carry_over"] == 1
    assert r["2026-W31"]["entregues"] == 1        # A entregue em W31

def test_carry_over_ordem_nova_nao_conta():
    docs = [_doc("B", "2026-W30")]
    r = {x["semana"]: x for x in hh._compute_fluxo(docs, ["2026-W30", "2026-W31"])}
    assert r["2026-W30"]["carry_over"] == 0      # nova, sem semana anterior
    assert r["2026-W31"]["carry_over"] == 1      # em W31 já veio de antes e segue aberta

def test_entregue_conta_na_semana_do_fecho():
    ent = _entrega("encerrada", 360, 300, "2026-W31")
    docs = [_doc("A", "2026-W30", entrega=ent)]
    r = {x["semana"]: x for x in hh._compute_fluxo(docs, ["2026-W30", "2026-W31"])}
    assert r["2026-W30"]["entregues"] == 0
    assert r["2026-W31"]["entregues"] == 1

def test_cancelada_nao_e_entregue_mas_sai_do_carry():
    ent = _entrega("cancelada", 360, 0, "2026-W31")
    docs = [_doc("A", "2026-W29", entrega=ent)]
    r = {x["semana"]: x for x in hh._compute_fluxo(docs, ["2026-W30", "2026-W31"])}
    assert r["2026-W30"]["entregues"] == 0       # cancelada não é entregue (BR-09/IN-05)
    assert r["2026-W30"]["carry_over"] == 1       # em W30 ainda não terminou (fecho em W31)
    assert r["2026-W31"]["carry_over"] == 0       # terminou (cancelada) em W31 → sai


# ---- BR-06 / BR-08: HH e aderência ponderada por horas --------------------------------

def test_hh_e_aderencia_ponderada_por_horas():
    # entregues em W22: ordem grande 40h/40h + ordem pequena 6h/8h
    grande = _entrega("encerrada", 2400, 2400, "2026-W22")
    pequena = _entrega("encerrada", 360, 480, "2026-W22")
    docs = [_doc("D", "2026-W22", entrega=grande), _doc("E", "2026-W22", entrega=pequena)]
    hh_serie = {x["semana"]: x for x in hh._compute_hh(docs, ["2026-W22"])}
    assert hh_serie["2026-W22"]["planejado_h"] == 46.0     # (2400+360)/60
    assert hh_serie["2026-W22"]["realizado_h"] == 48.0     # (2400+480)/60
    ader = {x["semana"]: x for x in hh._compute_aderencia(docs, ["2026-W22"])}
    # ponderado = 2880/2760*100 = 104.3  (mediana seria ~116.7 — prova que NÃO é mediana)
    assert ader["2026-W22"]["aderencia_pct"] == 104.3

def test_aderencia_sem_planejado_none():
    ader = hh._compute_aderencia([], ["2026-W22"])
    assert ader[0]["aderencia_pct"] is None

def test_hh_so_conta_entregues():
    # ordem aberta (sem entrega) não entra no HH mesmo tendo atribuição
    docs = [_doc("X", "2026-W22")]
    hh_serie = hh._compute_hh(docs, ["2026-W22"])
    assert hh_serie[0]["planejado_h"] == 0.0 and hh_serie[0]["realizado_h"] == 0.0


# ---- BR-09: replanejamentos (empurrar + cancelar; ajuste interno fora) -----------------

def test_replanejamentos_empurrar_e_cancelar_contam_ajuste_interno_nao():
    docs = [
        {"semana": "2026-W25", "tipo": "mover_semana", "categoria": "Falta de material"},
        {"semana": "2026-W25", "tipo": "remover", "categoria": "Produção não liberou"},
        {"semana": "2026-W25", "tipo": "mover_semana", "categoria": "Falta de material"},
        {"semana": "2026-W25", "tipo": "trocar_tecnico", "categoria": "x"},   # NÃO conta
        {"semana": "2026-W25", "tipo": "remontar_divisao", "categoria": "y"}, # NÃO conta
    ]
    r = hh._compute_replanejamentos(docs, ["2026-W25"])[0]["motivos"]
    assert r == {"Falta de material": 2, "Produção não liberou": 1}


# ---- BR-02: carry-over crônico (consecutivo, abertas, pulo zera) ----------------------

def _semanas_range(ini, fim):
    return hh._semanas_entre(ini, fim)

def test_cronico_consecutivo_conta_streak():
    docs = [_doc("F", w) for w in _semanas_range("2026-W17", "2026-W30")]   # 14 semanas seguidas, aberta
    r = hh._compute_eternas(docs, "2026-W30", janela=52)
    assert r[0]["ordem"] == "F" and r[0]["semanas_consec"] == 14

def test_cronico_pulo_zera_a_contagem():
    # atribuída W20 (isolada) + W28,W29,W30 → streak consecutivo até W30 = 3 (o pulo zera)
    docs = [_doc("G", "2026-W20")] + [_doc("G", w) for w in _semanas_range("2026-W28", "2026-W30")]
    r = {x["ordem"]: x for x in hh._compute_eternas(docs, "2026-W30", janela=52)}
    assert r["G"]["semanas_consec"] == 3

def test_cronico_abaixo_de_3_fora():
    docs = [_doc("H", "2026-W29"), _doc("H", "2026-W30")]     # só 2 seguidas
    assert hh._compute_eternas(docs, "2026-W30", janela=52) == []

def test_cronico_ordem_fechada_fora():
    ent = _entrega("encerrada", 120, 120, "2026-W30")
    docs = [_doc("I", w, entrega=ent) for w in _semanas_range("2026-W25", "2026-W30")]
    assert hh._compute_eternas(docs, "2026-W30", janela=52) == []   # não é "eterna" ativa

def test_eternas_top_5_ordenado():
    docs = []
    # 6 ordens com streaks 3..8 → top 5 devolve as 5 maiores (8,7,6,5,4)
    for i, ini in enumerate(["2026-W28", "2026-W27", "2026-W26", "2026-W25", "2026-W24", "2026-W23"]):
        docs += [_doc(f"O{i}", w) for w in _semanas_range(ini, "2026-W30")]
    r = hh._compute_eternas(docs, "2026-W30", janela=52, top=5)
    streaks = [x["semanas_consec"] for x in r]
    assert len(r) == 5 and streaks == sorted(streaks, reverse=True) and streaks[0] == 8


def test_top_motivos_ranking_na_janela():
    docs = [
        {"semana": "2026-W28", "tipo": "mover_semana", "categoria": "Falta de material"},
        {"semana": "2026-W29", "tipo": "remover", "categoria": "Falta de material"},
        {"semana": "2026-W30", "tipo": "mover_semana", "categoria": "Produção não liberou"},
        {"semana": "2026-W10", "tipo": "mover_semana", "categoria": "Fora da janela"},  # fora
    ]
    r = hh._compute_top_motivos(docs, "2026-W30", janela=6)
    assert r[0] == {"motivo": "Falta de material", "total": 2}
    assert {"motivo": "Produção não liberou", "total": 1} in r
    assert all(x["motivo"] != "Fora da janela" for x in r)


# ---- BR-12: captura Fase 2 do estado do backlog (SCD2 append-on-change) ----------------

def test_diff_ordem_nova_gera_insert():
    atual = {"5001": {"status_usuario": "ABIE", "disciplina": "Mecanica"}}
    inserts, closes = hh._diff_backlog(atual, {}, "2026-W30")
    assert closes == [] and len(inserts) == 1
    assert inserts[0]["valido_de"] == "2026-W30" and inserts[0]["valido_ate"] is None

def test_diff_status_igual_nao_escreve():
    atual = {"5001": {"status_usuario": "ENTR", "disciplina": "Mecanica"}}
    vig = {"5001": {"_id": 1, "status_usuario": "ENTR"}}
    inserts, closes = hh._diff_backlog(atual, vig, "2026-W30")
    assert inserts == [] and closes == []

def test_diff_status_mudou_fecha_e_abre():
    atual = {"5001": {"status_usuario": "ENPA", "disciplina": "Mecanica"}}
    vig = {"5001": {"_id": 7, "status_usuario": "ENTR"}}
    inserts, closes = hh._diff_backlog(atual, vig, "2026-W30")
    assert closes == [7] and len(inserts) == 1 and inserts[0]["status_usuario"] == "ENPA"

def test_diff_ordem_sumiu_encerra_vigente():
    vig = {"5001": {"_id": 9, "status_usuario": "ABIE"}}
    inserts, closes = hh._diff_backlog({}, vig, "2026-W30")
    assert closes == [9] and inserts == []

def test_cobre_intervalo_scd2():
    assert hh._cobre("2026-W25", None, "2026-W30") is True          # vigente
    assert hh._cobre("2026-W25", "2026-W28", "2026-W30") is False   # já encerrado antes
    assert hh._cobre("2026-W25", "2026-W31", "2026-W30") is True    # cobre a semana
    assert hh._cobre("2026-W31", None, "2026-W30") is False         # começou depois
    assert hh._cobre("2026-W30", "2026-W30", "2026-W30") is False   # [W30,W30) vazio

def test_contar_status_por_semana():
    lbl = lambda c: {"ABIE": "Aberta", "ENTR": "Em Tratamento"}.get(c, c)
    docs = [
        {"status_usuario": "ABIE", "valido_de": "2026-W28", "valido_ate": None},
        {"status_usuario": "ABIE", "valido_de": "2026-W29", "valido_ate": None},
        {"status_usuario": "ENTR", "valido_de": "2026-W29", "valido_ate": None},
        {"status_usuario": "ABIE", "valido_de": "2026-W20", "valido_ate": "2026-W27"},  # fora
    ]
    r = hh._contar_status(docs, "2026-W30", label_fn=lbl)
    assert r == {"Aberta": 2, "Em Tratamento": 1}
