"""Bloco L — botão "Rodar agora" no rodapé da home (disparo manual de coleta SAP).

O operador (perfil manutencao/producao + admin, level 1+) chega, vê no rodapé que
a coleta está desatualizada e dispara um job avulso SEM mexer no horário diário
configurado em `sap_scheduler_config`. Insere 1 doc `pendente` com
`agendado_para = agora`; o daemon faz claim no próximo polling (~30s) e executa —
já com o retry in-run do Bloco K.

Mecânica idêntica ao tick do cron (insert direto + unique index race-safe), mas
com `agendado_para = agora` em vez do horário agendado. **Não toca**
`sap_scheduler_config` — o schedule de todos os dias permanece intacto.
"""
from __future__ import annotations

import logging
from datetime import datetime

import dash_bootstrap_components as dbc
import pytz
from dash import Input, Output, ctx, html
from dash.exceptions import PreventUpdate
from pymongo.errors import DuplicateKeyError, PyMongoError

from .config import SapSchedulerConfig
from .mongo_helpers import get_db
from .validators import TIPOS_VALIDOS

logger = logging.getLogger(__name__)

# Perfis que podem disparar coleta manual (decisão Rodolfo, 2026-06-04):
# manutencao + producao (operadores/PCMs) + admin. Level 1+.
PERFIS_AUTORIZADOS = frozenset({"manutencao", "producao", "admin"})
LEVEL_MINIMO = 1

TOAST_ID = "toast-rerun-sap"
_RERUN_BTN_PREFIX = "btn-rerun-"

# Rótulo amigável por tipo (operador não conhece os nomes técnicos do SAP).
_LABEL_TIPO = {"zppprd": "Produção", "zpp_nt0001": "Paradas"}

# Mensagem + cor do toast por status retornado por `inserir_job_manual`.
_MSG = {
    "inserido": ("✅ Coleta disparada — o daemon processa em instantes.", "success"),
    "ja_em_andamento": (
        "ℹ️ Já há uma coleta deste tipo na fila ou em execução. Aguarde concluir.",
        "warning",
    ),
    "dedup": ("ℹ️ Já existe um disparo neste minuto. Tente de novo em 1 min.", "warning"),
    "erro": ("⚠ Não foi possível disparar a coleta. Veja os logs do webapp.", "danger"),
}


def _btn_id(tipo: str) -> str:
    """ID do botão de disparo manual de um tipo (ex: 'btn-rerun-zppprd')."""
    return f"{_RERUN_BTN_PREFIX}{tipo}"


