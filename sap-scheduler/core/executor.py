# -*- coding: utf-8 -*-
"""Executor GENÉRICO — acha o script do tipo no REGISTRY, roda (com retry) e marca o resultado.

Não conhece nenhum tipo: só despacha. Nunca propaga exceção pro loop (SP-04).
Papel exato do teu modelo: "daemon vê o job → qual script ele pede → roda → devolve sucesso/fracasso".
"""
from __future__ import annotations

import logging
import time
import traceback
from typing import Any

from . import mongo
from . import kill_excel
from . import registry
from .config import DaemonConfig
from .contracts import Ctx, Result, FASES_TRANSIENTES

logger = logging.getLogger(__name__)
RETRY_SLEEP_SEGUNDOS = 5


def _montar_erro(fase: str, original) -> dict:
    msg = str(original)
    if len(msg) > 200:
        msg = msg[:197] + "..."
    tb = traceback.extract_tb(original.__traceback__) if original is not None else []
    resumo = f"{tb[-1].filename}:{tb[-1].lineno} em {tb[-1].name}" if tb else ""
    return {
        "mensagem": msg,
        "tipo_excecao": type(original).__name__ if original is not None else "?",
        "fase": fase,
        "traceback_resumido": resumo,
    }


def executar_job(job: dict, db: Any, cfg: DaemonConfig) -> None:
    """Processa 1 job claimed. Assinatura (job, db, cfg) — chamada pelo loop."""
    _id, tipo = job["_id"], job["tipo"]
    logger.info("[exec] iniciando | _id=%s tipo=%s", _id, tipo)

    run_fn = registry.REGISTRY.get(tipo)
    if run_fn is None:
        _falhou(db, _id, _montar_erro("desconhecido", ValueError(f"tipo {tipo!r} sem script no REGISTRY")), cfg)
        return

    ctx = Ctx(cfg, db)
    ini = time.monotonic()
    result = _rodar_com_retry(run_fn, job, ctx, cfg)
    dur = int(time.monotonic() - ini)

    if not result.ok:
        logger.error("[exec] job falhou | _id=%s tipo=%s fase=%s erro=%s",
                     _id, tipo, result.fase, str(result.erro)[:200])
        _falhou(db, _id, _montar_erro(result.fase, result.erro), cfg)
        return

    dados = dict(result.dados)
    dados.setdefault("duracao_segundos", dur)
    dados.setdefault("tamanho_bytes", 0)
    dados.setdefault("tentativas", 1)
    try:
        if mongo.update_concluido(db, _id, dados, cfg.collection):
            logger.info("[done] job concluido | _id=%s tipo=%s duracao_s=%d tamanho_bytes=%d tentativas=%d",
                        _id, tipo, dados["duracao_segundos"], dados["tamanho_bytes"], dados["tentativas"])
        else:
            logger.warning("[exec] update_concluido nao bateu filtro | _id=%s", _id)
    except Exception:
        logger.exception("[exec] falha no update_concluido final | _id=%s (vira orfao)", _id)


def _rodar_com_retry(run_fn, job, ctx, cfg) -> Result:
    """Chama run_fn(job, ctx). Retry in-run só em fase transiente. Idempotência é do script."""
    ultimo = None
    for tentativa in range(1, cfg.max_tentativas_job + 1):
        try:
            result = run_fn(job, ctx)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:  # noqa: BLE001 — script não deveria vazar, mas defendemos
            result = Result.falha("desconhecido", exc)
        if not isinstance(result, Result):
            result = Result.falha("desconhecido", TypeError(f"script devolveu {type(result).__name__}, esperado Result"))
        result.dados.setdefault("tentativas", tentativa)

        if result.ok:
            if tentativa > 1:
                logger.info("[exec] sucesso apos retry | tentativa=%d/%d", tentativa, cfg.max_tentativas_job)
            return result

        ultimo = result
        pode_retry = result.fase in FASES_TRANSIENTES and tentativa < cfg.max_tentativas_job
        if not pode_retry:
            return result
        logger.warning("[exec] falha transiente fase=%s tentativa=%d/%d — retry em %ds | erro=%s",
                       result.fase, tentativa, cfg.max_tentativas_job, RETRY_SLEEP_SEGUNDOS, str(result.erro)[:160])
        try:
            kill_excel.kill_preventivo()
        except Exception:
            logger.warning("[exec] kill_preventivo no retry falhou (continua)")
        time.sleep(RETRY_SLEEP_SEGUNDOS)

    return ultimo or Result.falha("desconhecido", RuntimeError("retry loop terminou sem resultado"))


def _falhou(db, _id, erro: dict, cfg) -> None:
    try:
        mongo.update_falhou(db, _id, erro, cfg.collection)
    except Exception:
        logger.exception("[exec] falha no update_falhou final | _id=%s (vira orfao)", _id)
