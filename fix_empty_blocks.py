"""
Script para corrigir blocos if/else/try/except vazios
"""
import re
import os
import sys

# Forcar UTF-8 no Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def fix_empty_blocks(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    fixed_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        fixed_lines.append(line)

        # Verificar se é um bloco que precisa de corpo
        stripped = line.strip()
        if stripped.endswith(':') and (
            stripped.startswith('if ') or
            stripped.startswith('elif ') or
            stripped.startswith('else:') or
            stripped.startswith('try:') or
            stripped.startswith('except') or
            stripped.startswith('finally:') or
            stripped.startswith('for ') or
            stripped.startswith('while ')
        ):
            # Verificar se a próxima linha está no mesmo nível de indentação ou menor
            if i + 1 < len(lines):
                current_indent = len(line) - len(line.lstrip())
                next_line = lines[i + 1]
                next_indent = len(next_line) - len(next_line.lstrip())

                # Se próxima linha tem mesma ou menor indentação, adicionar pass
                if next_indent <= current_indent and next_line.strip():
                    fixed_lines.append(' ' * (current_indent + 4) + 'pass\n')

        i += 1

    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)

# Arquivos com problemas identificados
files_to_fix = [
    'webapp/src/callbacks.py',
    'webapp/src/callbacks_registers/maintenance_kpi_callbacks.py',
    'webapp/src/database/connection.py',
    'webapp/src/utils/maintenance_demo_data.py'
]

for file_path in files_to_fix:
    if os.path.exists(file_path):
        print(f"Fixing {file_path}...")
        fix_empty_blocks(file_path)
        print(f"  OK Done")
    else:
        print(f"  ERROR File not found: {file_path}")

print("\nAll files fixed!")
