"""
Módulo para cálculo de KPIs de Manutenção baseado nas collections ZPP
Implementa indicadores M01 (MTBF), M02 (MTTR) e M03 (Taxa de Avaria)
conforme documento PRO017 - KPI Calculation Procedures

Collections utilizadas:
- ZPP_Producao_2025: Dados de produção (horas de atividade)
- ZPP_Paradas_2025: Dados de paradas (avarias)

Códigos de avaria considerados: 201, S201, 202, S202, 203, S203
"""

import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
from src.database.connection import get_mongo_connection


# ==================== CONFIGURAÇÕES ====================

# Códigos de motivo que representam AVARIAS
BREAKDOWN_CODES = ['201', 'S201', '202', 'S202', '203', 'S203']

# Mapeamento de categorias por prefixo de equipamento
EQUIPMENT_CATEGORY_PREFIXES = {
    "Longitudinais": ["LONGI"],
    "Prensas": ["PRENS"],
    "Transversais": ["TRANS"]
}


# ==================== FUNÇÕES DE BUSCA DE DADOS ====================

def fetch_zpp_equipment_list() -> List[str]:
    """
    Busca lista única de equipamentos (linhas) das collections ZPP

    Returns:
        List[str]: Lista de equipamentos únicos (ex: ["LONGI001", "LONGI002", ...])
    """
    try:
        # Buscar de ambas as collections para garantir lista completa
        paradas_collection = get_mongo_connection("ZPP_Paradas_2025")
        producao_collection = get_mongo_connection("ZPP_Producao_2025")

        # Buscar valores únicos do campo 'linea' (paradas)
        equipment_from_paradas = set(paradas_collection.distinct("linea"))

        # Buscar valores únicos do campo 'pto_trab' (produção)
        equipment_from_producao = set(producao_collection.distinct("pto_trab"))

        # Combinar ambas as listas
        equipment_list = sorted(equipment_from_paradas | equipment_from_producao)

        # Remover valores vazios ou None
        equipment_list = [eq for eq in equipment_list if eq]

        print(f"[ZPP] {len(equipment_list)} equipamentos encontrados: {equipment_list}")
        return equipment_list

    except Exception as e:
        print(f"[ERRO] Falha ao buscar lista de equipamentos: {e}")
        return []


def fetch_zpp_production_data(year: int, months: List[int]) -> pd.DataFrame:
    """
    Busca dados de produção da collection ZPP_Producao_2025

    Args:
        year: Ano de referência (ex: 2025)
        months: Lista de meses (ex: [1, 2, 3] para Jan-Mar)

    Returns:
        DataFrame com colunas: [linea, date, month, horasact]
    """
    try:
        collection = get_mongo_connection("ZPP_Producao_2025")

        # Construir query MongoDB
        query = {
            "_year": year,
            "_processed": True
        }

        # Buscar documentos
        cursor = collection.find(
            query,
            {
                "pto_trab": 1,  # Campo de linha (pode ser pto_trab ou linea)
                "fininotif": 1,  # Data de início
                "horasact": 1,   # Horas de atividade
                "_id": 0
            }
        )

        # Converter para lista
        records = list(cursor)

        if not records:
            print(f"[AVISO] Nenhum dado de produção encontrado para {year}")
            return pd.DataFrame(columns=["linea", "date", "month", "horasact"])

        # Processar dados
        processed_records = []
        for record in records:
            # Extrair data
            date_obj = record.get("fininotif")
            if date_obj is None:
                continue  # Pular registros sem data

            # Converter para datetime se necessário
            if isinstance(date_obj, dict) and "$date" in date_obj:
                # Formato JSON do MongoDB
                date_str = date_obj["$date"]
                date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            elif isinstance(date_obj, datetime):
                # Já é um objeto datetime (retorno do PyMongo)
                date = date_obj
            else:
                continue  # Pular registros com formato inválido

            # Filtrar por mês
            if date.month not in months:
                continue

            # Extrair linha (priorizar pto_trab, fallback para linea)
            linea = record.get("pto_trab")
            if not linea:
                linea = record.get("linea")
            if not linea:
                continue

            # Extrair horas de atividade
            horasact = record.get("horasact", 0)

            processed_records.append({
                "linea": linea,
                "date": date.date(),
                "month": date.month,
                "horasact": float(horasact)
            })

        df = pd.DataFrame(processed_records)
        print(f"[ZPP] Produção: {len(df)} registros carregados para {year}, meses {months}")

        return df

    except Exception as e:
        print(f"[ERRO] Falha ao buscar dados de produção: {e}")
        return pd.DataFrame(columns=["linea", "date", "month", "horasact"])


