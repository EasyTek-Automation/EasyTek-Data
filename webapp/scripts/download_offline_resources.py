"""
Script para baixar recursos externos e tornar a aplicação AMG_Data completamente offline.

Baixa:
- Bootstrap Minty e Darkly (temas Bootswatch 5.3.6)
- Font Awesome 5.10.2 (CSS + webfonts)
- Bootstrap Icons 1.11.3 (CSS + webfonts)

Ajusta URLs dentro do CSS para caminhos locais.
"""

import requests
import re
from pathlib import Path


# Mapeamento de recursos para baixar
RESOURCES = {
    'bootstrap_minty': {
        'url': 'https://cdn.jsdelivr.net/npm/bootswatch@5.3.6/dist/minty/bootstrap.min.css',
        'path': 'assets/vendor/bootstrap/minty/bootstrap.min.css'
    },
    'bootstrap_darkly': {
        'url': 'https://cdn.jsdelivr.net/npm/bootswatch@5.3.6/dist/darkly/bootstrap.min.css',
        'path': 'assets/vendor/bootstrap/darkly/bootstrap.min.css'
    },
    'fontawesome_css': {
        'url': 'https://use.fontawesome.com/releases/v5.10.2/css/all.css',
        'path': 'assets/vendor/fontawesome/css/all.min.css'
    },
    'fontawesome_brands': {
        'url': 'https://use.fontawesome.com/releases/v5.10.2/webfonts/fa-brands-400.woff2',
        'path': 'assets/vendor/fontawesome/webfonts/fa-brands-400.woff2'
    },
    'fontawesome_regular': {
        'url': 'https://use.fontawesome.com/releases/v5.10.2/webfonts/fa-regular-400.woff2',
        'path': 'assets/vendor/fontawesome/webfonts/fa-regular-400.woff2'
    },
    'fontawesome_solid': {
        'url': 'https://use.fontawesome.com/releases/v5.10.2/webfonts/fa-solid-900.woff2',
        'path': 'assets/vendor/fontawesome/webfonts/fa-solid-900.woff2'
    },
    'bootstrap_icons_css': {
        'url': 'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css',
        'path': 'assets/vendor/bootstrap-icons/font/bootstrap-icons.min.css'
    },
    'bootstrap_icons_font': {
        'url': 'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/fonts/bootstrap-icons.woff2',
        'path': 'assets/vendor/bootstrap-icons/font/fonts/bootstrap-icons.woff2'
    }
}


def download_resource(name, config):
    """
    Baixa um recurso e salva no caminho especificado.

    Args:
        name: Nome do recurso (para logging)
        config: Dicionário com 'url' e 'path'

    Returns:
        bool: True se sucesso, False se falhou
    """
    base_path = Path(__file__).parent.parent / 'src'
    file_path = base_path / config['path']

    # Criar diretórios se não existirem
    file_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Baixando {name}...")
    print(f"  URL: {config['url']}")
    print(f"  Destino: {file_path}")

    try:
        # Download do recurso
        response = requests.get(config['url'], timeout=30)
        response.raise_for_status()

        content = response.content

        # Para arquivos CSS, ajustar caminhos de webfonts
        if config['path'].endswith('.css'):
            content_str = content.decode('utf-8')
            original_size = len(content_str)

            # Ajustar URLs do Font Awesome
            # De: https://use.fontawesome.com/releases/v5.10.2/webfonts/
            # Para: ../webfonts/
            content_str = re.sub(
                r'https://use\.fontawesome\.com/releases/v[0-9.]+/webfonts/',
                '../webfonts/',
                content_str
            )

            # Também ajustar URLs com .. (alguns CSS podem ter isso)
            content_str = re.sub(
                r'\.\./webfonts/fa-',
                '../webfonts/fa-',
                content_str
            )

            # Ajustar URLs do Bootstrap Icons
            # De: ./fonts/bootstrap-icons.woff2
            # Para: ./fonts/bootstrap-icons.woff2 (já está correto, mas garantir)
            # De: ../fonts/bootstrap-icons.woff2
            # Para: ./fonts/bootstrap-icons.woff2
            content_str = re.sub(
                r'\.\./fonts/bootstrap-icons',
                './fonts/bootstrap-icons',
                content_str
            )

            content = content_str.encode('utf-8')

            if original_size != len(content):
                print(f"  [OK] URLs ajustadas no CSS")

        # Salvar arquivo
        file_path.write_bytes(content)
        file_size_kb = len(content) / 1024
        print(f"  [OK] Salvo com sucesso ({file_size_kb:.1f} KB)\n")

        return True

    except requests.exceptions.RequestException as e:
        print(f"  [ERRO] Erro ao baixar: {e}\n")
        return False
    except Exception as e:
        print(f"  [ERRO] Erro ao processar: {e}\n")
        return False


def main():
    """Função principal - baixa todos os recursos."""
    print("=" * 70)
    print("Download de Recursos Offline para AMG_Data")
    print("=" * 70)
    print()

    success_count = 0
    failed_count = 0

    for name, config in RESOURCES.items():
        if download_resource(name, config):
            success_count += 1
        else:
            failed_count += 1

    # Resumo
    print("=" * 70)
    print("RESUMO")
    print("=" * 70)
    print(f"[OK] Downloads bem-sucedidos: {success_count}/{len(RESOURCES)}")
    if failed_count > 0:
        print(f"[ERRO] Downloads com falha: {failed_count}/{len(RESOURCES)}")
        print("\nALGUNS RECURSOS NAO FORAM BAIXADOS!")
        print("Verifique sua conexao de internet e tente novamente.")
        return 1
    else:
        print("\n>>> Todos os recursos foram baixados com sucesso!")
        print("\nProximos passos:")
        print("1. Verifique os arquivos em: webapp/src/assets/vendor/")
        print("2. Modifique app.py e theme_config.py conforme o plano")
        print("3. Execute: python scripts/validate_offline.py")
        return 0


if __name__ == '__main__':
    exit(main())
