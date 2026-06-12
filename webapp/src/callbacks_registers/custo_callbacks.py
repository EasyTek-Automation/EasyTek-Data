"""Callbacks da aba 'Custo de Manutencao' (DS-07/DS-08/DS-09).

Bloco autocontido: stores e ids proprios, drill-down grupo -> conta -> mes -> dia
por clique no grafico, breadcrumb para voltar, filtro lateral de centro de custo,
card do geral, tarja de reconciliacao, selo de seed, tabela de lancamentos e o
botao 'Rodar agora' (placeholder ate o transporte SAP — Bloco D).
"""
from __future__ import annotations

import logging

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, ctx, dash_table, dcc, html, no_update

try:
    from src.custos import leitura as L
    from src.custos.hierarquia import label_grupo
except ImportError:  # contexto de teste/script
    from custos import leitura as L  # type: ignore
    from custos.hierarquia import label_grupo  # type: ignore

logger = logging.getLogger("custos.callbacks")

# Paleta (alinhada à indicators-v2)
_AZUL = "#0d6efd"
_VERDE = "#198754"
_VERMELHO = "#dc3545"
_LARANJA = "#fd7e14"
_CINZA = "#6c757d"
_ORCADO_FILL = "#cfe2ff"   # barra "container" do orçado (azul pálido)
_GRID = "rgba(0,0,0,0.06)"


# --------------------------------------------------------------------------- #
# Formatacao
# --------------------------------------------------------------------------- #
def _brl(v) -> str:
    """Formata numero como moeda BR ('R$ 1.234,56')."""
    if v is None:
        return "—"
    s = f"{v:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return f"R$ {s}"


def _brl0(v) -> str:
    """Moeda BR sem centavos ('R$ 190.830') — rótulos compactos do gráfico."""
    if v is None:
        return "—"
    return "R$ " + f"{v:,.0f}".replace(",", ".")


def _pct(v) -> str:
    """Formata percentual ('90,7%') ou '—' quando indefinido (sem orçamento)."""
    if v is None:
        return "—"
    return f"{v:.1f}".replace(".", ",") + "%"


def _cor_exec(ln: dict) -> str:
    """Cor da barra de executado: laranja s/orçamento, vermelho estouro, verde ok."""
    if ln.get("sem_orcamento"):
        return _LARANJA
    if ln.get("estouro"):
        return _VERMELHO
    return _VERDE


# --------------------------------------------------------------------------- #
# Componentes
# --------------------------------------------------------------------------- #
def _kpi_card(titulo: str, valor: str, cor_borda: str, valor_cor: str = "#212529",
              sub=None) -> dbc.Col:
    """Card KPI no padrão indicators-v2: borda superior colorida + valor grande."""
    corpo = [
        html.Span(titulo, className="text-muted fw-semibold d-block",
                  style={"fontSize": "0.72rem", "letterSpacing": "0.4px",
                         "textTransform": "uppercase"}),
        html.Span(valor, className="d-block",
                  style={"fontSize": "1.6rem", "fontWeight": "700",
                         "color": valor_cor, "letterSpacing": "-0.5px",
                         "lineHeight": "1.15"}),
    ]
    if sub:
        corpo.append(html.Span(sub, className="text-muted", style={"fontSize": "0.74rem"}))
    return dbc.Col(
        dbc.Card(
            dbc.CardBody(corpo, className="py-2 px-3"),
            className="shadow-sm h-100 indicator-v2-card-md",
            style={"borderTop": f"4px solid {cor_borda}"},
        ),
        xs=6, md=3, className="mb-2",
    )


def _card_geral(m: dict) -> html.Div:
    """4 cards KPI do GT340 (orçado/executado/%/saldo) + barra de consumo."""
    if m["sem_orcamento"]:
        cor_pct = _LARANJA
    elif m["estouro"]:
        cor_pct = _VERMELHO
    elif (m["pct"] or 0) >= 90:
        cor_pct = _LARANJA
    else:
        cor_pct = _VERDE
    saldo_cor = _VERMELHO if m["saldo"] < 0 else _VERDE
    barra = dbc.Progress(
        value=min(m["pct"] or 0, 100),
        label=_pct(m["pct"]),
        color="danger" if m["estouro"] else ("warning" if (m["pct"] or 0) >= 90 else "success"),
        className="mt-1",
        style={"height": "18px", "fontSize": "0.72rem"},
    )
    return html.Div(
        [
            dbc.Row(
                [
                    _kpi_card("Orçado (ano)", _brl(m["orcado"]), _CINZA),
                    _kpi_card("Executado", _brl(m["executado"]), _AZUL, _AZUL),
                    _kpi_card("% Consumido", _pct(m["pct"]), cor_pct, cor_pct,
                              sub="sem orçamento" if m["sem_orcamento"] else None),
                    _kpi_card("Saldo", _brl(m["saldo"]), saldo_cor, saldo_cor),
                ],
                className="g-2",
            ),
            barra,
        ],
    )


