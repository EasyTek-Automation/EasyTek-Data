"""Config do sap-scheduler webapp side (DS-03 refresh / DS-06).

Carrega 6 variaveis de ambiente com defaults sas; valida tipos e formatos
fail-fast no boot. Erro de config = RuntimeError no boot do Flask
(evita rodar com config errada por dias).

Mudanca vs versao original (Bloco B):
- Campo `agendados` removido como source of truth. SAP_JOBS_AGENDADOS env var
  agora e lida como **seed-only** (RF-07-18..21) — vira `agendados_legacy:
  Optional[list[dict]]`. Fonte da verdade dos agendamentos vive em Mongo
  (`sap_scheduler_config` singleton — DS-06).
- Novo campo `collection_sap_scheduler_config` — nome da nova collection.

Variaveis:
- SAP_JOBS_HABILITADO                  bool   (default True) — kill switch
- SAP_JOBS_AGENDADOS                   JSON   (opcional)     — seed-only se Mongo vazio
- SAP_JOBS_JANELA_TICK_SEGUNDOS        int    (default 60)
- SAP_JOBS_TIMEZONE                    str    (default "America/Sao_Paulo")
- SAP_JOBS_FRESCOR_HORAS_LIMITE        int    (default 26)
- SAP_JOBS_COLLECTION                  str    (default "sap_jobs")
- SAP_SCHEDULER_CONFIG_COLLECTION      str    (default "sap_scheduler_config") — NOVO
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

import pytz

logger = logging.getLogger(__name__)

_HORA_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")


@dataclass(frozen=True)
class SapSchedulerConfig:
    """Config imutavel do sap-scheduler. Congelada apos `load_config()`."""

    habilitado: bool
    agendados: List[dict] = field(default_factory=list)  # legado: pode estar vazio
    janela_tick_segundos: int = 60
    timezone: str = "America/Sao_Paulo"
    frescor_horas_limite: int = 26
    collection: str = "sap_jobs"
    collection_sap_scheduler_config: str = "sap_scheduler_config"
    agendados_legacy: Optional[List[dict]] = None  # NOVO (DS-06 / SP-07 RF-07-18..21)


def _parse_bool(raw: str) -> bool:
    """`true`/`1`/`yes` -> True; `false`/`0`/`no` -> False; outros -> ValueError."""
    val = raw.strip().lower()
    if val in ("true", "1", "yes", "y"):
        return True
    if val in ("false", "0", "no", "n", ""):
        return False
    raise ValueError(f"valor booleano invalido: {raw!r}")


def _parse_agendados_legacy(raw: str) -> Optional[List[dict]]:
    """Parser do JSON em `SAP_JOBS_AGENDADOS` como seed-only (RF-07-18..21).

    Comportamento permissivo: se env var malformada, loga WARNING e retorna
    None (nao trava o webapp). Bootstrap usa default hardcoded `03:30`.

    Adiciona `ativo: True` por default em itens sem o campo (compatibilidade
    com formato antigo `[{tipo, hora}]` que nao tinha `ativo`).
    """
    if not raw or not raw.strip():
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(
            "SAP_JOBS_AGENDADOS env var nao e JSON valido, ignorada: %s",
            e,
        )
        return None

    if not isinstance(data, list):
        logger.warning(
            "SAP_JOBS_AGENDADOS env var deve ser lista; veio %s, ignorada",
            type(data).__name__,
        )
        return None

    if not data:
        return None

    agendados: List[dict] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "SAP_JOBS_AGENDADOS[%d] deve ser objeto; veio %s — ignorando env var inteira",
                i,
                type(item).__name__,
            )
            return None
        tipo = item.get("tipo")
        hora = item.get("hora")
        if not tipo or not isinstance(tipo, str):
            logger.warning(
                "SAP_JOBS_AGENDADOS[%d].tipo ausente/invalido — ignorando env var",
                i,
            )
            return None
        if not hora or not isinstance(hora, str) or not _HORA_RE.match(hora):
            logger.warning(
                "SAP_JOBS_AGENDADOS[%d].hora invalida (%r) — ignorando env var",
                i,
                hora,
            )
            return None
        agendados.append({
            "tipo": tipo,
            "hora": hora,
            "ativo": bool(item.get("ativo", True)),  # default ativo=True (compat)
        })

    return agendados


def load_config() -> SapSchedulerConfig:
    """Carrega config do ambiente. Chamado 1x no boot do `app.py`.

    Levanta `RuntimeError` em validacoes de tipos numericos invalidos ou
    timezone desconhecido (fail-fast). SAP_JOBS_AGENDADOS malformada
    nao trava — apenas vira None e bootstrap usa default `03:30`.
    """
    habilitado = _parse_bool(os.getenv("SAP_JOBS_HABILITADO", "true"))
    agendados_legacy = _parse_agendados_legacy(os.getenv("SAP_JOBS_AGENDADOS", ""))

    try:
        janela = int(os.getenv("SAP_JOBS_JANELA_TICK_SEGUNDOS", "60"))
    except ValueError as e:
        raise RuntimeError(
            f"SAP_JOBS_JANELA_TICK_SEGUNDOS nao e inteiro: {e}"
        ) from e
    if janela < 5:
        raise RuntimeError(
            f"SAP_JOBS_JANELA_TICK_SEGUNDOS deve ser >= 5; veio {janela}"
        )

    timezone = os.getenv("SAP_JOBS_TIMEZONE", "America/Sao_Paulo")
    try:
        pytz.timezone(timezone)
    except pytz.UnknownTimeZoneError as e:
        raise RuntimeError(f"SAP_JOBS_TIMEZONE desconhecido: {timezone!r}") from e

    try:
        frescor = int(os.getenv("SAP_JOBS_FRESCOR_HORAS_LIMITE", "26"))
    except ValueError as e:
        raise RuntimeError(
            f"SAP_JOBS_FRESCOR_HORAS_LIMITE nao e inteiro: {e}"
        ) from e
    if frescor < 1:
        raise RuntimeError(
            f"SAP_JOBS_FRESCOR_HORAS_LIMITE deve ser >= 1; veio {frescor}"
        )

    collection = os.getenv("SAP_JOBS_COLLECTION", "sap_jobs").strip()
    if not collection:
        raise RuntimeError("SAP_JOBS_COLLECTION nao pode ser vazio")

    collection_config = os.getenv(
        "SAP_SCHEDULER_CONFIG_COLLECTION", "sap_scheduler_config"
    ).strip()
    if not collection_config:
        raise RuntimeError("SAP_SCHEDULER_CONFIG_COLLECTION nao pode ser vazio")

    return SapSchedulerConfig(
        habilitado=habilitado,
        agendados=[],  # ja nao e source of truth — fica vazio
        agendados_legacy=agendados_legacy,
        janela_tick_segundos=janela,
        timezone=timezone,
        frescor_horas_limite=frescor,
        collection=collection,
        collection_sap_scheduler_config=collection_config,
    )
