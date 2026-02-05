"""
Maintenance Demo Data Generator
Gera dados fictícios de KPIs de manutenção para demonstração
Integrado com dados reais ZPP quando disponíveis
"""

import random
from typing import Dict, List

# Importar funções de integração com ZPP (dados reais)
try:
    from src.utils.zpp_kpi_calculator import (
        get_zpp_equipment_names,
        get_zpp_equipment_categories
    )
    ZPP_AVAILABLE = True
except ImportError as e:
    print(f"[AVISO] Módulo ZPP não disponível: {e}")
    ZPP_AVAILABLE = False

# ============================================
# CONFIGURAÇÃO DE METAS POR EQUIPAMENTO (2026)
# ============================================
# Metas individualizadas por equipamento (coluna 2026 da planilha SAP)
EQUIPMENT_TARGETS_2026 = {
    # Meta geral da planta
    "GENERAL": {
        "mtbf": 11.30,      # horas
        "mttr": 39.00,      # minutos (já convertido)
        "breakdown_rate": 5.1  # %
    },
    # Longitudinais
    "LONGI001": {  # LCL 4,5
        "mtbf": 11.3,
        "mttr": 32,
        "breakdown_rate": 3.2
    },
    "LONGI002": {  # LCL 8
        "mtbf": 12,
        "mttr": 40,
        "breakdown_rate": 5.5
    },
    # Transversais
    "TRANS003": {  # LCT 2,5
        "mtbf": 15,
        "mttr": 42,
        "breakdown_rate": 2.5
    },
    "TRANS002": {  # LCT 8
        "mtbf": 15,
        "mttr": 40,
        "breakdown_rate": 4.0
    },
    "TRANS001": {  # LCT 16
        "mtbf": 20,
        "mttr": 50,
        "breakdown_rate": 4.0
    },
    # Prensas
    "PRENS001": {  # Prensa 01
        "mtbf": 9,
        "mttr": 35,
        "breakdown_rate": 4.5
    },
    "PRENS002": {  # Prensa 02
        "mtbf": 11,
        "mttr": 40,
        "breakdown_rate": 5.0
    },
    # LWB (se existir no sistema)
    "LWB": {
        "mtbf": 30,
        "mttr": 30,
        "breakdown_rate": 2.0
    }
}

# ============================================
# METAS ANTIGAS (DEPRECADO - Manter para compatibilidade)
# ============================================
KPI_TARGETS = {
    "mtbf": 11.30,          # horas - Meta geral (média da planta)
    "mttr": 39.0 / 60,      # horas - Meta geral convertida de minutos
    "breakdown_rate": 5.1   # % - Meta geral
}

# Dicionário de nomes de equipamentos (expansível e personalizável)
EQUIPMENT_NAMES = {
    "LONGI001": "LCL-4,5",  # Pode alterar lado direito depois para "Longitudinal 1"
    "LONGI002": "LCL-08",
    "PRENS001": "PRENSA-01",
    "PRENS002": "PRENSA-02",
    "TRANS001": "LCT-16",
    "TRANS002": "LCT-08",
    "TRANS003": "LCT-2,5"
}

# Categorias para hierarquia Sunburst
EQUIPMENT_CATEGORIES = {
    "Longitudinais": ["LCL-4,5", "LCL-08"],
    "Prensas": ["PRENSA-01", "PRENSA-02"],
    "Transversais": ["LCT-16", "LCT-08", "LCT-2,5"]
}

# Valores base para geração de dados fictícios (em torno das metas ±30%)
BASE_VALUES = {
    "mtbf": {
        "mean": 20.0,
        "std": 6.0,
        "min": 12.0,
        "max": 32.0
    },
    "mttr": {
        "mean": 2.0,
        "std": 0.6,
        "min": 1.0,
        "max": 4.0
    },
    "breakdown_rate": {
        "mean": 3.0,
        "std": 1.0,
        "min": 1.5,
        "max": 6.0
    }
}


