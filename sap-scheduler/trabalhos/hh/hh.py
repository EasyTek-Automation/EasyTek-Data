# -*- coding: utf-8 -*-
"""Jobs `hh_planejado` (IW37) e `hh_realizado` (IW47) — coleta de Hora-Homem (BR02).

Cada job: coleta a tela via ALV nativo (ou mock), agrega por operação (dedup planejado /
soma realizado — BR-03), confere sanidade (BR-10) e grava snapshot atômico na sua
collection-fonte. Read-only no SAP. Contrato `run(job, ctx) -> Result`.

**Universo único (B41):** o quadro mostra exatamente as ordens **ABERTAS** (IW39) **∪ ATRIBUÍDAS**
no quadro (`hh_planejamento`). Os DOIS jobs coletam esse mesmo conjunto (`_aufnr_alvo`), por
**multisseleção de AUFNR, sem janela de datas** — o volume é limitado pela quantidade de ordens
(não pelo período, o que evita o dump ABAP das janelas largas) e alcança apontamento/planejado de
qualquer idade. Assim planejado (IW37 `ARBEI`) e realizado (IW47 `ISMNW`) ficam simétricos: toda
ordem que o quadro exibe — no backlog OU já encerrada mas atribuída — é coberta dos dois lados.
"""
from __future__ import annotations

from datetime import datetime

import pytz

from ...core.contracts import Result
from . import _agg, _carga, _coleta, _entregas

COLL_PLANEJADO = "sap_hh_planejado"
COLL_REALIZADO = "sap_hh_realizado"
COLL_ATRIB = "hh_planejamento"   # collection do webapp: atribuições do PCM (acoplamento B40/B41)
_BRT = pytz.timezone("America/Sao_Paulo")


def _agora_brt() -> datetime:
    """Agora no fuso de São Paulo (base do coleta_id)."""
    return datetime.now(tz=pytz.UTC).astimezone(_BRT)


def _aufnr_alvo(ctx, session) -> list:
    """Universo de coleta dos dois jobs = ordens ABERTAS do IW39 ∪ ATRIBUÍDAS no quadro (B40/B41).

    As abertas cobrem a fila; as atribuídas cobrem ordem já ENCERRADA que o quadro ainda mostra
    como card atribuído. Como a coleta por AUFNR é SEM janela, alcança apontamento/planejado de
    qualquer idade.

    **Acoplamento deliberado:** LÊ a collection `hh_planejamento` do webapp — exceção consciente à
    regra "jobs não se acoplam por dados". Degradação graciosa: se a leitura do Mongo falhar, segue
    só com as abertas do IW39.
    """
    from ..backlog._coleta import _iw39_ordens  # reuso da consulta IW39 (não da collection)
    aufnr = {str(a) for a in _iw39_ordens(session).keys()}
    try:
        atrib = {str(o) for o in ctx.db[COLL_ATRIB].distinct("ordem") if o}
        aufnr |= atrib
    except Exception:
        pass  # Mongo indisponível → segue só com as abertas (degradação graciosa)
    return list(aufnr)


def _coletar_planejado(ctx):
    """Coleta o planejado (IW37 `ARBEI`) das ordens-ALVO (abertas ∪ atribuídas), SEM janela (B41).

    Espelha o realizado: IW37 por multisseleção de `_aufnr_alvo`. O B14 já tinha tirado a janela
    FSAVD (estoura dump ABAP); o B41 amplia a fila de "só abertas" para "abertas ∪ atribuídas", de
    modo que ordem encerrada ainda atribuída no quadro (entregue) continue com texto/planejado/
    centro — senão o card entregue fica sem descrição/planejado/aderência/centro.
    """
    if getattr(ctx.cfg, "mock_sap", False):
        return _coleta.mock_planejado()
    session = ctx.sap()
    try:
        aufnr = _aufnr_alvo(ctx, session)
        if not aufnr:
            raise RuntimeError("hh_planejado: nenhuma AUFNR-alvo (IW39 vazio e sem atribuições)")
        return _coleta.coletar_planejado(session, aufnr)
    finally:
        try:
            session.findById("wnd[0]/tbar[0]/okcd").Text = "/n"
            session.findById("wnd[0]").sendVKey(0)
        except Exception:
            pass


