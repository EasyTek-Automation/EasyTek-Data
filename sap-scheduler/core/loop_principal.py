"""Loop principal do daemon (DS-04 + IM-D3).

Polling 30s sobre `sap_jobs.find_one_and_update` (claim atômico).
Captura PyMongoError transitórias; KeyboardInterrupt/SystemExit propaga.
Heartbeat 1h em ocioso.

Executor não conectado nesta IM (Bloco E). `_dispatch_job` é stub que apenas
loga "claim detectado" — IM-E5 substitui pelo `executor.executar_job`.
"""
from __future__ import annotations

import logging
import threading
import time

from pymongo.errors import PyMongoError

from . import mongo, registry
from .config import DaemonConfig

logger = logging.getLogger(__name__)

SHUTDOWN = threading.Event()


def _dispatch_job(job: dict, db, cfg: DaemonConfig) -> None:
    """Stub do dispatch — substituído por `executor.executar_job` em IM-E5.

    No bloco D, apenas loga + marca como falhou (sem executor).
    """
    logger.info("[claim] job claimed | _id=%s tipo=%s", job["_id"], job["tipo"])
    logger.warning(
        "[exec] executor nao conectado (IM-D3 stub) — marcando como falhou pra nao deixar orfao"
    )
    mongo.update_falhou(
        db,
        job["_id"],
        {
            "mensagem": "executor stub (IM-D3) — bloco E ainda nao integrado",
            "tipo_excecao": "NotImplementedError",
            "fase": "desconhecido",
        },
        collection_name=cfg.collection,
    )


def loop_principal(db, cfg: DaemonConfig, dispatcher=None) -> None:
    """Loop infinito de claim + dispatch.

    `dispatcher`: função `(job, db, cfg)` que processa o job. Default `_dispatch_job`
    (stub). IM-E5 passa `executor.executar_job`.
    """
    if dispatcher is None:
        dispatcher = _dispatch_job

    SHUTDOWN.clear()
    ultimo_heartbeat = time.monotonic()

    # Tipos claimáveis = união do whitelist do .env com TODOS os trabalhos registrados
    # (REGISTRY). Assim um trabalho novo (ex.: `backlog`) é claimado sem editar o `.env`
    # do cliente — o deploy preserva o `.env`, então depender só dele deixaria o job
    # eternamente `pendente`. SDD Backlog (IM-14b).
    tipos_efetivos = sorted(set(cfg.tipos_suportados) | set(registry.REGISTRY.keys()))

    logger.info(
        "daemon: loop principal iniciado | polling=%ds heartbeat=%ds tipos=%s",
        cfg.polling_segundos,
        cfg.heartbeat_segundos,
        tipos_efetivos,
    )

    while not SHUTDOWN.is_set():
        try:
            job = mongo.claim_atomico(db, tipos_efetivos, cfg.collection)
            if job is None:
                if time.monotonic() - ultimo_heartbeat >= cfg.heartbeat_segundos:
                    logger.debug("[tick] heartbeat: alive, 0 jobs pendentes")
                    ultimo_heartbeat = time.monotonic()
            else:
                dispatcher(job, db, cfg)
                ultimo_heartbeat = time.monotonic()
        except PyMongoError as e:
            logger.warning("[loop] PyMongoError transitorio: %s", e)
        except (KeyboardInterrupt, SystemExit):
            logger.info("[loop] sinal de shutdown recebido; saindo")
            break
        except Exception:
            logger.exception("[loop] excecao nao-prevista (loop continua)")

        # Sleep granular pra permitir SHUTDOWN.set() acelerar saída
        for _ in range(cfg.polling_segundos):
            if SHUTDOWN.is_set():
                break
            time.sleep(1)

    logger.info("daemon: loop principal encerrado")


def request_shutdown() -> None:
    """Sinaliza shutdown gracioso. Chamado por handler SIGTERM / Ctrl-C."""
    SHUTDOWN.set()
