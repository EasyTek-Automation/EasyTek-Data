# -*- coding: utf-8 -*-
"""Congelamento (snapshot) da ordem entregue — BR-20 / SP-09.6.

Quando uma ordem ATRIBUÍDA (`hh_planejamento`) é concluída no SAP, ela sai do universo de
abertas (`sap_backlog`) e sumiria do quadro. Este módulo detecta essas ordens, congela o
resultado final (planejado/realizado/aderência/status) no próprio doc de atribuição (campo
`entrega`) e mantém a ordem visível no quadro (render por união no webapp — B25).

Duas partes:
- **Detecção e congelamento** (só Mongo, testável offline): compara atribuídas × abertas,
  agrega os números por ordem a partir das collections-fonte HH e grava `entrega`.
- **Re-consulta dirigida** (SAP, validada no cliente): `hh.run_entregas` chama a coleta IW47 por
  multisseleção das AUFNR-alvo para obter o realizado final + status verdadeiro. Ver `_coleta`.

Fluxo do congelamento (idempotente):
1. `marcar_reabertas` — ordem que voltou ao backlog e já tinha snapshot → `entrega.superado`.
2. `congelar_provisorio` — grava um snapshot PROVISÓRIO com o último-visto das collections-fonte
   (números aparecem na hora; `status_saida="nao_confirmada"`, `provisorio=True`).
3. `aplicar_reconsulta` — com o retorno do SAP, confirma o realizado/status finais e marca
   `provisorio=False`; ordem concluída (de/para `hh_status_mapa`) vira `status_saida="concluida"`.

SAP read-only: nada é escrito no SAP; a re-consulta só lê.
"""
from __future__ import annotations

from datetime import datetime

COLL_ATRIB = "hh_planejamento"
COLL_BACKLOG = "sap_backlog"
COLL_STATUS = "hh_status_mapa"
COLL_PLANEJADO = "sap_hh_planejado"
COLL_REALIZADO = "sap_hh_realizado"


def _codigos_concluidos(db) -> set:
    """Códigos SAP mapeados como 'concluída' (de/para `hh_status_mapa` — BR-17/SP-09.3).

    Mesma fonte que o webapp (`_status_concluidos`). Vazio se o admin ainda não mapeou → nenhuma
    ordem é dada como concluída (fica `nao_confirmada` e reentra no próximo ciclo — conservador).
    """
    try:
        return {d["codigo_sap"] for d in db[COLL_STATUS].find({"concluida": True}, {"codigo_sap": 1})}
    except Exception:
        return set()


def _distinct_ordens(db, coll: str) -> set:
    """AUFNR distintas numa collection (ignora o doc meta do snapshot)."""
    try:
        return {str(o) for o in db[coll].distinct("ordem", {"ordem": {"$ne": None}}) if o}
    except Exception:
        return set()


def _agg_por_ordem(db, coll: str, campo: str, aufnr: set) -> dict:
    """Soma `campo` por ordem nas operações de `coll`, restrito a `aufnr`.

    Planejado e realizado já vêm no grão de operação (dedup/soma feitos na coleta — BR-03); aqui
    só somamos as operações da mesma ordem para ter o total da ordem (como o webapp faz na leitura).
    """
    if not aufnr:
        return {}
    out: dict[str, int] = {}
    try:
        cur = db[coll].find({"ordem": {"$in": list(aufnr)}}, {"ordem": 1, campo: 1})
        for d in cur:
            o = str(d.get("ordem") or "")
            if o:
                out[o] = out.get(o, 0) + int(d.get(campo) or 0)
    except Exception:
        return {}
    return out


def _status_por_ordem(db, coll: str, aufnr: set) -> dict:
    """Último status SAP visto (`status_sap`) por ordem, restrito a `aufnr`."""
    if not aufnr:
        return {}
    out: dict[str, str] = {}
    try:
        for d in db[coll].find({"ordem": {"$in": list(aufnr)}}, {"ordem": 1, "status_sap": 1}):
            o = str(d.get("ordem") or "")
            st = d.get("status_sap")
            if o and st:
                out[o] = st
    except Exception:
        return {}
    return out


def _aderencia(plan, real):
    """realizado ÷ planejado, ou None se não há planejado (número neutro — BR-09)."""
    if not plan or plan <= 0:
        return None
    return round((real or 0) / plan, 4)


