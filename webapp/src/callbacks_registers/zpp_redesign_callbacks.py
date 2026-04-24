"""
Callbacks do ZPP Processor redesenhado.
Upload retroativo (IN-13) e histórico de logs (IN-14).
"""
import base64
import io
import logging
import os
from datetime import datetime

import dash
import requests
from dash import Output, Input, State, html, no_update, clientside_callback
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from flask_login import current_user

logger = logging.getLogger(__name__)

ZPP_API_URL = os.getenv("ZPP_PROCESSOR_URL", "http://zpp-processor:5002")
ZPP_INTERNAL_SECRET = os.getenv("ZPP_INTERNAL_SECRET", "")
PER_PAGE = 20

_MESES = ["Jan","Fev","Mar","Abr","Mai","Jun",
          "Jul","Ago","Set","Out","Nov","Dez"]


def _internal_headers() -> dict:
    """Headers de autenticação interna para chamadas ao zpp-processor."""
    return {
        "X-ZPP-Secret": ZPP_INTERNAL_SECRET,
        "X-ZPP-User":   getattr(current_user, "username", "desconhecido"),
        "X-ZPP-Level":  str(getattr(current_user, "level", 0)),
    }


def _status_badge(status: str):
    mapping = {
        "success":  ("success", "✅ Sucesso"),
        "rejected": ("danger",  "❌ Rejeitado"),
        "failed":   ("warning", "⚠️ Erro"),
    }
    color, label = mapping.get(status, ("secondary", status))
    return dbc.Badge(label, color=color, pill=True)


def _fmt_mes(mes_ref: str) -> str:
    """'2026-02' → 'Fev/2026'"""
    try:
        y, m = mes_ref.split("-")
        return f"{_MESES[int(m)-1]}/{y}"
    except Exception:
        return mes_ref


def _fmt_dt(iso: str) -> str:
    """ISO 8601 → 'DD/MM/AAAA HH:MM'"""
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return iso


