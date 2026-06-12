"""Callbacks da aba 'Custo de Manutencao' — navegacao IDENTICA a indicators-v2.

Regra v2: sempre GRAFICO em cima + CARDS embaixo; tabela so no nivel final.
Fluxo (drill por tempo, contas sempre no eixo):
- Aba: grafico anual (GERAL + todas as contas).
- Clique -> modal nivel 'meses': grade de mini-graficos, 1 por mes (cada = GERAL +
  contas do mes). [analogo ao 'todas as maquinas' do v2]
- Clique num mes -> 'dias': grafico do mes (GERAL+contas) em cima + cards de dia.
- Clique num dia -> 'contas-dia': grafico das contas do dia + cards de conta.
- Clique numa conta -> 'lancamentos': tabela.
Voltar/Fechar em todos os niveis. Mini-graficos usam staticPlot p/ o clique borbulhar
ao Div (mesmo truque do v2).
"""
from __future__ import annotations

import logging

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, ctx, dash_table, dcc, html, no_update

try:
    from src.custos import leitura as L
    from src.custos.hierarquia import nome_conta
except ImportError:
    from custos import leitura as L  # type: ignore
    from custos.hierarquia import nome_conta  # type: ignore

logger = logging.getLogger("custos.callbacks")

_AZUL = "#0d6efd"
_VERDE = "#198754"
_VERMELHO = "#dc3545"
_LARANJA = "#fd7e14"
_CINZA = "#6c757d"
_ORCADO_FILL = "#cfe2ff"
_GRID = "rgba(0,0,0,0.06)"
_MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
          "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


# --------------------------------------------------------------------------- #
# Formatacao
# --------------------------------------------------------------------------- #
def _brl(v) -> str:
    if v is None:
        return "—"
    s = f"{v:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return f"R$ {s}"


def _brl0(v) -> str:
    if v is None:
        return "—"
    return "R$ " + f"{v:,.0f}".replace(",", ".")


def _pct(v) -> str:
    if v is None:
        return "—"
    return f"{v:.1f}".replace(".", ",") + "%"


def _nome_mes(mes: str) -> str:
    """'2026-02' -> 'Fev/26'."""
    try:
        y, m = mes.split("-")
        return f"{_MESES[int(m) - 1]}/{y[2:]}"
    except Exception:
        return mes


def _cor_exec(r: dict) -> str:
    if r.get("sem_orcamento"):
        return _LARANJA
    if r.get("estouro"):
        return _VERMELHO
    return _VERDE


# --------------------------------------------------------------------------- #
# Graficos
# --------------------------------------------------------------------------- #
def _fig_vazia(msg="Sem dados", h=380):
    fig = go.Figure()
    fig.add_annotation(text=msg, showarrow=False, x=0.5, y=0.5, xref="paper", yref="paper",
                       font={"size": 13, "color": _CINZA}, opacity=0.6)
    fig.update_layout(height=h, plot_bgcolor="rgba(248,250,252,0.6)",
                      paper_bgcolor="rgba(0,0,0,0)", xaxis={"visible": False},
                      yaxis={"visible": False}, margin={"l": 10, "r": 10, "t": 10, "b": 10})
    return fig


