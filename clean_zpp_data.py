"""
Script para limpeza de planilhas ZPP (Produção e Paradas)
Remove linhas totalizadoras antes de subir ao banco de dados.

Detecta automaticamente o tipo de planilha pela estrutura das colunas.
Processa todos os arquivos Excel de um diretório.

Autor: Claude Code
Data: 2026-01-28
Versão: 2.0.0
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import logging
import glob

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def detect_file_type(file_path: str) -> Optional[str]:
    """
    Detecta automaticamente o tipo de arquivo ZPP baseado nas colunas.

    Args:
        file_path: Caminho para o arquivo Excel

    Returns:
        'zppprd', 'zppparadas' ou None se não reconhecido
    """
    try:
        # Ler apenas as primeiras linhas para verificar colunas
        df_sample = pd.read_excel(file_path, nrows=5)
        columns = set(df_sample.columns)

        # Assinaturas de colunas por tipo
        signatures = {
            'zppprd': {'Pto.Trab.', 'Kg.Proc.', 'HorasAct.', 'FIniNotif', 'FFinNotif'},
            'zppparadas': {'LINEA', 'DATA INICIO', 'DATA FIM', 'MOTIVO', 'DURAÇÃO(min)'}
        }

        # Verificar qual assinatura corresponde melhor
        for file_type, signature in signatures.items():
            # Se pelo menos 80% das colunas da assinatura estão presentes
            matching_cols = signature & columns
            match_ratio = len(matching_cols) / len(signature)

            if match_ratio >= 0.8:
                logger.info(f"  -> Tipo detectado: {file_type} (confiança: {match_ratio*100:.0f}%)")
                return file_type

        logger.warning(f"  -> Tipo não reconhecido. Colunas encontradas: {list(columns)[:5]}...")
        return None

    except Exception as e:
        logger.error(f"  -> Erro ao detectar tipo: {e}")
        return None


def find_excel_files(directory: str, pattern: str = "*.xlsx") -> List[Path]:
    """
    Encontra todos os arquivos Excel em um diretório.

    Args:
        directory: Diretório para buscar
        pattern: Padrão de arquivo (default: *.xlsx)

    Returns:
        Lista de caminhos de arquivos Excel encontrados
    """
    search_path = Path(directory)

    if not search_path.exists():
        logger.error(f"Diretório não encontrado: {directory}")
        return []

    # Buscar arquivos .xlsx e .xls (case insensitive)
    excel_files = set()  # Usar set para evitar duplicatas
    for ext in ['*.xlsx', '*.XLSX', '*.xls', '*.XLS']:
        excel_files.update(search_path.glob(ext))

    # Filtrar apenas arquivos (não diretórios) e excluir arquivos _cleaned e temporários do Excel
    excel_files = [
        f for f in excel_files
        if f.is_file()
        and '_cleaned' not in f.name.lower()
        and not f.name.startswith('~$')  # Excluir arquivos temporários do Excel
    ]

    # Ordenar por nome para processamento consistente
    excel_files = sorted(excel_files, key=lambda x: x.name.lower())

    logger.info(f"Encontrados {len(excel_files)} arquivo(s) Excel em: {directory}")
    for f in excel_files:
        logger.info(f"  - {f.name}")

    return excel_files


def process_directory(directory: str, output_dir: Optional[str] = None) -> List[Dict]:
    """
    Processa todos os arquivos Excel de um diretório.

    Args:
        directory: Diretório contendo arquivos Excel
        output_dir: Diretório de saída (default: mesmo que entrada)

    Returns:
        Lista com estatísticas de processamento de cada arquivo
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"PROCESSAMENTO EM LOTE - DIRETÓRIO: {directory}")
    logger.info(f"{'='*80}\n")

    # Encontrar arquivos
    excel_files = find_excel_files(directory)

    if not excel_files:
        logger.warning("Nenhum arquivo Excel encontrado para processar.")
        return []

    # Definir diretório de saída
    if output_dir is None:
        output_dir = directory
    else:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    results = []

    # Processar cada arquivo
    for file_path in excel_files:
        logger.info(f"\n{'='*80}")
        logger.info(f"Processando: {file_path.name}")
        logger.info(f"{'='*80}\n")

        try:
            # Detectar tipo automaticamente
            logger.info("Detectando tipo de arquivo...")
            file_type = detect_file_type(str(file_path))

            if file_type is None:
                logger.warning(f"⚠ Arquivo ignorado (tipo não reconhecido): {file_path.name}\n")
                results.append({
                    'file': file_path.name,
                    'success': False,
                    'error': 'Tipo não reconhecido'
                })
                continue

            # Limpar dados
            cleaner = ZPPCleaner(str(file_path), file_type)
            cleaner.load_data()

            # Definir caminho de saída
            output_path = Path(output_dir) / f"{file_path.stem}_cleaned{file_path.suffix}"
            cleaner.save_cleaned_data(str(output_path))

            results.append({
                'file': file_path.name,
                'type': file_type,
                'original': cleaner.original_rows,
                'cleaned': cleaner.cleaned_rows,
                'removed': cleaner.removed_rows,
                'output': output_path.name,
                'success': True
            })

        except Exception as e:
            logger.error(f"✗ Erro ao processar {file_path.name}: {e}\n")
            results.append({
                'file': file_path.name,
                'success': False,
                'error': str(e)
            })

    return results


