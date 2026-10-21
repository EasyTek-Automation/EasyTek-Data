# -*- coding: utf-8 -*-
"""Testes das funções do job `hh_entregas` (BR-20 / SP-09.6) — congelamento do snapshot.

Sem SAP e sem Mongo real: um fake mínimo de collection (suporta match com `$in`/`$ne` e caminhos
pontilhados, `distinct`, `find_one`, `update_many` com `$set` pontilhado) exercita a detecção, o
congelamento provisório, a re-consulta aplicada e a marcação de reabertura. A navegação SAP em si
(`_coleta.navigate_realizado_por_aufnr`) é validada no cliente (como o B14).
"""
import importlib
import sys
from datetime import datetime
from pathlib import Path

_PARENT = Path(__file__).resolve().parents[2]  # AMG_Data/
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

_entregas = importlib.import_module("sap-scheduler.trabalhos.hh._entregas")
hh = importlib.import_module("sap-scheduler.trabalhos.hh.hh")

_AGORA = datetime(2026, 7, 13, 4, 0, 0)


# ---- fake mínimo de Mongo ------------------------------------------------------------

def _get(doc, dotted):
    cur = doc
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _match_val(val, cond):
    if isinstance(cond, dict):
        if "$in" in cond:
            return val in cond["$in"]
        if "$ne" in cond:
            return val != cond["$ne"]
    return val == cond


def _match(doc, filt):
    return all(_match_val(_get(doc, k), c) for k, c in filt.items())


def _set(doc, dotted, val):
    cur = doc
    parts = dotted.split(".")
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
        if cur is None:
            cur = {}
    cur[parts[-1]] = val


class _Res:
    def __init__(self, n): self.modified_count = n


class FakeColl:
    def __init__(self, docs=None): self.docs = [dict(d) for d in (docs or [])]

    def find(self, filt=None, proj=None):
        return [dict(d) for d in self.docs if _match(d, filt or {})]

    def find_one(self, filt=None, proj=None):
        for d in self.docs:
            if _match(d, filt or {}):
                return dict(d)
        return None

    def distinct(self, field, filt=None):
        return list({d.get(field) for d in self.docs if _match(d, filt or {})})

    def update_many(self, filt, update):
        n = 0
        for d in self.docs:
            if _match(d, filt):
                for k, v in update.get("$set", {}).items():
                    _set(d, k, v)
                n += 1
        return _Res(n)


class FakeDB:
    def __init__(self, colls): self.colls = colls
    def __getitem__(self, name): return self.colls.setdefault(name, FakeColl())


def _db(atrib=None, backlog=None, planejado=None, realizado=None, status=None):
    return FakeDB({
        _entregas.COLL_ATRIB: FakeColl(atrib),
        _entregas.COLL_BACKLOG: FakeColl(backlog),
        _entregas.COLL_PLANEJADO: FakeColl(planejado),
        _entregas.COLL_REALIZADO: FakeColl(realizado),
        _entregas.COLL_STATUS: FakeColl(status),
    })


# ---- helpers puros -------------------------------------------------------------------

def test_aderencia():
    assert _entregas._aderencia(120, 60) == 0.5
    assert _entregas._aderencia(0, 60) is None
    assert _entregas._aderencia(None, 60) is None


def test_saida_de_ustxt():
    # estado de saída vem do STATUS DO USUÁRIO (decisão 2026-07-15): CERR→encerrada, CANC→cancelada;
    # qualquer outro (ativo) → None (não-terminal, reentra e mostra o status do usuário).
    assert _entregas._saida_de_ustxt("CANC") == "cancelada"
    assert _entregas._saida_de_ustxt("CANC SMTO") == "cancelada"
    assert _entregas._saida_de_ustxt("CERR") == "encerrada"
    assert _entregas._saida_de_ustxt("ENPA PRIO") is None
    assert _entregas._saida_de_ustxt("ENTR") is None
    assert _entregas._saida_de_ustxt(None) is None


