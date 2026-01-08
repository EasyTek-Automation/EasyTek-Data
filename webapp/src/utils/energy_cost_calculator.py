# src/utils/energy_cost_calculator.py

"""
Utilitário para cálculo de custos de energia elétrica.

Funcionalidades:
- Classificação de horários ponta/fora-ponta
- Cálculo de demanda máxima (kW) a partir de consumo (kWh)
- Cálculo de custos mensais (TUSD + Energia + Demanda)
- Formatação de valores em Real brasileiro (R$)
"""

import pandas as pd
from datetime import datetime


def is_peak_hour(time_obj, peak_start, peak_end):
    """
    Verifica se um horário está dentro do período de ponta.
    Suporta horários noturnos (ex: 23:00-06:00).

    Args:
        time_obj: Objeto datetime.time
        peak_start: String "HH:MM" com horário de início da ponta
        peak_end: String "HH:MM" com horário de término da ponta

    Returns:
        bool: True se o horário está no período de ponta

    Example:
        >>> is_peak_hour(datetime.strptime("19:30", "%H:%M").time(), "18:00", "21:00")
        True
        >>> is_peak_hour(datetime.strptime("14:00", "%H:%M").time(), "18:00", "21:00")
        False
        >>> is_peak_hour(datetime.strptime("02:00", "%H:%M").time(), "23:00", "06:00")
        True
    """
    start_time = datetime.strptime(peak_start, "%H:%M").time()
    end_time = datetime.strptime(peak_end, "%H:%M").time()

    if start_time <= end_time:
        # Horário normal: 18:00 - 21:00
        return start_time <= time_obj <= end_time
    else:
        # Horário noturno: 23:00 - 06:00 (cruza meia-noite)
        return time_obj >= start_time or time_obj <= end_time


def classify_consumption_data(df, peak_start, peak_end):
    """
    Classifica cada registro de consumo como ponta ou fora-ponta.

    Args:
        df: DataFrame com colunas 'DateTime' e 'kwh_intervalo'
        peak_start: String "HH:MM" com horário de início da ponta
        peak_end: String "HH:MM" com horário de término da ponta

    Returns:
        DataFrame: DataFrame original com coluna adicional 'is_peak' (bool)

    Example:
        >>> df = pd.DataFrame({
        ...     'DateTime': pd.date_range('2026-01-01', periods=24, freq='H'),
        ...     'kwh_intervalo': [10] * 24
        ... })
        >>> df = classify_consumption_data(df, "18:00", "21:00")
        >>> df['is_peak'].sum()  # Conta quantos registros são ponta
        3
    """
    # Criar cópia para evitar SettingWithCopyWarning
    df = df.copy()

    # Aplicar classificação a cada registro
    df['is_peak'] = df['DateTime'].dt.time.apply(
        lambda t: is_peak_hour(t, peak_start, peak_end)
    )

    return df


def calculate_max_demand(df):
    """
    Calcula a demanda máxima (kW) a partir de dados de consumo (kWh).

    A demanda é calculada convertendo kWh em kW com base no intervalo de medição.
    Para intervalos de 15 minutos: kW = kWh / 0,25 = kWh × 4

    Args:
        df: DataFrame com colunas 'kwh_intervalo' e 'is_peak'

    Returns:
        dict: {
            'ponta_kw': float,         # Demanda máxima no horário de ponta
            'fora_ponta_kw': float     # Demanda máxima fora do horário de ponta
        }

    Example:
        >>> df = pd.DataFrame({
        ...     'kwh_intervalo': [10, 20, 15, 25],
        ...     'is_peak': [True, True, False, False]
        ... })
        >>> demand = calculate_max_demand(df)
        >>> demand['ponta_kw']
        80.0  # 20 kWh * 4 = 80 kW
        >>> demand['fora_ponta_kw']
        100.0  # 25 kWh * 4 = 100 kW
    """
    # Criar cópia para evitar SettingWithCopyWarning
    df = df.copy()

    # Converter kWh para kW (assumindo intervalos de 15 minutos)
    # kW = kWh / (intervalo_em_horas)
    # Para 15 min: kW = kWh / 0.25 = kWh * 4
    df['kw'] = df['kwh_intervalo'] * 4

    # Calcular máximo para ponta e fora-ponta
    ponta_df = df[df['is_peak'] == True]
    fora_ponta_df = df[df['is_peak'] == False]

    ponta_max = ponta_df['kw'].max() if not ponta_df.empty else 0
    fora_ponta_max = fora_ponta_df['kw'].max() if not fora_ponta_df.empty else 0

    return {
        'ponta_kw': float(ponta_max) if pd.notna(ponta_max) else 0.0,
        'fora_ponta_kw': float(fora_ponta_max) if pd.notna(fora_ponta_max) else 0.0
    }


