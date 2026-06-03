"""Mapeamento canônico tipo → args do `zpp_gridcap.export_grid` (DS-04 + IM-E1).

`SCRIPT_POR_TIPO` é fonte única da verdade. Adicionar novo tipo no futuro =
1 entrada nesta dict + 1 entrada em `TIPOS_SUPORTADOS` (DS-02 RF-02-22).

`FASE_ENUM` espelha exatamente o enum do schema Mongo (DS-02 RF-02-10).

Bloco I (2026-06-03 — propagacao do fix aplicado no cliente em 02/06):
- Janela de coleta: do PRIMEIRO dia do mes ate D-1 (em vez de so D-1).
  Motivo: zpp-processor faz delete-and-reinsert por `mes_referencia` —
  enviar so D-1 apagaria dias 1..D-2 do mes corrente. Achado A-03.
- IDs do ZPP_NT0001: extraidos do `sap-gate/nt0001-sel.txt` (Script Recording
  do cliente confirmou os campos reais). Placeholder anterior usava `P_WERKS`
  / `S_FECFIN` que NAO existem na transacao ZPP_NT0001 — teria falhado
  silenciosamente. Achado A-04.
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


def _janela_mes_ate_ontem(agora_brt: datetime) -> tuple[datetime, datetime]:
    """Bloco I A-03: janela = (primeiro_dia_do_mes_de_D-1, D-1).

    Ex: hoje=15/06 -> ontem=14/06 -> janela 01/06..14/06.
    Ex: hoje=01/07 -> ontem=30/06 -> janela 01/06..30/06.
    Ex: hoje=01/01 -> ontem=31/12 -> janela 01/12 (ano anterior)..31/12.

    `replace(day=1)` resolve virada de mes E de ano corretamente.
    """
    ontem = agora_brt - timedelta(days=1)
    primeiro_do_mes = ontem.replace(day=1)
    return primeiro_do_mes, ontem


def _args_zppprd(path_xlsx: str, agora_brt: datetime) -> SimpleNamespace:
    """Args ZPPPRD — filtros confirmados em RV-02 + ciclo real do cliente.

    Janela: PRIMEIRO_DIA_DO_MES_DE_D-1 ate D-1 (Bloco I A-03).
    Captura jornadas do mes corrente ate o dia que acabou — alinha com
    delete-and-reinsert por mes_referencia do zpp-processor.
    """
    inicio, fim = _janela_mes_ate_ontem(agora_brt)
    return SimpleNamespace(
        tx="zppprd",
        set=[
            "wnd[0]/usr/ctxtP_WERKS=BR02",
            f"wnd[0]/usr/ctxtS_FECFIN-LOW={_ddmmaaaa(inicio)}",
            f"wnd[0]/usr/ctxtS_FECFIN-HIGH={_ddmmaaaa(fim)}",
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
    """Args ZPP_NT0001 — IDs reais extraidos do `nt0001-sel.txt` (Bloco I A-04).

    Placeholder anterior usava `P_WERKS` / `S_FECFIN` (estrutura do ZPPPRD),
    que NAO existem nesta transacao — exporto teria falhado silenciosamente.

    IDs corretos (ZPP_NT0001):
    - PA_WERKS                    : centro (BR02)
    - SO_BUDAT-LOW / SO_BUDAT-HIGH: janela de datas
    - PA_HRINI / PA_HRFIN         : janela de horas (00:00:00 / 24:00:00)
    - radP_REL                    : modo "@select"
    - PA_VARIA                    : variante (vazio = default)

    Janela: PRIMEIRO_DIA_DO_MES_DE_D-1 ate D-1 (mesma regra do ZPPPRD).
    """
    inicio, fim = _janela_mes_ate_ontem(agora_brt)
    return SimpleNamespace(
        tx="zpp_nt0001",
        set=[
            "wnd[0]/usr/ctxtPA_WERKS=BR02",
            f"wnd[0]/usr/ctxtSO_BUDAT-LOW={_ddmmaaaa(inicio)}",
            f"wnd[0]/usr/ctxtSO_BUDAT-HIGH={_ddmmaaaa(fim)}",
            "wnd[0]/usr/ctxtPA_HRINI=00:00:00",
            "wnd[0]/usr/ctxtPA_HRFIN=24:00:00",
            "wnd[0]/usr/radP_REL=@select",
            "wnd[0]/usr/ctxtPA_VARIA=",  # vazio = variante default
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
