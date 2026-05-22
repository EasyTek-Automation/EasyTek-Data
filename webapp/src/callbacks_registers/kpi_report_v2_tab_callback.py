"""Callback de renderização da aba 'Relatório' do indicators-v2.

Reusa **estrutura V1** (helpers em `kpi_report_screen_callbacks` — cards KPI,
tabelas, seções) MAS substitui os sunbursts por **bar charts** alinhados ao
paradigma visual do Indicators-V2 (refactor sessão 03).

Trigger: `tabs-indicators-v2.active_tab == 'tab-v2-report'`.
Saída: `rd-v2-content-container.children` + `rd-v2-periodo-label.children`
       + `store-kpi-v2-data` (alimenta C8/C9 export).

Anti-pattern proibido: NÃO recalcula KPI. Delega a `coletar_dados_relatorio` v1
e renderiza via helpers V1 (`_row_3_kpis`, `_tabela_*`).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html, no_update

from src.callbacks_registers.kpi_report_screen_callbacks import (
    _row_3_kpis,
    _section,
    _tabela_detalhamento,
    _tabela_top_paradas,
)
from src.utils import kpi_report_config as cfg
from src.utils.kpi_report_data import (
    _build_kpis_bloco_planta,
    _build_top5_paradas,
    coletar_dados_relatorio,
)
from src.utils.kpi_report_v2_bars import build_bar_figure
from src.utils.kpi_report_v2_series import (
    build_daily_series_last_n,
    build_daily_series_last_n_ending,
    build_monthly_series_for_year,
)
from src.utils.zpp_kpi_calculator import fetch_zpp_kpi_data

logger = logging.getLogger(__name__)


_KPI_KEYS: tuple[tuple[str, str], ...] = (
    ("mtbf",        "MTBF"),
    ("mttr",        "MTTR"),
    ("taxa_avaria", "Taxa de Avaria"),
)


def _row_3_bars(series: dict | None, metas: dict | None) -> dbc.Row:
    """3 cards lado a lado — bar chart por KPI (substitui `_row_3_sunbursts`).

    `series`: dict com `labels`, `mtbf`, `mttr`, `taxa_avaria`, `current_idx`.
    `metas`: dict com `mtbf`, `mttr`, `taxa_avaria` (em h, min, %).
    """
    metas = metas or {}
    cols = []
    for kpi_key, _ in _KPI_KEYS:
        if not isinstance(series, dict) or not series.get("labels"):
            content = dbc.Alert("Sem dados.", color="warning",
                                 className="text-center mb-0")
        else:
            fig = build_bar_figure(
                labels=series.get("labels") or [],
                values=series.get(kpi_key) or [],
                kpi=kpi_key,
                target=metas.get(kpi_key),
                title="",
                highlight_idx=series.get("current_idx"),
                height=300,
            )
            content = dcc.Graph(
                figure=fig,
                config={"displayModeBar": False, "responsive": True},
                style={"height": "300px"},
            )
        cols.append(
            dbc.Col(
                dbc.Card(dbc.CardBody(content, className="p-2"),
                          className="shadow-sm h-100"),
                md=4, className="mb-3",
            )
        )
    return dbc.Row(cols)


def _recompute_blocos_24h(
    stored_data: dict,
    data_dia: datetime,
) -> tuple[dict, dict]:
    """Recalcula bloco3 + bloco5 com janela `[data_dia 00:00, data_dia+1 00:00)`.

    BR-02b: override do dia "últimas 24h". Reusa V1 `_build_kpis_bloco_planta`
    + `_build_top5_paradas` — fórmulas canônicas, não recalcula nada.
    """
    d_start = data_dia.replace(hour=0, minute=0, second=0, microsecond=0,
                                 tzinfo=None)
    d_end = d_start + timedelta(days=1)

    eq_ids = stored_data.get("equipment_ids") or []
    names = stored_data.get("names") or {}
    categories = stored_data.get("categories") or {}
    targets = stored_data.get("equipment_targets") or {}

    try:
        data_dia_kpi = fetch_zpp_kpi_data(d_start, d_end)
    except Exception:
        logger.warning("KPI v2 BR-02b: sem dados ZPP em [%s, %s)", d_start, d_end)
        data_dia_kpi = {}

    bloco3 = _build_kpis_bloco_planta(
        eq_ids, d_start, d_end, targets, names, categories,
        kpi_data=data_dia_kpi, year=d_start.year, monthly_aggregates=None,
        as_png=False,
    )
    bloco5 = _build_top5_paradas(d_start, d_end, names, top_n=None)
    return bloco3, bloco5


def _resolve_data_24h(value: Optional[str], agora: datetime) -> datetime:
    """Resolve DatePicker value (ISO 'YYYY-MM-DD') → datetime do dia escolhido.

    Default (None ou inválido): ontem (BR-02 padrão).
    """
    if value:
        try:
            return datetime.fromisoformat(str(value)[:10])
        except ValueError:
            pass
    # Default = ontem
    return (agora.replace(hour=0, minute=0, second=0, microsecond=0,
                            tzinfo=None) - timedelta(days=1))


def register_kpi_report_v2_tab_callback(app: dash.Dash) -> None:
    """Popula aba 'Relatório' do indicators-v2 com layout V1 quando ativada."""

    @app.callback(
        Output("rd-v2-content-container", "children"),
        Output("rd-v2-periodo-label", "children"),
        Output("store-kpi-v2-data", "data", allow_duplicate=True),
        Input("tabs-indicators-v2", "active_tab"),
        Input("kpi-v2-date-24h", "date"),
        prevent_initial_call=True,
    )
    def render_relatorio_v2(active_tab, date_24h):
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

        # BR-02b: se DatePicker forneceu data ≠ ontem, sobrescreve blocos 3/5
        # com janela [data 00:00, data+1 00:00) — fórmulas canônicas v1.
        data_dia = _resolve_data_24h(date_24h, agora)
        ontem = (agora.replace(hour=0, minute=0, second=0, microsecond=0,
                                 tzinfo=None) - timedelta(days=1))
        if data_dia.date() != ontem.date():
            try:
                b3, b5 = _recompute_blocos_24h(stored_data, data_dia)
            except Exception:
                logger.exception("KPI v2 BR-02b: falha recompute blocos 3/5")

        # Séries de barras — paradigma Indicators-V2. Reusa funções canônicas v1.
        eq_ids = stored_data.get("equipment_ids") if isinstance(stored_data, dict) else []
        try:
            monthly_series = build_monthly_series_for_year(
                year=agora.year, equipment_ids=eq_ids or [],
                current_month=agora.month,
            )
        except Exception:
            logger.exception("KPI v2 tab: monthly_series falhou")
            monthly_series = None
        try:
            # BR-02b: série diária encerra no dia escolhido (= último item destacado)
            daily_series = build_daily_series_last_n_ending(
                end_day=data_dia, n_days=7, equipment_ids=eq_ids or [],
            )
        except Exception:
            logger.exception("KPI v2 tab: daily_series falhou")
            daily_series = None

        # Label do dia escolhido (substitui texto "Últimas 24h" quando custom)
        label_24h = "Últimas 24h"
        if data_dia.date() != ontem.date():
            label_24h = f"24h de {data_dia.strftime('%d/%m/%Y')}"

        # Mesma ordem do Tab 4 v1 — alinhada ao template DOCX (2026-05-13).
        # Diferença: bar charts (paradigma Indicators-V2) no lugar de sunbursts.
        content = html.Div([
            _section(
                "KPIs da Planta (Mês Corrente)",
                _row_3_kpis(b1.get("kpis_planta", {}),
                            b1.get("metas", {}),
                            b1.get("cores_kpis", {})),
                _row_3_bars(monthly_series, b1.get("metas", {})),
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
                f"KPIs {label_24h}",
                _row_3_kpis(b3.get("kpis_planta", {}),
                            b3.get("metas", {}),
                            b3.get("cores_kpis", {})),
                _row_3_bars(daily_series, b3.get("metas", {})),
            ),
            _section(
                f"Todas as Paradas — {label_24h}",
                html.Div(
                    _tabela_top_paradas(
                        b5.get("paradas", []), b5.get("vazio", True),
                        "Sem paradas no dia selecionado.",
                    ),
                    style={"maxHeight": "500px", "overflowY": "auto"},
                ),
            ),
        ])

        # store-kpi-v2-data: marca disponível pra habilitar export (C11 desabilita
        # botões enquanto for None/empty). Não precisa serializar dados pesados —
        # callbacks de export coletam novamente com as_png=True.
        ready_marker = {"ready": True, "rotulo": rotulo}

        # Perf #5 — pré-aquece export cache em background. User clicar Exportar
        # PDF/DOCX dentro de 60s = cache hit ~1s.
        try:
            from src.callbacks_registers.kpi_report_v2_callbacks import (
                _kickoff_export_prewarm,
            )
            _kickoff_export_prewarm(stored_data, agora)
        except Exception:
            logger.warning("KPI v2 tab: falha ao spawnar prewarm (silent)")

        return content, rotulo, ready_marker
