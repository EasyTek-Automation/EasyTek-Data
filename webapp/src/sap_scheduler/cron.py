"""Cron do sap-scheduler webapp side (DS-03 refresh + DS-07).

Implementa o tick periodico que insere docs `pendente` em `sap_jobs` quando
a hora-alvo de cada agendamento ativo cai dentro da janela do tick atual.

Mudancas vs versao original (Bloco B):
- `_tick` rele config do Mongo (collection `sap_scheduler_config`) a cada
  invocacao — nao mais do boot via env var (DS-06 / SP-07 RF-07-14).
- `_calcular_agendado_para_hoje` arredonda pro minuto (DS-07 RF-08-05).
- `_tick_inserir_job_atomico` substitui o par `existe_doc_hoje + insert_job_pendente`
  por insert direto com try/except `DuplicateKeyError`, apoiado em unique index
  `idx_dedup_agendamento` (DS-07 RF-08-12..15). Resolve o bug A-06 (4 workers
  gunicorn x BackgroundScheduler -> 4x duplicacao).
- 3 niveis de fallback no `_tick` — sobrevive a connectivity error, doc deletado,
  schema corrompido (RF-01-14, RF-01-15).
"""
from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Optional

import pytz
from pymongo.errors import DuplicateKeyError, PyMongoError

from .config import SapSchedulerConfig
from .storage import read_config_singleton

logger = logging.getLogger(__name__)


# Fallback hardcoded usado quando o doc `sap_scheduler_config` esta corrompido
# (RF-01-15 / SP-07 RF-07-22). Mantem o webapp operando enquanto admin nao corrige.
_FALLBACK_AGENDAMENTOS: list[dict] = [
    {"tipo": "zppprd", "hora": "03:30", "ativo": True},
    {"tipo": "zpp_nt0001", "hora": "03:30", "ativo": True},
]


def _calcular_agendado_para_hoje(hora_hhmm: str, tz_name: str) -> datetime:
    """Calcula `agendado_para` em UTC pra hoje na timezone configurada.

    DS-07 RF-08-05: arredonda pro minuto (`.replace(second=0, microsecond=0)`)
    para garantir que N workers gunicorn com clock drift gerem a mesma chave
    `(tipo, agendado_para)` e o unique index dedupe.

    Ex: hora_hhmm='03:30', tz='America/Sao_Paulo' (UTC-3)
        -> hoje 03:30 BRT -> 06:30:00.000 UTC, naive
    """
    tz = pytz.timezone(tz_name)
    agora_local = datetime.now(tz=tz)
    hh, mm = hora_hhmm.split(":")
    alvo_naive = datetime.combine(agora_local.date(), time(int(hh), int(mm)))
    alvo_local = tz.localize(alvo_naive)
    alvo_utc = alvo_local.astimezone(pytz.UTC).replace(tzinfo=None)
    return alvo_utc.replace(second=0, microsecond=0)


def _tick_inserir_job_atomico(
    db,
    tipo: str,
    agendado_para_utc: datetime,
    collection_name: str = "sap_jobs",
) -> None:
    """Insere job pendente atomicamente (DS-07 RF-08-12..15).

    Race-safe: N workers gunicorn tickando simultaneamente -> unique index
    `idx_dedup_agendamento` dedupe. Vencedor da corrida insere; perdedores
    pegam `DuplicateKeyError` e logam INFO `dedup`.

    Outras `PyMongoError` sobem pro wrapper do `_tick` (loga ERROR + segue).
    """
    agora_utc = datetime.now(tz=pytz.UTC).replace(tzinfo=None)
    doc = {
        "tipo": tipo,
        "parametros": {},
        "status": "pendente",
        "agendado_para": agendado_para_utc,
        "criado_em": agora_utc,
        "iniciado_em": None,
        "concluido_em": None,
        "resultado": None,
        "erro": None,
    }
    try:
        result = db[collection_name].insert_one(doc)
        logger.info(
            "sap_scheduler: job inserido | tipo=%s _id=%s agendado_para=%s",
            tipo,
            result.inserted_id,
            agendado_para_utc.isoformat(),
        )
    except DuplicateKeyError:
        # Comportamento ESPERADO em race com N workers — nao e defeito (DC-07-04).
        logger.info(
            "sap_scheduler: dedup | tipo=%s agendado_para=%s "
            "(outro worker venceu a corrida)",
            tipo,
            agendado_para_utc.isoformat(),
        )


