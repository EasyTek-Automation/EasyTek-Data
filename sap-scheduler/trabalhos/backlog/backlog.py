# -*- coding: utf-8 -*-
"""Script `backlog` — coleta o backlog de manutenção (BR02) e grava snapshot em `sap_backlog`.

Fluxo (DS-01/04/05): IW39+IW37 (ou mock) → deriva categoria/disciplina/subclass → snapshot
atômico no Mongo. Read-only no SAP. Auto-contido.
"""
from __future__ import annotations

from datetime import datetime

import pytz

from ...core.contracts import Result
from . import _carga, _classifica, _coleta

TIPO = "backlog"
COLL = "sap_backlog"
_BRT = pytz.timezone("America/Sao_Paulo")


def run(job, ctx):
    agora = datetime.now(tz=pytz.UTC).astimezone(_BRT)
    coleta_id = agora.strftime("%Y%m%d.%H%M")

    # 1. coleta (SAP real ou mock para teste sem SAP — ctx.cfg.mock_sap)
    if getattr(ctx.cfg, "mock_sap", False):
        ordens = _coleta.mock_ordens()
    else:
        try:
            session = ctx.sap()
        except Exception as e:
            return Result.falha("conexao_sap", e)
        try:
            ordens = _coleta.coletar_ordens(session)
        except Exception as e:
            return Result.falha("navegacao", e)
        finally:
            try:
                session.findById("wnd[0]/tbar[0]/okcd").Text = "/n"
                session.findById("wnd[0]").sendVKey(0)
            except Exception:
                pass

    # 2. descarta tipos fora do mapa (defesa: PM04/ZPM* não entram) + deriva e monta docs
    ordens = _classifica.filtrar_categorias_validas(ordens)
    docs = [_classifica.montar_doc(o, coleta_id, agora) for o in ordens]

    # 3. snapshot atômico no Mongo
    try:
        _carga.ensure_indexes(ctx.db, COLL)
        n = _carga.gravar_snapshot(ctx.db, COLL, docs, coleta_id, agora)
    except Exception as e:
        return Result.falha("mongo_update", e)

    return Result.sucesso(path_xlsx=f"mongo:{COLL}", tamanho_bytes=n, coleta_id=coleta_id, ordens=n)
