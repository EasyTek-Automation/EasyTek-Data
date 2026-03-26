"""
Script de migração única: atualiza o campo 'data' dos relatórios (logs) para
herdar a data da atividade-pai, em vez de manter a data de criação do log.

Contexto:
    Logs são criados com 'data': datetime.now(), mas o filtro por data no workflow
    usa a data da atividade-pai. Após esta migração, log.data == atividade_pai.data,
    garantindo que o filtro funcione consistentemente em todos os contextos
    (tabela, card KPI, CB5 com JSON roundtrip via dcc.Store).

Comportamento:
    - Processa apenas documentos com record_type='log' e subtarefa_id preenchido
    - Para cada log, busca a atividade-pai pelo subtarefa_id
    - Atualiza log.data com a data da atividade-pai
    - Logs sem pai encontrado ou sem campo 'data' no pai são ignorados (aviso)
    - Idempotente: rodar mais de uma vez não causa dano

Uso:
    # Na VPS, dentro do container:
    docker exec -it easytek-infra-webapp-1 python webapp/scripts/migrate_log_dates.py

    # Localmente (requer .env com MONGO_URI):
    cd AMG_Data/webapp
    python scripts/migrate_log_dates.py
"""

import sys
import os
from bson import ObjectId

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
except ImportError:
    pass

from database.connection import get_mongo_connection

COLLECTION = 'MaintenanceHistory_workflow'


def migrar():
    print(f"Conectando à collection '{COLLECTION}'...")
    collection = get_mongo_connection(COLLECTION)

    logs = list(collection.find({
        'record_type': 'log',
        'subtarefa_id': {'$exists': True, '$ne': None, '$ne': ''},
    }))
    total = len(logs)

    if total == 0:
        print("Nenhum log encontrado para migrar.")
        return

    print(f"Encontrados {total} log(s) para processar.")

    atualizados = 0
    sem_pai = 0
    sem_data_pai = 0

    for log in logs:
        subtarefa_id = log.get('subtarefa_id')
        try:
            pai = collection.find_one({'_id': ObjectId(subtarefa_id)})
        except Exception:
            pai = collection.find_one({'hist_id': subtarefa_id})

        if not pai:
            print(f"  [AVISO] Log {log['_id']}: atividade-pai '{subtarefa_id}' não encontrada — ignorado")
            sem_pai += 1
            continue

        data_pai = pai.get('data')
        if not data_pai:
            print(f"  [AVISO] Log {log['_id']}: atividade-pai sem campo 'data' — ignorado")
            sem_data_pai += 1
            continue

        # Strip timezone (PyMongo pode retornar UTC-aware em versões mais novas)
        if hasattr(data_pai, 'tzinfo') and data_pai.tzinfo is not None:
            data_pai = data_pai.replace(tzinfo=None)

        # Datas retroativas são salvas como meia-noite UTC (00:00Z).
        # Em BRT (UTC-3) isso exibe como 21:00 do dia anterior.
        # Shift para meio-dia UTC garante exibição no dia correto em qualquer fuso do Brasil.
        if data_pai.hour == 0 and data_pai.minute == 0 and data_pai.second == 0:
            data_pai = data_pai.replace(hour=12)

        collection.update_one(
            {'_id': log['_id']},
            {'$set': {'data': data_pai}}
        )
        atualizados += 1

    print(f"\nMigração concluída:")
    print(f"  → {atualizados} log(s) atualizados com a data da atividade-pai")
    if sem_pai:
        print(f"  → {sem_pai} log(s) ignorados: atividade-pai não encontrada")
    if sem_data_pai:
        print(f"  → {sem_data_pai} log(s) ignorados: atividade-pai sem campo 'data'")
    print(f"  → Total processado: {total}")


if __name__ == '__main__':
    migrar()
