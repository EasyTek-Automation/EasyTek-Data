"""
Script de teste para verificar dados dos sunbursts
"""
import sys
import os

# Adicionar diretório do webapp ao path
webapp_src = os.path.join(os.path.dirname(__file__), 'webapp', 'src')
sys.path.insert(0, webapp_src)

# Mudar para o diretório do webapp para imports relativos funcionarem
os.chdir(webapp_src)

from utils.zpp_kpi_calculator import fetch_zpp_kpi_data
from utils.maintenance_demo_data import (
    calculate_kpi_averages,
    get_zpp_equipment_names,
    get_zpp_equipment_categories
)

print("="*80)
print("TESTE DE DADOS PARA SUNBURSTS")
print("="*80)

year = 2025
months = list(range(1, 13))

print(f"\n[1] Buscando dados ZPP para {year}, meses {months}...")
try:
    data = fetch_zpp_kpi_data(year, months)
    print(f"  ✓ Dados carregados: {len(data)} equipamentos")

    if not data:
        print("  ✗ PROBLEMA: Nenhum dado retornado!")
        exit(1)

    # Mostrar amostra
    eq_sample = list(data.keys())[0]
    print(f"\n  Amostra ({eq_sample}):")
    print(f"    Meses com dados: {len(data[eq_sample])}")
    if data[eq_sample]:
        print(f"    Primeiro mês: {data[eq_sample][0]}")

except Exception as e:
    print(f"  ✗ ERRO: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print(f"\n[2] Buscando nomes e categorias...")
try:
    names = get_zpp_equipment_names()
    categories = get_zpp_equipment_categories()
    print(f"  ✓ Nomes: {len(names)} equipamentos")
    print(f"  ✓ Categorias: {list(categories.keys())}")
except Exception as e:
    print(f"  ✗ ERRO: {e}")
    exit(1)

print(f"\n[3] Calculando médias...")
equipment_ids = list(data.keys())
try:
    averages = calculate_kpi_averages(data, equipment_ids, months, year=year)
    print(f"  ✓ Médias calculadas:")
    print(f"    - Equipamentos: {len(averages.get('by_equipment', {}))}")
    print(f"    - MTBF geral: {averages.get('mtbf')}")
    print(f"    - MTTR geral: {averages.get('mttr')}")
    print(f"    - Breakdown geral: {averages.get('breakdown_rate')}")

    if not averages.get("by_equipment"):
        print("  ✗ PROBLEMA: averages['by_equipment'] está vazio!")
        exit(1)

    # Mostrar amostra de equipamento
    eq_sample = list(averages["by_equipment"].keys())[0]
    print(f"\n  Amostra ({eq_sample}):")
    print(f"    MTBF: {averages['by_equipment'][eq_sample]['mtbf']}")
    print(f"    MTTR: {averages['by_equipment'][eq_sample]['mttr']}")
    print(f"    Breakdown: {averages['by_equipment'][eq_sample]['breakdown_rate']}")

except Exception as e:
    print(f"  ✗ ERRO: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print(f"\n[4] Preparando dados para sunburst...")
try:
    mtbf_by_eq = {eq: averages["by_equipment"][eq]["mtbf"] for eq in equipment_ids}
    mttr_by_eq = {eq: averages["by_equipment"][eq]["mttr"] for eq in equipment_ids}
    breakdown_by_eq = {eq: averages["by_equipment"][eq]["breakdown_rate"] for eq in equipment_ids}

    print(f"  ✓ Dados preparados:")
    print(f"    - MTBF: {list(mtbf_by_eq.items())[:3]}")
    print(f"    - MTTR: {list(mttr_by_eq.items())[:3]}")
    print(f"    - Breakdown: {list(breakdown_by_eq.items())[:3]}")

    # Verificar se há None
    none_mtbf = sum(1 for v in mtbf_by_eq.values() if v is None)
    none_mttr = sum(1 for v in mttr_by_eq.values() if v is None)
    none_breakdown = sum(1 for v in breakdown_by_eq.values() if v is None)

    if none_mtbf > 0 or none_mttr > 0 or none_breakdown > 0:
        print(f"\n  ⚠️  ATENÇÃO: Há valores None!")
        print(f"    - MTBF: {none_mtbf} None")
        print(f"    - MTTR: {none_mttr} None")
        print(f"    - Breakdown: {none_breakdown} None")
    else:
        print(f"\n  ✓ Nenhum valor None encontrado")

except Exception as e:
    print(f"  ✗ ERRO: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("\n" + "="*80)
print("✓ TODOS OS TESTES PASSARAM - Dados OK para criar sunbursts")
print("="*80)
