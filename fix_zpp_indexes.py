"""
Script para corrigir índices desatualizados das collections ZPP
Remove índices antigos e permite que sejam recriados corretamente
"""
import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DB_NAME')

if not MONGO_URI or not DB_NAME:
    print("[ERRO] Variáveis MONGO_URI e/ou DB_NAME não configuradas no .env")
    exit(1)

print("="*80)
print("CORREÇÃO DE ÍNDICES ZPP")
print("="*80)
print(f"\nDatabase: {DB_NAME}")
print(f"Collections: ZPP_Producao_2025, ZPP_Paradas_2025\n")

# Conectar ao MongoDB
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.server_info()
    db = client[DB_NAME]
    print("[OK] Conectado ao MongoDB\n")
except Exception as e:
    print(f"[ERRO] Falha ao conectar: {e}")
    exit(1)

# Collections a processar
collections_to_fix = ['ZPP_Producao_2025', 'ZPP_Paradas_2025']

for coll_name in collections_to_fix:
    print("="*80)
    print(f"COLLECTION: {coll_name}")
    print("="*80)

    collection = db[coll_name]

    # Listar índices existentes
    print("\n[1] Índices atuais:")
    indexes = collection.list_indexes()
    index_names = []
    for idx in indexes:
        index_names.append(idx['name'])
        print(f"  - {idx['name']}: {idx.get('key', {})}")

    # Remover índices (exceto _id_ que é obrigatório)
    print("\n[2] Removendo índices antigos...")
    removed_count = 0
    for idx_name in index_names:
        if idx_name != '_id_':  # Não pode remover índice do _id
            try:
                collection.drop_index(idx_name)
                print(f"  [OK] Removido: {idx_name}")
                removed_count += 1
            except Exception as e:
                print(f"  [AVISO] Não foi possível remover {idx_name}: {e}")

    if removed_count == 0:
        print("  Nenhum índice personalizado para remover")
    else:
        print(f"\n  Total removido: {removed_count} índice(s)")

    print("\n[3] Status final:")
    remaining = list(collection.list_indexes())
    print(f"  Índices restantes: {len(remaining)}")
    for idx in remaining:
        print(f"  - {idx['name']}")

    print()

print("="*80)
print("CONCLUSÃO")
print("="*80)
print("""
Os índices antigos foram removidos com sucesso.

PRÓXIMO PASSO:
Execute novamente o processamento com:
  python process_zpp_quick.py

O script irá criar automaticamente os índices corretos com os
nomes de campos normalizados.
""")
print("="*80)

client.close()