def calculate_monthly_costs(consumption_df, demand_df, config):
    """
    Calcula todos os custos de energia elétrica para um período.

    IMPORTANTE: Consumo e Demanda são calculados de períodos DIFERENTES:
    - Consumo (kWh): Do período selecionado pelo filtro
    - Demanda (kW): Do MÊS INTEIRO (padrão de cobrança)

    Fórmula total:
    Custo Total = TUSD_P + TUSD_FP + Energia_P + Energia_FP + Demanda_P + Demanda_FP

    Onde:
    - TUSD_P = kWh_ponta × preco_tusd_ponta
    - TUSD_FP = kWh_fora_ponta × preco_tusd_fora_ponta
    - Energia_P = kWh_ponta × preco_energia_ponta
    - Energia_FP = kWh_fora_ponta × preco_energia_fora_ponta
    - Demanda_P = demanda_usd_ponta × (% SE03 na demanda contratada ponta)
    - Demanda_FP = demanda_usd_fora_ponta × (% SE03 na demanda contratada fora ponta)

    Args:
        consumption_df: DataFrame para cálculo de CONSUMO (período filtrado)
                        Deve conter: DateTime, IDMaq, kwh_intervalo
        demand_df: DataFrame para cálculo de DEMANDA (mês inteiro)
                   Deve conter: DateTime, IDMaq, kwh_intervalo
        config: Dicionário com configuração de tarifas
                Deve conter:
                - demanda_usd_ponta
                - demanda_usd_fora_ponta
                - demanda_contratada_ponta_kw
                - demanda_contratada_fora_ponta_kw
                - preco_tusd_ponta
                - preco_tusd_fora_ponta
                - preco_energia_ponta
                - preco_energia_fora_ponta
                - horario_ponta_inicio
                - horario_ponta_fim

    Returns:
        dict or None: Dicionário com todas as métricas de custo, ou None se não houver dados
        {
            'demand_ponta_pct': float,          # Porcentagem da demanda contratada ponta
            'demand_fora_ponta_pct': float,     # Porcentagem da demanda contratada fora ponta
            'demand_ponta_kw': float,           # Demanda máxima ponta (kW) - DO MÊS INTEIRO
            'demand_fora_ponta_kw': float,      # Demanda máxima fora ponta (kW) - DO MÊS INTEIRO
            'kwh_ponta': float,                 # Total kWh consumido na ponta - DO PERÍODO FILTRADO
            'kwh_fora_ponta': float,            # Total kWh consumido fora ponta - DO PERÍODO FILTRADO
            'custo_tusd_ponta': float,          # Custo TUSD ponta (R$)
            'custo_tusd_fora_ponta': float,     # Custo TUSD fora ponta (R$)
            'custo_energia_ponta': float,       # Custo energia ponta (R$)
            'custo_energia_fora_ponta': float,  # Custo energia fora ponta (R$)
            'custo_demanda_ponta': float,       # Custo demanda ponta (R$)
            'custo_demanda_fora_ponta': float,  # Custo demanda fora ponta (R$)
            'custo_total': float                # Custo total (R$)
        }

    Example:
        >>> config = {
        ...     'demanda_usd_ponta': 1500,
        ...     'demanda_usd_fora_ponta': 800,
        ...     'demanda_contratada_ponta_kw': 2000,
        ...     'demanda_contratada_fora_ponta_kw': 3500,
        ...     'preco_tusd_ponta': 0.45,
        ...     'preco_tusd_fora_ponta': 0.30,
        ...     'preco_energia_ponta': 0.65,
        ...     'preco_energia_fora_ponta': 0.40,
        ...     'horario_ponta_inicio': '18:00',
        ...     'horario_ponta_fim': '21:00'
        ... }
        >>> costs = calculate_monthly_costs(df_period, df_month, config)
        >>> costs['custo_total']
        12345.67
    """
    # 1. Filtrar apenas equipamentos da SE03
    # IMPORTANTE: MM01 é o disjuntor geral (soma de MM02-MM07)
    # Não incluir MM01 para evitar contagem duplicada
    se03_equipment = [f"SE03_MM0{i}" for i in range(2, 8)]  # MM02 até MM07

    # Filtrar DataFrame de consumo (período selecionado)
    df_consumption = consumption_df[consumption_df['IDMaq'].isin(se03_equipment)].copy()

    # Filtrar DataFrame de demanda (mês inteiro)
    df_demand = demand_df[demand_df['IDMaq'].isin(se03_equipment)].copy()

    if df_consumption.empty or df_demand.empty:
        return None  # Sem dados disponíveis

    # 2. Classificar registros como ponta ou fora-ponta
    df_consumption = classify_consumption_data(
        df_consumption,
        config['horario_ponta_inicio'],
        config['horario_ponta_fim']
    )

    df_demand = classify_consumption_data(
        df_demand,
        config['horario_ponta_inicio'],
        config['horario_ponta_fim']
    )

    # 3. Calcular demanda máxima (kW) do MÊS INTEIRO e porcentagens
    demand = calculate_max_demand(df_demand)

    # Calcular porcentagem da demanda contratada
    demand_ponta_pct = (
        (demand['ponta_kw'] / config['demanda_contratada_ponta_kw'] * 100)
        if config['demanda_contratada_ponta_kw'] > 0
        else 0
    )

    demand_fora_ponta_pct = (
        (demand['fora_ponta_kw'] / config['demanda_contratada_fora_ponta_kw'] * 100)
        if config['demanda_contratada_fora_ponta_kw'] > 0
        else 0
    )

    # 4. Somar consumo (kWh) do PERÍODO FILTRADO
    kwh_ponta = df_consumption[df_consumption['is_peak'] == True]['kwh_intervalo'].sum()
    kwh_fora_ponta = df_consumption[df_consumption['is_peak'] == False]['kwh_intervalo'].sum()

    # 5. Calcular custos de consumo (TUSD + Energia) - baseado no período filtrado
    custo_tusd_ponta = kwh_ponta * config['preco_tusd_ponta']
    custo_tusd_fora_ponta = kwh_fora_ponta * config['preco_tusd_fora_ponta']
    custo_energia_ponta = kwh_ponta * config['preco_energia_ponta']
    custo_energia_fora_ponta = kwh_fora_ponta * config['preco_energia_fora_ponta']

    # 6. Calcular custos de demanda (proporcional ao uso da SE03 no mês inteiro)
    custo_demanda_ponta = config['demanda_usd_ponta'] * (demand_ponta_pct / 100)
    custo_demanda_fora_ponta = config['demanda_usd_fora_ponta'] * (demand_fora_ponta_pct / 100)

    # 7. Calcular custo total
    custo_total = (
        custo_tusd_ponta +
        custo_tusd_fora_ponta +
        custo_energia_ponta +
        custo_energia_fora_ponta +
        custo_demanda_ponta +
        custo_demanda_fora_ponta
    )

    # 8. Retornar todas as métricas
    return {
        'demand_ponta_pct': float(demand_ponta_pct),
        'demand_fora_ponta_pct': float(demand_fora_ponta_pct),
        'demand_ponta_kw': float(demand['ponta_kw']),
        'demand_fora_ponta_kw': float(demand['fora_ponta_kw']),
        'kwh_ponta': float(kwh_ponta),
        'kwh_fora_ponta': float(kwh_fora_ponta),
        'custo_tusd_ponta': float(custo_tusd_ponta),
        'custo_tusd_fora_ponta': float(custo_tusd_fora_ponta),
        'custo_energia_ponta': float(custo_energia_ponta),
        'custo_energia_fora_ponta': float(custo_energia_fora_ponta),
        'custo_demanda_ponta': float(custo_demanda_ponta),
        'custo_demanda_fora_ponta': float(custo_demanda_fora_ponta),
        'custo_total': float(custo_total)
    }


