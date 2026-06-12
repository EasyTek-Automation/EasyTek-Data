"""Callbacks da aba 'Custo de Manutencao' — navegacao IDENTICA a indicators-v2.

Mesma mecanica de drilldown da v2 (control_modal + render_modal): cards clicaveis no
topo (os 4 GRUPOS) abrem um modal unico; dentro, contas -> meses -> dias ->
lancamentos, com gráfico grande clicavel + mini-cards por nivel (inclusive cards de
mes) e botoes Voltar/Fechar. Stores de nivel proprios (autocontido).
"""
from __future__ import annotations

import logging
from datetime import datetime

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, ctx, dash_table, dcc, html, no_update

try:
    from src.custos import leitura as L
    from src.custos.hierarquia import GRUPOS, label_grupo
except ImportError:
    from custos import leitura as L  # type: ignore
    from custos.hierarquia import GRUPOS, label_grupo  # type: ignore

logger = logging.getLogger("custos.callbacks")

# Paleta (alinhada à indicators-v2)
_AZUL = "#0d6efd"
_VERDE = "#198754"
_VERMELHO = "#dc3545"
_LARANJA = "#fd7e14"
_CINZA = "#6c757d"
_ORCADO_FILL = "#cfe2ff"
_GRID = "rgba(0,0,0,0.06)"

_MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
          "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
# Cor de borda por grupo (4 grupos GT340)
_COR_GRUPO = {"G0341": "#0d6efd", "G0342": "#6f42c1", "G0343": "#20c997", "G0344": "#fd7e14"}


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


def _cor_exec(ln: dict) -> str:
    if ln.get("sem_orcamento"):
        return _LARANJA
    if ln.get("estouro"):
        return _VERMELHO
    return _VERDE


# --------------------------------------------------------------------------- #
# Cards KPI do geral (resumo)
# --------------------------------------------------------------------------- #
def _kpi_card(titulo, valor, cor_borda, valor_cor="#212529", sub=None) -> dbc.Col:
    corpo = [
        html.Span(titulo, className="text-muted fw-semibold d-block",
                  style={"fontSize": "0.72rem", "letterSpacing": "0.4px",
                         "textTransform": "uppercase"}),
        html.Span(valor, className="d-block",
                  style={"fontSize": "1.6rem", "fontWeight": "700", "color": valor_cor,
                         "letterSpacing": "-0.5px", "lineHeight": "1.15"}),
    ]
    if sub:
        corpo.append(html.Span(sub, className="text-muted", style={"fontSize": "0.74rem"}))
    return dbc.Col(
        dbc.Card(dbc.CardBody(corpo, className="py-2 px-3"),
                 className="shadow-sm h-100 indicator-v2-card-md",
                 style={"borderTop": f"4px solid {cor_borda}"}),
        xs=6, md=3, className="mb-2",
    )


def _card_geral(m: dict) -> html.Div:
    if m["sem_orcamento"]:
        cor_pct = _LARANJA
    elif m["estouro"] or (m["pct"] or 0) >= 90:
        cor_pct = _VERMELHO if m["estouro"] else _LARANJA
    else:
        cor_pct = _VERDE
    saldo_cor = _VERMELHO if m["saldo"] < 0 else _VERDE
    barra = dbc.Progress(
        value=min(m["pct"] or 0, 100), label=_pct(m["pct"]),
        color="danger" if m["estouro"] else ("warning" if (m["pct"] or 0) >= 90 else "success"),
        className="mt-1", style={"height": "18px", "fontSize": "0.72rem"},
    )
    return html.Div([
        dbc.Row([
            _kpi_card("Orçado (ano)", _brl(m["orcado"]), _CINZA),
            _kpi_card("Executado", _brl(m["executado"]), _AZUL, _AZUL),
            _kpi_card("% Consumido", _pct(m["pct"]), cor_pct, cor_pct,
                      sub="sem orçamento" if m["sem_orcamento"] else None),
            _kpi_card("Saldo", _brl(m["saldo"]), saldo_cor, saldo_cor),
        ], className="g-2"),
        barra,
    ])


