# -*- coding: utf-8 -*-
"""A faixa de situação da fábrica e o painel de ocorrências ativas.

Duas leituras que o desenho sozinho não dá:

* **A contagem** — quantas linhas estão em cada estado agora. O desenho mostra *onde*; a faixa
  responde *quanto*, que é a primeira pergunta de quem chega na sala e olha o telão.
* **A fila** — o que está aberto neste instante, em ordem de severidade e do mais recente para
  o mais antigo. É a lista que o técnico percorre; no desenho ela está espalhada por oito
  linhas e exige varredura visual.

Nenhuma das duas inventa dado: as duas são projeções da mesma lista de eventos que pinta as
máquinas (BR-01), montadas a cada repinte. Onde a planta e estes dois blocos divergissem, o
problema seria da projeção — não há caminho alternativo por onde a informação chegue aqui.
"""
from __future__ import annotations

from datetime import datetime

from dash import dcc, html

from src.components.monitoring.system_text import com_marcacoes
from src.utils.monitoring import projection as pj
from src.utils.monitoring.events import Cor, Gravidade, ativos, nome_do_conjunto

ID_FAIXA = "mon-situacao"
ID_FAIXA_SLOT = "mon-situacao-slot"
ID_FEED = "mon-feed"

ROTA_DO_ATIVO = "/maintenance/monitoramento-ativos/ativo"

# A ordem é a da régua de cor (BR-02), da pior para a melhor — a faixa se lê da esquerda para
# a direita como uma escala de severidade, não como uma lista arbitrária.
SITUACOES = [
    (Cor.VERMELHO, "vermelho", "parada", "paradas"),
    (Cor.AMARELO, "parcial", "em atenção", "em atenção"),
    (Cor.CINZA, "parado", "prevista", "previstas"),
    (Cor.VERDE, "cheio", "rodando", "rodando"),
]


def _contagem(eventos, agora: datetime) -> dict[Cor, int]:
    """Quantas linhas em cada estado. Linha sem evento conta como rodando."""
    por_ativo = pj.cor_dos_ativos_completo(eventos, agora)
    contagem = {cor: 0 for cor, *_ in SITUACOES}
    for cor in por_ativo.values():
        contagem[cor] = contagem.get(cor, 0) + 1
    return contagem


def faixa_de_situacao(eventos, agora: datetime | None = None) -> html.Div:
    """A contagem de linhas por estado, com a hora da leitura.

    O número vem antes da palavra e em corpo maior: quem passa o olho lê "1 parada" pelo
    algarismo, não pelo texto. Estado com zero linhas continua na faixa, apagado — sumir com
    ele faria a faixa mudar de largura a cada troca de cenário, e o "zero paradas" é
    informação tão boa quanto o "uma parada".
    """
    agora = agora or datetime.now()
    contagem = _contagem(eventos, agora)
    total = len(ativos())

    blocos = []
    for cor, classe, singular, plural in SITUACOES:
        quantas = contagem.get(cor, 0)
        blocos.append(
            html.Div(
                [
                    html.Span(className=f"mon-chip mon-chip-{classe}"),
                    html.Span(f"{quantas}", className="mon-situacao-numero"),
                    html.Span(singular if quantas == 1 else plural,
                              className="mon-situacao-rotulo"),
                ],
                className="mon-situacao-item" + ("" if quantas else " mon-situacao-zero"),
            )
        )

    blocos.append(
        html.Div(
            [
                html.Span(className="mon-live-dot"),
                html.Span("leitura de ", className="mon-situacao-rotulo"),
                html.Span(agora.strftime("%H:%M"), className="mon-situacao-hora"),
                html.Span(f" · {total} linhas monitoradas", className="mon-situacao-rotulo"),
            ],
            className="mon-situacao-item mon-situacao-leitura",
        )
    )
    return html.Div(blocos, id=ID_FAIXA, className="mon-situacao")


# --------------------------------------------------------------------------- #
# painel de ocorrências ativas
# --------------------------------------------------------------------------- #

ORDEM = {Gravidade.PARADA: 0, Gravidade.DEGRADACAO: 1, Gravidade.PLANEJADA: 2}

CLASSE_DA_GRAVIDADE = {
    Gravidade.PARADA: "vermelho",
    Gravidade.DEGRADACAO: "parcial",
    Gravidade.PLANEJADA: "parado",
}


def _duracao_curta(horas: float) -> str:
    minutos = int(round(horas * 60))
    if minutos < 60:
        return f"{minutos}min"
    if minutos < 60 * 48:
        return f"{minutos // 60}h{minutos % 60:02d}"
    return f"{horas / 24:.0f}d"


def painel_de_ocorrencias(eventos, cenario: str, agora: datetime | None = None) -> html.Div:
    """O que está aberto agora, do mais grave para o menos, do mais novo para o mais velho.

    Cada item leva à página da linha — é o mesmo destino do clique no desenho, por outro
    caminho. Quem já sabe o que procura vem pela lista; quem quer situar-se na fábrica vem
    pelo desenho.

    Evento fechado não entra: a lista é do que está acontecendo. O histórico continua inteiro
    na página de cada ativo.
    """
    agora = agora or datetime.now()
    abertos = sorted(
        pj.vigentes(eventos, agora),
        key=lambda e: (ORDEM[e.gravidade], -e.duracao(agora)),
    )

    if not abertos:
        corpo = [
            html.Div(
                [
                    html.Div("Nenhuma ocorrência aberta", className="mon-feed-vazio-titulo"),
                    html.Div("Todas as linhas rodando sem evento.",
                             className="mon-feed-vazio-texto"),
                ],
                className="mon-feed-vazio",
            )
        ]
    else:
        corpo = [
            dcc.Link(
                [
                    html.Div(
                        [
                            html.Span(evento.ativo, className="mon-feed-ativo"),
                            html.Span(_duracao_curta(evento.duracao(agora)),
                                      className="mon-feed-tempo"),
                        ],
                        className="mon-feed-topo",
                    ),
                    html.Div(
                        nome_do_conjunto().get(evento.conjunto, evento.conjunto),
                        className="mon-feed-conjunto",
                    ),
                    html.Div(com_marcacoes(evento.descricao), className="mon-feed-texto"),
                ],
                href=f"{ROTA_DO_ATIVO}?id={evento.ativo}&cenario={cenario}",
                className=f"mon-feed-item mon-feed-{CLASSE_DA_GRAVIDADE[evento.gravidade]}",
            )
            for evento in abertos
        ]

    return html.Div(
        [
            html.Div(
                [
                    html.Span("Ocorrências ativas", className="mon-feed-titulo"),
                    html.Span(f"{len(abertos)}", className="mon-feed-contador"),
                ],
                className="mon-feed-cabecalho",
            ),
            html.Div(corpo, className="mon-feed-lista"),
        ],
        id=ID_FEED,
        className="mon-feed",
    )