def _saida_de_ustxt(status_usuario) -> str | None:
    """Categoria de saída do backlog a partir do STATUS DO USUÁRIO (USTXT) — decisão do cliente
    2026-07-15: o estado da ordem que saiu é o status do USUÁRIO, não o de sistema (STTXT/de-para).

    `CANC`→`cancelada`, `CERR`→`encerrada` (terminais — congelam). Qualquer outro (ainda ativo:
    ENTR/ENPA/ESAC/ABIE… ou USTXT ausente) → `None` = não-terminal: o card mostra o próprio status
    do usuário e a ordem reentra no ciclo até virar terminal. Casa por substring (o USTXT pode vir
    com mais de um flag, ex. `CANC SMTO`, `ENPA PRIO`)."""
    u = (status_usuario or "").strip().upper()
    if "CANC" in u:
        return "cancelada"
    if "CERR" in u:
        return "encerrada"
    return None


def detectar(db) -> dict:
    """Detecta, só com Mongo (sem SAP), o que precisa de ação (SP-09.6a/f).

    Retorna {alvo, reabertas}:
    - `alvo`: AUFNR atribuídas que NÃO estão no `sap_backlog` (saíram das abertas) e cujo snapshot
      ainda não foi confirmado (`entrega` ausente OU `status_saida` in {None, nao_confirmada}),
      não superadas. São as que precisam de provisório + re-consulta.
    - `reabertas`: AUFNR que voltaram ao `sap_backlog` mas têm `entrega` não-superada → devem
      voltar a render ao vivo (marcar `superado`).
    """
    abertas = _distinct_ordens(db, COLL_BACKLOG)
    alvo, reabertas = set(), set()
    try:
        cur = db[COLL_ATRIB].find({}, {"ordem": 1, "entrega": 1})
    except Exception:
        return {"alvo": set(), "reabertas": set()}
    for d in cur:
        o = str(d.get("ordem") or "")
        if not o:
            continue
        ent = d.get("entrega")
        if o in abertas:
            if ent and not ent.get("superado"):
                reabertas.add(o)          # reabriu no SAP → snapshot superado
            continue
        # ordem fora do backlog de abertas (saiu). Entra no alvo p/ (re)resolver o estado a partir do
        # STATUS DO USUÁRIO (decisão cliente 2026-07-15). Só NÃO reentra quando já está num terminal
        # do usuário — `encerrada` (CERR) ou `cancelada` (CANC) — ou `reclassificada`. Qualquer outro
        # (None, ativa, e os antigos concluida/teco/nao_confirmada — status de SISTEMA) reentra e é
        # re-resolvido pelo USTXT: isso também MIGRA os snapshots antigos "entregue" p/ o novo modelo.
        saida = ent.get("status_saida") if ent else None
        if ent is None:
            alvo.add(o)
        elif not ent.get("superado"):
            terminal = saida in ("encerrada", "cancelada", "reclassificada")
            tem_desc = bool((ent.get("cabecalho") or {}).get("descricao"))
            # reentra se NÃO é terminal (re-resolve/mantém fresco) OU se é terminal mas ainda sem a
            # descrição/título (backfill único — snapshots resolvidos antes do KTEXT vir do IW39).
            if not terminal or not tem_desc:
                alvo.add(o)
    return {"alvo": alvo, "reabertas": reabertas}


def marcar_reabertas(db, reabertas: set) -> int:
    """Marca `entrega.superado=True` nas ordens que voltaram ao backlog (SP-09.6f). Idempotente."""
    if not reabertas:
        return 0
    r = db[COLL_ATRIB].update_many(
        {"ordem": {"$in": list(reabertas)}, "entrega": {"$ne": None}, "entrega.superado": {"$ne": True}},
        {"$set": {"entrega.superado": True}})
    return getattr(r, "modified_count", 0) or 0


