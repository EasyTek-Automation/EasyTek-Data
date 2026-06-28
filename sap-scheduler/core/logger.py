"""Setup do logger do daemon (DS-04 + IM-D1).

`TimedRotatingFileHandler` midnight + backupCount=30. Formato canônico:
`%(asctime)s %(levelname)-5s [%(name)s] %(message)s`. Console handler ativo
em DEBUG (debug local) ou se `DAEMON_CONSOLE_LOG=true`.
"""
from __future__ import annotations

import logging
import os
from logging.handlers import TimedRotatingFileHandler

from .config import DaemonConfig


def setup(cfg: DaemonConfig) -> None:
    """Configura logger root pra escrever em `daemon.log` com rotação midnight.

    Idempotente — múltiplas chamadas não duplicam handlers.
    """
    cfg.log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(getattr(logging, cfg.log_level))

    # Evitar duplicação se chamado 2×
    for h in list(root.handlers):
        if isinstance(h, TimedRotatingFileHandler) and getattr(h, "_sap_scheduler_marker", False):
            return

    fmt = logging.Formatter("%(asctime)s %(levelname)-5s [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S")

    file_handler = TimedRotatingFileHandler(
        filename=str(cfg.log_dir / "daemon.log"),
        when="midnight",
        backupCount=cfg.log_backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler._sap_scheduler_marker = True  # type: ignore[attr-defined]
    root.addHandler(file_handler)

    if cfg.log_level == "DEBUG" or os.getenv("DAEMON_CONSOLE_LOG", "").lower() in ("true", "1"):
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        root.addHandler(console)
