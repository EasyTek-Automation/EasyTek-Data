"""Validacao fail-fast de agendamentos do sap-scheduler.

Chamada client-side (UI da SP-09) E server-side (storage.py via callback).
Defesa em profundidade: backend nunca confia so no client.

Fonte: DS-06 (SDD sap-scheduler) - SP-07 RF-07-08..13.
"""
from __future__ import annotations

import re
from typing import Any

TIPOS_VALIDOS = frozenset({"zppprd", "zpp_nt0001", "backlog"})
HORA_REGEX = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def validar_item(item: Any) -> None:
    """Valida 1 item de agendamento; levanta ValueError com mensagem especifica."""
    if not isinstance(item, dict):
        raise ValueError(
            f"item de agendamento deve ser dict, recebeu {type(item).__name__}"
        )

    tipo = item.get("tipo")
    hora = item.get("hora")
    ativo = item.get("ativo")

    if tipo not in TIPOS_VALIDOS:
        raise ValueError(
            f"tipo invalido: {tipo!r} (esperado: {sorted(TIPOS_VALIDOS)})"
        )
    if not isinstance(hora, str) or not HORA_REGEX.match(hora.strip()):
        raise ValueError(
            f"hora invalida: {hora!r} (esperado HH:MM, 00:00-23:59)"
        )
    if not isinstance(ativo, bool):
        raise ValueError(
            f"ativo invalido: {ativo!r} (esperado True/False, "
            f"nao {type(ativo).__name__})"
        )


def validar_agendamentos(novos: Any) -> None:
    """Valida a lista completa antes de gravar.

    Aplica `.strip()` em strings de hora pra defesa contra whitespace de input HTML.
    Rejeita lista com tipo duplicado.

    Muta `novos` em duas formas: (a) trim em `hora`; (b) so faz isso se hora for str.
    Caller passa dict descartavel que vai para o Mongo — mutar e proposital.
    """
    if not isinstance(novos, list):
        raise ValueError(
            f"agendamentos deve ser list, recebeu {type(novos).__name__}"
        )

    tipos_vistos: set[str] = set()
    for item in novos:
        if isinstance(item, dict) and isinstance(item.get("hora"), str):
            item["hora"] = item["hora"].strip()
        validar_item(item)
        if item["tipo"] in tipos_vistos:
            raise ValueError(f"tipo duplicado na lista: {item['tipo']!r}")
        tipos_vistos.add(item["tipo"])