def get_kpi_targets(equipment_id: str = None) -> Dict[str, float]:
    """
    Retorna as metas configuradas para os KPIs de um equipamento específico.

    Busca APENAS do MongoDB (AMG_MaintenanceTargets).
    Se não encontrar configuração, retorna valores padrão.

    Args:
        equipment_id: ID do equipamento (ex: "LONGI001"). Se None, retorna meta geral.

    Returns:
        Dict com chaves: mtbf, mttr (em horas), breakdown_rate, alert_range
    """
    try:
        from src.database.connection import get_mongo_connection
        collection = get_mongo_connection("AMG_MaintenanceTargets")
        config = collection.find_one()

        if config and config.get("general"):
            general = config.get("general", {})
            equipment_targets = config.get("equipment_targets", {})

            # Verificar se os valores gerais são válidos
            if general.get("mtbf") is not None and general.get("mttr") is not None and general.get("breakdown_rate") is not None:
                alert_range = general.get("alert_range", 3.0)

                if equipment_id and equipment_id in equipment_targets:
                    # Meta específica do equipamento
                    eq_config = equipment_targets[equipment_id]
                    mttr_value = eq_config.get("mttr", general.get("mttr"))
                    return {
                        "mtbf": eq_config.get("mtbf", general.get("mtbf")),
                        "mttr": mttr_value / 60.0,  # min -> h
                        "breakdown_rate": eq_config.get("breakdown_rate", general.get("breakdown_rate")),
                        "alert_range": alert_range
                    }
                else:
                    # Meta geral
                    return {
                        "mtbf": general.get("mtbf"),
                        "mttr": general.get("mttr") / 60.0,  # min -> h
                        "breakdown_rate": general.get("breakdown_rate"),
                        "alert_range": alert_range
                    }
    except Exception as e:
        print(f"[ERRO] Falha ao buscar metas do MongoDB: {e}")

    # Se não encontrou configuração, retornar valores padrão
    print(f"[AVISO] Nenhuma configuração encontrada para {equipment_id or 'GENERAL'}. Configure as metas em /maintenance/config")
    return {
        "mtbf": 10.0,
        "mttr": 0.5,
        "breakdown_rate": 5.0,
        "alert_range": 3.0
    }


def get_all_equipment_targets() -> Dict[str, Dict[str, float]]:
    """
    Retorna todas as metas de todos os equipamentos.

    Busca APENAS do MongoDB (AMG_MaintenanceTargets).
    Se não encontrar configuração, retorna valores padrão.

    Returns:
        Dict mapeando equipment_id -> {mtbf, mttr (horas), breakdown_rate}
    """
    try:
        from src.database.connection import get_mongo_connection
        collection = get_mongo_connection("AMG_MaintenanceTargets")
        config = collection.find_one()

        if config and config.get("general"):
            general = config.get("general", {})
            equipment_targets = config.get("equipment_targets", {})

            # Verificar se os valores gerais são válidos
            if general.get("mtbf") is not None and general.get("mttr") is not None and general.get("breakdown_rate") is not None:
                all_targets = {}
                alert_range = general.get("alert_range", 3.0)

                # Para cada equipamento no sistema, buscar meta específica ou usar geral
                equipment_list = get_equipment_names()
                for eq_id in equipment_list:
                    if eq_id in equipment_targets:
                        eq_config = equipment_targets[eq_id]
                        mttr_value = eq_config.get("mttr", general.get("mttr"))
                        all_targets[eq_id] = {
                            "mtbf": eq_config.get("mtbf", general.get("mtbf")),
                            "mttr": mttr_value / 60.0,  # min -> h
                            "breakdown_rate": eq_config.get("breakdown_rate", general.get("breakdown_rate")),
                            "alert_range": alert_range
                        }
                    else:
                        # Usar meta geral
                        all_targets[eq_id] = {
                            "mtbf": general.get("mtbf"),
                            "mttr": general.get("mttr") / 60.0,  # min -> h
                            "breakdown_rate": general.get("breakdown_rate"),
                            "alert_range": alert_range
                        }

                # Adicionar meta geral também
                all_targets["GENERAL"] = {
                    "mtbf": general.get("mtbf"),
                    "mttr": general.get("mttr") / 60.0,  # min -> h
                    "breakdown_rate": general.get("breakdown_rate"),
                    "alert_range": alert_range
                }

                return all_targets
    except Exception as e:
        print(f"[ERRO] Falha ao buscar metas do MongoDB: {e}")

    # Se não encontrou configuração, retornar valores padrão para todos equipamentos
    print(f"[AVISO] Nenhuma configuração de metas encontrada. Configure as metas em /maintenance/config")
    all_targets = {}
    equipment_list = get_equipment_names()

    default_targets = {
        "mtbf": 10.0,
        "mttr": 0.5,
        "breakdown_rate": 5.0,
        "alert_range": 3.0
    }

    for eq_id in equipment_list:
        all_targets[eq_id] = default_targets.copy()

    all_targets["GENERAL"] = default_targets.copy()

    return all_targets