# ---- detecção (só Mongo) -------------------------------------------------------------

def test_detectar_alvo_e_reabertas():
    atrib = [
        {"ordem": "A1", "entrega": None},                                  # atribuída, sem snapshot
        {"ordem": "A2", "entrega": None},                                  # atribuída, ainda aberta
        {"ordem": "A3", "entrega": {"status_saida": "encerrada", "superado": False}},  # terminal, reabriu
        {"ordem": "A4", "entrega": {"status_saida": "ativa", "superado": False}},       # não-terminal, reentra
        {"ordem": "A5", "entrega": {"status_saida": "concluida", "superado": False}},   # SISTEMA antigo → migra
        {"ordem": "A6", "entrega": {"status_saida": "cancelada", "superado": False,
                                    "cabecalho": {"descricao": "X"}}},   # terminal COM título → não reentra
    ]
    backlog = [{"ordem": "A2"}, {"ordem": "A3"}]     # A2 e A3 estão abertas
    det = _entregas.detectar(_db(atrib=atrib, backlog=backlog))
    assert det["alvo"] == {"A1", "A4", "A5"}       # sem snapshot + ativa + antigo-sistema (migra p/ usuário)
    assert "A6" not in det["alvo"]                 # cancelada terminal COM título não reentra
    assert det["reabertas"] == {"A3"}              # voltou ao backlog com snapshot


def test_detectar_terminais_usuario_nao_reentram():
    # terminal do USUÁRIO (encerrada=CERR, cancelada=CANC) COM título NÃO reentra. Estados de SISTEMA
    # antigos (concluida/teco) e ativa reentram (re-resolvidos pelo USTXT); terminal SEM título reentra
    # uma vez p/ backfill do título (KTEXT vem do IW39). Migração automática (decisão 2).
    atrib = [
        {"ordem": "C1", "entrega": {"status_saida": "encerrada", "superado": False,
                                    "cabecalho": {"descricao": "X"}}},
        {"ordem": "C2", "entrega": {"status_saida": "cancelada", "superado": False,
                                    "cabecalho": {"descricao": "Y"}}},
        {"ordem": "C3", "entrega": {"status_saida": "ativa", "superado": False}},
        {"ordem": "C4", "entrega": {"status_saida": "concluida", "superado": False}},   # antigo sistema
        {"ordem": "C5", "entrega": {"status_saida": "teco", "superado": False}},        # antigo sistema
        {"ordem": "C6", "entrega": {"status_saida": "encerrada", "superado": False}},   # terminal SEM título
    ]
    det = _entregas.detectar(_db(atrib=atrib, backlog=[]))
    assert "C1" not in det["alvo"] and "C2" not in det["alvo"]    # terminais do usuário com título
    assert det["alvo"] == {"C3", "C4", "C5", "C6"}               # ativa + antigos sistema + backfill título


# ---- aplicação por status do usuário (aplicar_entregas) ------------------------------

def test_aplicar_entregas_encerrada_com_numeros_iw47():
    # ordem entregue/fechada: USTXT CERR (IW39) → encerrada; números do IW47 (por_ordem).
    atrib = [{"ordem": "A1", "entrega": {"status_saida": "ativa", "provisorio": True,
                                         "planejado_min": 120, "realizado_min": 0, "superado": False}}]
    db = _db(atrib=atrib)
    por_ordem = {"A1": {"realizado_min": 110, "planejado_min": 120, "status_sap": "ENTE",
                        "cabecalho": {"categoria": "Corretiva", "disciplina": "Mecanica"}}}
    status_map = {"A1": {"status_usuario": "CERR", "status_sistema": "ENTE"}}
    res = _entregas.aplicar_entregas(db, {"A1"}, por_ordem, status_map, _AGORA)
    ent = db[_entregas.COLL_ATRIB].docs[0]["entrega"]
    assert res["encerrada"] == 1
    assert ent["status_saida"] == "encerrada" and ent["provisorio"] is False
    assert ent["status_usuario"] == "CERR"
    assert ent["realizado_min"] == 110 and ent["planejado_min"] == 120
    assert ent["aderencia"] == round(110 / 120, 4)
    assert (ent.get("cabecalho") or {}).get("categoria") == "Corretiva"


