"""
Script facilitador para processamento rápido de planilhas ZPP
Processa automaticamente a pasta zpp_input/

Uso:
    python process_zpp_quick.py

Autor: Claude Code
Data: 2026-01-28
"""

import subprocess
import sys
from pathlib import Path

# Configuração
INPUT_DIR = "zpp_input"
SCRIPT = "process_zpp_to_mongo.py"

def main():
    print("\n" + "="*80)
    print("PROCESSAMENTO RÁPIDO ZPP")
    print("="*80)

    # Verificar se diretório de entrada existe
    input_path = Path(INPUT_DIR)
    if not input_path.exists():
        print(f"\n[!] Pasta '{INPUT_DIR}' nao encontrada!")
        print(f"[!] Criando pasta...")
        input_path.mkdir(exist_ok=True)
        print(f"[OK] Pasta criada: {input_path.absolute()}")
        print(f"\n[!] Coloque os arquivos Excel na pasta '{INPUT_DIR}' e execute novamente.")
        return

    # Verificar se há arquivos Excel (glob case-insensitive no Windows)
    all_files = list(input_path.glob("*.[xX][lL][sS][xX]")) + list(input_path.glob("*.[xX][lL][sS]"))
    # Remover duplicatas e filtrar arquivos temporários
    seen = set()
    excel_files = []
    for f in all_files:
        if f.name.lower() not in seen and not f.name.startswith('~$') and '_cleaned' not in f.name.lower():
            seen.add(f.name.lower())
            excel_files.append(f)

    if not excel_files:
        print(f"\n[!] Nenhum arquivo Excel encontrado em '{INPUT_DIR}'")
        print(f"\n[!] Coloque os arquivos Excel (.xlsx) na pasta e execute novamente.")
        return

    print(f"\nPasta de entrada: {input_path.absolute()}")
    print(f"Arquivos encontrados: {len(excel_files)}")
    for f in excel_files:
        print(f"   - {f.name}")

    print(f"\nIniciando processamento...\n")

    # Executar script principal
    cmd = [sys.executable, SCRIPT, INPUT_DIR]
    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("\n" + "="*80)
        print("[OK] PROCESSAMENTO CONCLUIDO COM SUCESSO!")
        print("="*80)
        print(f"\nArquivos processados foram movidos para: {INPUT_DIR}/analisados/")
        print(f"Dados carregados no MongoDB")
    else:
        print("\n" + "="*80)
        print("❌ ERRO NO PROCESSAMENTO")
        print("="*80)
        print(f"\nVerifique os logs acima para detalhes do erro.")

if __name__ == "__main__":
    main()