def _fig_vazia(msg="Sem dados para o recorte"):
    """Figura placeholder limpa (sem 'No data' default do Plotly)."""
    fig = go.Figure()
    fig.add_annotation(text=msg, showarrow=False, x=0.5, y=0.5,
                       xref="paper", yref="paper",
                       font={"size": 14, "color": _CINZA}, opacity=0.6)
    fig.update_layout(height=420, plot_bgcolor="rgba(248,250,252,0.6)",
                      paper_bgcolor="rgba(0,0,0,0)",
                      xaxis={"visible": False}, yaxis={"visible": False},
                      margin={"l": 10, "r": 10, "t": 10, "b": 10})
    return fig


def _fig_barras(linhas, campo_label, campo_code, com_orcado=True, titulo=""):
    """Gráfico do nível atual no padrão do mockup.

    Barras **sobrepostas**: orçado = barra larga pálida (container); executado =
    barra estreita sólida por dentro (verde dentro / vermelho estouro / laranja sem
    orçamento). Rótulo de % acima de cada barra. `customdata`=código para o drill.
    Eixo X em 2 linhas (rótulo + executado em R$). Altura FIXA (420).
    """
    if not linhas:
        return _fig_vazia()

    codes = [ln[campo_code] for ln in linhas]
    base = [str(ln[campo_label]) for ln in linhas]
    # rótulo do eixo X em 2 linhas: nome + executado compacto
    ticks = [f"<b>{b}</b><br><span style='font-size:0.72em;color:#8a929b'>{_brl0(ln['executado'])}</span>"
             for b, ln in zip(base, linhas)]
    xs = list(range(len(linhas)))
    execs = [ln["executado"] for ln in linhas]
    cores_exec = [_cor_exec(ln) for ln in linhas]

    fig = go.Figure()
    if com_orcado:
        fig.add_bar(
            name="Orçado", x=xs, y=[ln["orcado"] for ln in linhas],
            width=0.66, marker={"color": _ORCADO_FILL,
                                "line": {"color": "#9ec5fe", "width": 1}},
            customdata=codes, offsetgroup=0,
            hovertemplate="%{customdata}<br>Orçado: R$ %{y:,.2f}<extra></extra>",
        )
    fig.add_bar(
        name="Executado", x=xs, y=execs,
        width=0.34, marker={"color": cores_exec}, customdata=codes, offsetgroup=0,
        hovertemplate="%{customdata}<br>Executado: R$ %{y:,.2f}<extra></extra>",
    )

    # rótulos de % (ou s/orç) acima da barra mais alta de cada item
    anots = []
    for x, ln in zip(xs, linhas):
        topo = max(ln.get("orcado", 0) or 0, ln["executado"])
        if ln.get("sem_orcamento"):
            txt, cor = "s/orç", _LARANJA
        elif ln.get("pct") is None:
            txt, cor = "—", "#8a929b"
        else:
            txt, cor = _pct(ln["pct"]), (_VERMELHO if ln.get("estouro") else "#495057")
        anots.append(dict(x=x, y=topo, text=txt, showarrow=False, yshift=12,
                          font={"size": 11, "color": cor,
                                "family": "Arial", "weight": "bold"}))

    fig.update_layout(
        height=420, barmode="overlay",
        plot_bgcolor="rgba(248,250,252,0.6)", paper_bgcolor="rgba(0,0,0,0)",
        margin={"l": 56, "r": 16, "t": 44, "b": 78},
        title={"text": titulo, "font": {"size": 14, "color": "#343a40"},
               "x": 0, "xanchor": "left", "y": 0.97},
        legend={"orientation": "h", "y": 1.08, "x": 0, "font": {"size": 11}},
        bargap=0.35, annotations=anots,
        xaxis={"tickmode": "array", "tickvals": xs, "ticktext": ticks,
               "showgrid": False, "zeroline": False, "tickangle": 0,
               "tickfont": {"size": 11}},
        yaxis={"showgrid": True, "gridcolor": _GRID, "zeroline": False,
               "tickprefix": "R$ ", "tickformat": ",.0f", "tickfont": {"size": 10},
               "rangemode": "tozero"},
        hoverlabel={"bgcolor": "white", "font_size": 12},
    )
    return fig