def test_aplicar_entregas_cancelada_sem_iw47():
    # cancelada sem apontamento: IW47 vazio (não está em por_ordem); USTXT CANC + cabeçalho do IW39.
    atrib = [{"ordem": "A1", "entrega": {"status_saida": "ativa", "provisorio": True,
                                         "planejado_min": 0, "realizado_min": 0, "superado": False}}]
    db = _db(atrib=atrib)
    status_map = {"A1": {"status_usuario": "CANC SMTO", "status_sistema": "ENTE",
                         "auart": "YPM1", "tplnr": "BR02-0801"}}
    res = _entregas.aplicar_entregas(db, {"A1"}, {}, status_map, _AGORA)
    ent = db[_entregas.COLL_ATRIB].docs[0]["entrega"]
    assert res["cancelada"] == 1
    assert ent["status_saida"] == "cancelada" and ent["provisorio"] is False
    assert ent["status_usuario"] == "CANC SMTO"
    assert (ent.get("cabecalho") or {}).get("local_instalacao") == "BR02-0801"


def test_aplicar_entregas_ativa_mostra_status_usuario_e_reentra():
    atrib = [{"ordem": "A1", "entrega": {"status_saida": "ativa", "provisorio": True, "superado": False}}]
    db = _db(atrib=atrib)
    status_map = {"A1": {"status_usuario": "ENPA PRIO", "status_sistema": "LIB"}}
    res = _entregas.aplicar_entregas(db, {"A1"}, {}, status_map, _AGORA)
    ent = db[_entregas.COLL_ATRIB].docs[0]["entrega"]
    assert res["ativa"] == 1
    assert ent["status_saida"] == "ativa" and ent["provisorio"] is True   # não-terminal → reentra
    assert ent["status_usuario"] == "ENPA PRIO"


def test_aplicar_entregas_sem_status_map_fica_ativa():
    # IW39 falhou (fail-soft {}) → sem USTXT → ativa (reentra), sem quebrar o job.
    atrib = [{"ordem": "A1", "entrega": {"status_saida": "ativa", "provisorio": True, "superado": False}}]
    db = _db(atrib=atrib)
    res = _entregas.aplicar_entregas(db, {"A1"}, {}, {}, _AGORA)
    ent = db[_entregas.COLL_ATRIB].docs[0]["entrega"]
    assert res["ativa"] == 1
    assert ent["status_saida"] == "ativa" and ent.get("status_usuario") is None


def test_aplicar_entregas_recupera_titulo_do_iw39():
    # o título (descrição) vem do IW39 (KTEXT), NÃO do IW47. Mesmo com cabeçalho do IW47 sem
    # descrição, o merge preenche o título a partir do status_map (IW39) e preserva centro/categoria.
    atrib = [{"ordem": "A1", "entrega": {"status_saida": "ativa", "provisorio": True,
                                         "superado": False, "cabecalho": {}}}]
    db = _db(atrib=atrib)
    por_ordem = {"A1": {"realizado_min": 50,
                        "cabecalho": {"categoria": "Corretiva", "centro_operacao_0010": "Z12"}}}
    status_map = {"A1": {"status_usuario": "CERR", "descricao": "Troca rolamento", "auart": "YPM1"}}
    _entregas.aplicar_entregas(db, {"A1"}, por_ordem, status_map, _AGORA)
    cab = db[_entregas.COLL_ATRIB].docs[0]["entrega"]["cabecalho"]
    assert cab["descricao"] == "Troca rolamento"       # título do IW39
    assert cab["categoria"] == "Corretiva" and cab["centro_operacao_0010"] == "Z12"  # do IW47, preservados


