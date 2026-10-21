# -*- coding: utf-8 -*-
"""Página "Monitoramento de Ativos" — planta geral (/maintenance/monitoramento-ativos).

Protótipo: mostra a fábrica vista de cima, com a saúde de cada máquina em cor, e leva ao
detalhe de cada linha. Todos os dados são mockados (SDD `MonAtivo-Prototipo`).

O estado da tela — qual cenário e o que entra na conta — mora na **URL**, não em store. É o
que faz o filtro sobreviver à navegação para a página do ativo e, ao mesmo tempo, não
sobreviver a uma nova entrada pelo menu: quem entra sem parâmetro recebe os padrões. Filtro
com memória é armadilha em autoatendimento — a pessoa voltaria semanas depois, veria a planta
verde e não lembraria que deixou "Só Produção" ligado.

Acesso: perfis manutenção e produção, nível ≥ 1. A produção entra por decisão consciente —
sem ela, ninguém da área veria o próprio recorte no filtro.
"""
from dash import html

from src.components.monitoring import controls, plant_view, selo, status_bar
from src.utils.monitoring.events import Escopo
from src.utils.monitoring.scenarios import CENARIO_PADRAO

ROTA = "/maintenance/monitoramento-ativos"
# A raiz da página é nomeada para o CSS de tela cheia saber que está na planta: ali o desenho
# é o conteúdo, e cabeçalho, controles e legenda longa dão lugar à faixa compacta. Na página
# do ativo é o contrário — a página inteira é o conteúdo e nada dela se esconde.
ID_PAGINA = "mon-pagina-planta"


def layout(cenario: str | None = None, escopo: str | None = None) -> html.Div:
    """A planta geral. Sem parâmetro na URL, abre no cenário de entrada e em "Ver tudo"."""
    cenario = cenario or CENARIO_PADRAO
    escopo = escopo or Escopo.TUDO.value

    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.H4("Monitoramento de Ativos", className="mon-titulo"),
                            selo.selo_de_demonstracao(ROTA),
                        ],
                        className="mon-titulo-linha",
                    ),
                    plant_view.frase_de_contexto(Escopo(escopo)),
                ],
                className="mon-cabecalho",
            ),
            controls.barra_de_controles(cenario, escopo, tela_cheia=True),
            html.Div(controls.legenda(Escopo(escopo)), id="mon-legenda-slot"),
            html.Div(id=status_bar.ID_FAIXA_SLOT, className="mon-situacao-slot"),
            plant_view.planta(cenario, escopo),
        ],
        id=ID_PAGINA,
        className="mon-page p-3",
    )