def _card_grupo(g_code: str, m: dict) -> dbc.Col:
    """Card clicável de um grupo — entrada do drilldown (abre o modal)."""
    cor = _COR_GRUPO.get(g_code, _AZUL)
    val_cor = _VERMELHO if m["estouro"] else cor
    return dbc.Col(
        html.Div(
            dbc.Card(
                dbc.CardBody(
                    [
                        html.Div(
                            [
                                html.Strong(label_grupo(g_code), style={"fontSize": "0.95rem"}),
                                dbc.Badge([html.I(className="bi bi-zoom-in me-1"), "abrir"],
                                          color="light", text_color="primary",
                                          className="border", style={"fontSize": "0.68rem"}),
                            ],
                            className="d-flex justify-content-between align-items-start mb-1",
                        ),
                        html.Span(_brl(m["executado"]), className="d-block",
                                  style={"fontSize": "1.5rem", "fontWeight": "700",
                                         "color": val_cor, "lineHeight": "1.1"}),
                        html.Small([f"de {_brl0(m['orcado'])} orçado · ",
                                    html.Span(_pct(m["pct"]),
                                              style={"fontWeight": "600", "color": val_cor})],
                                   className="text-muted"),
                        dbc.Progress(
                            value=min(m["pct"] or 0, 100),
                            color="danger" if m["estouro"] else "primary",
                            className="mt-2", style={"height": "8px"},
                        ),
                    ],
                    className="py-2 px-3",
                ),
                className="shadow-sm h-100 indicator-v2-card",
                style={"borderTop": f"4px solid {cor}"},
            ),
            id={"type": "custo-grupo", "grupo": g_code},
            n_clicks=0, style={"cursor": "pointer", "height": "100%"},
        ),
        xs=12, sm=6, lg=3, className="mb-3",
    )


# --------------------------------------------------------------------------- #
# Graficos
# --------------------------------------------------------------------------- #
def _fig_vazia(msg="Sem dados para o recorte"):
    fig = go.Figure()
    fig.add_annotation(text=msg, showarrow=False, x=0.5, y=0.5, xref="paper", yref="paper",
                       font={"size": 14, "color": _CINZA}, opacity=0.6)
    fig.update_layout(height=380, plot_bgcolor="rgba(248,250,252,0.6)",
                      paper_bgcolor="rgba(0,0,0,0)", xaxis={"visible": False},
                      yaxis={"visible": False}, margin={"l": 10, "r": 10, "t": 10, "b": 10})
    return fig


def _fig_barras(rows, com_orcado, titulo):
    """Barras sobrepostas (mockup): orçado pálido container + executado sólido dentro.

    `rows` normalizadas: {label, code, orcado, executado, pct, estouro, sem_orcamento}.
    """
    if not rows:
        return _fig_vazia()
    codes = [r["code"] for r in rows]
    ticks = [f"<b>{r['label']}</b><br><span style='font-size:0.72em;color:#8a929b'>"
             f"{_brl0(r['executado'])}</span>" for r in rows]
    xs = list(range(len(rows)))

    fig = go.Figure()
    if com_orcado:
        fig.add_bar(name="Orçado", x=xs, y=[r["orcado"] for r in rows], width=0.66,
                    marker={"color": _ORCADO_FILL, "line": {"color": "#9ec5fe", "width": 1}},
                    customdata=codes,
                    hovertemplate="%{customdata}<br>Orçado: R$ %{y:,.2f}<extra></extra>")
    fig.add_bar(name="Executado", x=xs, y=[r["executado"] for r in rows], width=0.34,
                marker={"color": [_cor_exec(r) for r in rows]}, customdata=codes,
                hovertemplate="%{customdata}<br>Executado: R$ %{y:,.2f}<extra></extra>")

    anots = []
    for x, r in zip(xs, rows):
        topo = max(r.get("orcado", 0) or 0, r["executado"])
        if r.get("sem_orcamento"):
            txt, cor = "s/orç", _LARANJA
        elif r.get("pct") is None:
            txt, cor = "", "#8a929b"
        else:
            txt, cor = _pct(r["pct"]), (_VERMELHO if r.get("estouro") else "#495057")
        if txt:
            anots.append(dict(x=x, y=topo, text=txt, showarrow=False, yshift=12,
                              font={"size": 11, "color": cor, "weight": "bold"}))

    fig.update_layout(
        height=380, barmode="overlay",
        plot_bgcolor="rgba(248,250,252,0.6)", paper_bgcolor="rgba(0,0,0,0)",
        margin={"l": 56, "r": 16, "t": 40, "b": 70},
        title={"text": titulo, "font": {"size": 13, "color": "#343a40"},
               "x": 0, "xanchor": "left", "y": 0.98},
        legend={"orientation": "h", "y": 1.1, "x": 0, "font": {"size": 11}},
        bargap=0.35, annotations=anots,
        xaxis={"tickmode": "array", "tickvals": xs, "ticktext": ticks,
               "showgrid": False, "zeroline": False, "tickfont": {"size": 11}},
        yaxis={"showgrid": True, "gridcolor": _GRID, "zeroline": False,
               "tickprefix": "R$ ", "tickformat": ",.0f", "tickfont": {"size": 10},
               "rangemode": "tozero"},
        hoverlabel={"bgcolor": "white", "font_size": 12},
    )
    return fig


