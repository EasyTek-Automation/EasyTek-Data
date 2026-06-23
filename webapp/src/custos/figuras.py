"""Figuras de custo de manutenção sem dependência de Dash (DS-11 / SP-16).

Extrai a figura de barras da tela "Custo de Manutenção" (aba em `/maintenance/indicators-v2`)
para um contrato reusável por consumidores fora do Dash — em especial o builder DOCX do
KPIReport, que embute o gráfico do mês corrente no relatório.

O contrato público (`figura_custo_mensal`) não importa Dash; `_fig_barras` (Plotly puro, apesar
de morar no módulo de callbacks) é importado lazy dentro da função.
"""
from __future__ import annotations

import logging
from typing import Optional

import plotly.graph_objects as go

from src.custos import leitura as L

logger = logging.getLogger(__name__)


def _sem_dados(rows: list[dict] | None) -> bool:
    """True quando não há custo a plotar — lista vazia ou só o GERAL zerado.

    `fetch_contas_geral` devolve a 1ª linha como GERAL (rollup); sem carga no mês ela vem
    zerada e sem contas. Nesse caso o bloco do relatório deve ser omitido (SP-16).
    """
    if not rows:
        return True
    contas = [r for r in rows if r.get("code") != "__GERAL__"]
    if contas:
        return False
    geral = rows[0]
    return not (geral.get("executado") or geral.get("orcado"))


def figura_custo_mensal(ano: int, mes: str, h: int = 460) -> Optional[go.Figure]:
    """Figura de barras do custo do mês (GERAL + contas, % do orçado) ou `None` se sem dados.

    `mes` no formato 'YYYY-MM'. Eixo duplo com o GERAL destacado (idêntico à tela). Retorna
    `None` quando não há custo no mês — o chamador omite o bloco do relatório.
    """
    rows = L.fetch_contas_geral(ano, mes, centros=None)
    if _sem_dados(rows):
        logger.info("Custo mensal %s sem dados — figura omitida", mes)
        return None

    # Lazy import: `_fig_barras` é Plotly puro, mas vive em módulo que importa Dash. O export
    # roda dentro do webapp (Dash já carregado), então o import é seguro; mantê-lo lazy preserva
    # `figura_custo_mensal` importável sem efeitos colaterais de Dash.
    from src.callbacks_registers.custo_callbacks import _fig_barras

    titulo = f"Custo de Manutenção — {mes} — realizado por conta (% do orçado)"
    fig = _fig_barras(rows, com_orcado=True, titulo=titulo, h=h, modo="pct")
    # As fontes de `_fig_barras` são dimensionadas para a tela (8–13 px). No DOCX a figura é
    # renderizada em alta resolução e reduzida para a largura da página, deixando rótulos/eixos/
    # legenda minúsculos. Ampliamos as fontes só nesta cópia (não afeta a tela) e damos mais
    # margem para os rótulos longos do eixo X caberem.
    _ampliar_fontes_para_docx(fig, mult=_DOCX_FONT_MULT)
    return fig


_DOCX_FONT_MULT = 2.0
_DOCX_Y_HEADROOM = 1.35  # teto extra nos eixos Y p/ os rótulos não baterem no título/legenda


def _ampliar_fontes_para_docx(fig, mult: float) -> None:
    """Multiplica in-place as fontes da figura (rótulos, eixos, título, legenda) por `mult` e
    aumenta as margens proporcionalmente, para legibilidade no DOCX em largura cheia."""
    lay = fig.layout

    def _bump(font):
        if font is not None and getattr(font, "size", None):
            font.size = round(font.size * mult)

    _bump(getattr(lay, "font", None))
    if getattr(lay, "title", None) is not None:
        _bump(getattr(lay.title, "font", None))
    if getattr(lay, "legend", None) is not None:
        _bump(getattr(lay.legend, "font", None))
    for ax_name in ("xaxis", "yaxis", "yaxis2"):
        ax = getattr(lay, ax_name, None)
        if ax is not None:
            _bump(getattr(ax, "tickfont", None))
            if getattr(ax, "title", None) is not None:
                _bump(getattr(ax.title, "font", None))
    # Headroom extra nos eixos Y: com rótulos maiores e mais espaçados, as barras altas (GERAL,
    # contas estouradas) empurravam a pilha de rótulos para cima do título/legenda. Encolher as
    # barras (mais teto) abre espaço para os rótulos caberem abaixo do título.
    for ax_name in ("yaxis", "yaxis2"):
        ax = getattr(lay, ax_name, None)
        rng = getattr(ax, "range", None) if ax is not None else None
        if rng and rng[1]:
            ax.range = [rng[0], rng[1] * _DOCX_Y_HEADROOM]
    for ann in (lay.annotations or ()):
        _bump(getattr(ann, "font", None))
        # Os rótulos de dados são 3 linhas empilhadas por `yshift` fixo (exec/orçado/%). Ao
        # ampliar a fonte sem ampliar o deslocamento, as linhas se sobrepõem (a do meio espreme).
        # Escala o yshift na mesma proporção para manter o espaçamento entre as linhas.
        if getattr(ann, "yshift", None):
            ann.yshift = round(ann.yshift * mult)
    # margens: rótulos do eixo X (nomes de conta, rotacionados) e dos eixos Y (esq. e dir.)
    # precisam de mais espaço com as fontes maiores.
    m = lay.margin
    if m is not None:
        if m.b:
            m.b = round(m.b * mult)
        if m.l:
            m.l = round(m.l * mult)
        if m.t:
            m.t = round(m.t * mult)
        # eixo Y direito (y2, contas) só existe quando há GERAL destacado; reserva espaço fixo
        # para os ticks ("1000 %") não cortarem na borda.
        m.r = max(round((m.r or 0) * mult), 70)
