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
        fetch_top_breakdowns_by_equipment
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
            State("store-indicator-filters", "data")
        ]
    )
    def process_filters_and_load_data(n_clicks, n_intervals,
                                      period_type, ref_year,
                                      start_date, end_date,
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

        # IMPORTANTE: Verificar se dados estão COMPLETOS (incluindo categorias)
        # Se store tem dados MAS não tem categorias, precisa recarregar tudo
        has_complete_data = (
            current_data and
            current_data.get("data") and
            current_data.get("categories")  # ← CRÍTICO: Verificar categorias também!
        )

        if trigger_id == "interval-initial-load" and has_complete_data:
            # Interval disparou e temos dados COMPLETOS - apenas atualizar metas sem recarregar ZPP
            logger.debug("Interval: dados completos no store, apenas atualizando metas")
            logger.debug("Store: %d equipamentos, %d categorias",
                        len(current_data.get("equipment_ids", [])),
                        len(current_data.get("categories", {})))
            current_data["equipment_targets"] = get_all_equipment_targets()
            current_data["targets"] = get_kpi_targets("GENERAL")
            return current_data
        elif trigger_id == "interval-initial-load" and current_data and current_data.get("data"):
            # Store tem dados mas SEM categorias - forçar recarga completa
            logger.warning("Store sem categorias - forçando recarga completa")
            # Continua para o fluxo normal de recarga abaixo

        # Validar inputs baseado no tipo
        # Padrão: sempre usar modo "year" (ano completo)
        if not period_type:
            period_type = "year"

        if not ref_year:
            ref_year = 2026  # Ano padrão onde os dados ZPP estão disponíveis

        if period_type == "year":
            # Todos os meses do ano selecionado
            months = list(range(1, 13))
            year = ref_year

        elif period_type == "custom":
            # Período personalizado via date range
            if not start_date or not end_date:
                # Fallback: usar ano completo
                year = ref_year
                months = list(range(1, 13))
            else:
                from datetime import datetime
                start = datetime.fromisoformat(start_date) if isinstance(start_date, str) else start_date
                end = datetime.fromisoformat(end_date) if isinstance(end_date, str) else end_date

                year = start.year
                # Gerar lista de meses entre start e end
                # LIMITAÇÃO: Apenas meses do mesmo ano (start.year)
                months = []
                current = start
                while current <= end and current.year == start.year:
                    if current.month not in months:
                        months.append(current.month)
                    # Avançar para próximo mês
                    if current.month == 12:
                        break
                    current = current.replace(month=current.month + 1)

                months = sorted(months) if months else [start.month]

        else:
            # Fallback: ano completo
            year = ref_year
            months = list(range(1, 13))

        # Buscar dados reais - INTEGRAÇÃO ZPP

        data = {}
        all_equipment = []
        has_data = False

        logger.debug("ZPP_KPI_AVAILABLE=%s, buscando dados year=%d months=%s",
                    ZPP_KPI_AVAILABLE, year, months)

        if ZPP_KPI_AVAILABLE:
            try:
                # Tentar buscar dados reais do ZPP
                data = fetch_zpp_kpi_data(year, months)
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

                # Log diagnóstico: verificar se categorias foram carregadas
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
                names = {eq: eq for eq in all_equipment}  # Fallback: usar IDs como nomes
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
                monthly_aggregates = calculate_general_avg_by_month(data, all_equipment, months, year=year)
            except Exception as e:
                monthly_aggregates = None

        # Log diagnóstico: verificar o que está sendo armazenado no store
        logger.debug(
            "Armazenando no store: %d equipamentos, %d categorias",
            len(all_equipment), len(categories)
        )

        if categories:
            logger.debug("Categorias: %s", list(categories.keys()))
        else:
            logger.warning("Store será salvo SEM categorias")

        return {
            "period_type": period_type,
            "year": year,
            "months": months,
            "equipment_ids": all_equipment,
            "data": data,
            "targets": general_target,  # Meta geral (para compatibilidade)
            "equipment_targets": equipment_targets,  # Metas por equipamento
            "names": names,
            "categories": categories,
            "has_data": has_data,  # Indicador se há dados disponíveis
            "monthly_aggregates": monthly_aggregates  # Cache de agregações mensais
        }

    # ============================================================
    # CALLBACK 3: Atualizar Summary Cards
    # ============================================================
    @app.callback(
        [
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
        # Verificar se MongoDB está offline
        if stored_data and stored_data.get("db_error"):
            return ["--"] * 3 + ["BD Offline", "danger"] * 3 + ["0"]

        if not stored_data or not stored_data.get("has_data", False):
            return ["--"] * 3 + ["Sem dados", "secondary"] * 3 + ["0"]

        data = stored_data["data"]
        equipment_targets = stored_data["equipment_targets"]  # ALTERADO
        equipment_ids = stored_data["equipment_ids"]
        months = stored_data["months"]
        year = stored_data.get("year", 2026)
        monthly_aggregates = stored_data.get("monthly_aggregates")

        # Calcular médias (usando cache de monthly_aggregates do store)
        averages = calculate_kpi_averages(data, equipment_ids, months, year=year, monthly_aggregates=monthly_aggregates)

        # Se não houver médias válidas após o cálculo
        if not averages.get("by_equipment"):
            return ["--"] * 3 + ["Sem dados", "secondary"] * 3 + ["0"]

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

        return [
            f"{mtbf_avg:.1f} h",
            mtbf_badge_text,
            mtbf_badge_color,
            f"{mttr_avg_minutes:.1f} min",
            mttr_badge_text,
            mttr_badge_color,
            f"{breakdown_avg:.2f} %",
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
        equipment_ids = stored_data["equipment_ids"]
        months = stored_data["months"]
        year = stored_data.get("year", 2026)
        monthly_aggregates = stored_data.get("monthly_aggregates")

        for idx, eq_id in enumerate(equipment_ids[:2]):
            eq_data = data.get(eq_id, [])

        # Calcular médias por equipamento (usando cache de monthly_aggregates do store)
        averages = calculate_kpi_averages(data, equipment_ids, months, year=year, monthly_aggregates=monthly_aggregates)

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
        equipment_ids = stored_data["equipment_ids"]
        months = stored_data["months"]
        equipment_targets = stored_data.get("equipment_targets", {})
        year = stored_data.get("year", 2026)
        monthly_aggregates = stored_data.get("monthly_aggregates")

        # Log diagnóstico: verificar o que foi recuperado do store
        logger.debug(
            "Sunburst recebeu: %d equipamentos, %d categorias",
            len(equipment_ids), len(categories)
        )

        if categories:
            logger.debug("Categorias: %s", list(categories.keys()))
            for cat_name, cat_equipments in categories.items():
                logger.debug("  '%s': %d equipamentos", cat_name, len(cat_equipments))
        else:
            logger.warning("Sunburst recebeu categorias VAZIO do store")

        # Calcular médias por equipamento (usando cache de monthly_aggregates do store)
        averages = calculate_kpi_averages(data, equipment_ids, months, year=year, monthly_aggregates=monthly_aggregates)

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
        equipment_targets = stored_data.get("equipment_targets", {})
        year = stored_data.get("year", 2026)

        # Calcular médias gerais por mês (AGREGANDO dados brutos)
        general_avg_by_month = calculate_general_avg_by_month(data, equipment_ids, months, year=year)

        if not general_avg_by_month:
            return [
                create_no_data_figure("linha", template),
                create_no_data_figure("linha", template),
                create_no_data_figure("linha", template)
            ]

        # Extrair valores por mês
        mtbf_values = [general_avg_by_month[m]["mtbf"] for m in months if m in general_avg_by_month]
        mttr_values = [general_avg_by_month[m]["mttr"] for m in months if m in general_avg_by_month]
        breakdown_values = [general_avg_by_month[m]["breakdown_rate"] for m in months if m in general_avg_by_month]

        # Obter meta geral da planta
        general_target = equipment_targets.get("GENERAL", {"mtbf": 0, "mttr": 999, "breakdown_rate": 100, "alert_range": 3.0})
        alert_range = general_target.get("alert_range", 3.0)

        # Criar gráficos de linha (sem linha de média, pois JÁ É a média da planta)
        fig_mtbf = create_kpi_line_chart(
            months, mtbf_values, None,  # None = não mostrar linha de comparação
            "MTBF", "Média da Planta",
            general_target.get("mtbf", 0),
            template,
            margin_percent=alert_range
        )

        fig_mttr = create_kpi_line_chart(
            months, mttr_values, None,
            "MTTR", "Média da Planta",
            general_target.get("mttr", 999),
            template,
            margin_percent=alert_range
        )

        fig_breakdown = create_kpi_line_chart(
            months, breakdown_values, None,
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
        equipment_ids = stored_data["equipment_ids"]
        months = stored_data["months"]
        year = stored_data.get("year", 2026)
        monthly_aggregates = stored_data.get("monthly_aggregates")

        # Calcular médias por equipamento (usando cache de monthly_aggregates do store)
        averages = calculate_kpi_averages(data, equipment_ids, months, year=year, monthly_aggregates=monthly_aggregates)

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
    # CALLBACK 8: Botão Atualizar (Refresh)
    # ============================================================
    @app.callback(
        Output("store-indicator-filters", "data", allow_duplicate=True),
        Input("btn-refresh-indicators", "n_clicks"),
        State("store-indicator-filters", "data"),
        prevent_initial_call=True
    )
    def refresh_data(n_clicks, current_data):
        """
        Força atualização completa de dados E metas do MongoDB.
        Útil após salvar novas metas na página de configuração.
        """
        if not current_data:
            raise PreventUpdate


        year = current_data.get("year", 2026)
        months = current_data.get("months", list(range(1, 13)))

        # PASSO 1: Atualizar metas do MongoDB (SEMPRE)
        equipment_targets = get_all_equipment_targets()
        general_targets = get_kpi_targets("GENERAL")

        # PASSO 2: Re-buscar dados do ZPP
        new_data = {}
        has_data = False

        if ZPP_KPI_AVAILABLE:
            try:
                new_data = fetch_zpp_kpi_data(year, months)
                has_data = len(new_data) > 0

                if has_data:
                    pass
                else:
                    pass
            except Exception as e:
                has_data = False
        else:
            has_data = False

        # Atualizar nomes e categorias se houver dados
        if has_data and ZPP_KPI_AVAILABLE:
            try:
                current_data["names"] = get_zpp_equipment_names()
                current_data["categories"] = get_zpp_equipment_categories()
                current_data["equipment_ids"] = list(new_data.keys())
            except Exception as e:
                pass

        # Atualizar store com novos dados e metas
        current_data["data"] = new_data
        current_data["has_data"] = has_data
        current_data["equipment_targets"] = equipment_targets
        current_data["targets"] = general_targets

        return current_data

    # ============================================================
    # CALLBACK 8B: Auto-refresh ao navegar para a página
    # ============================================================
    @app.callback(
        Output("store-indicator-filters", "data", allow_duplicate=True),
        [Input("url", "pathname")],
        [State("store-indicator-filters", "data")],
        prevent_initial_call=True
    )
    def auto_refresh_on_navigation(pathname, current_data):
        """
        Atualiza metas quando usuário navega de volta para a página de indicadores.
        Útil após salvar metas na página de configuração.
        """
        # Apenas atualizar se estiver na página de indicadores
        if pathname != "/maintenance/indicators":
            raise PreventUpdate

        # Se não há dados ainda, deixar o interval inicial carregar
        if not current_data or not current_data.get("data"):
            raise PreventUpdate


        # Atualizar apenas as metas (não recarregar dados pesados do ZPP)
        current_data["equipment_targets"] = get_all_equipment_targets()
        current_data["targets"] = get_kpi_targets("GENERAL")

        return current_data

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
        """
        if not stored_data or not stored_data.get("has_data", False):
            return [], None

        equipment_ids = stored_data["equipment_ids"]
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
        averages = calculate_kpi_averages(data, equipment_ids, months, year=year, monthly_aggregates=monthly_aggregates)

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
        averages = calculate_kpi_averages(data, equipment_ids, months, year=year, monthly_aggregates=monthly_aggregates)

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
        equipment_targets = stored_data["equipment_targets"]  # ALTERADO: Usar metas por equipamento
        names = stored_data["names"]
        months = stored_data["months"]
        all_equipment = stored_data["equipment_ids"]
        year = stored_data.get("year", 2026)

        # Calcular médias gerais por mês (AGREGANDO dados brutos)
        general_avg_by_month = calculate_general_avg_by_month(data, all_equipment, months, year=year)

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

        # Extrair valores por mês (mantendo None para meses sem dados)
        # Garantir que temos um valor para cada mês solicitado
        mtbf_values = []
        mttr_values = []
        breakdown_values = []

        # Criar dicionário de dados por mês para lookup rápido
        eq_data_dict = {m["month"]: m for m in eq_data_by_month}

        for month in months:
            if month in eq_data_dict:
                mtbf_values.append(eq_data_dict[month]["mtbf"])
                mttr_values.append(eq_data_dict[month]["mttr"])
                breakdown_values.append(eq_data_dict[month]["breakdown_rate"])
            else:
                # Mês sem dados - usar None
                mtbf_values.append(None)
                mttr_values.append(None)
                breakdown_values.append(None)

        # Médias gerais por mês
        mtbf_avg = [general_avg_by_month.get(m, {}).get("mtbf") for m in months]
        mttr_avg = [general_avg_by_month.get(m, {}).get("mttr") for m in months]
        breakdown_avg = [general_avg_by_month.get(m, {}).get("breakdown_rate") for m in months]

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
            months, mtbf_values, mtbf_avg,
            "MTBF", names.get(equipment_id, equipment_id),
            eq_target.get("mtbf", 0),
            template,
            margin_percent=alert_range
        )

        fig_mttr = create_kpi_line_chart(
            months, mttr_values, mttr_avg,
            "MTTR", names.get(equipment_id, equipment_id),
            eq_target.get("mttr", 999),
            template,
            margin_percent=alert_range
        )

        fig_breakdown = create_kpi_line_chart(
            months, breakdown_values, breakdown_avg,
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
        year = stored_data.get("year", 2026)
        fig_calendar, stats = create_breakdown_calendar_heatmap(
            equipment_id, year, months, template
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

        year = stored_data.get("year")
        months = stored_data.get("months", [])
        names = stored_data.get("names", {})

        # Buscar top 5 paradas do equipamento
        if ZPP_KPI_AVAILABLE:
            try:
                breakdowns_data = fetch_top_breakdowns_by_equipment(
                    equipment_id=equipment_id,
                    year=year,
                    months=months,
                    top_n=5
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

