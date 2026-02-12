"""
Script de validação do MongoDB para ZPP Processor
Verifica se collections, índices e configurações estão corretos
"""
import sys
from pathlib import Path

# Adicionar diretório pai ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import MongoClient
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


def validate_connection(client, db_name):
    """Valida conexão com MongoDB"""
    logger.info("1. Validando conexão com MongoDB...")
    try:
        client.server_info()
        db = client[db_name]
        logger.info(f"  ✓ Conectado ao database: {db_name}\n")
        return True, db
    except Exception as e:
        logger.error(f"  ✗ Erro de conexão: {e}\n")
        return False, None


def validate_collections(db):
    """Valida existência das collections"""
    logger.info("2. Validando collections...")

    collections = db.list_collection_names()
    required = {
        'zpp_processing_logs': 'Histórico de processamentos',
        'zpp_processor_config': 'Configurações do serviço'
    }

    all_ok = True
    for col_name, description in required.items():
        exists = col_name in collections
        status = "✓" if exists else "✗"
        logger.info(f"  {status} {col_name} - {description}")

        if exists:
            count = db[col_name].count_documents({})
            logger.info(f"      Documentos: {count}")
        else:
            all_ok = False

    print()
    return all_ok


def validate_logs_indexes(db):
    """Valida índices da collection de logs"""
    logger.info("3. Validando índices de zpp_processing_logs...")

    collection = db['zpp_processing_logs']
    indexes = list(collection.list_indexes())

    expected_indexes = {
        'idx_job_id_unique': {'unique': True},
        'idx_started_at_desc': {},
        'idx_status_started': {},
        'idx_trigger_started': {},
        'idx_triggered_by_started': {'sparse': True}
    }

    found_indexes = {idx['name']: idx for idx in indexes if idx['name'] != '_id_'}

    all_ok = True
    for idx_name, expected_props in expected_indexes.items():
        if idx_name in found_indexes:
            idx = found_indexes[idx_name]

            # Verificar propriedades
            checks = []
            if expected_props.get('unique'):
                checks.append(f"UNIQUE: {idx.get('unique', False)}")
            if expected_props.get('sparse'):
                checks.append(f"SPARSE: {idx.get('sparse', False)}")

            check_str = f" ({', '.join(checks)})" if checks else ""
            logger.info(f"  ✓ {idx_name}{check_str}")
        else:
            logger.error(f"  ✗ {idx_name} - NÃO ENCONTRADO")
            all_ok = False

    # Índices extras (não esperados)
    extra = set(found_indexes.keys()) - set(expected_indexes.keys())
    if extra:
        logger.info(f"  ℹ Índices adicionais: {', '.join(extra)}")

    print()
    return all_ok


def validate_config(db):
    """Valida configuração padrão"""
    logger.info("4. Validando configuração...")

    collection = db['zpp_processor_config']
    config = collection.find_one({'_id': 'global'})

    if not config:
        logger.error("  ✗ Configuração padrão não encontrada\n")
        return False

    # Validar campos obrigatórios
    required_fields = {
        'auto_process': bool,
        'interval_minutes': int,
        'archive_enabled': bool,
        'last_updated': datetime,
        'updated_by': str
    }

    all_ok = True
    for field, expected_type in required_fields.items():
        value = config.get(field)

        if value is None:
            logger.error(f"  ✗ Campo '{field}' não encontrado")
            all_ok = False
        elif not isinstance(value, expected_type):
            logger.warning(f"  ⚠ Campo '{field}': tipo {type(value).__name__} (esperado: {expected_type.__name__})")
        else:
            logger.info(f"  ✓ {field}: {value}")

    print()
    return all_ok


