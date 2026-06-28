"""Agendamento diário da coleta de custo (DS-10 / SP-02) — isolado do sap-scheduler.

Por que próprio e não o sap-scheduler compartilhado: os tipos `custo_*` NÃO estão em
`TIPOS_VALIDOS` (de propósito — não poluir o rodapé/UI do sap-scheduler, preservação
SP-04). Então o custo tem seu próprio `BackgroundScheduler` com um `CronTrigger` diário
que enfileira `custo_orcado` + `custo_exec` na mesma fila `sap_jobs`. O daemon do cliente
(Bloco D) processa esses tipos como qualquer outro.

Multi-worker (gunicorn) é seguro: o `CronTrigger` dispara no mesmo minuto em todos os
workers, e o `enqueue_custo` deduplica via o unique index `(tipo, agendado_para)` +
guarda de job ativo. Hora configurável por env `CUSTOS_COLETA_HORA` (HH:MM, default 04:00).
"""
from __future__ import annotations

import logging
import os
import re

logger = logging.getLogger("custos.scheduler")

_HORA_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
_DEFAULT_HORA = "04:00"


def _parse_hora(raw: str) -> tuple[int, int]:
    """Converte 'HH:MM' em (hora, minuto); cai no default 04:00 se inválida."""
    m = _HORA_RE.match((raw or "").strip())
    if not m:
        logger.warning("custos: CUSTOS_COLETA_HORA inválida (%r) — usando %s", raw, _DEFAULT_HORA)
        return 4, 0
    return int(m.group(1)), int(m.group(2))


def _tick_coleta(db, tz_name: str) -> None:
    """Enfileira as 2 coletas de custo. Chamado pelo CronTrigger 1×/dia.

    Dedup garantido por `enqueue_custo` (unique index + guarda de job ativo), então
    N workers disparando no mesmo minuto inserem só 1 de cada tipo.
    """
    try:
        from src.custos.sap_jobs import enqueue_ambos
    except ImportError:
        from custos.sap_jobs import enqueue_ambos  # type: ignore
    res = enqueue_ambos(db, tz_name)
    logger.info("custos: coleta diária agendada disparada | %s", res)


def init_custo_scheduler(db, tz_name: str = "America/Sao_Paulo"):
    """Cria + inicia o BackgroundScheduler diário da coleta de custo.

    Retorna o handle do scheduler, ou `None` se APScheduler ausente ou `db` None.
    Chamado 1× no boot do `app.py` (após ensure_indexes do custo).
    """
    if db is None:
        logger.warning("custos: Mongo offline no boot — agendamento de coleta não inicia")
        return None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.error("custos: APScheduler ausente — agendamento de coleta não inicia")
        return None

    hh, mm = _parse_hora(os.environ.get("CUSTOS_COLETA_HORA", _DEFAULT_HORA))
    scheduler = BackgroundScheduler(timezone=tz_name)
    scheduler.add_job(
        func=_tick_coleta,
        trigger=CronTrigger(hour=hh, minute=mm, timezone=tz_name),
        args=[db, tz_name],
        id="custo_coleta_diaria",
        name="custo — coleta diária (orçado + executado)",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("custos: agendamento diário de coleta iniciado | hora=%02d:%02d tz=%s", hh, mm, tz_name)
    return scheduler
