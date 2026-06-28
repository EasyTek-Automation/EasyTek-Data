"""Entrypoint do daemon sap-scheduler (DS-04 + IM-D1).

Roda como `python daemon.py` no PC do PCM (Windows nativo, 32-bit) ou no jail
(Linux, modo MOCK_SAP pra testes).

Sequência de boot:
1. Carrega config (.env do daemon)
2. Setup logger (TimedRotatingFileHandler)
3. Adquire lockfile (single-instance)
4. Conecta Mongo + ping
5. Garante índices (defesa em profundidade c/ webapp)
6. Detecta órfãos (log WARN; sem cleanup)
7. Entra em loop principal
"""
from __future__ import annotations

import atexit
import logging
import os
import signal
import sys
from pathlib import Path

# Permite executar como `python daemon.py` (sem -m) — adiciona parent ao sys.path
_THIS = Path(__file__).resolve()
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(_THIS.parent.parent))
    __package__ = _THIS.parent.name

# stdout robusto (os scripts ALV usam print() com unicode; evita crash em console cp1252)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from .core import config as _config_mod
from .core import logger as _logger_mod
from .core import lockfile as _lock
from .core import mongo as _mongo_mod
from .core import orfaos as _orfaos
from .core.loop_principal import loop_principal, request_shutdown

VERSAO = "0.1.0-IM-D1"

log = logging.getLogger("daemon")


def _install_signal_handlers() -> None:
    """Handlers de SIGTERM/SIGINT — sinaliza loop pra sair na próxima iteração."""
    def handler(signum, frame):
        log.info("daemon: sinal recebido (signum=%d); request shutdown", signum)
        request_shutdown()

    signal.signal(signal.SIGINT, handler)
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, handler)


def main() -> int:
    """Boot completo + entra em loop. Retorna exit code."""
    try:
        cfg = _config_mod.load()
    except RuntimeError as e:
        print(f"[FATAL] config invalida: {e}", file=sys.stderr)
        return 1

    _logger_mod.setup(cfg)
    log.info("=" * 60)
    log.info("daemon: boot iniciado | pid=%s versao=%s mock_sap=%s", os.getpid(), VERSAO, cfg.mock_sap)
    log.info("=" * 60)

    if not _lock.acquire(cfg.lockfile_path):
        log.info("daemon: saindo limpo (outra instancia rodando)")
        return 0
    atexit.register(_lock.release, cfg.lockfile_path)

    _install_signal_handlers()

    try:
        db = _mongo_mod.connect(cfg.mongo_uri, cfg.db_name, timeout_ms=30000)
    except Exception as e:
        log.error("daemon: falha de conexao Mongo no boot: %s", e)
        return 1

    try:
        _mongo_mod.ensure_indexes(db, cfg.collection)
    except Exception as e:
        log.error("daemon: falha em ensure_indexes: %s", e)
        return 1

    try:
        _orfaos.detectar_e_logar(db, cfg.collection, idade_minima_horas=1)
    except Exception as e:
        log.warning("daemon: falha em detectar_orfaos (continua): %s", e)

    # IM-E5 conectado: executor.executar_job substitui o stub do bloco D.
    from .core.executor import executar_job
    try:
        loop_principal(db, cfg, dispatcher=executar_job)
    except KeyboardInterrupt:
        log.info("daemon: KeyboardInterrupt no main")
    finally:
        _mongo_mod.close(db.client)
        log.info("daemon: saiu limpo")

    return 0


if __name__ == "__main__":
    sys.exit(main())
