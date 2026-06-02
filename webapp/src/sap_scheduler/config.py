"""Config do sap-scheduler webapp side (DS-03 + IM-B1).

Carrega 6 variáveis de ambiente com defaults sãos; valida tipos e formatos
fail-fast no boot. Erro de config = `RuntimeError` no boot do Flask
(evita rodar com config errada por dias).

Variáveis (DS-03 RV-01 F-01-01):
- SAP_JOBS_HABILITADO              bool (default true) — kill switch
- SAP_JOBS_AGENDADOS               JSON array  [{tipo, hora}]
- SAP_JOBS_JANELA_TICK_SEGUNDOS    int (default 60)
- SAP_JOBS_TIMEZONE                str (default "America/Sao_Paulo")
- SAP_JOBS_FRESCOR_HORAS_LIMITE    int (default 26)
- SAP_JOBS_COLLECTION              str (default "sap_jobs")
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import List

import pytz

DEFAULT_AGENDADOS_JSON = (
    '[{"tipo":"zppprd","hora":"00:01"},{"tipo":"zpp_nt0001","hora":"00:01"}]'
)

_HORA_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")


@dataclass(frozen=True)
class JobAgendado:
    """Configuração de um job a agendar (1 entrada de `SAP_JOBS_AGENDADOS`)."""

    tipo: str
    hora: str  # formato "HH:MM"


@dataclass(frozen=True)
class SapSchedulerConfig:
    """Config imutável do sap-scheduler. Congelada após `load_config()`."""

    habilitado: bool
    agendados: List[JobAgendado] = field(default_factory=list)
    janela_tick_segundos: int = 60
    timezone: str = "America/Sao_Paulo"
    frescor_horas_limite: int = 26
    collection: str = "sap_jobs"


def _parse_bool(raw: str) -> bool:
    """`true`/`1`/`yes` → True; `false`/`0`/`no` → False; outros → ValueError."""
    val = raw.strip().lower()
    if val in ("true", "1", "yes", "y"):
        return True
    if val in ("false", "0", "no", "n", ""):
        return False
    raise ValueError(f"valor booleano invalido: {raw!r}")


def _parse_agendados(raw: str) -> List[JobAgendado]:
    """Parser do JSON em `SAP_JOBS_AGENDADOS` com validações.

    Falha `RuntimeError` se:
    - JSON inválido
    - Não é lista
    - Item sem `tipo` ou `hora`
    - `hora` fora do formato `HH:MM`
    - Lista vazia
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"SAP_JOBS_AGENDADOS nao e JSON valido: {e}") from e

    if not isinstance(data, list):
        raise RuntimeError(f"SAP_JOBS_AGENDADOS deve ser lista; veio {type(data).__name__}")

    if not data:
        raise RuntimeError("SAP_JOBS_AGENDADOS esta vazio — nenhum job configurado")

    agendados: List[JobAgendado] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise RuntimeError(f"SAP_JOBS_AGENDADOS[{i}] deve ser objeto; veio {type(item).__name__}")
        tipo = item.get("tipo")
        hora = item.get("hora")
        if not tipo or not isinstance(tipo, str):
            raise RuntimeError(f"SAP_JOBS_AGENDADOS[{i}].tipo ausente ou nao-string")
        if not hora or not isinstance(hora, str) or not _HORA_RE.match(hora):
            raise RuntimeError(
                f"SAP_JOBS_AGENDADOS[{i}].hora invalida: {hora!r} (esperado 'HH:MM')"
            )
        agendados.append(JobAgendado(tipo=tipo, hora=hora))

    return agendados


def load_config() -> SapSchedulerConfig:
    """Carrega config do ambiente. Chamado 1× no boot do `app.py`.

    Levanta `RuntimeError` em qualquer validação falha — Flask não sobe
    com config errada (fail-fast desejável).
    """
    habilitado = _parse_bool(os.getenv("SAP_JOBS_HABILITADO", "true"))
    agendados = _parse_agendados(os.getenv("SAP_JOBS_AGENDADOS", DEFAULT_AGENDADOS_JSON))

    try:
        janela = int(os.getenv("SAP_JOBS_JANELA_TICK_SEGUNDOS", "60"))
    except ValueError as e:
        raise RuntimeError(f"SAP_JOBS_JANELA_TICK_SEGUNDOS nao e inteiro: {e}") from e
    if janela < 5:
        raise RuntimeError(f"SAP_JOBS_JANELA_TICK_SEGUNDOS deve ser >= 5; veio {janela}")

    timezone = os.getenv("SAP_JOBS_TIMEZONE", "America/Sao_Paulo")
    try:
        pytz.timezone(timezone)
    except pytz.UnknownTimeZoneError as e:
        raise RuntimeError(f"SAP_JOBS_TIMEZONE desconhecido: {timezone!r}") from e

    try:
        frescor = int(os.getenv("SAP_JOBS_FRESCOR_HORAS_LIMITE", "26"))
    except ValueError as e:
        raise RuntimeError(f"SAP_JOBS_FRESCOR_HORAS_LIMITE nao e inteiro: {e}") from e
    if frescor < 1:
        raise RuntimeError(f"SAP_JOBS_FRESCOR_HORAS_LIMITE deve ser >= 1; veio {frescor}")

    collection = os.getenv("SAP_JOBS_COLLECTION", "sap_jobs")
    if not collection.strip():
        raise RuntimeError("SAP_JOBS_COLLECTION nao pode ser vazio")

    return SapSchedulerConfig(
        habilitado=habilitado,
        agendados=agendados,
        janela_tick_segundos=janela,
        timezone=timezone,
        frescor_horas_limite=frescor,
        collection=collection.strip(),
    )