def format_brl(value):
    """
    Formata um valor como moeda brasileira (Real).

    Formato: R$ 1.234,56
    - Ponto (.) para separador de milhares
    - Vírgula (,) para separador decimal

    Args:
        value: Valor numérico a ser formatado

    Returns:
        str: Valor formatado como R$ X.XXX,XX

    Example:
        >>> format_brl(1234.56)
        'R$ 1.234,56'
        >>> format_brl(1000000.99)
        'R$ 1.000.000,99'
        >>> format_brl(0.5)
        'R$ 0,50'
    """
    if value is None or pd.isna(value):
        return "R$ 0,00"

    # Formatar com separadores americanos primeiro
    formatted = f"{float(value):,.2f}"

    # Trocar separadores para padrão brasileiro
    # Temporariamente substituir vírgula por placeholder
    formatted = formatted.replace(",", "TEMP")
    # Trocar ponto por vírgula (decimal brasileiro)
    formatted = formatted.replace(".", ",")
    # Trocar placeholder por ponto (milhares brasileiro)
    formatted = formatted.replace("TEMP", ".")

    return f"R$ {formatted}"


def format_percentage(value):
    """
    Formata um valor como porcentagem brasileira.

    Formato: 85,3%
    - Vírgula (,) para separador decimal
    - Uma casa decimal

    Args:
        value: Valor numérico (já em escala de porcentagem, não 0-1)

    Returns:
        str: Valor formatado como X,X%

    Example:
        >>> format_percentage(85.3)
        '85,3%'
        >>> format_percentage(100.0)
        '100,0%'
        >>> format_percentage(12.75)
        '12,8%'
    """
    if value is None or pd.isna(value):
        return "0,0%"

    # Formatar com 1 casa decimal
    formatted = f"{float(value):.1f}"

    # Trocar ponto por vírgula (decimal brasileiro)
    formatted = formatted.replace(".", ",")

    return f"{formatted}%"
