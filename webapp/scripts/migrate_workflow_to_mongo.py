"""
Script de migração de dados do Workflow de CSV para MongoDB.

Execute este script UMA VEZ após criar as collections no MongoDB.

Uso:
    python webapp/scripts/migrate_workflow_to_mongo.py
"""
import sys
import os
from pathlib import Path
import pandas as pd
from datetime import datetime

# Adicionar caminho do projeto ao PYTHONPATH
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from webapp.src.database.connection import get_mongo_connection


def migrar_pendencias():
    """Migra pendências do CSV para MongoDB."""
    print("\n📦 Migrando pendências...")

    # Caminho do CSV
    csv_path = project_root / "webapp" / "src" / "data" / "workflow_pendencias.csv"

    if not csv_path.exists():
        print(f"⚠️  CSV não encontrado: {csv_path}")
        return 0

    # Carregar CSV
    df = pd.read_csv(csv_path)
    print(f"   Encontradas {len(df)} pendências no CSV")

    # Converter datas
    df['data_criacao'] = pd.to_datetime(df['data_criacao'], format='mixed')
    df['ultima_atualizacao'] = pd.to_datetime(df['ultima_atualizacao'], format='mixed')
    if 'ultima_edicao_data' in df.columns:
        df['ultima_edicao_data'] = pd.to_datetime(df['ultima_edicao_data'], format='mixed')

    # Conectar ao MongoDB
    collection = get_mongo_connection("workflow_pendencias")

    # Limpar collection (segurança: perguntar antes)
    count_existing = collection.count_documents({})
    if count_existing > 0:
        resposta = input(f"   ⚠️  Já existem {count_existing} documentos. Limpar collection? (s/N): ")
        if resposta.lower() == 's':
            collection.delete_many({})
            print("   ✅ Collection limpa")
        else:
            print("   ❌ Migração cancelada")
            return 0

    # Inserir documentos
    documentos = df.to_dict('records')
    if documentos:
        result = collection.insert_many(documentos)
        print(f"   ✅ {len(result.inserted_ids)} pendências migradas")
        return len(result.inserted_ids)
    else:
        print("   ⚠️  Nenhuma pendência para migrar")
        return 0


def migrar_historico():
    """Migra histórico do CSV para MongoDB."""
    print("\n📦 Migrando histórico...")

    # Caminho do CSV
    csv_path = project_root / "webapp" / "src" / "data" / "workflow_historico.csv"

    if not csv_path.exists():
        print(f"⚠️  CSV não encontrado: {csv_path}")
        return 0

    # Carregar CSV
    df = pd.read_csv(csv_path)
    print(f"   Encontrados {len(df)} registros de histórico no CSV")

    # Converter datas
    df['data'] = pd.to_datetime(df['data'], format='mixed')

    # Conectar ao MongoDB
    collection = get_mongo_connection("workflow_historico")

    # Limpar collection (segurança: perguntar antes)
    count_existing = collection.count_documents({})
    if count_existing > 0:
        resposta = input(f"   ⚠️  Já existem {count_existing} documentos. Limpar collection? (s/N): ")
        if resposta.lower() == 's':
            collection.delete_many({})
            print("   ✅ Collection limpa")
        else:
            print("   ❌ Migração cancelada")
            return 0

    # Inserir documentos
    documentos = df.to_dict('records')
    if documentos:
        result = collection.insert_many(documentos)
        print(f"   ✅ {len(result.inserted_ids)} registros de histórico migrados")
        return len(result.inserted_ids)
    else:
        print("   ⚠️  Nenhum histórico para migrar")
        return 0


def verificar_migracao():
    """Verifica se a migração foi bem-sucedida."""
    print("\n🔍 Verificando migração...")

    pend_collection = get_mongo_connection("workflow_pendencias")
    hist_collection = get_mongo_connection("workflow_historico")

    count_pend = pend_collection.count_documents({})
    count_hist = hist_collection.count_documents({})

    print(f"   📊 Pendências no MongoDB: {count_pend}")
    print(f"   📊 Histórico no MongoDB: {count_hist}")

    # Mostrar exemplo de documento
    if count_pend > 0:
        exemplo = pend_collection.find_one()
        print(f"\n   📄 Exemplo de pendência:")
        print(f"      ID: {exemplo.get('id')}")
        print(f"      Descrição: {exemplo.get('descricao')[:50]}...")
        print(f"      Responsável: {exemplo.get('responsavel')}")
        print(f"      Status: {exemplo.get('status')}")


def main():
    """Executa a migração completa."""
    print("=" * 70)
    print("🚀 MIGRAÇÃO DE WORKFLOW: CSV → MongoDB")
    print("=" * 70)

    try:
        # Migrar pendências
        total_pend = migrar_pendencias()

        # Migrar histórico
        total_hist = migrar_historico()

        # Verificar
        verificar_migracao()

        print("\n" + "=" * 70)
        print("✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        print(f"   Total migrado: {total_pend} pendências, {total_hist} históricos")
        print("=" * 70)

        print("\n📝 PRÓXIMOS PASSOS:")
        print("   1. Verifique os dados no MongoDB Compass")
        print("   2. Informe ao Claude para prosseguir com a migração do código")
        print("   3. Após testes, você pode arquivar os CSVs")

    except Exception as e:
        print(f"\n❌ ERRO durante a migração: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