def _fig_barras(rows, com_orcado, titulo, h=380, mini=False):
    """Barras sobrepostas (mockup): orçado pálido container + executado sólido dentro.

    GERAL (code '__GERAL__') destacado. `mini`=True compacta para a grade de meses.
    """
    if not rows:
        return _fig_vazia(h=h)
    codes = [r["code"] for r in rows]
    nomes = [r["label"] for r in rows]   # nome legível da conta/dia
    # eixo X: nome (sem código). Mini esconde rótulos (overview clicável).
    ticks = nomes
    xs = list(range(len(rows)))

    fig = go.Figure()
    if com_orcado:
        fig.add_bar(name="Orçado", x=xs, y=[r["orcado"] for r in rows], width=0.66,
                    marker={"color": _ORCADO_FILL, "line": {"color": "#9ec5fe", "width": 1}},
                    customdata=codes, hovertext=nomes,
                    hovertemplate="%{hovertext}<br>Orçado: R$ %{y:,.2f}<extra></extra>")
    # GERAL com cor própria (cinza-azulado) p/ destacar do resto
    cores = ["#34568b" if r["code"] == "__GERAL__" else _cor_exec(r) for r in rows]
    fig.add_bar(name="Executado", x=xs, y=[r["executado"] for r in rows], width=0.34,
                marker={"color": cores}, customdata=codes, hovertext=nomes,
                hovertemplate="%{hovertext}<br>Executado: R$ %{y:,.2f}<extra></extra>")

    anots = []
    if not mini:
        for x, r in zip(xs, rows):
            topo = max(r.get("orcado", 0) or 0, r["executado"])
            if r.get("sem_orcamento"):
                txt, cor = "s/orç", _LARANJA
            elif r.get("pct") is None:
                txt, cor = "", "#8a929b"
            else:
                txt, cor = _pct(r["pct"]), (_VERMELHO if r.get("estouro") else "#495057")
            if txt:
                anots.append(dict(x=x, y=topo, text=txt, showarrow=False, yshift=11,
                                  font={"size": 10, "color": cor, "weight": "bold"}))

    fig.update_layout(
        height=h, barmode="overlay",
        plot_bgcolor="rgba(248,250,252,0.6)", paper_bgcolor="rgba(0,0,0,0)",
        margin={"l": 44, "r": 12, "t": 34 if titulo else 10, "b": 18 if mini else 150},
        title=({"text": titulo, "font": {"size": 13 if not mini else 12, "color": "#343a40"},
                "x": 0, "xanchor": "left", "y": 0.98} if titulo else None),
        showlegend=not mini,
        legend={"orientation": "h", "y": 1.1, "x": 0, "font": {"size": 11}},
        bargap=0.35, annotations=anots,
        xaxis={"tickmode": "array", "tickvals": xs, "ticktext": ticks,
               "showgrid": False, "zeroline": False, "tickfont": {"size": 10},
               "tickangle": -35, "showticklabels": not mini},
        yaxis={"showgrid": True, "gridcolor": _GRID, "zeroline": False,
               "tickprefix": "R$ ", "tickformat": ",.0f", "tickfont": {"size": 9 if mini else 10},
               "rangemode": "tozero", "showticklabels": not mini},
        hoverlabel={"bgcolor": "white", "font_size": 12},
    )
    return fig


def _graph_click(rows, graph_id, com_orcado, titulo, h=360):
    """Gráfico grande clicável (clique na barra dispara drill)."""
    return dcc.Graph(id=graph_id, figure=_fig_barras(rows, com_orcado, titulo, h=h),
                     config={"displayModeBar": False, "responsive": True},
                     style={"height": f"{h}px", "cursor": "pointer"})


# --------------------------------------------------------------------------- #
# Cards clicáveis (espelha mini-cards do v2)
# --------------------------------------------------------------------------- #
def _mini_graph_card(mes, rows):
    """Card-mini-gráfico de um mês (grade do nível 'meses'). Clicável (staticPlot)."""
    return dbc.Col(
        html.Div(
            dbc.Card(
                [
                    dbc.CardHeader(html.Strong(_nome_mes(mes), style={"fontSize": "0.85rem"}),
                                   className="py-1"),
                    dbc.CardBody(
                        dcc.Graph(figure=_fig_barras(rows, True, "", h=200, mini=True),
                                  config={"displayModeBar": False, "staticPlot": True,
                                          "responsive": True},
                                  style={"height": "200px"}),
                        className="p-1",
                    ),
                ],
                className="shadow-sm h-100 indicator-v2-card",
            ),
            id={"type": "custo-mes-card", "mes": mes},
            n_clicks=0, style={"cursor": "pointer", "height": "100%"},
        ),
        xs=12, sm=6, md=4, className="mb-3",
    )


def _value_card(titulo, valor_txt, cor, cid, sub=None):
    """Card de valor clicável (dia / conta) — padrão dos mini-cards do v2."""
    body = [html.Div(titulo, className="text-muted small mb-1", style={"fontWeight": "600"}),
            html.Div(valor_txt, style={"fontSize": "1.0rem", "fontWeight": "bold", "color": cor})]
    if sub:
        body.append(html.Div(sub, style={"fontSize": "0.7rem", "color": cor}))
    return dbc.Col(
        html.Div(
            dbc.Card(dbc.CardBody(body, className="text-center py-2"),
                     className="shadow-sm h-100", style={"borderTop": f"3px solid {cor}"}),
            id=cid, n_clicks=0, style={"cursor": "pointer"},
        ),
        xs=6, sm=4, md=3, lg=2, className="mb-2",
    )