def _coletar_dirigido(ctx):
    """Coleta o realizado (IW47 `ISMNW`) das ordens-ALVO (abertas ∪ atribuídas), SEM janela (B41).

    Caminho ÚNICO do realizado (o B41 aposentou a janela `ERSDA` do B39 — redundante: encerrada
    que importa é a atribuída, já em `_aufnr_alvo`). Pega apontamento de qualquer idade: ordem
    aberta em pausa (apontamento antigo) e ordem encerrada ainda atribuída no quadro. Espelha
    `_coletar_planejado`: IW47 por multisseleção `AUFNR_O`, variante `/TRAB REAL`.
    """
    if getattr(ctx.cfg, "mock_sap", False):
        return _coleta.mock_realizado()
    session = ctx.sap()
    try:
        aufnr = _aufnr_alvo(ctx, session)
        if not aufnr:
            raise RuntimeError("hh_realizado: nenhuma AUFNR-alvo (IW39 vazio e sem atribuições)")
        return _coleta.coletar_realizado_por_aufnr(session, aufnr)
    finally:
        try:
            session.findById("wnd[0]/tbar[0]/okcd").Text = "/n"
            session.findById("wnd[0]").sendVKey(0)
        except Exception:
            pass


def run_planejado(job, ctx):
    """Job `hh_planejado`: IW37 (`ARBEI`) por multisseleção das ordens-ALVO (abertas ∪ atribuídas).

    B14 tirou a janela FSAVD (estoura dump ABAP); B41 amplia a fila para `_aufnr_alvo` (abertas ∪
    atribuídas) — simétrico ao realizado, para a ordem entregue (encerrada + atribuída) manter
    texto/planejado/centro. Read-only. Agrega por operação; a soma por ordem é no webapp.
    """
    agora = _agora_brt()
    coleta_id = agora.strftime("%Y%m%d.%H%M")

    try:
        rows = _coletar_planejado(ctx)
    except RuntimeError as e:
        return Result.falha("navegacao", e)
    except Exception as e:
        return Result.falha("conexao_sap", e)

    docs, info = _agg.agregar_planejado(rows, coleta_id, agora)
    if not _agg.checar_sanidade_total(rows, info["total_planejado_min"], "ARBEI"):
        return Result.falha("validacao_arquivo",
                            RuntimeError("hh_planejado: soma do planejado diverge da linha de total do ALV"))
    try:
        _carga.ensure_indexes(ctx.db, COLL_PLANEJADO)
        n = _carga.gravar_snapshot(ctx.db, COLL_PLANEJADO, docs, coleta_id, agora)
    except Exception as e:
        return Result.falha("mongo_update", e)

    return Result.sucesso(path_xlsx=f"mongo:{COLL_PLANEJADO}", tamanho_bytes=n,
                          coleta_id=coleta_id, operacoes=n,
                          total_planejado_min=info["total_planejado_min"])


def run_realizado(job, ctx):
    """Job `hh_realizado`: IW47 (`ISMNW`) por multisseleção das ordens-ALVO (abertas ∪ atribuídas).

    Caminho ÚNICO desde o B41 (aposentou a janela `ERSDA` do B39 — redundante: encerrada que
    importa é a atribuída, já em `_aufnr_alvo`). Sem janela → apontamento de qualquer idade.
    Read-only. Agrega por operação (soma das confirmações — BR-03); soma por ordem no webapp.
    """
    agora = _agora_brt()
    coleta_id = agora.strftime("%Y%m%d.%H%M")

    try:
        rows = _coletar_dirigido(ctx)
    except RuntimeError as e:
        return Result.falha("navegacao", e)
    except Exception as e:
        return Result.falha("conexao_sap", e)

    docs, info = _agg.agregar_realizado(rows, coleta_id, agora)
    if not _agg.checar_sanidade_total(rows, info["total_realizado_min"], "ISMNW"):
        return Result.falha("validacao_arquivo",
                            RuntimeError("hh_realizado: soma do realizado diverge da linha de total do ALV (BR-10)"))
    try:
        _carga.ensure_indexes(ctx.db, COLL_REALIZADO)
        n = _carga.gravar_snapshot(ctx.db, COLL_REALIZADO, docs, coleta_id, agora)
    except Exception as e:
        return Result.falha("mongo_update", e)

    return Result.sucesso(path_xlsx=f"mongo:{COLL_REALIZADO}", tamanho_bytes=n,
                          coleta_id=coleta_id, operacoes=n,
                          total_realizado_min=info["total_realizado_min"])


