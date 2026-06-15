# -*- coding: utf-8 -*-
"""Script custo_orcado — orçado+executado por conta (ZBRCO019) → AMG_CustoResumo.

Report Painter (não exporta ALV): lê por SCRAPE de rótulos. Grava Mongo direto. Auto-contido.
Janela: 2 meses (mês corrente + anterior, até D-1) → 1 scrape por período.
"""
from __future__ import annotations

from datetime import datetime

import pytz

from ...core.contracts import Result
from . import custo_collect, _carga

COLL = "AMG_CustoResumo"
_BRT = pytz.timezone("America/Sao_Paulo")


def _periodos(ini, fim):
    pers, y, m = [], ini.year, ini.month
    while (y, m) <= (fim.year, fim.month):
        pers.append((y, m))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return pers


def run(job, ctx):
    agora = datetime.now(tz=pytz.UTC).astimezone(_BRT)
    ini, fim = custo_collect.janela_dois_meses(agora)
    try:
        session = ctx.sap()
    except Exception as e:
        return Result.falha("conexao_sap", e)
    try:
        docs = custo_collect.collect_resumo(session, _periodos(ini, fim))
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
