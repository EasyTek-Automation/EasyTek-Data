"""
Script para corrigir índices após mudança de normalização de colunas
Remove índices antigos (com nomes em maiúsculas) e recria com nomes normalizados
"""

from pymongo import MongoClient, ASCENDING, DESCENDING
import os
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_indexes():
    """Remove índices antigos e recria com nomes normalizados"""

    # Conectar ao MongoDB
    MONGO_URI = os.getenv('MONGO_URI')
    DB_NAME = os.getenv('DB_NAME')

    if not MONGO_URI or not DB_NAME:
        logger.error("MONGO_URI e DB_NAME devem estar configurados no .env")
        return

    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    # Collections a corrigir (adicione mais se necessário)
    collections_to_fix = [
        'ZPP_Producao_2025',
        'ZPP_Producao_2024',
        'ZPP_Paradas_2025',
        'ZPP_Paradas_2024'
    ]

    for coll_name in collections_to_fix:
        if coll_name not in db.list_collection_names():
            logger.info(f"Collection {coll_name} não existe, pulando...")
            continue

        logger.info(f"\n{'='*60}")
        logger.info(f"Corrigindo: {coll_name}")
        logger.info(f"{'='*60}")

        collection = db[coll_name]

        # Listar índices atuais
        logger.info("\nÍndices atuais:")
        indexes = collection.list_indexes()
        for idx in indexes:
            logger.info(f"  - {idx['name']}: {idx['key']}")

        # Remover índice antigo de Ordem (maiúsculo)
        logger.info("\nRemovendo índice antigo...")
        try:
            collection.drop_index('idx_ordem_unique')
            logger.info("  [OK] idx_ordem_unique removido")
        except Exception as e:
            logger.warning(f"  [!] Não foi possível remover idx_ordem_unique: {e}")

        # Recriar índices com nomes normalizados
        logger.info("\nRecriando índices com nomes normalizados...")

        if 'Producao' in coll_name:
            # Índices para Produção
            indexes_to_create = [
                ([('pto_trab', ASCENDING), ('fininotif', DESCENDING)], 'idx_equipamento_data', {}),
                ([('ordem', ASCENDING)], 'idx_ordem_unique', {'unique': True, 'sparse': True}),  # sparse=True permite múltiplos null
                ([('fininotif', ASCENDING), ('ffinnotif', ASCENDING)], 'idx_range_datas', {}),
                ([('_year', ASCENDING)], 'idx_year', {}),
                ([('pto_trab', ASCENDING), ('kg_proc', DESCENDING)], 'idx_equipamento_producao', {})
            ]
        else:
            # Índices para Paradas
            indexes_to_create = [
                ([('linea', ASCENDING), ('data_inicio', DESCENDING)], 'idx_linha_data', {}),
                ([('ordem', ASCENDING)], 'idx_ordem', {'sparse': True}),
                ([('linea', ASCENDING), ('data_inicio', ASCENDING), ('hora_inicio', ASCENDING), ('ordem', ASCENDING)],
                 'idx_parada_unique', {'unique': True, 'sparse': True}),  # Impede duplicatas
                ([('motivo', ASCENDING)], 'idx_motivo', {}),
                ([('data_inicio', ASCENDING), ('data_fim', ASCENDING)], 'idx_range_datas', {}),
                ([('_year', ASCENDING)], 'idx_year', {}),
                ([('duracao_min', DESCENDING)], 'idx_duracao', {})
            ]

        for keys, name, options in indexes_to_create:
            try:
                # Remover índice se já existir
                try:
                    collection.drop_index(name)
                except:
                    pass

                # Criar índice
                collection.create_index(keys, name=name, **options)
                logger.info(f"  [OK] {name} criado")
            except Exception as e:
                logger.error(f"  [X] Erro ao criar {name}: {e}")

        logger.info(f"\n[OK] {coll_name} corrigido!")

    client.close()
    logger.info(f"\n{'='*60}")
    logger.info("Correção de índices concluída!")
    logger.info(f"{'='*60}\n")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("CORREÇÃO DE ÍNDICES ZPP")
    print("Remove índices antigos e recria com nomes normalizados")
    print("="*60 + "\n")

    fix_indexes()
