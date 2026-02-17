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
    producao = get_mongo_connection("ZPP_Producao")
    paradas = get_mongo_connection("ZPP_Paradas")
    print("    ✓ Conectado\n")

    # Verificar produção
    print("[2] Verificando ZPP_Producao...")
    count_prod = producao.count_documents({})

    print(f"    Total registros: {count_prod:,}")

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
    print("[3] Verificando ZPP_Paradas...")
    count_paradas = paradas.count_documents({})

    print(f"    Total registros: {count_paradas:,}")

    # Verificar códigos de motivo
    motivos = paradas.distinct("causa_do_desvio", {})
    print(f"    Códigos de causa encontrados (primeiros 10): {motivos[:10]}")

    # Verificar se tem os códigos de avaria que estamos procurando
    codigos_avaria = ['201', 'S201', '202', 'S202', '203', 'S203']
    count_avarias = paradas.count_documents({
        "causa_do_desvio": {"$in": codigos_avaria}
    })
    print(f"    Paradas com códigos de avaria {codigos_avaria}: {count_avarias}")

    print()

    # Diagnóstico
    print("[4] DIAGNÓSTICO:")
    if count_prod == 0:
        print("    ✗ PROBLEMA: Não há dados de produção")
    else:
        print(f"    ✓ Há {count_prod:,} registros de produção")

    if count_avarias == 0:
        print("    ⚠ AVISO: Não há paradas com códigos de avaria")
        print("      (Isso pode ser normal se não houver avarias registradas)")
    else:
        print(f"    ✓ Há {count_avarias} paradas (avarias)")

    print("\n" + "="*80 + "\n")

except Exception as e:
    print(f"\n✗ ERRO: {e}\n")
    import traceback
    traceback.print_exc()
