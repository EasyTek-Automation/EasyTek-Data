"""Funções para manipulação de Workflow via MongoDB."""
import pandas as pd
from datetime import datetime
from bson import ObjectId
from src.database.connection import get_mongo_connection


# Collections MongoDB
COLLECTION_PENDENCIAS = "Maintenance_workflow"
COLLECTION_HISTORICO = "MaintenanceHistory_workflow"

# Tipos de evento que requerem aprovação
TIPOS_REQUEREM_APROVACAO = [
    "Aguardando Aprovação",
    "Em Produção Assistida",
    "Encerramento",
    "Trabalho Adicional",
    "Lançamento Retroativo"
]


def carregar_pendencias():
    """
    Carrega pendências do MongoDB.

    Retrocompatibilidade: documentos sem campo 'status_aceite' recebem 'aceito'
    (tarefas criadas antes da feature são consideradas aceitas por padrão).

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
                'ultima_edicao_por', 'ultima_edicao_data', 'status_aceite', 'data_aceite'
            ])

        df = pd.DataFrame(documentos)

        # Retrocompatibilidade: status_aceite ausente → 'pendente'
        # (documentos antigos sem o campo precisam ser aceitos pelo responsável)
        if 'status_aceite' not in df.columns:
            df['status_aceite'] = 'pendente'
        else:
            df['status_aceite'] = df['status_aceite'].fillna('pendente')

        if 'data_aceite' not in df.columns:
            df['data_aceite'] = None

        if 'nota_gam' not in df.columns:
            df['nota_gam'] = None

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
            'ultima_edicao_por', 'ultima_edicao_data', 'status_aceite', 'data_aceite'
        ])


def carregar_historico():
    """
    Carrega histórico do MongoDB.

    Returns:
        pd.DataFrame: DataFrame com o histórico
    """
    try:
        collection = get_mongo_connection(COLLECTION_HISTORICO)
        documentos = list(collection.find({}).sort('data', -1))

        if not documentos:
            return pd.DataFrame(columns=[
                'hist_id', 'MaintenanceWF_id', 'descricao', 'data', 'responsavel',
                'tipo_evento', 'editado_por', 'observacoes', 'alteracoes',
                'horas', 'concluido', 'aprovador', 'status_aprovacao', 'data_aprovacao',
                'record_type', 'subtarefa_id'
            ])

        # Converter _id para string e remover campo _id original
        for doc in documentos:
            doc['hist_id'] = str(doc.pop('_id'))

        df = pd.DataFrame(documentos)

        # Garantir colunas novas com valores padrão para registros antigos
        if 'horas' not in df.columns:
            df['horas'] = None
        if 'concluido' not in df.columns:
            df['concluido'] = False
        if 'aprovador' not in df.columns:
            df['aprovador'] = None
        if 'status_aprovacao' not in df.columns:
            df['status_aprovacao'] = None
        if 'data_aprovacao' not in df.columns:
            df['data_aprovacao'] = None

        # Retrocompat record_type
        _tipos_sistema = {'criacao', 'atualizacao_workflow', 'aceite', 'rejeicao_aceite'}
        if 'record_type' not in df.columns:
            df['record_type'] = df['tipo_evento'].apply(
                lambda t: 'criacao' if t in _tipos_sistema else 'subtarefa'
            )
        else:
            df['record_type'] = df['record_type'].fillna('subtarefa')
            # Fix retroativo: editar_pendencia() gravava 'subtarefa' para eventos de sistema
            if 'tipo_evento' in df.columns:
                mask = df['record_type'].eq('subtarefa') & df['tipo_evento'].isin(_tipos_sistema)
                df.loc[mask, 'record_type'] = 'criacao'

        # Retrocompat subtarefa_id
        if 'subtarefa_id' not in df.columns:
            df['subtarefa_id'] = None

        # Converter datas
        if 'data' in df.columns:
            df['data'] = pd.to_datetime(df['data'])

        return df

    except Exception as e:
        print(f"Erro ao carregar histórico: {e}")
        return pd.DataFrame(columns=[
            'hist_id', 'MaintenanceWF_id', 'descricao', 'data', 'responsavel',
            'tipo_evento', 'editado_por', 'observacoes', 'alteracoes',
            'horas', 'concluido', 'aprovador', 'status_aprovacao', 'data_aprovacao',
            'record_type', 'subtarefa_id'
        ])


def gerar_proximo_id():
    """
    Gera próximo ID sequencial (AMG_WFXXX).

    Returns:
        str: Novo ID (ex: AMG_WF051)
    """
    try:
        collection = get_mongo_connection(COLLECTION_PENDENCIAS)

        # Buscar último ID
        ultimo_doc = collection.find_one(
            {},
            sort=[('id', -1)]
        )

        if not ultimo_doc:
            return "AMG_WF001"

        # Extrair número do ID
        ultimo_id = ultimo_doc.get('id', 'AMG_WF000')
        numero = int(ultimo_id.replace('AMG_WF', ''))
        proximo_num = numero + 1

        return f"AMG_WF{proximo_num:03d}"

    except Exception as e:
        print(f"Erro ao gerar ID: {e}")
        return "AMG_WF001"


def criar_pendencia(descricao, responsavel, status, criado_por, criado_por_perfil, nota_gam=None):
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
            'ultima_edicao_data': agora,
            'status_aceite': 'pendente',  # novo responsável deve aceitar a tarefa
            'data_aceite': None,
            'nota_gam': nota_gam or None
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
            'alteracoes': '',
            'horas': None,
            'concluido': False,
            'aprovador': None,
            'status_aprovacao': None,
            'data_aprovacao': None,
            'record_type': 'criacao',
            'subtarefa_id': None
        }

        collection_hist = get_mongo_connection(COLLECTION_HISTORICO)
        collection_hist.insert_one(nova_hist)

        return True, novo_id

    except Exception as e:
        return False, str(e)


def editar_pendencia(pend_id, nova_descricao, novo_responsavel, novo_status,
                     descricao_original, responsavel_original, status_original,
                     editado_por, tipo_evento, observacoes, horas=None, aprovador=None,
                     nota_gam=None):
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
        status_aceite_atual = pendencia.get('status_aceite')

        if nova_descricao and nova_descricao != descricao_original:
            updates['descricao'] = nova_descricao
            alteracoes_log.append("Descrição alterada")

        if novo_responsavel and novo_responsavel != responsavel_original:
            updates['responsavel'] = novo_responsavel
            alteracoes_log.append(f"Responsável: {responsavel_original} → {novo_responsavel}")
            # Ao redesignar, o novo responsável deve aceitar a tarefa
            updates['status_aceite'] = 'pendente'
            updates['data_aceite'] = None
        elif status_aceite_atual == 'rejeitado':
            # Tarefa rejeitada editada pelo nível 3 (mesmo sem trocar responsável):
            # reseta para pendente para que o responsável aceite novamente
            updates['status_aceite'] = 'pendente'
            updates['data_aceite'] = None
            alteracoes_log.append("Aceite resetado para pendente após edição")

        if novo_status and novo_status != status_original:
            updates['status'] = novo_status
            alteracoes_log.append(f"Status: {status_original} → {novo_status}")

        # Atualizar nota GAM (campo opcional — sempre sobrescreve se enviado)
        if nota_gam is not None:
            updates['nota_gam'] = nota_gam.strip() if nota_gam.strip() else None

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
            'alteracoes': ' | '.join(alteracoes_log) if alteracoes_log else '',
            'horas': horas,
            'concluido': False,
            'aprovador': aprovador,
            'status_aprovacao': 'pendente' if aprovador else None,
            'data_aprovacao': None,
            'record_type': 'criacao',
            'subtarefa_id': None
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


def get_usuarios_nivel3_por_perfil(perfil):
    """
    Retorna lista de usuários nível 3 de um determinado perfil (para seleção de aprovador).

    Args:
        perfil: Nome do perfil/departamento

    Returns:
        list: Lista de dicts com label e value para dropdown
    """
    try:
        usuarios = get_mongo_connection("usuarios")

        if perfil == "admin":
            query = {"level": 3}
        else:
            query = {"level": 3, "perfil": perfil}

        users = list(usuarios.find(query, {"username": 1}))

        return [
            {"label": u['username'], "value": u['username']}
            for u in users
        ]
    except Exception:
        return []


def marcar_subtarefa_concluida(hist_id_str):
    """
    Marca uma subatividade do histórico como concluída (operação irreversível).

    Args:
        hist_id_str: String com o ObjectId da entrada de histórico

    Returns:
        bool: True se a atualização foi bem-sucedida
    """
    try:
        collection = get_mongo_connection(COLLECTION_HISTORICO)
        result = collection.update_one(
            {'_id': ObjectId(hist_id_str), 'concluido': {'$ne': True}},
            {'$set': {'concluido': True}}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Erro ao marcar subtarefa como concluída: {e}")
        return False


def aprovar_ou_rejeitar(hist_id_str, status_aprovacao):
    """
    Aprova ou rejeita uma entrada de histórico que aguarda aprovação.

    Args:
        hist_id_str: String com o ObjectId da entrada de histórico
        status_aprovacao: 'aprovado' ou 'rejeitado'

    Returns:
        bool: True se a atualização foi bem-sucedida
    """
    try:
        collection = get_mongo_connection(COLLECTION_HISTORICO)
        result = collection.update_one(
            {'_id': ObjectId(hist_id_str), 'status_aprovacao': 'pendente'},
            {'$set': {
                'status_aprovacao': status_aprovacao,
                'data_aprovacao': datetime.now()
            }}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Erro ao aprovar/rejeitar: {e}")
        return False


def aceitar_tarefa(pend_id, username):
    """
    Registra o aceite de uma tarefa pelo responsável.

    Atualiza status_aceite → 'aceito' e cria entrada no histórico.

    Args:
        pend_id: ID da pendência (ex: 'AMG_WF001')
        username: Username de quem está aceitando

    Returns:
        tuple: (sucesso: bool, mensagem: str)
    """
    try:
        collection_pend = get_mongo_connection(COLLECTION_PENDENCIAS)
        collection_hist = get_mongo_connection(COLLECTION_HISTORICO)
        agora = datetime.now()

        # Verificar se pendência existe e está pendente de aceite
        pendencia = collection_pend.find_one({'id': pend_id})
        if not pendencia:
            return False, "Pendência não encontrada"

        if pendencia.get('status_aceite') == 'aceito':
            return False, "Tarefa já foi aceita"

        # Atualizar status_aceite
        collection_pend.update_one(
            {'id': pend_id},
            {'$set': {
                'status_aceite': 'aceito',
                'data_aceite': agora,
                'ultima_atualizacao': agora
            }}
        )

        # Criar entrada no histórico
        collection_hist.insert_one({
            'MaintenanceWF_id': pend_id,
            'descricao': 'Aceite de Tarefa',
            'data': agora,
            'responsavel': username,
            'tipo_evento': 'aceite',
            'editado_por': username,
            'observacoes': f'Tarefa aceita por {username}',
            'alteracoes': 'status_aceite: pendente → aceito',
            'horas': None,
            'concluido': False,
            'aprovador': None,
            'status_aprovacao': None,
            'data_aprovacao': None,
            'record_type': 'criacao',
            'subtarefa_id': None
        })

        return True, "Tarefa aceita com sucesso"

    except Exception as e:
        print(f"Erro ao aceitar tarefa: {e}")
        return False, str(e)


def rejeitar_tarefa(pend_id, username):
    """
    Registra a rejeição de uma tarefa pelo responsável.

    Atualiza status_aceite → 'rejeitado' e cria entrada no histórico.
    Nível 3 pode redesignar a tarefa (o reset de status_aceite ocorre em editar_pendencia).

    Args:
        pend_id: ID da pendência (ex: 'AMG_WF001')
        username: Username de quem está rejeitando

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

        if pendencia.get('status_aceite') == 'aceito':
            return False, "Tarefa já foi aceita e não pode ser rejeitada"

        # Atualizar status_aceite
        collection_pend.update_one(
            {'id': pend_id},
            {'$set': {
                'status_aceite': 'rejeitado',
                'data_aceite': agora,
                'ultima_atualizacao': agora
            }}
        )

        # Criar entrada no histórico
        collection_hist.insert_one({
            'MaintenanceWF_id': pend_id,
            'descricao': 'Rejeição de Aceite',
            'data': agora,
            'responsavel': username,
            'tipo_evento': 'rejeicao_aceite',
            'editado_por': username,
            'observacoes': f'Tarefa rejeitada por {username}. Aguardando redesignação.',
            'alteracoes': 'status_aceite: pendente → rejeitado',
            'horas': None,
            'concluido': False,
            'aprovador': None,
            'status_aprovacao': None,
            'data_aprovacao': None,
            'record_type': 'criacao',
            'subtarefa_id': None
        })

        return True, "Tarefa rejeitada. Solicite redesignação a um usuário nível 3."

    except Exception as e:
        print(f"Erro ao rejeitar tarefa: {e}")
        return False, str(e)


