"""
Script para remover referências ao Google Fonts dos temas Bootstrap baixados.
Isso garante que a aplicação funcione completamente offline sem tentar
carregar recursos externos.
"""

import re
from pathlib import Path


def remove_google_fonts_import(css_file_path):
    """
    Remove a linha @import do Google Fonts do arquivo CSS.

    Args:
        css_file_path: Path para o arquivo CSS

    Returns:
        bool: True se alterações foram feitas, False caso contrário
    """
    print(f"Processando: {css_file_path}")

    # Ler conteúdo do arquivo
    content = css_file_path.read_text(encoding='utf-8')
    original_content = content

    # Padrão para encontrar imports do Google Fonts
    # Exemplo: @import url(https://fonts.googleapis.com/css2?family=Lato:ital,wght@0,400;0,700;1,400&display=swap);
    google_fonts_pattern = r'@import\s+url\(https?://fonts\.googleapis\.com/[^)]+\);?'

    # Remover o import
    content = re.sub(google_fonts_pattern, '', content)

    # Verificar se houve mudanças
    if content != original_content:
        # Salvar arquivo modificado
        css_file_path.write_text(content, encoding='utf-8')
        print(f"  [OK] Removida referência ao Google Fonts")
        return True
    else:
        print(f"  [INFO] Nenhuma referência ao Google Fonts encontrada")
        return False


def main():
    """Função principal - processa todos os temas Bootstrap."""
    print("=" * 70)
    print("Correção de Referências ao Google Fonts - Modo Offline")
    print("=" * 70)
    print()

    # Caminho base dos temas
    base_path = Path(__file__).parent.parent / 'src' / 'assets' / 'vendor' / 'bootstrap'

    # Lista de temas para processar
    themes = ['minty', 'darkly']

    processed = 0
    modified = 0

    for theme in themes:
        css_file = base_path / theme / 'bootstrap.min.css'

        if not css_file.exists():
            print(f"[AVISO] Arquivo não encontrado: {css_file}")
            continue

        processed += 1
        if remove_google_fonts_import(css_file):
            modified += 1
        print()

    # Resumo
    print("=" * 70)
    print("RESUMO")
    print("=" * 70)
    print(f"Arquivos processados: {processed}/{len(themes)}")
    print(f"Arquivos modificados: {modified}")

    if modified > 0:
        print("\n>>> Correção aplicada com sucesso!")
        print("\nPróximos passos:")
        print("1. Reinicie a aplicação")
        print("2. Teste o switch de temas (claro/escuro)")
        print("3. Verifique se todos os componentes estão com tema correto")
    else:
        print("\n>>> Nenhuma modificação necessária")

    return 0


if __name__ == '__main__':
    exit(main())
