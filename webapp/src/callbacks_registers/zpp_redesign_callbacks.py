"""
Callbacks do ZPP Processor redesenhado.
Upload retroativo (IN-13) e histórico de logs (IN-14).
"""
import base64
import io
import logging
import os
from datetime import datetime

import requests
from dash import Output, Input, State, html, no_update, clientside_callback, ClientsideFunction
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from flask import request as flask_request

logger = logging.getLogger(__name__)

ZPP_API_URL = os.getenv("ZPP_PROCESSOR_URL", "http://zpp-processor:5002")
PER_PAGE = 20

_MESES = ["Jan","Fev","Mar","Abr","Mai","Jun",
          "Jul","Ago","Set","Out","Nov","Dez"]


def _session_cookie() -> str:
    try:
        return flask_request.cookies.get("session", "")
    except RuntimeError:
        return ""


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

        cookie = _session_cookie()
        try:
            resp = requests.post(
                f"{ZPP_API_URL}/upload/retroativo",
                data={"ano": ano, "mes": mes, "justificativa": justificativa},
                files={"file": (filename, io.BytesIO(file_bytes))},
                cookies={"session": cookie},
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
