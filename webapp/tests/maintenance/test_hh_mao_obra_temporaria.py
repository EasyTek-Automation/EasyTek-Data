# -*- coding: utf-8 -*-
"""Mão de obra temporária no planejamento semanal (GantManagement BR-25 / SP-17 / DS-18).

Filtro único por semana (quadro, relatório diário, histórico), trava do drop, horas atribuídas
da semana em diante e transições marcar/incluir/retirar com auditoria. Mongo sempre mockado.
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

from src.utils import gantt_db, hh_data
from src.utils import hh_historico_data as hist

SEM = "2026-W42"
FIXO = {"_id": "c1", "nome": "Carlos", "turno_padrao": "B", "ativo": True}
TEMP_FORA = {"_id": "t1", "nome": "Empresa X", "turno_padrao": "B", "ativo": True,
             "temporario": True, "periodos_quadro": []}
TEMP_DENTRO = {"_id": "t2", "nome": "Empresa Y", "turno_padrao": "B", "ativo": True,
               "temporario": True, "periodos_quadro": [{"de": "2026-W42", "ate": None}]}
USR = {"id": "u1", "nome": "pcm"}


def _quadro(funcionarios, semana=SEM):
    base = {"ordens": {}, "coletado_em": None}
    with patch.object(hh_data, "montar_ordens", return_value=base), \
         patch.object(hh_data, "listar_atribuicoes", return_value=[]), \
         patch.object(hh_data, "_carregar_funcionarios", return_value=funcionarios), \
         patch.object(hh_data, "_assignments_por_func", return_value={}), \
         patch.object(hh_data, "carregar_config_capacidade",
                      return_value={"disponivel_min": {"B": 480}, "meta_pct": 70}), \
         patch.object(hh_data, "carry_over", return_value=0), \
         patch.object(hh_data, "_agora_brt", return_value=datetime(2026, 10, 14)):
        return hh_data.montar_quadro(semana)


# ---- filtro único ----------------------------------------------------------------------

def test_funcionarios_da_semana_sem_temporarios_preserva_lista():
    fs = [FIXO, {"_id": "c2", "nome": "Ana", "turno_padrao": "A"}]
    assert hh_data.funcionarios_da_semana(fs, SEM) == fs


def test_montar_quadro_temporario_fora_nao_tem_linha_nem_picker():
    q = _quadro([FIXO, TEMP_FORA])
    for disc in ("Mecanica", "Eletrica"):
        ids = [t["funcionario_id"] for t in q["disciplinas"][disc]["tecnicos"]]
        assert ids == ["c1"]
        assert all(d["id"] != "t1" for d in q["disciplinas"][disc]["disponiveis_fora"])


def test_montar_quadro_temporario_fora_nao_soma_disponivel():
    so_fixo = _quadro([FIXO])
    com_temp = _quadro([FIXO, TEMP_FORA])
    assert com_temp["resumo_dias"] == so_fixo["resumo_dias"]


def test_montar_quadro_temporario_incluido_vira_linha_com_flag_e_soma():
    so_fixo = _quadro([FIXO])
    q = _quadro([FIXO, TEMP_DENTRO])
    tecs = {t["funcionario_id"]: t for t in q["disciplinas"]["Mecanica"]["tecnicos"]}
    assert tecs["t2"]["temporario"] is True
    assert tecs["c1"]["temporario"] is False
    disp = lambda qq: sum((d.get("disponivel") or 0) for d in qq["resumo_dias"].values())
    assert disp(q) > disp(so_fixo)


def test_montar_quadro_semana_anterior_a_inclusao_nao_tem_temporario():
    q = _quadro([FIXO, TEMP_DENTRO], semana="2026-W41")
    ids = [t["funcionario_id"] for t in q["disciplinas"]["Mecanica"]["tecnicos"]]
    assert ids == ["c1"]


def test_semana_mao_de_obra_filtra_disponivel():
    capt = {}

    def _disp(funcs, *a, **k):
        capt["ids"] = [f["_id"] for f in funcs]
        return {i: 0 for i in range(7)}

    with patch.object(hh_data, "montar_ordens", return_value={"ordens": {}}), \
         patch.object(hh_data, "listar_atribuicoes", return_value=[]), \
         patch.object(hh_data, "_carregar_funcionarios", return_value=[FIXO, TEMP_FORA, TEMP_DENTRO]), \
         patch.object(hh_data, "_assignments_por_func", return_value={}), \
         patch.object(hh_data, "carregar_config_capacidade",
                      return_value={"disponivel_min": {}, "meta_pct": 70}), \
         patch.object(hh_data, "disponivel_por_dia", side_effect=_disp), \
         patch.object(hh_data, "_carregar_snapshot", return_value={"docs": []}), \
         patch.object(hh_data, "_agora_brt", return_value=datetime(2026, 10, 20)):
        hh_data.semana_mao_de_obra(datetime(2026, 10, 14))      # quarta da W42
    assert capt["ids"] == ["c1", "t2"]


def test_serie_capacidade_filtra_temporario_por_semana():
    capt = {}

    def _cap(W, funcs, *a, **k):
        capt[W] = sorted(f["_id"] for f in funcs)
        return {}

    with patch.object(hist.hd, "_carregar_funcionarios", return_value=[FIXO, TEMP_DENTRO]), \
         patch.object(hist.hd, "_assignments_por_func", return_value={}), \
         patch.object(hist.hd, "carregar_config_capacidade", return_value={"disponivel_min": {}}), \
         patch.object(hist, "_ordens_para_capacidade", return_value={}), \
         patch.object(hist.hd, "listar_atribuicoes", return_value=[]), \
         patch.object(hist.hd, "calcular_capacidade", side_effect=_cap):
        hist.serie_capacidade("2026-W41", "2026-W42")
    assert capt == {"2026-W41": ["c1"], "2026-W42": ["c1", "t2"]}


# ---- semana atual ou futura ------------------------------------------------------------

def test_semana_atual_ou_futura():
    with patch.object(hh_data, "semana_atual", return_value="2026-W41"):
        assert hh_data.semana_atual_ou_futura("2026-W41")
        assert hh_data.semana_atual_ou_futura("2027-W01")
        assert not hh_data.semana_atual_ou_futura("2026-W40")


# ---- trava do drop ---------------------------------------------------------------------

def _pode(func_id, semana):
    base = {"ordens": {"M1": {"ordem": "M1", "disciplina": "Mecanica"}}}
    with patch.object(hh_data, "montar_ordens", return_value=base), \
         patch.object(hh_data, "ordem_atribuivel", return_value=True), \
         patch.object(hh_data, "_carregar_funcionarios", return_value=[FIXO, TEMP_FORA, TEMP_DENTRO]):
        return hh_data.pode_atribuir("M1", func_id, "Mecanica", semana=semana)


def test_pode_atribuir_recusa_temporario_fora_da_semana():
    assert _pode("t1", SEM) is False
    assert _pode("t2", "2026-W41") is False


def test_pode_atribuir_aceita_fixo_e_temporario_incluido():
    assert _pode("c1", SEM) is True
    assert _pode("t2", SEM) is True


def test_pode_atribuir_sem_semana_retrocompat():
    assert _pode("t1", None) is True


# ---- horas atribuídas da semana em diante ----------------------------------------------

def test_atribuicoes_desde_soma_por_semana_e_resolve_parcela_inteira():
    col = MagicMock()
    col.find.return_value = [
        {"semana": "2026-W46", "ordem": "A", "funcionario_id": "t2", "parcela_min": 120},
        {"semana": "2026-W45", "ordem": "B", "funcionario_id": "t2", "parcela_min": None},
        {"semana": "2026-W45", "ordem": "C", "funcionario_id": "t2", "parcela_min": 0},
    ]
    with patch.object(hh_data, "_coll_atrib", return_value=col), \
         patch.object(hh_data, "montar_ordens", return_value={"ordens": {"B": {"planejado_min": 300}}}), \
         patch.object(hh_data, "plan_iw37_por_ordem", return_value={}):
        out = hh_data.atribuicoes_desde("t2", "2026-W45")
    assert col.find.call_args[0][0] == {"funcionario_id": "t2", "semana": {"$gte": "2026-W45"}}
    assert out == {"2026-W45": 300, "2026-W46": 120}
    assert list(out) == ["2026-W45", "2026-W46"]


def test_atribuicoes_desde_vazio():
    col = MagicMock()
    col.find.return_value = []
    with patch.object(hh_data, "_coll_atrib", return_value=col):
        assert hh_data.atribuicoes_desde("t2", "2026-W45") == {}


# ---- transições ------------------------------------------------------------------------

def _transicao(fn, emp, *args, futuras=None, semana_atual="2026-W41"):
    upd, audit = MagicMock(), MagicMock()
    with patch.object(gantt_db, "get_employee_by_id", return_value=dict(emp)), \
         patch.object(gantt_db, "update_employee", upd), \
         patch.object(gantt_db, "append_audit_log", audit), \
         patch.object(hh_data, "semana_atual", return_value=semana_atual), \
         patch.object(hh_data, "atribuicoes_desde", return_value=futuras or {}):
        res = fn(emp["_id"], *args, USR)
    return res, upd, audit


def test_marcar_temporario_fixo_sem_ordens():
    (ok, _), upd, audit = _transicao(hh_data.marcar_temporario, FIXO, True)
    assert ok
    assert upd.call_args[0][1] == {"temporario": True,
                                   "periodos_quadro": [{"de": None, "ate": "2026-W40"}]}
    e = audit.call_args[0][0]
    assert (e["acao"], e["campo_alterado"], e["valor_anterior"], e["valor_novo"]) == \
        ("edicao", "temporario", "False", "True — a partir de 2026-W41")
    assert e["usuario_nome"] == "pcm" and e["entidade"] == "funcionario"


def test_marcar_temporario_fixo_com_ordens_recusa_sem_gravar():
    (ok, msg), upd, audit = _transicao(hh_data.marcar_temporario, FIXO, True,
                                       futuras={"2026-W41": 720})
    assert not ok
    assert "Carlos tem 12h atribuídas em 2026-W41" in msg
    upd.assert_not_called()
    audit.assert_not_called()


def test_desmarcar_temporario_preserva_passado():
    (ok, _), upd, audit = _transicao(hh_data.marcar_temporario, TEMP_FORA, False, semana_atual="2026-W45")
    assert ok
    assert audit.call_args[0][0]["valor_novo"] == "False — a partir de 2026-W45"
    assert upd.call_args[0][1] == {"temporario": False,
                                   "periodos_quadro": [{"de": "2026-W45", "ate": None}]}


def test_marcar_sem_mudanca_e_noop():
    (ok, _), upd, audit = _transicao(hh_data.marcar_temporario, FIXO, False)
    assert ok
    upd.assert_not_called()
    audit.assert_not_called()


def test_incluir_temporario():
    (ok, _), upd, audit = _transicao(hh_data.incluir_temporario, TEMP_FORA, "2026-W42")
    assert ok
    assert upd.call_args[0][1] == {"periodos_quadro": [{"de": "2026-W42", "ate": None}]}
    e = audit.call_args[0][0]
    assert e["acao"] == "inclusao_quadro" and e["valor_novo"] == "2026-W42→aberto"


def test_incluir_recusa_semana_passada_fixo_e_ja_incluido():
    assert not _transicao(hh_data.incluir_temporario, TEMP_FORA, "2026-W40")[0][0]
    assert not _transicao(hh_data.incluir_temporario, FIXO, "2026-W42")[0][0]
    assert not _transicao(hh_data.incluir_temporario, TEMP_DENTRO, "2026-W43")[0][0]
    inativo = dict(TEMP_FORA, ativo=False)
    assert not _transicao(hh_data.incluir_temporario, inativo, "2026-W42")[0][0]


def test_retirar_temporario():
    (ok, _), upd, audit = _transicao(hh_data.retirar_temporario, TEMP_DENTRO, "2026-W49")
    assert ok
    assert upd.call_args[0][1] == {"periodos_quadro": [{"de": "2026-W42", "ate": "2026-W48"}]}
    e = audit.call_args[0][0]
    assert e["acao"] == "retirada_quadro"
    assert (e["valor_anterior"], e["valor_novo"]) == ("2026-W42→aberto", "2026-W42→2026-W48")


def test_retirar_bloqueado_com_ordens():
    (ok, msg), upd, audit = _transicao(hh_data.retirar_temporario, TEMP_DENTRO, "2026-W45",
                                       futuras={"2026-W45": 480, "2026-W46": 240})
    assert not ok
    assert msg.startswith("Empresa Y tem 12h atribuídas em 2026-W45, 2026-W46")
    assert msg.endswith("antes de retirar.")
    upd.assert_not_called()
    audit.assert_not_called()


def test_retirar_recusa_semana_passada_e_nao_incluido():
    assert not _transicao(hh_data.retirar_temporario, TEMP_DENTRO, "2026-W40",
                          semana_atual="2026-W45")[0][0]
    assert not _transicao(hh_data.retirar_temporario, TEMP_FORA, "2026-W42")[0][0]
