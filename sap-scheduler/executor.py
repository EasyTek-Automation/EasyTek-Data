"""Executor — interface SP-03↔SP-04 (DS-04 + IM-E5).

`executar_job` é a função pública chamada pelo loop principal. Garante:
- nunca propaga exceção pra loop (SP-04 RF-04-02)
- nunca deixa job em `executando` (defesa em profundidade — RF-04-33)
- todo erro é classificado por fase (RF-04-19/20)
"""
from __future__ import annotations

import logging
import traceback
from typing import Any

from . import executor_sap
from . import mongo
from .config import DaemonConfig
from .executor_sap import ExcecaoClassificada

logger = logging.getLogger(__name__)


def _montar_erro(fase: str, original: BaseException) -> dict:
    """Subdocumento `erro` conforme DS-02. Trunca mensagem em 200 chars."""
    mensagem = str(original)
    if len(mensagem) > 200:
        mensagem = mensagem[:197] + "..."

    tb = traceback.extract_tb(original.__traceback__)
    traceback_resumido = ""
    if tb:
        last = tb[-1]
        traceback_resumido = f"{last.filename}:{last.lineno} em {last.name}"

    return {
        "mensagem": mensagem,
        "tipo_excecao": type(original).__name__,
        "fase": fase,
        "traceback_resumido": traceback_resumido,
    }


def executar_job(job: dict, db: Any, cfg: DaemonConfig) -> None:
    """Executa 1 job claimed. Nunca levanta exceção pro loop (exceto KeyboardInterrupt/SystemExit)."""
    _id = job["_id"]
    tipo = job["tipo"]
    logger.info("[exec] iniciando | _id=%s tipo=%s", _id, tipo)

    try:
        resultado = executor_sap.run(job, cfg)
    except (KeyboardInterrupt, SystemExit):
        # SP-04 RF-04-03: propaga shutdown gracioso
        raise
    except ExcecaoClassificada as e:
        logger.error(
            "[exec] job falhou | _id=%s tipo=%s fase=%s erro=%s",
            _id, tipo, e.fase, str(e.original)[:200],
            exc_info=e.original,
        )
        erro = _montar_erro(e.fase, e.original)
        _safe_update_falhou(db, _id, erro, cfg)
        return
    except Exception as exc:  # noqa: BLE001 — defesa em profundidade (RF-04-33)
        logger.exception("[exec] excecao nao-classificada | _id=%s", _id)
        erro = _montar_erro("desconhecido", exc)
        _safe_update_falhou(db, _id, erro, cfg)
        return

    # Sucesso — update Mongo
    try:
        if mongo.update_concluido(db, _id, resultado, cfg.collection):
            logger.info(
                "[done] job concluido | _id=%s tipo=%s duracao_s=%d tamanho_bytes=%d tentativas=%d",
                _id, tipo, resultado["duracao_segundos"], resultado["tamanho_bytes"],
                resultado.get("tentativas", 1),
            )
        else:
            logger.warning(
                "[exec] update_concluido nao bateu filtro (doc fora de 'executando') | _id=%s",
                _id,
            )
    except Exception:
        # Falha de update final — doc fica órfão; próximo boot detecta (SP-04 RF-04-34)
        logger.exception(
            "[exec] falha no update_concluido final | _id=%s (doc ficara como orfao)",
            _id,
        )


def _safe_update_falhou(db, _id, erro: dict, cfg: DaemonConfig) -> None:
    """Wrap update_falhou — falha de update final não derruba o loop."""
    try:
        mongo.update_falhou(db, _id, erro, cfg.collection)
    except Exception:
        logger.exception(
            "[exec] falha no update_falhou final | _id=%s (doc ficara como orfao)",
            _id,
        )
