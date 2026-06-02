"""Lockfile do daemon — single-instance via `tasklist` (Windows) / `ps` (Linux fallback).

DS-04 + IM-D1. Sem admin necessário. Detecta processo morto via PID check.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _pid_vivo(pid: int) -> bool:
    """Checa se PID está vivo. Windows: `tasklist`. Linux: `ps -p`."""
    if sys.platform == "win32":
        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout
            return str(pid) in out
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False  # assume morto se tasklist falha — fail open
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def acquire(path: Path) -> bool:
    """Tenta adquirir lockfile com criação atômica.

    Retorna True se conseguiu (lockfile inexistente ou PID anterior morto).
    Retorna False se outra instância viva está rodando.

    Cria o arquivo com `O_CREAT|O_EXCL` (atômico — falha se já existe).
    Se já existe, lê PID e checa se está vivo. Se morto, remove e retenta.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    pid = os.getpid()

    # 2 tentativas: 1ª cria; se falha (já existe), checa PID + remove se morto + retenta
    for tentativa in range(2):
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            try:
                os.write(fd, f"{pid}\n".encode("utf-8"))
            finally:
                os.close(fd)
            logger.info("daemon: lockfile adquirido | pid=%d path=%s", pid, path)
            return True
        except FileExistsError:
            # lockfile existe — verifica se PID está vivo
            try:
                pid_str = path.read_text(encoding="utf-8").strip().splitlines()[0]
                pid_old = int(pid_str)
            except (ValueError, IndexError, FileNotFoundError):
                logger.warning("daemon: lockfile %s corrompido na tentativa %d", path, tentativa)
                pid_old = None

            if pid_old is not None and _pid_vivo(pid_old):
                logger.info("daemon: outra instancia ja rodando | pid=%d", pid_old)
                return False

            logger.info("daemon: lockfile com PID morto/corrompido; removendo + retry")
            try:
                path.unlink()
            except FileNotFoundError:
                pass  # já removido por outro processo — próxima iteração tenta criar

    logger.error("daemon: nao conseguiu adquirir lockfile apos 2 tentativas")
    return False


def release(path: Path) -> None:
    """Remove lockfile best-effort (atexit + shutdown graceful)."""
    try:
        path.unlink()
        logger.info("daemon: lockfile liberado")
    except FileNotFoundError:
        pass
    except OSError as e:
        logger.warning("daemon: falha ao remover lockfile %s: %s", path, e)
