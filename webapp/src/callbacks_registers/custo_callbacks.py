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

_AZUL = "#0d6efd"
_VERMELHO = "#dc3545"
_CINZA = "#adb5bd"


# --------------------------------------------------------------------------- #
# Formatacao
# --------------------------------------------------------------------------- #
def _brl(v) -> str:
    """Formata numero como moeda BR ('R$ 1.234,56')."""
    if v is None:
        return "—"
    s = f"{v:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return f"R$ {s}"


def _pct(v) -> str:
    """Formata percentual ('90,7%') ou '—' quando indefinido (sem orçamento)."""
    if v is None:
        return "—"
    return f"{v:.1f}".replace(".", ",") + "%"


# --------------------------------------------------------------------------- #
# Componentes
# --------------------------------------------------------------------------- #
def _mini_card(titulo: str, valor: str, cor: str = "dark", sub: str = "") -> dbc.Col:
    """Mini-card de KPI do geral."""
    return dbc.Col(
        dbc.Card(
            dbc.CardBody(
                [
                    html.Small(titulo, className="text-muted d-block"),
                    html.H5(valor, className=f"mb-0 text-{cor}"),
                    html.Small(sub, className="text-muted") if sub else None,
                ]
            ),
            className="h-100",
        ),
    )


def _card_geral(m: dict) -> dbc.Row:
    """Card do GT340: orçado, executado, %, saldo + barra de consumo."""
    cor_pct = "danger" if m["estouro"] else ("warning" if (m["pct"] or 0) >= 90 else "success")
    saldo_cor = "danger" if m["saldo"] < 0 else "success"
    barra = dbc.Progress(
        value=min(m["pct"] or 0, 100),
        label=_pct(m["pct"]),
        color="danger" if m["estouro"] else "primary",
        className="mt-2",
        style={"height": "20px"},
    )
    return dbc.Row(
        [
            _mini_card("Orçado", _brl(m["orcado"])),
            _mini_card("Executado", _brl(m["executado"])),
            _mini_card("% Consumido", _pct(m["pct"]), cor_pct),
            _mini_card("Saldo", _brl(m["saldo"]), saldo_cor,
                       "sem orçamento" if m["sem_orcamento"] else ""),
            dbc.Col(barra, width=12, className="mt-2"),
        ],
        className="g-2",
    )


def _fig_barras(linhas, campo_label, campo_code, com_orcado=True, titulo=""):
    """Grafico de barras do nivel atual. customdata = codigo para o drill."""
    fig = go.Figure()
    if not linhas:
        fig.add_annotation(text="Sem dados para o recorte", showarrow=False,
                           font={"size": 14, "color": _CINZA})
        fig.update_layout(height=340, template="plotly_white",
                          margin={"l": 40, "r": 20, "t": 40, "b": 40}, title=titulo)
        return fig
    labels = [ln[campo_label] for ln in linhas]
    codes = [ln[campo_code] for ln in linhas]
    execs = [ln["executado"] for ln in linhas]
    cores = [_VERMELHO if ln.get("estouro") else _AZUL for ln in linhas]
    if com_orcado:
        fig.add_bar(name="Orçado", x=labels, y=[ln["orcado"] for ln in linhas],
                    marker_color=_CINZA, customdata=codes,
                    hovertemplate="%{x}<br>Orçado: R$ %{y:,.2f}<extra></extra>")
    fig.add_bar(name="Executado", x=labels, y=execs, marker_color=cores, customdata=codes,
                hovertemplate="%{x}<br>Executado: R$ %{y:,.2f}<extra></extra>")
    fig.update_layout(
        height=340, template="plotly_white", barmode="group",
        margin={"l": 40, "r": 20, "t": 40, "b": 60}, title=titulo,
        legend={"orientation": "h", "y": 1.12, "x": 0},
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
        page_size=15,
        sort_action="native",
        style_cell={"fontSize": "0.85rem", "padding": "6px", "textAlign": "left"},
        style_header={"fontWeight": "bold"},
        style_table={"overflowX": "auto"},
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
        Output("btn-custo-rodar-agora", "disabled"),
        Output("custo-rodar-feedback", "children"),
        Input("btn-custo-rodar-agora", "n_clicks"),
        prevent_initial_call=True,
    )
    def _rodar_agora(_n):
        """Placeholder até o transporte SAP (Bloco D): avisa e não dispara nada."""
        aviso = dbc.Alert(
            "A coleta automática do SAP ainda será configurada no cliente (Bloco D). "
            "Por enquanto os dados vêm da carga de exemplo (seed).",
            color="info", dismissable=True, className="py-2",
        )
        return no_update, aviso

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
