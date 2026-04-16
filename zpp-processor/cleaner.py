"""
Migrado de clean_zpp_data.py
Limpeza de planilhas ZPP (Produção e Paradas)
Remove linhas totalizadoras antes de subir ao banco de dados.
"""
import pandas as pd
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class UnknownFileTypeError(Exception):
    """Arquivo rejeitado por tipo não reconhecido (SP-01)."""
    pass


def detect_file_type(file_path: str) -> str:
    """
    Detecta o tipo do arquivo ZPP pela coluna obrigatória (SP-01).
    Detecção case-insensitive e tolerante a espaços extras.

    Retorna 'zppprd' ou 'zppparadas'.
    Lança UnknownFileTypeError se nenhuma coluna obrigatória for encontrada.
    """
    try:
        df_sample = pd.read_excel(file_path, nrows=5)
        cols = {c.strip().lower() for c in df_sample.columns}

        if "ffinnotif" in cols:
            logger.info("  -> Tipo detectado: zppprd")
            return "zppprd"

        if "fim execução" in cols:
            logger.info("  -> Tipo detectado: zppparadas")
            return "zppparadas"

        logger.error(f"  -> Tipo não reconhecido. Colunas: {list(df_sample.columns)[:8]}")
        raise UnknownFileTypeError(
            "Arquivo rejeitado: tipo de planilha não reconhecido. "
            "Colunas esperadas: 'FFinNotif' (zppprd) ou 'Fim execução' (zppparadas)."
        )

    except UnknownFileTypeError:
        raise
    except Exception as e:
        logger.error(f"  -> Erro ao detectar tipo: {e}")
        raise UnknownFileTypeError(f"Erro ao inspecionar colunas do arquivo: {e}")


def find_excel_files(directory: str) -> list:
    """
    Encontra todos os arquivos Excel em um diretório.

    Args:
        directory: Diretório para buscar

    Returns:
        Lista de caminhos de arquivos Excel encontrados
    """
    search_path = Path(directory)

    if not search_path.exists():
        logger.error(f"Diretório não encontrado: {directory}")
        return []

    # Buscar arquivos .xlsx e .xls (case insensitive)
    excel_files = set()
    for ext in ['*.xlsx', '*.XLSX', '*.xls', '*.XLS']:
        excel_files.update(search_path.glob(ext))

    # Filtrar apenas arquivos (não diretórios) e excluir temporários
    excel_files = [
        f for f in excel_files
        if f.is_file()
        and '_cleaned' not in f.name.lower()
        and not f.name.startswith('~$')
    ]

    # Ordenar por nome
    excel_files = sorted(excel_files, key=lambda x: x.name.lower())

    logger.info(f"Encontrados {len(excel_files)} arquivo(s) Excel em: {directory}")
    for f in excel_files:
        logger.info(f"  - {f.name}")

    return excel_files


