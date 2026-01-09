# src/config/docs_config.py

"""
Configuração do sistema de documentação de procedimentos.
Gerencia o caminho do volume externo e a estrutura de navegação via docs.yml.
"""

import os
import logging
from pathlib import Path

# Tentativa de importar PyYAML
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    logging.warning("PyYAML não instalado. Funcionalidade docs.yml desabilitada.")

logger = logging.getLogger(__name__)

# Cache global para estrutura de documentação
_docs_cache = {
    "config": None,
    "mtime": None,
    "path": None
}


def get_docs_path():
    """
    Retorna o caminho do volume de documentos.

    Prioridade:
    1. Variável de ambiente DOCS_PROCEDURES_PATH
    2. Fallback: pasta docs/procedures relativa ao projeto

    Returns:
        Path: Caminho do diretório de documentos
    """
    env_path = os.environ.get("DOCS_PROCEDURES_PATH")

    if env_path:
        path = Path(env_path)
        if not path.exists():
            logger.warning(f"DOCS_PROCEDURES_PATH '{env_path}' não existe. Usando fallback.")
        else:
            return path

    # Fallback para desenvolvimento local
    fallback_path = Path(__file__).parent.parent.parent.parent / "docs" / "procedures"
    return fallback_path


def get_markdown_title(filepath):
    """
    Extrai o título (primeiro H1) de um arquivo markdown.

    Args:
        filepath (Path): Caminho do arquivo markdown

    Returns:
        str: Título do documento ou nome do arquivo formatado
    """
    try:
        filepath = Path(filepath)
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('# '):
                        title = line[2:].strip()
                        # Truncar títulos longos
                        return title[:40] + "..." if len(title) > 40 else title
    except Exception as e:
        logger.debug(f"Erro ao extrair título de {filepath}: {e}")

    # Fallback: nome do arquivo formatado
    return filepath.stem.replace('_', ' ').replace('-', ' ').title()


def load_docs_structure():
    """
    Carrega estrutura de navegação do docs.yml.
    Usa cache com hot-reload baseado em modification time.

    Returns:
        dict: Estrutura de navegação com formato:
            {
                "title": str,
                "icon": str,
                "index": str | None,
                "sections": list
            }
    """
    global _docs_cache

    docs_path = get_docs_path()
    yml_path = docs_path / "docs.yml"

    # Tentar carregar do docs.yml
    if YAML_AVAILABLE and yml_path.exists():
        try:
            current_mtime = yml_path.stat().st_mtime

            # Verificar cache (hot-reload)
            if (_docs_cache["config"] is not None and
                _docs_cache["path"] == str(yml_path) and
                _docs_cache["mtime"] == current_mtime):
                return _docs_cache["config"]

            # Carregar YAML
            with open(yml_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            # Validar estrutura básica
            if not isinstance(config, dict):
                raise ValueError("docs.yml deve ser um dicionário")

            # Processar títulos automáticos dos arquivos
            _process_file_titles(config, docs_path)

            # Atualizar cache
            _docs_cache["config"] = config
            _docs_cache["mtime"] = current_mtime
            _docs_cache["path"] = str(yml_path)

            logger.info(f"docs.yml carregado de {yml_path}")
            return config

        except Exception as e:
            logger.error(f"Erro ao carregar docs.yml: {e}. Usando fallback.")

    # Fallback: scan automático da pasta
    return _scan_docs_directory_fallback(docs_path)


def _process_file_titles(config, docs_path):
    """
    Processa títulos automáticos para arquivos sem título definido.
    Modifica o config in-place.

    Args:
        config (dict): Configuração carregada do YAML
        docs_path (Path): Caminho base dos documentos
    """
    def process_section(section):
        # Processar arquivos da seção
        if "files" in section:
            for file_entry in section["files"]:
                if isinstance(file_entry, dict) and "path" in file_entry:
                    if "title" not in file_entry or not file_entry["title"]:
                        file_path = docs_path / file_entry["path"]
                        file_entry["title"] = get_markdown_title(file_path)

        # Processar subseções recursivamente
        if "sections" in section:
            for subsection in section["sections"]:
                process_section(subsection)

    # Processar todas as seções de nível superior
    if "sections" in config:
        for section in config["sections"]:
            process_section(section)


def _scan_docs_directory_fallback(docs_path):
    """
    Fallback: escaneia pasta se docs.yml não existir.
    Mantém compatibilidade com o comportamento anterior.

    Args:
        docs_path (Path): Caminho do diretório de documentos

    Returns:
        dict: Estrutura de navegação no formato do docs.yml
    """
    # Ícones padrão por nome de pasta
    default_icons = {
        "preventive": "bi-calendar-check",
        "corrective": "bi-tools",
        "emergency": "bi-exclamation-triangle",
        "calibration": "bi-rulers",
        "inspection": "bi-search",
        "lubrication": "bi-droplet",
        "predictive": "bi-graph-up",
        "safety": "bi-shield-check",
    }

    # Labels padrão por nome de pasta
    default_labels = {
        "preventive": "Preventiva",
        "corrective": "Corretiva",
        "emergency": "Emergência",
        "calibration": "Calibração",
        "inspection": "Inspeção",
        "lubrication": "Lubrificação",
        "predictive": "Preditiva",
        "safety": "Segurança",
    }

    structure = {
        "title": "Procedimentos",
        "icon": "bi-book",
        "index": None,
        "sections": []
    }

    if not docs_path.exists():
        logger.warning(f"Diretório de documentos não existe: {docs_path}")
        return structure

    # Verificar index.md na raiz
    index_file = docs_path / "index.md"
    if index_file.exists():
        structure["index"] = "index.md"

    # Escanear subdiretórios
    for item in sorted(docs_path.iterdir()):
        if item.is_dir() and not item.name.startswith('.'):
            folder_name = item.name

            section = {
                "name": folder_name,
                "label": default_labels.get(folder_name, folder_name.replace('_', ' ').title()),
                "icon": default_icons.get(folder_name, "bi-folder"),
                "expanded": False,
                "files": []
            }

            # Escanear arquivos .md no diretório
            for md_file in sorted(item.glob("*.md")):
                relative_path = md_file.relative_to(docs_path)
                section["files"].append({
                    "path": relative_path.as_posix(),
                    "title": get_markdown_title(md_file)
                })

            if section["files"]:
                structure["sections"].append(section)

    logger.info(f"Estrutura carregada via scan automático de {docs_path}")
    return structure


def clear_docs_cache():
    """Limpa o cache de documentação. Útil para testes."""
    global _docs_cache
    _docs_cache = {
        "config": None,
        "mtime": None,
        "path": None
    }


def check_file_exists(relative_path):
    """
    Verifica se um arquivo markdown existe no volume.

    Args:
        relative_path (str): Caminho relativo do arquivo

    Returns:
        tuple: (exists: bool, full_path: Path)
    """
    docs_path = get_docs_path()
    full_path = docs_path / relative_path

    # Verificação de segurança: garantir que está dentro do volume
    try:
        full_path = full_path.resolve()
        docs_resolved = docs_path.resolve()
        if not str(full_path).startswith(str(docs_resolved)):
            return False, None
    except (OSError, ValueError):
        return False, None

    return full_path.exists() and full_path.is_file(), full_path
