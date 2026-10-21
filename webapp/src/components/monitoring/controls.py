# -*- coding: utf-8 -*-
"""O controle da tela e as legendas (SP-02, SP-03, SP-04).

O mesmo controle serve a planta e a página do ativo: é a mesma pergunta nas duas telas.

O filtro por origem — "ver tudo / só produção / só manutenção" — saiu em 2026-08-05, quando a
tela passou a ser de manutenção: com todo evento vindo da mesma origem, o recorte não recortava
nada e o controle só ocupava espaço prometendo uma escolha vazia.
"""
from __future__ import annotations

from dash import dcc, html
import dash_bootstrap_components as dbc

from src.utils.monitoring.events import Cor, Escopo
from src.utils.monitoring.scenarios import CENARIOS

ID_CENARIO = "mon-cenario"
ID_TELA_CHEIA = "btn-mon-fullscreen"
ID_TEMA = "btn-mon-tema"

ROTULO_DO_ESCOPO = {
    Escopo.TUDO: "Ver tudo",
    Escopo.PRODUCAO: "Só Produção",
    Escopo.MANUTENCAO: "Só Manutenção",
}

SIGNIFICADO_DA_COR = [
    (Cor.VERDE, "Rodando", "Sem nenhum evento aberto"),
    (Cor.AMARELO, "Atenção", "Alerta preditivo aberto — a máquina roda, mas com sinal"),
    (Cor.VERMELHO, "Parado", "Linha parada por avaria ou por corretiva em execução"),
    (Cor.CINZA, "Parada prevista", "Preventiva programada ou turno sem programação"),
]

# A moldura da linha (BR-03) diz *onde olhar*; a cor da máquina diz *o quê*. São duas
# perguntas diferentes, e por isso duas legendas — a de cor fala do conjunto, esta fala do
# ativo inteiro. A forma faz parte do significado: o tracejado marca o que estava previsto.
SIGNIFICADO_DA_MOLDURA = [
    (Cor.VERMELHO, "Linha parada", "Moldura vermelha piscando — tem conjunto parado agora"),
    (Cor.AMARELO, "Linha em atenção", "Moldura amarela fixa — tem conjunto com alerta aberto"),
    (Cor.CINZA, "Linha em parada prevista", "Moldura cinza tracejada — programado, não é alarme"),
    (None, "Sem moldura", "Linha rodando — nada aberto nela"),
]


def seletor_de_cenario(valor: str) -> html.Div:
    """Os retratos mockados da fábrica, em ordem crescente de severidade."""
    return html.Div(
        [
            html.Label("Cenário", htmlFor=ID_CENARIO, className="mon-control-label"),
            dcc.Dropdown(
                id=ID_CENARIO,
                options=[{"label": c.rotulo, "value": c.chave} for c in CENARIOS],
                value=valor,
                clearable=False,
                searchable=False,
                className="mon-cenario",
            ),
        ],
        className="mon-control",
    )


def legenda(escopo: Escopo, com_molduras: bool = True) -> html.Div:
    """As quatro cores da máquina, as molduras da linha e o escopo em vigor.

    `com_molduras=False` na página do ativo: lá a tela **é** a linha, e nenhuma moldura é
    desenhada. Explicar uma marcação que não aparece seria descrever coisa inexistente.

    O escopo deixou de aparecer aqui junto com o filtro que o produzia: sem recorte por
    origem, verde quer dizer "sem evento aberto", sem condição a declarar.

    A legenda das molduras vem numa **linha própria**, depois da de cores: são duas perguntas
    distintas (*o que a máquina está fazendo* × *em qual linha olhar*) e misturá-las num
    parágrafo só faria a pessoa ler treze itens sem saber que mudam de assunto no meio.
    """
    itens = [
        html.Div(
            [
                html.Span(className=f"mon-chip mon-chip-{cor.value}"),
                html.Span(titulo, className="mon-chip-titulo"),
                html.Span(explicacao, className="mon-chip-texto"),
            ],
            className="mon-legenda-item",
        )
        for cor, titulo, explicacao in SIGNIFICADO_DA_COR
    ]
    if not com_molduras:
        return html.Div(itens, className="mon-legenda")

    molduras = [
        html.Span("Moldura da linha:", className="mon-legenda-rotulo"),
    ] + [
        html.Div(
            [
                html.Span(
                    className="mon-halo mon-halo-"
                    + (cor.value if cor is not None else "nenhuma")
                ),
                html.Span(titulo, className="mon-chip-titulo"),
                html.Span(explicacao, className="mon-chip-texto"),
            ],
            className="mon-legenda-item",
        )
        for cor, titulo, explicacao in SIGNIFICADO_DA_MOLDURA
    ]

    return html.Div(
        [
            html.Div(itens, className="mon-legenda"),
            html.Div(molduras, className="mon-legenda mon-legenda-molduras"),
        ]
    )


