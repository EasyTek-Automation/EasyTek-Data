"""Callbacks da renderização do Relatório Diário na tela (Tab 4 — IM-08).

Reusa `coletar_dados_relatorio(..., as_png=False)` para obter os mesmos dados que
o DOCX, mas com Plotly Figures nativos (interativos via dcc.Graph) em vez de PNG.

IM-08 do projeto SDD KPIReport — feature adicional à entrega original do KPIReport.
"""
from __future__ import annotations

import logging
from datetime import datetime

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html

from src.utils import kpi_report_config as cfg
from src.utils.kpi_report_data import coletar_dados_relatorio

logger = logging.getLogger(__name__)

_CHAVES_OBRIGATORIAS: tuple[str, ...] = ("data", "names", "year", "equipment_ids")


def _store_estrutura_valida(stored_data: dict | None) -> bool:
    if stored_data is None or not isinstance(stored_data, dict):
        return False
    return all(k in stored_data for k in _CHAVES_OBRIGATORIAS)


def _fmt_kpi(v, sufixo: str = "") -> str:
    if v is None:
        return "—"
    return f"{cfg.fmt_numero(v)}{sufixo}"


def _badge_color(cor: str | None) -> str:
    return {"verde": "success", "amarelo": "warning", "vermelho": "danger"}.get(cor or "", "secondary")


def _card_kpi(titulo: str, valor: str, meta: str, cor: str | None) -> dbc.Card:
    return dbc.Card(
        dbc.CardBody([
            html.Div(titulo, className="text-muted small text-uppercase fw-bold"),
            html.Div([
                html.Span(valor, className="fs-3 fw-bold me-2"),
                dbc.Badge(meta, color=_badge_color(cor), className="align-middle"),
            ], className="mt-2"),
        ]),
        className="shadow-sm h-100",
    )


def _row_3_kpis(kpis: dict, metas: dict, cores: dict) -> dbc.Row:
    """Linha com 3 cards: MTBF, MTTR, Taxa Avaria."""
    return dbc.Row([
        dbc.Col(_card_kpi(
            "MTBF",
            _fmt_kpi(kpis.get("mtbf"), " h"),
            f"Meta {_fmt_kpi(metas.get('mtbf'), ' h')}",
            cores.get("mtbf"),
        ), md=4, className="mb-3"),
        dbc.Col(_card_kpi(
            "MTTR",
            _fmt_kpi(kpis.get("mttr"), " min"),
            f"Meta {_fmt_kpi(metas.get('mttr'), ' min')}",
            cores.get("mttr"),
        ), md=4, className="mb-3"),
        dbc.Col(_card_kpi(
            "Taxa de Avaria",
            _fmt_kpi(kpis.get("taxa_avaria"), " %"),
            f"Meta {_fmt_kpi(metas.get('taxa_avaria'), ' %')}",
            cores.get("taxa_avaria"),
        ), md=4, className="mb-3"),
    ])


def _row_3_sunbursts(sunbursts: dict) -> dbc.Row:
    """Sunbursts em cards sem header — KPI cards acima já carregam os títulos."""
    cols = []
    for key in ("mtbf", "mttr", "taxa_avaria"):
        fig = sunbursts.get(key)
        if fig is None:
            content = dbc.Alert("Indisponível.", color="warning", className="text-center mb-0")
        else:
            content = dcc.Graph(figure=fig, config={"displayModeBar": False}, style={"height": "320px"})
        card = dbc.Card(
            dbc.CardBody(content, className="p-2"),
            className="shadow-sm h-100",
        )
        cols.append(dbc.Col(card, md=4, className="mb-3"))
    return dbc.Row(cols)


def _tabela_top_paradas(paradas: list[dict], vazio: bool, vazio_msg: str) -> html.Div:
    if vazio or not paradas:
        return dbc.Alert(vazio_msg, color="info", className="text-center")
    header = html.Thead(html.Tr([
        html.Th("#"),
        html.Th("Equipamento"),
        html.Th("Início"),
        html.Th("Duração"),
        html.Th("Causa"),
        html.Th("Descrição"),
    ]))
    body = html.Tbody([
        html.Tr([
            html.Td(p.get("posicao")),
            html.Td(p.get("equipamento")),
            html.Td(p.get("data_hora")),
            html.Td(p.get("duracao_min")),
            html.Td(p.get("causa")),
            html.Td(p.get("descricao")),
        ]) for p in paradas
    ])
    return dbc.Table([header, body], striped=True, hover=True, bordered=True, responsive=True, size="sm")


