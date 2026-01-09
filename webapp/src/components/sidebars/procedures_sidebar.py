# src/components/sidebars/procedures_sidebar.py

"""
Sidebar de navegação para procedimentos de manutenção.
Exibe uma árvore de navegação hierárquica baseada no docs.yml.
Suporta múltiplos níveis de aninhamento.
"""

from dash import html, dcc
import dash_bootstrap_components as dbc

from src.config.docs_config import load_docs_structure


def create_nav_link(file_info, current_path, depth=0):
    """
    Cria um link de navegação para um arquivo.

    Args:
        file_info (dict): Informações do arquivo (path, title)
        current_path (str): Caminho atual da página
        depth (int): Nível de profundidade para indentação

    Returns:
        dcc.Link: Componente de link com navegação SPA
    """
    # Construir URL completa
    file_path = file_info.get("path", "")
    if not file_path.startswith("/maintenance/"):
        url = f"/maintenance/{file_path}"
    else:
        url = file_path

    is_active = current_path == url

    # Calcular padding baseado na profundidade
    padding_left = 10 + (depth * 12)

    # Criar estilo com padding se necessário
    link_style = {"paddingLeft": f"{padding_left}px"} if depth > 0 else {}

    return dcc.Link(
        [
            html.I(
                className="bi bi-file-text me-2",
                style={"fontSize": "0.7rem", "opacity": "0.7"}
            ),
            html.Span(file_info.get("title", file_path))
        ],
        href=url,
        className=f"proc-nav-link {'active' if is_active else ''}",
        style=link_style
    )


def _is_section_active(section, current_path):
    """
    Verifica recursivamente se uma seção contém o documento atual.

    Args:
        section (dict): Dados da seção
        current_path (str): Caminho atual

    Returns:
        bool: True se a seção ou subseções contêm o documento atual
    """
    # Verificar arquivos da seção
    for file_info in section.get("files", []):
        file_path = file_info.get("path", "")
        url = f"/maintenance/{file_path}" if not file_path.startswith("/maintenance/") else file_path
        if current_path == url:
            return True

    # Verificar subseções recursivamente
    for subsection in section.get("sections", []):
        if _is_section_active(subsection, current_path):
            return True

    return False


def create_section(section_data, current_path, depth=0, parent_id=""):
    """
    Cria uma seção colapsável recursivamente.
    Suporta múltiplos níveis de aninhamento.

    Args:
        section_data (dict): Dados da seção do docs.yml
        current_path (str): Caminho atual da página
        depth (int): Nível de profundidade
        parent_id (str): ID do pai para criar IDs únicos

    Returns:
        html.Div: Componente da seção
    """
    section_name = section_data.get("name", f"section-{depth}")
    section_id = f"{parent_id}-{section_name}" if parent_id else section_name

    # Verificar se a seção está ativa (contém documento atual)
    has_active = _is_section_active(section_data, current_path)

    # Estado inicial: expandido se tem item ativo ou se definido no yml
    is_expanded = has_active or section_data.get("expanded", False)

    # Estilo do chevron baseado no estado
    chevron_style = {
        "fontSize": "0.65rem",
        "transition": "transform 0.2s ease",
        "transform": "rotate(0deg)" if is_expanded else "rotate(-90deg)"
    }

    # Calcular indentação
    margin_left = depth * 8

    # Criar conteúdo da seção
    content_items = []

    # Adicionar arquivos da seção
    for file_info in section_data.get("files", []):
        content_items.append(create_nav_link(file_info, current_path, depth + 1))

    # Adicionar subseções recursivamente
    for subsection in section_data.get("sections", []):
        content_items.append(
            create_section(subsection, current_path, depth + 1, section_id)
        )

    return html.Div([
        # Header clicável
        html.Div(
            [
                html.I(
                    className=f"bi {section_data.get('icon', 'bi-folder')} me-2",
                    style={"fontSize": "0.75rem"}
                ),
                html.Span(section_data.get("label", section_name), className="flex-grow-1"),
                html.I(
                    id={"type": "proc-chevron", "folder": section_id},
                    className="bi bi-chevron-down proc-chevron",
                    style=chevron_style
                ),
            ],
            id={"type": "proc-toggle", "folder": section_id},
            className=f"proc-folder-header {'has-active' if has_active else ''}",
            n_clicks=0,
        ),
        # Conteúdo colapsável
        dbc.Collapse(
            html.Div(content_items, className="proc-folder-content"),
            id={"type": "proc-collapse", "folder": section_id},
            is_open=is_expanded,
        ),
    ], className="proc-folder", style={"marginLeft": f"{margin_left}px"} if depth > 0 else None)


def create_procedures_sidebar_content(current_path="/maintenance/index.md"):
    """
    Cria o conteúdo da sidebar para páginas de procedimentos.
    Carrega estrutura do docs.yml ou usa fallback de scan automático.

    Args:
        current_path (str): Caminho atual da página

    Returns:
        html.Div: Componente com a navegação hierárquica
    """
    # Carregar estrutura de documentação
    structure = load_docs_structure()

    nav_items = []

    # Título da navegação
    nav_items.append(
        html.Div([
            html.I(className=f"bi {structure.get('icon', 'bi-book')} me-2"),
            html.Span(structure.get("title", "Procedimentos"))
        ], className="proc-nav-title")
    )

    # Link para índice principal (se existir)
    if structure.get("index"):
        index_url = f"/maintenance/{structure['index']}"
        is_active = current_path == index_url
        nav_items.append(
            dcc.Link(
                [
                    html.I(className="bi bi-house-door me-2", style={"fontSize": "0.75rem"}),
                    html.Span("Início")
                ],
                href=index_url,
                className=f"proc-nav-link proc-home {'active' if is_active else ''}",
            )
        )

    # Separador
    nav_items.append(html.Hr(className="my-2", style={"opacity": "0.2"}))

    # Renderizar seções
    for section in structure.get("sections", []):
        nav_items.append(create_section(section, current_path, depth=0))

    # Mensagem se não houver documentos
    if not structure.get("index") and not structure.get("sections"):
        nav_items.append(
            html.Div([
                html.I(className="bi bi-info-circle me-2 text-muted"),
                html.Span("Nenhum documento configurado", className="text-muted")
            ], className="proc-empty")
        )

    return html.Div(
        nav_items,
        id="procedures-sidebar-content",
        className="proc-nav",
    )
