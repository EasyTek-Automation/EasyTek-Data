# -*- coding: utf-8 -*-
"""A curva de capacidade produtiva do ativo, logo abaixo da linha do tempo.

A linha do tempo responde *em que estado a linha esteve*; esta curva responde *quanto ela
entregou enquanto esteve nesse estado*. São perguntas vizinhas e diferentes: uma linha pode
passar o turno inteiro sem parar e ainda assim entregar 80% do que poderia — e é justamente
essa perda silenciosa que não aparece na faixa de estados.

As duas compartilham o eixo do tempo e a mesma janela, de propósito: a queda da curva cai no
mesmo ponto em que a faixa vira vermelha, e a leitura de uma confirma a da outra. Se um dia
divergirem, o defeito é da projeção — não há caminho alternativo por onde este dado chegue.

Sobre a escala: **0 a 100%, fixa**. Escala que se ajusta ao dado faria uma oscilação de dois
pontos percentuais parecer um desabamento; aqui a altura da curva é comparável entre ativos e
entre cenários.
"""
from __future__ import annotations

from datetime import datetime

import plotly.graph_objects as go
from dash import dcc, html

from src.utils.monitoring.projection import capacidade_agora, capacidade_media

ID_GRAFICO = "mon-capacidade"

# Azul da aplicação, o mesmo dos gráficos de indicadores. A curva **não** usa a régua de cor da
# BR-02: a régua já está na faixa logo acima, e repetir a mesma semântica em dois desenhos
# empilhados faria a cor perder valor de sinal. Aqui o que informa é a altura.
COR_LINHA = "#0d6efd"
COR_AREA = "rgba(13, 110, 253, 0.14)"

# Vermelho de referência de limite — o mesmo tom da régua, usado aqui com outra gramática: é
# uma linha de teto, como a meta num gráfico de indicador, não o estado de uma máquina.
COR_TETO = "#e74c3c"


def figura(pontos) -> go.Figure:
    """A curva da janela, com a faixa de referência do que se considera "no máximo"."""
    fig = go.Figure()

    if pontos:
        # Faixa de referência: acima de 90% a linha está entregando o que dela se espera. Serve
        # de régua para o olho — sem ela, 84% e 94% parecem a mesma altura.
        fig.add_hrect(
            y0=90, y1=100,
            fillcolor="rgba(40, 199, 111, 0.10)",
            line_width=0, layer="below",
        )
        # O teto. A faixa sombreada sozinha era discreta demais para se ler como limite: o olho
        # precisa de uma linha para saber **onde é o máximo** e medir a distância até ela.
        # Tracejada e vermelha porque é referência de limite, não estado de máquina — e fica
        # fora da área da curva, encostada no topo, onde não disputa com o dado.
        fig.add_hline(
            y=100,
            line={"color": COR_TETO, "width": 1.6, "dash": "dash"},
            layer="above",
            annotation_text="capacidade máxima",
            annotation_position="top right",
            annotation_font={"size": 10, "color": COR_TETO},
        )
        fig.add_trace(
            go.Scatter(
                x=[p.instante for p in pontos],
                y=[p.percentual for p in pontos],
                mode="lines",
                line={"color": COR_LINHA, "width": 2, "shape": "spline", "smoothing": 0.6},
                fill="tozeroy",
                fillcolor=COR_AREA,
                hovertemplate="<b>%{y:.0f}%</b> da capacidade<br>%{x|%d/%m %H:%M}<extra></extra>",
                showlegend=False,
            )
        )

    fig.update_layout(
        height=104,
        margin={"l": 8, "r": 8, "t": 14, "b": 28},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel={"font": {"size": 12}},
        xaxis={
            "type": "date",
            "range": [pontos[0].instante, pontos[-1].instante] if pontos else None,
            "showgrid": False,
            "tickformat": "%H:%M",
            "tickfont": {"size": 11, "color": "#6c757d"},
            "linecolor": "#e3e3df",
        },
        yaxis={
            # Escala fixa: comparabilidade entre ativos e entre cenários vale mais do que
            # aproveitar a altura do quadro.
            "range": [0, 112],
            "fixedrange": True,
            "tickvals": [0, 50, 100],
            "ticktext": ["0", "50", "100%"],
            "tickfont": {"size": 10, "color": "#8a93a6"},
            "showgrid": True,
            "gridcolor": "rgba(0,0,0,0.05)",
            "zeroline": False,
        },
    )
    return fig


def bloco(pontos, agora: datetime | None = None) -> html.Div:
    """A curva com os dois números que ela resume: agora e média da janela."""
    atual = capacidade_agora(pontos)
    media = capacidade_media(pontos)

    return html.Div(
        [
            html.Div(
                [
                    html.H6("Capacidade produtiva — últimas 24 horas", className="mon-secao"),
                    html.Div(
                        [
                            html.Span("agora", className="mon-cap-rotulo"),
                            html.Span(f"{atual:.0f}%", className="mon-cap-valor"),
                            html.Span("média da janela", className="mon-cap-rotulo"),
                            html.Span(f"{media:.0f}%", className="mon-cap-valor"),
                        ],
                        className="mon-cap-resumo",
                    ),
                ],
                className="mon-cap-cabecalho",
            ),
            dcc.Graph(
                id=ID_GRAFICO,
                figure=figura(pontos),
                config={"displayModeBar": False},
                className="mon-timeline mon-capacidade",
            ),
        ],
        className="mon-bloco",
    )
