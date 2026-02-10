"""
Script de diagnóstico para verificar formato das planilhas ZPP
"""
import pandas as pd
from pathlib import Path

# Ler arquivo
file_path = Path('zpp_input/ZPPZNT001_.XLSX')
print(f"Analisando: {file_path.name}\n")
print("="*80)

# Carregar apenas colunas (sem dados)
df = pd.read_excel(file_path, nrows=0)
cols_found = set(df.columns)

print(f"COLUNAS ENCONTRADAS ({len(cols_found)} colunas):")
print("="*80)
for i, col in enumerate(df.columns, 1):
    print(f"{i:2}. '{col}'")

print("\n" + "="*80)
print("VERIFICAÇÃO DE ASSINATURAS")
print("="*80)

# Assinatura ANTIGA para zppparadas
signature_old = {
    'Centro de trabalho',
    'Início execução',
    'Fim execução',
    'Causa do desvio',
    'Duration (min)'
}

print("\n[1] Assinatura ANTIGA (zppparadas):")
for col in signature_old:
    exists = col in cols_found
    status = "✓ EXISTE" if exists else "✗ FALTA"
    print(f"  {status}: '{col}'")

matching_old = signature_old & cols_found
match_ratio_old = len(matching_old) / len(signature_old) * 100
print(f"\n  Match: {len(matching_old)}/{len(signature_old)} ({match_ratio_old:.0f}%)")
print(f"  Threshold: 80%")
print(f"  Status: {'✓ DETECTADO' if match_ratio_old >= 80 else '✗ NÃO DETECTADO'}")

# Assinatura ANTIGA para zppprd
signature_prd = {
    'Pto.Trab.',
    'Kg.Proc.',
    'HorasAct.',
    'FIniNotif',
    'FFinNotif'
}

print("\n[2] Assinatura ANTIGA (zppprd):")
for col in signature_prd:
    exists = col in cols_found
    status = "✓ EXISTE" if exists else "✗ FALTA"
    print(f"  {status}: '{col}'")

matching_prd = signature_prd & cols_found
match_ratio_prd = len(matching_prd) / len(signature_prd) * 100
print(f"\n  Match: {len(matching_prd)}/{len(signature_prd)} ({match_ratio_prd:.0f}%)")
print(f"  Threshold: 80%")
print(f"  Status: {'✓ DETECTADO' if match_ratio_prd >= 80 else '✗ NÃO DETECTADO'}")

print("\n" + "="*80)
print("CONCLUSÃO")
print("="*80)

if match_ratio_old >= 80:
    print("✓ Arquivo seria detectado como: ZPPPARADAS")
elif match_ratio_prd >= 80:
    print("✓ Arquivo seria detectado como: ZPPPRD")
else:
    print("✗ Arquivo NÃO seria detectado (nenhuma assinatura corresponde)")
    print("\nNOVA ASSINATURA SUGERIDA:")
    print("  Baseado nas colunas encontradas, sugestão:")
    print("  {")
    for col in list(cols_found)[:5]:
        print(f"    '{col}',")
    print("  }")

print("\n" + "="*80)
