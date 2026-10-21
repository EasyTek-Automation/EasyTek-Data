# -*- coding: utf-8 -*-
"""Página de um ativo do Monitoramento (/maintenance/monitoramento-ativos/ativo).

O aprofundamento da planta: o croqui daquela linha à esquerda e, à direita, a linha do tempo,
os cards e uma tabela por conjunto com ocorrência.

O ativo vem por `?id=` porque o roteador do webapp resolve rota por correspondência exata —
não há segmento dinâmico de caminho. Mesmo motivo, mesmo precedente da Análise de Falhas.

`id` ausente ou desconhecido volta para a planta, sem página de erro: caminho sem saída é o
que a IN-02 proíbe.
"""
from urllib.parse import urlencode

from dash import dcc, html
import dash_bootstrap_components as dbc

from src.components.monitoring import asset_view, controls, insight_cards, selo, timeline
from src.components.monitoring import failure_tables
from src.utils.monitoring.events import Escopo, ativos as ativos_conhecidos
from src.utils.monitoring.scenarios import CENARIO_PADRAO

ROTA = "/maintenance/monitoramento-ativos/ativo"
ROTA_PLANTA = "/maintenance/monitoramento-ativos"

ID_CAPACIDADE_SLOT = "mon-capacidade-slot"
ID_TIMELINE_SLOT = "mon-timeline-slot"
ID_CARDS_SLOT = "mon-cards-slot"
ID_TABELAS_SLOT = "mon-tabelas-slot"
ID_VOLTAR = "mon-voltar"
# A página inteira é o que entra em tela cheia quando se chega aqui vindo da planta em tela
# cheia — o croqui sozinho não responderia à pergunta que fez a pessoa clicar na linha.
ID_PAGINA = "mon-pagina-ativo"
# O contexto da página nasce junto com ela. É o que dispara o preenchimento dos blocos, no
# lugar da URL: pela URL, o callback corria contra o roteador — respondia antes de a página
# existir, o conteúdo entrava no DOM mas não no estado do Dash, e o primeiro clique em
# qualquer botão devolvia os blocos vazios.
ID_CONTEXTO = "mon-ativo-contexto"


def link_da_planta(cenario: str, escopo: str) -> str:
    """A volta para a planta, levando junto o que a pessoa estava vendo."""
    return f"{ROTA_PLANTA}?" + urlencode({"cenario": cenario, "escopo": escopo})


def layout(ativo: str | None = None, cenario: str | None = None, escopo: str | None = None):
    """A página do ativo. Sem `id` válido, redireciona para a planta."""
    cenario = cenario or CENARIO_PADRAO
    escopo = escopo or Escopo.TUDO.value

    if ativo not in ativos_conhecidos():
        return html.Div(dcc.Location(id="mon-redirect", href=link_da_planta(cenario, escopo)))

    return html.Div(
        [
            dcc.Store(
                id=ID_CONTEXTO,
                data={"ativo": ativo, "cenario": cenario, "escopo": escopo},
            ),
            html.Div(
                [
                    dcc.Link(
                        [html.I(className="bi bi-arrow-left me-2"), "Voltar para a planta"],
                        href=link_da_planta(cenario, escopo),
                        id=ID_VOLTAR,
                        className="mon-voltar",
                    ),
                    html.H4(ativo, className="mon-titulo mon-titulo-ativo"),
                    selo.selo_de_demonstracao(ROTA),
                ],
                className="mon-cabecalho-ativo",
            ),
            controls.barra_de_controles(cenario, escopo),
            html.Div(controls.legenda(Escopo(escopo), com_molduras=False), id="mon-legenda-slot"),
            dbc.Row(
                [
                    dbc.Col(asset_view.croqui(ativo), lg=4, md=12, class_name="mon-coluna-croqui"),
                    dbc.Col(
                        [
                            html.Div(
                                [
                                    html.H6("Linha do tempo — últimas 24 horas",
                                            className="mon-secao"),
                                    html.Div(id=ID_TIMELINE_SLOT),
                                ],
                                className="mon-bloco",
                            ),
                            # A capacidade vem logo abaixo da faixa de estados, e não em outro
                            # ponto da página: as duas dividem o mesmo eixo do tempo, e é essa
                            # vizinhança que deixa comparar "em que estado esteve" com "quanto
                            # entregou" sem tirar o olho do lugar.
                            html.Div(id=ID_CAPACIDADE_SLOT),
                            html.Div(id=ID_CARDS_SLOT, className="mon-bloco"),
                            html.Div(
                                [
                                    html.H6("Ocorrências por conjunto", className="mon-secao"),
                                    html.Div(id=ID_TABELAS_SLOT),
                                ],
                                className="mon-bloco",
                            ),
                        ],
                        lg=8,
                        md=12,
                    ),
                ],
                class_name="mon-corpo-ativo g-3",
            ),
            html.P(
                "A saúde por conjunto mostrada aqui depende de medição que ainda não existe "
                "por máquina — hoje o sistema mede a linha inteira.",
                className="mon-aviso-conjunto",
            ),
        ],
        id=ID_PAGINA,
        className="mon-page p-3",
    )
