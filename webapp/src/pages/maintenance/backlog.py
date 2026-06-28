# -*- coding: utf-8 -*-
"""Backlog de Manutenção (/maintenance/backlog) — SDD Backlog.

Painel clean das ordens de manutenção pendentes da BR02 (reproduz o backlog do GAM via
SAP IW39+IW37). Lê o snapshot de `sap_backlog` (Mongo); SAP só na coleta (job backlog).

Layout (DS-08): header (título + Atualizar + Exportar + selo de frescor) → filtros
(accordion) → 5 cards (Total · Preventiva · Corretiva · Melhoria · Matrizes) → tabela.
"""
from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc

# rótulos de exibição dos valores internos
LABEL_DISCIPLINA = {"Mecanica": "Mecânica", "Eletrica": "Elétrica",
                    "NaoClassificado": "Não classificado"}
LABEL_SUBCLASS = {"Corretiva": "Corretiva", "PDCA": "PDCA",
                  "CorretivaProgramada": "Corretiva Programada", "Preditiva": "Preditiva"}

TABLE_COLUMNS = [
    {"name": "Ordem", "id": "ordem"},
    {"name": "Descrição", "id": "descricao"},
    {"name": "Disciplina", "id": "disciplina"},
    {"name": "Centro / Operação", "id": "centro_operacao_0010"},
    {"name": "Início", "id": "data_inicio"},
    {"name": "Linha", "id": "local_pai_nome"},
    {"name": "Conjunto", "id": "local_instalacao"},
]


def _card(titulo, valor_id, cor, breakdown_ids=None):
    """Card de contagem. Se breakdown_ids, mostra as 3 linhas de disciplina embaixo."""
    corpo = [
        html.Div(titulo, className="text-muted small text-uppercase",
                 style={"letterSpacing": "0.5px"}),
        html.Div("—", id=valor_id, className="fw-bold",
                 style={"fontSize": "2rem", "lineHeight": "1.1", "color": cor}),
    ]
    if breakdown_ids:
        linhas = []
        for label, vid in breakdown_ids:
            linhas.append(html.Div([
                html.Span(label + ": ", className="text-muted small"),
                html.Span("—", id=vid, className="small fw-semibold"),
            ]))
        corpo.append(html.Div(linhas, className="mt-2"))
    return dbc.Card(dbc.CardBody(corpo), className="h-100 shadow-sm",
                    style={"borderLeft": f"4px solid {cor}"})


def _viz_row():
    grafo = {"displayModeBar": False}
    return dbc.Row([
        dbc.Col(html.Div([
            dbc.RadioItems(
                id="bk-rosca-mode", value="cat", inline=True, className="small mb-1",
                options=[{"label": "Categoria", "value": "cat"},
                         {"label": "Disciplina", "value": "disc"}]),
            dcc.Loading(dcc.Graph(id="bk-rosca-cat", config=grafo, style={"height": "270px"})),
        ], className="bk-field p-2 rounded bg-white h-100"), md=4, className="mb-3"),
        dbc.Col(html.Div([
            html.Div("Por linha (equipamento-pai)", className="small fw-bold bk-field-label mb-1"),
            dcc.Loading(dcc.Graph(id="bk-rosca-linha", config=grafo, style={"height": "270px"})),
        ], className="bk-field p-2 rounded bg-white h-100"), md=4, className="mb-3"),
        dbc.Col(html.Div([
            html.Div("Insights", className="small fw-bold bk-field-label mb-2"),
            html.Div(id="bk-insights"),
        ], className="bk-field p-3 rounded bg-white h-100"), md=4, className="mb-3"),
    ], className="g-3 mb-2")


def _barras_row():
    return dbc.Row(dbc.Col(html.Div([
        html.Div("Backlog por mês (data de início)", className="small fw-bold bk-field-label mb-1"),
        dcc.Loading(dcc.Graph(id="bk-barras-mes", config={"displayModeBar": False},
                              style={"height": "250px"})),
    ], className="bk-field p-2 rounded bg-white"), width=12), className="mb-3")


NAVY = "#08137C"  # azul escuro do logo Tekmont

# estilos dos checkboxes (contraste em fundo claro) e do campo
_CHK_INPUT = {"width": "1.05rem", "height": "1.05rem", "border": f"1px solid {NAVY}",
              "cursor": "pointer"}
_CHK_CHECKED = {"backgroundColor": NAVY, "borderColor": NAVY}
_CHK_LABEL = {"marginRight": "1rem", "marginLeft": "0.3rem", "cursor": "pointer"}


def _campo(label, control, **col):
    """Campo de filtro rotulado, com contorno navy à esquerda (dá estrutura/contraste)."""
    return dbc.Col(
        html.Div([
            html.Div(label, className="bk-field-label fw-bold mb-2"),
            control,
        ], className="bk-field p-3 rounded bg-white h-100"),
        className="mb-3", **col,
    )