def _reconsultar_realizado(ctx, aufnr):
    """Re-consulta IW47 dirigida (só as AUFNR-alvo) ou mock. Read-only (BR-20/SP-09.6b)."""
    if getattr(ctx.cfg, "mock_sap", False):
        return _coleta.mock_realizado_por_aufnr(aufnr)
    session = ctx.sap()
    try:
        return _coleta.coletar_realizado_por_aufnr(session, aufnr)
    finally:
        try:
            session.findById("wnd[0]/tbar[0]/okcd").Text = "/n"
            session.findById("wnd[0]").sendVKey(0)
        except Exception:
            pass


def _reconsultar_status(ctx, aufnr):
    """Status de ordem (STTXT/USTXT) das AUFNR que saíram do backlog SEM confirmação no IW47
    (canceladas/TECO). IW39-por-AUFNR, read-only e FAIL-SOFT: qualquer erro → `{}` (as ordens ficam
    nao_confirmada e reentram; nunca derruba o job). Mock: `{}`."""
    if getattr(ctx.cfg, "mock_sap", False):
        return _coleta.mock_status_por_aufnr(aufnr)
    try:
        session = ctx.sap()
    except Exception:
        return {}
    try:
        return _coleta.coletar_status_por_aufnr(session, aufnr)
    finally:
        try:
            session.findById("wnd[0]/tbar[0]/okcd").Text = "/n"
            session.findById("wnd[0]").sendVKey(0)
        except Exception:
            pass


def _por_ordem_realizado(rows, coleta_id, agora) -> dict:
    """Agrega o retorno da re-consulta IW47 por ORDEM: {aufnr: {realizado_min, planejado_min, status_sap}}.

    Reusa `_agg` (grão de operação): `agregar_realizado` (Σ ISMNW + STTXT) e `agregar_planejado`
    (dedup ARBEI — o IW47 também traz `ARBEI`, ver `TARGET_IW47`). O planejado é essencial aqui:
    a ordem já concluída **não está** em `sap_hh_planejado` (caiu do snapshot de abertas), então o
    ARBEI do próprio IW47 é a única fonte do plano p/ a aderência final (BR-09). Descarta a linha
    de total (ordem vazia — BR-10)."""
    real_docs, _ = _agg.agregar_realizado(rows, coleta_id, agora)
    plan_docs, _ = _agg.agregar_planejado(rows, coleta_id, agora)
    por_ordem: dict = {}

    def _slot(o):
        return por_ordem.setdefault(o, {"realizado_min": 0, "planejado_min": 0, "status_sap": None})

    for d in real_docs:
        o = str(d.get("ordem") or "").strip()
        if not o:
            continue
        e = _slot(o)
        e["realizado_min"] += int(d.get("realizado_min") or 0)
        if d.get("status_sap"):
            e["status_sap"] = d["status_sap"]
    for d in plan_docs:                        # planejado por ordem = Σ ARBEI (dedup por operação)
        o = str(d.get("ordem") or "").strip()
        if not o:
            continue
        _slot(o)["planejado_min"] += int(d.get("planejado_min") or 0)

    # cabeçalho por ordem (B29): a ordem fechada saiu do sap_backlog (única fonte do cabeçalho no
    # webapp), então congelamos o que o IW47 já traz — categoria (AUART) + disciplina (centro da
    # op 0010) + local (TPLNR). Reusa o classificador do backlog (mesmas regras BR-02/BR-07). A
    # DESCRIÇÃO (KTEXT) ainda não vem no TARGET_IW47 — follow-up.
    from ..backlog import _classifica  # noqa: PLC0415
    cab_raw: dict = {}
    for r in rows:
        o = str(r.get("AUFNR") or "").strip()
        if not o:
            continue
        c = cab_raw.setdefault(o, {"auart": None, "tplnr": None, "centro0010": None})
        if r.get("AUART") and not c["auart"]:
            c["auart"] = str(r.get("AUART")).strip()
        if r.get("TPLNR") and not c["tplnr"]:
            c["tplnr"] = str(r.get("TPLNR")).strip()
        if str(r.get("VORNR") or "").strip() == "0010" and r.get("PARBPL"):
            c["centro0010"] = str(r.get("PARBPL")).strip().upper()
    for o, c in cab_raw.items():
        if o in por_ordem:
            centro = c["centro0010"]
            por_ordem[o]["cabecalho"] = {
                "categoria": _classifica.derivar_categoria(c["auart"]),
                "disciplina": _classifica.derivar_disciplina(centro or ""),
                "local_instalacao": c["tplnr"],
                "centro_operacao_0010": centro,
            }
    return por_ordem


