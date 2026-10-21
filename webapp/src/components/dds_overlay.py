# src/components/dds_overlay.py

"""
Overlay do DDS (Diálogo Diário de Segurança) — componente global.

Vive no layout principal (`index.py`), não numa página: a tecla F9 chama o DDS
de qualquer tela do sistema. O conteúdo é sempre o mesmo — o guia em 6 passos,
o painel de condução (dias sem acidente · passo da vez · cronômetros) e o
gatilho invisível que o atalho aciona.

A arte é injetada como SVG vivo por `assets/home_dds.js`, que acende o card do
passo da vez, reescreve os minutos e desenha a barra de tempo dentro do card.
Quando o DDS abre estando na Visão Geral da Manutenção, o próprio JS pausa o
carrossel — e o retoma ao sair, se foi ele quem pausou.
"""

from dash import dcc, html


def build_dds_overlay():
    """Monta o overlay do DDS + stores + gatilho do atalho (F9)."""
    return html.Div(
        [
            # Estado do overlay e config vinda do banco (dias sem acidente, ritmo)
            dcc.Store(id="store-home-dds", storage_type="memory", data=False),
            dcc.Store(id="store-dds-cfg", storage_type="memory"),

            # Gatilho invisível: a tecla F9 e o botão "DDS" da Visão Geral clicam
            # AQUI. Assim existe um caminho único de estado, disponível em toda
            # tela, sem depender de nenhum botão de página.
            html.Button(id="btn-dds-trigger", n_clicks=0,
                        style={"display": "none"}, **{"aria-hidden": "true"}),

            html.Div(
                [
                    html.Button(html.I(className="bi bi-x-lg"),
                                id="btn-home-dds-close", className="home-dds-close",
                                n_clicks=0, title="Fechar (F9 ou Esc)"),

                    # Palco da arte — o SVG entra aqui via fetch (mesma origem).
                    html.Div(id="home-dds-art", className="home-dds-art"),

                    # Painel de condução: dias sem acidente · passo da vez · tempos
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div("DIAS SEM ACIDENTE", className="home-dds-safe-label"),
                                    html.Div("—", id="home-dds-safe-days",
                                             className="home-dds-safe-days"),
                                    html.Div(id="home-dds-safe-record",
                                             className="home-dds-safe-record"),
                                ],
                                className="home-dds-safe",
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        [html.Span("1", id="home-dds-step-num"),
                                         html.Span("/6", className="home-dds-step-total"),
                                         html.Span("RELEMBRAR", id="home-dds-step-name",
                                                   className="home-dds-step-name")],
                                        className="home-dds-step",
                                    ),
                                    html.Div("1:00", id="home-dds-step-clock",
                                             className="home-dds-step-clock"),
                                    html.Div(
                                        [
                                            html.Button("−", id="btn-dds-menos",
                                                        className="home-dds-adj", title="Menos 1 min neste passo"),
                                            html.Span("1 min", id="home-dds-step-budget",
                                                      className="home-dds-budget"),
                                            html.Button("+", id="btn-dds-mais",
                                                        className="home-dds-adj", title="Mais 1 min neste passo"),
                                        ],
                                        className="home-dds-adj-box",
                                    ),
                                ],
                                className="home-dds-center",
                            ),
                            html.Div(
                                [
                                    html.Div("TOTAL", className="home-dds-total-label"),
                                    html.Div("0:00", id="home-dds-total-clock",
                                             className="home-dds-total-clock"),
                                    html.Div(
                                        [
                                            html.Button(html.I(className="bi bi-pause-fill"),
                                                        id="btn-dds-pausa", className="home-dds-ctl",
                                                        title="Pausar/retomar o cronômetro (P)"),
                                            html.Button(html.I(className="bi bi-arrow-counterclockwise"),
                                                        id="btn-dds-reset", className="home-dds-ctl",
                                                        title="Recomeçar o DDS (R)"),
                                        ],
                                        className="home-dds-ctl-box",
                                    ),
                                ],
                                className="home-dds-right",
                            ),
                        ],
                        className="home-dds-hud",
                    ),

                    html.Div("Espaço avança o passo · P pausa · R recomeça · F9 ou Esc sai",
                             className="home-dds-hint"),
                ],
                id="home-dds-overlay", className="home-dds-overlay",
            ),
        ]
    )
