# -*- coding: utf-8 -*-
"""A planta desenhada e a camada que a torna navegável (SP-02, SP-05).

O desenho entra inline — é o que permite ao CSS gerado pintar cada conjunto por dentro. Por
cima dele fica uma camada de links transparentes, um por ativo, posicionados em porcentagem
a partir da caixa que o inventário guarda.

Por que links por cima e não clique no próprio SVG: o alvo é o **ativo inteiro** (conjunto,
moldura ou rótulo), e um link do roteador do webapp navega sem recarregar a página, preserva
`cenario` e `escopo` na URL e faz o botão "voltar" do navegador funcionar sozinho. Exigir
precisão de clique numa maquininha dentro de um desenho de 1789 px de largura seria hostil.
"""
from __future__ import annotations

from urllib.parse import urlencode

from dash import dcc, html
import dash_bootstrap_components as dbc

from src.utils.monitoring.events import Escopo, inventario
from src.utils.monitoring.scenarios import cenario as buscar_cenario

ID_ART = "mon-art"
ID_CANVAS = "mon-canvas"
ID_FONTE = "mon-art-src"
ID_ESTADOS = "mon-estados"
ID_PINTADO = "mon-pintado"
ID_CAMADA = "mon-hit-layer"
ID_BARRA_FS = "mon-barra-fs"
ID_SAIR_FS = "btn-mon-fullscreen-sair"
ID_TEMA_FS = "btn-mon-tema-fs"
# O nome do cenário e do escopo são atualizados isoladamente, e não a faixa inteira: se a
# faixa fosse recriada a cada repinte, o botão de trocar cenário nasceria com o contador de
# cliques zerado e o próprio clique se desfaria.
ID_FS_CENARIO = "mon-fs-cenario-texto"
ID_FS_TROCAR = "btn-mon-fs-cenario"
ID_FEED_SLOT = "mon-feed-slot"

URL_DA_PLANTA = "/monitoring/art/planta.svg"

ROTA_DO_ATIVO = "/maintenance/monitoramento-ativos/ativo"

# A zona "Decapado (futuro)" não entra: é rotulada, sem conjuntos, sem cor e não clicável.


def _caixas_em_porcentagem() -> list[tuple[str, dict[str, str]]]:
    """Cada ativo com sua caixa convertida para porcentagem do desenho.

    O SVG ocupa a largura toda do contêiner e mantém a proporção do `viewBox`, então
    porcentagem acompanha qualquer tamanho de tela sem recalcular nada no navegador.
    """
    _, _, largura, altura = inventario()["planta"]["view_box"]
    caixas = []
    for item in inventario()["ativos"]:
        caixa = item["caixa"]
        caixas.append(
            (
                item["ativo"],
                {
                    "left": f"{caixa['x'] / largura * 100:.3f}%",
                    "top": f"{caixa['y'] / altura * 100:.3f}%",
                    "width": f"{caixa['largura'] / largura * 100:.3f}%",
                    "height": f"{caixa['altura'] / altura * 100:.3f}%",
                },
            )
        )
    return caixas


def link_do_ativo(ativo: str, cenario: str, escopo: str) -> str:
    """O endereço da página daquele ativo, levando junto cenário e escopo."""
    return f"{ROTA_DO_ATIVO}?" + urlencode(
        {"id": ativo, "cenario": cenario, "escopo": escopo}
    )


def camada_de_cliques(cenario: str, escopo: str) -> list:
    """Um link por ativo, transparente, cobrindo a área da linha no desenho."""
    return [
        dcc.Link(
            html.Span(ativo, className="mon-hit-nome"),
            href=link_do_ativo(ativo, cenario, escopo),
            className="mon-hit",
            style=estilo,
        )
        for ativo, estilo in _caixas_em_porcentagem()
    ]