def _resolver_agendamentos_do_mongo() -> list[dict]:
    """Le agendamentos do `sap_scheduler_config` com fallbacks robustos.

    Retorna lista de dicts `{tipo, hora, ativo}`. Cai em fallback hardcoded
    se schema corrompido (RF-01-15).
    """
    try:
        doc = read_config_singleton()
    except PyMongoError as e:
        logger.error("sap_scheduler: erro lendo sap_scheduler_config: %s", e)
        return []  # tick faz no-op naquele ciclo
    except Exception as e:
        logger.exception("sap_scheduler: erro inesperado lendo config: %s", e)
        return []

    if doc is None:
        logger.warning(
            "sap_scheduler: sap_scheduler_config nao encontrado — tick faz no-op "
            "(proximo boot recria via bootstrap_config)"
        )
        return []

    agendamentos = doc.get("agendamentos")
    if not isinstance(agendamentos, list):
        logger.error(
            "sap_scheduler: schema corrompido (agendamentos com tipo %s); "
            "usando fallback hardcoded 03:30",
            type(agendamentos).__name__,
        )
        return _FALLBACK_AGENDAMENTOS

    return agendamentos


def _tick(config: SapSchedulerConfig, db) -> None:
    """Tick do APScheduler — implementa SP-01 RF-01-03..07 refresh.

    Funcao pura: recebe config + db, nao importa APScheduler.
    Testavel diretamente em unit test (mock db).

    Comportamento refresh (DS-03 + DS-07):
    1. Kill switch `habilitado=False` -> return imediato
    2. Le agendamentos do `sap_scheduler_config` no Mongo (DS-06)
    3. Pra cada item ativo: calcula `agendado_para` arredondado; checa janela;
       chama insert atomico (DS-07 — try/except DuplicateKeyError).
    4. Erros sobem pro wrapper que loga e segue (scheduler nao trava).
    """
    if not config.habilitado:
        return  # kill switch global (RF-01-06)

    agendamentos = _resolver_agendamentos_do_mongo()
    if not agendamentos:
        return  # connectivity error, doc deletado ou schema corrompido

    try:
        agora_utc = datetime.now(tz=pytz.UTC).replace(tzinfo=None)

        for item in agendamentos:
            if not item.get("ativo", True):
                continue  # tipo pausado pela UI

            try:
                tipo = item["tipo"]
                hora = item["hora"]
            except (KeyError, TypeError) as e:
                logger.error(
                    "sap_scheduler: item invalido em agendamentos: %s (%s)",
                    item,
                    e,
                )
                continue

            try:
                agendado_utc = _calcular_agendado_para_hoje(hora, config.timezone)
            except Exception as e:
                logger.error(
                    "sap_scheduler: erro calculando agendado_para "
                    "tipo=%s hora=%s: %s",
                    tipo,
                    hora,
                    e,
                )
                continue

            delta_s = abs((agora_utc - agendado_utc).total_seconds())
            if delta_s > config.janela_tick_segundos:
                continue  # fora da janela

            try:
                _tick_inserir_job_atomico(db, tipo, agendado_utc, config.collection)
            except PyMongoError as e:
                # DuplicateKeyError ja tratada dentro; outros PyMongoError vem aqui
                logger.exception(
                    "sap_scheduler: PyMongoError no insert | tipo=%s | %s",
                    tipo,
                    e,
                )
    except Exception:
        logger.exception("sap_scheduler: erro inesperado no tick (loop continua)")


def init_scheduler(cfg: SapSchedulerConfig, db) -> Optional[object]:
    """Cria + inicia o `BackgroundScheduler` do APScheduler.

    Retorna handle do scheduler (pra shutdown gracioso em teardown) ou
    `None` se APScheduler nao disponivel (defesa em profundidade).

    Chamado 1x no boot do `app.py` (DS-06 ordem) APOS:
    - migracao_dedup_sap_jobs(db)
    - ensure_indexes(db)
    - bootstrap_config(...)
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