def fetch_zpp_breakdown_data(year: int, months: List[int]) -> pd.DataFrame:
    """
    Busca dados de paradas (avarias) da collection ZPP_Paradas_2025

    Args:
        year: Ano de referência (ex: 2025)
        months: Lista de meses (ex: [1, 2, 3])

    Returns:
        DataFrame com colunas: [linea, date, month, motivo, duracao_min]
    """
    try:
        collection = get_mongo_connection("ZPP_Paradas_2025")

        # Construir query MongoDB
        query = {
            "_year": year,
            "_processed": True,
            "motivo": {"$in": BREAKDOWN_CODES}  # Filtrar apenas avarias
        }

        # Buscar documentos
        cursor = collection.find(
            query,
            {
                "linea": 1,
                "data_inicio": 1,
                "motivo": 1,
                "duracao_min": 1,
                "_id": 0
            }
        )

        # Converter para lista
        records = list(cursor)

        if not records:
            print(f"[AVISO] Nenhuma parada (avaria) encontrada para {year}")
            return pd.DataFrame(columns=["linea", "date", "month", "motivo", "duracao_min"])

        # Processar dados
        processed_records = []
        for record in records:
            # Extrair data
            date_obj = record.get("data_inicio")
            if date_obj is None:
                continue  # Pular registros sem data

            # Converter para datetime se necessário
            if isinstance(date_obj, dict) and "$date" in date_obj:
                # Formato JSON do MongoDB
                date_str = date_obj["$date"]
                date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            elif isinstance(date_obj, datetime):
                # Já é um objeto datetime (retorno do PyMongo)
                date = date_obj
            else:
                continue  # Pular registros com formato inválido

            # Filtrar por mês
            if date.month not in months:
                continue

            # Extrair campos
            linea = record.get("linea")
            motivo = record.get("motivo")
            duracao_min = record.get("duracao_min", 0)

            if not linea:
                continue

            processed_records.append({
                "linea": linea,
                "date": date.date(),
                "month": date.month,
                "motivo": motivo,
                "duracao_min": float(duracao_min)
            })

        df = pd.DataFrame(processed_records)
        print(f"[ZPP] Paradas: {len(df)} registros de avarias carregados para {year}, meses {months}")

        return df

    except Exception as e:
        print(f"[ERRO] Falha ao buscar dados de paradas: {e}")
        return pd.DataFrame(columns=["linea", "date", "month", "motivo", "duracao_min"])


# ==================== FUNÇÕES DE CÁLCULO DE KPIs ====================

