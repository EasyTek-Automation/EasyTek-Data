# -*- coding: utf-8 -*-
"""Script custo_exec — lançamentos reais de manutenção (KSB1) → AMG_CustoLancamentos.

Read-only no SAP (lê a grade VIA B). Grava Mongo direto. Auto-contido.
Janela: 2 meses (mês corrente + anterior, até D-1).
"""
from __future__ import annotations

from datetime import datetime

import pytz

from ...core.contracts import Result
from . import custo_collect, _carga

COLL = "AMG_CustoLancamentos"
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
    except Exception as e:
        return Result.falha("mongo_update", e)
    return Result.sucesso(path_xlsx=f"mongo:{COLL}", tamanho_bytes=n)