def test_aplicar_entregas_iw39_falho_nao_rebaixa_terminal():
    # backfill: ordem já encerrada reentra p/ título, mas IW39 falha (sem USTXT) → NÃO vira "ativa"
    # (preserva o terminal e o status do usuário já congelado).
    atrib = [{"ordem": "A1", "entrega": {"status_saida": "encerrada", "status_usuario": "CERR",
                                         "provisorio": False, "superado": False, "cabecalho": {}}}]
    db = _db(atrib=atrib)
    _entregas.aplicar_entregas(db, {"A1"}, {}, {}, _AGORA)   # IW47 e IW39 vazios
    ent = db[_entregas.COLL_ATRIB].docs[0]["entrega"]
    assert ent["status_saida"] == "encerrada" and ent["status_usuario"] == "CERR"


def test_aplicar_entregas_nao_toca_superado():
    atrib = [{"ordem": "A1", "entrega": {"status_saida": "encerrada", "superado": True,
                                         "realizado_min": 60}}]
    db = _db(atrib=atrib)
    _entregas.aplicar_entregas(db, {"A1"}, {"A1": {"realizado_min": 999}},
                               {"A1": {"status_usuario": "CANC"}}, _AGORA)
    assert db[_entregas.COLL_ATRIB].docs[0]["entrega"]["realizado_min"] == 60   # intacto (superado)


def test_marcar_reabertas_seta_superado():
    atrib = [{"ordem": "A3", "entrega": {"status_saida": "concluida", "superado": False}}]
    db = _db(atrib=atrib)
    n = _entregas.marcar_reabertas(db, {"A3"})
    assert n == 1
    assert db[_entregas.COLL_ATRIB].docs[0]["entrega"]["superado"] is True


# ---- congelamento provisório ---------------------------------------------------------

def test_congelar_provisorio_grava_numeros():
    atrib = [{"ordem": "A1", "funcionario_id": "c1", "dia": 0, "entrega": None}]
    planejado = [{"ordem": "A1", "operacao": "0010", "planejado_min": 120}]
    realizado = [{"ordem": "A1", "operacao": "0010", "realizado_min": 60, "status_sap": "LIB"}]
    db = _db(atrib=atrib, planejado=planejado, realizado=realizado)
    n = _entregas.congelar_provisorio(db, {"A1"}, _AGORA)
    assert n == 1
    ent = db[_entregas.COLL_ATRIB].docs[0]["entrega"]
    assert ent["provisorio"] is True and ent["status_saida"] == "nao_confirmada"
    assert ent["planejado_min"] == 120 and ent["realizado_min"] == 60
    assert ent["aderencia"] == 0.5


def test_congelar_provisorio_idempotente():
    # não regrava onde já existe entrega (só onde entrega=None)
    atrib = [{"ordem": "A1", "entrega": {"status_saida": "concluida", "planejado_min": 99}}]
    db = _db(atrib=atrib, planejado=[{"ordem": "A1", "operacao": "0010", "planejado_min": 120}])
    n = _entregas.congelar_provisorio(db, {"A1"}, _AGORA)
    assert n == 0
    assert db[_entregas.COLL_ATRIB].docs[0]["entrega"]["planejado_min"] == 99   # intacto


# ---- agregação do retorno da re-consulta (hh._por_ordem_realizado) -------------------

