# src/callbacks_registers/dds_config_callbacks.py
#
# Callbacks da configuração do DDS (/maintenance/dds):
#   1. Carrega os números de segurança, o histórico e os tempos salvos
#   2. Registra um acidente (zera o contador do telão)
#   3. Remove um registro de acidente (correção de cadastro errado)
#   4. Salva os minutos dos 6 passos / restaura o padrão
#   5. Mostra o total de minutos enquanto se digita

from dash import Input, Output, State, ALL, ctx, html, no_update
import dash_bootstrap_components as dbc
from flask_login import current_user

from src.utils import dds_data
from src.pages.maintenance.dds import PASSOS


def _usuario():
    """Nome de quem está mexendo — vai para o rastro de auditoria."""
    return getattr(current_user, "username", None)


def _alerta(ok, msg):
    return dbc.Alert(
        [html.I(className=f"bi bi-{'check-circle' if ok else 'exclamation-triangle'} me-2"), msg],
        color="success" if ok else "danger", duration=6000, className="mb-0",
    )


def _numero(valor, rotulo, cor, ajuda):
    """Cartão de número grande (dias sem acidente / recorde)."""
    return dbc.Col(
        html.Div(
            [
                html.Div(rotulo, className="text-muted",
                         style={"fontSize": "0.75rem", "letterSpacing": "0.08em"}),
                html.Div(valor, style={"fontSize": "2.6rem", "fontWeight": 800,
                                       "lineHeight": 1, "color": cor}),
                html.Small(ajuda, className="text-muted"),
            ],
            className="p-3 border rounded bg-light h-100",
        ),
        xs=12, md=4,
    )


