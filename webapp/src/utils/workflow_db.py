"""Funções para manipulação de Workflow via MongoDB."""
import pandas as pd
from datetime import datetime
from src.database.connection import get_mongo_connection


# Collections MongoDB
COLLECTION_PENDENCIAS = "Maintenance_workflow"
COLLECTION_HISTORICO = "MaintenanceHistory_workflow"


def carregar_pendencias():
    """
    Carrega pendências do MongoDB.

    Returns:
        pd.DataFrame: DataFrame com as pendências
    """
    try:
        collection = get_mongo_connection(COLLECTION_PENDENCIAS)
        documentos = list(collection.find({}, {'_id': 0}).sort('data_criacao', -1))

        if not documentos:
            return pd.DataFrame(columns=[
                'id', 'descricao', 'responsavel', 'status', 'data_criacao',
                'ultima_atualizacao', 'criado_por', 'criado_por_perfil',
                'ultima_edicao_por', 'ultima_edicao_data'
            ])

        df = pd.DataFrame(documentos)

        # Converter datas para datetime (já vêm como datetime do MongoDB)
        if 'data_criacao' in df.columns:
            df['data_criacao'] = pd.to_datetime(df['data_criacao'])
        if 'ultima_atualizacao' in df.columns:
            df['ultima_atualizacao'] = pd.to_datetime(df['ultima_atualizacao'])
        if 'ultima_edicao_data' in df.columns:
            df['ultima_edicao_data'] = pd.to_datetime(df['ultima_edicao_data'])

        return df

    except Exception as e:
        print(f"Erro ao carregar pendências: {e}")
        return pd.DataFrame(columns=[
            'id', 'descricao', 'responsavel', 'status', 'data_criacao',
            'ultima_atualizacao', 'criado_por', 'criado_por_perfil',
            'ultima_edicao_por', 'ultima_edicao_data'
        ])


def carregar_historico():
    """
    Carrega histórico do MongoDB.

    Returns:
        pd.DataFrame: DataFrame com o histórico
    """
    try:
        collection = get_mongo_connection(COLLECTION_HISTORICO)
        documentos = list(collection.find({}, {'_id': 0}).sort('data', -1))

        if not documentos:
            return pd.DataFrame(columns=[
                'MaintenanceWF_id', 'descricao', 'data', 'responsavel',
                'tipo_evento', 'editado_por', 'observacoes', 'alteracoes'
            ])

        df = pd.DataFrame(documentos)

        # Converter datas
        if 'data' in df.columns:
            df['data'] = pd.to_datetime(df['data'])

        return df

    except Exception as e:
        print(f"Erro ao carregar histórico: {e}")
        return pd.DataFrame(columns=[
            'MaintenanceWF_id', 'descricao', 'data', 'responsavel',
            'tipo_evento', 'editado_por', 'observacoes', 'alteracoes'
        ])


def gerar_proximo_id():
    """
    Gera próximo ID sequencial (PEND-XXX).

    Returns:
        str: Novo ID (ex: PEND-051)
    """
    try:
        collection = get_mongo_connection(COLLECTION_PENDENCIAS)

        # Buscar último ID
        ultimo_doc = collection.find_one(
            {},
            sort=[('id', -1)]
        )

        if not ultimo_doc:
            return "PEND-001"

        # Extrair número do ID
        ultimo_id = ultimo_doc.get('id', 'PEND-000')
        numero = int(ultimo_id.split('-')[1])
        proximo_num = numero + 1

        return f"PEND-{proximo_num:03d}"

    except Exception as e:
        print(f"Erro ao gerar ID: {e}")
        return "PEND-001"


def criar_pendencia(descricao, responsavel, status, criado_por, criado_por_perfil):
    """
    Cria nova pendência no MongoDB.

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
        # Gerar ID
        novo_id = gerar_proximo_id()
        agora = datetime.now()

        # Documento da pendência
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

        # Inserir pendência
        collection_pend = get_mongo_connection(COLLECTION_PENDENCIAS)
        collection_pend.insert_one(nova_pend)

        # Criar entrada no histórico
        nova_hist = {
            'MaintenanceWF_id': novo_id,
            'descricao': 'Início Workflow',
            'data': agora,
            'responsavel': responsavel,
            'tipo_evento': 'criacao',
            'editado_por': criado_por,
            'observacoes': f'Pendência criada e atribuída a {responsavel}',
            'alteracoes': ''  # Sem alterações na criação
        }

        collection_hist = get_mongo_connection(COLLECTION_HISTORICO)
        collection_hist.insert_one(nova_hist)

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
        collection_pend = get_mongo_connection(COLLECTION_PENDENCIAS)
        collection_hist = get_mongo_connection(COLLECTION_HISTORICO)
        agora = datetime.now()

        # Verificar se pendência existe
        pendencia = collection_pend.find_one({'id': pend_id})
        if not pendencia:
            return False, "Pendência não encontrada"

        # Construir log de alterações e updates
        alteracoes_log = []
        updates = {}

        if nova_descricao and nova_descricao != descricao_original:
            updates['descricao'] = nova_descricao
            alteracoes_log.append("Descrição alterada")

        if novo_responsavel and novo_responsavel != responsavel_original:
            updates['responsavel'] = novo_responsavel
            alteracoes_log.append(f"Responsável: {responsavel_original} → {novo_responsavel}")

        if novo_status and novo_status != status_original:
            updates['status'] = novo_status
            alteracoes_log.append(f"Status: {status_original} → {novo_status}")

        # Atualizar metadata
        updates['ultima_atualizacao'] = agora
        updates['ultima_edicao_por'] = editado_por
        updates['ultima_edicao_data'] = agora

        # Atualizar pendência
        collection_pend.update_one(
            {'id': pend_id},
            {'$set': updates}
        )

        # SEMPRE adicionar entrada no histórico
        nova_entrada_historico = {
            'MaintenanceWF_id': pend_id,
            'descricao': tipo_evento,  # Título do evento
            'data': agora,
            'responsavel': novo_responsavel or responsavel_original,
            'tipo_evento': 'atualizacao_workflow',
            'editado_por': editado_por,
            'observacoes': observacoes,
            'alteracoes': ' | '.join(alteracoes_log) if alteracoes_log else ''
        }

        collection_hist.insert_one(nova_entrada_historico)

        msg_mudanca = " (com alterações nos campos)" if alteracoes_log else ""
        return True, f"Atualização registrada com sucesso{msg_mudanca}"

    except Exception as e:
        return False, str(e)


def deletar_pendencia(pend_id):
    """
    Deleta pendência e todo seu histórico do MongoDB.

    Args:
        pend_id: ID da pendência

    Returns:
        tuple: (sucesso: bool, mensagem: str)
    """
    try:
        collection_pend = get_mongo_connection(COLLECTION_PENDENCIAS)
        collection_hist = get_mongo_connection(COLLECTION_HISTORICO)

        # Verificar se pendência existe
        pendencia = collection_pend.find_one({'id': pend_id})
        if not pendencia:
            return False, "Pendência não encontrada"

        # Deletar pendência
        collection_pend.delete_one({'id': pend_id})

        # Deletar histórico
        collection_hist.delete_many({'MaintenanceWF_id': pend_id})

        return True, f"Pendência {pend_id} deletada com sucesso"

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
