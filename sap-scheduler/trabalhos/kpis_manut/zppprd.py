# -*- coding: utf-8 -*-
"""Script ZPPPRD — indicadores de produção (grade ALV → &XXL → share). Auto-contido.

Janela: 1º dia do mês de D-1 até D-1 (Bloco I A-03). Layout `/prod.indic`.
"""
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

from . import _alv

TIPO = "zppprd"


def _janela(agora):
    ontem = agora - timedelta(days=1)
    return ontem.replace(day=1), ontem


def _args(path, agora):
    ini, fim = _janela(agora)
    sep = "\\" if "\\" in path else "/"
    return SimpleNamespace(
        tx="zppprd",
        set=[
            "wnd[0]/usr/ctxtP_WERKS=BR02",
            f"wnd[0]/usr/ctxtS_FECFIN-LOW={ini.strftime('%d.%m.%Y')}",
            f"wnd[0]/usr/ctxtS_FECFIN-HIGH={fim.strftime('%d.%m.%Y')}",
            "wnd[0]/usr/ctxtP_VARI=/prod.indic",
            "wnd[0]/usr/radP_REL=@select",
        ],
        no_f8=False,
        kill_excel=False,
        ctx_code="&XXL",
        save_dir=path.rsplit(sep, 1)[0],
        fname=path.rsplit(sep, 1)[-1],
    )


def run(job, ctx):
    return _alv.executar_export(TIPO, _args, ctx)