def get_equipment_names() -> Dict[str, str]:
    """
    Retorna o dicionário de nomes dos equipamentos.
    Tenta buscar dados reais do ZPP, com fallback para dados demo.

    Returns:
        Dict mapeando código técnico -> nome de exibição
    """
    if ZPP_AVAILABLE:
        try:
            # Tentar buscar equipamentos reais do ZPP
            zpp_names = get_zpp_equipment_names()
            if zpp_names:
                print(f"[INFO] Usando {len(zpp_names)} equipamentos reais do ZPP")
                return zpp_names
        except Exception as e:
            print(f"[AVISO] Erro ao buscar equipamentos ZPP: {e}")
            print("[INFO] Usando equipamentos demo como fallback")

    # Fallback para dados demo
    return EQUIPMENT_NAMES.copy()


def get_equipment_categories() -> Dict[str, List[str]]:
    """
    Retorna a hierarquia de categorias dos equipamentos.
    Tenta buscar dados reais do ZPP, com fallback para dados demo.

    Returns:
        Dict mapeando categoria -> lista de equipment IDs
    """
    if ZPP_AVAILABLE:
        try:
            # Tentar buscar categorias reais do ZPP
            zpp_categories = get_zpp_equipment_categories()
            if zpp_categories:
                print(f"[INFO] Usando {len(zpp_categories)} categorias reais do ZPP")
                return zpp_categories
        except Exception as e:
            print(f"[AVISO] Erro ao buscar categorias ZPP: {e}")
            print("[INFO] Usando categorias demo como fallback")

    # Fallback para dados demo
    return EQUIPMENT_CATEGORIES.copy()


def _generate_kpi_value(kpi_name: str, base_seed: int = None) -> float:
    """
    Gera um valor fictício para um KPI com variação realística.

    Args:
        kpi_name: "mtbf", "mttr" ou "breakdown_rate"
        base_seed: Seed opcional para reproduzibilidade

    Returns:
        Valor gerado dentro dos limites realísticos
    """
    if base_seed is not None:
        random.seed(base_seed)

    base = BASE_VALUES[kpi_name]

    # Gerar valor com distribuição normal
    value = random.gauss(base["mean"], base["std"])

    # Garantir que está dentro dos limites
    value = max(base["min"], min(base["max"], value))

    return round(value, 1)


def generate_monthly_kpi_data(year: int,
                               months: List[int],
                               equipment_ids: List[str]) -> Dict[str, List[Dict]]:
    """
    Gera dados fictícios mensais de KPIs para os equipamentos especificados.

    Args:
        year: Ano dos dados (ex: 2026)
        months: Lista de meses (1-12)
        equipment_ids: Lista de IDs dos equipamentos

    Returns:
        Dict mapeando equipment_id -> lista de dicts mensais
        Estrutura: {
            "LONGI001": [
                {"month": 1, "mtbf": 22.3, "mttr": 1.8, "breakdown_rate": 2.9},
                {"month": 2, "mtbf": 18.5, "mttr": 2.3, "breakdown_rate": 3.5},
                ...
            ],
            ...
        }
    """
    data = {}

    for eq_id in equipment_ids:
        monthly_data = []

        for month in months:
            # Usar combinação de year, month e eq_id como seed para valores consistentes
            # mas diferentes entre equipamentos e meses
            eq_index = list(EQUIPMENT_NAMES.keys()).index(eq_id)
            base_seed = year * 10000 + month * 100 + eq_index

            # Gerar valores para cada KPI
            mtbf = _generate_kpi_value("mtbf", base_seed)
            mttr = _generate_kpi_value("mttr", base_seed + 1)
            breakdown_rate = _generate_kpi_value("breakdown_rate", base_seed + 2)

            monthly_data.append({
                "month": month,
                "mtbf": mtbf,
                "mttr": mttr,
                "breakdown_rate": breakdown_rate
            })

        data[eq_id] = monthly_data

    return data


