"""Aba 'Custo de Manutencao' — layout autocontido (DS-06).

Navegacao IDENTICA a indicators-v2: cards clicaveis no topo (aqui, os 4 GRUPOS) que
abrem um **modal drilldown** unico (XL). Dentro do modal: contas -> meses -> dias ->
lancamentos, com mini-cards clicaveis por nivel (inclusive **cards de mes**),
breadcrumb pill e botoes Voltar/Fechar. Mesma mecanica, mesmo visual (classes
`indicator-v2-card`, `#modal-custo` espelha `#modal-v2` via assets/custo.css).

Bloco autocontido (IN-05). So le do Mongo (DS-01). Comportamento em
`callbacks_registers/custo_callbacks.py`.
"""
from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html

ANO_PADRAO = 2026
_CINZA = "#6c757d"


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
                # Estado proprio (autocontido) — espelha os stores de drill da v2
                dcc.Store(id="store-custo-ano", data=ANO_PADRAO),
                dcc.Store(id="store-custo-centros", data=[]),
                dcc.Store(id="store-custo-level", data="planta"),
                dcc.Store(id="store-custo-grupo", data=None),
                dcc.Store(id="store-custo-conta", data=None),
                dcc.Store(id="store-custo-mes", data=None),
                dcc.Store(id="store-custo-dia", data=None),
                dcc.Interval(id="custo-init", interval=300, max_intervals=1),

                dcc.Loading(
                    type="circle",
                    color="#0d6efd",
                    children=html.Div(
                        [
                            # ---- Cabecalho ----
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
                                                "clique num grupo para abrir o detalhamento.",
                                                className="text-muted",
                                                style={"fontSize": "0.82rem"},
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
                                                [_label("Centro de custo"),
                                                 dcc.Dropdown(
                                                     id="custo-centro-filter",
                                                     options=[], value=[], multi=True,
                                                     placeholder="Todos os centros",
                                                     style={"minWidth": "240px"})],
                                                className="me-3",
                                            ),
                                            html.Div(
                                                [_label("Coleta"),
                                                 dbc.Button(
                                                     [html.I(className="bi bi-arrow-repeat me-2"),
                                                      "Rodar agora"],
                                                     id="btn-custo-rodar-agora",
                                                     color="primary", outline=True, size="sm")],
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

                            # ---- Cards KPI do geral (resumo, não-clicável) ----
                            html.Div(id="custo-card-geral", className="mb-3"),

                            # ---- Cards dos GRUPOS (clicáveis → abrem o modal) ----
                            html.H6(
                                "Grupos de manutenção (clique para abrir)",
                                className="v2-section-h6 text-muted",
                            ),
                            html.Div(id="custo-grupos-cards"),
                        ],
                        className="p-3",
                    ),
                ),

                # ---- Modal drilldown (espelha #modal-v2) ----
                dbc.Modal(
                    [
                        dbc.ModalHeader(
                            dbc.ModalTitle(id="modal-custo-title"),
                            close_button=True,
                        ),
                        dbc.ModalBody(
                            [
                                html.Div(id="modal-custo-breadcrumb", className="mb-3"),
                                dcc.Loading(
                                    type="circle", color="#0d6efd", delay_show=120,
                                    children=html.Div(id="modal-custo-content"),
                                ),
                            ]
                        ),
                        dbc.ModalFooter(
                            [
                                dbc.Button(
                                    [html.I(className="bi bi-arrow-left me-1"), "Voltar"],
                                    id="btn-custo-back", color="secondary", outline=True,
                                ),
                                dbc.Button("Fechar", id="btn-custo-close",
                                           color="primary", className="ms-auto"),
                            ]
                        ),
                    ],
                    id="modal-custo",
                    size="xl",
                    is_open=False,
                    scrollable=True,
                    fullscreen="lg-down",
                ),
            ],
        ),
    )
