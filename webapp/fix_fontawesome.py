# webapp/fix_fontawesome.py
"""
Corrige as referências de fonte no arquivo Font Awesome para usar os arquivos locais.
"""

from pathlib import Path

ASSETS_DIR = Path(__file__).parent / 'src' / 'assets'
FA_CSS = ASSETS_DIR / 'fontawesome.min.css'

print("🔧 Corrigindo Font Awesome CSS...")

if not FA_CSS.exists():
    print(f"❌ Arquivo não encontrado: {FA_CSS}")
    exit(1)

# Lê o conteúdo
content = FA_CSS.read_text(encoding='utf-8')

# Substitui TODAS as referências de ../webfonts/ para /assets/
content = content.replace('url(../webfonts/', 'url(/assets/')

# Salva o arquivo corrigido
FA_CSS.write_text(content, encoding='utf-8')

print(f"✅ Font Awesome corrigido!")
print(f"📁 Arquivo: {FA_CSS}")

# Verifica se a correção funcionou
if '/assets/fa-solid-900' in content:
    print("✅ Referências atualizadas com sucesso!")
else:
    print("⚠️ Algo pode ter dado errado na correção")