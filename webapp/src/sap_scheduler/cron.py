"""Cron do sap-scheduler webapp side (DS-03 + IM-B2).

Implementa o tick periódico que insere docs `pendente` em `sap_jobs` quando
a hora-alvo de cada `JobAgendado` cai dentro da janela do tick atual.

Estrutura:
- `_tick(config, db, logger)`       → função pura, testável sem APScheduler
- `_calcular_agendado_para_hoje()`  → helper de timezone (testável isolado)
- `init_scheduler(server, cfg, db)` → wrap APScheduler `BackgroundScheduler`

`init_scheduler` é o único ponto que importa APScheduler — facilita teste
unitário do `_tick` (mock do db).
"""
from __future__ import annotations

import logging
from datetime import datetime, time, timedelta
from typing import Optional

import pytz

from .config import JobAgendado, SapSchedulerConfig
from .mongo_helpers import existe_doc_hoje, insert_job_pendente

logger = logging.getLogger(__name__)


def _calcular_agendado_para_hoje(hora_hhmm: str, tz_name: str) -> datetime:
    """Calcula `agendado_para` em UTC pra hoje na timezone configurada.

    Ex: hora_hhmm='00:01', tz='America/Sao_Paulo' (UTC-3)
        → hoje 00:01 BRT → 03:01 UTC
    """
    tz = pytz.timezone(tz_name)
    agora_local = datetime.now(tz=tz)
    hh, mm = hora_hhmm.split(":")
    alvo_naive = datetime.combine(agora_local.date(), time(int(hh), int(mm)))
    alvo_local = tz.localize(alvo_naive)
    return alvo_local.astimezone(pytz.UTC)


def _janela_do_dia_utc(agora_local: datetime, tz: pytz.BaseTzInfo) -> tuple[datetime, datetime]:
    """Retorna (00:00 BRT, 00:00 BRT do dia seguinte) em UTC.

    Usado pelo `existe_doc_hoje` pra delimitar a busca por "doc já inserido hoje".
    """
    dia_inicio_local = tz.localize(datetime.combine(agora_local.date(), time(0, 0)))
    dia_fim_local = dia_inicio_local + timedelta(days=1)
    return dia_inicio_local.astimezone(pytz.UTC), dia_fim_local.astimezone(pytz.UTC)


def _tick(config: SapSchedulerConfig, db) -> None:
    """Tick do APScheduler — implementa SP-01 RF-01-02..07.

    Função pura: recebe config + db, não importa APScheduler.
    Testável diretamente em unit test (mock db).

    Comportamento (DS-03):
    - Kill switch `habilitado=False` → return imediato
    - Pra cada `JobAgendado`: calcula agendado_para_hoje; checa janela;
      checa idempotência (`existe_doc_hoje`); insere se faltante.
    - Erros (PyMongoError ou Exception) → log + return; não derruba scheduler.
    """
    if not config.habilitado:
        return  # kill switch

    try:
        agora_utc = datetime.now(tz=pytz.UTC)
        tz = pytz.timezone(config.timezone)
        agora_local = agora_utc.astimezone(tz)
        dia_inicio_utc, dia_fim_utc = _janela_do_dia_utc(agora_local, tz)

        for job in config.agendados:
            agendado_utc = _calcular_agendado_para_hoje(job.hora, config.timezone)
            delta_s = abs((agora_utc - agendado_utc).total_seconds())
            if delta_s > config.janela_tick_segundos:
                continue  # fora da janela

            if existe_doc_hoje(db, job.tipo, dia_inicio_utc, dia_fim_utc, config.collection):
                logger.info(
                    "sap_scheduler: job ja existe hoje, skip | tipo=%s",
                    job.tipo,
                )
                continue

            _id = insert_job_pendente(db, job.tipo, agendado_utc, config.collection)
            logger.info(
                "sap_scheduler: job inserido | tipo=%s _id=%s agendado_para=%s",
                job.tipo,
                _id,
                agendado_utc.isoformat(),
            )
    except Exception:
        logger.exception("sap_scheduler: erro no tick (loop continua)")


def init_scheduler(cfg: SapSchedulerConfig, db) -> Optional[object]:
    """Cria + inicia o `BackgroundScheduler` do APScheduler.

    Retorna handle do scheduler (pra shutdown gracioso em teardown) ou
    `None` se APScheduler não disponível (defesa em profundidade).

    Chamado 1× no boot do `app.py` (IM-B3) após `dash.Dash(...)`.
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError:
        logger.error(
            "sap_scheduler: APScheduler nao instalado — scheduler nao inicia. "
            "Adicione 'APScheduler>=3.10,<4.0' ao requirements.txt"
        )
        return None

    scheduler = BackgroundScheduler(timezone=cfg.timezone)
    scheduler.add_job(
        func=_tick,
        trigger=IntervalTrigger(seconds=cfg.janela_tick_segundos),
        args=[cfg, db],
        id="sap_scheduler_tick",
        name="sap-scheduler tick agendamento",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "sap_scheduler: BackgroundScheduler iniciado | intervalo=%ds tz=%s habilitado=%s",
        cfg.janela_tick_segundos,
        cfg.timezone,
        cfg.habilitado,
    )
    return scheduler
