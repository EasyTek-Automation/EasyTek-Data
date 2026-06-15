# -*- coding: utf-8 -*-
"""Script ZPP_NT0001 — paragens por linha (grade ALV → &XXL → share). Auto-contido.

IDs reais (nt0001-sel.txt): PA_WERKS, SO_BUDAT-LOW/HIGH, PA_HRINI/PA_HRFIN, radP_REL, PA_VARIA.
Janela: 1º dia do mês de D-1 até D-1.
"""
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

from . import _alv

TIPO = "zpp_nt0001"


def _janela(agora):
    ontem = agora - timedelta(days=1)
    return ontem.replace(day=1), ontem


def _args(path, agora):
    ini, fim = _janela(agora)
    sep = "\\" if "\\" in path else "/"
    return SimpleNamespace(
        tx="zpp_nt0001",
        set=[
            "wnd[0]/usr/ctxtPA_WERKS=BR02",
            f"wnd[0]/usr/ctxtSO_BUDAT-LOW={ini.strftime('%d.%m.%Y')}",
            f"wnd[0]/usr/ctxtSO_BUDAT-HIGH={fim.strftime('%d.%m.%Y')}",
            "wnd[0]/usr/ctxtPA_HRINI=00:00:00",
            "wnd[0]/usr/ctxtPA_HRFIN=24:00:00",
            "wnd[0]/usr/radP_REL=@select",
            "wnd[0]/usr/ctxtPA_VARIA=",
        ],
        no_f8=False,
        kill_excel=False,
        ctx_code="&XXL",
        save_dir=path.rsplit(sep, 1)[0],
        fname=path.rsplit(sep, 1)[-1],
    )


def run(job, ctx):
    return _alv.executar_export(TIPO, _args, ctx)