def run_entregas(job, ctx):
    """Job `hh_entregas`: congela o snapshot das ordens atribuídas que saíram do backlog (BR-20).

    Detecta (só Mongo) as atribuídas que não estão mais no `sap_backlog`, marca reaberturas,
    congela um provisório (números aparecem já) e faz a re-consulta IW47 dirigida dessas AUFNR
    para confirmar realizado/status finais. Roda por ÚLTIMO no ciclo (depende do `sap_backlog`
    fresco). Read-only no SAP. Se não há alvo, não abre sessão SAP (barato — SP-09.6a).
    """
    agora = _agora_brt()
    coleta_id = agora.strftime("%Y%m%d.%H%M")
    db = ctx.db

    det = _entregas.detectar(db)
    reab = _entregas.marcar_reabertas(db, det["reabertas"])
    # B54: cura permanente do planejado que o IW47 rebaixou nos snapshots já congelados. Só Mongo,
    # roda antes do early-return porque independe de haver ordem saindo do backlog neste ciclo.
    rec = _entregas.recompor_planejado(db, agora)
    alvo = det["alvo"]
    if not alvo:
        return Result.sucesso(path_xlsx=f"mongo:{_entregas.COLL_ATRIB}", tamanho_bytes=0,
                              coleta_id=coleta_id, operacoes=0, reabertas=reab,
                              alvo=0, confirmadas=0,
                              recompostas=rec["ordens"], recompostas_min=rec["minutos"])

    prov = _entregas.congelar_provisorio(db, alvo, agora)   # números já aparecem no card

    try:
        rows = _reconsultar_realizado(ctx, sorted(alvo))
    except RuntimeError as e:
        return Result.falha("navegacao", e)      # provisório persistido; retry no próximo ciclo
    except Exception as e:
        return Result.falha("conexao_sap", e)

    por_ordem = _por_ordem_realizado(rows, coleta_id, agora)   # IW47 → números (realizado/planejado)

    # STATUS DO USUÁRIO de TODAS as alvo (decisão 2026-07-15): o estado de saída vem do USTXT, não do
    # status de sistema. O IW47 não traz USTXT (só STTXT), então busca via IW39-por-AUFNR (fail-soft:
    # `{}` se falhar → ordens ficam `ativa` e reentram, sem quebrar o job).
    status_map = _reconsultar_status(ctx, sorted(alvo))
    try:
        res = _entregas.aplicar_entregas(db, alvo, por_ordem, status_map, agora)
    except Exception as e:
        return Result.falha("mongo_update", e)

    return Result.sucesso(path_xlsx=f"mongo:{_entregas.COLL_ATRIB}", tamanho_bytes=res["encerrada"],
                          coleta_id=coleta_id, operacoes=len(por_ordem), reabertas=reab,
                          alvo=len(alvo), provisorios=prov,
                          encerradas=res["encerrada"], canceladas=res["cancelada"], ativas=res["ativa"],
                          recompostas=rec["ordens"], recompostas_min=rec["minutos"])
