# src/pages/maintenance/procedures.py

"""Renderizador de documentação Markdown para procedimentos"""

import re
from dash import html, dcc
import dash_bootstrap_components as dbc
from pathlib import Path

from src.config.docs_config import get_docs_path


def process_markdown_paths(md_content, file_path):
    """
    Processa o conteúdo markdown para converter caminhos relativos de imagens
    em caminhos absolutos usando a rota /docs-assets/.

    Args:
        md_content (str): Conteúdo markdown original
        file_path (Path): Caminho do arquivo markdown

    Returns:
        str: Conteúdo markdown com caminhos corrigidos
    """
    docs_base = get_docs_path()
    file_dir = Path(file_path).parent

    def replace_image_path(match):
        alt_text = match.group(1)
        relative_path = match.group(2)

        # Ignorar URLs externas (http://, https://, //)
        if relative_path.startswith(('http://', 'https://', '//')):
            return match.group(0)

        # Ignorar caminhos já absolutos (/docs-assets/)
        if relative_path.startswith('/docs-assets/'):
            return match.group(0)

        # Resolver caminho relativo para absoluto
        try:
            # Calcular caminho absoluto baseado na localização do arquivo
            absolute_path = (file_dir / relative_path).resolve()

            # Calcular caminho relativo ao docs_base
            relative_to_docs = absolute_path.relative_to(docs_base.resolve())

            # Converter para URL da rota
            url_path = f"/docs-assets/{relative_to_docs.as_posix()}"

            return f"![{alt_text}]({url_path})"
        except (ValueError, OSError):
            # Se não conseguir resolver, manter original
            return match.group(0)

    # Regex para encontrar imagens em markdown: ![alt](path)
    pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    processed_content = re.sub(pattern, replace_image_path, md_content)

    return processed_content


def render_markdown_file(filepath):
    """Renderiza arquivo markdown para HTML usando dcc.Markdown"""
    try:
        filepath = Path(filepath)
        if not filepath.exists():
            return dbc.Alert(f"Documento não encontrado: {filepath.name}", color="warning")

        with open(filepath, 'r', encoding='utf-8') as f:
            md_content = f.read()

        # Processar caminhos de imagens
        md_content = process_markdown_paths(md_content, filepath)

        return html.Div([
            dcc.Markdown(
                md_content,
                className="markdown-content",
                dangerously_allow_html=True,
                mathjax=True
            )
        ], className="p-4", style={"maxWidth": "1200px", "margin": "0 auto"})
    except Exception as e:
        return dbc.Alert([
            html.H4("Erro ao carregar documento", className="alert-heading"),
            html.P(str(e))
        ], color="danger")


def layout():
    """Layout da página de procedimentos"""
    # Carrega o documento index por padrão
    docs_path = get_docs_path()
    initial_doc = docs_path / "index.md"

    return html.Div([
        render_markdown_file(initial_doc)
    ], style={"height": "100%", "overflowY": "auto"})
