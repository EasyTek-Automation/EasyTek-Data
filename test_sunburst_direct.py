"""
Script de teste direto para verificar dados dos sunbursts
Evita problemas de imports complexos
"""
import os
import sys
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime

# Forcar UTF-8 no Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DB_NAME')

print("="*80)
print("TESTE DIRETO DE DADOS PARA SUNBURSTS")
print("="*80)

# Conectar ao MongoDB
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client[DB_NAME]

paradas_coll = db['ZPP_Paradas_2025']
producao_coll = db['ZPP_Producao_2025']

year = 2025
months = list(range(1, 13))

print(f"\n[1] Buscando equipamentos únicos...")
paradas_equipamentos = set(paradas_coll.distinct("centro_de_trabalho"))
producao_equipamentos = set(producao_coll.distinct("pto_trab"))

# Remover None
paradas_equipamentos = {eq for eq in paradas_equipamentos if eq}
producao_equipamentos = {eq for eq in producao_equipamentos if eq}

print(f"  ✓ Paradas: {len(paradas_equipamentos)} equipamentos")
print(f"  ✓ Produção: {len(producao_equipamentos)} equipamentos")

all_equipment = sorted(paradas_equipamentos | producao_equipamentos)
print(f"\n  Total de equipamentos: {len(all_equipment)}")
for eq in all_equipment:
    print(f"    - {eq}")

print(f"\n[2] Calculando KPIs por equipamento (simplificado)...")

start_date = datetime(year, 1, 1)
end_date = datetime(year, 12, 31, 23, 59, 59)

# Para cada equipamento, calcular MTBF, MTTR, Breakdown
results = {}

for eq_id in all_equipment:
    print(f"\n  Processando {eq_id}...")

    # Buscar dados de paradas
    pipeline_paradas = [
        {
            "$match": {
                "_processed": True,
                "centro_de_trabalho": eq_id,
                "causa_do_desvio": {"$in": ["201", "S201", "202", "S202", "203", "S203"]},
                "inicio_execucao": {"$gte": start_date, "$lte": end_date}
            }
        },
        {
            "$group": {
                "_id": None,
                "total_falhas": {"$sum": 1},
                "total_minutos": {"$sum": "$duration_min"}
            }
        }
    ]

    paradas_result = list(paradas_coll.aggregate(pipeline_paradas))

    # Buscar dados de produção
    pipeline_producao = [
        {
            "$match": {
                "_processed": True,
                "pto_trab": eq_id,
                "fininotif": {"$gte": start_date, "$lte": end_date}
            }
        },
        {
            "$group": {
                "_id": None,
                "total_horas": {"$sum": "$horasact"}
            }
        }
    ]

    producao_result = list(producao_coll.aggregate(pipeline_producao))

    # Calcular KPIs
    num_falhas = paradas_result[0]["total_falhas"] if paradas_result else 0
    minutos_parada = paradas_result[0]["total_minutos"] if paradas_result else 0
    horas_parada = minutos_parada / 60
    horas_atividade = producao_result[0]["total_horas"] if producao_result else 0

    # MTBF = (Horas de atividade - Horas de parada) / Número de falhas
    if num_falhas > 0 and horas_atividade > 0:
        mtbf = (horas_atividade - horas_parada) / num_falhas
    else:
        mtbf = None

    # MTTR = Total de horas de parada / Número de falhas
    if num_falhas > 0:
        mttr = horas_parada / num_falhas
    else:
        mttr = None

    # Taxa de Avaria = (Horas de parada / Horas de atividade) * 100
    if horas_atividade > 0:
        breakdown_rate = (horas_parada / horas_atividade) * 100
    else:
        breakdown_rate = None

    results[eq_id] = {
        "num_falhas": num_falhas,
        "horas_parada": horas_parada,
        "horas_atividade": horas_atividade,
        "mtbf": mtbf,
        "mttr": mttr,
        "breakdown_rate": breakdown_rate
    }

    print(f"    Falhas: {num_falhas}")
    print(f"    Horas parada: {horas_parada:.1f}")
    print(f"    Horas atividade: {horas_atividade:.1f}")
    mtbf_str = f"{mtbf:.1f}" if mtbf is not None else "N/A"
    mttr_str = f"{mttr:.1f}" if mttr is not None else "N/A"
    breakdown_str = f"{breakdown_rate:.2f}" if breakdown_rate is not None else "N/A"
    print(f"    MTBF: {mtbf_str}")
    print(f"    MTTR: {mttr_str}")
    print(f"    Breakdown: {breakdown_str}%")

print(f"\n[3] Preparando dados para sunburst...")

# Verificar quantos equipamentos têm dados válidos
valid_mtbf = sum(1 for v in results.values() if v["mtbf"] is not None)
valid_mttr = sum(1 for v in results.values() if v["mttr"] is not None)
valid_breakdown = sum(1 for v in results.values() if v["breakdown_rate"] is not None)

print(f"  Equipamentos com MTBF válido: {valid_mtbf}/{len(all_equipment)}")
print(f"  Equipamentos com MTTR válido: {valid_mttr}/{len(all_equipment)}")
print(f"  Equipamentos com Breakdown válido: {valid_breakdown}/{len(all_equipment)}")

# Categorizar equipamentos
categories = {
    "Longitudinais": [],
    "Prensas": [],
    "Transversais": []
}

for eq_id in all_equipment:
    if eq_id.startswith("LONGI"):
        categories["Longitudinais"].append(eq_id)
    elif eq_id.startswith("PRENS"):
        categories["Prensas"].append(eq_id)
    elif eq_id.startswith("TRANS"):
        categories["Transversais"].append(eq_id)

print(f"\n[4] Categorização de equipamentos:")
for cat, eqs in categories.items():
    print(f"  {cat}: {len(eqs)} equipamentos")
    for eq in eqs:
        print(f"    - {eq}")

print(f"\n[5] Verificação de dados para sunburst MTBF:")
for cat, eqs in categories.items():
    cat_values = [results[eq]["mtbf"] for eq in eqs if results[eq]["mtbf"] is not None]
    if cat_values:
        cat_avg = sum(cat_values) / len(cat_values)
        print(f"  {cat}: {len(cat_values)}/{len(eqs)} equipamentos com dados, média = {cat_avg:.1f}")
    else:
        print(f"  {cat}: 0/{len(eqs)} equipamentos com dados - PROBLEMA!")

print(f"\n[6] Verificação de dados para sunburst MTTR:")
for cat, eqs in categories.items():
    cat_values = [results[eq]["mttr"] for eq in eqs if results[eq]["mttr"] is not None]
    if cat_values:
        cat_avg = sum(cat_values) / len(cat_values)
        print(f"  {cat}: {len(cat_values)}/{len(eqs)} equipamentos com dados, média = {cat_avg:.1f}")
    else:
        print(f"  {cat}: 0/{len(eqs)} equipamentos com dados - PROBLEMA!")

print(f"\n[7] Verificação de dados para sunburst Breakdown:")
for cat, eqs in categories.items():
    cat_values = [results[eq]["breakdown_rate"] for eq in eqs if results[eq]["breakdown_rate"] is not None]
    if cat_values:
        cat_avg = sum(cat_values) / len(cat_values)
        print(f"  {cat}: {len(cat_values)}/{len(eqs)} equipamentos com dados, média = {cat_avg:.2f}%")
    else:
        print(f"  {cat}: 0/{len(eqs)} equipamentos com dados - PROBLEMA!")

print("\n" + "="*80)
print("✓ TESTE CONCLUÍDO")
print("="*80)

client.close()