def _tabela_lancamentos(docs):
    if not docs:
        return html.Small("Nenhum lançamento neste recorte.", className="text-muted")
    rows = []
    for d in docs:
        dt = d.get("data_lancamento")
        rows.append({
            "data": dt.strftime("%d/%m/%Y") if dt else "",
            "conta": d.get("conta", ""), "centro": d.get("centro_custo", ""),
            "valor": _brl(d.get("valor")),
            "descritor": d.get("descritor", "") or "(sem descrição)",
            "tipo": d.get("tipo_doc", ""), "documento": d.get("no_documento", ""),
        })
    return dash_table.DataTable(
        data=rows,
        columns=[{"name": "Data", "id": "data"}, {"name": "Conta", "id": "conta"},
                 {"name": "Centro", "id": "centro"}, {"name": "Valor", "id": "valor"},
                 {"name": "Descrição", "id": "descritor"}, {"name": "Tipo", "id": "tipo"},
                 {"name": "Documento", "id": "documento"}],
        page_size=12, sort_action="native", style_as_list_view=True,
        style_cell={"fontSize": "0.82rem", "padding": "8px 10px", "textAlign": "left",
                    "border": "none", "borderBottom": "1px solid #eef0f3"},
        style_header={"fontWeight": "700", "textTransform": "uppercase", "fontSize": "0.7rem",
                      "letterSpacing": "0.4px", "color": "#6c757d",
                      "backgroundColor": "#fafbfc", "borderBottom": "2px solid #e9ecef"},
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "rgba(248,250,252,0.6)"},
            {"if": {"column_id": "valor"}, "textAlign": "right", "fontWeight": "600"},
            {"if": {"column_id": "descritor"}, "color": "#495057"}],
        style_table={"overflowX": "auto"},
    )


def _crumb(*partes):
    itens = []
    for i, p in enumerate(partes):
        if i:
            itens.append(html.Span(" › ", className="mx-1 text-muted"))
        itens.append(html.Span(p, className="text-primary fw-semibold"))
    return itens


