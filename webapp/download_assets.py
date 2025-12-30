# webapp/download_assets.py
"""
Script para baixar todos os recursos externos para uso offline.
"""

import os
import requests
from pathlib import Path

# Cria pasta assets se não existir
ASSETS_DIR = Path(__file__).parent / 'src' / 'assets'
ASSETS_DIR.mkdir(exist_ok=True)

print("📦 Baixando recursos para modo offline...\n")

# Lista de recursos para baixar
resources = {
    # Bootstrap Minty Theme
    'bootstrap.min.css': 'https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/minty/bootstrap.min.css',
    
    # Bootstrap Darkly Theme (tema escuro)
    'bootstrap-dark.min.css': 'https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/darkly/bootstrap.min.css',
    
    # Font Awesome
    'fontawesome.min.css': 'https://use.fontawesome.com/releases/v5.10.2/css/all.css',
    'fa-solid-900.woff2': 'https://use.fontawesome.com/releases/v5.10.2/webfonts/fa-solid-900.woff2',
    'fa-regular-400.woff2': 'https://use.fontawesome.com/releases/v5.10.2/webfonts/fa-regular-400.woff2',
    'fa-brands-400.woff2': 'https://use.fontawesome.com/releases/v5.10.2/webfonts/fa-brands-400.woff2',
}

def download_file(url, filename):
    """Baixa um arquivo da URL e salva localmente."""
    try:
        print(f"⬇️  Baixando {filename}...")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        filepath = ASSETS_DIR / filename
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        print(f"✅ {filename} salvo com sucesso!")
        return True
    except Exception as e:
        print(f"❌ Erro ao baixar {filename}: {e}")
        return False

# Baixa todos os recursos
success_count = 0
for filename, url in resources.items():
    if download_file(url, filename):
        success_count += 1

print(f"\n🎉 Download concluído! {success_count}/{len(resources)} arquivos baixados.")
print(f"📁 Arquivos salvos em: {ASSETS_DIR}")