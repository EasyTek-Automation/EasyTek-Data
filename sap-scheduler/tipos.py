"""Mapeamento canônico tipo → args do `zpp_gridcap.export_grid` (DS-04 + IM-E1).

`SCRIPT_POR_TIPO` é fonte única da verdade. Adicionar novo tipo no futuro =
1 entrada nesta dict + 1 entrada em `TIPOS_SUPORTADOS` (DS-02 RF-02-22).

`FASE_ENUM` espelha exatamente o enum do schema Mongo (DS-02 RF-02-10).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Callable

TIPOS_SUPORTADOS = ("zppprd", "zpp_nt0001")

FASE_ENUM = (
    "conexao_sap",
    "navegacao",
    "export_alv",
    "salvamento",
    "validacao_arquivo",
    "kill_excel",
    "mongo_update",
    "desconhecido",
)


def _ddmmaaaa(d: datetime) -> str:
    """SAP variant format: dd.mm.yyyy."""
    return d.strftime("%d.%m.%Y")


def _args_zppprd(path_xlsx: str, agora_brt: datetime) -> SimpleNamespace:
    """Args ZPPPRD — filtros confirmados em RV-02 + PROMPT-claudinho-export-C.md.

    Datas: D-1 (dia anterior à execução) — captura jornada do dia que acabou.
    """
    ontem = agora_brt - timedelta(days=1)
    return SimpleNamespace(
        tx="zppprd",
        set=[
            "wnd[0]/usr/ctxtP_WERKS=BR02",
            f"wnd[0]/usr/ctxtS_FECFIN-LOW={_ddmmaaaa(ontem)}",
            f"wnd[0]/usr/ctxtS_FECFIN-HIGH={_ddmmaaaa(ontem)}",
            "wnd[0]/usr/ctxtP_VARI=/prod.indic",
            "wnd[0]/usr/radP_REL=@select",
        ],
        no_f8=False,
        kill_excel=False,  # daemon faz kill via kill_excel.py
        ctx_code="&XXL",
        save_dir=str(path_xlsx).rsplit("\\", 1)[0] if "\\" in str(path_xlsx) else str(path_xlsx).rsplit("/", 1)[0],
        fname=str(path_xlsx).rsplit("\\", 1)[-1] if "\\" in str(path_xlsx) else str(path_xlsx).rsplit("/", 1)[-1],
    )


def _args_zpp_nt0001(path_xlsx: str, agora_brt: datetime) -> SimpleNamespace:
    """Args ZPP_NT0001 — **filtros placeholder até VF-06-11 confirmar** (RV-02 F-02-11).

    Bloqueio aberto fase 06: SAP Script Recording no cliente vai gravar os
    IDs SAP corretos. Atualmente usa estrutura espelhada do ZPPPRD como base.
    """
    ontem = agora_brt - timedelta(days=1)
    return SimpleNamespace(
        tx="zpp_nt0001",
        set=[
            "wnd[0]/usr/ctxtP_WERKS=BR02",
            # TODO IM-G3: confirmar nomes exatos dos IDs SAP via Script Recording
            f"wnd[0]/usr/ctxtS_FECFIN-LOW={_ddmmaaaa(ontem)}",
            f"wnd[0]/usr/ctxtS_FECFIN-HIGH={_ddmmaaaa(ontem)}",
        ],
        no_f8=False,
        kill_excel=False,
        ctx_code="&XXL",
        save_dir=str(path_xlsx).rsplit("\\", 1)[0] if "\\" in str(path_xlsx) else str(path_xlsx).rsplit("/", 1)[0],
        fname=str(path_xlsx).rsplit("\\", 1)[-1] if "\\" in str(path_xlsx) else str(path_xlsx).rsplit("/", 1)[-1],
    )


SCRIPT_POR_TIPO: dict[str, Callable[[str, datetime], SimpleNamespace]] = {
    "zppprd": _args_zppprd,
    "zpp_nt0001": _args_zpp_nt0001,
}
