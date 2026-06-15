# -*- coding: utf-8 -*-
"""Contratos compartilhados entre o motor (core) e os scripts (trabalhos).

`Result` = o que todo script devolve (sucesso+dados | falha+fase+erro).
`Ctx`    = o que todo script recebe (config + sessão SAP lazy + Mongo db).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# fases canônicas (espelha o enum do schema Mongo DS-02)
FASE_ENUM = (
    "conexao_sap", "navegacao", "export_alv", "salvamento",
    "validacao_arquivo", "kill_excel", "mongo_update", "desconhecido",
)
# fases transientes (glitch momentâneo do SAP GUI) → elegíveis a retry in-run
FASES_TRANSIENTES = frozenset({"conexao_sap", "navegacao", "export_alv"})


@dataclass
class Result:
    """Resultado da execução de um script."""
    ok: bool
    dados: dict = field(default_factory=dict)
    fase: str = "desconhecido"
    erro: Optional[BaseException] = None

    @staticmethod
    def sucesso(**dados) -> "Result":
        return Result(ok=True, dados=dados)

    @staticmethod
    def falha(fase: str, erro: BaseException) -> "Result":
        assert fase in FASE_ENUM, f"fase invalida: {fase!r}"
        return Result(ok=False, fase=fase, erro=erro)


class Ctx:
    """Contexto passado a cada script. Sessão SAP conecta sob demanda (lazy)."""

    def __init__(self, cfg, db):
        self.cfg = cfg
        self.db = db
        self._sap = None

    def sap(self):
        if self._sap is None:
            from . import sap as _sap_mod  # noqa: PLC0415
            self._sap = _sap_mod.conectar_sessao()
        return self._sap
