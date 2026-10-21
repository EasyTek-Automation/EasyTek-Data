# -*- coding: utf-8 -*-
"""Script custo_exec — lançamentos reais de manutenção (KSB1) → AMG_CustoLancamentos.

Read-only no SAP (lê a grade VIA B). Grava Mongo direto. Auto-contido.
Janela: 2 meses INTEIROS (mês anterior + corrente) — ver `custo_collect.janela_dois_meses`.
"""
from __future__ import annotations

from datetime import datetime

import pytz

from ...core.contracts import Result
from . import custo_collect, _carga

COLL = "AMG_CustoLancamentos"
COLL_CENTROS = "AMG_CustoCentros"   # de/para código→nome do centro (OBJ_TXT da KSB1)
COLL_CONTAS = "AMG_CustoContas"     # de/para código→nome da conta  (CEL_KTXT da KSB1)
COLL_COMP = "AMG_CustoOrdemComponentes"   # itens do almoxarifado por ordem (MB25, BR-15)
_BRT = pytz.timezone("America/Sao_Paulo")


def run(job, ctx):
    agora = datetime.now(tz=pytz.UTC).astimezone(_BRT)
    ini, fim = custo_collect.janela_dois_meses(agora)
    try:
        session = ctx.sap()
    except Exception as e:
        return Result.falha("conexao_sap", e)
    try:
        docs = custo_collect.collect_lancamentos(session, ini, fim)
    except Exception as e:
        return Result.falha("navegacao", e)
    finally:
        try:
            session.findById("wnd[0]/tbar[0]/okcd").Text = "/n"
            session.findById("wnd[0]").sendVKey(0)
        except Exception:
            pass
    try:
        n = _carga.gravar(ctx.db, COLL, docs)
        # de/para de nome (centro/conta) extraído da mesma grade — upsert idempotente.
        # Não interrompe a carga principal se falhar (nome é complementar ao dado).
        try:
            cen, con = custo_collect.depara_de_docs(docs)
            _carga.upsert_depara(ctx.db, COLL_CENTROS, cen)
            _carga.upsert_depara(ctx.db, COLL_CONTAS, con)
        except Exception:
            pass
        # BR-15: itens do almoxarifado das ordens de liquidação, via MB25 em lote.
        # Best-effort — falha aqui não invalida a carga principal de lançamentos.
        try:
            ordens = sorted({d["ordem_emissora"] for d in docs
                             if d.get("familia") == "liquidacao" and d.get("ordem_emissora")})
            if ordens:
                mes_ref = max((d.get("mes_referencia") or "") for d in docs)
                comp = custo_collect.collect_componentes(session, ordens, mes_ref)
                _carga.gravar_componentes(ctx.db, COLL_COMP, comp, ordens)
        except Exception:
            pass
    except Exception as e:
        return Result.falha("mongo_update", e)
    # a janela REAL usada fica no doc do job (`resultado.janela`): o daemon é o dono da
    # regra e recalcula — `parametros.janela`, gravado pelo webapp, é ignorado (CONTRATO §5).
    return Result.sucesso(path_xlsx=f"mongo:{COLL}", tamanho_bytes=n,
                          janela={"inicio": custo_collect._ddmm(ini),
                                  "fim": custo_collect._ddmm(fim)})