def barra_de_tela_cheia(cenario: str, escopo: str) -> html.Div:
    """A faixa que só aparece em tela cheia.

    Em tela cheia o resto da página some, e com ele a legenda — sem ela, o significado das
    cores e das molduras some junto. Por isso a faixa carrega a legenda na versão compacta,
    além do cenário em cartaz. Traz também a saída, porque nem todo mundo lembra do Esc.

    O nome do cenário é clicável: cada clique avança para o próximo retrato, em ciclo. Assim
    dá para percorrer todas as situações da fábrica durante uma apresentação sem sair da tela
    cheia — que é justamente quando trocar de cenário interessa mais.
    """
    from src.components.monitoring.controls import botao_de_tema, legenda_compacta

    return html.Div(
        [
            html.Div(
                [
                    dbc.Button(
                        [
                            html.Span(
                                buscar_cenario(cenario).rotulo,
                                id=ID_FS_CENARIO,
                                className="mon-fs-cenario",
                            ),
                            html.I(className="bi bi-arrow-repeat ms-2 mon-fs-girar"),
                        ],
                        id=ID_FS_TROCAR,
                        color="link",
                        size="sm",
                        n_clicks=0,
                        title="Trocar de cenário sem sair da tela cheia",
                        class_name="mon-fs-trocar",
                    ),
                    # Em tela cheia é onde o painel escuro mais interessa — é o modo de
                    # apresentação —, e sair da tela cheia só para trocar de tema desfaria o
                    # que a pessoa está fazendo. Fica ao lado da saída, no mesmo agrupamento.
                    botao_de_tema(ID_TEMA_FS),
                    dbc.Button(
                        [html.I(className="bi bi-fullscreen-exit me-2"), "Sair da tela cheia"],
                        id=ID_SAIR_FS,
                        color="dark",
                        outline=True,
                        size="sm",
                        n_clicks=0,
                    ),
                ],
                className="mon-fs-linha",
            ),
            legenda_compacta(),
        ],
        id=ID_BARRA_FS,
        className="mon-barra-fs",
    )


def planta(cenario: str, escopo: str) -> html.Div:
    """A planta inteira: desenho, estado das cores e camada navegável.

    O desenho não vai no layout: vem por uma rota do próprio webapp e é o navegador que o
    monta dentro de `mon-canvas`. Ver `callbacks_registers/monitoring_routes.py`.
    """
    return html.Div(
        [
            dcc.Store(id=ID_FONTE, data=URL_DA_PLANTA),
            dcc.Store(id=ID_ESTADOS, data={"conjuntos": {}, "ativos": {}}),
            dcc.Store(id=ID_PINTADO),
            barra_de_tela_cheia(cenario, escopo),
            # Palco: o desenho e a camada de links precisam ter exatamente o mesmo
            # tamanho. Como o desenho é dimensionado pela altura e centralizado, o palco
            # encolhe junto com ele (`width: fit-content`) e a camada, posicionada em
            # porcentagem, continua caindo em cima da linha certa.
            # O desenho e o painel de ocorrências dividem a mesma faixa: um responde "onde",
            # o outro "o quê". Quem se situa na fábrica vem pelo desenho; quem já sabe o que
            # procura vem pela lista.
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(id=ID_CANVAS, className="mon-canvas"),
                            html.Div(
                                camada_de_cliques(cenario, escopo),
                                id=ID_CAMADA,
                                className="mon-hit-layer",
                            ),
                        ],
                        className="mon-palco",
                    ),
                    html.Div(id=ID_FEED_SLOT, className="mon-feed-slot"),
                ],
                className="mon-piso",
            ),
        ],
        id=ID_ART,
        className="mon-art",
    )


def frase_de_contexto(escopo: Escopo) -> html.P:
    """Uma frase, não um passo a passo: convite a mexer nos controles."""
    return html.P(
        "Os dados desta tela são ilustrativos. Troque o cenário para ver a fábrica em "
        "outra situação e clique numa linha para abrir o detalhe dela.",
        className="mon-convite",
    )
