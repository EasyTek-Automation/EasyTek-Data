"""Callback Dash do rodapé da home — exibe timestamp da última coleta SAP.

DS-03 + IM-C2. 4 estados de render conforme SP-01 RF-01-10..13:
- ok:        "ZPPPRD atualizado em DD/MM HH:MM"
- avisar:    "⚠ ZPPPRD: última coleta em DD/MM HH:MM (há X dias/horas)"
- sem doc:   "ZPPPRD: sem coleta registrada"
- fallback:  "⚠ não foi possível consultar status da coleta"

Callback dispara em `Input("url", "pathname")` — atualiza só quando user
navega pra home (não polling 24/7).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import pytz
from dash import Input, Output, html, no_update
from dash.exceptions import PreventUpdate
from pymongo.errors import PyMongoError

from .config import SapSchedulerConfig
from .mongo_helpers import find_ultimo_concluido_por_tipo, get_db
from .rodape_component import RODAPE_CONTENT_ID
from .validators import TIPOS_VALIDOS

logger = logging.getLogger(__name__)

# Rota da home — pathname canônico. Aliases (`/dashboard`, etc.) resolvem
# antes do callback via `index.py` ROUTE_ALIASES.
HOME_PATHNAME = "/dashboards/home"
HOME_ALIASES = {"/", "/home", "/dashboards/home"}


def _formatar_idade(delta_segundos: float) -> str:
    """Converte segundos em string legível: '3h', '2 dias', '1 dia'."""
    horas = delta_segundos / 3600
    if horas < 48:
        return f"{int(horas)}h"
    dias = int(horas / 24)
    return f"{dias} dia" if dias == 1 else f"{dias} dias"


def _render_por_tipo(
    tipo: str,
    doc: Optional[dict],
    agora_utc: datetime,
    frescor_limite_h: int,
    tz_name: str,
):
    """Renderiza span para 1 tipo. 3 dos 4 estados (fallback global vive no callback)."""
    tz = pytz.timezone(tz_name)
    if doc is None:
        return html.Span(
            f"{tipo.upper()}: sem coleta registrada",
            className="text-muted small mx-2",
        )

    concluido_em = doc["concluido_em"]
    # pymongo retorna datetime tz-naive em UTC; localizar
    if concluido_em.tzinfo is None:
        concluido_em = pytz.UTC.localize(concluido_em)
    idade_s = (agora_utc - concluido_em).total_seconds()
    label_dt = concluido_em.astimezone(tz).strftime("%d/%m %H:%M")

    if idade_s <= frescor_limite_h * 3600:
        return html.Span(
            f"{tipo.upper()} atualizado em {label_dt}",
            className="text-muted small mx-2",
        )

    idade_str = _formatar_idade(idade_s)
    return html.Span(
        f"⚠ {tipo.upper()}: última coleta em {label_dt} (há {idade_str})",
        className="text-warning small mx-2",
    )


_CALLBACK_REGISTERED_MARKER = "_sap_scheduler_rodape_callback_registered"


def register_callback(app, cfg: SapSchedulerConfig) -> None:
    """Registra callback Dash do rodapé. Chamado 1× no boot do `app.py`.

    Idempotente via marker flag — em cenário de hot-reload ou re-import,
    skip silencioso pra evitar `DuplicateCallback` do Dash 3.x.
    """
    if getattr(app, _CALLBACK_REGISTERED_MARKER, False):
        logger.info("sap_scheduler: callback do rodape ja registrado, skip")
        return
    setattr(app, _CALLBACK_REGISTERED_MARKER, True)

    @app.callback(
        Output(RODAPE_CONTENT_ID, "children"),
        Input("url", "pathname"),
    )
    def atualizar_rodape(pathname):
        if pathname not in HOME_ALIASES:
            raise PreventUpdate

        try:
            db = get_db()
            if db is None:
                return html.Span(
                    "⚠ não foi possível consultar status da coleta",
                    className="text-warning small",
                )

            agora_utc = datetime.now(tz=pytz.UTC)
            spans = []
            # DS-03 refresh: itera whitelist tecnica (TIPOS_VALIDOS) em vez de
            # cfg.agendados (que era source-of-truth antiga). Rodape mostra
            # 'ultima coleta' por tipo independente de estar `ativo` na config —
            # comportamento preservado do Bloco C.
            for tipo in sorted(TIPOS_VALIDOS):
                doc = find_ultimo_concluido_por_tipo(db, tipo, cfg.collection)
                spans.append(
                    _render_por_tipo(
                        tipo, doc, agora_utc, cfg.frescor_horas_limite, cfg.timezone
                    )
                )
            return html.Span(spans)
        except PyMongoError as e:
            logger.warning("sap_scheduler timestamp callback PyMongoError: %s", e)
            return html.Span(
                "⚠ não foi possível consultar status da coleta",
                className="text-warning small",
            )
        except Exception:
            logger.exception("sap_scheduler timestamp callback erro inesperado")
            return html.Span(
                "⚠ não foi possível consultar status da coleta",
                className="text-warning small",
            )

    logger.info("sap_scheduler: callback do rodape registrado")