def _graph(rows, graph_id, com_orcado, titulo):
    """dcc.Graph clicável do nível (clique na barra dispara o drill)."""
    return dcc.Graph(
        id=graph_id, figure=_fig_barras(rows, com_orcado, titulo),
        config={"displayModeBar": False, "responsive": True},
        style={"height": "380px", "cursor": "pointer"},
    )


# --------------------------------------------------------------------------- #
# Mini-cards clicáveis (espelha os mini-cards de mês/dia da v2)
# --------------------------------------------------------------------------- #
def _mini_card(titulo, valor_txt, cor, cid, sub=None):
    body = [html.Div(titulo, className="text-muted small mb-1", style={"fontWeight": "600"}),
            html.Div(valor_txt, style={"fontSize": "1.05rem", "fontWeight": "bold", "color": cor})]
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


# --------------------------------------------------------------------------- #
# Tabela de lançamentos (DS-08)
# --------------------------------------------------------------------------- #
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
    """Monta a lista de spans do breadcrumb pill (último = destacado via CSS)."""
    itens = []
    for i, p in enumerate(partes):
        if i:
            itens.append(html.Span(" › ", className="mx-1 text-muted"))
        itens.append(html.Span(p, className="text-primary fw-semibold"))
    return itens


# --------------------------------------------------------------------------- #
# Normalizadores por nível
# --------------------------------------------------------------------------- #
def _rows_contas(grupo, ano, centros):
    return [{"label": r["conta"], "code": r["conta"], "orcado": r["orcado"],
             "executado": r["executado"], "pct": r["pct"], "estouro": r["estouro"],
             "sem_orcamento": r["sem_orcamento"], "desc": r.get("conta_desc", "")}
            for r in L.fetch_contas(grupo, ano, centros)]


def _rows_meses(conta, ano, centros):
    return [{"label": _nome_mes(r["mes"]), "code": r["mes"], "orcado": r["orcado"],
             "executado": r["executado"], "pct": r["pct"], "estouro": r["estouro"],
             "sem_orcamento": r["sem_orcamento"]}
            for r in L.fetch_meses_da_conta(conta, ano, centros)]


