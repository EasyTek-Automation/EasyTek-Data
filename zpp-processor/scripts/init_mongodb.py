"""
Script de inicialização do MongoDB para ZPP Processor
Cria collections, índices e configuração inicial
"""
import sys
from pathlib import Path

# Adicionar diretório pai ao path para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime
import logging
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_processing_logs_indexes(db):
    """
    Cria índices para zpp_processing_logs
    """
    collection = db['zpp_processing_logs']

    logger.info("Criando índices para 'zpp_processing_logs'...")

    indexes = [
        # Índice único por job_id
        {
            'keys': [('job_id', ASCENDING)],
            'name': 'idx_job_id_unique',
            'options': {'unique': True}
        },
        # Índice por data de início (ordenação)
        {
            'keys': [('started_at', DESCENDING)],
            'name': 'idx_started_at_desc',
            'options': {}
        },
        # Índice composto: status + data (para filtros)
        {
            'keys': [('status', ASCENDING), ('started_at', DESCENDING)],
            'name': 'idx_status_started',
            'options': {}
        },
        # Índice por tipo de trigger
        {
            'keys': [('trigger_type', ASCENDING), ('started_at', DESCENDING)],
            'name': 'idx_trigger_started',
            'options': {}
        },
        # Índice por usuário que iniciou
        {
            'keys': [('triggered_by', ASCENDING), ('started_at', DESCENDING)],
            'name': 'idx_triggered_by_started',
            'options': {'sparse': True}  # sparse pois pode ser null
        }
    ]

    created_count = 0
    for index_def in indexes:
        try:
            collection.create_index(
                index_def['keys'],
                name=index_def['name'],
                **index_def['options']
            )
            logger.info(f"  ✓ Índice criado: {index_def['name']}")
            created_count += 1
        except Exception as e:
            if 'already exists' in str(e):
                logger.info(f"  - Índice já existe: {index_def['name']}")
            else:
                logger.error(f"  ✗ Erro ao criar índice {index_def['name']}: {e}")

    logger.info(f"  Total: {created_count}/{len(indexes)} índices criados\n")
    return created_count


def create_default_config(db):
    """
    Cria documento de configuração padrão se não existir
    """
    collection = db['zpp_processor_config']

    logger.info("Verificando configuração padrão...")

    existing = collection.find_one({'_id': 'global'})

    if existing:
        logger.info("  - Configuração já existe")
        logger.info(f"    auto_process: {existing.get('auto_process')}")
        logger.info(f"    interval_minutes: {existing.get('interval_minutes')}")
        logger.info(f"    última atualização: {existing.get('last_updated')}\n")
        return False

    # Criar configuração padrão
    default_config = {
        '_id': 'global',
        'auto_process': True,
        'interval_minutes': 60,
        'archive_enabled': True,
        'last_updated': datetime.now(),
        'updated_by': 'system',
        'created_at': datetime.now()
    }

    try:
        collection.insert_one(default_config)
        logger.info("  ✓ Configuração padrão criada")
        logger.info(f"    auto_process: {default_config['auto_process']}")
        logger.info(f"    interval_minutes: {default_config['interval_minutes']}\n")
        return True
    except Exception as e:
        logger.error(f"  ✗ Erro ao criar configuração: {e}\n")
        return False


def verify_collections(db):
    """
    Verifica se as collections foram criadas corretamente
    """
    logger.info("Verificando collections...")

    collections = db.list_collection_names()

    required = ['zpp_processing_logs', 'zpp_processor_config']

    all_exist = True
    for col in required:
        exists = col in collections
        status = "✓" if exists else "✗"
        logger.info(f"  {status} {col}")
        if not exists:
            all_exist = False

    print()
    return all_exist