class ZPPCleaner:
    """
    Classe para limpeza de dados ZPP (SAP)
    Remove linhas totalizadoras baseado em colunas específicas.
    """

    # Configurações de colunas críticas por tipo de arquivo
    CRITICAL_COLUMNS = {
        'zppprd': {
            'identifier': 'Pto.Trab.',  # Coluna identificadora principal
            'required': ['Pto.Trab.', 'FIniNotif', 'FFinNotif', 'Ordem'],  # Colunas que NÃO podem ser todas nulas
            'description': 'ZPP PRD - Produção'
        },
        'zppparadas': {
            'identifier': 'LINEA',  # Coluna identificadora principal
            'required': ['LINEA', 'Ordem', 'DATA INICIO', 'DATA FIM'],  # Colunas que NÃO podem ser todas nulas
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
            raise ValueError(f"Tipo de arquivo inválido: {file_type}. Use 'zppprd' ou 'zppparadas'")

        self.config = self.CRITICAL_COLUMNS[self.file_type]
        self.df = None
        self.original_rows = 0
        self.cleaned_rows = 0
        self.removed_rows = 0

    def load_data(self) -> pd.DataFrame:
        """
        Carrega os dados do arquivo Excel.

        Returns:
            DataFrame com os dados carregados
        """
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
        """
        Identifica linhas totalizadoras baseado nas colunas críticas.

        Uma linha é considerada totalizadora se:
        1. Todas as colunas obrigatórias (required) estão vazias/NaN
        OU
        2. A coluna identificadora principal está vazia
        OU
        3. A maioria (>=50%) das colunas obrigatórias (exceto identificador) está vazia

        Returns:
            Series booleana indicando quais linhas são totalizadoras
        """
        if self.df is None:
            raise ValueError("Dados não carregados. Execute load_data() primeiro.")

        logger.info(f"Identificando linhas totalizadoras...")
        logger.info(f"  Colunas críticas: {self.config['required']}")

        # Verificar se todas as colunas críticas existem
        missing_cols = [col for col in self.config['required'] if col not in self.df.columns]
        if missing_cols:
            logger.warning(f"  ⚠ Colunas não encontradas: {missing_cols}")
            # Usar apenas as colunas que existem
            required_cols = [col for col in self.config['required'] if col in self.df.columns]
        else:
            required_cols = self.config['required']

        # Método 1: Todas as colunas obrigatórias são nulas
        all_required_null = self.df[required_cols].isnull().all(axis=1)

        # Método 2: Coluna identificadora principal é nula
        identifier_null = self.df[self.config['identifier']].isnull()

        # Método 3: Maioria das colunas obrigatórias (exceto identificador) está nula
        # Útil para detectar totalizadores parciais (ex: total por equipamento)
        cols_except_identifier = [col for col in required_cols if col != self.config['identifier']]
        if len(cols_except_identifier) > 0:
            null_count = self.df[cols_except_identifier].isnull().sum(axis=1)
            threshold = len(cols_except_identifier) * 0.5  # 50% das colunas
            majority_null = null_count >= threshold
        else:
            majority_null = pd.Series([False] * len(self.df), index=self.df.index)

        # Combinar todos os métodos (OR lógico)
        is_totalizer = all_required_null | identifier_null | majority_null

        num_totalizers = is_totalizer.sum()
        logger.info(f"  ✓ Encontradas {num_totalizers} linhas totalizadoras")

        if num_totalizers > 0:
            # Mostrar índices das linhas totalizadoras
            totalizer_indices = self.df[is_totalizer].index.tolist()
            logger.info(f"  Índices: {totalizer_indices[:10]}{'...' if len(totalizer_indices) > 10 else ''}")

        return is_totalizer

    def remove_totalizer_rows(self) -> pd.DataFrame:
        """
        Remove linhas totalizadoras do DataFrame.

        Returns:
            DataFrame limpo (sem linhas totalizadoras)
        """
        if self.df is None:
            raise ValueError("Dados não carregados. Execute load_data() primeiro.")

        is_totalizer = self.identify_totalizer_rows()

        # Criar cópia do DataFrame sem as linhas totalizadoras
        df_cleaned = self.df[~is_totalizer].copy()

        self.cleaned_rows = len(df_cleaned)
        self.removed_rows = self.original_rows - self.cleaned_rows

        logger.info(f"\n📊 Resumo da Limpeza:")
        logger.info(f"  Linhas originais:    {self.original_rows:>6}")
        logger.info(f"  Linhas removidas:    {self.removed_rows:>6}")
        logger.info(f"  Linhas finais:       {self.cleaned_rows:>6}")
        logger.info(f"  Taxa de remoção:     {(self.removed_rows/self.original_rows*100):>5.2f}%")

        return df_cleaned

    def save_cleaned_data(self, output_path: Optional[str] = None) -> str:
        """
        Salva os dados limpos em um novo arquivo Excel.

        Args:
            output_path: Caminho para salvar o arquivo. Se None, adiciona '_cleaned' ao nome original

        Returns:
            Caminho do arquivo salvo
        """
        if self.df is None:
            raise ValueError("Dados não carregados. Execute load_data() primeiro.")

        # Remover totalizadores
        df_cleaned = self.remove_totalizer_rows()

        # Definir caminho de saída
        if output_path is None:
            output_path = self.file_path.parent / f"{self.file_path.stem}_cleaned{self.file_path.suffix}"
        else:
            output_path = Path(output_path)

        logger.info(f"\n💾 Salvando arquivo limpo: {output_path}")

        try:
            df_cleaned.to_excel(output_path, index=False, engine='openpyxl')
            logger.info(f"✓ Arquivo salvo com sucesso!")
            return str(output_path)

        except Exception as e:
            logger.error(f"✗ Erro ao salvar arquivo: {e}")
            raise

    def get_cleaned_dataframe(self) -> pd.DataFrame:
        """
        Retorna o DataFrame limpo (sem salvar em arquivo).

        Returns:
            DataFrame limpo
        """
        if self.df is None:
            raise ValueError("Dados não carregados. Execute load_data() primeiro.")

        return self.remove_totalizer_rows()


def clean_zpp_file(file_path: str, file_type: str, output_path: Optional[str] = None) -> pd.DataFrame:
    """
    Função auxiliar para limpar um arquivo ZPP em uma única chamada.

    Args:
        file_path: Caminho para o arquivo Excel
        file_type: Tipo do arquivo ('zppprd' ou 'zppparadas')
        output_path: Caminho de saída (opcional)

    Returns:
        DataFrame limpo

    Example:
        >>> df_clean = clean_zpp_file('zppprd geral ano 2025.xlsx', 'zppprd')
        >>> df_clean = clean_zpp_file('zppparadas geral ano 2025.xlsx', 'zppparadas', 'output/paradas_clean.xlsx')
    """
    cleaner = ZPPCleaner(file_path, file_type)
    cleaner.load_data()

    if output_path:
        cleaner.save_cleaned_data(output_path)

    return cleaner.get_cleaned_dataframe()


if __name__ == "__main__":
    """
    Execução principal do script

    Uso:
        python clean_zpp_data.py                    # Processa arquivos no diretório atual
        python clean_zpp_data.py <diretorio>        # Processa arquivos no diretório especificado
        python clean_zpp_data.py <dir_entrada> <dir_saida>  # Com diretório de saída customizado
    """
    import sys

    print("="*80)
    print("LIMPEZA DE DADOS ZPP - SAP (v2.0)")
    print("Detecção automática de tipo por estrutura")
    print("="*80)
    print()

    # Diretório base
    base_dir = Path(__file__).parent

    # Verificar argumentos de linha de comando
    if len(sys.argv) >= 2:
        input_dir = sys.argv[1]
        output_dir = sys.argv[2] if len(sys.argv) >= 3 else None
    else:
        # Usar diretório atual como padrão
        input_dir = str(base_dir)
        output_dir = None

    logger.info(f"Diretório de entrada: {input_dir}")
    if output_dir:
        logger.info(f"Diretório de saída: {output_dir}")
    else:
        logger.info(f"Diretório de saída: {input_dir} (mesmo que entrada)")

    # Processar todos os arquivos do diretório
    results = process_directory(input_dir, output_dir)

    # Resumo final
    print(f"\n\n{'='*80}")
    print("RESUMO FINAL DO PROCESSAMENTO")
    print(f"{'='*80}\n")

    if not results:
        print("Nenhum arquivo foi processado.")
    else:
        success_count = sum(1 for r in results if r['success'])
        error_count = len(results) - success_count

        print(f"Total de arquivos: {len(results)}")
        print(f"Processados com sucesso: {success_count}")
        print(f"Erros: {error_count}\n")

        for result in results:
            if result['success']:
                print(f"[OK] {result['file']}")
                print(f"     Tipo: {result['type'].upper()}")
                print(f"     Original: {result['original']} | Limpo: {result['cleaned']} | Removido: {result['removed']}")
                print(f"     Saída: {result['output']}")
            else:
                print(f"[ERRO] {result['file']}")
                print(f"       {result['error']}")
            print()

    print(f"{'='*80}\n")