def register_zpp_redesign_callbacks(app):

    # ------------------------------------------------------------------
    # CB-1 — Habilitar botão de envio (clientside)
    # ------------------------------------------------------------------
    clientside_callback(
        """
        function(contents, ano, mes, justificativa) {
            var filled = contents && ano && mes &&
                         justificativa && justificativa.trim().length >= 10;
            return !filled;
        }
        """,
        Output("btn-enviar-retroativo", "disabled"),
        Input("upload-zpp-retroativo", "contents"),
        Input("select-ano-retroativo", "value"),
        Input("select-mes-retroativo", "value"),
        Input("textarea-justificativa-retroativo", "value"),
        prevent_initial_call=True,
    )

    # ------------------------------------------------------------------
    # CB-2 — Mostrar nome do arquivo selecionado
    # ------------------------------------------------------------------
    @app.callback(
        Output("upload-zpp-filename", "children"),
        Input("upload-zpp-retroativo", "filename"),
        prevent_initial_call=True,
    )
    def show_filename(filename):
        if not filename:
            return ""
        return [html.I(className="bi bi-file-earmark-excel me-1 text-success"), filename]

    # ------------------------------------------------------------------
    # CB-3 — Enviar upload retroativo
    # ------------------------------------------------------------------
    @app.callback(
        Output("resultado-upload-retroativo", "children"),
        Output("btn-enviar-retroativo", "disabled", allow_duplicate=True),
        Input("btn-enviar-retroativo", "n_clicks"),
        State("upload-zpp-retroativo", "contents"),
        State("upload-zpp-retroativo", "filename"),
        State("select-ano-retroativo", "value"),
        State("select-mes-retroativo", "value"),
        State("textarea-justificativa-retroativo", "value"),
        prevent_initial_call=True,
    )
    def enviar_upload(n_clicks, contents, filename, ano, mes, justificativa):
        if not n_clicks or not contents:
            raise PreventUpdate

        # Decodificar base64
        try:
            content_type, content_string = contents.split(",", 1)
            file_bytes = base64.b64decode(content_string)
        except Exception as e:
            return dbc.Alert(f"Erro ao ler o arquivo: {e}", color="danger"), False

        try:
            resp = requests.post(
                f"{ZPP_API_URL}/upload/retroativo",
                data={"ano": ano, "mes": mes, "justificativa": justificativa},
                files={"file": (filename, io.BytesIO(file_bytes))},
                headers=_internal_headers(),
                timeout=60,
            )
        except requests.RequestException as e:
            return dbc.Alert(f"Erro de conexão com o serviço ZPP: {e}", color="danger"), False

        data = resp.json()

        if resp.status_code == 200:
            children = [
                dbc.Alert([
                    html.Strong("✓ Processado com sucesso"), html.Br(),
                    f"Tipo: {data.get('tipo')} | Mês: {_fmt_mes(data.get('mes_referencia',''))}",
                    html.Br(),
                    f"Inseridos: {data.get('registros_inseridos')} | "
                    f"Deletados: {data.get('registros_deletados')} | "
                    f"Strays descartados: {sum(s.get('quantidade',0) for s in data.get('strays_descartados',[]))}",
                ], color="success"),
            ]
            if data.get("aviso"):
                children.append(dbc.Alert(data["aviso"], color="warning"))
            return children, False

        if resp.status_code == 422:
            return dbc.Alert(
                [html.Strong("Arquivo rejeitado: "), data.get("motivo", "")],
                color="warning"
            ), False

        if resp.status_code == 409:
            return dbc.Alert(
                "Já existe um processamento em andamento. Tente novamente em instantes.",
                color="info"
            ), False

        if resp.status_code == 401:
            return dbc.Alert("Sessão expirada. Recarregue a página.", color="danger"), False

        return dbc.Alert("Erro interno no servidor. Contate o administrador.", color="danger"), False

    # ------------------------------------------------------------------
    # CB-4 — Carregar tabela de logs
    # ------------------------------------------------------------------
    @app.callback(
        Output("tabela-logs-zpp-container", "children"),
        Output("store-logs-page", "data"),
        Output("store-logs-items", "data"),
        Output("btn-logs-prev", "disabled"),
        Output("btn-logs-next", "disabled"),
        Output("txt-logs-page", "children"),
        Input("zpp-tabs", "active_tab"),
        Input("filter-tipo-logs", "value"),
        Input("filter-canal-logs", "value"),
        Input("filter-status-logs", "value"),
        Input("filter-mes-logs", "value"),
        Input("store-logs-page", "data"),
        prevent_initial_call=True,
    )
    def carregar_logs(active_tab, tipo, canal, status, mes, page):
        if active_tab != "tab-historico-logs":
            raise PreventUpdate

        from dash import callback_context
        trigger = callback_context.triggered_id
        if trigger in ("filter-tipo-logs", "filter-canal-logs",
                       "filter-status-logs", "filter-mes-logs"):
            page = 1

        page = page or 1

        params = {"page": page, "per_page": PER_PAGE}
        if tipo:   params["tipo"]   = tipo
        if canal:  params["canal"]  = canal
        if status: params["status"] = status
        if mes:    params["mes"]    = mes

        try:
            resp = requests.get(
                f"{ZPP_API_URL}/logs",
                params=params,
                headers=_internal_headers(),
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return (dbc.Alert(f"Erro ao carregar logs: {e}", color="danger"),
                    page, [], True, True, "")

        items = data.get("items", [])
        total = data.get("total", 0)
        total_pages = max((total + PER_PAGE - 1) // PER_PAGE, 1)

        if not items:
            tabela = html.P("Nenhum registro encontrado.", className="text-muted text-center py-4")
        else:
            rows = []
            for i, item in enumerate(items):
                rows.append(html.Tr([
                    html.Td(_fmt_dt(item.get("iniciado_em", "")), className="small"),
                    html.Td(item.get("arquivo", ""), className="small text-truncate",
                            style={"maxWidth": "200px"}),
                    html.Td(item.get("tipo", ""), className="small"),
                    html.Td("Padrão" if item.get("canal") == "padrao" else "Retroativo",
                            className="small"),
                    html.Td(_fmt_mes(item.get("mes_referencia", "")), className="small"),
                    html.Td(_status_badge(item.get("status", "")), className="small"),
                    html.Td(str(item.get("registros_inseridos", "")), className="small text-end"),
                    html.Td(str(item.get("registros_deletados", "")), className="small text-end"),
                    html.Td(
                        dbc.Button("Ver", size="sm", color="link", className="p-0",
                                   id={"type": "btn-ver-log", "index": i}),
                    ),
                ], className="align-middle"))

            tabela = dbc.Table([
                html.Thead(html.Tr([
                    html.Th("Data"), html.Th("Arquivo"), html.Th("Tipo"),
                    html.Th("Canal"), html.Th("Mês"), html.Th("Status"),
                    html.Th("Inseridos", className="text-end"),
                    html.Th("Deletados", className="text-end"),
                    html.Th(""),
                ])),
                html.Tbody(rows),
            ], bordered=True, hover=True, responsive=True, size="sm")

        txt_page = f"Página {page} de {total_pages}" if total > 0 else ""
        return (tabela, page, items,
                page <= 1, page >= total_pages, txt_page)

    # ------------------------------------------------------------------
    # CB-5 — Navegar entre páginas (botões fixos prev/next)
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-logs-page", "data", allow_duplicate=True),
        Input("btn-logs-prev", "n_clicks"),
        Input("btn-logs-next", "n_clicks"),
        State("store-logs-page", "data"),
        prevent_initial_call=True,
    )
    def mudar_pagina(n_prev, n_next, page):
        from dash import callback_context
        trigger = callback_context.triggered_id
        page = page or 1
        if trigger == "btn-logs-prev":
            return max(1, page - 1)
        if trigger == "btn-logs-next":
            return page + 1
        raise PreventUpdate

    # ------------------------------------------------------------------
    # CB-6 — Abrir modal de detalhe
    # ------------------------------------------------------------------
    @app.callback(
        Output("modal-detalhe-log", "is_open"),
        Output("modal-log-title", "children"),
        Output("modal-log-body", "children"),
        Input({"type": "btn-ver-log", "index": dash.ALL}, "n_clicks"),
        State("store-logs-items", "data"),
        prevent_initial_call=True,
    )
    def abrir_modal(n_clicks_list, items):
        from dash import callback_context
        if not any(n for n in n_clicks_list if n):
            raise PreventUpdate

        triggered = callback_context.triggered_id
        if not triggered:
            raise PreventUpdate

        try:
            item = items[triggered["index"]]
        except Exception:
            raise PreventUpdate

        titulo = f"{item.get('arquivo', '')} — {_fmt_dt(item.get('iniciado_em', ''))}"

        corpo = [
            dbc.Row([
                dbc.Col([html.Strong("Tipo: "), item.get("tipo", "")], md=3),
                dbc.Col([html.Strong("Canal: "),
                         "Padrão" if item.get("canal") == "padrao" else "Retroativo"], md=3),
                dbc.Col([html.Strong("Mês: "), _fmt_mes(item.get("mes_referencia", ""))], md=3),
                dbc.Col([html.Strong("Status: "), _status_badge(item.get("status", ""))], md=3),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col([html.Strong("Operador: "), item.get("operador", "")], md=4),
                dbc.Col([html.Strong("Inseridos: "), str(item.get("registros_inseridos", ""))], md=4),
                dbc.Col([html.Strong("Deletados: "), str(item.get("registros_deletados", ""))], md=4),
            ], className="mb-2"),
        ]

        if item.get("canal") == "retroativo":
            corpo.append(dbc.Row([
                dbc.Col([html.Strong("Justificativa: "), item.get("justificativa", "")]),
            ], className="mb-2"))

        if item.get("strays_descartados"):
            corpo.append(html.Div([
                html.Strong("Strays descartados:"),
                html.Ul([html.Li(f"{s['mes']}: {s['quantidade']} registros")
                         for s in item["strays_descartados"]]),
            ], className="mb-2"))

        if item.get("inconsistencias"):
            corpo.append(html.Div([
                html.Strong("Inconsistências:"),
                html.Ul([
                    html.Li(f"{inc.get('equipamento')} | Ordem {inc.get('ordem')} | "
                            f"{inc.get('sobreposicao_min')} min de sobreposição")
                    for inc in item["inconsistencias"]
                ]),
            ], className="mb-2"))

        if item.get("motivo_rejeicao"):
            corpo.append(dbc.Alert(
                [html.Strong("Motivo de rejeição: "), item["motivo_rejeicao"]],
                color="warning", className="mb-2"
            ))

        if item.get("erro"):
            corpo.append(html.Div([
                html.Strong("Erro interno:"),
                dbc.Textarea(value=item["erro"], readOnly=True, rows=8,
                             className="font-monospace small mt-1"),
            ]))

        return True, titulo, corpo

    # ------------------------------------------------------------------
    # CB-7 — Fechar modal
    # ------------------------------------------------------------------
    @app.callback(
        Output("modal-detalhe-log", "is_open", allow_duplicate=True),
        Input("btn-fechar-modal-log", "n_clicks"),
        prevent_initial_call=True,
    )
    def fechar_modal(n):
        return False
