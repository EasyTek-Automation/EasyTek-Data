# -*- coding: utf-8 -*-
"""Fluxo compartilhado dos tipos ALV (zppprd/nt0001): grade ALV → &XXL → arquivo no share.

Cada script de KPI só fornece os `args` (tx, seleção, layout); o resto do fluxo é aqui.
Devolve Result (não levanta) — o executor cuida do retry/marcação.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime

import pytz

from ...core import path_resolver, kill_excel
from ...core.contracts import Result
from . import zpp_gridcap

logger = logging.getLogger(__name__)
_BRT = pytz.timezone("America/Sao_Paulo")


def _classificar(e: Exception) -> str:
    msg = str(e).lower()
    if "contextmenu" in msg or "selectcontextmenuitem" in msg:
        return "export_alv"
    if "save" in msg or "popup" in msg or "path" in msg or "arquivo nao criado" in msg:
        return "salvamento"
    return "navegacao"


def executar_export(tipo: str, args_fn, ctx) -> Result:
    """`args_fn(path, agora_brt)` -> SimpleNamespace (tx, set, ctx_code='&XXL', save_dir, fname)."""
    agora = datetime.now(tz=pytz.UTC).astimezone(_BRT)
    path = path_resolver.calcular(tipo, agora, ctx.cfg.pasta_input)

    try:
        path_resolver.validar_pasta(ctx.cfg.pasta_input)
    except Exception as e:
        return Result.falha("salvamento", e)
    try:
        kill_excel.kill_preventivo()
    except Exception as e:
        return Result.falha("kill_excel", e)
    try:
        session = ctx.sap()
    except Exception as e:
        return Result.falha("conexao_sap", e)

    before = kill_excel.pids_atuais()
    try:
        args = args_fn(path, agora)
        zpp_gridcap.export_grid(session, args)
    except Exception as e:
        return Result.falha(_classificar(e), e)
    try:
        kill_excel.kill_pos(before, wait=20)
    except Exception as e:
        return Result.falha("kill_excel", e)

    try:
        if not os.path.isfile(path):
            raise OSError(f"arquivo nao criado: {path}")
        size = os.path.getsize(path)
        if size <= 1024:
            raise OSError(f"arquivo vazio ({size} bytes): {path}")
    except Exception as e:
        return Result.falha("validacao_arquivo", e)

    return Result.sucesso(path_xlsx=path, tamanho_bytes=size)
