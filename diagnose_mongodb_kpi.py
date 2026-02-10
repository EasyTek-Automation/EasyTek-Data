"""
Script de diagnóstico para verificar dados ZPP no MongoDB
Identifica problemas de compatibilidade entre collections
"""
import os
from pymongo import MongoClient
from dotenv import load_dotenv
from collections import Counter

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DB_NAME')

print("="*80)
print("DIAGNÓSTICO ZPP - VERIFICAÇÃO DE DADOS")
print("="*80)

# Conectar
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client[DB_NAME]

paradas_coll = db['ZPP_Paradas_2025']
producao_coll = db['ZPP_Producao_2025']

print(f"\n[1] EQUIPAMENTOS DISPONÍVEIS")
print("="*80)

# Buscar equipamentos únicos
paradas_equipamentos = set(paradas_coll.distinct("centro_de_trabalho"))
producao_equipamentos = set(producao_coll.distinct("pto_trab"))

# Remover None e valores vazios
paradas_equipamentos = {eq for eq in paradas_equipamentos if eq}
producao_equipamentos = {eq for eq in producao_equipamentos if eq}

print(f"\nParadas (centro_de_trabalho): {len(paradas_equipamentos)} equipamentos")
for eq in sorted(paradas_equipamentos):
    print(f"  - {eq}")

print(f"\nProdução (pto_trab): {len(producao_equipamentos)} equipamentos")
for eq in sorted(producao_equipamentos):
    print(f"  - {eq}")

print(f"\n[2] ANÁLISE DE DIVERGÊNCIAS")
print("="*80)

# Equipamentos só em Paradas (PROBLEMA!)
only_paradas = paradas_equipamentos - producao_equipamentos
if only_paradas:
    print(f"\n❌ PROBLEMA: {len(only_paradas)} equipamento(s) SÓ EM PARADAS (sem dados de produção):")
    for eq in sorted(only_paradas):
        print(f"  - {eq}")
    print("  → Isso causa MTBF = None (sem horas de atividade)")
else:
    print("\n✓ Nenhum equipamento só em Paradas")

# Equipamentos só em Produção (OK, mas informativo)
only_producao = producao_equipamentos - paradas_equipamentos
if only_producao:
    print(f"\nℹ️  {len(only_producao)} equipamento(s) SÓ EM PRODUÇÃO (sem avarias registradas):")
    for eq in sorted(only_producao):
        print(f"  - {eq}")
    print("  → OK - Significa que não tiveram avarias no período")
else:
    print("\n✓ Nenhum equipamento só em Produção")

# Equipamentos em ambas
common = paradas_equipamentos & producao_equipamentos
print(f"\n✓ {len(common)} equipamento(s) EM AMBAS as collections (OK):")
for eq in sorted(common):
    print(f"  - {eq}")

print(f"\n[3] DADOS DE AVARIAS (Paradas)")
print("="*80)

from datetime import datetime
start_date = datetime(2025, 1, 1)
end_date = datetime(2025, 12, 31, 23, 59, 59)

pipeline = [
    {
        "$match": {
            "_processed": True,
            "causa_do_desvio": {"$in": ["201", "S201", "202", "S202", "203", "S203"]},
            "inicio_execucao": {
                "$gte": start_date,
                "$lte": end_date
            }
        }
    },
    {
        "$group": {
            "_id": "$centro_de_trabalho",
            "total_falhas": {"$sum": 1},
            "total_minutos": {"$sum": "$duration_min"}
        }
    },
    {"$sort": {"_id": 1}}
]

paradas_data = list(paradas_coll.aggregate(pipeline))

print(f"\nTotal de equipamentos com avarias: {len(paradas_data)}")
print(f"\n{'Equipamento':<15} {'Falhas':>10} {'Minutos':>12} {'Horas':>10}")
print("-" * 50)
for item in paradas_data:
    eq = item['_id']
    falhas = item['total_falhas']
    minutos = item.get('total_minutos', 0) or 0
    horas = minutos / 60
    print(f"{eq:<15} {falhas:>10} {minutos:>12.1f} {horas:>10.1f}")

print(f"\n[4] DADOS DE PRODUÇÃO (Horas de Atividade)")
print("="*80)

pipeline = [
    {
        "$match": {
            "_processed": True,
            "fininotif": {
                "$gte": start_date,
                "$lte": end_date
            }
        }
    },
    {
        "$group": {
            "_id": "$pto_trab",
            "total_horas": {"$sum": "$horasact"}
        }
    },
    {"$sort": {"_id": 1}}
]

producao_data = list(producao_coll.aggregate(pipeline))

print(f"\nTotal de equipamentos com produção: {len(producao_data)}")
print(f"\n{'Equipamento':<15} {'Horas Atividade':>20}")
print("-" * 40)
for item in producao_data:
    eq = item['_id']
    horas = item.get('total_horas', 0) or 0
    print(f"{eq:<15} {horas:>20.1f}")

print(f"\n[5] CRUZAMENTO DE DADOS (KPI Viável?)")
print("="*80)

# Criar dicionários para lookup rápido
paradas_dict = {item['_id']: item for item in paradas_data}
producao_dict = {item['_id']: item for item in producao_data}

print(f"\n{'Equipamento':<15} {'Falhas':>8} {'Horas Prod':>12} {'KPI Viável?':>15}")
print("-" * 55)

todos_equipamentos = sorted(paradas_equipamentos | producao_equipamentos)

for eq in todos_equipamentos:
    parada_info = paradas_dict.get(eq, {})
    producao_info = producao_dict.get(eq, {})

    falhas = parada_info.get('total_falhas', 0)
    horas = producao_info.get('total_horas', 0) or 0

    # Verificar se KPI é viável
    if falhas > 0 and horas > 0:
        status = "✓ SIM"
    elif falhas == 0 and horas > 0:
        status = "⚠️  Sem avarias"
    elif falhas > 0 and horas == 0:
        status = "❌ Sem produção"
    else:
        status = "❌ Sem dados"

    print(f"{eq:<15} {falhas:>8} {horas:>12.1f} {status:>15}")

print(f"\n[6] RESUMO")
print("="*80)

total_equipamentos = len(todos_equipamentos)
com_kpi = sum(1 for eq in todos_equipamentos
              if paradas_dict.get(eq, {}).get('total_falhas', 0) > 0
              and (producao_dict.get(eq, {}).get('total_horas', 0) or 0) > 0)
sem_avarias = sum(1 for eq in todos_equipamentos
                  if paradas_dict.get(eq, {}).get('total_falhas', 0) == 0
                  and (producao_dict.get(eq, {}).get('total_horas', 0) or 0) > 0)
sem_producao = sum(1 for eq in todos_equipamentos
                   if paradas_dict.get(eq, {}).get('total_falhas', 0) > 0
                   and (producao_dict.get(eq, {}).get('total_horas', 0) or 0) == 0)

print(f"\nTotal de equipamentos: {total_equipamentos}")
print(f"  ✓ Com KPI viável (falhas + produção): {com_kpi}")
print(f"  ⚠️  Sem avarias (só produção): {sem_avarias}")
print(f"  ❌ Sem produção (só avarias): {sem_producao}")
print(f"  ❌ Sem dados: {total_equipamentos - com_kpi - sem_avarias - sem_producao}")

if sem_producao > 0:
    print(f"\n⚠️  ATENÇÃO: {sem_producao} equipamento(s) têm avarias mas SEM dados de produção!")
    print("   Isso impede o cálculo do MTBF e causa erro 'None' nos gráficos individuais.")

print("\n" + "="*80)

client.close()