def criar_subtarefa(pend_id, titulo, tipo_evento, responsavel, observacoes,
                    editado_por, aprovador=None, data_retroativa=None):
    """
    Cria nova subtarefa (record_type='subtarefa') no histórico.

    Args:
        pend_id: ID da pendência
        titulo: Título livre da subtarefa
        tipo_evento: Categoria/tipo do evento (dropdown)
        responsavel: Username do responsável
        observacoes: Detalhes opcionais
        editado_por: Username de quem está criando
        aprovador: Username do aprovador (opcional)
        data_retroativa: datetime da data real do evento (Lançamento Retroativo)

    Returns:
        tuple: (sucesso: bool, mensagem: str)
    """
    try:
        collection_pend = get_mongo_connection(COLLECTION_PENDENCIAS)
        collection_hist = get_mongo_connection(COLLECTION_HISTORICO)
        agora = datetime.now()

        pendencia = collection_pend.find_one({'id': pend_id})
        if not pendencia:
            return False, "Pendência não encontrada"

        doc = {
            'MaintenanceWF_id': pend_id,
            'titulo': titulo,
            'descricao': titulo,  # mantido para retrocompat de display
            'data': data_retroativa if data_retroativa else agora,
            'data_insercao': agora,
            'responsavel': responsavel,
            'tipo_evento': tipo_evento,
            'editado_por': editado_por,
            'observacoes': observacoes or '',
            'alteracoes': '',
            'horas': None,  # horas registradas nos logs/relatórios
            'concluido': False,
            'aprovador': aprovador,
            'status_aprovacao': 'pendente' if aprovador else None,
            'data_aprovacao': None,
            'record_type': 'subtarefa',
            'subtarefa_id': None,
            'data_retroativa': data_retroativa  # None para eventos normais
        }

        collection_hist.insert_one(doc)
        collection_pend.update_one(
            {'id': pend_id},
            {'$set': {'ultima_atualizacao': agora}}
        )

        return True, "Subtarefa criada com sucesso"

    except Exception as e:
        return False, str(e)


