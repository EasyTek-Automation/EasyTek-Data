"""
Maintenance KPI Callbacks
Callbacks para a página de indicadores de manutenção
"""

from dash import Output, Input, State, dcc, html, no_update
from dash.exceptions import PreventUpdate
import dash
import pandas as pd
from src.config.theme_config import TEMPLATE_THEME_MINTY

# Importar funções de cálculo e agregação (mantidas para processar dados ZPP)
from src.utils.maintenance_demo_data import (
    calculate_kpi_averages,
    calculate_general_avg_by_month,
    get_kpi_targets
)

# Importar funções de integração com ZPP
try:
    from src.utils.zpp_kpi_calculator import (
        fetch_zpp_kpi_data,
        get_zpp_equipment_names,
        get_zpp_equipment_categories
    )
    ZPP_KPI_AVAILABLE = True
except ImportError:
    ZPP_KPI_AVAILABLE = False
    print("[AVISO] Módulo ZPP KPI não disponível - nenhum dado será exibido")

from src.components.maintenance_kpi_graphs import (
    create_kpi_bar_chart,
    create_kpi_sunburst_chart,
    create_kpi_summary_table,
    create_empty_kpi_figure,
    create_kpi_line_chart,
    create_comparison_bar_chart
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
        ctx = dash.callback_context

        if not ctx.triggered:
            raise PreventUpdate

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # Carregar apenas uma vez no início
        if trigger_id == "interval-initial-load" and current_data:
            raise PreventUpdate

        # Validar inputs baseado no tipo
        if not period_type:
            period_type = "last12"  # Padrão

        if period_type in ["year", "last12"]:
            if not ref_year:
                ref_year = 2025  # Ano onde os dados ZPP estão disponíveis

            if period_type == "year":
                # Todos os meses do ano
                months = list(range(1, 13))
                year = ref_year
            else:  # last12
                # Últimos 12 meses a partir do ano
                # Assumir que estamos em dez/2025, então últimos 12 = jan-dez 2025
                months = list(range(1, 13))
                year = ref_year

        else:  # custom
            if not start_date or not end_date:
                # Usar padrão se não informado
                year = 2025  # Ano onde os dados ZPP estão disponíveis
                months = list(range(1, 13))
            else:
                # TODO: Implementar lógica para extrair ano/meses do date range
                # Por enquanto usar todos os meses de 2025
                year = 2025  # Ano onde os dados ZPP estão disponíveis
                months = list(range(1, 13))

        # Buscar dados reais - INTEGRAÇÃO ZPP
        print("\n" + "="*80)
        print(">>> CALLBACK 2: CARREGANDO DADOS DE KPI")
        print("="*80)
        print(f"Ano: {year}, Meses: {months}")
        print(f"ZPP_KPI_AVAILABLE: {ZPP_KPI_AVAILABLE}")

        data = {}
        all_equipment = []
        has_data = False

        if ZPP_KPI_AVAILABLE:
            print("[TENTANDO] Buscar dados reais do ZPP...")
            try:
                # Tentar buscar dados reais do ZPP
                data = fetch_zpp_kpi_data(year, months)
                all_equipment = list(data.keys())
                has_data = len(data) > 0

                if has_data:
                    print(f"[SUCESSO] Dados ZPP carregados!")
                    print(f"  - Equipamentos: {all_equipment}")
                    print(f"  - Total: {len(all_equipment)} equipamentos")
                else:
                    print("[AVISO] Nenhum dado disponível no banco para o período selecionado")
                print("="*80 + "\n")
            except Exception as e:
                # Sem fallback - apenas informar erro
                print(f"[ERRO] Falha ao carregar dados ZPP: {e}")
                print("[INFO] Nenhum dado será exibido")
                print("="*80 + "\n")
                import traceback
                traceback.print_exc()
                has_data = False
        else:
            # Módulo ZPP não disponível - não mostrar nada
            print("[AVISO] Módulo ZPP não disponível")
            print("[INFO] Nenhum dado será exibido")
            print("="*80 + "\n")
            has_data = False

        # Buscar nomes e categorias de equipamentos
        if has_data and ZPP_KPI_AVAILABLE:
            try:
                names = get_zpp_equipment_names()
                categories = get_zpp_equipment_categories()
            except Exception as e:
                print(f"[AVISO] Erro ao buscar nomes/categorias: {e}")
                names = {eq: eq for eq in all_equipment}  # Fallback: usar IDs como nomes
                categories = {}
        else:
            names = {}
            categories = {}

        return {
            "period_type": period_type,
            "year": year,
            "months": months,
            "equipment_ids": all_equipment,
            "data": data,
            "targets": get_kpi_targets() if has_data else {},
            "names": names,
            "categories": categories,
            "has_data": has_data  # Indicador se há dados disponíveis
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
        Atualiza os 4 cards de resumo com médias e badges de status.
        """
        if not stored_data or not stored_data.get("has_data", False):
            return ["--"] * 3 + ["Sem dados", "secondary"] * 3 + ["0"]

        data = stored_data["data"]
        targets = stored_data["targets"]
        equipment_ids = stored_data["equipment_ids"]
        months = stored_data["months"]

        # Calcular médias
        averages = calculate_kpi_averages(data, equipment_ids, months)

        # Se não houver médias válidas após o cálculo
        if not averages.get("by_equipment"):
            return ["--"] * 3 + ["Sem dados", "secondary"] * 3 + ["0"]

        # MTBF (maior é melhor)
        mtbf_avg = averages["mtbf"]
        mtbf_meets_target = mtbf_avg >= targets["mtbf"]
        mtbf_badge_text = "✓ Acima da Meta" if mtbf_meets_target else "⚠ Abaixo da Meta"
        mtbf_badge_color = "success" if mtbf_meets_target else "danger"

        # MTTR (menor é melhor) - converter de horas para minutos
        mttr_avg_minutes = averages["mttr"] * 60
        mttr_target_minutes = targets["mttr"] * 60
        mttr_meets_target = mttr_avg_minutes <= mttr_target_minutes
        mttr_badge_text = "✓ Dentro da Meta" if mttr_meets_target else "⚠ Acima da Meta"
        mttr_badge_color = "success" if mttr_meets_target else "danger"

        # Taxa de Avaria (menor é melhor)
        breakdown_avg = averages["breakdown_rate"]
        breakdown_meets_target = breakdown_avg <= targets["breakdown_rate"]
        breakdown_badge_text = "✓ Dentro da Meta" if breakdown_meets_target else "⚠ Acima da Meta"
        breakdown_badge_color = "success" if breakdown_meets_target else "danger"

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
        Atualiza os 3 gráficos de barras com médias, metas e tendências.
        """
        template = TEMPLATE_THEME_MINTY  # Tema fixo em Minty (claro)

        if not stored_data:
            return [
                create_empty_kpi_figure("MTBF", template),
                create_empty_kpi_figure("MTTR", template),
                create_empty_kpi_figure("Taxa de Avaria", template)
            ]

        data = stored_data["data"]
        targets = stored_data["targets"]
        names = stored_data["names"]
        equipment_ids = stored_data["equipment_ids"]
        months = stored_data["months"]

        # Calcular médias por equipamento
        averages = calculate_kpi_averages(data, equipment_ids, months)

        # Verificar se há dados válidos
        if not averages.get("by_equipment"):
            return [
                create_empty_kpi_figure("MTBF", template),
                create_empty_kpi_figure("MTTR", template),
                create_empty_kpi_figure("Taxa de Avaria", template)
            ]

        # Preparar dados para gráficos
        mtbf_values = [averages["by_equipment"][eq]["mtbf"] for eq in equipment_ids]
        mttr_values = [averages["by_equipment"][eq]["mttr"] for eq in equipment_ids]
        breakdown_values = [averages["by_equipment"][eq]["breakdown_rate"] for eq in equipment_ids]

        # Criar gráficos
        fig_mtbf = create_kpi_bar_chart(
            equipment_ids, mtbf_values, "MTBF",
            averages["mtbf"], targets["mtbf"],
            names, template
        )

        fig_mttr = create_kpi_bar_chart(
            equipment_ids, mttr_values, "MTTR",
            averages["mttr"], targets["mttr"],
            names, template
        )

        fig_breakdown = create_kpi_bar_chart(
            equipment_ids, breakdown_values, "Taxa de Avaria",
            averages["breakdown_rate"], targets["breakdown_rate"],
            names, template
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

        if not stored_data:
            # Retornar sunbursts vazios
            empty_fig = go.Figure()
            empty_fig.update_layout(template=template)
            return [empty_fig] * 3

        data = stored_data["data"]
        names = stored_data["names"]
        categories = stored_data["categories"]
        equipment_ids = stored_data["equipment_ids"]
        months = stored_data["months"]

        # Calcular médias por equipamento
        averages = calculate_kpi_averages(data, equipment_ids, months)

        if not averages.get("by_equipment"):
            empty_fig = go.Figure()
            empty_fig.update_layout(template=template)
            return [empty_fig] * 3

        # Preparar dados para sunbursts (apenas valores por equipamento)
        mtbf_by_eq = {eq: averages["by_equipment"][eq]["mtbf"] for eq in equipment_ids}
        mttr_by_eq = {eq: averages["by_equipment"][eq]["mttr"] for eq in equipment_ids}
        breakdown_by_eq = {eq: averages["by_equipment"][eq]["breakdown_rate"] for eq in equipment_ids}

        # Criar sunbursts
        fig_mtbf = create_kpi_sunburst_chart(
            mtbf_by_eq, "MTBF", categories, names, template
        )

        fig_mttr = create_kpi_sunburst_chart(
            mttr_by_eq, "MTTR", categories, names, template
        )

        fig_breakdown = create_kpi_sunburst_chart(
            breakdown_by_eq, "Taxa de Avaria", categories, names, template
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
        Atualiza a tabela resumo com todos os KPIs por equipamento.
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
        targets = stored_data["targets"]
        names = stored_data["names"]
        equipment_ids = stored_data["equipment_ids"]
        months = stored_data["months"]

        # Calcular médias por equipamento
        averages = calculate_kpi_averages(data, equipment_ids, months)

        if not averages.get("by_equipment"):
            return html.Div([
                html.I(className="bi bi-inbox fs-1 text-muted mb-3"),
                html.P(
                    "Nenhum dado disponível para o período selecionado.",
                    className="text-muted text-center"
                )
            ], className="text-center py-5")

        # Criar tabela
        return create_kpi_summary_table(
            averages["by_equipment"],
            targets,
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
        Atualiza dados (reais do ZPP ou fictícios) com mesmos filtros.
        """
        if not current_data:
            raise PreventUpdate

        year = current_data["year"]
        months = current_data["months"]

        # Re-buscar dados com mesmos parâmetros - INTEGRAÇÃO ZPP
        new_data = {}
        has_data = False

        if ZPP_KPI_AVAILABLE:
            try:
                # Tentar buscar dados reais atualizados do ZPP
                print(f"[INFO] Atualizando dados ZPP para {year}, meses {months}")
                new_data = fetch_zpp_kpi_data(year, months)
                has_data = len(new_data) > 0

                if has_data:
                    print(f"[✓] Dados ZPP atualizados: {len(new_data)} equipamentos")
                else:
                    print("[AVISO] Nenhum dado disponível no banco após atualização")
            except Exception as e:
                # Sem fallback - apenas informar erro
                print(f"[ERRO] Erro ao atualizar dados ZPP: {e}")
                print("[INFO] Nenhum dado será exibido")
                has_data = False
        else:
            # Módulo ZPP não disponível
            print("[AVISO] Módulo ZPP não disponível")
            print("[INFO] Nenhum dado será exibido")
            has_data = False

        # Atualizar nomes e categorias se houver dados
        if has_data and ZPP_KPI_AVAILABLE:
            try:
                current_data["names"] = get_zpp_equipment_names()
                current_data["categories"] = get_zpp_equipment_categories()
                current_data["equipment_ids"] = list(new_data.keys())
            except Exception as e:
                print(f"[AVISO] Erro ao atualizar nomes/categorias: {e}")

        # Atualizar dados e flag
        current_data["data"] = new_data
        current_data["has_data"] = has_data

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
    # CALLBACK 10: Atualizar Cards Individuais
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

        # Calcular médias por equipamento
        averages = calculate_kpi_averages(data, equipment_ids, months)

        if not averages.get("by_equipment") or equipment_id not in averages["by_equipment"]:
            return ["--", "--", "--"]

        eq_data = averages["by_equipment"][equipment_id]

        return [
            f"{eq_data['mtbf']:.1f} h",
            f"{eq_data['mttr'] * 60:.1f} min",
            f"{eq_data['breakdown_rate']:.2f} %"
        ]

    # ============================================================
    # CALLBACK 11: Atualizar Tab Individual (Gráficos)
    # ============================================================
    @app.callback(
        [
            Output("line-chart-mtbf-individual", "figure"),
            Output("line-chart-mttr-individual", "figure"),
            Output("line-chart-breakdown-individual", "figure"),
            Output("comparison-chart-individual", "figure")
        ],
        [
            Input("store-indicator-filters", "data"),
            Input("dropdown-equipment-individual", "value")
        ]
    )
    def update_individual_tab(stored_data, equipment_id):
        """
        Atualiza gráficos da tab Individual quando:
        - Dados são carregados/atualizados
        - Equipamento selecionado muda
        """
        import plotly.graph_objects as go

        template = TEMPLATE_THEME_MINTY  # Tema fixo em Minty (claro)

        if not stored_data or not equipment_id:
            # Retornar figuras vazias
            return [go.Figure()] * 4

        data = stored_data["data"]
        targets = stored_data["targets"]
        names = stored_data["names"]
        months = stored_data["months"]
        all_equipment = stored_data["equipment_ids"]

        # Calcular médias gerais por mês
        general_avg_by_month = calculate_general_avg_by_month(data, all_equipment, months)

        # Dados do equipamento selecionado
        eq_data_by_month = data.get(equipment_id, [])

        if not eq_data_by_month or not general_avg_by_month:
            return [go.Figure()] * 4

        # Extrair valores por mês
        mtbf_values = [m["mtbf"] for m in eq_data_by_month if m["month"] in months]
        mttr_values = [m["mttr"] for m in eq_data_by_month if m["month"] in months]
        breakdown_values = [m["breakdown_rate"] for m in eq_data_by_month if m["month"] in months]

        mtbf_avg = [general_avg_by_month[m]["mtbf"] for m in months if m in general_avg_by_month]
        mttr_avg = [general_avg_by_month[m]["mttr"] for m in months if m in general_avg_by_month]
        breakdown_avg = [general_avg_by_month[m]["breakdown_rate"] for m in months if m in general_avg_by_month]

        # Criar gráficos de linha
        fig_mtbf = create_kpi_line_chart(
            months, mtbf_values, mtbf_avg,
            "MTBF", names.get(equipment_id, equipment_id), targets["mtbf"], template
        )

        fig_mttr = create_kpi_line_chart(
            months, mttr_values, mttr_avg,
            "MTTR", names.get(equipment_id, equipment_id), targets["mttr"], template
        )

        fig_breakdown = create_kpi_line_chart(
            months, breakdown_values, breakdown_avg,
            "Taxa de Avaria", names.get(equipment_id, equipment_id), targets["breakdown_rate"], template
        )

        # Gráfico de comparação
        eq_summary = {
            "mtbf": sum(mtbf_values) / len(mtbf_values) if mtbf_values else 0,
            "mttr": sum(mttr_values) / len(mttr_values) if mttr_values else 0,
            "breakdown_rate": sum(breakdown_values) / len(breakdown_values) if breakdown_values else 0
        }

        general_summary = {
            "mtbf": sum(mtbf_avg) / len(mtbf_avg) if mtbf_avg else 0,
            "mttr": sum(mttr_avg) / len(mttr_avg) if mttr_avg else 0,
            "breakdown_rate": sum(breakdown_avg) / len(breakdown_avg) if breakdown_avg else 0
        }

        fig_comparison = create_comparison_bar_chart(
            eq_summary, general_summary, names.get(equipment_id, equipment_id), template
        )

        return [fig_mtbf, fig_mttr, fig_breakdown, fig_comparison]