def calculate_monthly_kpis(production_df: pd.DataFrame, breakdown_df: pd.DataFrame) -> Dict:
    """
    Calcula KPIs mensais por equipamento baseado nos dados de produção e paradas

    Implementa fórmulas do documento PRO017:
    - M01 (MTBF): (∑Horas Atividade - ∑Tempo Falha) / Número Falhas
    - M02 (MTTR): Minutos Paragem / Número Paragens (convertido para horas)
    - M03 (Taxa Avaria): (Tempo Paragem / Horas Atividade) × 100

    Args:
        production_df: DataFrame com dados de produção
        breakdown_df: DataFrame com dados de paradas

    Returns:
        dict: Estrutura {
            "LINEA001": [
                {"month": 1, "mtbf": 22.3, "mttr": 1.8, "breakdown_rate": 2.9},
                ...
            ],
            ...
        }
    """
    result = {}

    # Verificar se há dados
    if production_df.empty:
        print("[AVISO] Sem dados de produção para calcular KPIs")
        return result

    # Obter lista de equipamentos e meses únicos
    equipment_list = production_df['linea'].unique()
    months = sorted(production_df['month'].unique())

    print(f"[ZPP] Calculando KPIs para {len(equipment_list)} equipamentos, {len(months)} meses")

    for linea in equipment_list:
        monthly_data = []

        # Filtrar dados do equipamento
        prod_linea = production_df[production_df['linea'] == linea]
        breakdown_linea = breakdown_df[breakdown_df['linea'] == linea]

        for month in months:
            # Filtrar dados do mês
            prod_month = prod_linea[prod_linea['month'] == month]
            breakdown_month = breakdown_linea[breakdown_linea['month'] == month]

            # Calcular agregações
            total_active_hours = prod_month['horasact'].sum()

            if breakdown_month.empty:
                # Sem paradas no mês
                num_failures = 0
                total_breakdown_minutes = 0
            else:
                num_failures = len(breakdown_month)
                total_breakdown_minutes = breakdown_month['duracao_min'].sum()

            total_breakdown_hours = total_breakdown_minutes / 60.0

            # Calcular KPIs
            if total_active_hours > 0:
                # M01 - MTBF (horas)
                if num_failures > 0:
                    mtbf = (total_active_hours - total_breakdown_hours) / num_failures
                else:
                    # Sem falhas = MTBF infinito (usar valor alto)
                    mtbf = 999.0

                # M02 - MTTR (horas)
                if num_failures > 0:
                    mttr = total_breakdown_hours / num_failures
                else:
                    mttr = 0.0

                # M03 - Taxa de Avaria (%)
                breakdown_rate = (total_breakdown_hours / total_active_hours) * 100
            else:
                # Sem horas de atividade
                mtbf = None
                mttr = None
                breakdown_rate = None

            monthly_data.append({
                "month": month,
                "mtbf": round(mtbf, 2) if mtbf is not None else None,
                "mttr": round(mttr, 2) if mttr is not None else None,
                "breakdown_rate": round(breakdown_rate, 2) if breakdown_rate is not None else None
            })

        result[linea] = monthly_data

    print(f"[ZPP] KPIs calculados com sucesso para {len(result)} equipamentos")
    return result


# ==================== FUNÇÃO PRINCIPAL ====================

def fetch_zpp_kpi_data(year: int, months: List[int]) -> Dict:
    """
    Função principal: busca dados do MongoDB e calcula KPIs

    Args:
        year: Ano de referência (ex: 2025)
        months: Lista de meses (ex: [1, 2, 3] para Jan-Mar)

    Returns:
        dict: Dados de KPIs no formato esperado pelos callbacks

    Raises:
        Exception: Se houver erro ao buscar ou processar dados
    """
    print("\n" + "-"*60)
    print(f">>> ZPP: Iniciando fetch_zpp_kpi_data")
    print(f"    Ano: {year}")
    print(f"    Meses: {months}")
    print("-"*60)

    try:
        # 1. Buscar dados de produção
        production_df = fetch_zpp_production_data(year, months)

        # 2. Buscar dados de paradas
        breakdown_df = fetch_zpp_breakdown_data(year, months)

        # 3. Calcular KPIs
        kpi_data = calculate_monthly_kpis(production_df, breakdown_df)

        if not kpi_data:
            raise Exception("Nenhum dado de KPI foi calculado (sem dados de produção)")

        print(f"[ZPP] ✓ Dados carregados com sucesso: {len(kpi_data)} equipamentos")
        return kpi_data

    except Exception as e:
        print(f"[ERRO] Falha ao buscar dados ZPP: {e}")
        raise