def calculate_kpi_averages(data: Dict[str, List[Dict]],
                           equipment_filter: List[str],
                           month_filter: List[int],
                           year: int = None,
                           monthly_aggregates: Dict[int, Dict] = None) -> Dict:
    """
    Calcula médias dos KPIs considerando filtros.

    Média geral agora calculada como: (Jan + Fev + ... + Dez) / número_de_meses
    ao invés de média das médias dos equipamentos.

    Args:
        data: Dados gerados por generate_monthly_kpi_data()
        equipment_filter: Lista de equipment IDs a considerar
        month_filter: Lista de meses a considerar
        year: Ano para buscar dados brutos (se None, usa método antigo)
        monthly_aggregates: Valores mensais já calculados (otimização de performance)

    Returns:
        Dict com estrutura:
        {
            "mtbf": média_geral,
            "mttr": média_geral,
            "breakdown_rate": média_geral,
            "by_equipment": {
                "LONGI001": {"mtbf": X, "mttr": Y, "breakdown_rate": Z},
                ...
            }
        }
    """
    # Validar que há dados
    if not data or not equipment_filter or not month_filter:
        return {
            "mtbf": 0.0,
            "mttr": 0.0,
            "breakdown_rate": 0.0,
            "by_equipment": {}
        }

    # Calcular médias por equipamento
    by_equipment = {}

    for eq_id in equipment_filter:
        if eq_id not in data:
            continue

        # Filtrar apenas os meses selecionados
        filtered_months = [
            month_data for month_data in data[eq_id]
            if month_data["month"] in month_filter
        ]

        if not filtered_months:
            continue

        # Calcular média de cada KPI para este equipamento
        mtbf_avg = sum(m["mtbf"] for m in filtered_months) / len(filtered_months)
        mttr_avg = sum(m["mttr"] for m in filtered_months) / len(filtered_months)
        breakdown_avg = sum(m["breakdown_rate"] for m in filtered_months) / len(filtered_months)

        by_equipment[eq_id] = {
            "mtbf": round(mtbf_avg, 1),
            "mttr": round(mttr_avg, 1),
            "breakdown_rate": round(breakdown_avg, 1)
        }

    # Calcular médias gerais usando VALORES MENSAIS
    # Método: (Jan + Fev + ... + Dez) / número_de_meses

    # OTIMIZAÇÃO: Usar dados já calculados se fornecidos
    if monthly_aggregates is not None:
        # Usar valores mensais já calculados (evita re-buscar MongoDB)
        monthly_values = monthly_aggregates
    elif year is not None:
        # Buscar valores mensais do MongoDB
        monthly_values = calculate_general_avg_by_month(data, equipment_filter, month_filter, year=year)
    else:
        monthly_values = None

    # Calcular médias gerais
    if monthly_values:
        mtbf_general = sum(m["mtbf"] for m in monthly_values.values()) / len(monthly_values)
        mttr_general = sum(m["mttr"] for m in monthly_values.values()) / len(monthly_values)
        breakdown_general = sum(m["breakdown_rate"] for m in monthly_values.values()) / len(monthly_values)
    elif by_equipment:
        # Fallback: Média das médias dos equipamentos
        mtbf_general = sum(eq["mtbf"] for eq in by_equipment.values()) / len(by_equipment)
        mttr_general = sum(eq["mttr"] for eq in by_equipment.values()) / len(by_equipment)
        breakdown_general = sum(eq["breakdown_rate"] for eq in by_equipment.values()) / len(by_equipment)
    else:
        mtbf_general = 0.0
        mttr_general = 0.0
        breakdown_general = 0.0

    return {
        "mtbf": round(mtbf_general, 1),
        "mttr": round(mttr_general, 4),  # MTTR em horas
        "breakdown_rate": round(breakdown_general, 2),
        "by_equipment": by_equipment
    }


