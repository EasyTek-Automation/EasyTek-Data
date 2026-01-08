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
    create_se03_cost_sidebar_content,
    create_energy_sidebar_no_config,
    create_default_energy_sidebar_content
)
from src.database.connection import get_mongo_connection
from src.utils.energy_cost_calculator import calculate_monthly_costs, format_brl, format_percentage
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
                print(f"Erro ao verificar configuração de energia: {e}")
                config = None

            # Determinar conteúdo baseado na tab ativa
            if active_tab == "se03":
                # Tab SE03: mostrar custos (se config existir) ou mensagem
                if config:
                    return create_se03_cost_sidebar_content()
                else:
                    return create_energy_sidebar_no_config()
            else:
                # Outras tabs de energia: mensagem padrão
                return create_default_energy_sidebar_content()

        # Para páginas não-energia, delegar ao sistema padrão
        from src.sidebar import get_sidebar_content_for_page
        return get_sidebar_content_for_page(pathname)


    # ========================================
    # CALLBACK 2: Calcular e exibir custos da SE03
    # ========================================
    @app.callback(
        [
            # Outputs existentes
            Output("se03-demand-ponta-pct", "children"),
            Output("se03-demand-ponta-kw", "children"),
            Output("se03-demand-fora-ponta-pct", "children"),
            Output("se03-demand-fora-ponta-kw", "children"),
            Output("se03-cost-total-current", "children"),
            Output("se03-kwh-total-current", "children"),
            Output("se03-cost-total-previous", "children"),
            Output("se03-kwh-total-previous", "children"),
            # Novos outputs DEBUG
            Output("debug-period-info", "children"),
            Output("debug-month-info", "children"),
            Output("debug-records-count", "children"),
            Output("debug-kwh-ponta", "children"),
            Output("debug-kwh-fora-ponta", "children"),
            Output("debug-tusd-ponta-calc", "children"),
            Output("debug-tusd-fora-calc", "children"),
            Output("debug-energia-ponta-calc", "children"),
            Output("debug-energia-fora-calc", "children"),
            Output("debug-demanda-ponta-calc", "children"),
            Output("debug-demanda-fora-calc", "children"),
            Output("debug-tusd-total", "children"),
            Output("debug-energia-total", "children"),
            Output("debug-demanda-total", "children"),
        ],
        [
            Input("energy-tabs", "active_tab"),
            Input("interval-component", "n_intervals"),  # Auto-refresh a cada 10s
            Input("store-start-date", "data"),  # Filtro de data início
            Input("store-end-date", "data"),    # Filtro de data fim
            Input("store-start-hour", "data"),  # Filtro de hora início
            Input("store-end-hour", "data"),    # Filtro de hora fim
        ],
        prevent_initial_call=False
    )
    def calculate_se03_costs(active_tab, n_intervals, start_date, end_date, start_hour, end_hour):
        """
        Calcula e atualiza todos os custos da SE03 para o período selecionado.
        Roda automaticamente a cada 10 segundos via interval-component.

        Fluxo:
        1. Verifica se tab ativa é "se03" (senão, não faz nada)
        2. Carrega configuração de tarifas do MongoDB
        3. Usa filtros de data/hora do usuário
        4. Consulta dados de consumo do período selecionado (AMG_Consumo)
        5. Calcula custos usando energy_cost_calculator
        6. Consulta dados do período anterior (mesmo intervalo, shifted back)
        7. Formata e retorna todos os valores

        Args:
            active_tab: Tab ativa do componente energy-tabs
            n_intervals: Contador de intervalos (usado para auto-refresh)
            start_date: Data inicial do filtro (string ISO ou None)
            end_date: Data final do filtro (string ISO ou None)
            start_hour: Hora inicial do filtro (string HH:MM ou None)
            end_hour: Hora final do filtro (string HH:MM ou None)

        Returns:
            tuple: 12 strings formatadas com valores de custo ou "N/A" se não houver dados
                   (demand_ponta_pct, demand_ponta_kw, demand_fora_ponta_pct, demand_fora_ponta_kw,
                    tusd_ponta, tusd_fora_ponta, energia_ponta, energia_fora_ponta,
                    total_current, kwh_current, total_previous, kwh_previous)
        """
        # Só calcular quando tab SE03 estiver ativa
        if active_tab != "se03":
            raise PreventUpdate

        try:
            # ========================================
            # PASSO 1: Carregar configuração de tarifas
            # ========================================
            config_collection = get_mongo_connection("AMG_EnergyConfig")
            config = config_collection.find_one()

            if not config:
                # Sem configuração - retornar placeholders
                return ["---"] * 22

            # ========================================
            # PASSO 2: Processar filtros de data/hora
            # ========================================
            tz = pytz.timezone('America/Sao_Paulo')

            # Se não houver filtros, usar últimas 24h como padrão
            if not start_date or not end_date:
                now = datetime.now(tz)
                period_end = now
                period_start = now - timedelta(hours=24)
            else:
                # Converter datas do filtro
                from datetime import date as date_type

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

            # Calcular duração do período
            period_duration = period_end - period_start

            # ========================================
            # PASSO 3: Consultar dados do período selecionado
            # ========================================
            consumo_collection = get_mongo_connection("AMG_Consumo")

            current_period_data = list(consumo_collection.find({
                "DateTime": {
                    "$gte": period_start_utc,
                    "$lte": period_end_utc
                }
            }))

            if not current_period_data:
                # Sem dados disponíveis para o período selecionado
                return ["N/A"] * 22

            # Converter para DataFrame
            df_current = pd.DataFrame(current_period_data)

            # Converter DateTime para timezone São Paulo
            df_current['DateTime'] = pd.to_datetime(df_current['DateTime'])
            df_current['DateTime'] = df_current['DateTime'].dt.tz_localize('UTC').dt.tz_convert('America/Sao_Paulo')

            # ========================================
            # PASSO 4: Consultar dados do MÊS INTEIRO (para demanda)
            # ========================================
            # Demanda é SEMPRE calculada no mês completo (padrão de cobrança)
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
                # Sem dados no mês
                return ["N/A"] * 22

            # Converter para DataFrame
            df_full_month = pd.DataFrame(full_month_data)
            df_full_month['DateTime'] = pd.to_datetime(df_full_month['DateTime'])
            df_full_month['DateTime'] = df_full_month['DateTime'].dt.tz_localize('UTC').dt.tz_convert('America/Sao_Paulo')

            # ========================================
            # PASSO 5: Calcular custos MISTOS
            # - Consumo (kWh): do período filtrado
            # - Demanda (kW): do mês inteiro
            # ========================================
            costs_current = calculate_monthly_costs(
                consumption_df=df_current,      # Consumo do período filtrado
                demand_df=df_full_month,        # Demanda do mês inteiro
                config=config
            )

            if not costs_current:
                # Cálculo falhou (ex: sem dados da SE03)
                return ["N/A"] * 22

            # ========================================
            # PASSO 6: Consultar dados do período anterior (comparação)
            # ========================================
            # Período anterior tem a mesma duração, shifted back
            prev_period_end = period_start - timedelta(seconds=1)
            prev_period_start = prev_period_end - period_duration

            # Converter para UTC
            prev_period_start_utc = prev_period_start.astimezone(pytz.UTC).replace(tzinfo=None)
            prev_period_end_utc = prev_period_end.astimezone(pytz.UTC).replace(tzinfo=None)

            previous_period_data = list(consumo_collection.find({
                "DateTime": {
                    "$gte": prev_period_start_utc,
                    "$lte": prev_period_end_utc
                }
            }))

            # Calcular custos do período anterior (se houver dados)
            if previous_period_data:
                df_previous = pd.DataFrame(previous_period_data)
                df_previous['DateTime'] = pd.to_datetime(df_previous['DateTime'])
                df_previous['DateTime'] = df_previous['DateTime'].dt.tz_localize('UTC').dt.tz_convert('America/Sao_Paulo')

                # Mês do período anterior
                prev_month_start = prev_period_start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                if prev_period_start.month == 12:
                    prev_next_month = prev_period_start.replace(year=prev_period_start.year + 1, month=1, day=1)
                else:
                    prev_next_month = prev_period_start.replace(month=prev_period_start.month + 1, day=1)
                prev_month_end = prev_next_month - timedelta(seconds=1)

                prev_month_start_utc = prev_month_start.astimezone(pytz.UTC).replace(tzinfo=None)
                prev_month_end_utc = prev_month_end.astimezone(pytz.UTC).replace(tzinfo=None)

                # Query mês completo anterior
                prev_full_month_data = list(consumo_collection.find({
                    "DateTime": {
                        "$gte": prev_month_start_utc,
                        "$lte": prev_month_end_utc
                    }
                }))

                if prev_full_month_data:
                    df_prev_full_month = pd.DataFrame(prev_full_month_data)
                    df_prev_full_month['DateTime'] = pd.to_datetime(df_prev_full_month['DateTime'])
                    df_prev_full_month['DateTime'] = df_prev_full_month['DateTime'].dt.tz_localize('UTC').dt.tz_convert('America/Sao_Paulo')

                    costs_previous = calculate_monthly_costs(
                        consumption_df=df_previous,
                        demand_df=df_prev_full_month,
                        config=config
                    )
                else:
                    costs_previous = None
            else:
                costs_previous = None

            # ========================================
            # PASSO 6: Formatar valores para exibição
            # ========================================
            return [
                # ========================================
                # OUTPUTS EXISTENTES (1-8)
                # ========================================
                # Demanda ponta
                format_percentage(costs_current['demand_ponta_pct']),
                f"{costs_current['demand_ponta_kw']:.0f} kW",

                # Demanda fora de ponta
                format_percentage(costs_current['demand_fora_ponta_pct']),
                f"{costs_current['demand_fora_ponta_kw']:.0f} kW",

                # Totais do período atual
                format_brl(costs_current['custo_total']),
                f"{costs_current['kwh_ponta'] + costs_current['kwh_fora_ponta']:.0f} kWh",

                # Totais do período anterior
                format_brl(costs_previous['custo_total']) if costs_previous else "N/A",
                f"{costs_previous['kwh_ponta'] + costs_previous['kwh_fora_ponta']:.0f} kWh" if costs_previous else "N/A",

                # ========================================
                # OUTPUTS DEBUG (9-22)
                # ========================================
                # 9. Informações do período (CONSUMO)
                f"{period_start.strftime('%d/%m/%Y %H:%M')} até {period_end.strftime('%d/%m/%Y %H:%M')}",

                # 10. Informações do mês (DEMANDA)
                f"Mês inteiro: {current_month_start.strftime('%d/%m/%Y')} até {current_month_end.strftime('%d/%m/%Y')}",

                # 11. Contagem de registros
                f"Registros (período): {len(df_current)} | Registros (mês): {len(df_full_month)}",

                # 12. kWh ponta
                f"{costs_current['kwh_ponta']:.0f} kWh",

                # 13. kWh fora de ponta
                f"{costs_current['kwh_fora_ponta']:.0f} kWh",

                # 14. Cálculo TUSD ponta
                f"Ponta: {costs_current['kwh_ponta']:.0f} kWh × {format_brl(config['preco_tusd_ponta'])} = {format_brl(costs_current['custo_tusd_ponta'])}",

                # 15. Cálculo TUSD fora de ponta
                f"Fora: {costs_current['kwh_fora_ponta']:.0f} kWh × {format_brl(config['preco_tusd_fora_ponta'])} = {format_brl(costs_current['custo_tusd_fora_ponta'])}",

                # 16. Cálculo Energia ponta
                f"Ponta: {costs_current['kwh_ponta']:.0f} kWh × {format_brl(config['preco_energia_ponta'])} = {format_brl(costs_current['custo_energia_ponta'])}",

                # 17. Cálculo Energia fora de ponta
                f"Fora: {costs_current['kwh_fora_ponta']:.0f} kWh × {format_brl(config['preco_energia_fora_ponta'])} = {format_brl(costs_current['custo_energia_fora_ponta'])}",

                # 18. Cálculo Demanda ponta (baseado no MÊS INTEIRO)
                f"Ponta: {format_brl(config['demanda_usd_ponta'])} × {format_percentage(costs_current['demand_ponta_pct'])} = {format_brl(costs_current['custo_demanda_ponta'])}",

                # 19. Cálculo Demanda fora de ponta (baseado no MÊS INTEIRO)
                f"Fora: {format_brl(config['demanda_usd_fora_ponta'])} × {format_percentage(costs_current['demand_fora_ponta_pct'])} = {format_brl(costs_current['custo_demanda_fora_ponta'])}",

                # 20. Total TUSD
                format_brl(costs_current['custo_tusd_ponta'] + costs_current['custo_tusd_fora_ponta']),

                # 21. Total Energia
                format_brl(costs_current['custo_energia_ponta'] + costs_current['custo_energia_fora_ponta']),

                # 22. Total Demanda
                format_brl(costs_current['custo_demanda_ponta'] + costs_current['custo_demanda_fora_ponta']),
            ]

        except Exception as e:
            # Log de erro detalhado
            print(f"Erro ao calcular custos da SE03: {e}")
            import traceback
            traceback.print_exc()

            # Retornar estado de erro
            return ["Erro"] * 22
