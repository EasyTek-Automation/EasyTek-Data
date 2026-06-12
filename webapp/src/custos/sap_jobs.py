"""Enfileiramento dos jobs de coleta de custo no SAP (DS-10 — lado webapp).

Esta metade vive no webapp: apenas **enfileira** os jobs na coleche `sap_jobs`
(mesma fila do sap-scheduler) com os tipos proprios da feature. A **execucao** —
GUI scripting de ZBRCO019/KSB1, geracao do xlsx e carga no Mongo — roda no
**daemon do cliente** (sap-gate/daemon-payload), entregue via prompt claudinho
(`PROMPT-claudinho-custo-manutencao.md`). Localmente nada executa SAP (transporte
diferido — DS-01/DS-11).

Dois tipos (D1):
- `custo_orcado` — orcamento do mes (ZBRCO019, Report Painter, leitura por rotulo).
- `custo_exec`   — executado linha-a-linha (KSB1, grade ALV, export nativo).

Janela de coleta = **dois meses** (mes corrente + anterior, ate D-1) — BR-09 / gap G1.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pytz

try:
    from src.sap_scheduler.manual_trigger import _agendado_para_agora, _existe_job_ativo
except ImportError:  # contexto de teste/script
    from sap_scheduler.manual_trigger import _agendado_para_agora, _existe_job_ativo  # type: ignore

logger = logging.getLogger("custos.sap_jobs")

TIPO_ORCADO = "custo_orcado"
TIPO_EXEC = "custo_exec"
TIPOS_CUSTO = (TIPO_ORCADO, TIPO_EXEC)

_LABEL = {TIPO_ORCADO: "Orçado (ZBRCO019)", TIPO_EXEC: "Executado (KSB1)"}


def _ddmmaaaa(d: datetime) -> str:
    """Formato de data do SAP: dd.mm.aaaa."""
    return d.strftime("%d.%m.%Y")


def janela_dois_meses(agora_brt: datetime) -> tuple[datetime, datetime, list[str]]:
    """Janela de coleta de custo: 1º dia do mês ANTERIOR ao de D-1 até D-1 (BR-09 / G1).

    Reprocessa o mês corrente e o anterior a cada coleta (retroativos/recodificações).
    `replace(day=1)` resolve viradas de mês e de ano.

    Ex: hoje=15/06 → ontem=14/06 → janela 01/05..14/06; meses=['2026-05','2026-06'].
    Ex: hoje=05/01 → ontem=04/01 → janela 01/12(ano-1)..04/01; meses=['2025-12','2026-01'].
    """
    ontem = agora_brt - timedelta(days=1)
    primeiro_mes_atual = ontem.replace(day=1)
    fim_mes_anterior = primeiro_mes_atual - timedelta(days=1)
    inicio = fim_mes_anterior.replace(day=1)
    meses = [fim_mes_anterior.strftime("%Y-%m"), ontem.strftime("%Y-%m")]
    return inicio, ontem, meses


def enqueue_custo(db, tipo: str, tz_name: str = "America/Sao_Paulo",
                  collection: str = "sap_jobs") -> str:
    """Insere job de coleta de custo `pendente` para agora. Espelha `inserir_job_manual`.

    Guard: se já houver job `pendente`/`executando` do tipo, não insere
    (`ja_em_andamento`). Dedup race-safe pelo unique index `(tipo, agendado_para)`.
    Retorna: `inserido` | `ja_em_andamento` | `dedup` | `erro`.
    """
    from pymongo.errors import DuplicateKeyError, PyMongoError

    if tipo not in TIPOS_CUSTO:
        return "erro"
    try:
        if _existe_job_ativo(db, tipo, collection):
            return "ja_em_andamento"
        agora_brt = datetime.now(tz=pytz.timezone(tz_name))
        inicio, fim, meses = janela_dois_meses(agora_brt)
        doc = {
            "tipo": tipo,
            "parametros": {
                "disparo_manual": True,
                "janela": {
                    "inicio": _ddmmaaaa(inicio),
                    "fim": _ddmmaaaa(fim),
                    "meses": meses,
                },
            },
            "status": "pendente",
            "agendado_para": _agendado_para_agora(tz_name),
            "criado_em": datetime.now(tz=pytz.UTC).replace(tzinfo=None),
            "iniciado_em": None,
            "concluido_em": None,
            "resultado": None,
            "erro": None,
        }
        try:
            res = db[collection].insert_one(doc)
            logger.info("custos: coleta enfileirada | tipo=%s _id=%s meses=%s", tipo, res.inserted_id, meses)
            return "inserido"
        except DuplicateKeyError:
            logger.info("custos: coleta dedup | tipo=%s (mesmo minuto)", tipo)
            return "dedup"
    except PyMongoError as e:
        logger.warning("custos: erro Mongo ao enfileirar | tipo=%s: %s", tipo, e)
        return "erro"
    except Exception:
        logger.exception("custos: erro inesperado ao enfileirar | tipo=%s", tipo)
        return "erro"


def enqueue_ambos(db, tz_name: str = "America/Sao_Paulo") -> dict[str, str]:
    """Enfileira as duas coletas (orçado + executado). Retorna {tipo: status}."""
    return {t: enqueue_custo(db, t, tz_name) for t in TIPOS_CUSTO}
