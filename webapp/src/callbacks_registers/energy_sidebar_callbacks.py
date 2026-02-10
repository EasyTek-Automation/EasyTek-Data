# src/callbacks_registers/energy_sidebar_callbacks.py

"""
Callbacks para sidebar dinâmica das páginas de energia.
Implementa sistema de sidebar consciente de tabs (tab-aware sidebar).

Funcionalidades:
- Troca conteúdo da sidebar baseado em pathname E tab ativa
- Calcula e exibe custos em tempo real para a SE03
- Atualiza automaticamente a cada 10 segundos via interval-component
"""

from dash import Input, Output
from dash.exceptions import PreventUpdate
from src.components.sidebars.energy_sidebar import (
    create_se03_cost_sidebar_with_groups,
    create_energy_sidebar_no_config,
    create_default_energy_sidebar_content
)
from src.database.connection import get_mongo_connection
from src.utils.energy_cost_calculator import calculate_costs_by_groups, format_brl, format_percentage
from datetime import datetime, timedelta
import pandas as pd
import pytz


def register_energy_sidebar_callbacks(app):
    """
    Registra callbacks para sidebar tab-aware de energia.

    Callbacks:
    1. update_sidebar_layout_for_tab: Troca layout da sidebar baseado na tab ativa
    2. calculate_se03_costs: Calcula e atualiza custos da SE03

    Args:
        app: Instância da aplicação Dash.
    """

    # ========================================
    # CALLBACK 1: Trocar layout da sidebar baseado em tab
    # ========================================
    @app.callback(
        Output("sidebar-dynamic-content", "children", allow_duplicate=True),
        [
            Input("url", "pathname"),
            Input("energy-tabs", "active_tab")
        ],
        prevent_initial_call='initial_duplicate'
    )
    def update_sidebar_layout_for_tab(pathname, active_tab):
        """
        Atualiza o layout da sidebar quando a página é energia E quando a tab muda.

        IMPORTANTE: Este callback tem PRIORIDADE sobre o callback padrão de sidebar
        quando a página é /utilities/energy ou /energy. Para outras páginas,
        delega ao sistema padrão.

        Lógica:
        - Se pathname = /utilities/energy OU /energy:
            - Se active_tab = "se03":
                - Se config existe → mostrar sidebar com custos
                - Se config não existe → mostrar mensagem "configure tarifas"
            - Senão: mostrar sidebar padrão de energia
        - Senão: delegar para get_sidebar_content_for_page()

        Args:
            pathname: Caminho da URL atual
            active_tab: Tab ativa (valor do componente dbc.Tabs)

        Returns:
            html.Div: Conteúdo apropriado para a sidebar
        """
        # Só interceptar para páginas de energia
        if pathname in ["/utilities/energy", "/energy"]:

            # Verificar se configuração de tarifas existe
            try:
                config_collection = get_mongo_connection("AMG_EnergyConfig")
                config = config_collection.find_one()
            except Exception as e:
                config = None

            # Determinar conteúdo baseado na tab ativa
            if active_tab == "se03":
                # Tab SE03: mostrar custos por grupo (se config existir) ou mensagem
                if config:
                    return create_se03_cost_sidebar_with_groups()
                else:
                    return create_energy_sidebar_no_config()
            else:
                # Outras tabs de energia: mensagem padrão
                return create_default_energy_sidebar_content()

        # Para páginas não-energia, delegar ao sistema padrão
        from src.sidebar import get_sidebar_content_for_page
        return get_sidebar_content_for_page(pathname)


    # ========================================
    # CALLBACK 2: Calcular e exibir custos da SE03 POR GRUPO
    # ========================================
    @app.callback(
        [
            # Outputs: Demanda Compartilhada
            Output("se03-demand-shared-ponta-kw", "children"),
            Output("se03-demand-shared-ponta-pct", "children"),
            Output("se03-demand-shared-fora-kw", "children"),
            Output("se03-demand-shared-fora-pct", "children"),

            # Outputs: Grupo 1 (Transversais)
            Output("se03-group1-equipment-list", "children"),
            Output("se03-group1-kwh-ponta", "children"),
            Output("se03-group1-kwh-fora", "children"),
            Output("se03-group1-custo-tusd", "children"),
            Output("se03-group1-custo-energia", "children"),
            Output("se03-group1-custo-demanda", "children"),
            Output("se03-group1-custo-total", "children"),

            # Outputs: Grupo 2 (Longitudinais)
            Output("se03-group2-equipment-list", "children"),
            Output("se03-group2-kwh-ponta", "children"),
            Output("se03-group2-kwh-fora", "children"),
            Output("se03-group2-custo-tusd", "children"),
            Output("se03-group2-custo-energia", "children"),
            Output("se03-group2-custo-demanda", "children"),
            Output("se03-group2-custo-total", "children"),

            # Outputs: Total Geral
            Output("se03-total-kwh", "children"),
            Output("se03-total-custo-tusd", "children"),
            Output("se03-total-custo-energia", "children"),
            Output("se03-total-custo-demanda", "children"),
            Output("se03-total-custo-final", "children"),
        ],
        [
            Input("energy-tabs", "active_tab"),
            Input("interval-component", "n_intervals"),  # Auto-refresh a cada 10s
            Input("store-start-date", "data"),  # Filtro de data início
            Input("store-end-date", "data"),    # Filtro de data fim
            Input("store-start-hour", "data"),  # Filtro de hora início
            Input("store-end-hour", "data"),    # Filtro de hora fim
            Input("machine-dropdown-group1", "value"),  # Equipamentos Transversais
            Input("machine-dropdown-group2", "value"),  # Equipamentos Longitudinais
        ],
        prevent_initial_call=False
    )
    def calculate_se03_costs_by_groups(
        active_tab, n_intervals, start_date, end_date, start_hour, end_hour,
        group1_equipment, group2_equipment
    ):
        """
        Calcula e atualiza custos da SE03 SEPARADOS POR GRUPO (Transversais vs Longitudinais).
        Roda automaticamente a cada 10 segundos via interval-component.

        Funcionalidades:
        - Calcula consumo (kWh) separado para cada grupo do período filtrado
        - Calcula demanda (kW) do mês inteiro de TODOS os equipamentos
        - Rateia custo de demanda proporcionalmente ao consumo de cada grupo
        - Respeita filtros de equipamentos (permite testar impacto removendo equipamentos)

        Args:
            active_tab: Tab ativa do componente energy-tabs
            n_intervals: Contador de intervalos (usado para auto-refresh)
            start_date: Data inicial do filtro (string ISO ou None)
            end_date: Data final do filtro (string ISO ou None)
            start_hour: Hora inicial do filtro (string HH:MM ou None)
            end_hour: Hora final do filtro (string HH:MM ou None)
            group1_equipment: Lista de equipamentos Transversais selecionados
            group2_equipment: Lista de equipamentos Longitudinais selecionados

        Returns:
            tuple: 23 strings formatadas com valores de custo ou "N/A" se não houver dados
        """
        # Só calcular quando tab SE03 estiver ativa
        if active_tab != "se03":
            raise PreventUpdate

        try:
            # ========================================
            # PASSO 1: Validar equipamentos selecionados
            # ========================================
            if not group1_equipment:
                group1_equipment = []
            if not group2_equipment:
                group2_equipment = []

            # Se nenhum equipamento selecionado, retornar N/A
            if not group1_equipment and not group2_equipment:
                return ["N/A"] * 23

            # ========================================
            # PASSO 2: Carregar configuração de tarifas
            # ========================================
            config_collection = get_mongo_connection("AMG_EnergyConfig")
            config = config_collection.find_one()

            if not config:
                # Sem configuração - retornar placeholders
                return ["---"] * 23

            # ========================================
            # PASSO 3: Processar filtros de data/hora
            # ========================================
            tz = pytz.timezone('America/Sao_Paulo')

            # Se não houver filtros, usar últimas 24h como padrão
            if not start_date or not end_date:
                now = datetime.now(tz)
                period_end = now
                period_start = now - timedelta(hours=24)
            else:
                # Parse das datas (podem vir como string ISO)
                if isinstance(start_date, str):
                    start_date_obj = datetime.fromisoformat(start_date.replace('Z', '+00:00')).date()
                else:
                    start_date_obj = start_date

                if isinstance(end_date, str):
                    end_date_obj = datetime.fromisoformat(end_date.replace('Z', '+00:00')).date()
                else:
                    end_date_obj = end_date

                # Parse das horas (formato HH:MM)
                if start_hour:
                    start_h, start_m = map(int, start_hour.split(':'))
                else:
                    start_h, start_m = 0, 0

                if end_hour:
                    end_h, end_m = map(int, end_hour.split(':'))
                else:
                    end_h, end_m = 23, 59

                # Construir datetimes completos
                period_start = tz.localize(datetime.combine(start_date_obj, datetime.min.time()).replace(hour=start_h, minute=start_m))
                period_end = tz.localize(datetime.combine(end_date_obj, datetime.min.time()).replace(hour=end_h, minute=end_m))

            # Converter para UTC (MongoDB armazena em UTC)
            period_start_utc = period_start.astimezone(pytz.UTC).replace(tzinfo=None)
            period_end_utc = period_end.astimezone(pytz.UTC).replace(tzinfo=None)

            # ========================================
            # PASSO 4: Consultar dados do período selecionado
            # ========================================
            consumo_collection = get_mongo_connection("AMG_Consumo")

            current_period_data = list(consumo_collection.find({
                "DateTime": {
                    "$gte": period_start_utc,
                    "$lte": period_end_utc
                }
            }))

            if not current_period_data:
                # Sem dados disponíveis
                return ["N/A"] * 23

            # Converter para DataFrame
            df_current = pd.DataFrame(current_period_data)
            df_current['DateTime'] = pd.to_datetime(df_current['DateTime'])
            df_current['DateTime'] = df_current['DateTime'].dt.tz_localize('UTC').dt.tz_convert('America/Sao_Paulo')

            # ========================================
            # PASSO 5: Consultar dados do MÊS INTEIRO (para demanda)
            # ========================================
            current_month_start = period_start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # Último dia do mês
            if period_start.month == 12:
                next_month = period_start.replace(year=period_start.year + 1, month=1, day=1)
            else:
                next_month = period_start.replace(month=period_start.month + 1, day=1)
            current_month_end = next_month - timedelta(seconds=1)

            # Converter para UTC
            current_month_start_utc = current_month_start.astimezone(pytz.UTC).replace(tzinfo=None)
            current_month_end_utc = current_month_end.astimezone(pytz.UTC).replace(tzinfo=None)

            # Query para mês completo
            full_month_data = list(consumo_collection.find({
                "DateTime": {
                    "$gte": current_month_start_utc,
                    "$lte": current_month_end_utc
                }
            }))

            if not full_month_data:
                return ["N/A"] * 23

            # Converter para DataFrame
            df_full_month = pd.DataFrame(full_month_data)
            df_full_month['DateTime'] = pd.to_datetime(df_full_month['DateTime'])
            df_full_month['DateTime'] = df_full_month['DateTime'].dt.tz_localize('UTC').dt.tz_convert('America/Sao_Paulo')

            # ========================================
            # PASSO 6: Calcular custos POR GRUPO
            # ========================================
            costs = calculate_costs_by_groups(
                consumption_df=df_current,
                demand_df=df_full_month,
                config=config,
                group1_equipment=group1_equipment,
                group2_equipment=group2_equipment
            )

            if not costs:
                return ["N/A"] * 23

            # ========================================
            # PASSO 7: Formatar listas de equipamentos
            # ========================================
            group1_names = [eq.replace("SE03_", "") for eq in costs['group1']['equipment_list']]
            group2_names = [eq.replace("SE03_", "") for eq in costs['group2']['equipment_list']]

            # ========================================
            # PASSO 8: Retornar todos os valores formatados
            # ========================================
            return [
                # Demanda Compartilhada (4 outputs)
                f"{costs['demand_shared']['demand_ponta_kw']:.0f} kW",
                format_percentage(costs['demand_shared']['demand_ponta_pct']),
                f"{costs['demand_shared']['demand_fora_ponta_kw']:.0f} kW",
                format_percentage(costs['demand_shared']['demand_fora_ponta_pct']),

                # Grupo 1 - Transversais (7 outputs)
                ", ".join(group1_names) if group1_names else "Nenhum",
                f"{costs['group1']['kwh_ponta']:.0f} kWh",
                f"{costs['group1']['kwh_fora_ponta']:.0f} kWh",
                format_brl(costs['group1']['custo_tusd_ponta'] + costs['group1']['custo_tusd_fora_ponta']),
                format_brl(costs['group1']['custo_energia_ponta'] + costs['group1']['custo_energia_fora_ponta']),
                format_brl(costs['group1']['custo_demanda_ponta'] + costs['group1']['custo_demanda_fora_ponta']),
                format_brl(costs['group1']['custo_total']),

                # Grupo 2 - Longitudinais (7 outputs)
                ", ".join(group2_names) if group2_names else "Nenhum",
                f"{costs['group2']['kwh_ponta']:.0f} kWh",
                f"{costs['group2']['kwh_fora_ponta']:.0f} kWh",
                format_brl(costs['group2']['custo_tusd_ponta'] + costs['group2']['custo_tusd_fora_ponta']),
                format_brl(costs['group2']['custo_energia_ponta'] + costs['group2']['custo_energia_fora_ponta']),
                format_brl(costs['group2']['custo_demanda_ponta'] + costs['group2']['custo_demanda_fora_ponta']),
                format_brl(costs['group2']['custo_total']),

                # Total Geral (5 outputs)
                f"{costs['total']['kwh_ponta'] + costs['total']['kwh_fora_ponta']:.0f} kWh",
                format_brl(costs['total']['custo_tusd_ponta'] + costs['total']['custo_tusd_fora_ponta']),
                format_brl(costs['total']['custo_energia_ponta'] + costs['total']['custo_energia_fora_ponta']),
                format_brl(costs['total']['custo_demanda_ponta'] + costs['total']['custo_demanda_fora_ponta']),
                format_brl(costs['total']['custo_total']),
            ]

        except Exception as e:
            # Log de erro detalhado
            import traceback
            traceback.print_exc()

            # Retornar estado de erro
            return ["Erro"] * 23
