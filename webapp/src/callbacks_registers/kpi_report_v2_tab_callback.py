"""Callback de renderização da aba 'Relatório' do indicators-v2.

Reusa **layout V1** (helpers em `kpi_report_screen_callbacks`) — entrega o mesmo
visual do Tab 4 "Relatório Diário" da página /maintenance/indicators.

Trigger: `tabs-indicators-v2.active_tab == 'tab-v2-report'`.
Saída: `rd-v2-content-container.children` + `rd-v2-periodo-label.children`
       + `store-kpi-v2-data` (alimenta C8/C9 export).

Anti-pattern proibido: NÃO recalcula KPI. Delega a `coletar_dados_relatorio` v1
e renderiza via helpers V1 (`_row_3_kpis`, `_row_3_sunbursts`, `_tabela_*`).
"""
from __future__ import annotations

import logging

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, html, no_update

from src.callbacks_registers.kpi_report_screen_callbacks import (
    _row_3_kpis,
    _row_3_sunbursts,
    _section,
    _tabela_detalhamento,
    _tabela_top_paradas,
)
from src.utils import kpi_report_config as cfg
from src.utils.kpi_report_data import coletar_dados_relatorio

logger = logging.getLogger(__name__)


def register_kpi_report_v2_tab_callback(app: dash.Dash) -> None:
    """Popula aba 'Relatório' do indicators-v2 com layout V1 quando ativada."""

    @app.callback(
        Output("rd-v2-content-container", "children"),
        Output("rd-v2-periodo-label", "children"),
        Output("store-kpi-v2-data", "data", allow_duplicate=True),
        Input("tabs-indicators-v2", "active_tab"),
        prevent_initial_call=True,
    )
    def render_relatorio_v2(active_tab):
        """Renderiza relatório quando aba 'Relatório' fica ativa.

        Reusa estrutura e helpers do Tab 4 "Relatório Diário" v1 (DS-08 SDD v1).
        Popula `store-kpi-v2-data` pra habilitar botões de export (C11).
        """
        if active_tab != "tab-v2-report":
            raise dash.exceptions.PreventUpdate

        # Indicators-V2 não tem store-indicator-filters (rota não popula store v1).
        # Monta stored_data via funções canônicas v1 (mesmo path da rota standalone).
        try:
            from src.callbacks_registers.kpi_report_v2_callbacks import (
                _build_default_stored_data,
            )
            stored_data = _build_default_stored_data()
        except Exception:
            logger.exception("KPI v2 tab: falha _build_default_stored_data")
            stored_data = None

        if not stored_data or not stored_data.get("equipment_ids"):
            empty = dbc.Alert(
                "Sem equipamentos no escopo. Verifique conexão com o ZPP.",
                color="warning",
                className="text-center mt-4",
            )
            return empty, "", {"empty": True, "reason": "no_equipment"}

        try:
            agora = cfg._now_in_report_timezone()
            dados = coletar_dados_relatorio(stored_data, agora, as_png=False)
        except Exception:
            logger.exception("KPI v2 tab: falha em coletar_dados_relatorio")
            return (
                dbc.Alert(
                    "Erro ao gerar relatório. Veja os logs do servidor.",
                    color="danger",
                ),
                "",
                {"empty": True, "reason": "error"},
            )

        periodo = dados.get("periodo") or {}
        rotulo = periodo.get("rotulo", "")
        b1 = dados.get("bloco1") or {}
        b2 = dados.get("bloco2") or {}
        b3 = dados.get("bloco3") or {}
        b4 = dados.get("bloco4") or {}
        b5 = dados.get("bloco5") or {}

        if dados.get("planta_vazia"):
            return (
                dbc.Alert(
                    "Planta sem dados no período. Verifique se os ZPP estão atualizados.",
                    color="info",
                ),
                rotulo,
                {"empty": True, "reason": "planta_vazia"},
            )

        # Mesma ordem do Tab 4 v1 — alinhada ao template DOCX (2026-05-13).
        content = html.Div([
            _section(
                "KPIs da Planta (Mês Corrente)",
                _row_3_kpis(b1.get("kpis_planta", {}),
                            b1.get("metas", {}),
                            b1.get("cores_kpis", {})),
                _row_3_sunbursts(b1.get("sunburst_figures", {})),
            ),
            _section(
                "Top 5 Paradas do Mês",
                _tabela_top_paradas(
                    b2.get("paradas", []), b2.get("vazio", True),
                    "Sem paradas registradas no mês corrente.",
                ),
            ),
            _section(
                "Detalhamento por Equipamento",
                _tabela_detalhamento(b4),
            ),
            _section(
                "KPIs Últimas 24h",
                _row_3_kpis(b3.get("kpis_planta", {}),
                            b3.get("metas", {}),
                            b3.get("cores_kpis", {})),
                _row_3_sunbursts(b3.get("sunburst_figures", {})),
            ),
            _section(
                "Todas as Paradas das Últimas 24h",
                html.Div(
                    _tabela_top_paradas(
                        b5.get("paradas", []), b5.get("vazio", True),
                        "Sem paradas nas últimas 24 horas.",
                    ),
                    style={"maxHeight": "500px", "overflowY": "auto"},
                ),
            ),
        ])

        # store-kpi-v2-data: marca disponível pra habilitar export (C11 desabilita
        # botões enquanto for None/empty). Não precisa serializar dados pesados —
        # callbacks de export coletam novamente com as_png=True.
        ready_marker = {"ready": True, "rotulo": rotulo}
        return content, rotulo, ready_marker
