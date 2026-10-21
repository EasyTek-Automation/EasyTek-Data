# src/pages/maintenance/dds.py

"""
Página de Configuração do DDS (Diálogo Diário de Segurança)
============================================================

Alimenta o painel do DDS exibido em tela cheia na Visão Geral da Manutenção
(tecla F9). Duas coisas se configuram aqui:

1. **Segurança** — o registro dos acidentes. O telão mostra há quantos dias a
   planta está sem acidente e qual o recorde; os dois números saem do histórico
   registrado nesta tela, não de um campo digitado à mão.

2. **Ritmo do DDS** — quantos minutos cada um dos 6 passos do guia deve durar.
   É o tempo que o telão cobra durante a condução.

Restrita a administradores (nível 3): registrar um acidente zera o contador
exibido para toda a planta.

Persistência: MongoDB — `dds_acidentes` (histórico) e `dds_config` (tempos).
"""

from datetime import date

from dash import html, dcc
import dash_bootstrap_components as dbc

from src.utils import dds_data

# Nomes dos 6 passos, na ordem da arte do guia.
PASSOS = ["Relembrar", "Conectar", "Provocar", "Construir", "Aplicar", "Comprometer"]


def _card_seguranca():
    """Bloco de segurança: números do telão + registro de acidente + histórico."""
    return dbc.Card(
        [
            dbc.CardHeader(
                html.H4([html.I(className="bi bi-shield-check me-2"),
                         "Segurança — dias sem acidente"], className="mb-0")
            ),
            dbc.CardBody(
                [
                    html.P(
                        "Os dois números que aparecem no telão saem daqui. Ao registrar "
                        "um acidente, o contador de dias volta a zero na mesma hora.",
                        className="text-muted mb-3",
                    ),

                    # Números atuais (preenchidos pelo callback)
                    html.Div(id="dds-cfg-numeros", className="mb-4"),

                    html.Hr(),

                    html.H6([html.I(className="bi bi-plus-circle me-2"),
                             "Registrar acidente"], className="mb-3"),
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Label("Data do acidente"),
                                    dcc.DatePickerSingle(
                                        id="dds-cfg-data",
                                        display_format="DD/MM/YYYY",
                                        placeholder="dd/mm/aaaa",
                                        max_date_allowed=date.today(),
                                        className="d-block",
                                    ),
                                    html.Small("Não aceita data futura.",
                                               className="text-muted"),
                                ],
                                md=3,
                            ),
                            dbc.Col(
                                [
                                    dbc.Label("Observação (opcional)"),
                                    dbc.Input(id="dds-cfg-obs", type="text",
                                              placeholder="Ex: prensa 2 — corte na mão, sem afastamento",
                                              maxLength=200),
                                    html.Small("Fica no histórico, não vai para o telão.",
                                               className="text-muted"),
                                ],
                                md=6,
                            ),
                            dbc.Col(
                                dbc.Button([html.I(className="bi bi-save me-2"), "Registrar"],
                                           id="btn-dds-cfg-registrar", color="danger",
                                           className="w-100", n_clicks=0),
                                md=3, className="d-flex align-items-end",
                            ),
                        ],
                        className="g-3 mb-3",
                    ),
                    html.Div(id="dds-cfg-msg-acidente"),

                    html.Hr(className="mt-4"),
                    html.H6([html.I(className="bi bi-clock-history me-2"),
                             "Histórico"], className="mb-3"),
                    html.Div(id="dds-cfg-historico"),
                ]
            ),
        ],
        className="shadow-sm mb-4",
        style={"borderTop": "4px solid #dc3545"},
    )


def _card_tempos():
    """Bloco de ritmo: minutos de cada um dos 6 passos."""
    return dbc.Card(
        [
            dbc.CardHeader(
                html.H4([html.I(className="bi bi-stopwatch me-2"),
                         "Ritmo do DDS — minutos por passo"], className="mb-0")
            ),
            dbc.CardBody(
                [
                    html.P(
                        "Tempo que o telão cobra em cada passo do guia. Quem estiver "
                        "conduzindo ainda pode esticar ou encurtar um passo na hora, com "
                        "os botões − e +, sem alterar o que está salvo aqui.",
                        className="text-muted mb-3",
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Label([html.Span(f"{i + 1:02d} ",
                                                         className="text-muted"), nome]),
                                    dbc.InputGroup(
                                        [
                                            dbc.Input(id=f"dds-cfg-passo-{i}", type="number",
                                                      min=1, max=60, step=1),
                                            dbc.InputGroupText("min"),
                                        ]
                                    ),
                                ],
                                xs=6, md=2,
                            )
                            for i, nome in enumerate(PASSOS)
                        ],
                        className="g-3 mb-3",
                    ),
                    html.Div(
                        [
                            dbc.Button([html.I(className="bi bi-save me-2"), "Salvar tempos"],
                                       id="btn-dds-cfg-salvar", color="primary", n_clicks=0),
                            dbc.Button([html.I(className="bi bi-arrow-counterclockwise me-2"),
                                        "Voltar ao padrão (1·2·2·2·2·1)"],
                                       id="btn-dds-cfg-padrao", color="secondary",
                                       outline=True, n_clicks=0, className="ms-2"),
                            html.Span(id="dds-cfg-total", className="ms-3 text-muted"),
                        ],
                        className="d-flex align-items-center flex-wrap",
                    ),
                    html.Div(id="dds-cfg-msg-tempos", className="mt-3"),
                ]
            ),
        ],
        className="shadow-sm",
        style={"borderTop": "4px solid #0d6efd"},
    )


def layout():
    """Layout da configuração do DDS."""
    return dbc.Container(
        [
            # Recarrega os blocos após cada gravação, sem sair da página.
            dcc.Store(id="dds-cfg-refresh", data=0),

            dbc.Row(
                dbc.Col(
                    [
                        html.H2([html.I(className="bi bi-megaphone me-3"),
                                 "Diálogo Diário de Segurança (DDS)"], className="mb-1"),
                        html.P(
                            [
                                "Configura o painel que aparece em tela cheia na ",
                                html.A("Visão Geral da Manutenção",
                                       href="/maintenance/overview", className="text-decoration-none"),
                                " pela tecla ", html.Kbd("F9"), ".",
                            ],
                            className="text-muted",
                        ),
                        dbc.Alert(
                            [html.I(className="bi bi-shield-lock me-2"),
                             "Página restrita a administradores (Nível 3) — registrar um "
                             "acidente zera o contador exibido para toda a planta."],
                            color="warning", className="mb-4",
                        ),
                    ]
                )
            ),

            _card_seguranca(),
            _card_tempos(),
        ],
        fluid=True,
        className="p-3",
    )