# ==================== FUNÇÕES AUXILIARES ====================

def get_zpp_equipment_categories() -> Dict[str, List[str]]:
    """
    Retorna categorias de equipamentos baseado nos prefixos

    Returns:
        dict: {
            "Longitudinais": ["LONGI001", "LONGI002"],
            "Prensas": ["PRENS001", ...],
            ...
        }
    """
    try:
        equipment_list = fetch_zpp_equipment_list()

        categories = {}

        for category_name, prefixes in EQUIPMENT_CATEGORY_PREFIXES.items():
            # Filtrar equipamentos que começam com algum dos prefixos
            category_equipment = [
                eq for eq in equipment_list
                if any(eq.startswith(prefix) for prefix in prefixes)
            ]

            if category_equipment:
                categories[category_name] = category_equipment

        # Adicionar categoria "Outros" para equipamentos não categorizados
        categorized = [eq for cat_list in categories.values() for eq in cat_list]
        others = [eq for eq in equipment_list if eq not in categorized]
        if others:
            categories["Outros"] = others

        return categories

    except Exception as e:
        print(f"[ERRO] Falha ao buscar categorias: {e}")
        return {}


def get_zpp_equipment_names() -> Dict[str, str]:
    """
    Retorna dicionário de equipamentos {id: nome_amigavel}

    Returns:
        dict: {"LONGI001": "Longitudinal 001", ...}
    """
    try:
        equipment_list = fetch_zpp_equipment_list()

        # Criar nomes amigáveis baseado no ID
        names = {}
        for eq_id in equipment_list:
            # Extrair tipo e número
            if eq_id.startswith("LONGI"):
                tipo = "Longitudinal"
                numero = eq_id.replace("LONGI", "")
            elif eq_id.startswith("PRENS"):
                tipo = "Prensa"
                numero = eq_id.replace("PRENS", "")
            elif eq_id.startswith("TRANS"):
                tipo = "Transversal"
                numero = eq_id.replace("TRANS", "")
            else:
                tipo = "Equipamento"
                numero = eq_id

            names[eq_id] = f"{tipo} {numero}"

        return names

    except Exception as e:
        print(f"[ERRO] Falha ao buscar nomes de equipamentos: {e}")
        return {}


# ==================== FUNÇÃO DE TESTE ====================

if __name__ == "__main__":
    """Script de teste para validar cálculos"""
    print("\n" + "="*80)
    print("TESTE: Módulo ZPP KPI Calculator")
    print("="*80 + "\n")

    # Testar busca de equipamentos
    print("1. Buscando lista de equipamentos...")
    equipments = fetch_zpp_equipment_list()
    print(f"   → Encontrados: {equipments}\n")

    # Testar busca de categorias
    print("2. Buscando categorias...")
    categories = get_zpp_equipment_categories()
    for cat, eqs in categories.items():
        print(f"   → {cat}: {eqs}")
    print()

    # Testar busca de dados e cálculo de KPIs
    print("3. Testando cálculo de KPIs para Jan-Mar 2025...")
    try:
        kpi_data = fetch_zpp_kpi_data(year=2025, months=[1, 2, 3])

        # Mostrar exemplo de resultado
        if kpi_data:
            first_equipment = list(kpi_data.keys())[0]
            print(f"\n   Exemplo: {first_equipment}")
            for month_data in kpi_data[first_equipment]:
                print(f"   → Mês {month_data['month']}: "
                      f"MTBF={month_data['mtbf']}h, "
                      f"MTTR={month_data['mttr']}h, "
                      f"Taxa={month_data['breakdown_rate']}%")

        print(f"\n   ✓ Teste concluído com sucesso!")

    except Exception as e:
        print(f"\n   ✗ Erro no teste: {e}")

    print("\n" + "="*80)