def _rows_dias(conta, mes, centros):
    return [{"label": r["dia"][-2:], "code": r["dia"], "orcado": 0,
             "executado": r["executado"], "pct": None, "estouro": False,
             "sem_orcamento": False}
            for r in L.fetch_dias_da_conta_mes(conta, mes, centros)]


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

    # Topo da aba: resumo geral + cards de grupo + selo + tarja
    @app.callback(
        Output("custo-card-geral", "children"),
        Output("custo-grupos-cards", "children"),
        Output("custo-seed-selo", "children"),
        Output("custo-reconc-banner", "children"),
        Input("store-custo-centros", "data"),
        Input("store-custo-ano", "data"),
        Input("custo-init", "n_intervals"),
    )
    def _render_topo(centros, ano, _n):
        ano = int(ano or 2026)
        centros = centros or None
        card = _card_geral(L.fetch_geral(ano, centros))

        grupos = {g["grupo"]: g for g in L.fetch_grupos(ano, centros)}
        cards = dbc.Row([_card_grupo(g, grupos[g]) for g in GRUPOS if g in grupos], className="g-3")

        rc = L.reconciliacao(ano)
        banner = None
        if rc.get("por_mes") and not rc["bate"]:
            banner = dbc.Alert(
                [html.I(className="bi bi-exclamation-triangle me-2"),
                 f"Esta coleta não fechou com o SAP (diferença {_brl(rc['diff'])}). "
                 "Confira antes de decidir."],
                color="warning", className="py-2 mb-0")
        selo = None
        if L.fonte_dos_dados(ano) == "csv":
            selo = dbc.Badge([html.I(className="bi bi-info-circle me-1"),
                              "dados de exemplo (seed)"], color="secondary")
        return card, cards, selo, banner

    # Controle do modal: abre/avança/volta/fecha (espelha control_modal da v2)
    @app.callback(
        Output("modal-custo", "is_open"),
        Output("store-custo-level", "data"),
        Output("store-custo-grupo", "data"),
        Output("store-custo-conta", "data"),
        Output("store-custo-mes", "data"),
        Output("store-custo-dia", "data"),
        Output("modal-custo-content", "children", allow_duplicate=True),
        Output("modal-custo-title", "children", allow_duplicate=True),
        Output("modal-custo-breadcrumb", "children", allow_duplicate=True),
        Input({"type": "custo-grupo", "grupo": ALL}, "n_clicks"),
        Input({"type": "custo-conta", "conta": ALL}, "n_clicks"),
        Input({"type": "custo-mes", "mes": ALL}, "n_clicks"),
        Input({"type": "custo-dia", "dia": ALL}, "n_clicks"),
        Input({"type": "custo-bar", "nivel": ALL}, "clickData"),
        Input("btn-custo-back", "n_clicks"),
        Input("btn-custo-close", "n_clicks"),
        State("store-custo-level", "data"),
        State("store-custo-grupo", "data"),
        State("store-custo-conta", "data"),
        State("store-custo-mes", "data"),
        prevent_initial_call=True,
    )
    def _control_modal(*args):
        trig = ctx.triggered_id
        level, grupo, conta, mes = args[-4], args[-3], args[-2], args[-1]
        CLEAR = (None, "", None)
        NOOP = (no_update,) * 6 + CLEAR

        if trig == "btn-custo-close":
            return (False, "planta", None, None, None, None) + CLEAR
        if trig == "btn-custo-back":
            if level == "lancamentos":
                return (True, "dias", grupo, conta, mes, None) + CLEAR
            if level == "dias":
                return (True, "meses", grupo, conta, None, None) + CLEAR
            if level == "meses":
                return (True, "contas", grupo, None, None, None) + CLEAR
            if level == "contas":
                return (False, "planta", None, None, None, None) + CLEAR
            return NOOP

        if isinstance(trig, dict):
            t = trig.get("type")
            # Cards montados dinamicamente disparam com n_clicks=0/None — ignora
            # (só clique real, n_clicks>=1, abre/avança). Barras tratadas à parte.
            _val = (dash.callback_context.triggered or [{}])[0].get("value")
            if t in ("custo-grupo", "custo-conta", "custo-mes", "custo-dia") and not _val:
                return NOOP
            if t == "custo-grupo":
                return (True, "contas", trig["grupo"], None, None, None) + CLEAR
            if t == "custo-conta":
                return (True, "meses", grupo, trig["conta"], None, None) + CLEAR
            if t == "custo-mes":
                return (True, "dias", grupo, conta, trig["mes"], None) + CLEAR
            if t == "custo-dia":
                return (True, "lancamentos", grupo, conta, mes, trig["dia"]) + CLEAR
            # cliques nas barras dos gráficos grandes (id wildcard custo-bar/nivel)
            if t == "custo-bar":
                tr = dash.callback_context.triggered
                if not tr or tr[0].get("value") is None:
                    return NOOP
                code = tr[0]["value"]["points"][0].get("customdata")
                if code is None:
                    return NOOP
                niv = trig.get("nivel")
                if niv == "conta":
                    return (True, "meses", grupo, code, None, None) + CLEAR
                if niv == "mes":
                    return (True, "dias", grupo, conta, code, None) + CLEAR
                if niv == "dia":
                    return (True, "lancamentos", grupo, conta, mes, code) + CLEAR
        return NOOP

    # Render do conteúdo do modal por nível (espelha render_modal da v2)
    @app.callback(
        Output("modal-custo-content", "children", allow_duplicate=True),
        Output("modal-custo-title", "children", allow_duplicate=True),
        Output("modal-custo-breadcrumb", "children", allow_duplicate=True),
        Output("btn-custo-back", "style"),
        Input("store-custo-level", "data"),
        Input("store-custo-grupo", "data"),
        Input("store-custo-conta", "data"),
        Input("store-custo-mes", "data"),
        Input("store-custo-dia", "data"),
        State("store-custo-centros", "data"),
        State("store-custo-ano", "data"),
        prevent_initial_call=True,
    )
    def _render_modal(level, grupo, conta, mes, dia, centros, ano):
        if not grupo or level == "planta":
            return None, "", None, {"display": "none"}
        ano = int(ano or 2026)
        centros = centros or None
        g_label = label_grupo(grupo)

        # NÍVEL 1 — contas do grupo
        if level == "contas":
            rows = _rows_contas(grupo, ano, centros)
            mini = [_mini_card(r["label"], _brl0(r["executado"]), _cor_exec(r),
                               {"type": "custo-conta", "conta": r["code"]},
                               sub=_pct(r["pct"]) if r["pct"] is not None
                               else ("s/orç" if r["sem_orcamento"] else None))
                    for r in rows]
            content = html.Div([
                _graph(rows, {"type": "custo-bar", "nivel": "conta"}, True,
                       f"{g_label} — contas (orçado × executado)"),
                html.Hr(),
                html.H6("Clique numa barra ou num card para ver os meses:",
                        className="v2-section-h6 text-muted"),
                dbc.Row(mini, className="g-2"),
            ])
            return content, f"Custo — {g_label}", _crumb(g_label), {}

        # NÍVEL 2 — meses da conta (CARDS DE MÊS)
        if level == "meses" and conta:
            rows = _rows_meses(conta, ano, centros)
            mini = [_mini_card(r["label"], _brl0(r["executado"]), _cor_exec(r),
                               {"type": "custo-mes", "mes": r["code"]},
                               sub=_pct(r["pct"]) if r["pct"] is not None
                               else ("s/orç" if r["sem_orcamento"] else None))
                    for r in rows]
            content = html.Div([
                _graph(rows, {"type": "custo-bar", "nivel": "mes"}, True,
                       f"Conta {conta} — meses (orçado × executado)"),
                html.Hr(),
                html.H6("Clique numa barra ou num card de mês para ver os dias:",
                        className="v2-section-h6 text-muted"),
                dbc.Row(mini, className="g-2"),
            ])
            return content, f"Custo — {g_label} — conta {conta}", _crumb(g_label, f"Conta {conta}"), {}

        # NÍVEL 3 — dias do mês (CARDS DE DIA)
        if level == "dias" and conta and mes:
            rows = _rows_dias(conta, mes, centros)
            mini = [_mini_card(r["label"], _brl0(r["executado"]), _AZUL,
                               {"type": "custo-dia", "dia": r["code"]})
                    for r in rows]
            content = html.Div([
                _graph(rows, {"type": "custo-bar", "nivel": "dia"}, False,
                       f"Conta {conta} — {_nome_mes(mes)} — executado por dia"),
                html.Hr(),
                html.H6("Clique numa barra ou num card de dia para ver os lançamentos:",
                        className="v2-section-h6 text-muted"),
                dbc.Row(mini, className="g-2"),
            ])
            return (content, f"Custo — conta {conta} — {_nome_mes(mes)}",
                    _crumb(g_label, f"Conta {conta}", _nome_mes(mes)), {})

        # NÍVEL 4 — lançamentos do dia
        if level == "lancamentos" and conta and mes:
            docs = L.fetch_lancamentos(ano, conta=conta, mes=mes, centros=centros)
            if dia:
                docs = [d for d in docs if d.get("data_lancamento")
                        and d["data_lancamento"].strftime("%Y-%m-%d") == dia]
            dia_txt = dia[-2:] if dia else "—"
            content = html.Div([
                html.H6(f"Lançamentos — conta {conta}, {dia_txt}/{_nome_mes(mes)}",
                        className="v2-section-h6 text-muted"),
                _tabela_lancamentos(docs),
            ])
            return (content, f"Custo — conta {conta} — {dia_txt}/{_nome_mes(mes)}",
                    _crumb(g_label, f"Conta {conta}", _nome_mes(mes), f"Dia {dia_txt}"), {})

        return None, "", None, {"display": "none"}

    # Botão "Rodar agora" — enfileira coletas SAP (execução no cliente, diferida)
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