def _tabela_lancamentos(docs) -> object:
    """Tabela de lançamentos do recorte (DS-08)."""
    if not docs:
        return html.Small("Selecione uma conta ou mês para ver os lançamentos.",
                          className="text-muted")
    rows = []
    for d in docs:
        dt = d.get("data_lancamento")
        rows.append({
            "data": dt.strftime("%d/%m/%Y") if dt else "",
            "conta": d.get("conta", ""),
            "centro": d.get("centro_custo", ""),
            "valor": _brl(d.get("valor")),
            "descritor": d.get("descritor", "") or "(sem descrição)",
            "tipo": d.get("tipo_doc", ""),
            "documento": d.get("no_documento", ""),
        })
    return dash_table.DataTable(
        data=rows,
        columns=[
            {"name": "Data", "id": "data"},
            {"name": "Conta", "id": "conta"},
            {"name": "Centro", "id": "centro"},
            {"name": "Valor", "id": "valor"},
            {"name": "Descrição", "id": "descritor"},
            {"name": "Tipo", "id": "tipo"},
            {"name": "Documento", "id": "documento"},
        ],
        page_size=12,
        sort_action="native",
        style_as_list_view=True,
        style_cell={"fontSize": "0.82rem", "padding": "8px 10px", "textAlign": "left",
                    "fontFamily": "inherit", "border": "none",
                    "borderBottom": "1px solid #eef0f3"},
        style_header={"fontWeight": "700", "textTransform": "uppercase",
                      "fontSize": "0.7rem", "letterSpacing": "0.4px",
                      "color": "#6c757d", "backgroundColor": "#fafbfc",
                      "borderBottom": "2px solid #e9ecef"},
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "rgba(248,250,252,0.6)"},
            {"if": {"column_id": "valor"}, "textAlign": "right",
             "fontVariantNumeric": "tabular-nums", "fontWeight": "600"},
            {"if": {"column_id": "descritor"}, "color": "#495057"},
        ],
        style_table={"overflowX": "auto"},
        page_action="native",
    )


def _breadcrumb(drill: dict) -> object:
    """Trilha de navegação clicável (volta a um nível)."""
    nivel = drill.get("nivel", "planta")
    itens = [("Planta (GT340)", {"type": "custo-crumb", "lvl": "planta"})]
    if nivel in ("grupo", "conta", "mes") and drill.get("grupo"):
        itens.append((label_grupo(drill["grupo"]),
                      {"type": "custo-crumb", "lvl": "grupo"}))
    if nivel in ("conta", "mes") and drill.get("conta"):
        itens.append((f"Conta {drill['conta']}",
                      {"type": "custo-crumb", "lvl": "conta"}))
    if nivel == "mes" and drill.get("mes"):
        itens.append((f"Mês {drill['mes']}", {"type": "custo-crumb", "lvl": "mes"}))
    botoes = []
    for i, (txt, cid) in enumerate(itens):
        ultimo = i == len(itens) - 1
        botoes.append(
            dbc.Button(txt, id=cid, size="sm", disabled=ultimo,
                       color="link" if not ultimo else "secondary",
                       className="p-0 me-1" if not ultimo else "p-1 me-1")
        )
        if not ultimo:
            botoes.append(html.Span("›", className="text-muted me-1"))
    return html.Div(botoes, className="d-flex align-items-center flex-wrap")