def adicionar_log(subtarefa_hist_id, pend_id, observacoes, editado_por, horas=None):
    """
    Adiciona log (relatório) a uma subtarefa existente.

    Args:
        subtarefa_hist_id: hist_id da subtarefa pai
        pend_id: ID da pendência
        observacoes: Texto do relatório (obrigatório)
        editado_por: Username de quem está registrando
        horas: Horas trabalhadas neste relatório (opcional)

    Returns:
        tuple: (sucesso: bool, mensagem: str)
    """
    try:
        collection_hist = get_mongo_connection(COLLECTION_HISTORICO)
        collection_pend = get_mongo_connection(COLLECTION_PENDENCIAS)
        agora = datetime.now()

        doc = {
            'MaintenanceWF_id': pend_id,
            'descricao': 'Relatório',
            'data': agora,
            'responsavel': editado_por,
            'tipo_evento': 'log',
            'editado_por': editado_por,
            'observacoes': observacoes,
            'alteracoes': '',
            'horas': horas,
            'concluido': False,
            'aprovador': None,
            'status_aprovacao': None,
            'data_aprovacao': None,
            'record_type': 'log',
            'subtarefa_id': subtarefa_hist_id
        }

        collection_hist.insert_one(doc)
        collection_pend.update_one(
            {'id': pend_id},
            {'$set': {'ultima_atualizacao': agora}}
        )

        return True, "Relatório adicionado com sucesso"

    except Exception as e:
        return False, str(e)