def register_dds_config_callbacks(app):
    """Registra os callbacks da página de configuração do DDS."""

    # 1. Carga da página e recarga após cada gravação
    @app.callback(
        Output("dds-cfg-numeros", "children"),
        Output("dds-cfg-historico", "children"),
        Output("dds-cfg-passo-0", "value"),
        Output("dds-cfg-passo-1", "value"),
        Output("dds-cfg-passo-2", "value"),
        Output("dds-cfg-passo-3", "value"),
        Output("dds-cfg-passo-4", "value"),
        Output("dds-cfg-passo-5", "value"),
        Input("dds-cfg-refresh", "data"),
    )
    def carregar(_n):
        dias = dds_data.dias_sem_acidente()
        recorde, batendo = dds_data.recorde_dias()
        ultimo = dds_data.ultimo_acidente()

        numeros = dbc.Row(
            [
                _numero("—" if dias is None else str(dias), "DIAS SEM ACIDENTE", "#198754",
                        "O número grande do telão."),
                _numero("—" if recorde is None else str(recorde), "RECORDE", "#0d6efd",
                        "Recorde sendo batido agora." if batendo
                        else "Melhor período já alcançado."),
                _numero(ultimo.strftime("%d/%m/%Y") if ultimo else "—", "ÚLTIMO ACIDENTE",
                        "#dc3545",
                        "Sem registro — o telão mostra um traço." if not ultimo
                        else "Data que zerou o contador."),
            ],
            className="g-3",
        )

        registros = dds_data.listar_acidentes()
        if not registros:
            historico = dbc.Alert(
                [html.I(className="bi bi-info-circle me-2"),
                 "Nenhum acidente registrado. Enquanto não houver registro, o telão exibe "
                 "um traço no lugar do número de dias."],
                color="light", className="mb-0",
            )
        else:
            linhas = [
                html.Tr([
                    html.Td(r["data"].strftime("%d/%m/%Y")),
                    html.Td(r["observacao"] or html.Span("—", className="text-muted")),
                    html.Td(r["registrado_por"] or html.Span("—", className="text-muted"),
                            className="text-muted"),
                    html.Td(
                        dbc.Button(html.I(className="bi bi-trash"),
                                   id={"type": "dds-cfg-del", "id": r["id"]},
                                   color="link", size="sm", className="text-danger p-0",
                                   title="Remover este registro"),
                        className="text-end",
                    ),
                ])
                for r in registros
            ]
            historico = dbc.Table(
                [html.Thead(html.Tr([html.Th("Data"), html.Th("Observação"),
                                     html.Th("Registrado por"), html.Th()])),
                 html.Tbody(linhas)],
                hover=True, size="sm", className="mb-0",
            )

        passos = dds_data.passos_minutos()
        return (numeros, historico, *passos)

    # 2. Registrar acidente
    @app.callback(
        Output("dds-cfg-msg-acidente", "children"),
        Output("dds-cfg-refresh", "data"),
        Output("dds-cfg-data", "date"),
        Output("dds-cfg-obs", "value"),
        Input("btn-dds-cfg-registrar", "n_clicks"),
        State("dds-cfg-data", "date"),
        State("dds-cfg-obs", "value"),
        State("dds-cfg-refresh", "data"),
        prevent_initial_call=True,
    )
    def registrar(_n, data, obs, refresh):
        ok, msg = dds_data.registrar_acidente(data, usuario=_usuario(), observacao=obs or "")
        if not ok:
            return _alerta(False, msg), no_update, no_update, no_update
        return _alerta(True, msg), (refresh or 0) + 1, None, ""

    # 3. Remover registro
    @app.callback(
        Output("dds-cfg-msg-acidente", "children", allow_duplicate=True),
        Output("dds-cfg-refresh", "data", allow_duplicate=True),
        Input({"type": "dds-cfg-del", "id": ALL}, "n_clicks"),
        State("dds-cfg-refresh", "data"),
        prevent_initial_call=True,
    )
    def remover(cliques, refresh):
        # A lista nasce toda com n_clicks=None; sem isto o callback apagaria um
        # registro a cada recarga da tabela.
        if not any(cliques or []):
            return no_update, no_update
        alvo = (ctx.triggered_id or {}).get("id")
        if not alvo:
            return no_update, no_update
        ok, msg = dds_data.remover_acidente(alvo)
        return _alerta(ok, msg), (refresh or 0) + 1 if ok else no_update

    # 4. Salvar tempos / restaurar padrão
    @app.callback(
        Output("dds-cfg-msg-tempos", "children"),
        Output("dds-cfg-refresh", "data", allow_duplicate=True),
        Output("dds-cfg-passo-0", "value", allow_duplicate=True),
        Output("dds-cfg-passo-1", "value", allow_duplicate=True),
        Output("dds-cfg-passo-2", "value", allow_duplicate=True),
        Output("dds-cfg-passo-3", "value", allow_duplicate=True),
        Output("dds-cfg-passo-4", "value", allow_duplicate=True),
        Output("dds-cfg-passo-5", "value", allow_duplicate=True),
        Input("btn-dds-cfg-salvar", "n_clicks"),
        Input("btn-dds-cfg-padrao", "n_clicks"),
        State("dds-cfg-passo-0", "value"), State("dds-cfg-passo-1", "value"),
        State("dds-cfg-passo-2", "value"), State("dds-cfg-passo-3", "value"),
        State("dds-cfg-passo-4", "value"), State("dds-cfg-passo-5", "value"),
        State("dds-cfg-refresh", "data"),
        prevent_initial_call=True,
    )
    def salvar_tempos(_s, _p, p0, p1, p2, p3, p4, p5, refresh):
        if ctx.triggered_id == "btn-dds-cfg-padrao":
            # Só preenche os campos — quem salva é o usuário, no botão ao lado.
            padrao = list(dds_data.PASSOS_PADRAO)
            return (dbc.Alert([html.I(className="bi bi-info-circle me-2"),
                               "Campos preenchidos com o padrão. Clique em “Salvar tempos” "
                               "para valer."], color="info", duration=6000, className="mb-0"),
                    no_update, *padrao)

        ok, msg = dds_data.salvar_passos([p0, p1, p2, p3, p4, p5], usuario=_usuario())
        if not ok:
            return _alerta(False, msg), no_update, *([no_update] * 6)
        return _alerta(True, msg), (refresh or 0) + 1, *([no_update] * 6)

    # 5. Total de minutos enquanto se digita
    @app.callback(
        Output("dds-cfg-total", "children"),
        Input("dds-cfg-passo-0", "value"), Input("dds-cfg-passo-1", "value"),
        Input("dds-cfg-passo-2", "value"), Input("dds-cfg-passo-3", "value"),
        Input("dds-cfg-passo-4", "value"), Input("dds-cfg-passo-5", "value"),
    )
    def total(*valores):
        try:
            soma = sum(int(v) for v in valores if v is not None)
        except (TypeError, ValueError):
            return ""
        faltando = [PASSOS[i] for i, v in enumerate(valores) if v is None]
        if faltando:
            return f"Faltou preencher: {', '.join(faltando)}."
        return f"O DDS inteiro leva {soma} minutos."
