"""Script para atualizar CSVs de workflow com novos campos."""
import pandas as pd
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent / "src" / "data"
PENDENCIAS_CSV = BASE_DIR / "workflow_pendencias.csv"
HISTORICO_CSV = BASE_DIR / "workflow_historico.csv"


def atualizar_pendencias():
    """Adiciona colunas criado_por, criado_por_perfil, ultima_edicao_por, ultima_edicao_data."""
    if not PENDENCIAS_CSV.exists():
        print(f"[ERRO] Arquivo {PENDENCIAS_CSV} nao encontrado")
        return

    df = pd.read_csv(PENDENCIAS_CSV)
    print(f"[INFO] Lendo {len(df)} pendencias de {PENDENCIAS_CSV}")

    # Adicionar colunas se não existirem
    colunas_adicionadas = []

    if 'criado_por' not in df.columns:
        df['criado_por'] = 'admin.sistema'
        colunas_adicionadas.append('criado_por')

    if 'criado_por_perfil' not in df.columns:
        df['criado_por_perfil'] = 'admin'
        colunas_adicionadas.append('criado_por_perfil')

    if 'ultima_edicao_por' not in df.columns:
        df['ultima_edicao_por'] = 'admin.sistema'
        colunas_adicionadas.append('ultima_edicao_por')

    if 'ultima_edicao_data' not in df.columns:
        df['ultima_edicao_data'] = df['ultima_atualizacao']
        colunas_adicionadas.append('ultima_edicao_data')

    if colunas_adicionadas:
        df.to_csv(PENDENCIAS_CSV, index=False)
        print(f"[OK] {PENDENCIAS_CSV.name} atualizado com {len(df)} registros")
        print(f"  Colunas adicionadas: {', '.join(colunas_adicionadas)}")
    else:
        print(f"[OK] {PENDENCIAS_CSV.name} ja possui todas as colunas necessarias")


def atualizar_historico():
    """Adiciona colunas tipo_evento, editado_por."""
    if not HISTORICO_CSV.exists():
        print(f"[ERRO] Arquivo {HISTORICO_CSV} nao encontrado")
        return

    df = pd.read_csv(HISTORICO_CSV)
    print(f"\n[INFO] Lendo {len(df)} entradas de historico de {HISTORICO_CSV}")

    # Adicionar colunas se não existirem
    colunas_adicionadas = []

    if 'tipo_evento' not in df.columns:
        df['tipo_evento'] = 'atualizacao_manual'
        colunas_adicionadas.append('tipo_evento')

    if 'editado_por' not in df.columns:
        df['editado_por'] = df['responsavel']
        colunas_adicionadas.append('editado_por')

    if colunas_adicionadas:
        df.to_csv(HISTORICO_CSV, index=False)
        print(f"[OK] {HISTORICO_CSV.name} atualizado com {len(df)} registros")
        print(f"  Colunas adicionadas: {', '.join(colunas_adicionadas)}")
    else:
        print(f"[OK] {HISTORICO_CSV.name} ja possui todas as colunas necessarias")


if __name__ == '__main__':
    print("=" * 60)
    print("Atualizando CSVs de workflow com novos campos...")
    print("=" * 60)

    atualizar_pendencias()
    atualizar_historico()

    print("\n" + "=" * 60)
    print("[OK] Atualizacao concluida com sucesso!")
    print("=" * 60)
