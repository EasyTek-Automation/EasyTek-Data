"""
Script rápido para verificar dados MongoDB ZPP
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from src.database.connection import get_mongo_connection

print("\n" + "="*80)
print("VERIFICAÇÃO RÁPIDA - MongoDB ZPP")
print("="*80 + "\n")

try:
    # Conectar
    print("[1] Conectando ao MongoDB...")
    producao = get_mongo_connection("ZPP_Producao_2025")
    paradas = get_mongo_connection("ZPP_Paradas_2025")
    print("    ✓ Conectado\n")

    # Verificar produção
    print("[2] Verificando ZPP_Producao_2025...")
    count_prod = producao.count_documents({})
    count_prod_2025 = producao.count_documents({"_year": 2025})

    print(f"    Total registros: {count_prod:,}")
    print(f"    Registros 2025: {count_prod_2025:,}")

    # Verificar campos
    if count_prod > 0:
        sample = producao.find_one({})
        print(f"    Campos disponíveis: {list(sample.keys())}")

        # Verificar qual campo tem a linha
        if 'linea' in sample:
            print(f"    ✓ Campo 'linea' encontrado: {sample.get('linea')}")
        elif 'pto_trab' in sample:
            print(f"    ⚠ Campo 'linea' NÃO encontrado, mas 'pto_trab' existe: {sample.get('pto_trab')}")

    print()

    # Verificar paradas
    print("[3] Verificando ZPP_Paradas_2025...")
    count_paradas = paradas.count_documents({})
    count_paradas_2025 = paradas.count_documents({"_year": 2025})

    print(f"    Total registros: {count_paradas:,}")
    print(f"    Registros 2025: {count_paradas_2025:,}")

    # Verificar códigos de motivo
    motivos = paradas.distinct("motivo", {"_year": 2025})
    print(f"    Códigos de motivo encontrados: {motivos}")

    # Verificar se tem os códigos de avaria que estamos procurando
    codigos_avaria = ['201', 'S201', '202', 'S202', '203', 'S203']
    count_avarias = paradas.count_documents({
        "_year": 2025,
        "motivo": {"$in": codigos_avaria}
    })
    print(f"    Paradas com códigos de avaria {codigos_avaria}: {count_avarias}")

    print()

    # Diagnóstico
    print("[4] DIAGNÓSTICO:")
    if count_prod_2025 == 0:
        print("    ✗ PROBLEMA: Não há dados de produção para 2025")
    else:
        print(f"    ✓ Há {count_prod_2025:,} registros de produção em 2025")

    if count_avarias == 0:
        print("    ⚠ AVISO: Não há paradas com códigos de avaria em 2025")
        print("      (Isso pode ser normal se não houver avarias registradas)")
    else:
        print(f"    ✓ Há {count_avarias} paradas (avarias) em 2025")

    print("\n" + "="*80 + "\n")

except Exception as e:
    print(f"\n✗ ERRO: {e}\n")
    import traceback
    traceback.print_exc()
