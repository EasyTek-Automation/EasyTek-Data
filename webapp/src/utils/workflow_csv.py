"""Funções para manipulação de CSVs de workflow."""
import os
import pandas as pd
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent / "data"
PENDENCIAS_CSV = BASE_DIR / "workflow_pendencias.csv"
HISTORICO_CSV = BASE_DIR / "workflow_historico.csv"


def carregar_pendencias():
    """Carrega pendências do CSV."""
    if not PENDENCIAS_CSV.exists():
        return pd.DataFrame(columns=[
            'id', 'descricao', 'responsavel', 'status', 'data_criacao',
            'ultima_atualizacao', 'criado_por', 'criado_por_perfil',
            'ultima_edicao_por', 'ultima_edicao_data'
        ])

    df = pd.read_csv(PENDENCIAS_CSV)
    df['data_criacao'] = pd.to_datetime(df['data_criacao'], format='mixed')
    df['ultima_atualizacao'] = pd.to_datetime(df['ultima_atualizacao'], format='mixed')
    if 'ultima_edicao_data' in df.columns:
        df['ultima_edicao_data'] = pd.to_datetime(df['ultima_edicao_data'], format='mixed')
    return df


def carregar_historico():
    """Carrega histórico do CSV."""
    if not HISTORICO_CSV.exists():
        return pd.DataFrame(columns=[
            'pendencia_id', 'descricao', 'data', 'responsavel',
            'tipo_evento', 'editado_por', 'observacoes'
        ])

    df = pd.read_csv(HISTORICO_CSV)
    df['data'] = pd.to_datetime(df['data'], format='mixed')
    return df


def gerar_proximo_id(df_pendencias):
    """
    Gera próximo ID sequencial (PEND-XXX).

    Args:
        df_pendencias: DataFrame de pendências

    Returns:
        str: Novo ID (ex: PEND-051)
    """
    if df_pendencias.empty:
        return "PEND-001"

    # Extrair números dos IDs existentes
    ids_numericos = df_pendencias['id'].str.extract(r'PEND-(\d+)')[0].astype(int)
    proximo_num = ids_numericos.max() + 1

    return f"PEND-{proximo_num:03d}"


def criar_pendencia(descricao, responsavel, status, criado_por, criado_por_perfil):
    """
    Cria nova pendência.

    Args:
        descricao: Texto da pendência
        responsavel: Username do responsável
        status: Status inicial
        criado_por: Username do criador
        criado_por_perfil: Perfil do criador

    Returns:
        tuple: (sucesso: bool, id_criado: str or mensagem_erro: str)
    """
    try:
        df_pend = carregar_pendencias()
        df_hist = carregar_historico()

        # Gerar ID
        novo_id = gerar_proximo_id(df_pend)
        agora = datetime.now()

        # Nova linha de pendência
        nova_pend = {
            'id': novo_id,
            'descricao': descricao,
            'responsavel': responsavel,
            'status': status,
            'data_criacao': agora,
            'ultima_atualizacao': agora,
            'criado_por': criado_por,
            'criado_por_perfil': criado_por_perfil,
            'ultima_edicao_por': criado_por,
            'ultima_edicao_data': agora
        }

        # Adicionar ao DataFrame
        df_pend = pd.concat([df_pend, pd.DataFrame([nova_pend])], ignore_index=True)
        df_pend.to_csv(PENDENCIAS_CSV, index=False)

        # Adicionar entrada no histórico
        nova_hist = {
            'pendencia_id': novo_id,
            'descricao': 'Início Workflow',
            'data': agora,
            'responsavel': responsavel,
            'tipo_evento': 'criacao',
            'editado_por': criado_por,
            'observacoes': f'Pendência criada e atribuída a {responsavel}'
        }

        df_hist = pd.concat([df_hist, pd.DataFrame([nova_hist])], ignore_index=True)
        df_hist.to_csv(HISTORICO_CSV, index=False)

        return True, novo_id

    except Exception as e:
        return False, str(e)


def editar_pendencia(pend_id, nova_descricao, novo_responsavel, novo_status,
                     descricao_original, responsavel_original, status_original,
                     editado_por, tipo_evento, observacoes):
    """
    Edita pendência existente e adiciona entrada no histórico.

    Args:
        pend_id: ID da pendência
        nova_descricao: Nova descrição (ou None se não mudou)
        novo_responsavel: Novo responsável (ou None se não mudou)
        novo_status: Novo status (ou None se não mudou)
        descricao_original: Descrição antes da edição
        responsavel_original: Responsável antes da edição
        status_original: Status antes da edição
        editado_por: Username de quem está editando
        tipo_evento: Tipo de evento (título do histórico) - OBRIGATÓRIO
        observacoes: Detalhes/observações da atualização - OBRIGATÓRIO

    Returns:
        tuple: (sucesso: bool, mensagem: str)
    """
    try:
        df_pend = carregar_pendencias()
        df_hist = carregar_historico()
        agora = datetime.now()

        # Encontrar pendência
        idx = df_pend[df_pend['id'] == pend_id].index
        if len(idx) == 0:
            return False, "Pendência não encontrada"

        idx = idx[0]
        houve_mudanca = False

        # Aplicar mudanças nos campos (se houver)
        if nova_descricao and nova_descricao != descricao_original:
            df_pend.at[idx, 'descricao'] = nova_descricao
            houve_mudanca = True

        if novo_responsavel and novo_responsavel != responsavel_original:
            df_pend.at[idx, 'responsavel'] = novo_responsavel
            houve_mudanca = True

        if novo_status and novo_status != status_original:
            df_pend.at[idx, 'status'] = novo_status
            houve_mudanca = True

        # Atualizar metadata
        df_pend.at[idx, 'ultima_atualizacao'] = agora
        df_pend.at[idx, 'ultima_edicao_por'] = editado_por
        df_pend.at[idx, 'ultima_edicao_data'] = agora

        # Salvar pendências
        df_pend.to_csv(PENDENCIAS_CSV, index=False)

        # SEMPRE adicionar entrada no histórico com tipo_evento e observações
        nova_entrada_historico = {
            'pendencia_id': pend_id,
            'descricao': tipo_evento,  # Título do evento (ex: "Primeira inspeção concluída")
            'data': agora,
            'responsavel': novo_responsavel or responsavel_original,
            'tipo_evento': 'atualizacao_workflow',
            'editado_por': editado_por,
            'observacoes': observacoes  # Detalhes da atualização
        }

        df_hist = pd.concat([df_hist, pd.DataFrame([nova_entrada_historico])], ignore_index=True)
        df_hist.to_csv(HISTORICO_CSV, index=False)

        msg_mudanca = " (com alterações nos campos)" if houve_mudanca else ""
        return True, f"Atualização registrada com sucesso{msg_mudanca}"

    except Exception as e:
        return False, str(e)


def get_usuarios_por_perfil(perfil):
    """
    Retorna lista de usuários de um determinado perfil para dropdown.

    Args:
        perfil: Nome do perfil/departamento

    Returns:
        list: Lista de dicts com label e value para dropdown
    """
    from src.database.connection import get_mongo_connection

    try:
        usuarios = get_mongo_connection("usuarios")

        # Se for admin, buscar todos os usuários
        if perfil == "admin":
            query = {}
        else:
            query = {"perfil": perfil}

        users = list(usuarios.find(query, {"username": 1, "email": 1, "level": 1}))

        return [
            {
                "label": f"{u['username']} (Nível {u.get('level', 1)})",
                "value": u['username']
            }
            for u in users
        ]
    except Exception:
        return []