def show_indexes(db):
    """
    Mostra todos os índices criados
    """
    logger.info("Índices criados para zpp_processing_logs:")

    collection = db['zpp_processing_logs']
    indexes = collection.list_indexes()

    for idx in indexes:
        name = idx.get('name', 'unnamed')
        keys = idx.get('key', {})
        unique = idx.get('unique', False)
        sparse = idx.get('sparse', False)

        key_str = ', '.join([f"{k}: {v}" for k, v in keys.items()])
        flags = []
        if unique:
            flags.append('UNIQUE')
        if sparse:
            flags.append('SPARSE')

        flag_str = f" [{', '.join(flags)}]" if flags else ""
        logger.info(f"  - {name}: {{{key_str}}}{flag_str}")

    print()


def insert_sample_log(db):
    """
    Insere um log de exemplo para demonstração (opcional)
    """
    collection = db['zpp_processing_logs']

    # Verificar se já existe log de exemplo
    existing = collection.find_one({'job_id': 'sample-job-123'})
    if existing:
        logger.info("Log de exemplo já existe (pulando inserção)\n")
        return

    logger.info("Inserindo log de exemplo...")

    sample_log = {
        'job_id': 'sample-job-123',
        'status': 'success',
        'started_at': datetime.now(),
        'completed_at': datetime.now(),
        'duration_seconds': 135.5,
        'trigger_type': 'manual',
        'triggered_by': 'admin@example.com',
        'files_processed': [
            {
                'filename': 'zppprd_202601.xlsx',
                'type': 'zppprd',
                'collection_name': 'ZPP_Producao_2025',
                'uploaded_rows': 15000,
                'status': 'success'
            },
            {
                'filename': 'paradas_202601.xlsx',
                'type': 'zppparadas',
                'collection_name': 'ZPP_Paradas_2025',
                'uploaded_rows': 8300,
                'status': 'success'
            }
        ],
        'summary': {
            'total_files': 2,
            'total_uploaded_records': 23300
        }
    }

    try:
        collection.insert_one(sample_log)
        logger.info("  ✓ Log de exemplo inserido\n")
    except Exception as e:
        logger.error(f"  ✗ Erro ao inserir log de exemplo: {e}\n")


def main():
    """
    Função principal
    """
    print("=" * 80)
    print("ZPP PROCESSOR - INICIALIZAÇÃO DO MONGODB")
    print("=" * 80)
    print()

    # Obter configurações
    MONGO_URI = os.getenv('MONGO_URI')
    DB_NAME = os.getenv('DB_NAME')

    if not MONGO_URI or not DB_NAME:
        logger.error("ERRO: Variáveis MONGO_URI e DB_NAME não configuradas")
        logger.error("Configure no arquivo .env antes de executar\n")
        return 1

    logger.info(f"MongoDB URI: {MONGO_URI[:50]}...")
    logger.info(f"Database: {DB_NAME}\n")

    # Conectar ao MongoDB
    try:
        logger.info("Conectando ao MongoDB...")
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.server_info()  # Testa conexão
        db = client[DB_NAME]
        logger.info("  ✓ Conexão estabelecida\n")
    except Exception as e:
        logger.error(f"  ✗ Erro ao conectar: {e}\n")
        return 1

    try:
        # 1. Criar índices para logs
        create_processing_logs_indexes(db)

        # 2. Criar configuração padrão
        create_default_config(db)

        # 3. Verificar collections
        verify_collections(db)

        # 4. Mostrar índices criados
        show_indexes(db)

        # 5. Inserir log de exemplo (opcional)
        # Descomente para inserir log de demonstração
        # insert_sample_log(db)

        print("=" * 80)
        print("✓ INICIALIZAÇÃO CONCLUÍDA COM SUCESSO")
        print("=" * 80)
        print()
        print("Próximos passos:")
        print("  1. Verificar configuração: db.zpp_processor_config.findOne({_id: 'global'})")
        print("  2. Iniciar serviço: docker-compose up -d zpp-processor")
        print("  3. Verificar health: curl http://localhost:5002/api/health")
        print()

        return 0

    except Exception as e:
        logger.error(f"\n✗ Erro durante inicialização: {e}\n")
        return 1

    finally:
        client.close()


if __name__ == '__main__':
    exit(main())
