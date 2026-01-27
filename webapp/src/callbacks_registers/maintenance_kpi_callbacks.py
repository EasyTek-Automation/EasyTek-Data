"""
Maintenance KPI Callbacks
Callbacks para a página de indicadores de manutenção
"""

from dash import Output, Input, State, dcc, html, no_update
from dash.exceptions import PreventUpdate
import dash
import pandas as pd
from dash_bootstrap_templates import ThemeSwitchAIO

from src.utils.maintenance_demo_data import (
    generate_monthly_kpi_data,
    calculate_kpi_averages,
    get_kpi_targets,
    get_equipment_names,
    get_equipment_categories
)
from src.components.maintenance_kpi_graphs import (
    create_kpi_bar_chart,
    create_kpi_sunburst_chart,
    create_kpi_summary_table,
    create_empty_kpi_figure
)


def register_maintenance_kpi_callbacks(app):
    """
    Registra todos os callbacks da página de indicadores de manutenção.

    Args:
        app: Instância do Dash app
    """

    # ============================================================
    # CALLBACK 1: Toggle Filtros
    # ============================================================
    @app.callback(
        Output("collapse-indicator-filters", "is_open"),
        Input("btn-toggle-indicator-filters", "n_clicks"),
        State("collapse-indicator-filters", "is_open"),
        prevent_initial_call=True
    )
    def toggle_filters(n_clicks, is_open):
        """Toggle do painel de filtros."""
        if n_clicks:
            return not is_open
        return is_open

    # ============================================================
    # CALLBACK 2: Carregar Dados Iniciais (ao abrir página)
    # ============================================================
    @app.callback(
        Output("store-indicator-filters", "data"),
        [
            Input("btn-apply-indicator-filters", "n_clicks"),
            Input("interval-initial-load", "n_intervals")  # Carrega automaticamente
        ],
        [
            State("filter-indicator-year", "value"),
            State("filter-indicator-months", "value"),
            State("store-indicator-filters", "data")
        ]
    )
    def load_or_apply_filters(n_clicks, n_intervals, year, months, current_data):
        """
        Carrega dados automaticamente ao abrir a página OU quando clicar em Aplicar.
        """
        ctx = dash.callback_context

        if not ctx.triggered:
            raise PreventUpdate

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # Se já tem dados carregados e trigger foi o interval, não recarregar
        if trigger_id == "interval-initial-load" and current_data:
            raise PreventUpdate

        # Se clicou em Aplicar, validar inputs
        if trigger_id == "btn-apply-indicator-filters":
            if not n_clicks or not year or not months:
                raise PreventUpdate
            if not isinstance(months, list) or len(months) == 0:
                raise PreventUpdate

        # Se não tem dados ainda ou valores não são válidos, usar padrões
        if not year or not months:
            year = 2026
            months = list(range(1, 13))
        elif not isinstance(months, list):
            months = [months] if months else list(range(1, 13))

        # Gerar dados com os filtros
        all_equipment = list(get_equipment_names().keys())
        data = generate_monthly_kpi_data(year, months, all_equipment)

        return {
            "year": year,
            "months": months,
            "equipment_ids": all_equipment,
            "data": data,
            "targets": get_kpi_targets(),
            "names": get_equipment_names(),
            "categories": get_equipment_categories()
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
        if not stored_data:
            return ["--"] * 3 + ["Aguardando dados", "secondary"] * 3 + ["--"]

        data = stored_data["data"]
        targets = stored_data["targets"]
        equipment_ids = stored_data["equipment_ids"]
        months = stored_data["months"]

        # Calcular médias
        averages = calculate_kpi_averages(data, equipment_ids, months)

        # MTBF (maior é melhor)
        mtbf_avg = averages["mtbf"]
        mtbf_meets_target = mtbf_avg >= targets["mtbf"]
        mtbf_badge_text = "✓ Acima da Meta" if mtbf_meets_target else "⚠ Abaixo da Meta"
        mtbf_badge_color = "success" if mtbf_meets_target else "danger"

        # MTTR (menor é melhor)
        mttr_avg = averages["mttr"]
        mttr_meets_target = mttr_avg <= targets["mttr"]
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
            f"{mttr_avg:.1f} h",
            mttr_badge_text,
            mttr_badge_color,
            f"{breakdown_avg:.1f} %",
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
            Input("store-indicator-filters", "data"),
            Input(ThemeSwitchAIO.ids.switch("theme"), "value")
        ]
    )
    def update_bar_charts(stored_data, theme_switch_on):
        """
        Atualiza os 3 gráficos de barras com médias, metas e tendências.
        """
        template = 'minty' if theme_switch_on else 'darkly'

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
            Input("store-indicator-filters", "data"),
            Input(ThemeSwitchAIO.ids.switch("theme"), "value")
        ]
    )
    def update_sunburst_charts(stored_data, theme_switch_on):
        """
        Atualiza os 3 gráficos Sunburst hierárquicos.
        """
        import plotly.graph_objects as go

        template = 'minty' if theme_switch_on else 'darkly'

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
        if not stored_data:
            return html.P(
                "Selecione os filtros e clique em 'Aplicar' para visualizar os dados.",
                className="text-muted text-center py-4"
            )

        data = stored_data["data"]
        targets = stored_data["targets"]
        names = stored_data["names"]
        equipment_ids = stored_data["equipment_ids"]
        months = stored_data["months"]

        # Calcular médias por equipamento
        averages = calculate_kpi_averages(data, equipment_ids, months)

        if not averages.get("by_equipment"):
            return html.P(
                "Não há dados disponíveis para o período selecionado.",
                className="text-muted text-center py-4"
            )

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
                    "MTTR (h)": month_entry["mttr"],
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
        Regenera dados fictícios com mesmos filtros.
        Simula atualização de dados em tempo real.
        """
        if not current_data:
            raise PreventUpdate

        # Re-gerar dados com mesmos parâmetros
        new_data = generate_monthly_kpi_data(
            current_data["year"],
            current_data["months"],
            current_data["equipment_ids"]
        )

        # Atualizar apenas os dados, mantendo resto
        current_data["data"] = new_data

        return current_data
