"""
Script de migração única: adiciona record_type e subtarefa_id aos documentos
existentes em MaintenanceHistory_workflow.

Regras:
  tipo_evento == 'criacao'  →  record_type = 'criacao',   subtarefa_id = None
  tipo_evento != 'criacao'  →  record_type = 'subtarefa', subtarefa_id = None

Documentos que já possuem record_type são ignorados (idempotente).

Uso:
    cd AMG_Data/webapp
    python scripts/migrate_workflow_record_types.py
"""

import sys
import os

# Ajustar path para importar módulos do webapp
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
except ImportError:
    pass

from database.connection import get_mongo_connection

COLLECTION = "MaintenanceHistory_workflow"


def migrar():
    print(f"Conectando à collection '{COLLECTION}'...")
    collection = get_mongo_connection(COLLECTION)

    # Buscar documentos sem record_type
    sem_campo = list(collection.find({"record_type": {"$exists": False}}))
    total = len(sem_campo)

    if total == 0:
        print("Nenhum documento precisa de migração. Tudo já está atualizado.")
        return

    print(f"Encontrados {total} documento(s) sem record_type.")

    criacao_count = 0
    subtarefa_count = 0

    for doc in sem_campo:
        tipo_evento = doc.get('tipo_evento', '')
        if tipo_evento == 'criacao':
            record_type = 'criacao'
            criacao_count += 1
        else:
            record_type = 'subtarefa'
            subtarefa_count += 1

        collection.update_one(
            {'_id': doc['_id']},
            {'$set': {
                'record_type': record_type,
                'subtarefa_id': None
            }}
        )

    print(f"\nMigração concluída:")
    print(f"  → {criacao_count} documento(s) marcados como 'criacao'")
    print(f"  → {subtarefa_count} documento(s) marcados como 'subtarefa'")
    print(f"  → Total: {total} documento(s) atualizados")


if __name__ == '__main__':
    migrar()
