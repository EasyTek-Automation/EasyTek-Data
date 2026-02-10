"""
Script unificado para processamento de planilhas ZPP ao MongoDB
Fluxo completo: Detecção → Limpeza → Upload → Arquivamento

Funcionalidades:
- Detecta automaticamente o tipo de planilha (PRD ou Paradas)
- Limpa dados (remove linhas totalizadoras)
- Faz upload direto ao MongoDB (sem gerar arquivos intermediários)
- Move arquivos processados para subdiretório "analisados"

Autor: Claude Code
Data: 2026-01-28
Versão: 3.0.0
"""

import pandas as pd
from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime, time as datetime_time, timedelta
from pathlib import Path
import logging
from typing import Dict, List, Optional
import os
import shutil
import re
import unicodedata
from dotenv import load_dotenv
from clean_zpp_data import detect_file_type, find_excel_files, ZPPCleaner

# Carregar variáveis de ambiente
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def normalize_column_name(col_name: str) -> str:
    """
    Normaliza nome de coluna para padrão MongoDB-friendly

    Transformações:
    - Remove acentos (ç → c, á → a, etc)
    - Converte para minúsculas
    - Remove caracteres especiais
    - Substitui espaços por underscores
    - Remove underscores duplicados/extremidades

    Exemplos:
        'DURAÇÃO(min)' → 'duracao_min'
        'DATA INÍCIO' → 'data_inicio'
        'Pto.Trab.' → 'pto_trab'
    """
    # Remover acentos
    normalized = unicodedata.normalize('NFKD', str(col_name))
    normalized = normalized.encode('ASCII', 'ignore').decode('ASCII')

    # Converter para minúsculas
    normalized = normalized.lower()

    # Substituir espaços e caracteres especiais por underscore
    normalized = re.sub(r'[^a-z0-9]+', '_', normalized)

    # Remover underscores duplicados
    normalized = re.sub(r'_+', '_', normalized)

    # Remover underscores das extremidades
    normalized = normalized.strip('_')

    return normalized


