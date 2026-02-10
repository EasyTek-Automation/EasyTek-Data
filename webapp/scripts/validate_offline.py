"""
Script de validação para garantir que a aplicação AMG_Data está
completamente offline (sem dependências externas).

Verifica:
1. Presença de todos os recursos locais baixados
2. Ausência de referências a URLs externas no código
3. Configuração correta de external_stylesheets
"""

import re
from pathlib import Path
import sys


# Recursos que devem existir localmente
REQUIRED_FILES = [
    'src/assets/vendor/bootstrap/minty/bootstrap.min.css',
    'src/assets/vendor/bootstrap/darkly/bootstrap.min.css',
    'src/assets/vendor/fontawesome/css/all.min.css',
    'src/assets/vendor/fontawesome/webfonts/fa-brands-400.woff2',
    'src/assets/vendor/fontawesome/webfonts/fa-regular-400.woff2',
    'src/assets/vendor/fontawesome/webfonts/fa-solid-900.woff2',
    'src/assets/vendor/bootstrap-icons/font/bootstrap-icons.min.css',
    'src/assets/vendor/bootstrap-icons/font/fonts/bootstrap-icons.woff2',
]

# URLs que NÃO devem estar no código (CDNs)
FORBIDDEN_URLS = [
    r'https://use\.fontawesome\.com',
    r'https://cdn\.jsdelivr\.net',
    r'dbc\.themes\.MINTY',
    r'dbc\.themes\.DARKLY',
    r'dbc\.themes\.BOOTSTRAP',
]

# Arquivos a escanear (padrões glob)
FILES_TO_SCAN = [
    'src/app.py',
    'src/config/theme_config.py',
    'src/header.py',
]


def check_local_resources():
    """Verifica se todos os recursos locais existem."""
    print("=" * 70)
    print("1. VERIFICANDO RECURSOS LOCAIS")
    print("=" * 70)

    base_path = Path(__file__).parent.parent
    missing_files = []

    for file_rel in REQUIRED_FILES:
        file_path = base_path / file_rel
        if not file_path.exists():
            missing_files.append(file_rel)
            print(f"  [FALTA] {file_rel}")
        else:
            file_size = file_path.stat().st_size / 1024
            print(f"  [OK] {file_rel} ({file_size:.1f} KB)")

    print()
    if missing_files:
        print(f"[ERRO] {len(missing_files)} arquivo(s) faltando!")
        print("Execute: python scripts/download_offline_resources.py")
        return False
    else:
        print(f"[OK] Todos os {len(REQUIRED_FILES)} recursos locais presentes")
        return True


def scan_for_external_urls():
    """Escaneia código em busca de URLs externas proibidas."""
    print("\n" + "=" * 70)
    print("2. ESCANEANDO CODIGO POR URLs EXTERNAS")
    print("=" * 70)

    base_path = Path(__file__).parent.parent
    issues = []

    for file_pattern in FILES_TO_SCAN:
        file_path = base_path / file_pattern

        if not file_path.exists():
            print(f"  [AVISO] Arquivo nao encontrado: {file_pattern}")
            continue

        content = file_path.read_text(encoding='utf-8')
        file_issues = []

        for pattern in FORBIDDEN_URLS:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                # Encontrar número da linha
                line_num = content[:match.start()].count('\n') + 1
                file_issues.append((line_num, match.group(0)))

        if file_issues:
            print(f"\n  [AVISO] {file_pattern}:")
            for line_num, url in file_issues:
                print(f"    Linha {line_num}: {url}")
            issues.extend([(file_pattern, line_num, url) for line_num, url in file_issues])
        else:
            print(f"  [OK] {file_pattern}")

    print()
    if issues:
        print(f"[AVISO] {len(issues)} referencia(s) externa(s) encontrada(s)")
        print("Isso pode indicar que algumas mudancas nao foram aplicadas.")
        return False
    else:
        print("[OK] Nenhuma referencia a CDNs encontrada nos arquivos principais")
        return True


def check_configuration():
    """Verifica configuração do app.py."""
    print("\n" + "=" * 70)
    print("3. VERIFICANDO CONFIGURACAO")
    print("=" * 70)

    base_path = Path(__file__).parent.parent
    app_path = base_path / 'src' / 'app.py'

    if not app_path.exists():
        print("[ERRO] app.py nao encontrado")
        return False

    content = app_path.read_text(encoding='utf-8')

    checks = [
        ('Font Awesome local', r'/assets/vendor/fontawesome/css/all\.min\.css'),
        ('Bootstrap Minty local', r'/assets/vendor/bootstrap/minty/bootstrap\.min\.css'),
        ('Bootstrap Icons local', r'/assets/vendor/bootstrap-icons/font/bootstrap-icons\.min\.css'),
    ]

    all_good = True
    for name, pattern in checks:
        if re.search(pattern, content):
            print(f"  [OK] {name} configurado")
        else:
            print(f"  [ERRO] {name} NAO encontrado")
            all_good = False

    print()
    if all_good:
        print("[OK] Configuracao correta em app.py")
    else:
        print("[ERRO] Configuracao incorreta - verifique app.py")

    return all_good


def check_theme_config():
    """Verifica theme_config.py."""
    print("\n" + "=" * 70)
    print("4. VERIFICANDO THEME_CONFIG.PY")
    print("=" * 70)

    base_path = Path(__file__).parent.parent
    theme_path = base_path / 'src' / 'config' / 'theme_config.py'

    if not theme_path.exists():
        print("[ERRO] theme_config.py nao encontrado")
        return False

    content = theme_path.read_text(encoding='utf-8')

    checks = [
        ('URL_THEME_MINTY local', r"URL_THEME_MINTY\s*=\s*['\"]\/assets\/vendor\/bootstrap\/minty\/bootstrap\.min\.css['\"]"),
        ('URL_THEME_DARKLY local', r"URL_THEME_DARKLY\s*=\s*['\"]\/assets\/vendor\/bootstrap\/darkly\/bootstrap\.min\.css['\"]"),
    ]

    all_good = True
    for name, pattern in checks:
        if re.search(pattern, content):
            print(f"  [OK] {name} configurado")
        else:
            print(f"  [ERRO] {name} NAO encontrado")
            all_good = False

    print()
    if all_good:
        print("[OK] Temas locais configurados corretamente")
    else:
        print("[ERRO] theme_config.py nao esta configurado corretamente")

    return all_good


def main():
    """Função principal."""
    print("\n")
    print("#" * 70)
    print("# VALIDACAO DE MODO OFFLINE - AMG_Data")
    print("#" * 70)
    print()

    results = {
        'recursos_locais': check_local_resources(),
        'urls_externas': scan_for_external_urls(),
        'configuracao_app': check_configuration(),
        'configuracao_theme': check_theme_config(),
    }

    # Resumo final
    print("\n" + "=" * 70)
    print("RESUMO FINAL")
    print("=" * 70)

    all_passed = all(results.values())

    for check, passed in results.items():
        status = "[OK]" if passed else "[ERRO]"
        print(f"{status} {check.replace('_', ' ').title()}")

    print()
    if all_passed:
        print(">>> SUCESSO! Aplicacao configurada para modo offline completo.")
        print("\nProximos passos:")
        print("1. Iniciar aplicacao: python webapp/src/run.py")
        print("2. Verificar DevTools > Network (nenhuma requisicao externa)")
        print("3. Testar troca de temas (claro/escuro)")
        print("4. Teste offline: desconectar Wi-Fi e navegar pela app")
        return 0
    else:
        print(">>> FALHA! Alguns problemas foram encontrados.")
        print("Revise os erros acima e corrija antes de prosseguir.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