def editar_subtarefa(hist_id, titulo=None, tipo_evento=None, observacoes=None, concluido=None):
    """
    Edita campos de uma subtarefa existente.

    Args:
        hist_id: ObjectId string da subtarefa
        titulo: Novo título livre (ou None para não alterar)
        tipo_evento: Novo tipo de evento (ou None para não alterar)
        observacoes: Novas observações (ou None para não alterar)
        concluido: Novo status de conclusão (ou None para não alterar)

    Returns:
        tuple: (sucesso: bool, mensagem: str)
    """
    try:
        collection = get_mongo_connection(COLLECTION_HISTORICO)

        updates = {}
        if titulo is not None:
            updates['titulo'] = titulo
            updates['descricao'] = titulo  # mantém retrocompat
        if tipo_evento is not None:
            updates['tipo_evento'] = tipo_evento
        if observacoes is not None:
            updates['observacoes'] = observacoes
        if concluido is not None:
            updates['concluido'] = concluido

        if not updates:
            return False, "Nenhum campo para atualizar"

        result = collection.update_one(
            {'_id': ObjectId(hist_id)},
            {'$set': updates}
        )

        if result.matched_count == 0:
            return False, "Subtarefa não encontrada"

        return True, "Subtarefa atualizada com sucesso"

    except Exception as e:
        return False, str(e)


def deletar_subtarefa(hist_id):
    """
    Deleta uma subtarefa e todos os seus logs.

    Args:
        hist_id: ObjectId string da subtarefa

    Returns:
        tuple: (sucesso: bool, mensagem: str)
    """
    try:
        collection = get_mongo_connection(COLLECTION_HISTORICO)

        result = collection.delete_one({'_id': ObjectId(hist_id)})
        if result.deleted_count == 0:
            return False, "Subtarefa não encontrada"

        # Deletar logs vinculados
        collection.delete_many({'subtarefa_id': hist_id})

        return True, "Subtarefa e seus logs foram removidos"

    except Exception as e:
        return False, str(e)
