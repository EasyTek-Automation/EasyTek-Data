"""
Maintenance KPI Callbacks
Callbacks para a página de indicadores de manutenção
"""

import logging
from dash import Output, Input, State, dcc, html, no_update
from dash.exceptions import PreventUpdate
import dash
import dash_bootstrap_components as dbc
import pandas as pd
from src.config.theme_config import TEMPLATE_THEME_MINTY

logger = logging.getLogger(__name__)

# Verificação de saúde do MongoDB
from src.database.connection import get_connection_status, reconnect_mongodb

# Importar funções de cálculo e agregação (mantidas para processar dados ZPP)
from src.utils.maintenance_demo_data import (
    calculate_kpi_averages,
    calculate_general_avg_by_month,
    get_kpi_targets,
    get_all_equipment_targets
)

# Importar funções de integração com ZPP
try:
    from src.utils.zpp_kpi_calculator import (
        fetch_zpp_kpi_data,
        get_zpp_equipment_names,
        get_zpp_equipment_categories,
        fetch_top_breakdowns_by_equipment,
        get_zpp_data_coverage,
    )
    ZPP_KPI_AVAILABLE = True
except ImportError:
    ZPP_KPI_AVAILABLE = False

from src.components.maintenance_kpi_graphs import (
    create_kpi_bar_chart,
    create_kpi_sunburst_chart,
    create_kpi_summary_table,
    create_empty_kpi_figure,
    create_no_data_figure,
    create_kpi_line_chart,
    create_performance_radar_chart,
    create_breakdown_calendar_heatmap,
    create_top_breakdowns_chart,
    create_kpi_gauge
)


# ==================== CONFIGURAÇÃO DE EQUIPAMENTOS ====================

# Equipamentos excluídos dos GRÁFICOS por padrão (mas incluídos nos cards gerais da planta)
# NOTA: Para reincluir um equipamento, basta removê-lo desta lista
# Exemplo: Para incluir DECAP001, mude para: EQUIPMENT_EXCLUDED_BY_DEFAULT = []
EQUIPMENT_EXCLUDED_BY_DEFAULT = ["DECAP001"]

# =====================================================================