# --------------------------------------------------------------------------- #
# Registro
# --------------------------------------------------------------------------- #
def register_custo_callbacks(app):
    """Registra todos os callbacks da aba de custo."""

    @app.callback(
        Output("custo-centro-filter", "options"),
        Input("custo-init", "n_intervals"),
        State("store-custo-ano", "data"),
    )
    def _popular_centros(_n, ano):
        return [{"label": c, "value": c} for c in L.fetch_centros_disponiveis(int(ano or 2026))]

    @app.callback(
        Output("store-custo-centros", "data"),
        Input("custo-centro-filter", "value"),
        prevent_initial_call=True,
    )
    def _set_centros(value):
        return value or []

    @app.callback(
        Output("store-custo-ano", "data"),
        Input("custo-ano-select", "value"),
        prevent_initial_call=True,
    )
    def _set_ano(value):
        return value

    # Gráfico de entrada (anual) + selo + tarja
    @app.callback(
        Output("custo-graph-entry", "figure"),
        Output("custo-seed-selo", "children"),
        Output("custo-reconc-banner", "children"),
        Input("store-custo-centros", "data"),
        Input("store-custo-ano", "data"),
        Input("custo-init", "n_intervals"),
    )
    def _render_entry(centros, ano, _n):
        ano = int(ano or 2026)
        centros = centros or None
        fig = _fig_barras(L.fetch_contas_geral(ano, None, centros), True,
                          "", h=460)
        rc = L.reconciliacao(ano)
        banner = None
        if rc.get("por_mes") and not rc["bate"]:
            banner = dbc.Alert(
                [html.I(className="bi bi-exclamation-triangle me-2"),
                 f"Esta coleta não fechou com o SAP (diferença {_brl(rc['diff'])}). "
                 "Confira antes de decidir."], color="warning", className="py-2 mb-0")
        selo = None
        if L.fonte_dos_dados(ano) == "csv":
            selo = dbc.Badge([html.I(className="bi bi-info-circle me-1"),
                              "dados de exemplo (seed)"], color="secondary")
        return fig, selo, banner

    # Controle do modal (espelha control_modal da v2)
    @app.callback(
        Output("modal-custo", "is_open"),
        Output("store-custo-level", "data"),
        Output("store-custo-mes", "data"),
        Output("store-custo-dia", "data"),
        Output("store-custo-conta", "data"),
        Output("modal-custo-content", "children", allow_duplicate=True),
        Output("modal-custo-title", "children", allow_duplicate=True),
        Output("modal-custo-breadcrumb", "children", allow_duplicate=True),
        Input("custo-entry-wrap", "n_clicks"),
        Input({"type": "custo-mes-card", "mes": ALL}, "n_clicks"),
        Input({"type": "custo-dia-card", "dia": ALL}, "n_clicks"),
        Input({"type": "custo-conta-card", "conta": ALL}, "n_clicks"),
        Input({"type": "custo-bar", "nivel": ALL}, "clickData"),
        Input("btn-custo-back", "n_clicks"),
        Input("btn-custo-close", "n_clicks"),
        State("store-custo-level", "data"),
        State("store-custo-mes", "data"),
        State("store-custo-dia", "data"),
        State("store-custo-conta", "data"),
        prevent_initial_call=True,
    )
    def _control_modal(*args):
        trig = ctx.triggered_id
        level, mes, dia, conta = args[-4], args[-3], args[-2], args[-1]
        CLEAR = (None, "", None)
        NOOP = (no_update,) * 5 + CLEAR

        if trig == "btn-custo-close":
            return (False, "planta", None, None, None) + CLEAR
        if trig == "btn-custo-back":
            if level == "lancamentos":
                return (True, "contas-dia" if dia else "dias", mes, dia, None) + CLEAR
            if level == "contas-dia":
                return (True, "dias", mes, None, None) + CLEAR
            if level == "dias":
                return (True, "meses", None, None, None) + CLEAR
            if level == "meses":
                return (False, "planta", None, None, None) + CLEAR
            return NOOP

        # Clique no gráfico de entrada (área inteira clicável) → abre nível meses
        if trig == "custo-entry-wrap":
            tr = dash.callback_context.triggered
            if not tr or not tr[0].get("value"):
                return NOOP
            return (True, "meses", None, None, None) + CLEAR

        if isinstance(trig, dict):
            t = trig.get("type")
            _val = (dash.callback_context.triggered or [{}])[0].get("value")
            if t in ("custo-mes-card", "custo-dia-card", "custo-conta-card") and not _val:
                return NOOP
            if t == "custo-mes-card":
                return (True, "dias", trig["mes"], None, None) + CLEAR
            if t == "custo-dia-card":
                return (True, "contas-dia", mes, trig["dia"], None) + CLEAR
            if t == "custo-conta-card":
                return (True, "lancamentos", mes, dia, trig["conta"]) + CLEAR
            if t == "custo-bar":
                tr = dash.callback_context.triggered
                if not tr or tr[0].get("value") is None:
                    return NOOP
                code = tr[0]["value"]["points"][0].get("customdata")
                if code is None or code == "__GERAL__":
                    return NOOP
                niv = trig.get("nivel")
                if niv == "mes-contas":      # conta clicada no gráfico do mês
                    return (True, "lancamentos", mes, None, code) + CLEAR
                if niv == "dia-contas":      # conta clicada no gráfico do dia
                    return (True, "lancamentos", mes, dia, code) + CLEAR
        return NOOP

    # Render do conteúdo do modal por nível (espelha render_modal da v2)
    @app.callback(
        Output("modal-custo-content", "children", allow_duplicate=True),
        Output("modal-custo-title", "children", allow_duplicate=True),
        Output("modal-custo-breadcrumb", "children", allow_duplicate=True),
        Output("btn-custo-back", "style"),
        Input("store-custo-level", "data"),
        Input("store-custo-mes", "data"),
        Input("store-custo-dia", "data"),
        Input("store-custo-conta", "data"),
        State("store-custo-centros", "data"),
        State("store-custo-ano", "data"),
        prevent_initial_call=True,
    )
    def _render_modal(level, mes, dia, conta, centros, ano):
        if not level or level == "planta":
            return None, "", None, {"display": "none"}
        ano = int(ano or 2026)
        centros = centros or None
        ano_lbl = f"{ano}"

        # NÍVEL 1 — meses (grade de mini-gráficos, 1 por mês)
        if level == "meses":
            meses = L.meses_com_dados(ano)
            cards = [_mini_graph_card(m, L.fetch_contas_geral(ano, m, centros)) for m in meses]
            content = html.Div([
                html.H6("Clique num mês para ver os dias:", className="v2-section-h6 text-muted"),
                dbc.Row(cards, className="g-3"),
            ])
            return content, "Custo — meses (orçado × executado)", _crumb(ano_lbl), {}

        # NÍVEL 2 — dias (gráfico do mês + cards de dia)
        if level == "dias" and mes:
            rows = L.fetch_contas_geral(ano, mes, centros)
            dias = L.fetch_dias_total_mes(ano, mes, centros)
            cards = [_value_card(d["label"], _brl0(d["executado"]), _AZUL,
                                 {"type": "custo-dia-card", "dia": d["code"]}) for d in dias]
            content = html.Div([
                _graph_click(rows, {"type": "custo-bar", "nivel": "mes-contas"}, True,
                             f"{_nome_mes(mes)} — orçado × executado por conta"),
                html.Hr(),
                html.H6("Clique num dia (card) para ver as contas do dia, ou numa barra "
                        "de conta para os lançamentos:", className="v2-section-h6 text-muted"),
                dbc.Row(cards, className="g-2"),
            ])
            return (content, f"Custo — {_nome_mes(mes)}",
                    _crumb(ano_lbl, _nome_mes(mes)), {})

        # NÍVEL 3 — contas do dia (gráfico das contas do dia + cards de conta)
        if level == "contas-dia" and dia:
            rows = L.fetch_contas_no_dia(ano, dia, centros)
            cards = [_value_card(r["label"], _brl0(r["executado"]), _AZUL,
                                 {"type": "custo-conta-card", "conta": r["code"]})
                     for r in rows if r["code"] != "__GERAL__"]
            content = html.Div([
                _graph_click(rows, {"type": "custo-bar", "nivel": "dia-contas"}, False,
                             f"{dia[-2:]}/{_nome_mes(mes)} — executado por conta"),
                html.Hr(),
                html.H6("Clique numa conta (card ou barra) para ver os lançamentos:",
                        className="v2-section-h6 text-muted"),
                dbc.Row(cards, className="g-2"),
            ])
            return (content, f"Custo — {dia[-2:]}/{_nome_mes(mes)} — contas do dia",
                    _crumb(ano_lbl, _nome_mes(mes), f"Dia {dia[-2:]}"), {})

        # NÍVEL 4 — lançamentos (tabela)
        if level == "lancamentos" and conta:
            nome = nome_conta(conta)
            if dia:
                docs = L.fetch_lancamentos_no_dia(ano, dia, conta=conta, centros=centros)
                escopo = f"{dia[-2:]}/{_nome_mes(mes)}"
                crumb = _crumb(ano_lbl, _nome_mes(mes), f"Dia {dia[-2:]}", nome)
            else:
                docs = L.fetch_lancamentos(ano, conta=conta, mes=mes, centros=centros)
                escopo = _nome_mes(mes)
                crumb = _crumb(ano_lbl, _nome_mes(mes), nome)
            content = html.Div([
                html.H6(f"Lançamentos — {nome} ({conta}), {escopo}",
                        className="v2-section-h6 text-muted"),
                _tabela_lancamentos(docs),
            ])
            return content, f"Custo — {nome} — {escopo}", crumb, {}

        return None, "", None, {"display": "none"}

    # Botão "Rodar agora"
    @app.callback(
        Output("custo-rodar-feedback", "children"),
        Input("btn-custo-rodar-agora", "n_clicks"),
        prevent_initial_call=True,
    )
    def _rodar_agora(_n):
        try:
            from src.sap_scheduler.mongo_helpers import get_db
            from src.custos.sap_jobs import enqueue_ambos, _LABEL
        except ImportError:
            from sap_scheduler.mongo_helpers import get_db  # type: ignore
            from custos.sap_jobs import enqueue_ambos, _LABEL  # type: ignore
        db = get_db()
        if db is None:
            return dbc.Alert("Banco indisponível — não foi possível enfileirar.",
                             color="danger", dismissable=True, className="py-2")
        res = enqueue_ambos(db)
        msg_map = {"inserido": "enfileirada", "ja_em_andamento": "já em andamento",
                   "dedup": "já enfileirada neste minuto", "erro": "falhou"}
        linhas = [f"{_LABEL.get(t, t)}: {msg_map.get(s, s)}" for t, s in res.items()]
        cor = "success" if any(s == "inserido" for s in res.values()) else "info"
        return dbc.Alert(
            [html.Div("Coletas SAP solicitadas:", className="fw-bold"),
             html.Ul([html.Li(x) for x in linhas], className="mb-1"),
             html.Small("A execução roda no coletor do cliente (transporte diferido); "
                        "enquanto isso, os dados vêm da carga de exemplo (seed).",
                        className="text-muted")],
            color=cor, dismissable=True, className="py-2")
