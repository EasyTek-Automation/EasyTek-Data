# -*- coding: utf-8 -*-
"""Uma tabela por conjunto com evento aberto ou fechado no período (BR-06, SP-08).

A quantidade de tabelas não é fixa: depende de quantos conjuntos têm algo a contar naquele
momento e naquele escopo. Conjunto sem evento **não gera tabela** — nem vazia, nem com
"nenhum registro". Nenhuma tabela visível é estado válido, não erro.

As tabelas saem na ordem física do conjunto na linha, a mesma do croqui ao lado, para dar
para cruzar tabela e desenho com o olho.
"""
from __future__ import annotations

from datetime import datetime

from dash import html
import dash_bootstrap_components as dbc

from src.components.monitoring.system_text import com_marcacoes
from src.utils.monitoring.events import Cor, Gravidade, nome_do_conjunto

# Cor do cabeçalho de cada tabela: a mesma régua da máquina, para o bloco de texto e o
# desenho contarem a mesma história.
COR_DO_CABECALHO = {
    Gravidade.PARADA: "mon-tabela-vermelho",
    Gravidade.DEGRADACAO: "mon-tabela-amarelo",
    Gravidade.PLANEJADA: "mon-tabela-cinza",
}

COLUNAS = ["Início", "Fim", "Duração", "Tipo", "Descrição"]


def _quando(momento: datetime | None) -> str:
    return momento.strftime("%d/%m %H:%M") if momento else "em curso"


def _duracao(horas: float) -> str:
    total = int(round(horas * 60))
    if total < 60:
        return f"{total} min"
    if total < 60 * 48:
        return f"{total // 60}h{total % 60:02d}"
    return f"{horas / 24:.1f} dias"


def _tabela(conjunto: str, eventos, agora: datetime) -> html.Div:
    pior = min(
        (e.gravidade for e in eventos),
        key=lambda g: [Gravidade.PARADA, Gravidade.DEGRADACAO, Gravidade.PLANEJADA].index(g),
    )
    linhas = [
        html.Tr(
            [
                html.Td(_quando(e.inicio)),
                html.Td(_quando(e.fim)),
                html.Td(_duracao(e.duracao(agora))),
                html.Td(e.tipo),
                html.Td(com_marcacoes(e.descricao), className="mon-tabela-descricao"),
            ]
        )
        for e in eventos
    ]

    return html.Div(
        [
            html.Div(
                nome_do_conjunto().get(conjunto, conjunto),
                className=f"mon-tabela-titulo {COR_DO_CABECALHO[pior]}",
            ),
            dbc.Table(
                [
                    html.Thead(html.Tr([html.Th(c) for c in COLUNAS])),
                    html.Tbody(linhas),
                ],
                bordered=False,
                hover=True,
                size="sm",
                class_name="mon-tabela",
            ),
        ],
        className="mon-tabela-bloco",
    )


def tabelas(por_conjunto: dict, agora: datetime | None = None) -> html.Div:
    """As tabelas do ativo, ou uma frase curta quando não há nenhuma."""
    agora = agora or datetime.now()
    if not por_conjunto:
        return html.Div(
            "Nenhum conjunto deste ativo tem ocorrência no que está selecionado.",
            className="mon-sem-tabela",
        )
    return html.Div(
        [_tabela(chave, eventos, agora) for chave, eventos in por_conjunto.items()],
        className="mon-tabelas",
    )