def validate_sample_data(db):
    """Valida estrutura de um documento de log (se existir)"""
    logger.info("5. Validando estrutura de logs...")

    collection = db['zpp_processing_logs']
    sample = collection.find_one()

    if not sample:
        logger.info("  ℹ Nenhum log encontrado (esperado em instalação nova)\n")
        return True

    # Validar estrutura
    required_fields = [
        'job_id', 'status', 'started_at', 'trigger_type',
        'files_processed', 'summary'
    ]

    all_ok = True
    for field in required_fields:
        if field in sample:
            logger.info(f"  ✓ {field}: {type(sample[field]).__name__}")
        else:
            logger.error(f"  ✗ {field}: AUSENTE")
            all_ok = False

    # Validar summary
    if 'summary' in sample:
        summary_fields = ['total_files', 'total_uploaded_records']
        for field in summary_fields:
            if field in sample['summary']:
                logger.info(f"    ✓ summary.{field}: {sample['summary'][field]}")
            else:
                logger.warning(f"    ⚠ summary.{field}: AUSENTE")

    print()
    return all_ok


def show_summary(db):
    """Mostra resumo do estado atual"""
    logger.info("=" * 60)
    logger.info("RESUMO")
    logger.info("=" * 60)

    # Logs
    logs_count = db['zpp_processing_logs'].count_documents({})
    success_count = db['zpp_processing_logs'].count_documents({'status': 'success'})
    failed_count = db['zpp_processing_logs'].count_documents({'status': 'failed'})
    running_count = db['zpp_processing_logs'].count_documents({'status': 'running'})

    logger.info(f"Logs de processamento:")
    logger.info(f"  Total:       {logs_count}")
    logger.info(f"  Sucesso:     {success_count}")
    logger.info(f"  Falhas:      {failed_count}")
    logger.info(f"  Em execução: {running_count}")

    # Configuração
    config = db['zpp_processor_config'].find_one({'_id': 'global'})
    if config:
        logger.info(f"\nConfiguração:")
        logger.info(f"  Auto-process:     {config.get('auto_process')}")
        logger.info(f"  Intervalo (min):  {config.get('interval_minutes')}")
        logger.info(f"  Arquivamento:     {config.get('archive_enabled')}")
        logger.info(f"  Última atualização: {config.get('last_updated')}")

    print()


def main():
    """Função principal"""
    print("\n" + "=" * 80)
    print("ZPP PROCESSOR - VALIDAÇÃO DO MONGODB")
    print("=" * 80)
    print()

    # Obter configurações
    MONGO_URI = os.getenv('MONGO_URI')
    DB_NAME = os.getenv('DB_NAME')

    if not MONGO_URI or not DB_NAME:
        logger.error("ERRO: Variáveis MONGO_URI e DB_NAME não configuradas\n")
        return 1

    logger.info(f"Database: {DB_NAME}\n")

    # Conectar
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    except Exception as e:
        logger.error(f"Erro ao conectar: {e}\n")
        return 1

    try:
        # Executar validações
        results = []

        ok, db = validate_connection(client, DB_NAME)
        results.append(("Conexão", ok))

        if not db:
            return 1

        results.append(("Collections", validate_collections(db)))
        results.append(("Índices", validate_logs_indexes(db)))
        results.append(("Configuração", validate_config(db)))
        results.append(("Estrutura de Logs", validate_sample_data(db)))

        # Resumo
        show_summary(db)

        # Resultado final
        logger.info("=" * 60)
        logger.info("RESULTADO DAS VALIDAÇÕES")
        logger.info("=" * 60)

        all_ok = True
        for name, ok in results:
            status = "✓ PASS" if ok else "✗ FAIL"
            logger.info(f"{status} - {name}")
            if not ok:
                all_ok = False

        print()

        if all_ok:
            logger.info("✓ TODAS AS VALIDAÇÕES PASSARAM")
            logger.info("\nO MongoDB está configurado corretamente para o ZPP Processor.\n")
            return 0
        else:
            logger.error("✗ ALGUMAS VALIDAÇÕES FALHARAM")
            logger.error("\nExecute init_mongodb.py para corrigir problemas.\n")
            return 1

    except Exception as e:
        logger.error(f"\nErro durante validação: {e}\n")
        return 1

    finally:
        client.close()


if __name__ == '__main__':
    exit(main())
