"""kill_excel — preventivo + pós (DS-04 + IM-E2).

Windows: `tasklist /FI "IMAGENAME eq EXCEL.EXE" /FO CSV /NH` + `taskkill /PID <p> /F`.
Linux (CI/jail): stub que loga "no Excel on Linux".
"""
from __future__ import annotations

import logging
import subprocess
import sys

logger = logging.getLogger(__name__)


def pids_atuais() -> set[int]:
    """Retorna set de PIDs de processos EXCEL.EXE em execução. Linux → set vazio."""
    if sys.platform != "win32":
        return set()
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq EXCEL.EXE", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return set()

    pids: set[int] = set()
    for linha in out.splitlines():
        # Formato CSV: "EXCEL.EXE","<pid>","<sessao>",...
        partes = [p.strip('"') for p in linha.split(",")]
        if len(partes) >= 2 and partes[0].upper() == "EXCEL.EXE":
            try:
                pids.add(int(partes[1]))
            except ValueError:
                continue
    return pids


def _matar(pid: int) -> bool:
    """Mata PID via taskkill. Retorna True se mata, False se falha silenciosa."""
    if sys.platform != "win32":
        return False
    try:
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def kill_preventivo() -> int:
    """SP-04 RF-04-11/12: mata todo Excel pendurado antes de iniciar job.

    Retorna contagem de processos mortos. Linux → 0.
    """
    if sys.platform != "win32":
        logger.info("kill-excel preventivo: nao se aplica (nao-Windows)")
        return 0

    pids = pids_atuais()
    if not pids:
        logger.info("kill-excel preventivo: nenhum processo")
        return 0

    mortos = sum(1 for pid in pids if _matar(pid))
    logger.info("kill-excel preventivo: %d processos mortos", mortos)
    return mortos


def kill_pos(before_pids: set[int], wait: int = 20) -> int:
    """SP-04 RF-04-17: mata PIDs novos (surgiram durante exec).

    `wait`: tempo (s) pra esperar o `&XXL` abrir Excel antes de listar.
    Preserva instâncias do usuário (before_pids).
    """
    if sys.platform != "win32":
        logger.info("kill-excel pos: nao se aplica (nao-Windows)")
        return 0

    import time
    time.sleep(wait)

    atuais = pids_atuais()
    novos = atuais - before_pids
    if not novos:
        logger.info("kill-excel pos: nenhum processo novo")
        return 0

    mortos = sum(1 for pid in novos if _matar(pid))
    logger.info("kill-excel pos: %d processos novos mortos", mortos)
    return mortos
