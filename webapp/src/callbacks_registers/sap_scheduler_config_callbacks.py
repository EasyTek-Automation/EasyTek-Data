"""Callbacks da pagina /config/sap-scheduler (DS-08 / SP-09).

3 callbacks principais + 3 helpers de renderizacao:
- carregar (load via OP-CONFIG-01)
- salvar   (save via OP-CONFIG-02 + revalida + re-render)
- toggle_historico (pura UI — collapse abre/fecha)

Assinatura: `register_sap_scheduler_config_callbacks(app)` sem `db` arg
(DC-05-04 / F-05-04 — `get_mongo_connection` chamado dentro do callback).

Defesa em profundidade: callback re-checa permissao via `State` lendo
`dcc.Store` (DC-05-03 — Flask-Login `current_user` indisponivel em
callback Dash, retorna `AnonymousUserMixin`).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import dash_bootstrap_components as dbc
from dash import ALL, Input, Output, State, html, no_update

from src.sap_scheduler.storage import (
    atualizar_agendamento,
    read_config_singleton,
)
from src.sap_scheduler.validators import TIPOS_VALIDOS, validar_agendamentos

logger = logging.getLogger(__name__)

ALERT_DURATION_MS = 5000


# =========================================================================
# Helpers de renderizacao
# =========================================================================

def _construir_tabela(agendamentos: list[dict]):
    """Constroi `dbc.Table` com inputs pattern-matching pra cada tipo.

    Whitelist tecnica TIPOS_VALIDOS — sempre renderiza todos os tipos
    conhecidos. Se algum tipo nao estiver no doc, cria linha vazia
    (admin pode ativar via UI sem precisar criar entrada manual).
    """
    # Mapa tipo -> item; preenche faltantes com defaults inativos
    mapa = {item["tipo"]: item for item in agendamentos if isinstance(item, dict)}
    rows = []
    for tipo in sorted(TIPOS_VALIDOS):
        item = mapa.get(tipo, {"tipo": tipo, "hora": "03:30", "ativo": False})
        rows.append(
            html.Tr(
                [
                    html.Td(tipo, className="align-middle fw-bold"),
                    html.Td(
                        dbc.Input(
                            id={"type": "sap-sched-input-hora", "tipo": tipo},
                            type="text",
                            value=item.get("hora", "03:30"),
                            placeholder="HH:MM",
                            pattern="^([01][0-9]|2[0-3]):[0-5][0-9]$",
                            style={"max-width": "120px"},
                        ),
                    ),
                    html.Td(
                        dbc.Switch(
                            id={"type": "sap-sched-switch-ativo", "tipo": tipo},
                            value=bool(item.get("ativo", False)),
                            className="mt-2",
                        ),
                        className="align-middle",
                    ),
                ]
            )
        )

    return dbc.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Tipo"),
                        html.Th("Horario (HH:MM)"),
                        html.Th("Ativo"),
                    ]
                )
            ),
            html.Tbody(rows),
        ],
        hover=True,
        responsive=True,
        className="mb-0",
    )


def _formatar_em(em) -> str:
    """Converte ISODate (datetime ou string) em 'DD/MM HH:MM' ou '?' se invalido."""
    if em is None:
        return "?"
    if isinstance(em, str):
        try:
            em = datetime.fromisoformat(em.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return "?"
    if hasattr(em, "strftime"):
        return em.strftime("%d/%m %H:%M")
    return "?"


def _construir_texto_ultima_alteracao(doc: dict) -> str:
    """Linha pequena sob o botao: 'Ultima alteracao: DD/MM HH:MM por <quem>'."""
    if not isinstance(doc, dict):
        return ""
    historico = doc.get("historico_alteracoes") or []
    if not historico:
        return ""
    ultima = historico[0]
    if not isinstance(ultima, dict):
        return ""
    em_str = _formatar_em(ultima.get("em"))
    quem = ultima.get("quem", "desconhecido")
    return f"Ultima alteracao: {em_str} por {quem}"


def _construir_historico(historico: list[dict]):
    """Lista textual das ultimas N entradas do historico (max 20)."""
    if not historico:
        return html.Div(
            "Nenhuma alteracao registrada ainda.",
            className="text-muted small mt-2",
        )

    linhas = []
    for entrada in historico[:20]:
        if not isinstance(entrada, dict):
            continue
        em_str = _formatar_em(entrada.get("em"))
        quem = entrada.get("quem", "desconhecido")

        antes_map = {
            it["tipo"]: it
            for it in (entrada.get("antes") or [])
            if isinstance(it, dict) and "tipo" in it
        }
        depois_map = {
            it["tipo"]: it
            for it in (entrada.get("depois") or [])
            if isinstance(it, dict) and "tipo" in it
        }

        diffs = []
        for tipo in sorted(set(antes_map) | set(depois_map)):
            a = antes_map.get(tipo)
            d = depois_map.get(tipo)
            if a and d:
                if a.get("hora") != d.get("hora"):
                    diffs.append(f"{tipo}: {a.get('hora')} -> {d.get('hora')}")
                if a.get("ativo") != d.get("ativo"):
                    diffs.append(
                        f"{tipo}: {'[ativado]' if d.get('ativo') else '[desativado]'}"
                    )
            elif d:
                diffs.append(f"{tipo}: [criado] hora={d.get('hora')}")
            elif a:
                diffs.append(f"{tipo}: [removido]")
        diff_str = "; ".join(diffs) if diffs else "[sem mudancas visiveis]"
        linhas.append(html.Li(f"{em_str}  {quem}  {diff_str}", className="small"))

    return html.Ul(linhas, className="mt-2 list-unstyled")


# =========================================================================
# Registro de callbacks
# =========================================================================

def register_sap_scheduler_config_callbacks(app) -> None:
    """Registra 3 callbacks da pagina admin (DS-08 + SP-09)."""

    # ---------- Callback 1: carregar config + renderizar ----------
    @app.callback(
        Output("sap-sched-tabela-container", "children"),
        Output("sap-sched-config-atual", "data"),
        Output("sap-sched-ultima-alteracao", "children"),
        Output("sap-sched-historico-container", "children"),
        Input("sap-sched-load-trigger", "n_intervals"),
    )
    def carregar(_n):
        """SP-09 RF-09-17..21 — load via OP-CONFIG-01."""
        try:
            doc = read_config_singleton()
        except Exception as e:  # pragma: no cover — defensivo
            logger.exception("[sap-sched] erro lendo sap_scheduler_config")
            alert = dbc.Alert(
                [
                    html.I(className="bi bi-exclamation-triangle me-2"),
                    f"Erro ao consultar configuracao: {e}",
                ],
                color="danger",
            )
            return alert, None, "", ""

        if doc is None:
            alert = dbc.Alert(
                [
                    html.I(className="bi bi-info-circle me-2"),
                    "Configuracao nao encontrada — recarregue a pagina em alguns segundos.",
                ],
                color="warning",
            )
            return alert, None, "", ""

        agendamentos = doc.get("agendamentos") or []
        tabela = _construir_tabela(agendamentos)
        ultima = _construir_texto_ultima_alteracao(doc)
        historico = _construir_historico(doc.get("historico_alteracoes") or [])
        # Doc completo (com datetime) vai pro Store; Dash serializa
        return tabela, doc, ultima, historico

    # ---------- Callback 2: salvar ----------
    @app.callback(
        Output("sap-sched-alert", "children", allow_duplicate=True),
        Output("sap-sched-alert", "color", allow_duplicate=True),
        Output("sap-sched-alert", "is_open", allow_duplicate=True),
        Output("sap-sched-tabela-container", "children", allow_duplicate=True),
        Output("sap-sched-config-atual", "data", allow_duplicate=True),
        Output("sap-sched-ultima-alteracao", "children", allow_duplicate=True),
        Output("sap-sched-historico-container", "children", allow_duplicate=True),
        Input("sap-sched-btn-salvar", "n_clicks"),
        State({"type": "sap-sched-input-hora", "tipo": ALL}, "value"),
        State({"type": "sap-sched-switch-ativo", "tipo": ALL}, "value"),
        State({"type": "sap-sched-input-hora", "tipo": ALL}, "id"),
        State("sap-sched-admin-user-level", "data"),
        State("sap-sched-admin-user-perfil", "data"),
        State("sap-sched-admin-user-username", "data"),
        State("sap-sched-config-atual", "data"),
        prevent_initial_call=True,
    )
    def salvar(
        n_clicks,
        horas,
        ativos,
        ids,
        user_level,
        user_perfil,
        username,
        config_atual,
    ):
        """SP-09 RF-09-22..30 + DC-05-03 — re-check via State, NAO via current_user."""
        if not n_clicks:
            return (no_update,) * 7

        # 1. Re-check server-side de permissao (DC-05-03 — defesa em profundidade).
        # Alinhado com precedente /config/users/create (shared=True, qualquer lvl 3).
        # Perfil nao e mais filtrado server-side — route-level check ja restringiu.
        _ = user_perfil  # mantido como State pra eventual filtragem futura
        if (user_level or 0) < 3:
            msg = [
                html.I(className="bi bi-exclamation-triangle me-2"),
                "Permissao negada — requer level 3.",
            ]
            return msg, "danger", True, no_update, no_update, no_update, no_update

        # 2. Constroi lista novos a partir do form (pattern-matching State)
        novos: list[dict] = []
        for hora, ativo, id_dict in zip(horas or [], ativos or [], ids or []):
            tipo = id_dict.get("tipo") if isinstance(id_dict, dict) else None
            if not tipo:
                continue
            novos.append(
                {
                    "tipo": tipo,
                    "hora": (hora or "").strip(),  # DC-06-06
                    "ativo": bool(ativo),
                }
            )

        # 3. Valida fail-fast (SP-07 RF-07-08..13)
        try:
            validar_agendamentos(novos)
        except ValueError as e:
            msg = [
                html.I(className="bi bi-exclamation-triangle me-2"),
                str(e),
            ]
            return msg, "danger", True, no_update, no_update, no_update, no_update

        # 4. Captura `antes` (config_atual veio do Store gravado pelo callback load)
        antes = []
        if isinstance(config_atual, dict):
            antes = config_atual.get("agendamentos") or []

        # 5. Persiste via OP-CONFIG-02
        try:
            atualizar_agendamento(
                novos, quem=username or "desconhecido", antes=antes
            )
        except Exception as e:
            logger.exception("[sap-sched] erro salvando")
            msg = [
                html.I(className="bi bi-exclamation-triangle me-2"),
                f"Erro: {e}",
            ]
            return msg, "danger", True, no_update, no_update, no_update, no_update

        # 6. Mensagem de sucesso ou info (todos inativos)
        if all(not item["ativo"] for item in novos) and novos:
            mensagem = [
                html.I(className="bi bi-info-circle me-2"),
                "Atencao: todos os tipos estao inativos. Nenhum job sera disparado ate reativar.",
            ]
            cor = "info"
        else:
            mensagem = [
                html.I(className="bi bi-check-circle me-2"),
                "Agendamento atualizado. Proximo tick pega o novo valor (ate 60s).",
            ]
            cor = "success"

        # 7. Re-renderiza tabela + historico com state atualizado
        try:
            doc_novo = read_config_singleton()
            if doc_novo is None:
                return mensagem, cor, True, no_update, no_update, no_update, no_update
            tabela_nova = _construir_tabela(doc_novo.get("agendamentos") or [])
            ultima_nova = _construir_texto_ultima_alteracao(doc_novo)
            historico_novo = _construir_historico(
                doc_novo.get("historico_alteracoes") or []
            )
            return (
                mensagem,
                cor,
                True,
                tabela_nova,
                doc_novo,
                ultima_nova,
                historico_novo,
            )
        except Exception:  # pragma: no cover — defensivo
            logger.exception("[sap-sched] erro re-renderizando pos-save")
            return mensagem, cor, True, no_update, no_update, no_update, no_update

    # ---------- Callback 3: toggle do historico (puro UI) ----------
    @app.callback(
        Output("sap-sched-historico-collapse", "is_open"),
        Input("sap-sched-historico-toggle", "n_clicks"),
        State("sap-sched-historico-collapse", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_historico(_n, is_open):
        """Toggle puro UI — abre/fecha collapse de historico."""
        return not is_open