def congelar_provisorio(db, alvo: set, agora: datetime) -> int:
    """Grava snapshot PROVISÓRIO (último-visto das collections-fonte) onde `entrega` ainda é None.

    Faz os números aparecerem imediatamente no card (em vez de "plan — real —"), antes mesmo da
    re-consulta ao SAP. `provisorio=True`, `status_saida="nao_confirmada"`. Idempotente (só grava
    onde não há `entrega`). Retorna nº de ordens congeladas provisoriamente.
    """
    if not alvo:
        return 0
    plan = _agg_por_ordem(db, COLL_PLANEJADO, "planejado_min", alvo)
    real = _agg_por_ordem(db, COLL_REALIZADO, "realizado_min", alvo)
    stt = _status_por_ordem(db, COLL_REALIZADO, alvo)
    n = 0
    for o in alvo:
        p, r = plan.get(o, 0), real.get(o, 0)
        entrega = {"status_saida": "nao_confirmada", "provisorio": True,
                   "planejado_min": p, "realizado_min": r, "aderencia": _aderencia(p, r),
                   "status_sap_raw": stt.get(o), "data_conclusao": None,
                   "congelado_em": agora, "superado": False}
        res = db[COLL_ATRIB].update_many(
            {"ordem": o, "entrega": None}, {"$set": {"entrega": entrega}})
        if getattr(res, "modified_count", 0):
            n += 1
    return n


def recompor_planejado(db, agora: datetime) -> dict:
    """Regrava `entrega.planejado_min` das ordens já congeladas cujo total no IW37 é MAIOR (B54).

    Cura permanente do snapshot que o IW47 rebaixou (só operações apontadas). Roda a cada ciclo e é
    idempotente: só toca quem está abaixo do total do IW37, e nunca reduz. Existe porque a leitura
    do webapp recompõe pelo IW37 em tempo real, mas isso depende da ordem seguir aparecendo no
    snapshot; gravando enquanto ela está lá, o valor certo sobrevive à saída dela do IW37.

    Não toca snapshot `superado` (ordem reaberta usa o valor vivo). Retorna {ordens, minutos}.
    """
    try:
        docs = list(db[COLL_ATRIB].find(
            {"entrega.planejado_min": {"$exists": True}, "entrega.superado": {"$ne": True}},
            {"ordem": 1, "entrega.planejado_min": 1, "entrega.realizado_min": 1}))
    except Exception:
        return {"ordens": 0, "minutos": 0}
    if not docs:
        return {"ordens": 0, "minutos": 0}
    alvo = {str(d.get("ordem")) for d in docs}
    plan = _agg_por_ordem(db, COLL_PLANEJADO, "planejado_min", alvo)
    curadas, ganho = set(), 0
    for d in docs:
        o = str(d.get("ordem"))
        atual = int(((d.get("entrega") or {}).get("planejado_min")) or 0)
        total = int(plan.get(o) or 0)
        if total <= atual:
            continue
        real = int(((d.get("entrega") or {}).get("realizado_min")) or 0)
        try:
            db[COLL_ATRIB].update_many(
                {"ordem": o, "entrega": {"$ne": None}, "entrega.superado": {"$ne": True}},
                {"$set": {"entrega.planejado_min": total,
                          "entrega.aderencia": _aderencia(total, real),
                          "entrega.planejado_recomposto_em": agora}})
        except Exception:
            continue
        if o not in curadas:
            curadas.add(o)
            ganho += total - atual
    return {"ordens": len(curadas), "minutos": ganho}


def _cab_de_status(info: dict) -> dict | None:
    """Cabeçalho parcial (categoria/local/DESCRIÇÃO) a partir do IW39-por-AUFNR. A descrição (KTEXT)
    só vem por aqui (o IW47 não traz KTEXT nas confirmações), então é a fonte do TÍTULO da ordem que
    saiu do backlog. Sem centro da op 0010 (o IW39 não dá nesse grão) → disciplina None e o card usa
    a do técnico (BR-20). None se não há nenhum dado."""
    from ..backlog import _classifica  # noqa: PLC0415 — só quando há alvo
    au = (info.get("auart") or "").strip() or None
    tp = (info.get("tplnr") or "").strip() or None
    desc = (info.get("descricao") or "").strip() or None
    if not (au or tp or desc):
        return None
    return {"categoria": _classifica.derivar_categoria(au) if au else None,
            "disciplina": None,
            "local_instalacao": tp,
            "centro_operacao_0010": None,
            "descricao": desc}


