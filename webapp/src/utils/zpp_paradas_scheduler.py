"""Agenda da coleta da ZPPPARADAS (KPIReport-v2 BR-14 / DS-18 revisado 2026-10-08).

Isolada do sap-scheduler, como a coleta de custo (`custos/scheduler.py`): o tipo
`zpp_paradas_pendentes` NÃO entra em `TIPOS_VALIDOS`, para não mudar o rodapé, os botões
"Rodar agora" da home nem a tela `/config/sap-scheduler` (um horário por tipo). Decisão do
usuário em 2026-10-08. O webapp só enfileira em `sap_jobs`; o daemon do cliente executa.

Horários por env `ZPP_PARADAS_PENDENTES_HORAS` (lista "HH:MM,HH:MM", default 06:30 e 10:00).
Multi-worker seguro: dedup pelo unique index `(tipo, agendado_para)` + guarda de job ativo.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime

import pytz

logger = logging.getLogger("zpp_paradas.scheduler")

TIPO = "zpp_paradas_pendentes"
_DEFAULT_HORAS = "06:30,10:00"
_HORA_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def parse_horas(raw: str) -> list[tuple[int, int]]:
    """'06:30,10:00' → [(6, 30), (10, 0)]; itens inválidos são ignorados; vazio → default."""
    out = []
    for parte in (raw or "").split(","):
        m = _HORA_RE.match(parte.strip())
        if m:
            out.append((int(m.group(1)), int(m.group(2))))
        elif parte.strip():
            logger.warning("zpp_paradas: hora inválida em ZPP_PARADAS_PENDENTES_HORAS: %r", parte)
    if not out and raw != _DEFAULT_HORAS:
        return parse_horas(_DEFAULT_HORAS)
    return out


def enqueue(db, tz_name: str = "America/Sao_Paulo", collection: str = "sap_jobs") -> str:
    """Insere job `pendente` para agora. Retorna `inserido` | `ja_em_andamento` | `dedup` | `erro`."""
    from pymongo.errors import DuplicateKeyError, PyMongoError
    try:
        from src.sap_scheduler.manual_trigger import _agendado_para_agora, _existe_job_ativo
    except ImportError:  # contexto de teste/script
        from sap_scheduler.manual_trigger import _agendado_para_agora, _existe_job_ativo  # type: ignore
    try:
        if _existe_job_ativo(db, TIPO, collection):
            return "ja_em_andamento"
        doc = {
            "tipo": TIPO,
            "parametros": {},
            "status": "pendente",
            "agendado_para": _agendado_para_agora(tz_name),
            "criado_em": datetime.now(tz=pytz.UTC).replace(tzinfo=None),
            "iniciado_em": None,
            "concluido_em": None,
            "resultado": None,
            "erro": None,
        }
        try:
            db[collection].insert_one(doc)
            return "inserido"
        except DuplicateKeyError:
            return "dedup"
    except PyMongoError as e:
        logger.warning("zpp_paradas: erro Mongo ao enfileirar: %s", e)
        return "erro"
    except Exception:
        logger.exception("zpp_paradas: erro inesperado ao enfileirar")
        return "erro"


def _tick(db, tz_name: str) -> None:
    """Disparo agendado — enfileira 1 coleta."""
    logger.info("zpp_paradas: coleta agendada | %s", enqueue(db, tz_name))


def init_scheduler(db, tz_name: str = "America/Sao_Paulo"):
    """Cria + inicia o BackgroundScheduler (1 CronTrigger por horário). `None` se não der."""
    if db is None:
        logger.warning("zpp_paradas: Mongo offline no boot — agenda não inicia")
        return None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.error("zpp_paradas: APScheduler ausente — agenda não inicia")
        return None
    horas = parse_horas(os.environ.get("ZPP_PARADAS_PENDENTES_HORAS", _DEFAULT_HORAS))
    scheduler = BackgroundScheduler(timezone=tz_name)
    for hh, mm in horas:
        scheduler.add_job(
            func=_tick, trigger=CronTrigger(hour=hh, minute=mm, timezone=tz_name),
            args=[db, tz_name], id=f"zpp_paradas_{hh:02d}{mm:02d}",
            name=f"zpp_paradas — coleta {hh:02d}:{mm:02d}", replace_existing=True,
        )
    scheduler.start()
    logger.info("zpp_paradas: agenda iniciada | horas=%s tz=%s",
                ",".join(f"{h:02d}:{m:02d}" for h, m in horas), tz_name)
    return scheduler