def _chk(cid, options):
    return dbc.Checklist(
        id=cid, options=options, value=[], inline=True,
        input_style=_CHK_INPUT, input_checked_style=_CHK_CHECKED, label_style=_CHK_LABEL,
        className="d-flex flex-wrap",
    )


def _filtros():
    opt_cat = [{"label": c, "value": c} for c in ("Preventiva", "Corretiva", "Melhoria", "Matrizes")]
    opt_disc = [{"label": v, "value": k} for k, v in LABEL_DISCIPLINA.items()]
    opt_sub = [{"label": v, "value": k} for k, v in LABEL_SUBCLASS.items()]

    corpo = html.Div([
        dbc.Row([
            _campo("Categoria", _chk("bk-f-categoria", opt_cat), md=4),
            _campo("Disciplina", _chk("bk-f-disciplina", opt_disc), md=4),
            _campo("Subclassificação", _chk("bk-f-subclass", opt_sub), md=4),
        ], className="g-3"),
        dbc.Row([
            _campo("Linha",
                   dcc.Dropdown(id="bk-f-local-pai", multi=True, options=[],
                                placeholder="Todas as linhas", className="bk-dropdown"),
                   md=4),
            _campo("Período (data de início)",
                   html.Div(
                       dcc.DatePickerRange(
                           id="bk-f-periodo", display_format="DD/MM/YYYY",
                           start_date_placeholder_text="De", end_date_placeholder_text="Até",
                           clearable=True),
                       className="bk-daterange", style={"minWidth": "300px"}),
                   md=4),
            _campo("Busca (nº ordem / descrição)",
                   dbc.Input(id="bk-f-busca", type="text", placeholder="ex: prensa, 5012522", size="sm"),
                   md=4),
        ], className="g-3"),
        html.Div([
            dbc.Button("Aplicar filtros", id="btn-apply-backlog-filters", size="sm",
                       style={"backgroundColor": NAVY, "borderColor": NAVY}),
            dbc.Button("Limpar", id="btn-backlog-clear", color="secondary", outline=True,
                       size="sm", className="ms-2"),
        ], className="d-flex justify-content-end mt-1"),
    ], className="p-3 bg-light")

    return html.Div(
        dbc.Accordion([dbc.AccordionItem(corpo, title="🔎 Filtros")],
                      start_collapsed=True, flush=True, className="bk-filtros-acc"),
        className="mb-3 bk-filtros-panel",
        style={"border": f"1.5px solid {NAVY}", "borderRadius": "0.5rem"},
    )


def _header():
    return dbc.Row([
        dbc.Col(html.H4("Backlog de Manutenção", className="mb-0"), md="auto"),
        dbc.Col(html.Span("—", id="bk-frescor", className="text-muted small"),
                md="auto", className="d-flex align-items-center"),
        dbc.Col([
            dbc.Button("🔄 Atualizar agora", id="btn-backlog-refresh",
                       size="sm", className="me-2 bk-btn-navy-outline"),
            dbc.Button("⬇ Exportar", id="btn-backlog-export",
                       size="sm", className="bk-btn-navy-outline me-2"),
            dbc.Button("📄 Exportar PDF", id="btn-backlog-pdf",
                       size="sm", className="bk-btn-navy-outline"),
        ], className="ms-auto text-end"),
    ], className="align-items-center mb-3 g-2")


def layout():
    return dbc.Container([
        _header(),
        _filtros(),
        _viz_row(),
        _barras_row(),
        dbc.Row(
            dbc.Col(
                dbc.InputGroup([
                    dbc.InputGroupText("Itens por página", className="small"),
                    dbc.Select(
                        id="bk-page-size",
                        options=[{"label": str(n), "value": str(n)} for n in (10, 20, 50, 100)],
                        value="20",
                    ),
                ], size="sm", style={"maxWidth": "220px"}),
                width="auto", className="ms-auto",
            ),
            className="mb-2",
        ),
        dcc.Loading(dash_table.DataTable(
            id="bk-table",
            columns=TABLE_COLUMNS,
            data=[],
            page_size=20,
            sort_action="native",
            filter_action="none",
            style_table={"overflowX": "auto"},
            style_cell={"fontSize": "0.85rem", "padding": "6px",
                        "textAlign": "left", "maxWidth": "260px",
                        "overflow": "hidden", "textOverflow": "ellipsis"},
            style_header={"fontWeight": "600", "backgroundColor": "#f8f9fa"},
        ), type="default"),
        # estado + infra
        dcc.Store(id="store-backlog"),
        dcc.Store(id="bk-last-trigger"),
        dcc.Download(id="download-backlog-xlsx"),
        dcc.Download(id="download-backlog-pdf"),
        dcc.Interval(id="bk-interval-load", interval=400, max_intervals=1),
        dcc.Interval(id="bk-cooldown", interval=15000),  # re-habilita o botão após o cooldown
        html.Div(id="bk-refresh-status", className="small text-muted mt-2"),
    ], fluid=True, className="py-3")