def register_maintenance_kpi_callbacks(app):
    """
    Registra todos os callbacks da página de indicadores de manutenção.

    Args:
        app: Instância do Dash app
    """

    # ============================================================
    # CALLBACK 1: Visibilidade Condicional dos Filtros
    # ============================================================
    @app.callback(
        [
            Output("div-reference-year", "style"),
            Output("div-date-range", "style")
        ],
        Input("filter-period-type", "value")
    )
    def toggle_filter_visibility(period_type):
        """
        Mostra/esconde filtros baseado no tipo de período selecionado.

        - year ou last12: Mostra ano referência, esconde date picker
        - custom: Esconde ano referência, mostra date picker
        """
        if period_type in ["year", "last12"]:
            return {"display": "block"}, {"display": "none"}
        else:  # custom
            return {"display": "none"}, {"display": "block"}

    # ============================================================
    # CALLBACK 1B: Popular Dropdown de Equipamentos
    # ============================================================
    @app.callback(
        [
            Output("filter-equipment-selection", "options"),
            Output("filter-equipment-selection", "value")
        ],
        Input("store-indicator-filters", "data")
    )
    def populate_equipment_filter(stored_data):
        """
        Popula dropdown de equipamentos com lista dinâmica.
        Por padrão, seleciona todos EXCETO os equipamentos em EQUIPMENT_EXCLUDED_BY_DEFAULT.
        """
        if not stored_data or not stored_data.get("has_data"):
            return [], []

        equipment_ids = stored_data.get("equipment_ids", [])
        names = stored_data.get("names", {})

        # Criar options com nomes amigáveis
        options = [
            {"label": names.get(eq_id, eq_id), "value": eq_id}
            for eq_id in equipment_ids
        ]

        # Valor padrão: todos EXCETO os excluídos por padrão
        default_value = [
            eq_id for eq_id in equipment_ids
            if eq_id not in EQUIPMENT_EXCLUDED_BY_DEFAULT
        ]

        return options, default_value

    # ============================================================
    # CALLBACK 2: Processar Filtros e Gerar Dados
    # ============================================================
    @app.callback(
        Output("store-indicator-filters", "data"),
        [
            Input("btn-apply-indicator-filters", "n_clicks"),
            Input("interval-initial-load", "n_intervals")  # Carrega automaticamente
        ],
        [
            State("filter-period-type", "value"),
            State("filter-reference-year", "value"),
            State("filter-date-range", "start_date"),
            State("filter-date-range", "end_date"),
            State("filter-equipment-selection", "value"),
            State("filter-breakdown-codes", "value"),
            State("store-indicator-filters", "data")
        ]
    )
    def process_filters_and_load_data(n_clicks, n_intervals,
                                      period_type, ref_year,
                                      start_date, end_date,
                                      selected_equipment, selected_breakdown_codes,
                                      current_data):
        """
        Processa filtros e gera dados baseado no tipo de período.

        Lógica:
        - year: Gera dados de todos os meses do ano selecionado
        - last12: Gera dados dos últimos 12 meses a partir do ano ref
        - custom: Gera dados do período start_date até end_date
        """
        logger.debug("Callback iniciado (n_clicks=%s, n_intervals=%s)", n_clicks, n_intervals)

        ctx = dash.callback_context

        if not ctx.triggered:
            logger.debug("PreventUpdate (ctx not triggered)")
            raise PreventUpdate

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
        logger.debug("Disparado por '%s'", trigger_id)

        # Se interval disparou e NÃO há dados ainda, carregar dados iniciais
        # Se botão apply foi clicado, sempre recarregar
        # ⚠️ VERIFICAÇÃO CRÍTICA: MongoDB disponível?
        db_status = get_connection_status()
        logger.debug("MongoDB status = %s", db_status["available"])

        if not db_status["available"]:
            logger.warning("MongoDB indisponível - retornando dados vazios")
            return {
                "has_data": False,
                "db_error": True,
                "error_message": db_status.get("error", "MongoDB indisponível"),
                "period_type": period_type or "last12",
                "year": ref_year or 2026,
                "months": list(range(1, 13)),
                "equipment_ids": [],
                "data": {},
                "targets": {},
                "equipment_targets": {},
                "names": {},
                "categories": {}
            }

        # Sempre fazer recarga completa — sem cache condicional.
        # O store usa storage_type='memory', então já é limpo no refresh da página.
        # Cache condicional causava dados desatualizados e race conditions.

        # Validar inputs baseado no tipo
        # Padrão: sempre usar modo "year" (ano completo)
        if not period_type:
            period_type = "year"

        if not ref_year:
            ref_year = 2026  # Ano padrão onde os dados ZPP estão disponíveis

        from datetime import datetime as _datetime
        from src.utils.zpp_kpi_calculator import _get_month_periods

        # ── Calcular start_date_dt / end_date_dt para todos os tipos de período ──
        # Suporta ranges multi-ano (ex: Out/2025 → Fev/2026) sem truncar no fim do ano.
        if period_type == "year":
            year = ref_year
            start_date_dt = _datetime(year, 1, 1)
            end_date_dt = _datetime(year, 12, 31, 23, 59, 59)
            period_start = f"{year}-01-01"
            period_end = f"{year}-12-31"

        elif period_type == "custom":
            if not start_date or not end_date:
                # Fallback: usar ano completo
                year = ref_year
                start_date_dt = _datetime(year, 1, 1)
                end_date_dt = _datetime(year, 12, 31, 23, 59, 59)
                period_start = f"{year}-01-01"
                period_end = f"{year}-12-31"
            else:
                start_date_dt = _datetime.fromisoformat(start_date) if isinstance(start_date, str) else start_date
                end_date_dt = _datetime.fromisoformat(end_date) if isinstance(end_date, str) else end_date
                period_start = start_date if isinstance(start_date, str) else start_date.isoformat()
                period_end = end_date if isinstance(end_date, str) else end_date.isoformat()
                year = start_date_dt.year  # Ano de início (para compatibilidade em display)

        else:
            # Fallback: ano completo
            year = ref_year
            start_date_dt = _datetime(year, 1, 1)
            end_date_dt = _datetime(year, 12, 31, 23, 59, 59)
            period_start = f"{year}-01-01"
            period_end = f"{year}-12-31"

        # Derivar months e year_months a partir do range completo (suporta multi-ano)
        all_periods = _get_month_periods(start_date_dt, end_date_dt)
        months = sorted(set(m for (_, m) in all_periods))            # Flat ints (para labels)
        year_months = [f"{y}-{m:02d}" for (y, m) in all_periods]    # "YYYY-MM" (filtro preciso)

        # Buscar dados reais - INTEGRAÇÃO ZPP
        data = {}
        all_equipment = []
        has_data = False

        logger.debug(
            "ZPP_KPI_AVAILABLE=%s, buscando dados %s → %s (%d períodos)",
            ZPP_KPI_AVAILABLE, start_date_dt.date(), end_date_dt.date(), len(all_periods)
        )

        # Normalizar lista de códigos selecionados
        from src.utils.zpp_kpi_calculator import BREAKDOWN_CODES as _DEFAULT_CODES
        active_codes = selected_breakdown_codes if selected_breakdown_codes else _DEFAULT_CODES

        if ZPP_KPI_AVAILABLE:
            try:
                # Tentar buscar dados reais do ZPP (com filtro de códigos selecionados)
                data = fetch_zpp_kpi_data(start_date_dt, end_date_dt, breakdown_codes=active_codes)
                all_equipment = list(data.keys())
                has_data = len(data) > 0

                logger.info("Dados ZPP carregados: %d equipamentos", len(all_equipment))

                if has_data:
                    logger.debug("Equipamentos: %s", all_equipment)
                else:
                    logger.warning("fetch_zpp_kpi_data retornou vazio")
            except Exception as e:
                # Sem fallback - apenas informar erro
                logger.error("Erro ao buscar dados ZPP: %s", str(e), exc_info=True)
                import traceback
                traceback.print_exc()
                has_data = False
        else:
            logger.warning("ZPP_KPI_AVAILABLE=False, sem integração ZPP")
            has_data = False

        # Buscar nomes e categorias de equipamentos
        if has_data and ZPP_KPI_AVAILABLE:
            try:
                names = get_zpp_equipment_names()
                categories = get_zpp_equipment_categories()

                logger.debug("Nomes carregados: %d equipamentos", len(names))
                logger.info("Categorias carregadas: %d categorias", len(categories))

                if categories:
                    for cat_name, cat_equipments in categories.items():
                        logger.debug(
                            "  Categoria '%s': %d equipamentos",
                            cat_name, len(cat_equipments)
                        )
                else:
                    logger.warning("get_zpp_equipment_categories() retornou vazio")

            except Exception as e:
                logger.error(
                    "Erro ao carregar nomes/categorias: %s",
                    str(e),
                    exc_info=True
                )
                names = {eq: eq for eq in all_equipment}
                categories = {}
        else:
            logger.debug("Usando nomes/categorias vazias (has_data=%s, ZPP_AVAILABLE=%s)",
                        has_data, ZPP_KPI_AVAILABLE)
            names = {}
            categories = {}

        # Obter metas individualizadas por equipamento
        # SEMPRE carregar metas, mesmo se não houver dados (para evitar erros nos callbacks)
        equipment_targets = get_all_equipment_targets()
        general_target = get_kpi_targets("GENERAL")

        # OTIMIZAÇÃO: Calcular monthly_aggregates UMA VEZ e cachear no store
        # Isso evita múltiplas chamadas ao MongoDB nos callbacks seguintes
        monthly_aggregates = None
        if has_data:
            from src.utils.maintenance_demo_data import calculate_general_avg_by_month
            try:
                monthly_aggregates = calculate_general_avg_by_month(
                    data, all_equipment,
                    start_date=start_date_dt, end_date=end_date_dt
                )
            except Exception as e:
                monthly_aggregates = None

        # Cobertura de dados: último dia e nº de dias distintos em cada collection
        data_coverage = {}
        if has_data and ZPP_KPI_AVAILABLE:
            try:
                data_coverage = get_zpp_data_coverage(
                    start_date_dt, end_date_dt, breakdown_codes=active_codes
                )
            except Exception as e:
                logger.error("Erro ao buscar cobertura ZPP: %s", e)

        # Processar seleção de equipamentos para gráficos
        if not selected_equipment or len(selected_equipment) == 0:
            selected_equipment_ids = [
                eq for eq in all_equipment
                if eq not in EQUIPMENT_EXCLUDED_BY_DEFAULT
            ]
        else:
            selected_equipment_ids = [eq for eq in selected_equipment if eq in all_equipment]

        logger.debug(
            "Armazenando no store: %d equipamentos total, %d selecionados para gráficos, %d categorias",
            len(all_equipment), len(selected_equipment_ids), len(categories)
        )

        if categories:
            logger.debug("Categorias: %s", list(categories.keys()))
        else:
            logger.warning("Store será salvo SEM categorias")

        return {
            "period_type": period_type,
            "period_start": period_start,
            "period_end": period_end,
            "start_date": start_date_dt.isoformat(),   # Novo: datetime de início do período
            "end_date": end_date_dt.isoformat(),        # Novo: datetime de fim do período
            "year": year,                               # Ano de início (compatibilidade display)
            "months": months,                           # Meses únicos flat (compatibilidade labels)
            "year_months": year_months,                 # "YYYY-MM" para filtro multi-ano preciso
            "equipment_ids": all_equipment,
            "selected_equipment_ids": selected_equipment_ids,
            "data": data,
            "targets": general_target,
            "equipment_targets": equipment_targets,
            "names": names,
            "categories": categories,
            "has_data": has_data,
            "monthly_aggregates": monthly_aggregates,
            "data_coverage": data_coverage,
            "selected_breakdown_codes": active_codes,
        }

    # ============================================================
    # CALLBACK 3: Atualizar Summary Cards
    # ============================================================
    _MONTH_NAMES_PT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                       "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

    def _build_period_label(period_start, period_end, period_type):
        """Constrói o componente de rótulo do período analisado com datas completas."""
        from datetime import datetime as _dt
        try:
            s = _dt.fromisoformat(period_start)
            e = _dt.fromisoformat(period_end)
        except (TypeError, ValueError):
            return None

        sm = _MONTH_NAMES_PT[s.month - 1]
        em = _MONTH_NAMES_PT[e.month - 1]

        if s.year == e.year:
            date_text = f"{s.day:02d}/{sm} a {e.day:02d}/{em}/{e.year}"
        else:
            date_text = f"{s.day:02d}/{sm}/{s.year} a {e.day:02d}/{em}/{e.year}"

        type_label = {
            "year": "Ano completo",
            "last12": "Últimos 12 meses",
            "custom": "Período personalizado",
        }.get(period_type, "Período")

        return html.Span([
            html.I(className="bi bi-calendar3 me-2"),
            html.Strong(f"{type_label}: "),
            date_text
        ], className="text-muted small")

    @app.callback(
        [
            Output("period-analysis-label", "children"),
            Output("summary-mtbf-value", "children"),
            Output("summary-mtbf-badge", "children"),
            Output("summary-mtbf-badge", "color"),
            Output("summary-mttr-value", "children"),
            Output("summary-mttr-badge", "children"),
            Output("summary-mttr-badge", "color"),
            Output("summary-breakdown-value", "children"),
            Output("summary-breakdown-badge", "children"),
            Output("summary-breakdown-badge", "color"),
            Output("summary-equipment-count", "children")
        ],
        Input("store-indicator-filters", "data")
    )
    def update_summary_cards(stored_data):
        """
        Atualiza os 4 cards de resumo com médias gerais comparadas com meta da planta.
        """
        _no_data_period = html.Span(
            [html.I(className="bi bi-calendar3 me-2"), "Período: —"],
            className="text-muted small"
        )

        # Verificar se MongoDB está offline
        if stored_data and stored_data.get("db_error"):
            return [_no_data_period] + ["--"] * 3 + ["BD Offline", "danger"] * 3 + ["0"]

        if not stored_data or not stored_data.get("has_data", False):
            return [_no_data_period] + ["--"] * 3 + ["Sem dados", "secondary"] * 3 + ["0"]

        data = stored_data["data"]
        equipment_targets = stored_data["equipment_targets"]  # ALTERADO
        equipment_ids = stored_data["equipment_ids"]
        months = stored_data["months"]
        year = stored_data.get("year", 2026)
        monthly_aggregates = stored_data.get("monthly_aggregates")

        # Calcular médias (usando cache de monthly_aggregates do store)
        averages = calculate_kpi_averages(data, equipment_ids, months, year=year, monthly_aggregates=monthly_aggregates, year_months=stored_data.get("year_months"))

        # Se não houver médias válidas após o cálculo
        if not averages.get("by_equipment"):
            return [_no_data_period] + ["--"] * 3 + ["Sem dados", "secondary"] * 3 + ["0"]

        # Importar função helper para cores simplificadas
        from src.components.maintenance_kpi_graphs import get_kpi_color

        # Usar meta geral da planta (GENERAL) para os cards de resumo
        general_target = equipment_targets.get("GENERAL", {"mtbf": 0, "mttr": 999, "breakdown_rate": 100, "alert_range": 3.0})
        alert_range = general_target.get("alert_range", 3.0)

        # Sistema de cores simplificado (3 cores com margem dinâmica)
        # Verde: Melhor e fora da margem
        # Amarelo: Dentro de ±alert_range% da meta
        # Vermelho: Pior e fora da margem

        # MTBF (maior é melhor)
        mtbf_avg = averages["mtbf"]
        mtbf_color_hex = get_kpi_color(mtbf_avg, general_target["mtbf"], "MTBF", margin_percent=alert_range)
        if mtbf_color_hex == "#198754":  # Verde
            mtbf_badge_text = "✓ Muito Acima"
            mtbf_badge_color = "success"
        elif mtbf_color_hex == "#ffc107":  # Amarelo
            mtbf_badge_text = "≈ Dentro da Meta"
            mtbf_badge_color = "warning"
        else:  # Vermelho
            mtbf_badge_text = "✗ Abaixo"
            mtbf_badge_color = "danger"

        # MTTR (menor é melhor) - converter para minutos
        mttr_avg_minutes = averages["mttr"] * 60
        mttr_target_minutes = general_target["mttr"] * 60
        mttr_color_hex = get_kpi_color(mttr_avg_minutes, mttr_target_minutes, "MTTR", margin_percent=alert_range)
        if mttr_color_hex == "#198754":  # Verde
            mttr_badge_text = "✓ Muito Abaixo"
            mttr_badge_color = "success"
        elif mttr_color_hex == "#ffc107":  # Amarelo
            mttr_badge_text = "≈ Dentro da Meta"
            mttr_badge_color = "warning"
        else:  # Vermelho
            mttr_badge_text = "✗ Acima"
            mttr_badge_color = "danger"

        # Taxa de Avaria (menor é melhor)
        breakdown_avg = averages["breakdown_rate"]
        breakdown_color_hex = get_kpi_color(breakdown_avg, general_target["breakdown_rate"], "breakdown_rate", margin_percent=alert_range)
        if breakdown_color_hex == "#198754":  # Verde
            breakdown_badge_text = "✓ Muito Abaixo"
            breakdown_badge_color = "success"
        elif breakdown_color_hex == "#ffc107":  # Amarelo
            breakdown_badge_text = "≈ Dentro da Meta"
            breakdown_badge_color = "warning"
        else:  # Vermelho
            breakdown_badge_text = "✗ Acima"
            breakdown_badge_color = "danger"

        # Contagem de equipamentos
        eq_count = len(equipment_ids)

        target_style = {"fontSize": "0.65em", "color": "#6c757d", "fontWeight": "normal"}

        mtbf_display = [
            f"{mtbf_avg:.1f} h",
            html.Span(f" / {general_target['mtbf']:.1f} h", style=target_style)
        ]
        mttr_display = [
            f"{mttr_avg_minutes:.1f} min",
            html.Span(f" / {mttr_target_minutes:.1f} min", style=target_style)
        ]
        breakdown_display = [
            f"{breakdown_avg:.2f} %",
            html.Span(f" / {general_target['breakdown_rate']:.2f} %", style=target_style)
        ]

        period_label = _build_period_label(
            stored_data.get("period_start"),
            stored_data.get("period_end"),
            stored_data.get("period_type", "year")
        )

        return [
            period_label,
            mtbf_display,
            mtbf_badge_text,
            mtbf_badge_color,
            mttr_display,
            mttr_badge_text,
            mttr_badge_color,
            breakdown_display,
            breakdown_badge_text,
            breakdown_badge_color,
            f"{eq_count}"
        ]

    # ============================================================
    # CALLBACK 4: Atualizar Gráficos de Barras
    # ============================================================
    @app.callback(
        [
            Output("bar-chart-mtbf", "figure"),
            Output("bar-chart-mttr", "figure"),
            Output("bar-chart-breakdown", "figure")
        ],
        [
            Input("store-indicator-filters", "data")
        ]
    )
    def update_bar_charts(stored_data):
        """
        Atualiza os 3 gráficos de barras com médias e metas individualizadas.
        """

        template = TEMPLATE_THEME_MINTY  # Tema fixo em Minty (claro)

        if not stored_data:
            return [
                create_empty_kpi_figure("MTBF", template),
                create_empty_kpi_figure("MTTR", template),
                create_empty_kpi_figure("Taxa de Avaria", template)
            ]

        # ⚠️ Verificar se há erro de banco de dados
        if stored_data.get("db_error"):
            from src.components.maintenance_kpi_graphs import create_database_error_figure
            error_msg = stored_data.get("error_message", "Banco de dados offline")
            return [
                create_database_error_figure("MTBF", error_msg, template),
                create_database_error_figure("MTTR", error_msg, template),
                create_database_error_figure("Taxa de Avaria", error_msg, template)
            ]

        data = stored_data["data"]
        equipment_targets = stored_data["equipment_targets"]  # ALTERADO: Usar metas por equipamento
        names = stored_data["names"]
        # IMPORTANTE: Usar equipamentos SELECIONADOS para gráficos (exclui DECAP001 por padrão)
        equipment_ids = stored_data.get("selected_equipment_ids", stored_data["equipment_ids"])
        months = stored_data["months"]
        year = stored_data.get("year", 2026)
        monthly_aggregates = stored_data.get("monthly_aggregates")

        for idx, eq_id in enumerate(equipment_ids[:2]):
            eq_data = data.get(eq_id, [])

        # Calcular médias por equipamento (usando cache de monthly_aggregates do store)
        averages = calculate_kpi_averages(data, equipment_ids, months, year=year, monthly_aggregates=monthly_aggregates, year_months=stored_data.get("year_months"))

        # Verificar se há dados válidos
        if not averages.get("by_equipment"):
            return [
                create_no_data_figure("barra", template),
                create_no_data_figure("barra", template),
                create_no_data_figure("barra", template)
            ]

        # Preparar dados para gráficos (filtrar equipamentos sem dados válidos)
        # Só incluir equipamentos que têm pelo menos um KPI válido (não None)
        valid_equipment = [
            eq for eq in equipment_ids
            if eq in averages["by_equipment"] and (
                averages["by_equipment"][eq]["mtbf"] is not None or
                averages["by_equipment"][eq]["mttr"] is not None or
                averages["by_equipment"][eq]["breakdown_rate"] is not None
            )
        ]

        if not valid_equipment:
            return [
                create_no_data_figure("barra", template),
                create_no_data_figure("barra", template),
                create_no_data_figure("barra", template)
            ]

        # Usar apenas equipamentos válidos
        equipment_ids = valid_equipment
        mtbf_values = [averages["by_equipment"][eq]["mtbf"] for eq in equipment_ids]
        mttr_values = [averages["by_equipment"][eq]["mttr"] for eq in equipment_ids]
        breakdown_values = [averages["by_equipment"][eq]["breakdown_rate"] for eq in equipment_ids]

        # Preparar dicionários de metas individuais por equipamento
        # Fallback para meta geral se equipamento não tiver meta específica
        general_target = equipment_targets.get("GENERAL", {"mtbf": 0, "mttr": 999, "breakdown_rate": 100, "alert_range": 3.0})
        alert_range = general_target.get("alert_range", 3.0)

        mtbf_targets = {}
        mttr_targets = {}
        breakdown_targets = {}

        for eq_id in equipment_ids:
            eq_target = equipment_targets.get(eq_id, general_target)
            mtbf_targets[eq_id] = eq_target.get("mtbf", general_target["mtbf"])
            mttr_targets[eq_id] = eq_target.get("mttr", general_target["mttr"])
            breakdown_targets[eq_id] = eq_target.get("breakdown_rate", general_target["breakdown_rate"])

        # Criar gráficos com metas individualizadas
        # IMPORTANTE: A linha tracejada mostra a META DA PLANTA, não a média geral
        fig_mtbf = create_kpi_bar_chart(
            equipment_ids, mtbf_values, "MTBF",
            averages["mtbf"], mtbf_targets,
            names, template,
            plant_target=general_target["mtbf"],
            margin_percent=alert_range
        )

        fig_mttr = create_kpi_bar_chart(
            equipment_ids, mttr_values, "MTTR",
            averages["mttr"], mttr_targets,
            names, template,
            plant_target=general_target["mttr"],
            margin_percent=alert_range
        )

        fig_breakdown = create_kpi_bar_chart(
            equipment_ids, breakdown_values, "Taxa de Avaria",
            averages["breakdown_rate"], breakdown_targets,
            names, template,
            plant_target=general_target["breakdown_rate"],
            margin_percent=alert_range
        )

        return [fig_mtbf, fig_mttr, fig_breakdown]

    # ============================================================
    # CALLBACK 5: Atualizar Sunbursts
    # ============================================================
    @app.callback(
        [
            Output("sunburst-chart-mtbf", "figure"),
            Output("sunburst-chart-mttr", "figure"),
            Output("sunburst-chart-breakdown", "figure")
        ],
        [
            Input("store-indicator-filters", "data")
        ]
    )
    def update_sunburst_charts(stored_data):
        """
        Atualiza os 3 gráficos Sunburst hierárquicos.
        """
        import plotly.graph_objects as go

        template = TEMPLATE_THEME_MINTY  # Tema fixo em Minty (claro)

        if not stored_data or not stored_data.get("has_data", False):
            # Retornar sunbursts com mensagem de sem dados
            return [
                create_no_data_figure("sunburst", template),
                create_no_data_figure("sunburst", template),
                create_no_data_figure("sunburst", template)
            ]

        data = stored_data["data"]
        names = stored_data["names"]
        categories = stored_data["categories"]
        # IMPORTANTE: Usar equipamentos SELECIONADOS para gráficos (exclui DECAP001 por padrão)
        equipment_ids = stored_data.get("selected_equipment_ids", stored_data["equipment_ids"])
        months = stored_data["months"]
        equipment_targets = stored_data.get("equipment_targets", {})
        year = stored_data.get("year", 2026)
        monthly_aggregates = stored_data.get("monthly_aggregates")

        # Log diagnóstico: verificar o que foi recuperado do store
        logger.debug(
            "Sunburst recebeu: %d equipamentos selecionados, %d categorias",
            len(equipment_ids), len(categories)
        )

        if categories:
            logger.debug("Categorias: %s", list(categories.keys()))
            for cat_name, cat_equipments in categories.items():
                logger.debug("  '%s': %d equipamentos", cat_name, len(cat_equipments))
        else:
            logger.warning("Sunburst recebeu categorias VAZIO do store")

        # Calcular médias por equipamento SELECIONADO (usando cache de monthly_aggregates do store)
        averages = calculate_kpi_averages(data, equipment_ids, months, year=year, monthly_aggregates=monthly_aggregates, year_months=stored_data.get("year_months"))

        if not averages.get("by_equipment"):
            return [
                create_no_data_figure("sunburst", template),
                create_no_data_figure("sunburst", template),
                create_no_data_figure("sunburst", template)
            ]

        # Preparar dados para sunbursts (apenas equipamentos que existem em by_equipment)
        mtbf_by_eq = {
            eq: averages["by_equipment"][eq]["mtbf"]
            for eq in equipment_ids
            if eq in averages["by_equipment"]
        }
        mttr_by_eq = {
            eq: averages["by_equipment"][eq]["mttr"]
            for eq in equipment_ids
            if eq in averages["by_equipment"]
        }
        breakdown_by_eq = {
            eq: averages["by_equipment"][eq]["breakdown_rate"]
            for eq in equipment_ids
            if eq in averages["by_equipment"]
        }

        # Obter meta geral da planta
        general_target = equipment_targets.get("GENERAL", {"mtbf": 0, "mttr": 999, "breakdown_rate": 100, "alert_range": 3.0})
        alert_range = general_target.get("alert_range", 3.0)

        # Preparar dicionários de metas por equipamento
        mtbf_targets = {eq_id: equipment_targets.get(eq_id, general_target).get("mtbf", general_target["mtbf"])
                       for eq_id in equipment_ids}
        mttr_targets = {eq_id: equipment_targets.get(eq_id, general_target).get("mttr", general_target["mttr"])
                       for eq_id in equipment_ids}
        breakdown_targets = {eq_id: equipment_targets.get(eq_id, general_target).get("breakdown_rate", general_target["breakdown_rate"])
                            for eq_id in equipment_ids}

        # Criar sunbursts com cores baseadas na META GERAL DA PLANTA
        # Passar plant_average para que o centro mostre média dos valores mensais
        fig_mtbf = create_kpi_sunburst_chart(
            mtbf_by_eq, "MTBF", categories, names, template,
            target_values=mtbf_targets,
            plant_target=general_target["mtbf"],
            margin_percent=alert_range,
            plant_average=averages["mtbf"]  # Média dos valores mensais
        )

        fig_mttr = create_kpi_sunburst_chart(
            mttr_by_eq, "MTTR", categories, names, template,
            target_values=mttr_targets,
            plant_target=general_target["mttr"],
            margin_percent=alert_range,
            plant_average=averages["mttr"]  # Média dos valores mensais (em horas)
        )

        fig_breakdown = create_kpi_sunburst_chart(
            breakdown_by_eq, "Taxa de Avaria", categories, names, template,
            target_values=breakdown_targets,
            plant_target=general_target["breakdown_rate"],
            margin_percent=alert_range,
            plant_average=averages["breakdown_rate"]  # Média dos valores mensais
        )

        return [fig_mtbf, fig_mttr, fig_breakdown]

    # ============================================================
    # CALLBACK 5B: Atualizar Gráficos de Linha Gerais (Evolução Temporal da Planta)
    # ============================================================
    @app.callback(
        [
            Output("line-chart-mtbf-general", "figure"),
            Output("line-chart-mttr-general", "figure"),
            Output("line-chart-breakdown-general", "figure")
        ],
        [
            Input("store-indicator-filters", "data")
        ]
    )
    def update_general_line_charts(stored_data):
        """
        Atualiza os 3 gráficos de linha mostrando a evolução mensal da planta toda.
        """
        template = TEMPLATE_THEME_MINTY  # Tema fixo em Minty (claro)

        if not stored_data or not stored_data.get("has_data", False):
            return [
                create_no_data_figure("linha", template),
                create_no_data_figure("linha", template),
                create_no_data_figure("linha", template)
            ]

        data = stored_data["data"]
        equipment_ids = stored_data["equipment_ids"]
        months = stored_data["months"]
        year_months = stored_data.get("year_months") or [f"{stored_data.get('year', 2026)}-{m:02d}" for m in months]
        equipment_targets = stored_data.get("equipment_targets", {})

        from datetime import datetime as _dt
        _sd = stored_data.get("start_date")
        _ed = stored_data.get("end_date")
        _start_dt = _dt.fromisoformat(_sd) if _sd else None
        _end_dt = _dt.fromisoformat(_ed) if _ed else None

        # Calcular médias gerais por mês (AGREGANDO dados brutos, suporta multi-ano)
        general_avg_by_month = calculate_general_avg_by_month(
            data, equipment_ids,
            start_date=_start_dt, end_date=_end_dt
        )

        if not general_avg_by_month:
            return [
                create_no_data_figure("linha", template),
                create_no_data_figure("linha", template),
                create_no_data_figure("linha", template)
            ]

        # Extrair valores na ordem cronológica dos year_months
        mtbf_values = [general_avg_by_month[ym]["mtbf"] for ym in year_months if ym in general_avg_by_month]
        mttr_values = [general_avg_by_month[ym]["mttr"] for ym in year_months if ym in general_avg_by_month]
        breakdown_values = [general_avg_by_month[ym]["breakdown_rate"] for ym in year_months if ym in general_avg_by_month]
        # Meses presentes nos dados (para labels no eixo X)
        months_present = [int(ym.split("-")[1]) for ym in year_months if ym in general_avg_by_month]

        # Obter meta geral da planta
        general_target = equipment_targets.get("GENERAL", {"mtbf": 0, "mttr": 999, "breakdown_rate": 100, "alert_range": 3.0})
        alert_range = general_target.get("alert_range", 3.0)

        # Criar gráficos de linha (sem linha de média, pois JÁ É a média da planta)
        fig_mtbf = create_kpi_line_chart(
            months_present, mtbf_values, None,
            "MTBF", "Média da Planta",
            general_target.get("mtbf", 0),
            template,
            margin_percent=alert_range
        )

        fig_mttr = create_kpi_line_chart(
            months_present, mttr_values, None,
            "MTTR", "Média da Planta",
            general_target.get("mttr", 999),
            template,
            margin_percent=alert_range
        )

        fig_breakdown = create_kpi_line_chart(
            months_present, breakdown_values, None,
            "Taxa de Avaria", "Média da Planta",
            general_target.get("breakdown_rate", 100),
            template,
            margin_percent=alert_range
        )

        return [fig_mtbf, fig_mttr, fig_breakdown]

    # ============================================================
    # CALLBACK 6: Atualizar Tabela Resumo
    # ============================================================
    @app.callback(
        Output("kpi-summary-table-container", "children"),
        Input("store-indicator-filters", "data")
    )
    def update_summary_table(stored_data):
        """
        Atualiza a tabela resumo com todos os KPIs por equipamento com metas individualizadas.
        """
        if not stored_data or not stored_data.get("has_data", False):
            return html.Div([
                html.I(className="bi bi-inbox fs-1 text-muted mb-3"),
                html.P(
                    "Nenhum dado de manutenção disponível no banco de dados.",
                    className="text-muted text-center"
                ),
                html.Small(
                    "Os dados são carregados automaticamente quando disponíveis no sistema.",
                    className="text-muted text-center d-block"
                )
            ], className="text-center py-5")

        data = stored_data["data"]
        equipment_targets = stored_data["equipment_targets"]  # ALTERADO: Usar metas por equipamento
        names = stored_data["names"]
        # IMPORTANTE: Usar equipamentos SELECIONADOS para tabela (exclui DECAP001 por padrão)
        equipment_ids = stored_data.get("selected_equipment_ids", stored_data["equipment_ids"])
        months = stored_data["months"]
        year = stored_data.get("year", 2026)
        monthly_aggregates = stored_data.get("monthly_aggregates")

        # Calcular médias por equipamento (usando cache de monthly_aggregates do store)
        averages = calculate_kpi_averages(data, equipment_ids, months, year=year, monthly_aggregates=monthly_aggregates, year_months=stored_data.get("year_months"))

        if not averages.get("by_equipment"):
            return html.Div([
                html.I(className="bi bi-inbox fs-1 text-muted mb-3"),
                html.P(
                    "Nenhum dado disponível para o período selecionado.",
                    className="text-muted text-center"
                )
            ], className="text-center py-5")

        # Criar tabela com metas individualizadas
        return create_kpi_summary_table(
            averages["by_equipment"],
            equipment_targets,  # ALTERADO: Dict de metas por equipamento
            names
        )

    # ============================================================
    # CALLBACK 6B: Aba de Dados Brutos (Conferência)
    # ============================================================
    @app.callback(
        [
            Output("raw-data-coverage-info", "children"),
            Output("raw-data-monthly-debug", "children"),
            Output("raw-data-summary-cards", "children"),
            Output("raw-data-table-container", "children"),
        ],
        [
            Input("store-indicator-filters", "data"),
            Input("indicator-tabs", "active_tab"),
        ]
    )
    def update_raw_data_tab(stored_data, active_tab):
        """
        Constrói a aba de conferência de dados brutos por equipamento.
        Agrega totais do período filtrado e recalcula KPIs a partir dos totais.
        """
        from dash import dash_table

        if active_tab != "tab-data":
            raise PreventUpdate

        _empty = html.P(
            "Sem dados disponíveis para o período selecionado.",
            className="text-muted text-center py-5"
        )

        if not stored_data or not stored_data.get("has_data", False):
            return [_empty, _empty, _empty, _empty]

        data = stored_data["data"]
        names = stored_data.get("names", {})
        categories = stored_data.get("categories", {})
        equipment_ids = stored_data.get("equipment_ids", [])  # Todos os equipamentos, igual aos cards do topo
        months = stored_data.get("months", [])
        year_months = stored_data.get("year_months")

        # Mapa reverso: eq_id → categoria
        eq_category = {
            eq: cat
            for cat, eq_list in categories.items()
            for eq in eq_list
        }

        # Agregar totais do período por equipamento
        rows = []
        for eq_id in equipment_ids:
            if eq_id not in data:
                continue
            if year_months:
                monthly_list = [m for m in data[eq_id] if m.get("year_month") in year_months]
            else:
                monthly_list = [m for m in data[eq_id] if m["month"] in months]
            if not monthly_list:
                continue

            tot_fail = sum(m.get("num_failures", 0) for m in monthly_list)
            tot_act_h = sum(m.get("total_active_hours", 0.0) for m in monthly_list)
            tot_bd_min = sum(m.get("total_breakdown_minutes", 0.0) for m in monthly_list)
            tot_bd_h = tot_bd_min / 60.0
            tot_up_h = max(tot_act_h - tot_bd_h, 0)

            # KPIs recalculados dos totais (mais preciso que média de médias)
            bd_rate = (tot_bd_h / tot_act_h * 100) if tot_act_h > 0 else None
            if tot_fail > 0:
                mtbf = (tot_act_h - tot_bd_h) / tot_fail
                mttr_min = tot_bd_min / tot_fail
            elif tot_act_h > 0:
                mtbf = tot_act_h
                mttr_min = 0.0
            else:
                mtbf = None
                mttr_min = None

            rows.append({
                "eq_id": eq_id,
                "equipamento": names.get(eq_id, eq_id),
                "categoria": eq_category.get(eq_id, "—"),
                "num_paradas": tot_fail,
                "avaria_min": round(tot_bd_min, 1),
                "avaria_h": round(tot_bd_h, 2),
                "atividade_h": round(tot_act_h, 2),
                "uptime_h": round(tot_up_h, 2),
                "mtbf_h": round(mtbf, 1) if mtbf is not None else None,
                "mttr_min": round(mttr_min, 1) if mttr_min is not None else None,
                "taxa_avaria": round(bd_rate, 2) if bd_rate is not None else None,
            })

        if not rows:
            return [_empty, _empty, _empty, _empty]

        # ── Totais da planta ─────────────────────────────────────
        # Somar os valores brutos (não os já arredondados) para máxima precisão
        p_fail   = sum(r["num_paradas"]  for r in rows)
        p_act_h  = sum(r["atividade_h"]  for r in rows)
        p_bd_min = sum(r["avaria_min"]   for r in rows)
        p_bd_h   = p_bd_min / 60.0
        p_up_h   = sum(r["uptime_h"]     for r in rows)
        p_bd_rate = round(p_bd_h / p_act_h * 100, 2) if p_act_h > 0 else None
        p_mtbf    = round((p_act_h - p_bd_h) / p_fail, 1) if p_fail > 0 else (round(p_act_h, 1) if p_act_h > 0 else None)
        p_mttr    = round(p_bd_min / p_fail, 1) if p_fail > 0 else 0.0

        def _fv(v, dec=1):
            """Formata float para string ou '—' se None."""
            return f"{v:.{dec}f}" if v is not None else "—"

        # ── Cards de resumo da planta ─────────────────────────────
        def _stat_card(icon, label, value, color):
            return dbc.Col([
                dbc.Card([dbc.CardBody([
                    html.Div([
                        html.I(className=f"bi {icon}", style={"fontSize": "1.3rem", "color": color}),
                        html.Div([
                            html.Small(label, className="text-muted d-block", style={"fontSize": "0.75rem"}),
                            html.Strong(value, style={"fontSize": "1.05rem"})
                        ], className="ms-3")
                    ], className="d-flex align-items-center")
                ])], className="shadow-sm h-100")
            ], xs=6, sm=4, md=3, lg=2, className="mb-3")

        summary_cards = dbc.Row([
            _stat_card("bi-exclamation-circle-fill", "Nº Paradas",      str(p_fail),              "#dc3545"),
            _stat_card("bi-hourglass-split",         "Avaria (min)",    f"{p_bd_min:.1f}",         "#fd7e14"),
            _stat_card("bi-hourglass-split",         "Avaria (h)",      f"{p_bd_h:.2f}",           "#fd7e14"),
            _stat_card("bi-lightning-charge-fill",   "Atividade (h)",   f"{p_act_h:.2f}",          "#0d6efd"),
            _stat_card("bi-arrow-up-circle-fill",    "Uptime (h)",      f"{p_up_h:.2f}",           "#198754"),
            _stat_card("bi-clock-history",           "MTBF (h)",        _fv(p_mtbf, 1),            "#20c997"),
            _stat_card("bi-tools",                   "MTTR (min)",      _fv(p_mttr, 1),            "#6f42c1"),
            _stat_card("bi-graph-down",              "Taxa Avaria (%)", _fv(p_bd_rate, 2),         "#ffc107"),
        ], className="g-2")

        # ── Tabela por equipamento ────────────────────────────────
        # Guardar valores como números para que o sort nativo funcione corretamente
        table_data = []
        for r in sorted(rows, key=lambda x: (x["categoria"], x["equipamento"])):
            table_data.append({
                "equipamento":  r["equipamento"],
                "categoria":    r["categoria"],
                "num_paradas":  r["num_paradas"],
                "avaria_min":   r["avaria_min"],
                "avaria_h":     r["avaria_h"],
                "atividade_h":  r["atividade_h"],
                "uptime_h":     r["uptime_h"],
                "mtbf_h":       r["mtbf_h"],   # pode ser None → DataTable mostra vazio
                "mttr_min":     r["mttr_min"],
                "taxa_avaria":  r["taxa_avaria"],
            })

        # Linha de total da planta (sempre ao final)
        table_data.append({
            "equipamento":  "TOTAL DA PLANTA",
            "categoria":    "—",
            "num_paradas":  p_fail,
            "avaria_min":   round(p_bd_min, 1),
            "avaria_h":     round(p_bd_h, 2),
            "atividade_h":  round(p_act_h, 2),
            "uptime_h":     round(p_up_h, 2),
            "mtbf_h":       p_mtbf,
            "mttr_min":     p_mttr,
            "taxa_avaria":  p_bd_rate,
        })

        def _col(name, col_id, dec=None):
            """Helper para coluna numérica com ou sem formato."""
            c = {"name": name, "id": col_id, "type": "numeric"}
            if dec is not None:
                c["format"] = {"specifier": f".{dec}f"}
            return c

        columns = [
            {"name": "Equipamento",     "id": "equipamento"},
            {"name": "Categoria",       "id": "categoria"},
            _col("Nº Paradas",      "num_paradas",  0),
            _col("Avaria (min)",    "avaria_min",   1),
            _col("Avaria (h)",      "avaria_h",     2),
            _col("Atividade (h)",   "atividade_h",  2),
            _col("Uptime (h)",      "uptime_h",     2),
            _col("MTBF (h)",        "mtbf_h",       1),
            _col("MTTR (min)",      "mttr_min",     1),
            _col("Taxa Avaria (%)", "taxa_avaria",  2),
        ]

        table = dash_table.DataTable(
            columns=columns,
            data=table_data,
            sort_action="native",
            style_table={"overflowX": "auto"},
            style_cell={
                "textAlign": "center",
                "padding": "8px 14px",
                "fontFamily": "inherit",
                "fontSize": "0.85rem",
                "borderBottom": "1px solid #dee2e6",
            },
            style_cell_conditional=[
                {"if": {"column_id": "equipamento"}, "textAlign": "left", "fontWeight": "500", "minWidth": "130px"},
                {"if": {"column_id": "categoria"},   "textAlign": "left", "minWidth": "110px"},
            ],
            style_header={
                "backgroundColor": "#f8f9fa",
                "fontWeight": "bold",
                "borderBottom": "2px solid #dee2e6",
                "fontSize": "0.8rem",
                "textAlign": "center",
            },
            style_data_conditional=[
                {
                    "if": {"filter_query": '{equipamento} = "TOTAL DA PLANTA"'},
                    "backgroundColor": "#e9ecef",
                    "fontWeight": "bold",
                    "borderTop": "2px solid #6c757d",
                },
                {"if": {"row_index": "odd"}, "backgroundColor": "#fafafa"},
            ],
        )

        # ── Tabela diagnóstico: base de cálculo dos cards do topo ──
        _MN = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]

        # Agregar todos os equipamentos por mês (igual ao que calculate_general_avg_by_month faz)
        monthly_debug_rows = []
        # Usar year_months para correta distinção em ranges multi-ano
        _ym_list = year_months if year_months else [f"????-{m:02d}" for m in sorted(months)]
        for ym in _ym_list:
            month = int(ym.split("-")[1])
            if year_months:
                m_act_h  = sum(m.get("total_active_hours", 0.0)       for eq in equipment_ids if eq in data for m in data[eq] if m.get("year_month") == ym)
                m_bd_min = sum(m.get("total_breakdown_minutes", 0.0)  for eq in equipment_ids if eq in data for m in data[eq] if m.get("year_month") == ym)
                m_fail   = sum(m.get("num_failures", 0)               for eq in equipment_ids if eq in data for m in data[eq] if m.get("year_month") == ym)
            else:
                m_act_h  = sum(m.get("total_active_hours", 0.0)       for eq in equipment_ids if eq in data for m in data[eq] if m["month"] == month)
                m_bd_min = sum(m.get("total_breakdown_minutes", 0.0)  for eq in equipment_ids if eq in data for m in data[eq] if m["month"] == month)
                m_fail   = sum(m.get("num_failures", 0)               for eq in equipment_ids if eq in data for m in data[eq] if m["month"] == month)
            m_bd_h   = m_bd_min / 60.0

            if m_fail > 0 and m_act_h > 0:
                m_mtbf     = (m_act_h - m_bd_h) / m_fail
                m_mttr_min = m_bd_min / m_fail
                m_bd_rate  = (m_bd_h / m_act_h) * 100
            elif m_act_h > 0:
                m_mtbf     = m_act_h
                m_mttr_min = 0.0
                m_bd_rate  = 0.0
            else:
                m_mtbf = m_mttr_min = m_bd_rate = None

            _year_str = ym.split("-")[0]
            _mes_label = f"{_MN[month - 1]}/{_year_str[2:]}" if len(set(ym.split('-')[0] for ym in _ym_list)) > 1 else _MN[month - 1]
            monthly_debug_rows.append({
                "mes":       _mes_label,
                "falhas":    m_fail,
                "act_h":     round(m_act_h, 2),
                "bd_h":      round(m_bd_h, 2),
                "mtbf":      round(m_mtbf, 1)     if m_mtbf     is not None else None,
                "mttr_min":  round(m_mttr_min, 1) if m_mttr_min is not None else None,
                "bd_rate":   round(m_bd_rate, 2)  if m_bd_rate  is not None else None,
            })

        # Média final = o que aparece nos cards do topo
        valid_mtbf  = [r["mtbf"]     for r in monthly_debug_rows if r["mtbf"]     is not None]
        valid_mttr  = [r["mttr_min"] for r in monthly_debug_rows if r["mttr_min"] is not None]
        valid_bdr   = [r["bd_rate"]  for r in monthly_debug_rows if r["bd_rate"]  is not None]
        avg_mtbf    = round(sum(valid_mtbf) / len(valid_mtbf), 1) if valid_mtbf else None
        avg_mttr    = round(sum(valid_mttr) / len(valid_mttr), 1) if valid_mttr else None
        avg_bdr     = round(sum(valid_bdr)  / len(valid_bdr),  2) if valid_bdr  else None

        def _td(content, bold=False, bg=None, align="center"):
            style = {"textAlign": align, "padding": "6px 10px", "fontSize": "0.82rem"}
            if bold:
                style["fontWeight"] = "bold"
            if bg:
                style["backgroundColor"] = bg
            return html.Td(content, style=style)

        def _fmt(v, dec=1):
            return f"{v:.{dec}f}" if v is not None else "—"

        header = html.Thead(html.Tr([
            html.Th("Mês",             style={"textAlign":"center","padding":"6px 10px","fontSize":"0.8rem"}),
            html.Th("Nº Falhas",       style={"textAlign":"center","padding":"6px 10px","fontSize":"0.8rem"}),
            html.Th("Atividade (h)",   style={"textAlign":"center","padding":"6px 10px","fontSize":"0.8rem"}),
            html.Th("Avaria (h)",      style={"textAlign":"center","padding":"6px 10px","fontSize":"0.8rem"}),
            html.Th("MTBF mensal (h)", style={"textAlign":"center","padding":"6px 10px","fontSize":"0.8rem"}),
            html.Th("MTTR mensal (min)",style={"textAlign":"center","padding":"6px 10px","fontSize":"0.8rem"}),
            html.Th("Taxa Avaria (%)", style={"textAlign":"center","padding":"6px 10px","fontSize":"0.8rem"}),
        ], style={"backgroundColor":"#f8f9fa","borderBottom":"2px solid #dee2e6"}))

        body_rows = []
        for r in monthly_debug_rows:
            body_rows.append(html.Tr([
                _td(r["mes"], bold=True, align="left"),
                _td(str(r["falhas"])),
                _td(_fmt(r["act_h"],    2)),
                _td(_fmt(r["bd_h"],     2)),
                _td(_fmt(r["mtbf"],     1)),
                _td(_fmt(r["mttr_min"], 1)),
                _td(_fmt(r["bd_rate"],  2)),
            ]))

        # Linha separadora + linha de média (= cards do topo)
        n = len(monthly_debug_rows)
        body_rows.append(html.Tr([
            _td(f"Média ({n} meses) → Cards topo", bold=True, bg="#fff3cd", align="left"),
            _td("—",              bg="#fff3cd"),
            _td("—",              bg="#fff3cd"),
            _td("—",              bg="#fff3cd"),
            _td(_fmt(avg_mtbf,  1), bold=True, bg="#fff3cd"),
            _td(_fmt(avg_mttr,  1), bold=True, bg="#fff3cd"),
            _td(_fmt(avg_bdr,   2), bold=True, bg="#fff3cd"),
        ]))

        debug_table = dbc.Card([
            dbc.CardBody(
                dbc.Table(
                    [header, html.Tbody(body_rows)],
                    bordered=True, hover=True, size="sm",
                    className="mb-0"
                ),
                style={"padding": "0.5rem"}
            )
        ], className="shadow-sm")

        # ── Card de cobertura de dados ────────────────────────────
        coverage = stored_data.get("data_coverage", {})

        def _cov_item(label, last_date, num_days, icon, color):
            return dbc.Col([
                html.Div([
                    html.I(className=f"bi {icon} me-2", style={"color": color, "fontSize": "1.1rem"}),
                    html.Strong(label, className="me-2"),
                    html.Span(
                        f"{num_days} dias  |  último: {last_date}" if last_date else "sem dados",
                        className="text-muted small"
                    ),
                ], className="d-flex align-items-center py-1")
            ], xs=12, md=6)

        coverage_div = dbc.Card([
            dbc.CardBody([
                html.Div([
                    html.I(className="bi bi-database-check me-2", style={"color": "#0d6efd"}),
                    html.Strong("Cobertura dos dados"),
                ], className="d-flex align-items-center mb-2"),
                dbc.Row([
                    _cov_item(
                        "ZPP Prod",
                        coverage.get("prod_last_date"),
                        coverage.get("prod_num_days", 0),
                        "bi-play-circle-fill", "#198754"
                    ),
                    _cov_item(
                        "ZPP Paradas",
                        coverage.get("paradas_last_date"),
                        coverage.get("paradas_num_days", 0),
                        "bi-exclamation-triangle-fill", "#dc3545"
                    ),
                ], className="g-0"),
            ], style={"padding": "0.75rem 1rem"})
        ], className="shadow-sm mb-3 border-start border-primary border-3")

        return [
            coverage_div,
            debug_table,
            summary_cards,
            dbc.Card([dbc.CardBody(table)], className="shadow-sm")
        ]

    # ============================================================
    # CALLBACK 7: Exportar Dados
    # ============================================================
    @app.callback(
        Output("download-indicators-data", "data"),
        Input("btn-export-indicators", "n_clicks"),
        State("store-indicator-filters", "data"),
        prevent_initial_call=True
    )
    def export_data(n_clicks, stored_data):
        """
        Exporta dados para Excel.
        """
        if not stored_data:
            raise PreventUpdate

        data = stored_data["data"]
        names = stored_data["names"]
        year = stored_data["year"]

        # Preparar DataFrame
        rows = []
        for eq_id, monthly_data in data.items():
            for month_entry in monthly_data:
                rows.append({
                    "Equipamento": names.get(eq_id, eq_id),
                    "Ano": year,
                    "Mês": month_entry["month"],
                    "MTBF (h)": month_entry["mtbf"],
                    "MTTR (min)": month_entry["mttr"] * 60,  # Converter para minutos
                    "Taxa Avaria (%)": month_entry["breakdown_rate"]
                })

        df = pd.DataFrame(rows)

        # Ordenar por equipamento e mês
        df = df.sort_values(["Equipamento", "Mês"])

        return dcc.send_data_frame(
            df.to_excel,
            f"indicadores_manutencao_{year}.xlsx",
            sheet_name="Indicadores",
            index=False
        )

    # ============================================================
    # CALLBACK 8: Botão Atualizar → delega para Aplicar Filtros
    # Opção C (clientside): evita duplicação de lógica de fetch.
    # "Atualizar" usa os filtros ATUAIS do header (não os do store).
    # DÍVIDA TÉCNICA: ver .dev-docs/technical-debt/indicadores-botao-atualizar.md
    # ============================================================
    app.clientside_callback(
        "function(n) { if (!n) return window.dash_clientside.no_update; return n; }",
        Output("btn-apply-indicator-filters", "n_clicks"),
        Input("btn-refresh-indicators", "n_clicks"),
        prevent_initial_call=True
    )

    # REMOVIDO: refresh_data callback separado.
    # Mantido aqui apenas para registrar o motivo da remoção:
    # - Duplicava toda a lógica de process_filters_and_load_data
    # - Não atualizava monthly_aggregates, data_coverage e period_start/end
    # - Causava segundo escritor no store (potencial race condition)
    # A delegação via clientside elimina todos esses problemas.

    # ============================================================
    # CALLBACK 9: Popular Dropdown de Equipamentos
    # ============================================================
    @app.callback(
        [
            Output("dropdown-equipment-individual", "options"),
            Output("dropdown-equipment-individual", "value")
        ],
        Input("store-indicator-filters", "data")
    )
    def populate_equipment_dropdown(stored_data):
        """
        Popula o dropdown de equipamentos com os dados carregados.
        IMPORTANTE: Usa equipamentos SELECIONADOS (exclui DECAP001 por padrão).
        """
        if not stored_data or not stored_data.get("has_data", False):
            return [], None

        # IMPORTANTE: Usar equipamentos SELECIONADOS para dropdown (exclui DECAP001 por padrão)
        equipment_ids = stored_data.get("selected_equipment_ids", stored_data["equipment_ids"])
        names = stored_data["names"]

        options = [
            {"label": names.get(eq_id, eq_id), "value": eq_id}
            for eq_id in equipment_ids
        ]

        # Selecionar primeiro equipamento por padrão
        default_value = equipment_ids[0] if equipment_ids else None

        return options, default_value

    # ============================================================
    # CALLBACK 9B: Exibir Badges de Metas abaixo do Dropdown
    # ============================================================
    @app.callback(
        Output("equipment-targets-badges", "children"),
        [
            Input("store-indicator-filters", "data"),
            Input("dropdown-equipment-individual", "value")
        ]
    )
    def display_equipment_targets_badges(stored_data, equipment_id):
        """
        Exibe badges compactos com as metas do equipamento selecionado
        logo abaixo do dropdown de seleção.
        """
        import dash_bootstrap_components as dbc
        from dash import html

        if not stored_data or not equipment_id:
            return html.Div()

        equipment_targets = stored_data.get("equipment_targets", {})

        # Obter meta específica do equipamento (ou usar meta geral como fallback)
        eq_target = equipment_targets.get(equipment_id, equipment_targets.get("GENERAL", {}))

        if not eq_target:
            return html.Div()

        # Converter MTTR para minutos
        mttr_target_min = eq_target.get("mttr", 0) * 60

        # Verificar se é meta geral ou específica
        is_general_target = equipment_id not in equipment_targets

        return html.Div([
            html.Small([
                html.I(className="bi bi-bullseye me-1", style={"fontSize": "0.8rem"}),
                html.Span("Metas 2026", className="text-muted fw-bold"),
                html.Span(
                    " (Geral)" if is_general_target else " (Específica)",
                    className="text-muted",
                    style={"fontSize": "0.75rem", "fontStyle": "italic"}
                ),
                html.Span(" | ", className="text-muted mx-1"),
                dbc.Badge(
                    f"MTBF ≥ {eq_target.get('mtbf', 0):.1f}h",
                    color="success",
                    className="me-1",
                    pill=True,
                    style={"fontSize": "0.75rem", "fontWeight": "normal"}
                ),
                dbc.Badge(
                    f"MTTR ≤ {mttr_target_min:.0f}min",
                    color="primary",
                    className="me-1",
                    pill=True,
                    style={"fontSize": "0.75rem", "fontWeight": "normal"}
                ),
                dbc.Badge(
                    f"Avaria ≤ {eq_target.get('breakdown_rate', 0):.1f}%",
                    color="warning",
                    className="",
                    pill=True,
                    style={"fontSize": "0.75rem", "fontWeight": "normal"}
                )
            ])
        ], style={"lineHeight": "1.8"})

    # ============================================================
    # CALLBACK 10: Exibir Metas do Equipamento Selecionado
    # ============================================================
    @app.callback(
        Output("equipment-targets-info", "children"),
        [
            Input("store-indicator-filters", "data"),
            Input("dropdown-equipment-individual", "value")
        ]
    )
    def display_equipment_targets(stored_data, equipment_id):
        """
        Exibe as metas do equipamento selecionado acima dos gauges.

        Mostra:
        - Nome do equipamento
        - Meta MTBF
        - Meta MTTR
        - Meta Taxa de Avaria
        """
        import dash_bootstrap_components as dbc
        from dash import html

        if not stored_data or not equipment_id:
            return html.Div()

        equipment_targets = stored_data.get("equipment_targets", {})
        names = stored_data.get("names", {})

        # Obter meta específica do equipamento (ou usar meta geral como fallback)
        eq_target = equipment_targets.get(equipment_id, equipment_targets.get("GENERAL", {}))
        equipment_name = names.get(equipment_id, equipment_id)

        if not eq_target:
            return html.Div()

        # Converter MTTR para minutos
        mttr_target_min = eq_target.get("mttr", 0) * 60

        # Verificar se é meta geral ou específica
        is_general_target = equipment_id not in equipment_targets

        return dbc.Alert([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.I(className="bi bi-bullseye me-2", style={"fontSize": "1.1rem"}),
                        html.Strong("Metas 2026", style={"fontSize": "0.95rem"}),
                        html.Span(
                            " (Geral)" if is_general_target else " (Específica)",
                            className="text-muted ms-1",
                            style={"fontSize": "0.85rem", "fontStyle": "italic"}
                        )
                    ], className="mb-2")
                ], width=12)
            ]),
            dbc.Row([
                # MTBF
                dbc.Col([
                    html.Div([
                        html.Span("MTBF: ", className="text-muted", style={"fontSize": "0.85rem"}),
                        html.Strong(
                            f"{eq_target.get('mtbf', 0):.1f} h",
                            style={"fontSize": "0.95rem", "color": "#198754"}
                        )
                    ])
                ], width=4, className="text-center"),

                # MTTR
                dbc.Col([
                    html.Div([
                        html.Span("MTTR: ", className="text-muted", style={"fontSize": "0.85rem"}),
                        html.Strong(
                            f"{mttr_target_min:.0f} min",
                            style={"fontSize": "0.95rem", "color": "#0d6efd"}
                        )
                    ])
                ], width=4, className="text-center"),

                # Taxa de Avaria
                dbc.Col([
                    html.Div([
                        html.Span("Taxa Avaria: ", className="text-muted", style={"fontSize": "0.85rem"}),
                        html.Strong(
                            f"{eq_target.get('breakdown_rate', 0):.1f} %",
                            style={"fontSize": "0.95rem", "color": "#fd7e14"}
                        )
                    ])
                ], width=4, className="text-center")
            ], className="g-0")
        ], color="light", className="mb-2 py-2 px-3", style={
            "borderLeft": "4px solid #0d6efd",
            "boxShadow": "0 2px 4px rgba(0,0,0,0.05)"
        })

    # ============================================================
    # CALLBACK 10B: Atualizar Cards Individuais (renumerado)
    # ============================================================
    @app.callback(
        [
            Output("individual-mtbf-value", "children"),
            Output("individual-mttr-value", "children"),
            Output("individual-breakdown-value", "children")
        ],
        [
            Input("store-indicator-filters", "data"),
            Input("dropdown-equipment-individual", "value")
        ]
    )
    def update_individual_cards(stored_data, equipment_id):
        """
        Atualiza os 3 cards de resumo do equipamento selecionado.
        """
        if not stored_data or not equipment_id:
            return ["--", "--", "--"]

        data = stored_data["data"]
        equipment_ids = stored_data["equipment_ids"]
        months = stored_data["months"]
        year = stored_data.get("year", 2026)
        monthly_aggregates = stored_data.get("monthly_aggregates")

        # Calcular médias por equipamento (usando cache de monthly_aggregates do store)
        averages = calculate_kpi_averages(data, equipment_ids, months, year=year, monthly_aggregates=monthly_aggregates, year_months=stored_data.get("year_months"))

        if not averages.get("by_equipment") or equipment_id not in averages["by_equipment"]:
            return ["--", "--", "--"]

        eq_data = averages["by_equipment"][equipment_id]

        return [
            f"{eq_data['mtbf']:.1f} h",
            f"{eq_data['mttr'] * 60:.1f} min",
            f"{eq_data['breakdown_rate']:.2f} %"
        ]

    # ============================================================
    # CALLBACK 11: Atualizar Gauges Individuais (MTBF, MTTR, Taxa Avaria)
    # ============================================================
    @app.callback(
        [
            Output("gauge-mtbf-individual", "figure"),
            Output("gauge-mttr-individual", "figure"),
            Output("gauge-breakdown-individual", "figure")
        ],
        [
            Input("store-indicator-filters", "data"),
            Input("dropdown-equipment-individual", "value")
        ]
    )
    def update_individual_gauges(stored_data, equipment_id):
        """
        Atualiza os 3 gauges (MTBF, MTTR, Taxa de Avaria) com metas individualizadas quando:
        - Dados são carregados/atualizados
        - Equipamento selecionado muda
        """
        import plotly.graph_objects as go

        template = TEMPLATE_THEME_MINTY  # Tema fixo em Minty (claro)

        if not stored_data or not equipment_id or not stored_data.get("has_data", False):
            # Retornar figuras com mensagem de sem dados
            return [
                create_no_data_figure("gauge", template),
                create_no_data_figure("gauge", template),
                create_no_data_figure("gauge", template)
            ]

        data = stored_data["data"]
        equipment_targets = stored_data["equipment_targets"]  # ALTERADO: Usar metas por equipamento
        equipment_ids = stored_data["equipment_ids"]
        months = stored_data["months"]
        year = stored_data.get("year", 2026)
        monthly_aggregates = stored_data.get("monthly_aggregates")

        # Calcular médias por equipamento (usando cache de monthly_aggregates do store)
        averages = calculate_kpi_averages(data, equipment_ids, months, year=year, monthly_aggregates=monthly_aggregates, year_months=stored_data.get("year_months"))

        if not averages.get("by_equipment") or equipment_id not in averages["by_equipment"]:
            return [
                create_no_data_figure("gauge", template),
                create_no_data_figure("gauge", template),
                create_no_data_figure("gauge", template)
            ]

        eq_data = averages["by_equipment"][equipment_id]

        # Obter meta específica do equipamento (ou usar meta geral como fallback)
        eq_target = equipment_targets.get(equipment_id, equipment_targets.get("GENERAL", {}))
        alert_range = eq_target.get("alert_range", 3.0)

        # Criar gauges com meta individualizada
        fig_mtbf = create_kpi_gauge(
            value=eq_data['mtbf'],
            kpi_name="MTBF",
            target_value=eq_target.get("mtbf", 0),
            template=template,
            margin_percent=alert_range
        )

        fig_mttr = create_kpi_gauge(
            value=eq_data['mttr'],
            kpi_name="MTTR",
            target_value=eq_target.get("mttr", 999),
            template=template,
            margin_percent=alert_range
        )

        fig_breakdown = create_kpi_gauge(
            value=eq_data['breakdown_rate'],
            kpi_name="Taxa de Avaria",
            target_value=eq_target.get("breakdown_rate", 100),
            template=template,
            margin_percent=alert_range
        )

        return [fig_mtbf, fig_mttr, fig_breakdown]

    # ============================================================
    # CALLBACK 11B: Toggle Calendar Collapse
    # ============================================================
    @app.callback(
        [
            Output("calendar-collapse", "is_open"),
            Output("calendar-collapse-icon", "className")
        ],
        Input("calendar-collapse-button", "n_clicks"),
        State("calendar-collapse", "is_open")
    )
    def toggle_calendar_collapse(n_clicks, is_open):
        """
        Controla expansão/colapso do calendar heatmap.
        """
        if n_clicks is None:
            raise PreventUpdate

        new_state = not is_open
        icon_class = "bi bi-chevron-up me-2" if new_state else "bi bi-chevron-down me-2"
        return new_state, icon_class

    # ============================================================
    # CALLBACK 12: Atualizar Gráficos de Linha (Evolução Temporal) + Estatísticas
    # ============================================================
    @app.callback(
        [
            Output("line-chart-mtbf-individual", "figure"),
            Output("line-chart-mttr-individual", "figure"),
            Output("line-chart-breakdown-individual", "figure"),
            Output("comparison-chart-individual", "figure"),
            Output("calendar-heatmap-individual", "figure"),
            Output("heatmap-stats-card", "children")  # NOVO: Card de estatísticas
        ],
        [
            Input("store-indicator-filters", "data"),
            Input("dropdown-equipment-individual", "value")
        ]
    )
    def update_individual_tab(stored_data, equipment_id):
        """
        Atualiza gráficos da tab Individual com metas individualizadas quando:
        - Dados são carregados/atualizados
        - Equipamento selecionado muda
        """
        import plotly.graph_objects as go

        template = TEMPLATE_THEME_MINTY  # Tema fixo em Minty (claro)

        if not stored_data or not equipment_id or not stored_data.get("has_data", False):
            # Retornar figuras com mensagem de sem dados
            return [
                create_no_data_figure("linha", template),
                create_no_data_figure("linha", template),
                create_no_data_figure("linha", template),
                create_no_data_figure("comparacao", template),
                create_no_data_figure("heatmap", template)
            ]

        data = stored_data["data"]
        equipment_targets = stored_data["equipment_targets"]
        names = stored_data["names"]
        months = stored_data["months"]
        year_months = stored_data.get("year_months") or [f"{stored_data.get('year', 2026)}-{m:02d}" for m in months]
        all_equipment = stored_data["equipment_ids"]

        from datetime import datetime as _dt
        _sd = stored_data.get("start_date")
        _ed = stored_data.get("end_date")
        _start_dt = _dt.fromisoformat(_sd) if _sd else None
        _end_dt = _dt.fromisoformat(_ed) if _ed else None

        # Calcular médias gerais por mês (AGREGANDO dados brutos, suporta multi-ano)
        general_avg_by_month = calculate_general_avg_by_month(
            data, all_equipment, start_date=_start_dt, end_date=_end_dt
        )

        # Dados do equipamento selecionado
        eq_data_by_month = data.get(equipment_id, [])

        if not eq_data_by_month or not general_avg_by_month:
            return [
                create_no_data_figure("linha", template),
                create_no_data_figure("linha", template),
                create_no_data_figure("linha", template),
                create_no_data_figure("comparacao", template),
                create_no_data_figure("heatmap", template)
            ]

        # Lookup por year_month (preciso para multi-ano)
        eq_data_dict = {m.get("year_month", f"????-{m['month']:02d}"): m for m in eq_data_by_month}

        mtbf_values = []
        mttr_values = []
        breakdown_values = []
        months_present = []

        for ym in year_months:
            month_int = int(ym.split("-")[1])
            if ym in eq_data_dict:
                mtbf_values.append(eq_data_dict[ym]["mtbf"])
                mttr_values.append(eq_data_dict[ym]["mttr"])
                breakdown_values.append(eq_data_dict[ym]["breakdown_rate"])
            else:
                mtbf_values.append(None)
                mttr_values.append(None)
                breakdown_values.append(None)
            months_present.append(month_int)

        # Médias gerais por mês (indexadas por year_month)
        mtbf_avg = [general_avg_by_month.get(ym, {}).get("mtbf") for ym in year_months]
        mttr_avg = [general_avg_by_month.get(ym, {}).get("mttr") for ym in year_months]
        breakdown_avg = [general_avg_by_month.get(ym, {}).get("breakdown_rate") for ym in year_months]

        # Verificar se há pelo menos UM valor não-None em cada lista
        has_valid_data = (
            any(v is not None for v in mtbf_values) and
            any(v is not None for v in mttr_values) and
            any(v is not None for v in breakdown_values) and
            any(v is not None for v in mtbf_avg) and
            any(v is not None for v in mttr_avg) and
            any(v is not None for v in breakdown_avg)
        )

        if not has_valid_data:
            return [
                create_no_data_figure("linha", template),
                create_no_data_figure("linha", template),
                create_no_data_figure("linha", template),
                create_no_data_figure("comparacao", template),
                create_no_data_figure("heatmap", template)
            ]

        # Obter meta específica do equipamento (ou usar meta geral como fallback)
        eq_target = equipment_targets.get(equipment_id, equipment_targets.get("GENERAL", {}))
        alert_range = eq_target.get("alert_range", 3.0)

        # Criar gráficos de linha com meta individualizada
        fig_mtbf = create_kpi_line_chart(
            months_present, mtbf_values, mtbf_avg,
            "MTBF", names.get(equipment_id, equipment_id),
            eq_target.get("mtbf", 0),
            template,
            margin_percent=alert_range
        )

        fig_mttr = create_kpi_line_chart(
            months_present, mttr_values, mttr_avg,
            "MTTR", names.get(equipment_id, equipment_id),
            eq_target.get("mttr", 999),
            template,
            margin_percent=alert_range
        )

        fig_breakdown = create_kpi_line_chart(
            months_present, breakdown_values, breakdown_avg,
            "Taxa de Avaria", names.get(equipment_id, equipment_id),
            eq_target.get("breakdown_rate", 100),
            template,
            margin_percent=alert_range
        )

        # Gráfico de comparação
        # Filtra None antes de calcular médias
        mtbf_values_clean = [v for v in mtbf_values if v is not None]
        mttr_values_clean = [v for v in mttr_values if v is not None]
        breakdown_values_clean = [v for v in breakdown_values if v is not None]

        eq_summary = {
            "mtbf": sum(mtbf_values_clean) / len(mtbf_values_clean) if mtbf_values_clean else 0,
            "mttr": sum(mttr_values_clean) / len(mttr_values_clean) if mttr_values_clean else 0,
            "breakdown_rate": sum(breakdown_values_clean) / len(breakdown_values_clean) if breakdown_values_clean else 0
        }

        mtbf_avg_clean = [v for v in mtbf_avg if v is not None]
        mttr_avg_clean = [v for v in mttr_avg if v is not None]
        breakdown_avg_clean = [v for v in breakdown_avg if v is not None]

        general_summary = {
            "mtbf": sum(mtbf_avg_clean) / len(mtbf_avg_clean) if mtbf_avg_clean else 0,
            "mttr": sum(mttr_avg_clean) / len(mttr_avg_clean) if mttr_avg_clean else 0,
            "breakdown_rate": sum(breakdown_avg_clean) / len(breakdown_avg_clean) if breakdown_avg_clean else 0
        }

        fig_comparison = create_performance_radar_chart(
            eq_summary, general_summary, names.get(equipment_id, equipment_id),
            equipment_target=eq_target, template=template
        )

        # Calendar heatmap (✅ OTIMIZADO: usa agregação ao invés de loop)
        fig_calendar, stats = create_breakdown_calendar_heatmap(
            equipment_id, _start_dt, _end_dt, template
        )

        # Criar card de estatísticas em 2 colunas
        stats_content = dbc.Row([
            # COLUNA ESQUERDA
            dbc.Col([
                # Estatísticas Gerais
                html.H6("📊 Estatísticas", className="mb-2"),
                html.Hr(className="my-2"),
                html.Small([
                    f"📅 {stats['total_days']} dias | 🏭 {stats['production_days']} úteis", html.Br(),
                    f"✅ {stats['days_no_failure']} sem falha ({stats['days_no_failure']/stats['production_days']*100 if stats['production_days'] > 0 else 0:.0f}%)", html.Br(),
                    f"⚠️ {stats['days_with_failure']} com falha ({stats['days_with_failure']/stats['production_days']*100 if stats['production_days'] > 0 else 0:.0f}%)", html.Br(),
                    f"🔥 {stats['total_breakdowns']} paradas | 🏆 {stats['max_streak']} streak",
                ]),

                # Melhor Dia
                html.H6("💚 Melhor Dia", className="mb-2 mt-3"),
                html.Hr(className="my-2"),
                html.Small([
                    html.B(stats['best_weekday_name'], style={"color": "#198754", "fontSize": "1.1rem"}), html.Br(),
                    f"📊 {stats['best_weekday_avg']:.2f} falhas/dia", html.Br(),
                    f"📅 {stats['best_weekday_days_count']} dias", html.Br(),
                    f"✅ {stats['best_weekday_zero_failures']} sem falhas ({stats['best_weekday_zero_pct']:.0f}%)",
                ]),

                # Tendência
                html.H6("📈 Tendência", className="mb-2 mt-3"),
                html.Hr(className="my-2"),
                html.Small([
                    html.Span([stats['trend_icon'], " ", html.B(stats['trend_text'])], style={"color": stats['trend_color']}), html.Br(),
                    f"1ª: {stats['first_half_avg']:.2f} | 2ª: {stats['second_half_avg']:.2f}",
                ]),
            ], md=6),

            # COLUNA DIREITA
            dbc.Col([
                # Pior Dia
                html.H6("🔴 Pior Dia", className="mb-2"),
                html.Hr(className="my-2"),
                html.Small([
                    html.B(stats['worst_weekday_name'], style={"color": "#dc3545", "fontSize": "1.1rem"}), html.Br(),
                    f"📊 {stats['worst_weekday_avg']:.2f} falhas/dia", html.Br(),
                    f"📅 {stats['worst_weekday_days_count']} dias", html.Br(),
                    f"⚠️ {stats['worst_weekday_with_failures']} com falhas ({stats['worst_weekday_with_failures_pct']:.0f}%)",
                ]),

                # Dias Críticos
                html.H6("🔥 Dias Críticos", className="mb-2 mt-3"),
                html.Hr(className="my-2"),
                html.Small([
                    f"⚠️ {stats['critical_days']} dias (2+ falhas)", html.Br(),
                    f"{stats['critical_days_pct']:.1f}% dos úteis",
                ]),

                # Ranking
                html.H6("📅 Ranking", className="mb-2 mt-3"),
                html.Hr(className="my-2"),
                html.Small([
                    html.Div([
                        f"{'🥇' if i == 0 else '🥈' if i == 1 else '🥉' if i == 2 else '  '} ",
                        html.Span(name[:3], style={"color": "#dc3545" if name == stats['worst_weekday_name'] else "#198754" if name == stats['best_weekday_name'] else "#6c757d"}),
                        html.Span(f" {avg:.2f}", style={"color": "#dc3545" if name == stats['worst_weekday_name'] else "#198754" if name == stats['best_weekday_name'] else "#6c757d"})
                    ]) for i, (name, avg, _) in enumerate(stats['weekday_avg'])
                ])
            ], md=6)
        ])

        return [fig_mtbf, fig_mttr, fig_breakdown, fig_comparison, fig_calendar, stats_content]

    # ============================================================
    # CALLBACK 13: Atualizar Top Paradas Gráfico
    # ============================================================
    @app.callback(
        Output("top-breakdowns-chart-individual", "figure"),
        [
            Input("store-indicator-filters", "data"),
            Input("dropdown-equipment-individual", "value")
        ]
    )
    def update_top_breakdowns_chart(stored_data, equipment_id):
        """
        Atualiza gráfico de top 10 paradas com maior tempo quando:
        - Dados são carregados/atualizados
        - Equipamento selecionado muda
        """
        import plotly.graph_objects as go

        template = TEMPLATE_THEME_MINTY  # Tema fixo em Minty (claro)

        if not stored_data or not equipment_id or not stored_data.get("has_data", False):
            # Retornar figura com mensagem de sem dados
            return create_no_data_figure("paradas", template)

        names = stored_data.get("names", {})
        active_codes = stored_data.get("selected_breakdown_codes") or None

        # Buscar top 5 paradas do equipamento (com filtro de códigos ativo)
        if ZPP_KPI_AVAILABLE:
            try:
                from datetime import datetime as _dt
                _sd = stored_data.get("start_date")
                _ed = stored_data.get("end_date")
                _start_dt = _dt.fromisoformat(_sd) if _sd else _dt(stored_data.get("year", 2026), 1, 1)
                _end_dt = _dt.fromisoformat(_ed) if _ed else _dt(stored_data.get("year", 2026), 12, 31, 23, 59, 59)
                breakdowns_data = fetch_top_breakdowns_by_equipment(
                    equipment_id=equipment_id,
                    start_date=_start_dt,
                    end_date=_end_dt,
                    top_n=5,
                    breakdown_codes=active_codes
                )

                # Criar gráfico
                fig = create_top_breakdowns_chart(
                    breakdowns_data=breakdowns_data,
                    equipment_name=names.get(equipment_id, equipment_id),
                    template=template
                )

                return fig

            except Exception as e:
                import traceback
                traceback.print_exc()

                # Retornar figura com mensagem de erro
                return create_no_data_figure("paradas", template)
        else:
            # Módulo ZPP não disponível
            return create_no_data_figure("paradas", template)