def pode_disparar_manual(user) -> bool:
    """True se o usuário logado pode disparar coleta manual (perfil + level)."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    perfil = getattr(user, "perfil", None)
    level = getattr(user, "level", 0)
    return perfil in PERFIS_AUTORIZADOS and level >= LEVEL_MINIMO


def build_rerun_controls(user):
    """Botões "Rodar agora" — isolados, abaixo do rodapé de status.

    Renderiza só para usuário autorizado (`pode_disparar_manual`); para os demais
    retorna `html.Div()` vazio (sem ids) — preserva o rodapé validado e não expõe
    a ação a quem não pode usá-la.
    """
    if not pode_disparar_manual(user):
        return html.Div()

    botoes = [
        dbc.Button(
            [html.I(className="bi bi-arrow-repeat me-1"), f"Rodar agora — {_LABEL_TIPO.get(tipo, tipo.upper())}"],
            id=_btn_id(tipo),
            color="secondary",
            outline=True,
            size="sm",
            className="mx-1",
        )
        for tipo in sorted(TIPOS_VALIDOS)
    ]

    return html.Div(
        [
            html.Div(botoes, className="text-center mt-2"),
            dbc.Toast(
                id=TOAST_ID,
                header="Coleta SAP",
                is_open=False,
                dismissable=True,
                duration=6000,
                icon="primary",
                style={
                    "position": "fixed",
                    "top": 70,
                    "right": 16,
                    "zIndex": 1999,
                    "minWidth": 320,
                },
            ),
        ]
    )


def _agendado_para_agora(tz_name: str) -> datetime:
    """`agora` na timezone, arredondado pro minuto, em UTC naive (convenção sap_jobs)."""
    tz = pytz.timezone(tz_name)
    agora_utc = datetime.now(tz=tz).astimezone(pytz.UTC).replace(tzinfo=None)
    return agora_utc.replace(second=0, microsecond=0)


def _existe_job_ativo(db, tipo: str, collection: str) -> bool:
    """True se já há job `pendente` OU `executando` do tipo — evita disparo duplicado."""
    doc = db[collection].find_one(
        {"tipo": tipo, "status": {"$in": ["pendente", "executando"]}},
        projection={"_id": 1},
    )
    return doc is not None


def inserir_job_manual(db, tipo: str, tz_name: str, collection: str = "sap_jobs") -> str:
    """Insere job avulso `pendente` pra agora. Não toca `sap_scheduler_config`.

    Retorna status: `inserido` | `ja_em_andamento` | `dedup` | `erro`.
    Guard: se já houver job `pendente`/`executando` do tipo, não insere
    (`ja_em_andamento`). Insert race-safe via unique index `(tipo, agendado_para)`
    — colisão no mesmo minuto vira `dedup`.
    """
    if tipo not in TIPOS_VALIDOS:
        return "erro"
    try:
        if _existe_job_ativo(db, tipo, collection):
            return "ja_em_andamento"
        doc = {
            "tipo": tipo,
            "parametros": {"disparo_manual": True},
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
            logger.info("sap_scheduler: disparo manual | tipo=%s _id=%s", tipo, res.inserted_id)
            return "inserido"
        except DuplicateKeyError:
            logger.info("sap_scheduler: disparo manual dedup | tipo=%s (mesmo minuto)", tipo)
            return "dedup"
    except PyMongoError as e:
        logger.warning("sap_scheduler: disparo manual erro Mongo | tipo=%s: %s", tipo, e)
        return "erro"
    except Exception:
        logger.exception("sap_scheduler: disparo manual erro inesperado | tipo=%s", tipo)
        return "erro"


_CALLBACK_REGISTERED_MARKER = "_sap_scheduler_rerun_callback_registered"


def register_callback(app, cfg: SapSchedulerConfig) -> None:
    """Registra o callback de disparo manual. Chamado 1× no boot do `app.py`.

    Idempotente via marker flag (evita `DuplicateCallback` em hot-reload).
    """
    if getattr(app, _CALLBACK_REGISTERED_MARKER, False):
        logger.info("sap_scheduler: callback de disparo manual ja registrado, skip")
        return
    setattr(app, _CALLBACK_REGISTERED_MARKER, True)

    inputs = [Input(_btn_id(tipo), "n_clicks") for tipo in sorted(TIPOS_VALIDOS)]

    @app.callback(
        Output(TOAST_ID, "is_open"),
        Output(TOAST_ID, "children"),
        Output(TOAST_ID, "icon"),
        *inputs,
        prevent_initial_call=True,
    )
    def _disparar(*_n_clicks):
        trig = ctx.triggered_id
        if not trig or not str(trig).startswith(_RERUN_BTN_PREFIX):
            raise PreventUpdate
        tipo = str(trig)[len(_RERUN_BTN_PREFIX):]
        if tipo not in TIPOS_VALIDOS:
            raise PreventUpdate

        # Re-checa autorização no servidor — não confiar só no render (botão
        # poderia ser forjado no cliente).
        from flask_login import current_user

        if not pode_disparar_manual(current_user):
            logger.warning("sap_scheduler: disparo manual NEGADO (sem permissao) | tipo=%s", tipo)
            return True, "⚠ Você não tem permissão para disparar coletas.", "danger"

        db = get_db()
        if db is None:
            return True, _MSG["erro"][0], "danger"
        status = inserir_job_manual(db, tipo, cfg.timezone, cfg.collection)
        msg, icon = _MSG[status]
        return True, msg, icon

    logger.info("sap_scheduler: callback de disparo manual registrado")
