"""Executor SAP — orquestra 7 fases por job (DS-04 + IM-E4 + IM-E6 mock).

Cada fase é encapsulada em `try/except` que levanta `ExcecaoClassificada(fase, original)`.
`executor.executar_job` captura e atualiza Mongo com `erro.fase` correto.

Em modo `MOCK_SAP=true` (IM-E6), as fases SAP (`conexao_sap`, `navegacao`, `export_alv`,
`salvamento`) são substituídas por `_mock_export` que copia `.xlsx` aleatório de
`AUDIT_MAIO_DIR` pra `path_xlsx`. Permite smoke E2E local sem SAPlogon real.
"""
from __future__ import annotations

import logging
import os
import random
import shutil
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import pytz

from . import kill_excel
from . import path_resolver
from . import tipos
from .config import DaemonConfig

logger = logging.getLogger(__name__)


class ExcecaoClassificada(Exception):
    """Exceção interna com `fase` (FASE_ENUM) carregada + exception original."""

    def __init__(self, fase: str, original: BaseException, mensagem: Optional[str] = None):
        assert fase in tipos.FASE_ENUM, f"fase invalida: {fase!r}"
        self.fase = fase
        self.original = original
        super().__init__(mensagem or f"[{fase}] {original}")


def _classificar_export_grid_error(e: Exception) -> str:
    """Mapeia substring da mensagem → fase. Decisão fixada em DS-04."""
    msg = str(e).lower()
    if "contextmenu" in msg or "selectcontextmenuitem" in msg:
        return "export_alv"
    if "save" in msg or "popup" in msg or "path" in msg or "arquivo nao criado" in msg:
        return "salvamento"
    if "grid" in msg or "navega" in msg or "render" in msg:
        return "navegacao"
    return "navegacao"  # fallback razoável


def _fase_pre_validacao(cfg: DaemonConfig) -> None:
    try:
        path_resolver.validar_pasta(cfg.pasta_input)
    except Exception as e:
        raise ExcecaoClassificada("salvamento", e)


def _fase_kill_pre() -> None:
    try:
        kill_excel.kill_preventivo()
    except Exception as e:
        raise ExcecaoClassificada("kill_excel", e)


def _fase_conexao(sap_gate_dir: Path):
    """Importa zpp_gridcap (com AJ-02-01 aplicado) + conecta engine SAP."""
    try:
        if str(sap_gate_dir) not in sys.path:
            sys.path.insert(0, str(sap_gate_dir))
        import zpp_gridcap  # noqa: PLC0415 — lazy import (necessário pelo sys.path)

        engine = zpp_gridcap.get_engine()  # AJ-02-01: levanta RuntimeError em falha
        return engine, zpp_gridcap
    except (RuntimeError, ImportError) as e:
        raise ExcecaoClassificada("conexao_sap", e)
    except Exception as e:
        raise ExcecaoClassificada("conexao_sap", e)


def _fase_export(zpp_gridcap_mod, engine, args: SimpleNamespace) -> None:
    try:
        session = engine.Children(0).Children(0)
        zpp_gridcap_mod.export_grid(session, args)  # AJ-02-02: levanta em falhas críticas
    except RuntimeError as e:
        raise ExcecaoClassificada(_classificar_export_grid_error(e), e)
    except Exception as e:
        raise ExcecaoClassificada("navegacao", e)


def _fase_kill_pos(before_pids: set[int]) -> None:
    try:
        kill_excel.kill_pos(before_pids, wait=20)
    except Exception as e:
        raise ExcecaoClassificada("kill_excel", e)


def _fase_validacao(path_xlsx: str) -> int:
    """SP-04 RF-04-21..23. Retorna tamanho_bytes pra resultado."""
    try:
        if not os.path.isfile(path_xlsx):
            raise OSError(f"arquivo nao criado: {path_xlsx}")
        size = os.path.getsize(path_xlsx)
        if size <= 1024:
            raise OSError(f"arquivo vazio ({size} bytes): {path_xlsx}")
        return size
    except Exception as e:
        raise ExcecaoClassificada("validacao_arquivo", e)


def _mock_export(path_xlsx: str, cfg: DaemonConfig) -> None:
    """IM-E6: copia .xlsx aleatorio de AUDIT_MAIO_DIR pra path_xlsx.

    Substitui fases SAP em modo MOCK_SAP=true. Mantém validação real intacta.
    """
    if cfg.audit_maio_dir is None or not cfg.audit_maio_dir.exists():
        raise ExcecaoClassificada(
            "conexao_sap",
            FileNotFoundError(f"AUDIT_MAIO_DIR ausente ou inacessivel: {cfg.audit_maio_dir}"),
        )

    candidatos = list(cfg.audit_maio_dir.glob("*.XLSX")) + list(cfg.audit_maio_dir.glob("*.xlsx"))
    if not candidatos:
        raise ExcecaoClassificada(
            "conexao_sap",
            FileNotFoundError(f"nenhum .xlsx em {cfg.audit_maio_dir}"),
        )

    src = random.choice(candidatos)
    logger.info("[mock] copiando %s -> %s", src.name, path_xlsx)
    shutil.copyfile(str(src), path_xlsx)


def run(job: dict, cfg: DaemonConfig) -> dict:
    """Executa 1 job. Retorna `resultado` dict; levanta `ExcecaoClassificada`.

    Modo MOCK_SAP: pula fases SAP, copia .xlsx do Audit Maio.
    """
    tipo = job["tipo"]
    if tipo not in tipos.SCRIPT_POR_TIPO:
        raise ExcecaoClassificada("desconhecido", ValueError(f"tipo {tipo!r} sem mapeamento"))

    iniciado_em = datetime.now(tz=pytz.UTC)
    agora_brt = iniciado_em.astimezone(pytz.timezone("America/Sao_Paulo"))
    args_factory = tipos.SCRIPT_POR_TIPO[tipo]
    path_xlsx = path_resolver.calcular(tipo, agora_brt, cfg.pasta_input)
    logger.info("[exec] iniciando export | tipo=%s path=%s mock=%s", tipo, path_xlsx, cfg.mock_sap)

    _fase_pre_validacao(cfg)
    _fase_kill_pre()

    if cfg.mock_sap:
        # IM-E6: pula fases SAP, copia .xlsx real do Audit Maio
        _mock_export(path_xlsx, cfg)
    else:
        engine, zpp_gridcap_mod = _fase_conexao(cfg.sap_gate_dir)
        before_pids = kill_excel.pids_atuais()
        args = args_factory(path_xlsx, agora_brt)
        _fase_export(zpp_gridcap_mod, engine, args)
        _fase_kill_pos(before_pids)

    tamanho = _fase_validacao(path_xlsx)
    duracao_s = int((datetime.now(tz=pytz.UTC) - iniciado_em).total_seconds())
    logger.info("[exec] export ok | tamanho_bytes=%d duracao_s=%d", tamanho, duracao_s)

    return {
        "path_xlsx": path_xlsx,
        "tamanho_bytes": tamanho,
        "duracao_segundos": duracao_s,
    }