def test_por_ordem_realizado_agrega_realizado_e_planejado():
    # IW47 traz ISMNW (realizado, soma) E ARBEI (planejado, dedup por operação — TARGET_IW47).
    rows = [
        {"AUFNR": "A1", "VORNR": "0010", "ISMNW": "60", "ISMNE": "MIN", "ARBEI": "45", "ARBEH": "MIN", "STTXT": "LIB ENCE"},
        {"AUFNR": "A1", "VORNR": "0010", "ISMNW": "20", "ISMNE": "MIN", "ARBEI": "45", "ARBEH": "MIN", "STTXT": "LIB ENCE"},  # 2ª conf da mesma op
        {"AUFNR": "A1", "VORNR": "0020", "ISMNW": "40", "ISMNE": "MIN", "ARBEI": "30", "ARBEH": "MIN", "STTXT": "LIB ENCE"},
        {"AUFNR": "", "VORNR": "", "ISMNW": "120", "ISMNE": "MIN"},   # linha de total → descartada
    ]
    po = hh._por_ordem_realizado(rows, "20260713.0400", _AGORA)
    assert set(po.keys()) == {"A1"}
    assert po["A1"]["realizado_min"] == 120        # 60+20+40 (soma das confirmações)
    assert po["A1"]["planejado_min"] == 75         # 45 (dedup op 0010) + 30 (op 0020) — NÃO 45+45+30
    assert po["A1"]["status_sap"] == "LIB ENCE"


# ---- integração: run_entregas end-to-end (mock SAP + Mongo fake) ---------------------

class _FakeCfg:
    mock_sap = True


class _FakeCtx:
    def __init__(self, db):
        self.db = db
        self.cfg = _FakeCfg()

    def sap(self):
        raise AssertionError("mock_sap=True: run_entregas não deve abrir sessão SAP")


def test_run_entregas_e2e_encerra_por_status_usuario_planejado_do_iw47():
    # Ordem fechada FORA do backlog e SEM planejado coletado (sap_hh_planejado vazio). O plano vem do
    # ARBEI do próprio IW47 (senão a aderência se perde). O ESTADO de saída vem do STATUS DO USUÁRIO
    # (IW39-por-AUFNR mock → CERR) → status_saida="encerrada" (não mais "concluida" do de/para).
    atrib = [{"ordem": "A1", "funcionario_id": "c1", "dia": 0, "disciplina": "Mecanica",
              "entrega": None}]
    db = _db(atrib=atrib, backlog=[{"ordem": "A9"}],   # A1 não está no backlog
             planejado=[],   # <-- SEM planejado coletado (ordem fechada caiu do snapshot de abertas)
             realizado=[{"ordem": "A1", "operacao": "0010", "realizado_min": 60, "status_sap": "LIB"}])
    res = hh.run_entregas(job=None, ctx=_FakeCtx(db))
    assert res.ok is True
    ent = db[_entregas.COLL_ATRIB].docs[0]["entrega"]
    assert ent["status_saida"] == "encerrada"       # USTXT CERR (mock IW39) → encerrada
    assert ent["status_usuario"] == "CERR"
    assert ent["provisorio"] is False
    assert ent["realizado_min"] == 100              # realizado final do IW47
    assert ent["planejado_min"] == 120              # planejado veio do ARBEI do IW47 (não era 0)
    assert ent["aderencia"] == round(100 / 120, 4)  # aderência NÃO se perdeu
    # cabeçalho congelado do IW47 (B29): categoria (AUART YPM1) + disciplina (centro Z12) + local
    cab = ent.get("cabecalho") or {}
    assert cab.get("categoria") == "Corretiva"
    assert cab.get("disciplina") == "Mecanica"
    assert cab.get("local_instalacao") == "BR02-0801"
    assert cab.get("centro_operacao_0010") == "Z12"
    assert cab.get("descricao") == "Troca rolamento"     # título recuperado do IW39 (KTEXT)


def test_run_entregas_e2e_no_op_sem_alvo():
    # todas as atribuídas ainda no backlog → nada a congelar; não abre SAP (sap() levantaria)
    atrib = [{"ordem": "A1", "entrega": None}]
    db = _db(atrib=atrib, backlog=[{"ordem": "A1"}])
    res = hh.run_entregas(job=None, ctx=_FakeCtx(db))
    assert res.ok is True
    assert db[_entregas.COLL_ATRIB].docs[0]["entrega"] is None   # intacto