def check_equipment_meets_targets(mtbf: float, mttr: float,
                                  breakdown_rate: float) -> bool:
    """
    Verifica se um equipamento atende TODAS as metas.

    Args:
        mtbf: Valor de MTBF
        mttr: Valor de MTTR
        breakdown_rate: Valor de Taxa de Avaria

    Returns:
        True se atende todas as metas, False caso contrário
    """
    targets = get_kpi_targets()

    mtbf_ok = mtbf >= targets["mtbf"]
    mttr_ok = mttr <= targets["mttr"]
    breakdown_ok = breakdown_rate <= targets["breakdown_rate"]

    return mtbf_ok and mttr_ok and breakdown_ok


def calculate_general_avg_by_month(data: Dict[str, List[Dict]],
                                   equipment_ids: List[str],
                                   months: List[int],
                                   year: int = None) -> Dict[int, Dict]:
    """
    Calcula KPI geral por mês agregando dados BRUTOS de todos os equipamentos.

    IMPORTANTE: Agora usa agregação de dados brutos (igual aos debug cards)
    ao invés de média aritmética dos KPIs individuais.

    Método:
    1. Busca dados brutos de produção e paradas do MongoDB
    2. Agrega por mês (soma horas, conta falhas)
    3. Calcula KPI da PLANTA (não média dos equipamentos)

    Args:
        data: Dados gerados (usado apenas como fallback se year=None)
        equipment_ids: Lista de IDs dos equipamentos
        months: Lista de meses a considerar
        year: Ano para buscar dados brutos (se None, usa método antigo)

    Returns:
        Dicionário com KPIs por mês:
        {
            1: {"mtbf": X, "mttr": Y, "breakdown_rate": Z},
            2: {...},
            ...
        }
    """
    result = {}

    # Se year não foi passado, usar método antigo (média aritmética) para compatibilidade
    if year is None:
        for month in months:
            mtbf_sum = 0
            mttr_sum = 0
            breakdown_sum = 0
            count = 0

            for eq_id in equipment_ids:
                for month_data in data[eq_id]:
                    if month_data["month"] == month:
                        mtbf_sum += month_data["mtbf"]
                        mttr_sum += month_data["mttr"]
                        breakdown_sum += month_data["breakdown_rate"]
                        count += 1
                        break

            if count > 0:
                result[month] = {
                    "mtbf": round(mtbf_sum / count, 1),
                    "mttr": round(mttr_sum / count, 1),
                    "breakdown_rate": round(breakdown_sum / count, 1)
                }

        return result

    # NOVO MÉTODO: Agregação de dados brutos (igual debug cards)
    try:
        from src.utils.zpp_kpi_calculator import fetch_zpp_production_data, fetch_zpp_breakdown_data

        # Buscar dados brutos do MongoDB
        production_df = fetch_zpp_production_data(year, months)
        breakdown_df = fetch_zpp_breakdown_data(year, months)

        if production_df.empty:
            print("[AVISO] calculate_general_avg_by_month: Sem dados de produção")
            return result

        # Calcular KPIs por mês agregando TODOS os equipamentos
        for month in months:
            # Filtrar dados do mês
            prod_month = production_df[production_df['month'] == month]
            breakdown_month = breakdown_df[breakdown_df['month'] == month]

            # Calcular agregações
            total_active_hours = prod_month['horasact'].sum()

            if breakdown_month.empty:
                num_failures = 0
                total_breakdown_minutes = 0
            else:
                num_failures = len(breakdown_month)
                total_breakdown_minutes = breakdown_month['duracao_min'].sum()

            total_breakdown_hours = total_breakdown_minutes / 60.0

            # Calcular KPIs (mesma lógica dos debug cards)
            if num_failures > 0 and total_active_hours > 0:
                mtbf = (total_active_hours - total_breakdown_hours) / num_failures
                mttr = total_breakdown_hours / num_failures
                breakdown_rate = (total_breakdown_hours / total_active_hours) * 100
            elif total_active_hours > 0:
                # Sem falhas
                mtbf = 999.0
                mttr = 0.0
                breakdown_rate = 0.0
            else:
                # Sem dados
                continue

            result[month] = {
                "mtbf": round(mtbf, 1),
                "mttr": round(mttr, 4),  # MTTR em horas (será convertido para minutos na exibição)
                "breakdown_rate": round(breakdown_rate, 2)
            }

    except Exception as e:
        print(f"[ERRO] calculate_general_avg_by_month: Falha ao agregar dados brutos: {e}")
        import traceback
        traceback.print_exc()

    return result
