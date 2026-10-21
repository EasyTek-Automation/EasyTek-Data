# -*- coding: utf-8 -*-
"""A linha do tempo de estados do ativo (SP-07).

Uma faixa horizontal contando em que estado o ativo esteve nas últimas horas: verde quando
rodou sem nenhum evento, amarelo quando rodou abaixo do programado ou com alerta aberto,
vermelho quando parou, cinza quando a parada era prevista.

As faixas vêm prontas da projeção — este módulo só desenha. Faixa cuja origem foi filtrada
já não chega aqui, e o período volta a contar como rodando (BR-05).

#### Sobre o "reuso obrigatório" da SP-07

A SP-07 mandava replicar a linha do tempo estilo *evocon* da home. Ela **não existe mais no
código**: sobraram o leitor de dados (`utils/zpp_timeline_loader.py`, hoje sem nenhum
consumidor) e o CSS de animação. O que dava para preservar foi preservado — mesma leitura de
faixa contínua com o tempo no eixo horizontal, mesma altura baixa, sem legenda, detalhe no
hover. As cores são as **da própria tela** (BR-02), não as da paleta antiga: seria confuso a
mesma parada aparecer de um vermelho no desenho e de outro na faixa logo abaixo.
"""
from __future__ import annotations

from datetime import datetime

import plotly.graph_objects as go
from dash import dcc

from src.utils.monitoring.events import Cor

ID_GRAFICO = "mon-timeline"

COR_HEX = {
    Cor.VERDE: "#28c76f",
    Cor.AMARELO: "#f6c026",
    Cor.VERMELHO: "#e74c3c",
    Cor.CINZA: "#d7d7d2",
}


def _hora(momento: datetime) -> str:
    return momento.strftime("%d/%m %H:%M")


def figura(faixas, agora: datetime | None = None) -> go.Figure:
    """A faixa do período, um retângulo por trecho de mesmo estado."""
    fig = go.Figure()

    for faixa in faixas:
        fig.add_trace(
            go.Bar(
                # Num eixo de tempo a largura da barra é medida em milissegundos: passar
                # horas desenha uma faixa de 24 ms — presente no DOM e invisível na tela.
                x=[faixa.horas * 3_600_000],
                y=["estado"],
                base=[faixa.inicio],
                orientation="h",
                marker={"color": COR_HEX[faixa.cor], "line": {"width": 0}},
                hovertemplate=(
                    f"<b>{faixa.rotulo}</b><br>"
                    f"{_hora(faixa.inicio)} → {_hora(faixa.fim)}<br>"
                    f"{faixa.horas:.1f} h<extra></extra>"
                ),
                showlegend=False,
            )
        )

    inicio = faixas[0].inicio if faixas else None
    fim = faixas[-1].fim if faixas else None

    fig.update_layout(
        barmode="stack",
        bargap=0,
        height=118,
        margin={"l": 8, "r": 8, "t": 8, "b": 28},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel={"font": {"size": 12}},
        xaxis={
            "type": "date",
            "range": [inicio, fim] if inicio and fim else None,
            "showgrid": False,
            "tickformat": "%H:%M",
            "tickfont": {"size": 11, "color": "#6c757d"},
            "linecolor": "#e3e3df",
        },
        yaxis={"visible": False, "fixedrange": True},
    )
    return fig


def grafico(faixas, agora: datetime | None = None) -> dcc.Graph:
    return dcc.Graph(
        id=ID_GRAFICO,
        figure=figura(faixas, agora),
        config={"displayModeBar": False, "staticPlot": False},
        className="mon-timeline",
    )
