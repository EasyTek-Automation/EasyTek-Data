"""
Migrado e adaptado de process_zpp_to_mongo.py
Processador unificado de planilhas ZPP com integração para logs MongoDB
"""
import pandas as pd
from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime, time as datetime_time, timedelta
from pathlib import Path
import logging
from typing import Dict, List, Optional
import shutil
import re
import unicodedata

from cleaner import detect_file_type, ZPPCleaner, find_excel_files
from models.processing_log import create_file_entry
import config

logger = logging.getLogger(__name__)


def normalize_column_name(col_name: str) -> str:
    """
    Normaliza nome de coluna para padrão MongoDB-friendly

    Transformações:
    - Remove acentos (ç → c, á → a, etc)
    - Converte para minúsculas
    - Remove caracteres especiais
    - Substitui espaços por underscores
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

    def __init__(self, mongo_uri: str, db_name: str, archive_dir: Path):
        """
        Inicializa o processador

        Args:
            mongo_uri: URI de conexão MongoDB
            db_name: Nome do banco de dados
            archive_dir: Diretório para arquivar arquivos processados
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

        self.archive_dir = archive_dir

    def prepare_dataframe(self, df: pd.DataFrame, file_type: str,
                         file_name: str) -> pd.DataFrame:
        """Prepara DataFrame para upload ao MongoDB"""
        df = df.copy()

        # Normalizar nomes das colunas
        logger.info("  Normalizando nomes das colunas...")
        original_columns = df.columns.tolist()
        df.columns = [normalize_column_name(col) for col in df.columns]

        # Log das mudanças
        for i, (orig, new) in enumerate(zip(original_columns[:5], df.columns[:5])):
            if orig != new:
                logger.info(f"    '{orig}' → '{new}'")
        if len(original_columns) > 5:
            logger.info(f"    ... e mais {len(original_columns) - 5} colunas")

        # Converter datetime.time e timedelta para string
        for col in df.columns:
            if df[col].dtype == 'object':
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
                df[col] = df[col].apply(lambda x: str(x) if pd.notna(x) else None)

        # Converter datetime64[ns] para datetime Python
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].apply(lambda x: x.to_pydatetime() if pd.notna(x) else None)

        # Converter NaN para None
        df = df.where(pd.notna(df), None)

        # Adicionar metadados
        df['_uploaded_at'] = datetime.now()
        df['_source_file'] = file_type
        df['_source_filename'] = file_name
        df['_processed'] = True

        return df

    def create_indexes_producao(self, collection):
        """Cria índices otimizados para Produção"""
        logger.info("  Criando índices para Produção...")

        indexes = [
            ([('pto_trab', ASCENDING), ('fininotif', DESCENDING)], 'idx_equipamento_data', {}),
            ([('ordem', ASCENDING)], 'idx_ordem_unique', {'unique': True, 'sparse': True}),
            ([('fininotif', ASCENDING), ('ffinnotif', ASCENDING)], 'idx_range_datas', {}),
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

        indexes = [
            ([('centro_de_trabalho', ASCENDING), ('inicio_execucao', DESCENDING)], 'idx_linha_data', {}),
            ([('ordem', ASCENDING)], 'idx_ordem', {'sparse': True}),
            ([('centro_de_trabalho', ASCENDING), ('inicio_execucao', ASCENDING), ('inicio_real_hora', ASCENDING), ('ordem', ASCENDING)],
             'idx_parada_unique', {'unique': True, 'sparse': True}),
            ([('causa_do_desvio', ASCENDING)], 'idx_motivo', {}),
            ([('inicio_execucao', ASCENDING), ('fim_execucao', ASCENDING)], 'idx_range_datas', {}),
            ([('duration_min', DESCENDING)], 'idx_duracao', {})
        ]

        for keys, name, options in indexes:
            try:
                collection.create_index(keys, name=name, **options)
            except Exception as e:
                logger.warning(f"  [!] Índice {name} já existe ou erro: {e}")

        logger.info("  [OK] Índices de Paradas configurados")

    def move_to_archive(self, file_path: Path) -> Optional[Path]:
        """
        Move arquivo processado para diretório de arquivamento

        Args:
            file_path: Caminho do arquivo a mover

        Returns:
            Path do arquivo no destino ou None se falhar
        """
        try:
            # Garantir que diretório existe
            self.archive_dir.mkdir(parents=True, exist_ok=True)

            # Definir destino
            destination = self.archive_dir / file_path.name

            # Se arquivo já existe, adicionar timestamp
            if destination.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                stem = destination.stem
                suffix = destination.suffix
                destination = self.archive_dir / f"{stem}_{timestamp}{suffix}"

            # Mover arquivo
            shutil.move(str(file_path), str(destination))
            logger.info(f"  [OK] Arquivo movido para: {destination.name}")

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
            move_after_process: Se True, move arquivo para output após sucesso

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
                'filename': file_name,
                'type': 'unknown',
                'collection_name': None,
                'uploaded_rows': 0,
                'status': 'failed',
                'error_message': 'Tipo não reconhecido'
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
                'filename': file_name,
                'type': file_type,
                'collection_name': None,
                'uploaded_rows': 0,
                'status': 'failed',
                'error_message': f'Erro na limpeza: {str(e)}'
            }

        # 3. Preparar para MongoDB
        logger.info("Etapa 3/5: Preparando para MongoDB...")
        df_prepared = self.prepare_dataframe(df_clean, file_type, file_name)

        # Determinar collection (nomes fixos)
        if file_type == 'zppprd':
            collection_name = 'ZPP_Producao'
        else:
            collection_name = 'ZPP_Paradas'

        logger.info(f"  [OK] Collection: {collection_name}\n")

        # FILTRAR EQUIPAMENTOS INDESEJADOS
        logger.info("Etapa 3.5/5: Filtrando equipamentos...")
        records_before = len(df_prepared)

        equipment_col = 'pto_trab' if file_type == 'zppprd' else 'centro_de_trabalho'
        ignore_prefixes = ['EMBAL', 'EMBBOBCP']

        mask = ~df_prepared[equipment_col].astype(str).str.upper().str.startswith(tuple(ignore_prefixes))
        df_prepared = df_prepared[mask]

        records_after = len(df_prepared)
        records_removed = records_before - records_after

        if records_removed > 0:
            logger.info(f"  [OK] Removidos {records_removed:,} registros EMBAL")
        logger.info(f"  [OK] {records_after:,} registros para upload\n")

        # 4. Upload ao MongoDB (modo replace: delete + reinsert)
        logger.info("Etapa 4/5: Upload ao MongoDB (modo substituição)...")
        collection = self.db[collection_name]

        records = df_prepared.to_dict('records')
        total_records = len(records)
        total_inserted = 0
        replaced_count = 0

        logger.info(f"  Total: {total_records:,} registros")

        # ── Passo 4a: determinar intervalo de datas da planilha ─────────────
        # Produção: campo ffinnotif (data FIM) — alinha com MONTH_BOUNDARY_RULE="fim"
        # Paradas: campo inicio_execucao
        date_field = 'ffinnotif' if file_type == 'zppprd' else 'inicio_execucao'

        dates = [r[date_field] for r in records if r.get(date_field) is not None]
        if not dates:
            logger.error(f"  [X] Nenhuma data válida no campo '{date_field}' — abortando")
            raise ValueError(f"Campo '{date_field}' ausente ou nulo em todos os registros")

        min_date = min(dates)
        max_date = max(dates)

        # Usar as datas exatas da planilha — sem expandir para mês completo
        range_start = min_date.replace(hour=0, minute=0, second=0, microsecond=0)
        range_end   = max_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        logger.info(f"  Intervalo da planilha: {range_start.strftime('%d/%m/%Y')} "
                    f"→ {range_end.strftime('%d/%m/%Y')}")

        # ── Passo 4b: backup + delete de TODOS os registros do Mongo no intervalo
        backup = []
        try:
            date_query = {date_field: {'$gte': range_start, '$lte': range_end}}
            backup = list(collection.find(date_query))
            replaced_count = len(backup)

            if replaced_count:
                collection.delete_many(date_query)
                logger.info(f"  [OK] {replaced_count} registros removidos do Mongo (período coberto pela planilha)")
            else:
                logger.info("  Nenhum registro existente no período — inserção pura")

        except Exception as e:
            logger.error(f"  [X] Erro na etapa de backup/delete: {e}")
            raise

        # ── Passo 4b: inserir todos os registros em lotes ───────────────────
        total_batches = (total_records - 1) // batch_size + 1 if total_records else 0
        logger.info(f"  Lotes: {total_batches}")

        try:
            for i in range(0, total_records, batch_size):
                batch = records[i:i + batch_size]
                batch_num = i // batch_size + 1

                result = collection.insert_many(batch, ordered=False)
                total_inserted += len(result.inserted_ids)

                percent = ((i + len(batch)) / total_records) * 100
                logger.info(f"  -> Lote {batch_num:>3}/{total_batches}: "
                            f"{total_inserted:>6}/{total_records} ({percent:>5.1f}%)")

        except Exception as e:
            logger.error(f"  [X] Erro no upload: {e}")

            # ── Rollback: restaurar backup ───────────────────────────────────
            if backup:
                logger.warning(f"  [!] Iniciando rollback — restaurando {len(backup)} registros...")
                try:
                    for doc in backup:
                        doc.pop('_id', None)
                    collection.insert_many(backup, ordered=False)
                    logger.info(f"  [OK] Rollback concluído — dados originais restaurados")
                except Exception as restore_err:
                    logger.error(f"  [XX] Falha no rollback: {restore_err}")
                    logger.error(f"  [XX] ATENÇÃO: dados podem estar inconsistentes na collection {collection_name}")
            raise

        logger.info(f"  [OK] Upload concluído: {total_inserted:,} inseridos, "
                    f"{replaced_count:,} substituídos\n")

        # 5. Criar índices
        logger.info("Etapa 5/5: Configurando índices...")
        if file_type == 'zppprd':
            self.create_indexes_producao(collection)
        else:
            self.create_indexes_paradas(collection)
        print()

        # 6. Arquivar
        archive_path = None
        if move_after_process:
            logger.info("Arquivando...")
            archive_path = self.move_to_archive(file_path)

        # Retornar entrada para log (formato create_file_entry)
        return create_file_entry(
            filename=file_name,
            file_type=file_type,
            collection_name=collection_name,
            uploaded_rows=total_inserted,
            status='success' if total_inserted > 0 else 'failed',
            error_message=None if total_inserted > 0 else 'Nenhum registro inserido',
            replaced_rows=replaced_count
        )

    def process_directory(self, directory: Path, batch_size: int = 1000,
                         move_after_process: bool = True) -> List[Dict]:
        """
        Processa todos os arquivos Excel de um diretório

        Args:
            directory: Diretório contendo arquivos Excel
            batch_size: Tamanho do lote
            move_after_process: Se True, move arquivos

        Returns:
            Lista com estatísticas (formato create_file_entry)
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"PROCESSAMENTO EM LOTE")
        logger.info(f"Diretório: {directory}")
        logger.info(f"{'='*80}\n")

        excel_files = find_excel_files(str(directory))

        if not excel_files:
            logger.warning("Nenhum arquivo encontrado.")
            return []

        results = []

        for file_path in excel_files:
            try:
                file_result = self.process_file(file_path, batch_size, move_after_process)
                results.append(file_result)
            except Exception as e:
                logger.error(f"[X] Erro inesperado: {e}\n")
                results.append(create_file_entry(
                    filename=file_path.name,
                    file_type='unknown',
                    collection_name=None,
                    uploaded_rows=0,
                    status='failed',
                    error_message=str(e)
                ))

        return results

    def close(self):
        """Fecha conexão MongoDB"""
        self.client.close()
        logger.info("Conexão MongoDB fechada")
