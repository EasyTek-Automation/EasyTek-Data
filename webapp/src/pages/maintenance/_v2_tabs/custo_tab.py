"""Aba 'Custo de Manutencao' — layout autocontido (DS-06).

Navegacao IDENTICA a indicators-v2 (grafico em cima + cards embaixo; tabela no nivel
final). Entrada = GRAFICO anual (GERAL + todas as contas, modelo do mockup). Clique
abre um modal drilldown unico: meses (grade de mini-graficos, 1 por mes) -> dias
(grafico do mes + cards de dia) -> contas do dia (grafico + cards de conta) ->
lancamentos (tabela). Botoes Voltar/Fechar. `#modal-custo` espelha `#modal-v2`.

Bloco autocontido (IN-05). So le do Mongo (DS-01). Comportamento em
`callbacks_registers/custo_callbacks.py`.
"""
from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html

ANO_PADRAO = 2026


def _label(txt: str) -> html.Label:
    """Label de toolbar no padrao indicators-v2 (uppercase, espacado, muted)."""
    return html.Label(
        txt,
        className="text-muted fw-semibold d-block mb-1",
        style={"fontSize": "0.72rem", "letterSpacing": "0.4px", "textTransform": "uppercase"},
    )


def build_tab() -> dbc.Tab:
    """Constroi a `dbc.Tab` da feature de custo, para inserir em indicators_v2."""
    return dbc.Tab(
        label="💰 Custo de Manutenção",
        id="tab-v2-custo-component",
        tab_id="tab-v2-custo",
        children=html.Div(
            [
                # Estado proprio (autocontido). Drill por tempo: ano -> mes -> dia -> conta.
                # Filtros persistem na sessão do navegador (sobrevivem a reload/navegação).
                dcc.Store(id="store-custo-ano", data=ANO_PADRAO, storage_type="session"),
                dcc.Store(id="store-custo-contas-sel", data=[], storage_type="session"),
                dcc.Store(id="store-custo-level", data="planta"),
                dcc.Store(id="store-custo-mes", data=None),
                dcc.Store(id="store-custo-dia", data=None),
                dcc.Store(id="store-custo-conta", data=None),
                dcc.Interval(id="custo-init", interval=300, max_intervals=1),

                dcc.Loading(
                    type="circle",
                    color="#0d6efd",
                    children=html.Div(
                        [
                            # ---- Cabecalho + toolbar ----
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.H4(
                                                [html.I(className="bi bi-cash-coin me-2",
                                                        style={"color": "#0d6efd"}),
                                                 "Custo de Manutenção"],
                                                className="mb-0 fw-bold",
                                                style={"letterSpacing": "-0.3px"},
                                            ),
                                            html.Span(
                                                "Orçado × Executado da manutenção (GT340) — "
                                                "clique no gráfico para abrir o detalhamento por mês.",
                                                className="text-muted", style={"fontSize": "0.82rem"},
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        [
                                            html.Div(
                                                [_label("Ano"),
                                                 dcc.Dropdown(
                                                     id="custo-ano-select",
                                                     options=[{"label": str(ANO_PADRAO),
                                                               "value": ANO_PADRAO}],
                                                     value=ANO_PADRAO, clearable=False,
                                                     style={"width": "110px"})],
                                                className="me-3",
                                            ),
                                            html.Div(
                                                [_label("Contas (barras)"),
                                                 # Filtro das BARRAS (contas/classes de custo) —
                                                 # desmarque uma conta p/ tirá-la do gráfico.
                                                 # Colapsável, fechado por padrão.
                                                 dbc.Button(
                                                     "Todas as contas",
                                                     id="custo-contas-toggle",
                                                     color="light", size="sm",
                                                     className="border d-flex align-items-center "
                                                               "justify-content-between",
                                                     style={"minWidth": "260px"}),
                                                 dbc.Collapse(
                                                     dcc.Dropdown(
                                                         id="custo-conta-filter", options=[],
                                                         value=[], multi=True,
                                                         placeholder="Todas as contas",
                                                         className="mt-1",
                                                         style={"minWidth": "260px"}),
                                                     id="custo-contas-collapse", is_open=False)],
                                                className="me-3 d-flex flex-column",
                                            ),
                                            html.Div(
                                                [_label("Coleta"),
                                                 dbc.Button(
                                                     [html.I(className="bi bi-arrow-repeat me-2"),
                                                      "Rodar agora"],
                                                     id="btn-custo-rodar-agora",
                                                     color="primary", outline=True, size="sm")],
                                            ),
                                            # Controle isolado (não toca nos grupos acima): fixa a
                                            # seleção atual de contas para o slide de Custos do telão
                                            # (modo apresentação da home). Persiste no Mongo.
                                            html.Div(
                                                [_label("Telão"),
                                                 dbc.Button(
                                                     [html.I(className="bi bi-pin-angle me-2"),
                                                      "Fixar no telão"],
                                                     id="btn-custo-fixar-telao",
                                                     color="secondary", outline=True, size="sm"),
                                                 html.Small(id="custo-fixar-telao-feedback",
                                                            className="text-muted ms-2")],
                                                className="d-flex align-items-end",
                                            ),
                                        ],
                                        className="d-flex align-items-end flex-wrap gap-2",
                                    ),
                                ],
                                className="d-flex justify-content-between align-items-end mb-3 flex-wrap gap-3",
                            ),

                            html.Div(id="custo-seed-selo", className="mb-2"),
                            html.Div(id="custo-rodar-feedback"),
                            html.Div(id="custo-reconc-banner", className="mb-2"),

                            # ---- Gráfico de ENTRADA (anual: GERAL + todas as contas) ----
                            dbc.Card(
                                [
                                    dbc.CardHeader(
                                        html.H6(
                                            [html.I(className="bi bi-bar-chart-line me-2"),
                                             "Realizado por conta (% do orçado, ano) — clique para abrir os meses"],
                                            className="mb-0 fw-bold",
                                        ),
                                        className="py-2",
                                    ),
                                    dbc.CardBody(
                                        [
                                            dbc.Row(
                                                [
                                                    # Rosca (esquerda): distribuição por equipamento
                                                    dbc.Col(
                                                        dcc.Graph(
                                                            id="custo-graph-rosca",
                                                            config={"displayModeBar": False,
                                                                    "responsive": True},
                                                            style={"height": "460px",
                                                                   "width": "100%",
                                                                   "cursor": "pointer"},
                                                        ),
                                                        xs=12, md=4,
                                                    ),
                                                    # Barras (direita): realizado por conta
                                                    dbc.Col(
                                                        html.Div(
                                                            dcc.Graph(
                                                                id="custo-graph-entry",
                                                                config={"displayModeBar": False,
                                                                        "responsive": True,
                                                                        "doubleClick": False,
                                                                        "scrollZoom": False},
                                                                style={"height": "460px",
                                                                       "width": "100%"},
                                                            ),
                                                            id="custo-entry-wrap",
                                                            n_clicks=0,
                                                            style={"cursor": "pointer"},
                                                        ),
                                                        xs=12, md=8,
                                                    ),
                                                ],
                                                className="g-2 align-items-center",
                                            ),
                                            # Filtro por valor (slider duplo) — linha nova, fora do
                                            # wrapper clicável p/ não disparar o modal ao arrastar.
                                            html.Div(
                                                [
                                                    html.Label(
                                                        "Filtrar contas por valor executado (R$)",
                                                        className="text-muted small mb-2 d-block",
                                                    ),
                                                    dcc.RangeSlider(
                                                        id="custo-slider-geral",
                                                        min=0, max=1, value=[0, 1], step=1,
                                                        allowCross=False,
                                                        tooltip={"placement": "top",
                                                                 "always_visible": True,
                                                                 "transform": "custoRsLog"},
                                                    ),
                                                ],
                                                className="px-3 pt-2 pb-1",
                                            ),
                                        ],
                                        className="p-2",
                                    ),
                                ],
                                className="shadow-sm indicator-v2-card-md",
                                style={"borderTop": "4px solid #0d6efd"},
                            ),
                        ],
                        className="p-3",
                    ),
                ),

                # ---- Modal drilldown (espelha #modal-v2) ----
                dbc.Modal(
                    [
                        dbc.ModalHeader(dbc.ModalTitle(id="modal-custo-title"),
                                        close_button=True),
                        dbc.ModalBody(
                            [
                                html.Div(id="modal-custo-breadcrumb", className="mb-3"),
                                # Filtro por valor (slider duplo) do drill — escondido nos níveis
                                # sem barras (lançamentos). Mesma mecânica do slider do anual.
                                html.Div(
                                    [
                                        html.Label(
                                            "Filtrar contas por valor executado (R$)",
                                            className="text-muted small mb-2 d-block",
                                        ),
                                        dcc.RangeSlider(
                                            id="custo-slider-modal",
                                            min=0, max=1, value=[0, 1], step=1,
                                            allowCross=False,
                                            tooltip={"placement": "top",
                                                     "always_visible": True,
                                                     "transform": "custoRsLog"},
                                        ),
                                    ],
                                    id="custo-slider-modal-wrap",
                                    className="px-3 mb-3",
                                    style={"display": "none"},
                                ),
                                dcc.Loading(
                                    type="circle", color="#0d6efd", delay_show=120,
                                    children=html.Div(id="modal-custo-content"),
                                ),
                            ]
                        ),
                        dbc.ModalFooter(
                            [
                                dbc.Button([html.I(className="bi bi-arrow-left me-1"), "Voltar"],
                                           id="btn-custo-back", color="secondary", outline=True),
                                dbc.Button("Fechar", id="btn-custo-close",
                                           color="primary", className="ms-auto"),
                            ]
                        ),
                    ],
                    id="modal-custo", size="xl", is_open=False, scrollable=True,
                    fullscreen="lg-down",
                ),

                # ---- Modal da rosca (clique numa fatia → o que compõe o equipamento) ----
                # Isolado do #modal-custo (drill das contas) — dimensão diferente (centro
                # de custo, não conta). Resumos colapsáveis (por conta / por centro) +
                # filtros + tabela de lançamentos da fatia. Estrutura estática: a fatia
                # clicada vai p/ `store-rosca-centros` e a tabela reage aos filtros.
                dbc.Modal(
                    [
                        dbc.ModalHeader(dbc.ModalTitle(id="modal-rosca-title"),
                                        close_button=True),
                        dbc.ModalBody(
                            [
                                dcc.Store(id="store-rosca-centros"),

                                # --- Resumo "Por conta" (colapsável, fecha por padrão) ---
                                dbc.Button(
                                    [html.Span([html.I(className="bi bi-tags me-2"),
                                                "Por conta"], className="fw-semibold"),
                                     html.I(id="chev-rosca-conta",
                                            className="bi bi-chevron-down")],
                                    id="toggle-rosca-conta", color="light", n_clicks=0,
                                    className="border w-100 d-flex align-items-center "
                                              "justify-content-between mb-1",
                                ),
                                dbc.Collapse(
                                    dcc.Loading(html.Div(id="modal-rosca-resumo-conta"),
                                                type="circle", color="#34568b"),
                                    id="collapse-rosca-conta", is_open=False,
                                    className="mb-2",
                                ),

                                # --- Resumo "Por centro" (colapsável, fecha por padrão) ---
                                dbc.Button(
                                    [html.Span([html.I(className="bi bi-diagram-3 me-2"),
                                                "Por centro de custo"], className="fw-semibold"),
                                     html.I(id="chev-rosca-centro",
                                            className="bi bi-chevron-down")],
                                    id="toggle-rosca-centro", color="light", n_clicks=0,
                                    className="border w-100 d-flex align-items-center "
                                              "justify-content-between mb-1",
                                ),
                                dbc.Collapse(
                                    dcc.Loading(html.Div(id="modal-rosca-resumo-centro"),
                                                type="circle", color="#34568b"),
                                    id="collapse-rosca-centro", is_open=False,
                                    className="mb-3",
                                ),

                                html.Hr(className="my-2"),

                                # --- Filtros da tabela de lançamentos ---
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            [_label("Conta"),
                                             dcc.Dropdown(id="rosca-f-conta", multi=True,
                                                          options=[], value=[],
                                                          placeholder="Todas")],
                                            xs=12, md=5),
                                        dbc.Col(
                                            [_label("Centro"),
                                             dcc.Dropdown(id="rosca-f-centro", multi=True,
                                                          options=[], value=[],
                                                          placeholder="Todos")],
                                            xs=12, md=3),
                                        dbc.Col(
                                            [_label("Buscar na descrição"),
                                             dcc.Input(id="rosca-f-busca", type="text",
                                                       debounce=True, value="",
                                                       placeholder="ex: inversor",
                                                       className="form-control")],
                                            xs=12, md=2),
                                        dbc.Col(
                                            [_label("Valor (R$)"),
                                             dcc.RangeSlider(id="rosca-f-valor",
                                                             min=0, max=1, value=[0, 1],
                                                             step=1, allowCross=False,
                                                             tooltip={"placement": "top",
                                                                      "always_visible": False})],
                                            xs=12, md=2),
                                    ],
                                    className="g-2 align-items-start mb-3",
                                ),

                                # --- Tabela de lançamentos (reage aos filtros) ---
                                dcc.Loading(
                                    type="circle", color="#34568b", delay_show=120,
                                    children=html.Div(id="modal-rosca-tabela"),
                                ),
                            ]
                        ),
                        dbc.ModalFooter(
                            dbc.Button("Fechar", id="btn-rosca-close",
                                       color="primary", className="ms-auto"),
                        ),
                    ],
                    id="modal-rosca", size="xl", is_open=False, scrollable=True,
                    fullscreen="lg-down",
                ),
            ],
        ),
    )
