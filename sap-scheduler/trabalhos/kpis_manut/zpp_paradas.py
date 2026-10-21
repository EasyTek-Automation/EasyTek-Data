# -*- coding: utf-8 -*-
"""Script `zpp_paradas_pendentes` — retrato da ZPPPARADAS ("Paradas por linha") no Mongo.

KPIReport-v2 BR-14 / SP-24/25 / DS-17. A ZPPPARADAS mostra a parada assim que o operador a
registra; a NT0001 (fonte oficial dos indicadores) só depois que a confirmação da ordem é
lançada. O webapp compara este retrato com `ZPP_Paradas` e marca as que faltam como pendentes.

Fluxo: ZPPPARADAS (CENTRO=BR02, FECHA = 1º do mês de ontem → hoje, R_HORA 00:00–23:59:59)
→ &XXL para uma pasta TEMPORÁRIA do robô (nunca a pasta do zpp-processor, que tentaria ingerir
a planilha como NT0001) → leitura (propaga MOTIVO, descarta subtotais) → snapshot atômico em
`ZPP_Paradas_Lancadas` → apaga o arquivo.

⚠ READ-ONLY. A tela de resultado tem "Mark Reviewed (F6)" e "Save (Ctrl+F10)", que GRAVAM no
SAP. Este script só preenche a seleção, F8 e o &XXL do menu de contexto da grade.
"""
from __future__ import annotations

import logging
import os
import shutil
import tempfile
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytz

from ...core import kill_excel
from ...core.contracts import Result
from ..backlog import _carga
from . import _zpp_paradas_ler as _ler
from . import zpp_gridcap

logger = logging.getLogger(__name__)

TIPO = "zpp_paradas_pendentes"
COLL = "ZPP_Paradas_Lancadas"
_BRT = pytz.timezone("America/Sao_Paulo")


# --------------------------------------------------------------------------- seleção SAP

def _janela(agora):
    """1º dia do mês de ontem → hoje (no dia 1 ainda cobre o mês anterior)."""
    ontem = agora - timedelta(days=1)
    return ontem.replace(day=1), agora


def _args(path, agora):
    ini, fim = _janela(agora)
    return SimpleNamespace(
        tx="ZPPPARADAS",
        set=[
            "wnd[0]/usr/ctxtCENTRO=BR02",
            f"wnd[0]/usr/ctxtFECHA-LOW={ini.strftime('%d.%m.%Y')}",
            f"wnd[0]/usr/ctxtFECHA-HIGH={fim.strftime('%d.%m.%Y')}",
            "wnd[0]/usr/radR_HORA=@select",
            "wnd[0]/usr/ctxtHORA-LOW=00:00:00",
            "wnd[0]/usr/ctxtHORA-HIGH=23:59:59",
            "wnd[0]/usr/ctxtP_LAYOUT=",
        ],
        no_f8=False,
        kill_excel=False,
        ctx_code="&XXL",
        save_dir=os.path.dirname(path),
        fname=os.path.basename(path),
    )


# --------------------------------------------------------------------------- leitura
# (em `_zpp_paradas_ler.py`, sem imports relativos — copiável pro teste no cliente)
normalizar_linhas = _ler.normalizar_linhas
ler_xlsx = _ler.ler_xlsx


def ensure_indexes(db) -> None:
    c = db[COLL]
    c.create_index([("coleta_id", 1)], name="idx_coleta")
    c.create_index([("linha", 1), ("ordem", 1), ("inicio", 1)], name="idx_chave")
    c.create_index([("inicio", 1)], name="idx_inicio")


# --------------------------------------------------------------------------- run

def _mock_rows(ctx):
    """mock_sap: lê a planilha indicada em `ctx.cfg.mock_zpp_paradas_xlsx` (estudo de 07/10)."""
    path = getattr(ctx.cfg, "mock_zpp_paradas_xlsx", "") or ""
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(f"mock_zpp_paradas_xlsx ausente: {path!r}")
    return ler_xlsx(path)


def run(job, ctx):
    agora = datetime.now(tz=pytz.UTC).astimezone(_BRT)
    coleta_id = agora.strftime("%Y%m%d.%H%M")
    coletado_em = agora.replace(tzinfo=None)  # BRT naive, como o resto do relatório

    if getattr(ctx.cfg, "mock_sap", False):
        try:
            rows = _mock_rows(ctx)
        except Exception as e:
            return Result.falha("validacao_arquivo", e)
    else:
        tmpdir = tempfile.mkdtemp(prefix="zppparadas_")
        path = os.path.join(tmpdir, f"ZPPPARADAS_{coleta_id}.xlsx")
        try:
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
                zpp_gridcap.export_grid(session, _args(path, agora))
            except Exception as e:
                msg = str(e).lower()
                fase = "export_alv" if ("contextmenu" in msg or "export" in msg) else "navegacao"
                return Result.falha(fase, e)
            finally:
                try:
                    session.findById("wnd[0]/tbar[0]/okcd").Text = "/n"
                    session.findById("wnd[0]").sendVKey(0)
                except Exception:
                    pass
            try:
                kill_excel.kill_pos(before, wait=20)
            except Exception as e:
                return Result.falha("kill_excel", e)
            try:
                if not os.path.isfile(path):
                    raise OSError(f"arquivo nao criado: {path}")
                rows = ler_xlsx(path)
            except Exception as e:
                return Result.falha("validacao_arquivo", e)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    try:
        docs = normalizar_linhas(rows, coleta_id, coletado_em)
    except Exception as e:
        return Result.falha("validacao_arquivo", e)

    try:
        ensure_indexes(ctx.db)
        n = _carga.gravar_snapshot(ctx.db, COLL, docs, coleta_id, coletado_em)
    except Exception as e:
        return Result.falha("mongo_update", e)

    return Result.sucesso(path_xlsx=f"mongo:{COLL}", tamanho_bytes=n, coleta_id=coleta_id, paradas=n)
