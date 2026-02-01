"""
Script de Teste - Integração ZPP com Indicadores de Manutenção
Valida conexão MongoDB, busca de dados e cálculos de KPIs
"""

import sys
import os

# Adicionar paths necessários
webapp_src = os.path.join(os.path.dirname(__file__), "webapp", "src")
sys.path.insert(0, webapp_src)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "webapp"))

# Carregar variáveis de ambiente
from dotenv import load_dotenv
load_dotenv()

from src.database.connection import get_mongo_connection
from src.utils.zpp_kpi_calculator import (
    fetch_zpp_equipment_list,
    fetch_zpp_production_data,
    fetch_zpp_breakdown_data,
    fetch_zpp_kpi_data,
    get_zpp_equipment_categories,
    get_zpp_equipment_names
)
from src.utils.maintenance_demo_data import (
    get_equipment_names,
    get_equipment_categories
)

def print_header(title):
    """Imprime cabeçalho formatado"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")

def print_success(message):
    """Imprime mensagem de sucesso"""
    print(f"[OK] {message}")

def print_warning(message):
    """Imprime mensagem de aviso"""
    print(f"[AVISO] {message}")

def print_error(message):
    """Imprime mensagem de erro"""
    print(f"[ERRO] {message}")

def test_mongodb_connection():
    """Teste 1: Verificar conexão com MongoDB"""
    print_header("TESTE 1: Conexão com MongoDB")

    try:
        # Testar conexão com collections
        producao = get_mongo_connection("ZPP_Producao_2025")
        paradas = get_mongo_connection("ZPP_Paradas_2025")

        # Contar documentos
        count_producao = producao.count_documents({})
        count_paradas = paradas.count_documents({})

        print_success(f"Conectado à collection ZPP_Producao_2025")
        print(f"  └─ Total de registros: {count_producao:,}")

        print_success(f"Conectado à collection ZPP_Paradas_2025")
        print(f"  └─ Total de registros: {count_paradas:,}")

        # Verificar dados processados
        count_prod_processed = producao.count_documents({"_processed": True})
        count_paradas_processed = paradas.count_documents({"_processed": True})

        print(f"\n  Registros processados:")
        print(f"    • Produção: {count_prod_processed:,} ({count_prod_processed/count_producao*100:.1f}%)")
        print(f"    • Paradas: {count_paradas_processed:,} ({count_paradas_processed/count_paradas*100:.1f}%)")

        return True

    except Exception as e:
        print_error(f"Falha na conexão: {e}")
        return False

def test_equipment_list():
    """Teste 2: Buscar lista de equipamentos"""
    print_header("TESTE 2: Lista de Equipamentos")

    try:
        equipment_list = fetch_zpp_equipment_list()

        if equipment_list:
            print_success(f"Encontrados {len(equipment_list)} equipamentos:")
            for eq in equipment_list:
                print(f"  • {eq}")
            return True
        else:
            print_warning("Nenhum equipamento encontrado")
            return False

    except Exception as e:
        print_error(f"Falha ao buscar equipamentos: {e}")
        return False

def test_equipment_categories():
    """Teste 3: Categorias de equipamentos"""
    print_header("TESTE 3: Categorias de Equipamentos")

    try:
        categories = get_zpp_equipment_categories()

        if categories:
            print_success(f"Encontradas {len(categories)} categorias:")
            for cat_name, equipments in categories.items():
                print(f"  • {cat_name}: {len(equipments)} equipamentos")
                for eq in equipments:
                    print(f"    └─ {eq}")
            return True
        else:
            print_warning("Nenhuma categoria encontrada")
            return False

    except Exception as e:
        print_error(f"Falha ao buscar categorias: {e}")
        return False

def test_production_data():
    """Teste 4: Buscar dados de produção"""
    print_header("TESTE 4: Dados de Produção")

    try:
        # Testar com Jan-Mar 2025
        df = fetch_zpp_production_data(year=2025, months=[1, 2, 3])

        if not df.empty:
            print_success(f"Dados de produção carregados: {len(df)} registros")
            print(f"\n  Colunas: {list(df.columns)}")
            print(f"  Equipamentos únicos: {df['linea'].nunique()}")
            print(f"  Período: {df['date'].min()} a {df['date'].max()}")
            print(f"  Total horas atividade: {df['horasact'].sum():.2f}h")

            # Mostrar amostra
            print("\n  Amostra de dados:")
            print(df.head(3).to_string(index=False))

            return True
        else:
            print_warning("Nenhum dado de produção encontrado para Jan-Mar 2025")
            return False

    except Exception as e:
        print_error(f"Falha ao buscar dados de produção: {e}")
        return False

def test_breakdown_data():
    """Teste 5: Buscar dados de paradas"""
    print_header("TESTE 5: Dados de Paradas (Avarias)")

    try:
        # Testar com Jan-Mar 2025
        df = fetch_zpp_breakdown_data(year=2025, months=[1, 2, 3])

        if not df.empty:
            print_success(f"Dados de paradas carregados: {len(df)} registros")
            print(f"\n  Colunas: {list(df.columns)}")
            print(f"  Equipamentos únicos: {df['linea'].nunique()}")
            print(f"  Período: {df['date'].min()} a {df['date'].max()}")
            print(f"  Total minutos parada: {df['duracao_min'].sum():.2f} min ({df['duracao_min'].sum()/60:.2f}h)")

            # Distribuição por motivo
            print("\n  Distribuição por motivo:")
            motivos = df['motivo'].value_counts()
            for motivo, count in motivos.items():
                print(f"    • {motivo}: {count} ocorrências")

            # Mostrar amostra
            print("\n  Amostra de dados:")
            print(df.head(3).to_string(index=False))

            return True
        else:
            print_warning("Nenhuma parada encontrada para Jan-Mar 2025")
            print("  (Isso pode ser normal se não houver avarias no período)")
            return True  # Não é erro

    except Exception as e:
        print_error(f"Falha ao buscar dados de paradas: {e}")
        return False

def test_kpi_calculation():
    """Teste 6: Cálculo de KPIs"""
    print_header("TESTE 6: Cálculo de KPIs (M01, M02, M03)")

    try:
        # Calcular KPIs para Jan-Mar 2025
        kpi_data = fetch_zpp_kpi_data(year=2025, months=[1, 2, 3])

        if kpi_data:
            print_success(f"KPIs calculados para {len(kpi_data)} equipamentos")

            # Mostrar detalhes do primeiro equipamento
            first_eq = list(kpi_data.keys())[0]
            print(f"\n  Exemplo detalhado: {first_eq}")
            print(f"  {'Mês':<6} {'MTBF (h)':<12} {'MTTR (h)':<12} {'Taxa Avaria (%)':<18}")
            print("  " + "-"*50)

            for month_data in kpi_data[first_eq]:
                mtbf = month_data['mtbf'] if month_data['mtbf'] is not None else 'N/A'
                mttr = month_data['mttr'] if month_data['mttr'] is not None else 'N/A'
                rate = month_data['breakdown_rate'] if month_data['breakdown_rate'] is not None else 'N/A'

                print(f"  {month_data['month']:<6} {str(mtbf):<12} {str(mttr):<12} {str(rate):<18}")

            # Estatísticas gerais
            print("\n  Estatísticas gerais de todos equipamentos:")
            all_mtbf = [m['mtbf'] for eq_data in kpi_data.values() for m in eq_data if m['mtbf'] is not None]
            all_mttr = [m['mttr'] for eq_data in kpi_data.values() for m in eq_data if m['mttr'] is not None]
            all_rate = [m['breakdown_rate'] for eq_data in kpi_data.values() for m in eq_data if m['breakdown_rate'] is not None]

            if all_mtbf:
                print(f"    • MTBF médio: {sum(all_mtbf)/len(all_mtbf):.2f}h (min: {min(all_mtbf):.2f}h, max: {max(all_mtbf):.2f}h)")
            if all_mttr:
                print(f"    • MTTR médio: {sum(all_mttr)/len(all_mttr):.2f}h (min: {min(all_mttr):.2f}h, max: {max(all_mttr):.2f}h)")
            if all_rate:
                print(f"    • Taxa Avaria média: {sum(all_rate)/len(all_rate):.2f}% (min: {min(all_rate):.2f}%, max: {max(all_rate):.2f}%)")

            return True
        else:
            print_warning("Nenhum KPI calculado (sem dados de produção)")
            return False

    except Exception as e:
        print_error(f"Falha ao calcular KPIs: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_integration_with_demo_data():
    """Teste 7: Integração com maintenance_demo_data"""
    print_header("TESTE 7: Integração com Sistema Existente")

    try:
        # Testar funções que usam ZPP como fonte
        equipment_names = get_equipment_names()
        equipment_categories = get_equipment_categories()

        print_success("Funções de maintenance_demo_data integradas com ZPP")
        print(f"\n  Equipamentos disponíveis: {len(equipment_names)}")
        for eq_id, eq_name in list(equipment_names.items())[:5]:
            print(f"    • {eq_id}: {eq_name}")
        if len(equipment_names) > 5:
            print(f"    ... e mais {len(equipment_names) - 5} equipamentos")

        print(f"\n  Categorias disponíveis: {len(equipment_categories)}")
        for cat_name, equipments in equipment_categories.items():
            print(f"    • {cat_name}: {len(equipments)} equipamentos")

        return True

    except Exception as e:
        print_error(f"Falha na integração: {e}")
        return False

def main():
    """Executa todos os testes"""
    print("\n" + "="*80)
    print("  TESTE DE INTEGRAÇÃO ZPP - INDICADORES DE MANUTENÇÃO")
    print("  Validando conexão, dados e cálculos de KPIs M01, M02, M03")
    print("="*80)

    results = {
        "Conexão MongoDB": test_mongodb_connection(),
        "Lista de Equipamentos": test_equipment_list(),
        "Categorias de Equipamentos": test_equipment_categories(),
        "Dados de Produção": test_production_data(),
        "Dados de Paradas": test_breakdown_data(),
        "Cálculo de KPIs": test_kpi_calculation(),
        "Integração com Sistema": test_integration_with_demo_data()
    }

    # Resumo final
    print_header("RESUMO DOS TESTES")

    passed = sum(results.values())
    total = len(results)

    for test_name, passed_test in results.items():
        status = "[OK]" if passed_test else "[FALHA]"
        print(f"{status} {test_name}")

    print(f"\n  Resultado: {passed}/{total} testes passaram ({passed/total*100:.1f}%)")

    if passed == total:
        print("\n  ✓ TODOS OS TESTES PASSARAM!")
        print("  A integração ZPP está funcionando corretamente.")
        print("\n  Próximos passos:")
        print("    1. Iniciar o aplicativo: python webapp/src/run.py")
        print("    2. Acessar: http://localhost:8050/maintenance/indicators")
        print("    3. Verificar que os dados reais aparecem nos gráficos")
    else:
        print("\n  ⚠ ALGUNS TESTES FALHARAM")
        print("  Verifique os erros acima e corrija antes de usar em produção.")

    print("\n" + "="*80 + "\n")

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
