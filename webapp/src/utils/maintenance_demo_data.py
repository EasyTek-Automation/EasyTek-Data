"""
Maintenance Demo Data Generator
Gera dados fictícios de KPIs de manutenção para demonstração
"""

import random
from typing import Dict, List

# ============================================
# CONFIGURAÇÃO DE METAS (FÁCIL PERSONALIZAÇÃO)
# ============================================
KPI_TARGETS = {
    "mtbf": 20.0,           # horas - Mean Time Between Failures - EDITÁVEL AQUI
    "mttr": 2.0,            # horas - Mean Time To Repair - EDITÁVEL AQUI
    "breakdown_rate": 3.0   # % - Taxa de Avaria - EDITÁVEL AQUI
}

# Dicionário de nomes de equipamentos (expansível e personalizável)
EQUIPMENT_NAMES = {
    "LONGI001": "LONGI001",  # Pode alterar lado direito depois para "Longitudinal 1"
    "LONGI002": "LONGI002",
    "PRENS001": "PRENS001",
    "PRENS002": "PRENS002",
    "TRANS001": "TRANS001",
    "TRANS002": "TRANS002",
    "TRANS003": "TRANS003"
}

# Categorias para hierarquia Sunburst
EQUIPMENT_CATEGORIES = {
    "Longitudinais": ["LONGI001", "LONGI002"],
    "Prensas": ["PRENS001", "PRENS002"],
    "Transversais": ["TRANS001", "TRANS002", "TRANS003"]
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


def get_kpi_targets() -> Dict[str, float]:
    """
    Retorna as metas configuradas para os KPIs.

    Returns:
        Dict com chaves: mtbf, mttr, breakdown_rate
    """
    return KPI_TARGETS.copy()


def get_equipment_names() -> Dict[str, str]:
    """
    Retorna o dicionário de nomes dos equipamentos.

    Returns:
        Dict mapeando código técnico -> nome de exibição
    """
    return EQUIPMENT_NAMES.copy()


def get_equipment_categories() -> Dict[str, List[str]]:
    """
    Retorna a hierarquia de categorias dos equipamentos.

    Returns:
        Dict mapeando categoria -> lista de equipment IDs
    """
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
                           month_filter: List[int]) -> Dict:
    """
    Calcula médias dos KPIs considerando filtros.

    Args:
        data: Dados gerados por generate_monthly_kpi_data()
        equipment_filter: Lista de equipment IDs a considerar
        month_filter: Lista de meses a considerar

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

    # Calcular médias gerais (média das médias dos equipamentos)
    if by_equipment:
        mtbf_general = sum(eq["mtbf"] for eq in by_equipment.values()) / len(by_equipment)
        mttr_general = sum(eq["mttr"] for eq in by_equipment.values()) / len(by_equipment)
        breakdown_general = sum(eq["breakdown_rate"] for eq in by_equipment.values()) / len(by_equipment)
    else:
        mtbf_general = 0.0
        mttr_general = 0.0
        breakdown_general = 0.0

    return {
        "mtbf": round(mtbf_general, 1),
        "mttr": round(mttr_general, 1),
        "breakdown_rate": round(breakdown_general, 1),
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