class ZPPProcessor:
    """
    Processador unificado de planilhas ZPP
    Processa, faz upload ao MongoDB e arquiva automaticamente
    """

    def __init__(self, mongo_uri: str, db_name: str, archive_dir: str = "analisados"):
        """
        Inicializa o processador

        Args:
            mongo_uri: URI de conexão MongoDB
            db_name: Nome do banco de dados
            archive_dir: Nome do subdiretório para arquivar (default: "analisados")
        """
        # Conectar ao MongoDB
        try:
            self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            self.client.server_info()
            self.db = self.client[db_name]
            logger.info(f"[OK] Conectado ao MongoDB: {db_name}")
        except Exception as e:
            logger.error(f"[X] Erro ao conectar ao MongoDB: {e}")
            raise

        self.archive_dir_name = archive_dir

    def extract_year_from_data(self, df: pd.DataFrame, file_type: str) -> int:
        """Extrai o ano dos dados baseado nas colunas de data"""
        try:
            if file_type == 'zppprd':
                date_col = 'FIniNotif'
            else:
                date_col = 'Início execução'

            first_date = df[date_col].dropna().iloc[0]
            if isinstance(first_date, pd.Timestamp):
                return first_date.year
            else:
                return datetime.now().year
        except:
            return datetime.now().year

    def prepare_dataframe(self, df: pd.DataFrame, file_type: str, year: int,
                         file_name: str) -> pd.DataFrame:
        """Prepara DataFrame para upload ao MongoDB"""
        df = df.copy()

        # Normalizar nomes das colunas
        logger.info("  Normalizando nomes das colunas...")
        original_columns = df.columns.tolist()
        df.columns = [normalize_column_name(col) for col in df.columns]

        # Log das mudanças mais significativas (primeiras 5)
        for i, (orig, new) in enumerate(zip(original_columns[:5], df.columns[:5])):
            if orig != new:
                logger.info(f"    '{orig}' → '{new}'")
        if len(original_columns) > 5:
            logger.info(f"    ... e mais {len(original_columns) - 5} colunas")

        # Converter datetime.time e timedelta para string (MongoDB não suporta esses tipos)
        for col in df.columns:
            if df[col].dtype == 'object':
                # Converter cada célula individualmente (pode ter tipos mistos)
                def convert_time_types(x):
                    if x is None or pd.isna(x):
                        return None
                    if isinstance(x, datetime_time):
                        return x.strftime('%H:%M:%S')
                    elif isinstance(x, timedelta):
                        return str(x)
                    else:
                        return x

                df[col] = df[col].apply(convert_time_types)

            elif df[col].dtype == 'timedelta64[ns]':
                # Converter timedelta64 para string
                df[col] = df[col].apply(lambda x: str(x) if pd.notna(x) else None)

        # Converter datetime64[ns] para datetime Python (compatível com MongoDB)
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].apply(lambda x: x.to_pydatetime() if pd.notna(x) else None)

        # Converter NaN para None
        df = df.where(pd.notna(df), None)

        # Adicionar metadados
        df['_uploaded_at'] = datetime.now()
        df['_source_file'] = file_type
        df['_source_filename'] = file_name
        df['_year'] = year
        df['_processed'] = True

        return df

    def create_indexes_producao(self, collection):
        """Cria índices otimizados para Produção"""
        logger.info("  Criando índices para Produção...")

        # Nomes normalizados: Pto.Trab. → pto_trab, FIniNotif → fininotif, etc
        indexes = [
            ([('pto_trab', ASCENDING), ('fininotif', DESCENDING)], 'idx_equipamento_data', {}),
            ([('ordem', ASCENDING)], 'idx_ordem_unique', {'unique': True, 'sparse': True}),  # sparse=True permite múltiplos null
            ([('fininotif', ASCENDING), ('ffinnotif', ASCENDING)], 'idx_range_datas', {}),
            ([('_year', ASCENDING)], 'idx_year', {}),
            ([('pto_trab', ASCENDING), ('kg_proc', DESCENDING)], 'idx_equipamento_producao', {})
        ]

        for keys, name, options in indexes:
            try:
                collection.create_index(keys, name=name, **options)
            except Exception as e:
                logger.warning(f"  [!] Índice {name} já existe ou erro: {e}")

        logger.info("  [OK] Índices de Produção configurados")

    def create_indexes_paradas(self, collection):
        """Cria índices otimizados para Paradas"""
        logger.info("  Criando índices para Paradas...")

        # Nomes normalizados: Centro de trabalho → centro_de_trabalho, Início execução → inicio_execucao, etc
        indexes = [
            ([('centro_de_trabalho', ASCENDING), ('inicio_execucao', DESCENDING)], 'idx_linha_data', {}),
            ([('ordem', ASCENDING)], 'idx_ordem', {'sparse': True}),  # sparse=True permite múltiplos null
            ([('centro_de_trabalho', ASCENDING), ('inicio_execucao', ASCENDING), ('inicio_real_hora', ASCENDING), ('ordem', ASCENDING)],
             'idx_parada_unique', {'unique': True, 'sparse': True}),  # Impede duplicatas
            ([('causa_do_desvio', ASCENDING)], 'idx_motivo', {}),
            ([('inicio_execucao', ASCENDING), ('fim_execucao', ASCENDING)], 'idx_range_datas', {}),
            ([('_year', ASCENDING)], 'idx_year', {}),
            ([('duration_min', DESCENDING)], 'idx_duracao', {})
        ]

        for keys, name, options in indexes:
            try:
                collection.create_index(keys, name=name, **options)
            except Exception as e:
                logger.warning(f"  [!] Índice {name} já existe ou erro: {e}")

        logger.info("  [OK] Índices de Paradas configurados")

    def move_to_archive(self, file_path: Path, base_dir: Path) -> Optional[Path]:
        """
        Move arquivo processado para subdiretório "analisados"

        Args:
            file_path: Caminho do arquivo a mover
            base_dir: Diretório base onde criar o subdiretório

        Returns:
            Path do arquivo no destino ou None se falhar
        """
        try:
            # Criar subdiretório se não existir
            archive_dir = base_dir / self.archive_dir_name
            archive_dir.mkdir(exist_ok=True)

            # Definir destino
            destination = archive_dir / file_path.name

            # Se arquivo já existe no destino, adicionar timestamp
            if destination.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                stem = destination.stem
                suffix = destination.suffix
                destination = archive_dir / f"{stem}_{timestamp}{suffix}"

            # Mover arquivo
            shutil.move(str(file_path), str(destination))
            logger.info(f"  [OK] Arquivo movido para: {self.archive_dir_name}/{destination.name}")

            return destination

        except Exception as e:
            logger.error(f"  [X] Erro ao mover arquivo: {e}")
            return None

    def process_file(self, file_path: Path, batch_size: int = 1000,
                    move_after_process: bool = True) -> Dict:
        """
        Processa um arquivo: detecta tipo, limpa, faz upload e arquiva

        Args:
            file_path: Caminho do arquivo Excel
            batch_size: Tamanho do lote para inserção
            move_after_process: Se True, move arquivo para "analisados" após sucesso

        Returns:
            Dict com estatísticas do processamento
        """
        file_name = file_path.name

        logger.info(f"\n{'='*80}")
        logger.info(f"PROCESSANDO: {file_name}")
        logger.info(f"{'='*80}\n")

        # 1. Detectar tipo
        logger.info("Etapa 1/5: Detectando tipo...")
        file_type = detect_file_type(str(file_path))

        if file_type is None:
            logger.error(f"[X] Tipo não reconhecido: {file_name}\n")
            return {
                'file': file_name,
                'success': False,
                'error': 'Tipo não reconhecido'
            }

        logger.info(f"  [OK] Tipo: {file_type.upper()}\n")

        # 2. Limpar dados
        logger.info("Etapa 2/5: Limpando dados...")
        try:
            cleaner = ZPPCleaner(str(file_path), file_type)
            cleaner.load_data()
            df_clean = cleaner.get_cleaned_dataframe()
            logger.info(f"  [OK] {len(df_clean)} linhas limpas")
            logger.info(f"  [OK] {cleaner.removed_rows} linhas totalizadoras removidas\n")
        except Exception as e:
            logger.error(f"[X] Erro ao limpar dados: {e}\n")
            return {
                'file': file_name,
                'success': False,
                'error': f'Erro na limpeza: {str(e)}'
            }

        # 3. Preparar para MongoDB
        logger.info("Etapa 3/5: Preparando para MongoDB...")
        year = self.extract_year_from_data(df_clean, file_type)
        df_prepared = self.prepare_dataframe(df_clean, file_type, year, file_name)

        # Determinar collection baseado no ano detectado
        if file_type == 'zppprd':
            collection_name = f'ZPP_Producao_{year}'
        else:
            collection_name = f'ZPP_Paradas_{year}'

        logger.info(f"  [OK] Ano detectado nos dados: {year}")
        logger.info(f"  [OK] Collection dinâmica: {collection_name}\n")

        # FILTRAR EQUIPAMENTOS INDESEJADOS (EMBAL*, EMBBOBCP)
        logger.info("Etapa 3.5/5: Filtrando equipamentos indesejados...")
        records_before = len(df_prepared)

        # Determinar coluna de equipamento baseado no tipo
        equipment_col = 'pto_trab' if file_type == 'zppprd' else 'centro_de_trabalho'

        # Lista de prefixos e nomes exatos a ignorar (DECAP deve aparecer!)
        ignore_prefixes = ['EMBAL', 'EMBBOBCP']

        # Filtrar usando máscaras booleanas
        mask = ~df_prepared[equipment_col].astype(str).str.upper().str.startswith(tuple(ignore_prefixes))
        df_prepared = df_prepared[mask]

        records_after = len(df_prepared)
        records_removed = records_before - records_after

        if records_removed > 0:
            logger.info(f"  [OK] Removidos {records_removed:,} registros de equipamentos EMBAL")
            logger.info(f"  [OK] Restam {records_after:,} registros para upload\n")
        else:
            logger.info(f"  [OK] Nenhum registro removido (todos os equipamentos são válidos)\n")

        # 4. Upload ao MongoDB
        logger.info("Etapa 4/5: Fazendo upload ao MongoDB...")
        collection = self.db[collection_name]

        records = df_prepared.to_dict('records')
        total_records = len(records)
        total_batches = (total_records - 1) // batch_size + 1
        total_inserted = 0
        failed_inserts = 0

        logger.info(f"  Total de registros: {total_records:,}")
        logger.info(f"  Tamanho do lote: {batch_size:,}")
        logger.info(f"  Total de lotes: {total_batches}")
        logger.info(f"  Iniciando upload...")

        # Upload em lotes (com verificação de duplicatas)
        for i in range(0, total_records, batch_size):
            batch = records[i:i + batch_size]
            batch_num = i // batch_size + 1

            # VERIFICAÇÃO DE DUPLICATAS - filtrar registros que já existem
            if file_type == 'zppprd':
                # Para Produção: verificar por 'ordem' (quando não-null)
                ordens_to_check = [r['ordem'] for r in batch if r.get('ordem') is not None]
                if ordens_to_check:
                    existing = set(doc['ordem'] for doc in collection.find(
                        {'ordem': {'$in': ordens_to_check}},
                        {'ordem': 1}
                    ))
                    batch = [r for r in batch if r.get('ordem') is None or r['ordem'] not in existing]
                    skipped = len(ordens_to_check) - len([r for r in batch if r.get('ordem') in ordens_to_check])
                    if skipped > 0:
                        failed_inserts += skipped
            else:
                # Para Paradas: verificar por combinação centro_de_trabalho + inicio_execucao + inicio_real_hora + ordem
                keys_to_check = []
                for r in batch:
                    if all(k in r for k in ['centro_de_trabalho', 'inicio_execucao', 'inicio_real_hora', 'ordem']):
                        keys_to_check.append({
                            'centro_de_trabalho': r['centro_de_trabalho'],
                            'inicio_execucao': r['inicio_execucao'],
                            'inicio_real_hora': r['inicio_real_hora'],
                            'ordem': r['ordem']
                        })

                if keys_to_check:
                    existing_keys = set()
                    existing_docs = collection.find({'$or': keys_to_check}, {
                        'centro_de_trabalho': 1, 'inicio_execucao': 1, 'inicio_real_hora': 1, 'ordem': 1
                    })
                    for doc in existing_docs:
                        key = f"{doc.get('centro_de_trabalho')}|{doc.get('inicio_execucao')}|{doc.get('inicio_real_hora')}|{doc.get('ordem')}"
                        existing_keys.add(key)

                    # Filtrar batch
                    original_len = len(batch)
                    batch = [r for r in batch if
                             f"{r.get('centro_de_trabalho')}|{r.get('inicio_execucao')}|{r.get('inicio_real_hora')}|{r.get('ordem')}" not in existing_keys]
                    skipped = original_len - len(batch)
                    if skipped > 0:
                        failed_inserts += skipped

            # Se o lote ficou vazio após filtrar duplicatas, pular
            if not batch:
                logger.info(f"  -> Lote {batch_num:>3}/{total_batches}: "
                          f"PULADO (todos duplicados)")
                continue

            try:
                result = collection.insert_many(batch, ordered=False)
                total_inserted += len(result.inserted_ids)

                # Mostrar progresso a cada lote
                percent = ((i + len(batch)) / total_records) * 100
                logger.info(f"  -> Lote {batch_num:>3}/{total_batches}: "
                          f"{total_inserted:>6}/{total_records} documentos "
                          f"({percent:>5.1f}%)")

            except Exception as e:
                # Inserção individual em caso de erro
                logger.error(f"  [X] Erro no lote {batch_num}: {type(e).__name__}: {str(e)}")
                logger.warning(f"  [!] Tentando inserção individual...")
                for record in batch:
                    try:
                        collection.insert_one(record)
                        total_inserted += 1
                    except Exception as err:
                        failed_inserts += 1
                        if failed_inserts <= 3:  # Mostrar apenas os 3 primeiros erros
                            logger.error(f"     [X] Erro ao inserir registro: {type(err).__name__}: {str(err)}")

        if failed_inserts > 0:
            logger.warning(f"  [!] {failed_inserts} documentos não inseridos (duplicatas)")

        logger.info(f"  [OK] Upload concluído: {total_inserted:,} documentos\n")

        # 5. Criar índices
        logger.info("Etapa 5/5: Configurando índices...")
        if file_type == 'zppprd':
            self.create_indexes_producao(collection)
        else:
            self.create_indexes_paradas(collection)
        print()

        # 6. Arquivar arquivo processado
        archive_path = None
        if move_after_process:
            logger.info("Arquivando arquivo processado...")
            base_dir = file_path.parent
            archive_path = self.move_to_archive(file_path, base_dir)
            if archive_path:
                logger.info(f"  [OK] Arquivo arquivado com sucesso\n")
            else:
                logger.warning(f"  [!] Arquivo não foi movido, mas dados foram carregados\n")

        # Estatísticas
        stats = {
            'file': file_name,
            'type': file_type,
            'collection': collection_name,
            'year': year,
            'original_rows': cleaner.original_rows,
            'cleaned_rows': cleaner.cleaned_rows,
            'removed_rows': cleaner.removed_rows,
            'uploaded_rows': total_inserted,
            'failed_rows': failed_inserts,
            'archived': archive_path is not None,
            'archive_path': str(archive_path) if archive_path else None,
            'success': True
        }

        logger.info(f"{'='*80}")
        logger.info(f"RESUMO: {file_name}")
        logger.info(f"{'='*80}")
        logger.info(f"  Tipo:                {file_type.upper()}")
        logger.info(f"  Ano:                 {year}")
        logger.info(f"  Linhas originais:    {stats['original_rows']:>6}")
        logger.info(f"  Linhas removidas:    {stats['removed_rows']:>6}")
        logger.info(f"  Documentos salvos:   {stats['uploaded_rows']:>6}")
        if failed_inserts > 0:
            logger.info(f"  Duplicatas ignoradas:{failed_inserts:>6}")
        logger.info(f"  Collection:          {collection_name}")
        logger.info(f"  Arquivado:           {'Sim' if stats['archived'] else 'Não'}")
        logger.info(f"{'='*80}\n")

        return stats

    def process_directory(self, directory: str, batch_size: int = 1000,
                         move_after_process: bool = True) -> List[Dict]:
        """
        Processa todos os arquivos Excel de um diretório

        Args:
            directory: Diretório contendo arquivos Excel
            batch_size: Tamanho do lote para inserção
            move_after_process: Se True, move arquivos processados

        Returns:
            Lista com estatísticas de cada arquivo
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"PROCESSAMENTO EM LOTE")
        logger.info(f"Diretório: {directory}")
        logger.info(f"Arquivamento: {'Ativado' if move_after_process else 'Desativado'}")
        logger.info(f"{'='*80}\n")

        # Encontrar arquivos
        excel_files = find_excel_files(directory)

        if not excel_files:
            logger.warning("Nenhum arquivo Excel encontrado.")
            return []

        results = []

        # Processar cada arquivo
        for file_path in excel_files:
            try:
                stats = self.process_file(file_path, batch_size, move_after_process)
                results.append(stats)
            except Exception as e:
                logger.error(f"[X] Erro inesperado ao processar {file_path.name}: {e}\n")
                results.append({
                    'file': file_path.name,
                    'success': False,
                    'error': str(e)
                })

        return results

    def close(self):
        """Fecha conexão com MongoDB"""
        self.client.close()
        logger.info("Conexão MongoDB fechada")


def main():
    """
    Execução principal do script

    Uso:
        python process_zpp_to_mongo.py                      # Processa diretório atual
        python process_zpp_to_mongo.py <diretorio>          # Processa diretório especificado
        python process_zpp_to_mongo.py <dir> --no-archive   # Sem mover arquivos
    """
    import sys

    print("\n" + "="*80)
    print("PROCESSAMENTO ZPP -> MONGODB (v3.0)")
    print("Deteccao -> Limpeza -> Upload -> Arquivamento")
    print("="*80)

    # Configurações MongoDB
    MONGO_URI = os.getenv('MONGO_URI')
    DB_NAME = os.getenv('DB_NAME')

    if not MONGO_URI or not DB_NAME:
        logger.error("\n[X] Variáveis de ambiente não configuradas: MONGO_URI e/ou DB_NAME")
        logger.error("  Configure no arquivo .env\n")
        sys.exit(1)

    # Argumentos
    args = sys.argv[1:]
    input_dir = args[0] if len(args) >= 1 and not args[0].startswith('--') else str(Path(__file__).parent)
    move_files = '--no-archive' not in args and '--no-move' not in args

    logger.info(f"\nConfiguração:")
    logger.info(f"  MongoDB URI:     {MONGO_URI}")
    logger.info(f"  Database:        {DB_NAME}")
    logger.info(f"  Diretório:       {input_dir}")
    logger.info(f"  Arquivamento:    {'Ativado' if move_files else 'Desativado'}")
    logger.info(f"  Subdiretório:    analisados/")

    try:
        # Inicializar processador
        processor = ZPPProcessor(MONGO_URI, DB_NAME, archive_dir="analisados")

        # Processar diretório
        results = processor.process_directory(
            input_dir,
            batch_size=1000,
            move_after_process=move_files
        )

        # Fechar conexão
        processor.close()

        # Resumo final
        print("\n" + "="*80)
        print("RESUMO FINAL")
        print("="*80 + "\n")

        if not results:
            print("Nenhum arquivo foi processado.\n")
        else:
            success_count = sum(1 for r in results if r['success'])
            error_count = len(results) - success_count
            total_uploaded = sum(r.get('uploaded_rows', 0) for r in results if r['success'])
            total_archived = sum(1 for r in results if r.get('archived', False))

            print(f"Total de arquivos:           {len(results)}")
            print(f"Processados com sucesso:     {success_count}")
            print(f"Erros:                       {error_count}")
            print(f"Documentos carregados:       {total_uploaded:,}")
            if move_files:
                print(f"Arquivos movidos:            {total_archived}")
            print()

            for stat in results:
                if stat['success']:
                    print(f"[OK] {stat['file']}")
                    print(f"  Tipo: {stat['type'].upper()} | Ano: {stat['year']}")
                    print(f"  Carregados: {stat['uploaded_rows']:,} docs")
                    print(f"  Removidas: {stat['removed_rows']} linhas totalizadoras")
                    print(f"  Collection: {stat['collection']}")
                    if move_files:
                        print(f"  Arquivado: {'Sim' if stat['archived'] else 'Não'}")
                else:
                    print(f"[X] {stat['file']}")
                    print(f"  Erro: {stat['error']}")
                print()

        print("="*80 + "\n")

    except Exception as e:
        logger.error(f"\n[X] Erro durante processamento: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
