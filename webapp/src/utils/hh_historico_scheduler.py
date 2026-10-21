"""Agendamento semanal da captura Fase 2 do Histórico Semanal (SDD hh-historico, Bloco E).

Job **no webapp** (decisão do usuário 2026-07-24): a captura é só Mongo — lê `sap_backlog`
(estado atual das ordens, via `montar_ordens`) e grava a série histórica `hh_historico_semanal`
(SCD2 append-on-change) + o snapshot de trabalho fora do plano `hh_historico_fora`. Não toca o
daemon do cliente; sobe com o webapp.

Roda 1×/semana (segunda de manhã, configurável por `HIST_CAPTURA_DIA`/`HIST_CAPTURA_HORA`).
Idempotente por semana: rodar de novo na mesma semana não duplica (append-on-change). Multi-worker
(gunicorn) é seguro pela idempotência — no pior caso os workers recomputam a mesma foto.
"""
from __future__ import annotations

import logging
import os
import re

logger = logging.getLogger("hh_historico.scheduler")

_HORA_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
_DIAS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _parse_hora(raw: str) -> tuple[int, int]:
    m = _HORA_RE.match((raw or "").strip())
    return (int(m.group(1)), int(m.group(2))) if m else (5, 0)


def _tick_captura() -> None:
    """Dispara a captura semanal (backlog SCD2 + fora do plano). Chamado pelo CronTrigger."""
    try:
        from src.utils import hh_historico_data as hh
    except ImportError:
        from utils import hh_historico_data as hh  # type: ignore
    try:
        res = hh.capturar_semanal()
        logger.info("histórico: captura semanal | %s", res)
    except Exception:
        logger.exception("histórico: captura semanal falhou")


def init_historico_scheduler(db, tz_name: str = "America/Sao_Paulo"):
    """Cria + inicia o BackgroundScheduler semanal da captura Fase 2. None se APScheduler ausente
    ou `db` None. Chamado 1× no boot do `app.py`."""
    if db is None:
        logger.warning("histórico: Mongo offline no boot — captura semanal não inicia")
        return None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.error("histórico: APScheduler ausente — captura semanal não inicia")
        return None

    dia = _DIAS.get(os.environ.get("HIST_CAPTURA_DIA", "mon").strip().lower(), 0)
    hh_, mm = _parse_hora(os.environ.get("HIST_CAPTURA_HORA", "05:00"))
    dow = [k for k, v in _DIAS.items() if v == dia][0]
    scheduler = BackgroundScheduler(timezone=tz_name)
    scheduler.add_job(
        func=_tick_captura,
        trigger=CronTrigger(day_of_week=dow, hour=hh_, minute=mm, timezone=tz_name),
        id="hist_captura_semanal",
        name="histórico — captura semanal (backlog + fora do plano)",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("histórico: captura semanal agendada | %s %02d:%02d tz=%s", dow, hh_, mm, tz_name)
    return scheduler
