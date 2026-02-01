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
    print("[AVISO] Módulo ZPP KPI não disponível - nenhum dado será exibido")

from src.components.maintenance_kpi_graphs import (
    create_kpi_bar_chart,
    create_kpi_sunburst_chart,
    create_kpi_summary_table,
    create_empty_kpi_figure,
    create_kpi_line_chart,
    create_comparison_bar_chart,
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
        ctx = dash.callback_context

        if not ctx.triggered:
            raise PreventUpdate

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # Se interval disparou e NÃO há dados ainda, carregar dados iniciais
        # Se botão apply foi clicado, sempre recarregar
        if trigger_id == "interval-initial-load" and current_data and current_data.get("data"):
            # Interval disparou mas já temos dados - apenas atualizar metas sem recarregar ZPP
            print("[INFO] Interval: Atualizando apenas metas (dados já carregados)")
            current_data["equipment_targets"] = get_all_equipment_targets()
            current_data["targets"] = get_kpi_targets("GENERAL")
            return current_data

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

        # Obter metas individualizadas por equipamento
        # SEMPRE carregar metas, mesmo se não houver dados (para evitar erros nos callbacks)
        equipment_targets = get_all_equipment_targets()
        general_target = get_kpi_targets("GENERAL")

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
        Atualiza os 4 cards de resumo com médias gerais comparadas com meta da planta.
        """
        if not stored_data or not stored_data.get("has_data", False):
            return ["--"] * 3 + ["Sem dados", "secondary"] * 3 + ["0"]

        data = stored_data["data"]
        equipment_targets = stored_data["equipment_targets"]  # ALTERADO
        equipment_ids = stored_data["equipment_ids"]
        months = stored_data["months"]

        # Calcular médias
        averages = calculate_kpi_averages(data, equipment_ids, months)

        # Se não houver médias válidas após o cálculo
        if not averages.get("by_equipment"):
            return ["--"] * 3 + ["Sem dados", "secondary"] * 3 + ["0"]

        # ALTERADO: Usar meta geral da planta (GENERAL) para os cards de resumo
        general_target = equipment_targets.get("GENERAL", {"mtbf": 0, "mttr": 999, "breakdown_rate": 100})

        # MTBF (maior é melhor)
        mtbf_avg = averages["mtbf"]
        mtbf_meets_target = mtbf_avg >= general_target["mtbf"]
        mtbf_badge_text = "✓ Acima da Meta" if mtbf_meets_target else "⚠ Abaixo da Meta"
        mtbf_badge_color = "success" if mtbf_meets_target else "danger"

        # MTTR (menor é melhor) - converter de horas para minutos
        mttr_avg_minutes = averages["mttr"] * 60
        mttr_target_minutes = general_target["mttr"] * 60
        mttr_meets_target = mttr_avg_minutes <= mttr_target_minutes
        mttr_badge_text = "✓ Dentro da Meta" if mttr_meets_target else "⚠ Acima da Meta"
        mttr_badge_color = "success" if mttr_meets_target else "danger"

        # Taxa de Avaria (menor é melhor)
        breakdown_avg = averages["breakdown_rate"]
        breakdown_meets_target = breakdown_avg <= general_target["breakdown_rate"]
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
        Atualiza os 3 gráficos de barras com médias e metas individualizadas.
        """
        template = TEMPLATE_THEME_MINTY  # Tema fixo em Minty (claro)

        if not stored_data:
            return [
                create_empty_kpi_figure("MTBF", template),
                create_empty_kpi_figure("MTTR", template),
                create_empty_kpi_figure("Taxa de Avaria", template)
            ]

        data = stored_data["data"]
        equipment_targets = stored_data["equipment_targets"]  # ALTERADO: Usar metas por equipamento
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

        # Preparar dicionários de metas individuais por equipamento
        # Fallback para meta geral se equipamento não tiver meta específica
        general_target = equipment_targets.get("GENERAL", {"mtbf": 0, "mttr": 999, "breakdown_rate": 100})

        mtbf_targets = {}
        mttr_targets = {}
        breakdown_targets = {}

        for eq_id in equipment_ids:
            eq_target = equipment_targets.get(eq_id, general_target)
            mtbf_targets[eq_id] = eq_target.get("mtbf", general_target["mtbf"])
            mttr_targets[eq_id] = eq_target.get("mttr", general_target["mttr"])
            breakdown_targets[eq_id] = eq_target.get("breakdown_rate", general_target["breakdown_rate"])

        # Criar gráficos com metas individualizadas
        fig_mtbf = create_kpi_bar_chart(
            equipment_ids, mtbf_values, "MTBF",
            averages["mtbf"], mtbf_targets,  # ALTERADO: Dict de metas
            names, template
        )

        fig_mttr = create_kpi_bar_chart(
            equipment_ids, mttr_values, "MTTR",
            averages["mttr"], mttr_targets,  # ALTERADO: Dict de metas
            names, template
        )

        fig_breakdown = create_kpi_bar_chart(
            equipment_ids, breakdown_values, "Taxa de Avaria",
            averages["breakdown_rate"], breakdown_targets,  # ALTERADO: Dict de metas
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

        print("\n" + "="*80)
        print(">>> REFRESH: Forçando atualização completa de dados e metas")
        print("="*80)

        year = current_data.get("year", 2025)
        months = current_data.get("months", list(range(1, 13)))

        # PASSO 1: Atualizar metas do MongoDB (SEMPRE)
        print("[1/2] Atualizando metas do MongoDB...")
        equipment_targets = get_all_equipment_targets()
        general_targets = get_kpi_targets("GENERAL")
        print(f"  - Meta geral MTBF: {general_targets['mtbf']:.1f}h")
        print(f"  - Meta geral MTTR: {general_targets['mttr']*60:.0f}min")
        print(f"  - Metas específicas: {len([k for k in equipment_targets.keys() if k != 'GENERAL'])} equipamentos")

        # PASSO 2: Re-buscar dados do ZPP
        new_data = {}
        has_data = False

        if ZPP_KPI_AVAILABLE:
            try:
                print(f"[2/2] Atualizando dados ZPP para {year}, meses {months}...")
                new_data = fetch_zpp_kpi_data(year, months)
                has_data = len(new_data) > 0

                if has_data:
                    print(f"  - ✓ Dados carregados: {len(new_data)} equipamentos")
                else:
                    print("  - ⚠ Nenhum dado disponível no banco")
            except Exception as e:
                print(f"  - ✗ ERRO ao atualizar dados ZPP: {e}")
                has_data = False
        else:
            print("[2/2] Módulo ZPP não disponível")
            has_data = False

        # Atualizar nomes e categorias se houver dados
        if has_data and ZPP_KPI_AVAILABLE:
            try:
                current_data["names"] = get_zpp_equipment_names()
                current_data["categories"] = get_zpp_equipment_categories()
                current_data["equipment_ids"] = list(new_data.keys())
            except Exception as e:
                print(f"[AVISO] Erro ao atualizar nomes/categorias: {e}")

        # Atualizar store com novos dados e metas
        current_data["data"] = new_data
        current_data["has_data"] = has_data
        current_data["equipment_targets"] = equipment_targets
        current_data["targets"] = general_targets

        print("="*80 + "\n")
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

        print("[INFO] Navegação detectada - Atualizando metas do MongoDB...")

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
            # Retornar figuras vazias
            return [go.Figure()] * 3

        data = stored_data["data"]
        equipment_targets = stored_data["equipment_targets"]  # ALTERADO: Usar metas por equipamento
        equipment_ids = stored_data["equipment_ids"]
        months = stored_data["months"]

        # Calcular médias por equipamento
        averages = calculate_kpi_averages(data, equipment_ids, months)

        if not averages.get("by_equipment") or equipment_id not in averages["by_equipment"]:
            return [go.Figure()] * 3

        eq_data = averages["by_equipment"][equipment_id]

        # Obter meta específica do equipamento (ou usar meta geral como fallback)
        eq_target = equipment_targets.get(equipment_id, equipment_targets.get("GENERAL", {}))

        # Criar gauges com meta individualizada
        fig_mtbf = create_kpi_gauge(
            value=eq_data['mtbf'],
            kpi_name="MTBF",
            target_value=eq_target.get("mtbf", 0),  # ALTERADO: Meta individual
            template=template
        )

        fig_mttr = create_kpi_gauge(
            value=eq_data['mttr'],
            kpi_name="MTTR",
            target_value=eq_target.get("mttr", 999),  # ALTERADO: Meta individual
            template=template
        )

        fig_breakdown = create_kpi_gauge(
            value=eq_data['breakdown_rate'],
            kpi_name="Taxa de Avaria",
            target_value=eq_target.get("breakdown_rate", 100),  # ALTERADO: Meta individual
            template=template
        )

        return [fig_mtbf, fig_mttr, fig_breakdown]

    # ============================================================
    # CALLBACK 12: Atualizar Gráficos de Linha (Evolução Temporal)
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
        Atualiza gráficos da tab Individual com metas individualizadas quando:
        - Dados são carregados/atualizados
        - Equipamento selecionado muda
        """
        import plotly.graph_objects as go

        template = TEMPLATE_THEME_MINTY  # Tema fixo em Minty (claro)

        if not stored_data or not equipment_id:
            # Retornar figuras vazias
            return [go.Figure()] * 4

        data = stored_data["data"]
        equipment_targets = stored_data["equipment_targets"]  # ALTERADO: Usar metas por equipamento
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

        # Obter meta específica do equipamento (ou usar meta geral como fallback)
        eq_target = equipment_targets.get(equipment_id, equipment_targets.get("GENERAL", {}))

        # Criar gráficos de linha com meta individualizada
        fig_mtbf = create_kpi_line_chart(
            months, mtbf_values, mtbf_avg,
            "MTBF", names.get(equipment_id, equipment_id),
            eq_target.get("mtbf", 0),  # ALTERADO: Meta individual
            template
        )

        fig_mttr = create_kpi_line_chart(
            months, mttr_values, mttr_avg,
            "MTTR", names.get(equipment_id, equipment_id),
            eq_target.get("mttr", 999),  # ALTERADO: Meta individual
            template
        )

        fig_breakdown = create_kpi_line_chart(
            months, breakdown_values, breakdown_avg,
            "Taxa de Avaria", names.get(equipment_id, equipment_id),
            eq_target.get("breakdown_rate", 100),  # ALTERADO: Meta individual
            template
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

        if not stored_data or not equipment_id:
            # Retornar figura vazia
            return go.Figure()

        year = stored_data.get("year")
        months = stored_data.get("months", [])
        names = stored_data.get("names", {})

        # Buscar top 10 paradas do equipamento
        if ZPP_KPI_AVAILABLE:
            try:
                print(f"[INFO] Buscando top 10 paradas para {equipment_id}")
                breakdowns_data = fetch_top_breakdowns_by_equipment(
                    equipment_id=equipment_id,
                    year=year,
                    months=months,
                    top_n=10
                )

                if breakdowns_data:
                    print(f"[SUCESSO] {len(breakdowns_data)} paradas encontradas")
                else:
                    print(f"[AVISO] Nenhuma parada encontrada para {equipment_id}")

                # Criar gráfico
                fig = create_top_breakdowns_chart(
                    breakdowns_data=breakdowns_data,
                    equipment_name=names.get(equipment_id, equipment_id),
                    template=template
                )

                return fig

            except Exception as e:
                print(f"[ERRO] Falha ao buscar top paradas: {e}")
                import traceback
                traceback.print_exc()

                # Retornar figura vazia com mensagem de erro
                fig = go.Figure()
                fig.add_annotation(
                    x=0.5, y=0.5,
                    text=f"Erro ao carregar dados: {str(e)}",
                    xref="paper", yref="paper",
                    showarrow=False,
                    font=dict(size=14, color='#dc3545')
                )
                fig.update_layout(
                    template=template,
                    xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
                    yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
                    height=400
                )
                return fig
        else:
            # Módulo ZPP não disponível
            fig = go.Figure()
            fig.add_annotation(
                x=0.5, y=0.5,
                text="Módulo ZPP não disponível",
                xref="paper", yref="paper",
                showarrow=False,
                font=dict(size=14, color='#6c757d')
            )
            fig.update_layout(
                template=template,
                xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
                yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
                height=400
            )
            return fig

