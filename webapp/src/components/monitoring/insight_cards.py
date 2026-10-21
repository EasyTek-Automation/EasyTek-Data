# -*- coding: utf-8 -*-
"""A faixa de cards do ativo (SP-09).

Cada card traz uma frase curta com um rótulo. Card sem dado no escopo filtrado não aparece —
a faixa encolhe, não fica com buraco. Isso já vem resolvido da projeção: os cards são
calculados sobre a lista de eventos já recortada.

**Nenhum card é clicável e nenhum leva a ação.** A tela parece supervisório; se tiver botão,
alguém aperta — e o dado é ilustrativo.
"""
from __future__ import annotations

from dash import html
import dash_bootstrap_components as dbc

from src.utils.monitoring.events import Origem

ETIQUETA_DA_ORIGEM = {
    Origem.PRODUCAO: "Produção",
    Origem.MANUTENCAO: "Manutenção",
}


def _card(card) -> dbc.Card:
    # A etiqueta de origem saiu em 2026-08-05: com a tela dedicada à manutenção, todo card
    # dizia "Manutenção" e a etiqueta virou ruído repetido quatro vezes na mesma faixa. O
    # mapa fica no módulo — devolver a etiqueta é uma linha, se a produção voltar à tela.
    rodape = None
    # A faixa no topo do card usa a mesma régua da máquina (BR-02): quem bate o olho lê a
    # gravidade pela cor antes de ler o texto, como nos cards da home e da indicators-v2.
    tom = f" mon-card-{card.cor.value}" if card.cor else ""
    return dbc.Card(
        dbc.CardBody(
            [
                html.Div(card.rotulo, className="mon-card-rotulo"),
                html.Div(card.valor, className="mon-card-valor"),
                rodape,
            ]
        ),
        class_name="mon-card" + tom,
    )


def faixa(cards) -> html.Div:
    """Os cards lado a lado, na ordem em que a projeção os devolveu."""
    return html.Div([_card(c) for c in cards], className="mon-cards")