def _tabela_detalhamento(bloco4: dict) -> html.Div:
    """Renderiza tabela do Bloco 4 com cores por célula (BR-06).

    Cor aplicada como classe `text-success/warning/danger`; quando `cor` é None
    NÃO aplica `text-secondary` (gray text + gray bg na linha TOTAL ficava ilegível).
    """
    if bloco4.get("vazio"):
        return dbc.Alert("Sem dados de detalhamento no período.", color="info", className="text-center")

    _COR_CLASS = {"verde": "text-success", "amarelo": "text-warning", "vermelho": "text-danger"}

    def _td_cor(valor, cor):
        cls = _COR_CLASS.get(cor or "", "")
        return html.Td(_fmt_kpi(valor), className=cls)

    header = html.Thead(html.Tr([
        html.Th("Equipamento"),
        html.Th("MTBF (h)"),
        html.Th("MTTR (min)"),
        html.Th("Taxa Avaria (%)"),
    ]))
    rows = []
    for linha in bloco4.get("linhas", []):
        rows.append(html.Tr([
            html.Td(linha.get("equipamento")),
            _td_cor(linha.get("mtbf"), linha.get("cor_mtbf")),
            _td_cor(linha.get("mttr"), linha.get("cor_mttr")),
            _td_cor(linha.get("taxa_avaria"), linha.get("cor_taxa_avaria")),
        ]))

    total = bloco4.get("total", {})

    def _td_total(valor, cor):
        cls = _COR_CLASS.get(cor or "", "")
        return html.Td(html.Strong(_fmt_kpi(valor)), className=f"{cls} fw-bold".strip())

    rows.append(html.Tr([
        html.Td(html.Strong("TOTAL"), className="fw-bold"),
        _td_total(total.get("mtbf"),        total.get("cor_mtbf")),
        _td_total(total.get("mttr"),        total.get("cor_mttr")),
        _td_total(total.get("taxa_avaria"), total.get("cor_taxa_avaria")),
    ], className="table-secondary"))
    return dbc.Table([header, html.Tbody(rows)], striped=False, hover=True, bordered=True, responsive=True, size="sm")


def _section(titulo: str, *children) -> html.Div:
    return html.Div([
        html.H5(titulo, className="border-bottom pb-2 mb-3 mt-4"),
        *children,
    ])


def register_kpi_report_screen_callbacks(app: dash.Dash) -> None:
    """Registra callback de renderização da Tab 4 — Relatório Diário."""

    @app.callback(
        Output("rd-content-container", "children"),
        Output("rd-periodo-label", "children"),
        Input("indicator-tabs", "active_tab"),
        Input("store-indicator-filters", "data"),
        prevent_initial_call=True,
    )
    def render_relatorio_diario(active_tab, stored_data):
        """Popula Tab 4 com os 5 blocos do relatório quando ativa.

        Reusa coletar_dados_relatorio com as_png=False para Plotly nativos.
        Recalcula ao mudar de aba OU quando o store atualiza (preserva interatividade
        após o usuário aplicar novo filtro na tela — embora os blocos não obedeçam
        ao filtro custom da página: Bloco Mensal = mês corrente, Bloco 24h = ontem).
        """
        if active_tab != "tab-relatorio-diario":
            raise dash.exceptions.PreventUpdate

        if not _store_estrutura_valida(stored_data):
            empty = dbc.Alert(
                "Aguardando dados do dashboard... carregue a aba Geral primeiro.",
                color="warning",
                className="text-center mt-4",
            )
            return empty, ""

        try:
            agora = cfg._now_in_report_timezone()
            dados = coletar_dados_relatorio(stored_data, agora, as_png=False)
        except Exception:
            logger.exception("Falha ao coletar dados para Relatório Diário na tela")
            return dbc.Alert("Erro ao gerar relatório. Veja os logs.", color="danger"), ""

        periodo = dados.get("periodo", {})
        rotulo = periodo.get("rotulo", "")
        b1 = dados.get("bloco1", {})
        b2 = dados.get("bloco2", {})
        b3 = dados.get("bloco3", {})
        b4 = dados.get("bloco4", {})
        b5 = dados.get("bloco5", {})

        if dados.get("planta_vazia"):
            return dbc.Alert(
                "Planta sem dados no período. Verifique se os ZPP estão atualizados.",
                color="info",
            ), rotulo

        # Ordem alinhada ao template DOCX (atualizado 2026-05-13): Detalhamento por
        # Equipamento aparece após Top Paradas Mensais; KPIs 24h e lista 24h ao final.
        content = html.Div([
            _section(
                "KPIs da Planta (Mês Corrente)",
                _row_3_kpis(b1.get("kpis_planta", {}), b1.get("metas", {}), b1.get("cores_kpis", {})),
                _row_3_sunbursts(b1.get("sunburst_figures", {})),
            ),
            _section(
                "Top 5 Paradas do Mês",
                _tabela_top_paradas(b2.get("paradas", []), b2.get("vazio", True),
                                    "Sem paradas registradas no mês corrente."),
            ),
            _section(
                "Detalhamento por Equipamento",
                _tabela_detalhamento(b4),
            ),
            _section(
                "KPIs Últimas 24h",
                _row_3_kpis(b3.get("kpis_planta", {}), b3.get("metas", {}), b3.get("cores_kpis", {})),
                _row_3_sunbursts(b3.get("sunburst_figures", {})),
            ),
            _section(
                "Todas as Paradas das Últimas 24h",
                html.Div(
                    _tabela_top_paradas(b5.get("paradas", []), b5.get("vazio", True),
                                        "Sem paradas nas últimas 24 horas."),
                    style={"maxHeight": "500px", "overflowY": "auto"},
                ),
            ),
        ])

        return content, rotulo