def legenda_compacta() -> html.Div:
    """A mesma legenda, sem as frases de explicação — para a faixa de tela cheia.

    Em tela cheia o que se está pedindo é a fábrica grande: cada linha de texto ali sai do
    tamanho do desenho. Por isso só o chip e o nome do estado, numa faixa horizontal — as
    frases longas ficam na tela normal, onde há espaço para elas.

    Cores e molduras vêm separadas por um traço vertical: continuam sendo duas perguntas
    diferentes, mesmo comprimidas na mesma linha.
    """
    cores = [
        html.Div(
            [
                html.Span(className=f"mon-chip mon-chip-{cor.value}"),
                html.Span(titulo, className="mon-chip-titulo"),
            ],
            className="mon-legenda-item",
        )
        for cor, titulo, _ in SIGNIFICADO_DA_COR
    ]
    molduras = [
        html.Div(
            [
                html.Span(
                    className="mon-halo mon-halo-"
                    + (cor.value if cor is not None else "nenhuma")
                ),
                html.Span(titulo, className="mon-chip-titulo"),
            ],
            className="mon-legenda-item",
        )
        for cor, titulo, _ in SIGNIFICADO_DA_MOLDURA
        if cor is not None  # "sem moldura" não tem o que mostrar comprimido
    ]
    return html.Div(
        cores
        + [html.Span("Moldura:", className="mon-legenda-rotulo mon-fs-sep-legenda")]
        + molduras,
        className="mon-legenda mon-legenda-compacta",
    )


def botao_tela_cheia() -> dbc.Button:
    """Põe o desenho em tela cheia, como o modo apresentação da home.

    Fica isolado à direita, fora dos dois agrupamentos de controle — a barra que já
    existia não muda de forma por causa dele.
    """
    return dbc.Button(
        [html.I(className="bi bi-arrows-fullscreen me-2"), "Tela cheia"],
        id=ID_TELA_CHEIA,
        color="dark",
        outline=True,
        size="sm",
        n_clicks=0,
        title="Mostrar a planta em tela cheia (Esc para sair)",
        class_name="mon-tela-cheia",
    )


def botao_de_tema(id_do_botao: str = ID_TEMA) -> dbc.Button:
    """Alterna entre o painel claro e o escuro.

    Sala de controle costuma ser escura — o fundo apagado tira a concorrência da luz branca e
    deixa as quatro cores de estado falarem sozinhas. Mas a aplicação inteira é clara, e impor
    o escuro faria esta tela destoar de todas as outras. Por isso é escolha de quem está
    olhando, e não do projeto: o botão fica isolado à direita, ao lado do de tela cheia, e a
    escolha acompanha a pessoa na próxima visita.

    A troca é feita no navegador (`assets/monitoring_tema.js`), não por callback: o botão
    existe em dois lugares — a barra de controles e a faixa de tela cheia — e um callback do
    Dash exigiria ids fixos nos dois, que nem sempre estão na tela ao mesmo tempo. O
    navegador resolve isso lendo a classe, e ainda mantém os dois rótulos sincronizados.
    """
    return dbc.Button(
        [
            html.I(className="bi bi-moon-stars me-2 mon-tema-icone"),
            html.Span("Painel escuro", className="mon-tema-texto"),
        ],
        id=id_do_botao,
        color="dark",
        outline=True,
        size="sm",
        n_clicks=0,
        title="Alternar entre o painel claro e o escuro",
        class_name="mon-tema",
    )


def barra_de_controles(cenario: str, escopo: str, tela_cheia: bool = False,
                       tema: bool = True) -> html.Div:
    """Os controles da tela. `tela_cheia` acrescenta o botão de tela cheia à direita.

    O filtro de origem saiu da interface em 2026-08-05: a tela passou a ser de manutenção, e
    escolher "Só Produção" num quadro em que todo evento é de manutenção não recorta nada. O
    parâmetro `escopo` continua na assinatura porque as projeções ainda o recebem — hoje
    sempre "ver tudo" —, e devolvê-lo à tela seria expor o controle de novo, nada mais.
    """
    itens = [seletor_de_cenario(cenario)]
    if tema:
        itens.append(botao_de_tema())
    if tela_cheia:
        itens.append(botao_tela_cheia())
    return html.Div(itens, className="mon-controles")