class ZPPCleaner:
    """
    Classe para limpeza de dados ZPP (SAP)
    Remove linhas totalizadoras baseado em colunas específicas.
    """

    # Configurações de colunas críticas por tipo de arquivo
    CRITICAL_COLUMNS = {
        'zppprd': {
            'identifier': 'Pto.Trab.',
            'required': ['Pto.Trab.', 'FIniNotif', 'FFinNotif', 'Ordem'],
            'description': 'ZPP PRD - Produção'
        },
        'zppparadas': {
            'identifier': 'Centro de trabalho',
            'required': ['Centro de trabalho', 'Ordem', 'Início execução', 'Fim execução'],
            'description': 'ZPP PARADAS - Paradas de Linha'
        }
    }

    def __init__(self, file_path: str, file_type: str):
        """
        Inicializa o limpador de dados ZPP.

        Args:
            file_path: Caminho para o arquivo Excel
            file_type: Tipo do arquivo ('zppprd' ou 'zppparadas')
        """
        self.file_path = Path(file_path)
        self.file_type = file_type.lower()

        if self.file_type not in self.CRITICAL_COLUMNS:
            raise ValueError(f"Tipo de arquivo inválido: {file_type}")

        self.config = self.CRITICAL_COLUMNS[self.file_type]
        self.df = None
        self.original_rows = 0
        self.cleaned_rows = 0
        self.removed_rows = 0

    def load_data(self) -> pd.DataFrame:
        """Carrega os dados do arquivo Excel"""
        logger.info(f"Carregando arquivo: {self.file_path}")

        try:
            self.df = pd.read_excel(self.file_path, sheet_name=0)
            self.original_rows = len(self.df)

            logger.info(f"✓ Arquivo carregado: {self.original_rows} linhas x {len(self.df.columns)} colunas")
            logger.info(f"  Tipo: {self.config['description']}")

            return self.df

        except Exception as e:
            logger.error(f"✗ Erro ao carregar arquivo: {e}")
            raise

    def identify_totalizer_rows(self) -> pd.Series:
        """Identifica linhas totalizadoras baseado nas colunas críticas"""
        if self.df is None:
            raise ValueError("Dados não carregados. Execute load_data() primeiro.")

        logger.info(f"Identificando linhas totalizadoras...")
        logger.info(f"  Colunas críticas: {self.config['required']}")

        # Verificar se todas as colunas críticas existem
        missing_cols = [col for col in self.config['required'] if col not in self.df.columns]
        if missing_cols:
            logger.warning(f"  ⚠ Colunas não encontradas: {missing_cols}")
            required_cols = [col for col in self.config['required'] if col in self.df.columns]
        else:
            required_cols = self.config['required']

        # Método 1: Todas as colunas obrigatórias são nulas
        all_required_null = self.df[required_cols].isnull().all(axis=1)

        # Método 2: Coluna identificadora principal é nula
        identifier_null = self.df[self.config['identifier']].isnull()

        # Método 3: Maioria das colunas obrigatórias está nula
        cols_except_identifier = [col for col in required_cols if col != self.config['identifier']]
        if len(cols_except_identifier) > 0:
            null_count = self.df[cols_except_identifier].isnull().sum(axis=1)
            threshold = len(cols_except_identifier) * 0.5
            majority_null = null_count >= threshold
        else:
            majority_null = pd.Series([False] * len(self.df), index=self.df.index)

        # Combinar todos os métodos
        is_totalizer = all_required_null | identifier_null | majority_null

        num_totalizers = is_totalizer.sum()
        logger.info(f"  ✓ Encontradas {num_totalizers} linhas totalizadoras")

        if num_totalizers > 0:
            totalizer_indices = self.df[is_totalizer].index.tolist()
            logger.info(f"  Índices: {totalizer_indices[:10]}{'...' if len(totalizer_indices) > 10 else ''}")

        return is_totalizer

    def remove_totalizer_rows(self) -> pd.DataFrame:
        """Remove linhas totalizadoras do DataFrame"""
        if self.df is None:
            raise ValueError("Dados não carregados. Execute load_data() primeiro.")

        is_totalizer = self.identify_totalizer_rows()

        # Criar cópia sem linhas totalizadoras
        df_cleaned = self.df[~is_totalizer].copy()

        self.cleaned_rows = len(df_cleaned)
        self.removed_rows = self.original_rows - self.cleaned_rows

        logger.info(f"\n📊 Resumo da Limpeza:")
        logger.info(f"  Linhas originais:    {self.original_rows:>6}")
        logger.info(f"  Linhas removidas:    {self.removed_rows:>6}")
        logger.info(f"  Linhas finais:       {self.cleaned_rows:>6}")
        logger.info(f"  Taxa de remoção:     {(self.removed_rows/self.original_rows*100):>5.2f}%")

        return df_cleaned

    def get_cleaned_dataframe(self) -> pd.DataFrame:
        """Retorna o DataFrame limpo (sem salvar em arquivo)"""
        if self.df is None:
            raise ValueError("Dados não carregados. Execute load_data() primeiro.")

        return self.remove_totalizer_rows()