def aplicar_entregas(db, alvo: set, por_ordem: dict, status_map: dict, agora: datetime) -> dict:
    """Resolve o estado de saída de TODA ordem-alvo a partir do STATUS DO USUÁRIO (decisão 2026-07-15).

    Duas fontes: `por_ordem` = IW47 (números — realizado/planejado/aderência; pode faltar p/ ordem
    sem apontamento) e `status_map` = IW39-por-AUFNR ({aufnr: {status_usuario, status_sistema, auart,
    tplnr}}; fail-soft `{}` se a leitura SAP falhou). O `status_saida` vem do USTXT (`_saida_de_ustxt`):
    CERR→`encerrada`, CANC→`cancelada` (terminais — `provisorio=False`, param de reentrar); qualquer
    outro → `ativa` (não-terminal — mantém `provisorio=True`, reentra, e o card mostra o próprio
    status do usuário). Números do IW47 quando vierem, senão mantém o do provisório. Não toca
    snapshot superado. Idempotente. Retorna contagem por categoria.
    """
    conf = {"encerrada": 0, "cancelada": 0, "ativa": 0}
    plan_iw37 = _agg_por_ordem(db, COLL_PLANEJADO, "planejado_min", set(alvo or set()))
    for o in (alvo or set()):
        o = str(o)
        dados = (por_ordem or {}).get(o) or {}
        info = (status_map or {}).get(o) or {}
        doc = db[COLL_ATRIB].find_one({"ordem": o, "entrega": {"$ne": None}},
                                      {"entrega.planejado_min": 1, "entrega.realizado_min": 1,
                                       "entrega.cabecalho": 1, "entrega.status_saida": 1,
                                       "entrega.status_usuario": 1})
        ent0 = (doc or {}).get("entrega") or {}
        # status do usuário do IW39 deste ciclo, ou o já congelado (não perde por falha do IW39)
        ustxt = info.get("status_usuario") or ent0.get("status_usuario")
        saida = _saida_de_ustxt(ustxt)
        if saida is None and ent0.get("status_saida") in ("encerrada", "cancelada"):
            saida = ent0["status_saida"]     # não rebaixa terminal já resolvido só por falta de USTXT
        setc = {"entrega.congelado_em": agora}
        if ustxt:
            setc["entrega.status_usuario"] = ustxt
        if info.get("status_sistema"):
            setc["entrega.status_sistema"] = info["status_sistema"]
            setc["entrega.status_sap_raw"] = info["status_sistema"]   # retrocompat de leitura
        real = dados.get("realizado_min")
        if real is not None:
            setc["entrega.realizado_min"] = int(real)
        # B54: o planejado do IW47 NÃO manda sozinho. O IW47 só devolve operação COM apontamento,
        # e como o manutentor não aponta operação a operação, uma ordem de 5 operações de 30 min
        # era confirmada com 30 min. Vale o maior entre: IW37 (traz a ordem inteira e, ao contrário
        # do que este job supunha, continua trazendo a ordem depois de encerrada), o já congelado
        # no provisório, e o IW47. O realizado segue vindo do IW47, que é a fonte certa dele.
        p_iw47 = dados.get("planejado_min")
        p_iw37 = plan_iw37.get(o)
        cands = [int(x) for x in (p_iw47, p_iw37, ent0.get("planejado_min")) if x is not None]
        p = max(cands) if cands else None
        if p is not None:
            setc["entrega.planejado_min"] = int(p)
        # aderência: recalc com os números finais (planejado consolidado + IW47 quando veio)
        pp = int(p) if p is not None else ent0.get("planejado_min")
        rr = int(real) if real is not None else ent0.get("realizado_min")
        setc["entrega.aderencia"] = _aderencia(pp, rr)
        # cabeçalho: parte do já congelado (não perde centro/disciplina de um IW47 anterior) e
        # completa lacunas com o IW47 deste ciclo (centro/disciplina) e o IW39 (categoria/local/
        # DESCRIÇÃO = título). A descrição só vem do IW39 — é o que recupera o título da ordem.
        cab = dict(ent0.get("cabecalho") or {})
        for src in (dados.get("cabecalho") or {}, _cab_de_status(info) or {}):
            for k, v in src.items():
                if v and not cab.get(k):
                    cab[k] = v
        if cab:
            setc["entrega.cabecalho"] = cab
        if saida in ("encerrada", "cancelada"):
            setc["entrega.status_saida"] = saida
            setc["entrega.provisorio"] = False
            conf[saida] += 1
        else:
            setc["entrega.status_saida"] = "ativa"   # ainda ativo no SAP → reentra e mantém fresco
            setc["entrega.provisorio"] = True
            conf["ativa"] += 1
        db[COLL_ATRIB].update_many(
            {"ordem": o, "entrega": {"$ne": None}, "entrega.superado": {"$ne": True}},
            {"$set": setc})
    return conf
