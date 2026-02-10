# -*- coding: utf-8 -*-
"""Teste de detecção de tipo ZPP"""
import pandas as pd
from clean_zpp_data import detect_file_type

file_path = 'zpp_input/ZPPZNT001_.XLSX'

print(f"Testando deteccao para: {file_path}")
print("=" * 80)

# Ler colunas
df = pd.read_excel(file_path, nrows=0)
print(f"\nColunas encontradas ({len(df.columns)}):")
for i, col in enumerate(df.columns, 1):
    print(f"  {i:2}. {repr(col)}")

# Tentar detectar tipo
print("\n" + "=" * 80)
print("EXECUTANDO DETECCAO...")
print("=" * 80)

file_type = detect_file_type(file_path)

print(f"\nRESULTADO: {file_type if file_type else 'NAO DETECTADO'}")

if not file_type:
    print("\nPROBLEMA: Arquivo nao foi reconhecido!")
    print("Precisamos atualizar as assinaturas no arquivo clean_zpp_data.py")