# --------------------------------------------------------------------------- #
# Registro
# --------------------------------------------------------------------------- #
def register_custo_callbacks(app):
    """Registra todos os callbacks da aba de custo."""

    @app.callback(
        Output("custo-centro-filter", "options"),
        Input("custo-init", "n_intervals"),
        State("store-custo-ano", "data"),
        prevent_initial_call=False,
    )
    def _popular_centros(_n, ano):
        """Popula o filtro lateral com os centros disponíveis no ano."""
        ano = ano or 2026
        return [{"label": c, "value": c} for c in L.fetch_centros_disponiveis(int(ano))]

    @app.callback(
        Output("store-custo-centros", "data"),
        Input("custo-centro-filter", "value"),
        prevent_initial_call=True,
    )
    def _set_centros(value):
        """Espelha a seleção de centros no store (reseta drill não é necessário)."""
        return value or []

    @app.callback(
        Output("store-custo-ano", "data"),
        Input("custo-ano-select", "value"),
        prevent_initial_call=True,
    )
    def _set_ano(value):
        """Atualiza o ano selecionado."""
        return value

    @app.callback(
        Output("store-custo-drill", "data", allow_duplicate=True),
        Input("custo-graph", "clickData"),
        State("store-custo-drill", "data"),
        prevent_initial_call=True,
    )
    def _drill(click, drill):
        """Avança um nível ao clicar numa barra (usa customdata = código)."""
        if not click or not click.get("points"):
            return no_update
        code = click["points"][0].get("customdata")
        if code is None:
            return no_update
        drill = dict(drill or {"nivel": "planta"})
        nivel = drill.get("nivel", "planta")
        if nivel == "planta":
            return {"nivel": "grupo", "grupo": code}
        if nivel == "grupo":
            return {"nivel": "conta", "grupo": drill.get("grupo"), "conta": code}
        if nivel == "conta":
            return {"nivel": "mes", "grupo": drill.get("grupo"),
                    "conta": drill.get("conta"), "mes": code}
        return no_update  # nível dia não drilla mais

    @app.callback(
        Output("store-custo-drill", "data", allow_duplicate=True),
        Input({"type": "custo-crumb", "lvl": ALL}, "n_clicks"),
        State("store-custo-drill", "data"),
        prevent_initial_call=True,
    )
    def _breadcrumb_nav(_clicks, drill):
        """Volta ao nível clicado na trilha."""
        if not ctx.triggered_id or not any(_clicks or []):
            return no_update
        lvl = ctx.triggered_id.get("lvl")
        drill = dict(drill or {})
        if lvl == "planta":
            return {"nivel": "planta"}
        if lvl == "grupo":
            return {"nivel": "grupo", "grupo": drill.get("grupo")}
        if lvl == "conta":
            return {"nivel": "conta", "grupo": drill.get("grupo"), "conta": drill.get("conta")}
        return no_update

    @app.callback(
        Output("custo-rodar-feedback", "children"),
        Input("btn-custo-rodar-agora", "n_clicks"),
        prevent_initial_call=True,
    )
    def _rodar_agora(_n):
        """Enfileira as duas coletas de custo (orçado + executado) na fila do SAP (SP-10).

        A execução real roda no coletor do cliente (transporte diferido — Bloco D);
        localmente o job fica `pendente` até o daemon do cliente processá-lo.
        """
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
                        "enquanto isso, os dados exibidos vêm da carga de exemplo (seed).",
                        className="text-muted")],
            color=cor, dismissable=True, className="py-2",
        )

    @app.callback(
        Output("custo-card-geral", "children"),
        Output("custo-graph", "figure"),
        Output("custo-tabela", "children"),
        Output("custo-breadcrumb", "children"),
        Output("custo-reconc-banner", "children"),
        Output("custo-seed-selo", "children"),
        Input("store-custo-drill", "data"),
        Input("store-custo-centros", "data"),
        Input("store-custo-ano", "data"),
        Input("custo-init", "n_intervals"),
    )
    def _render(drill, centros, ano, _n):
        """Renderiza tudo a partir do estado (nível + centros + ano)."""
        ano = int(ano or 2026)
        centros = centros or None
        drill = drill or {"nivel": "planta"}
        nivel = drill.get("nivel", "planta")

        # Card geral (sempre o GT340 inteiro, respeitando filtro de centro)
        card = _card_geral(L.fetch_geral(ano, centros))

        # Tarja de reconciliação (DS-09) — usa o resumo (número oficial)
        rc = L.reconciliacao(ano)
        if rc.get("por_mes") and not rc["bate"]:
            banner = dbc.Alert(
                [html.I(className="bi bi-exclamation-triangle me-2"),
                 f"Esta coleta não fechou com o SAP (diferença {_brl(rc['diff'])}). "
                 "Confira antes de decidir."],
                color="warning", className="py-2 mb-0",
            )
        else:
            banner = None

        # Selo de seed (DS-09)
        if L.fonte_dos_dados(ano) == "csv":
            selo = dbc.Badge(
                [html.I(className="bi bi-info-circle me-1"), "dados de exemplo (seed)"],
                color="secondary", className="text-wrap",
            )
        else:
            selo = None

        # Nível atual → gráfico + tabela
        tabela = _tabela_lancamentos([])
        if nivel == "planta":
            fig = _fig_barras(L.fetch_grupos(ano, centros), "label", "grupo",
                              titulo="Grupos de manutenção (clique para abrir)")
        elif nivel == "grupo":
            g = drill.get("grupo")
            fig = _fig_barras(L.fetch_contas(g, ano, centros), "conta", "conta",
                              titulo=f"{label_grupo(g)} — contas (clique para abrir)")
        elif nivel == "conta":
            c = drill.get("conta")
            fig = _fig_barras(L.fetch_meses_da_conta(c, ano, centros), "mes", "mes",
                              titulo=f"Conta {c} — meses (clique para abrir o dia)")
            tabela = _tabela_lancamentos(L.fetch_lancamentos(ano, conta=c, centros=centros))
        elif nivel == "mes":
            c, m = drill.get("conta"), drill.get("mes")
            dias = L.fetch_dias_da_conta_mes(c, m, centros)
            fig = _fig_barras(dias, "dia", "dia", com_orcado=False,
                              titulo=f"Conta {c} — {m} — executado por dia")
            tabela = _tabela_lancamentos(L.fetch_lancamentos(ano, conta=c, mes=m, centros=centros))
        else:
            fig = _fig_barras([], "label", "grupo")

        return card, fig, tabela, _breadcrumb(drill), banner, selo
