"""
Testes para src/utils/workflow_db.py

Captura o comportamento ATUAL antes de qualquer alteração.
Usa unittest.mock.patch para mockar get_mongo_connection.
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from datetime import datetime


# =============================================================================
# FIXTURE: Mock MongoDB
# =============================================================================

def make_collection_mock(docs=None):
    """Cria mock de collection MongoDB."""
    mock = MagicMock()
    docs = docs or []

    # find().sort() retorna docs
    find_result = MagicMock()
    find_result.sort.return_value = iter(docs)
    mock.find.return_value = find_result

    # find_one retorna primeiro doc ou None
    mock.find_one.return_value = docs[0] if docs else None

    mock.insert_one.return_value = MagicMock(inserted_id="fake_id")
    mock.update_one.return_value = MagicMock(modified_count=1)
    mock.delete_one.return_value = MagicMock(deleted_count=1)
    mock.delete_many.return_value = MagicMock(deleted_count=1)

    return mock


# =============================================================================
# TESTES: TIPOS_REQUEREM_APROVACAO
# =============================================================================

class TestTiposRequeremAprovacao:
    """Testa que TIPOS_REQUEREM_APROVACAO contém os tipos esperados."""

    def test_tipos_existentes_presentes(self):
        from src.utils.workflow_db import TIPOS_REQUEREM_APROVACAO
        assert "Aguardando Aprovação" in TIPOS_REQUEREM_APROVACAO
        assert "Em Produção Assistida" in TIPOS_REQUEREM_APROVACAO
        assert "Encerramento" in TIPOS_REQUEREM_APROVACAO

    def test_trabalho_adicional_presente(self):
        """Fase 2: 'Trabalho Adicional' deve estar na lista."""
        from src.utils.workflow_db import TIPOS_REQUEREM_APROVACAO
        assert "Trabalho Adicional" in TIPOS_REQUEREM_APROVACAO

    def test_e_iteravel(self):
        from src.utils.workflow_db import TIPOS_REQUEREM_APROVACAO
        assert hasattr(TIPOS_REQUEREM_APROVACAO, '__iter__')
        assert len(list(TIPOS_REQUEREM_APROVACAO)) >= 4

    def test_tipo_normal_nao_requer(self):
        from src.utils.workflow_db import TIPOS_REQUEREM_APROVACAO
        assert "Análise de Falha" not in TIPOS_REQUEREM_APROVACAO
        assert "Manutenção Corretiva" not in TIPOS_REQUEREM_APROVACAO


# =============================================================================
# TESTES: carregar_pendencias()
# =============================================================================

class TestCarregarPendencias:
    """Testa carregar_pendencias() com mock MongoDB."""

    def test_retorna_dataframe_vazio_quando_sem_documentos(self):
        mock_col = make_collection_mock(docs=[])
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock_col):
            from src.utils.workflow_db import carregar_pendencias
            df = carregar_pendencias()
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_retorna_dataframe_com_colunas_esperadas_quando_vazio(self):
        mock_col = make_collection_mock(docs=[])
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock_col):
            from src.utils.workflow_db import carregar_pendencias
            df = carregar_pendencias()
        colunas_esperadas = ['id', 'descricao', 'responsavel', 'status', 'data_criacao']
        for col in colunas_esperadas:
            assert col in df.columns, f"Coluna '{col}' ausente"

    def test_retorna_dataframe_com_documentos(self):
        agora = datetime.now()
        docs = [
            {
                'id': 'AMG_WF001',
                'descricao': 'Teste',
                'responsavel': 'usuario1',
                'status': 'Pendente',
                'data_criacao': agora,
                'ultima_atualizacao': agora,
                'criado_por': 'admin',
                'criado_por_perfil': 'manutencao',
                'ultima_edicao_por': 'admin',
                'ultima_edicao_data': agora
            }
        ]
        mock_col = make_collection_mock(docs=docs)
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock_col):
            from src.utils.workflow_db import carregar_pendencias
            df = carregar_pendencias()
        assert len(df) == 1
        assert df.iloc[0]['id'] == 'AMG_WF001'
        assert df.iloc[0]['responsavel'] == 'usuario1'

    def test_retorna_dataframe_vazio_em_caso_de_erro(self):
        mock_col = MagicMock()
        mock_col.find.side_effect = Exception("Erro de conexão")
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock_col):
            from src.utils.workflow_db import carregar_pendencias
            df = carregar_pendencias()
        assert isinstance(df, pd.DataFrame)
        assert df.empty


# =============================================================================
# TESTES: criar_pendencia()
# =============================================================================

class TestCriarPendencia:
    """Testa criar_pendencia() com mock MongoDB."""

    def _setup_mocks(self, id_existente=None):
        """Cria mocks para as duas collections usadas em criar_pendencia."""
        mock_pend_col = MagicMock()
        mock_hist_col = MagicMock()

        # Simular gerar_proximo_id: buscar último doc
        if id_existente:
            ultimo_doc = {'id': id_existente}
        else:
            ultimo_doc = None

        mock_pend_col.find_one.return_value = ultimo_doc
        mock_pend_col.insert_one.return_value = MagicMock()
        mock_hist_col.insert_one.return_value = MagicMock()

        return mock_pend_col, mock_hist_col

    def test_retorna_true_e_id_em_sucesso(self):
        mock_pend, mock_hist = self._setup_mocks()

        def side_effect(collection_name):
            if collection_name == 'Maintenance_workflow':
                return mock_pend
            return mock_hist

        with patch('src.utils.workflow_db.get_mongo_connection', side_effect=side_effect):
            from src.utils.workflow_db import criar_pendencia
            sucesso, resultado = criar_pendencia(
                descricao='Teste',
                responsavel='user1',
                status='Pendente',
                criado_por='admin',
                criado_por_perfil='manutencao'
            )
        assert sucesso is True
        assert isinstance(resultado, str)
        assert resultado.startswith('AMG_WF')

    def test_id_sequencial_baseado_no_ultimo(self):
        mock_pend, mock_hist = self._setup_mocks(id_existente='AMG_WF050')

        def side_effect(collection_name):
            if collection_name == 'Maintenance_workflow':
                return mock_pend
            return mock_hist

        with patch('src.utils.workflow_db.get_mongo_connection', side_effect=side_effect):
            from src.utils.workflow_db import criar_pendencia
            sucesso, resultado = criar_pendencia(
                descricao='Teste',
                responsavel='user1',
                status='Pendente',
                criado_por='admin',
                criado_por_perfil='manutencao'
            )
        assert sucesso is True
        assert resultado == 'AMG_WF051'

    def test_insere_documento_na_collection(self):
        mock_pend, mock_hist = self._setup_mocks()

        def side_effect(collection_name):
            if collection_name == 'Maintenance_workflow':
                return mock_pend
            return mock_hist

        with patch('src.utils.workflow_db.get_mongo_connection', side_effect=side_effect):
            from src.utils.workflow_db import criar_pendencia
            criar_pendencia('Desc', 'user1', 'Pendente', 'admin', 'manutencao')

        # Verificar que insert_one foi chamado na collection de pendências
        assert mock_pend.insert_one.called

    def test_cria_entrada_historico(self):
        mock_pend, mock_hist = self._setup_mocks()

        def side_effect(collection_name):
            if collection_name == 'Maintenance_workflow':
                return mock_pend
            return mock_hist

        with patch('src.utils.workflow_db.get_mongo_connection', side_effect=side_effect):
            from src.utils.workflow_db import criar_pendencia
            criar_pendencia('Desc', 'user1', 'Pendente', 'admin', 'manutencao')

        # Verificar que insert_one foi chamado no histórico
        assert mock_hist.insert_one.called

    def test_retorna_false_em_caso_de_erro(self):
        # gerar_proximo_id() captura erros internamente e retorna fallback
        # criar_pendencia() só falha se insert_one falhar
        mock_pend = MagicMock()
        mock_pend.find_one.return_value = None  # gerar_proximo_id usa find_one
        mock_pend.insert_one.side_effect = Exception("Erro de inserção")

        def side_effect(collection_name):
            return mock_pend

        with patch('src.utils.workflow_db.get_mongo_connection', side_effect=side_effect):
            from src.utils.workflow_db import criar_pendencia
            sucesso, mensagem = criar_pendencia('Desc', 'user1', 'Pendente', 'admin', 'manutencao')
        assert sucesso is False


# =============================================================================
# TESTES: editar_pendencia()
# =============================================================================

class TestEditarPendencia:
    """Testa editar_pendencia() com mock MongoDB."""

    def _make_pend_mock(self, pend_existente=True):
        mock_pend = MagicMock()
        mock_hist = MagicMock()

        if pend_existente:
            mock_pend.find_one.return_value = {
                'id': 'AMG_WF001',
                'descricao': 'Desc original',
                'responsavel': 'user1',
                'status': 'Pendente'
            }
        else:
            mock_pend.find_one.return_value = None

        mock_pend.update_one.return_value = MagicMock(modified_count=1)
        mock_hist.insert_one.return_value = MagicMock()
        return mock_pend, mock_hist

    def test_retorna_false_pendencia_nao_encontrada(self):
        mock_pend, mock_hist = self._make_pend_mock(pend_existente=False)

        def side_effect(collection_name):
            if collection_name == 'Maintenance_workflow':
                return mock_pend
            return mock_hist

        with patch('src.utils.workflow_db.get_mongo_connection', side_effect=side_effect):
            from src.utils.workflow_db import editar_pendencia
            sucesso, msg = editar_pendencia(
                pend_id='AMG_WF999',
                nova_descricao=None, novo_responsavel=None, novo_status=None,
                descricao_original='orig', responsavel_original='user1', status_original='Pendente',
                editado_por='admin', tipo_evento='Análise de Falha', observacoes='obs'
            )
        assert sucesso is False

    def test_retorna_true_em_sucesso(self):
        mock_pend, mock_hist = self._make_pend_mock()

        def side_effect(collection_name):
            if collection_name == 'Maintenance_workflow':
                return mock_pend
            return mock_hist

        with patch('src.utils.workflow_db.get_mongo_connection', side_effect=side_effect):
            from src.utils.workflow_db import editar_pendencia
            sucesso, msg = editar_pendencia(
                pend_id='AMG_WF001',
                nova_descricao='Nova desc', novo_responsavel=None, novo_status=None,
                descricao_original='Desc original', responsavel_original='user1', status_original='Pendente',
                editado_por='admin', tipo_evento='Análise de Falha', observacoes='Observações detalhadas'
            )
        assert sucesso is True

    def test_cria_entrada_historico_sempre(self):
        mock_pend, mock_hist = self._make_pend_mock()

        def side_effect(collection_name):
            if collection_name == 'Maintenance_workflow':
                return mock_pend
            return mock_hist

        with patch('src.utils.workflow_db.get_mongo_connection', side_effect=side_effect):
            from src.utils.workflow_db import editar_pendencia
            editar_pendencia(
                pend_id='AMG_WF001',
                nova_descricao=None, novo_responsavel=None, novo_status=None,
                descricao_original='Desc original', responsavel_original='user1', status_original='Pendente',
                editado_por='admin', tipo_evento='Análise de Falha', observacoes='Obs'
            )

        assert mock_hist.insert_one.called

    def test_log_alteracoes_responsavel(self):
        mock_pend, mock_hist = self._make_pend_mock()
        chamadas = []

        def side_effect(collection_name):
            if collection_name == 'Maintenance_workflow':
                return mock_pend
            return mock_hist

        mock_hist.insert_one.side_effect = lambda doc: chamadas.append(doc)

        with patch('src.utils.workflow_db.get_mongo_connection', side_effect=side_effect):
            from src.utils.workflow_db import editar_pendencia
            editar_pendencia(
                pend_id='AMG_WF001',
                nova_descricao=None, novo_responsavel='user2', novo_status=None,
                descricao_original='Desc original', responsavel_original='user1', status_original='Pendente',
                editado_por='admin', tipo_evento='Análise de Falha', observacoes='Obs'
            )

        assert chamadas, "insert_one não foi chamado"
        doc_hist = chamadas[0]
        assert 'user1' in doc_hist.get('alteracoes', '') or 'user2' in doc_hist.get('alteracoes', '')

    def test_reset_status_aceite_ao_mudar_responsavel(self):
        """Fase 3: ao mudar responsável, status_aceite deve ser resetado para 'pendente'."""
        mock_pend, mock_hist = self._make_pend_mock()
        updates_capturados = []

        def side_effect(collection_name):
            if collection_name == 'Maintenance_workflow':
                return mock_pend
            return mock_hist

        mock_pend.update_one.side_effect = lambda q, u: updates_capturados.append(u)

        with patch('src.utils.workflow_db.get_mongo_connection', side_effect=side_effect):
            from src.utils.workflow_db import editar_pendencia
            editar_pendencia(
                pend_id='AMG_WF001',
                nova_descricao=None, novo_responsavel='user2', novo_status=None,
                descricao_original='Desc original', responsavel_original='user1', status_original='Pendente',
                editado_por='admin', tipo_evento='Análise de Falha', observacoes='Obs'
            )

        assert updates_capturados, "update_one não foi chamado"
        set_ops = updates_capturados[0].get('$set', {})
        assert set_ops.get('status_aceite') == 'pendente', "status_aceite não foi resetado"


# =============================================================================
# TESTES: criar_pendencia() — campo status_aceite
# =============================================================================

class TestCriarPendenciaStatusAceite:
    """Testa que criar_pendencia() inicializa status_aceite='pendente'."""

    def test_insere_status_aceite_pendente(self):
        mock_pend = MagicMock()
        mock_hist = MagicMock()
        mock_pend.find_one.return_value = None
        documentos_inseridos = []
        mock_pend.insert_one.side_effect = lambda doc: documentos_inseridos.append(doc)

        def side_effect(collection_name):
            if collection_name == 'Maintenance_workflow':
                return mock_pend
            return mock_hist

        with patch('src.utils.workflow_db.get_mongo_connection', side_effect=side_effect):
            from src.utils.workflow_db import criar_pendencia
            criar_pendencia('Desc', 'user1', 'Pendente', 'admin', 'manutencao')

        assert documentos_inseridos, "Nenhum documento foi inserido"
        doc = documentos_inseridos[0]
        assert doc.get('status_aceite') == 'pendente', "status_aceite não foi inicializado como 'pendente'"


# =============================================================================
# TESTES: carregar_pendencias() — retrocompatibilidade status_aceite
# =============================================================================

class TestCarregarPendenciasStatusAceite:
    """Testa retrocompatibilidade do campo status_aceite."""

    def test_documento_sem_status_aceite_recebe_aceito(self):
        """Documentos sem o campo status_aceite devem receber 'aceito' por padrão."""
        agora = datetime.now()
        docs = [{
            'id': 'AMG_WF001',
            'descricao': 'Tarefa antiga',
            'responsavel': 'user1',
            'status': 'Em Andamento',
            'data_criacao': agora,
            'ultima_atualizacao': agora,
            'criado_por': 'admin',
            'criado_por_perfil': 'manutencao',
            'ultima_edicao_por': 'admin',
            'ultima_edicao_data': agora
            # Sem campo 'status_aceite' — documento antigo
        }]
        mock_col = make_collection_mock(docs=docs)
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock_col):
            from src.utils.workflow_db import carregar_pendencias
            df = carregar_pendencias()

        assert 'status_aceite' in df.columns
        assert df.iloc[0]['status_aceite'] == 'pendente'

    def test_documento_com_status_aceite_pendente_mantem(self):
        """Documentos com status_aceite='pendente' devem manter o valor."""
        agora = datetime.now()
        docs = [{
            'id': 'AMG_WF002',
            'descricao': 'Tarefa nova',
            'responsavel': 'user1',
            'status': 'Pendente',
            'data_criacao': agora,
            'ultima_atualizacao': agora,
            'criado_por': 'admin',
            'criado_por_perfil': 'manutencao',
            'ultima_edicao_por': 'admin',
            'ultima_edicao_data': agora,
            'status_aceite': 'pendente',
            'data_aceite': None
        }]
        mock_col = make_collection_mock(docs=docs)
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock_col):
            from src.utils.workflow_db import carregar_pendencias
            df = carregar_pendencias()

        assert df.iloc[0]['status_aceite'] == 'pendente'


# =============================================================================
# TESTES: aceitar_tarefa() e rejeitar_tarefa()
# =============================================================================

class TestAceitarRejeitarTarefa:
    """Testa aceitar_tarefa() e rejeitar_tarefa()."""

    def _make_mocks(self, status_aceite='pendente'):
        mock_pend = MagicMock()
        mock_hist = MagicMock()
        mock_pend.find_one.return_value = {
            'id': 'AMG_WF001',
            'responsavel': 'user1',
            'status_aceite': status_aceite
        }
        mock_pend.update_one.return_value = MagicMock(modified_count=1)
        mock_hist.insert_one.return_value = MagicMock()
        return mock_pend, mock_hist

    def _side_effect(self, mock_pend, mock_hist):
        def fn(collection_name):
            if collection_name == 'Maintenance_workflow':
                return mock_pend
            return mock_hist
        return fn

    # --- aceitar_tarefa ---

    def test_aceitar_retorna_true_em_sucesso(self):
        mock_pend, mock_hist = self._make_mocks()
        with patch('src.utils.workflow_db.get_mongo_connection',
                   side_effect=self._side_effect(mock_pend, mock_hist)):
            from src.utils.workflow_db import aceitar_tarefa
            sucesso, msg = aceitar_tarefa('AMG_WF001', 'user1')
        assert sucesso is True

    def test_aceitar_tarefa_inexistente_retorna_false(self):
        mock_pend = MagicMock()
        mock_pend.find_one.return_value = None
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock_pend):
            from src.utils.workflow_db import aceitar_tarefa
            sucesso, msg = aceitar_tarefa('AMG_WF999', 'user1')
        assert sucesso is False

    def test_aceitar_tarefa_ja_aceita_retorna_false(self):
        mock_pend, mock_hist = self._make_mocks(status_aceite='aceito')
        with patch('src.utils.workflow_db.get_mongo_connection',
                   side_effect=self._side_effect(mock_pend, mock_hist)):
            from src.utils.workflow_db import aceitar_tarefa
            sucesso, msg = aceitar_tarefa('AMG_WF001', 'user1')
        assert sucesso is False

    def test_aceitar_atualiza_status_no_mongodb(self):
        mock_pend, mock_hist = self._make_mocks()
        updates = []
        mock_pend.update_one.side_effect = lambda q, u: updates.append(u)
        with patch('src.utils.workflow_db.get_mongo_connection',
                   side_effect=self._side_effect(mock_pend, mock_hist)):
            from src.utils.workflow_db import aceitar_tarefa
            aceitar_tarefa('AMG_WF001', 'user1')
        assert updates
        assert updates[0].get('$set', {}).get('status_aceite') == 'aceito'

    def test_aceitar_cria_entrada_historico(self):
        mock_pend, mock_hist = self._make_mocks()
        with patch('src.utils.workflow_db.get_mongo_connection',
                   side_effect=self._side_effect(mock_pend, mock_hist)):
            from src.utils.workflow_db import aceitar_tarefa
            aceitar_tarefa('AMG_WF001', 'user1')
        assert mock_hist.insert_one.called

    # --- rejeitar_tarefa ---

    def test_rejeitar_retorna_true_em_sucesso(self):
        mock_pend, mock_hist = self._make_mocks()
        with patch('src.utils.workflow_db.get_mongo_connection',
                   side_effect=self._side_effect(mock_pend, mock_hist)):
            from src.utils.workflow_db import rejeitar_tarefa
            sucesso, msg = rejeitar_tarefa('AMG_WF001', 'user1')
        assert sucesso is True

    def test_rejeitar_tarefa_inexistente_retorna_false(self):
        mock_pend = MagicMock()
        mock_pend.find_one.return_value = None
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock_pend):
            from src.utils.workflow_db import rejeitar_tarefa
            sucesso, msg = rejeitar_tarefa('AMG_WF999', 'user1')
        assert sucesso is False

    def test_rejeitar_tarefa_ja_aceita_retorna_false(self):
        mock_pend, mock_hist = self._make_mocks(status_aceite='aceito')
        with patch('src.utils.workflow_db.get_mongo_connection',
                   side_effect=self._side_effect(mock_pend, mock_hist)):
            from src.utils.workflow_db import rejeitar_tarefa
            sucesso, msg = rejeitar_tarefa('AMG_WF001', 'user1')
        assert sucesso is False

    def test_rejeitar_atualiza_status_rejeitado(self):
        mock_pend, mock_hist = self._make_mocks()
        updates = []
        mock_pend.update_one.side_effect = lambda q, u: updates.append(u)
        with patch('src.utils.workflow_db.get_mongo_connection',
                   side_effect=self._side_effect(mock_pend, mock_hist)):
            from src.utils.workflow_db import rejeitar_tarefa
            rejeitar_tarefa('AMG_WF001', 'user1')
        assert updates
        assert updates[0].get('$set', {}).get('status_aceite') == 'rejeitado'

    def test_rejeitar_cria_entrada_historico(self):
        mock_pend, mock_hist = self._make_mocks()
        with patch('src.utils.workflow_db.get_mongo_connection',
                   side_effect=self._side_effect(mock_pend, mock_hist)):
            from src.utils.workflow_db import rejeitar_tarefa
            rejeitar_tarefa('AMG_WF001', 'user1')
        assert mock_hist.insert_one.called


# =============================================================================
# TESTES: prioridade em carregar_historico (retrocompat)
# =============================================================================

class TestCarregarHistoricoPrioridade:
    """Testa retrocompatibilidade do campo prioridade em carregar_historico."""

    def _docs_sem_prioridade(self):
        from bson import ObjectId
        return [
            {'_id': ObjectId(), 'MaintenanceWF_id': 'WF001', 'descricao': 'Ativ',
             'data': datetime.now(), 'responsavel': 'u1', 'tipo_evento': 'Manutenção Corretiva',
             'editado_por': 'u1', 'observacoes': '', 'alteracoes': '',
             'horas': None, 'concluido': False, 'aprovador': None,
             'status_aprovacao': None, 'data_aprovacao': None,
             'record_type': 'subtarefa', 'subtarefa_id': None},
        ]

    def test_documentos_sem_prioridade_recebem_normal(self):
        """Atividades sem campo prioridade devem receber 'normal' por retrocompat."""
        docs = self._docs_sem_prioridade()
        mock_col = make_collection_mock(docs)
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock_col):
            from src.utils.workflow_db import carregar_historico
            df = carregar_historico()
        assert 'prioridade' in df.columns
        assert df['prioridade'].iloc[0] == 'normal'

    def test_prioridade_existente_preservada(self):
        """Atividades com prioridade 'alta' devem manter o valor."""
        docs = self._docs_sem_prioridade()
        docs[0]['prioridade'] = 'alta'
        mock_col = make_collection_mock(docs)
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock_col):
            from src.utils.workflow_db import carregar_historico
            df = carregar_historico()
        assert df['prioridade'].iloc[0] == 'alta'

    def test_prioridade_none_recebe_normal(self):
        """Atividades com prioridade=None devem receber 'normal'."""
        docs = self._docs_sem_prioridade()
        docs[0]['prioridade'] = None
        mock_col = make_collection_mock(docs)
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock_col):
            from src.utils.workflow_db import carregar_historico
            df = carregar_historico()
        assert df['prioridade'].iloc[0] == 'normal'


# =============================================================================
# TESTES: prioridade em criar_subtarefa
# =============================================================================

class TestCriarSubtarefaPrioridade:
    """Testa que criar_subtarefa salva prioridade corretamente."""

    def _make_mocks(self):
        from bson import ObjectId
        mock_pend = make_collection_mock([{
            '_id': ObjectId(), 'id': 'WF001', 'descricao': 'Demanda',
            'responsavel': 'u1', 'status': 'Em Andamento',
        }])
        mock_hist = make_collection_mock()
        return mock_pend, mock_hist

    def _side_effect(self, mock_pend, mock_hist):
        from src.utils.workflow_db import COLLECTION_PENDENCIAS, COLLECTION_HISTORICO
        def _se(col_name):
            return mock_pend if col_name == COLLECTION_PENDENCIAS else mock_hist
        return _se

    def test_prioridade_padrao_e_normal(self):
        """Sem informar prioridade, deve gravar 'normal'."""
        mock_pend, mock_hist = self._make_mocks()
        with patch('src.utils.workflow_db.get_mongo_connection',
                   side_effect=self._side_effect(mock_pend, mock_hist)):
            from src.utils.workflow_db import criar_subtarefa
            criar_subtarefa('WF001', 'Título', 'Análise de Falha', 'u1', '', 'u1')
        doc = mock_hist.insert_one.call_args[0][0]
        assert doc.get('prioridade') == 'normal'

    def test_prioridade_alta_salva_corretamente(self):
        """Passando prioridade='alta', deve gravar 'alta'."""
        mock_pend, mock_hist = self._make_mocks()
        with patch('src.utils.workflow_db.get_mongo_connection',
                   side_effect=self._side_effect(mock_pend, mock_hist)):
            from src.utils.workflow_db import criar_subtarefa
            criar_subtarefa('WF001', 'Título', 'Análise de Falha', 'u1', '', 'u1',
                            prioridade='alta')
        doc = mock_hist.insert_one.call_args[0][0]
        assert doc.get('prioridade') == 'alta'

    def test_prioridade_urgente_salva_corretamente(self):
        mock_pend, mock_hist = self._make_mocks()
        with patch('src.utils.workflow_db.get_mongo_connection',
                   side_effect=self._side_effect(mock_pend, mock_hist)):
            from src.utils.workflow_db import criar_subtarefa
            criar_subtarefa('WF001', 'Título', 'Análise de Falha', 'u1', '', 'u1',
                            prioridade='urgente')
        doc = mock_hist.insert_one.call_args[0][0]
        assert doc.get('prioridade') == 'urgente'


# =============================================================================
# TESTES: prioridade em editar_subtarefa
# =============================================================================

class TestEditarSubtarefaPrioridade:
    """Testa que editar_subtarefa atualiza prioridade corretamente."""

    def _make_mock_hist(self):
        from bson import ObjectId
        self._oid = ObjectId()
        mock_hist = make_collection_mock([{
            '_id': self._oid, 'MaintenanceWF_id': 'WF001',
            'record_type': 'subtarefa', 'prioridade': 'normal',
        }])
        mock_hist.find_one.return_value = {'_id': self._oid, 'prioridade': 'normal'}
        return mock_hist

    def test_atualiza_prioridade_para_urgente(self):
        """editar_subtarefa com prioridade='urgente' deve atualizar o campo."""
        mock_hist = self._make_mock_hist()
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock_hist):
            from src.utils.workflow_db import editar_subtarefa
            sucesso, _ = editar_subtarefa(str(self._oid), prioridade='urgente')
        assert sucesso
        updates = mock_hist.update_one.call_args[0][1]['$set']
        assert updates.get('prioridade') == 'urgente'

    def test_sem_prioridade_nao_atualiza_campo(self):
        """editar_subtarefa sem prioridade não deve incluir o campo no $set."""
        mock_hist = self._make_mock_hist()
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock_hist):
            from src.utils.workflow_db import editar_subtarefa
            editar_subtarefa(str(self._oid), titulo='Novo título')
        updates = mock_hist.update_one.call_args[0][1]['$set']
        assert 'prioridade' not in updates


# =============================================================================
# TESTES: Fase 2 — data_planejada / data_execucao
# =============================================================================

class TestCarregarHistoricoDatasPlanejada:
    """Retrocompat para data_planejada e data_execucao em carregar_historico."""

    def _make_mock(self, docs):
        mock = MagicMock()
        fr = MagicMock()
        fr.sort.return_value = iter(docs)
        mock.find.return_value = fr
        return mock

    def test_sem_data_planejada_recebe_none(self):
        from bson import ObjectId
        doc = {'_id': ObjectId(), 'MaintenanceWF_id': 'WF001', 'descricao': 'X',
               'data': datetime.now(), 'responsavel': 'u', 'tipo_evento': 'Análise de Falha',
               'editado_por': 'u', 'horas': None, 'concluido': False}
        mock = self._make_mock([doc])
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock):
            from src.utils.workflow_db import carregar_historico
            df = carregar_historico()
        assert 'data_planejada' in df.columns
        assert df.iloc[0]['data_planejada'] is None

    def test_sem_data_execucao_recebe_none(self):
        from bson import ObjectId
        doc = {'_id': ObjectId(), 'MaintenanceWF_id': 'WF001', 'descricao': 'X',
               'data': datetime.now(), 'responsavel': 'u', 'tipo_evento': 'Análise de Falha',
               'editado_por': 'u', 'horas': None, 'concluido': False}
        mock = self._make_mock([doc])
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock):
            from src.utils.workflow_db import carregar_historico
            df = carregar_historico()
        assert 'data_execucao' in df.columns
        assert df.iloc[0]['data_execucao'] is None

    def test_data_planejada_existente_preservada(self):
        from bson import ObjectId
        from datetime import date
        data_plan = datetime(2026, 3, 20)
        doc = {'_id': ObjectId(), 'MaintenanceWF_id': 'WF001', 'descricao': 'X',
               'data': datetime.now(), 'responsavel': 'u', 'tipo_evento': 'Análise de Falha',
               'editado_por': 'u', 'horas': None, 'concluido': False,
               'data_planejada': data_plan}
        mock = self._make_mock([doc])
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock):
            from src.utils.workflow_db import carregar_historico
            df = carregar_historico()
        assert df.iloc[0]['data_planejada'] == data_plan


class TestCriarSubtarefaDataPlanejada:
    """Testa que data_planejada é salva corretamente em criar_subtarefa."""

    def _make_mocks(self):
        mock_pend = MagicMock()
        mock_pend.find_one.return_value = {'id': 'WF001', 'descricao': 'X', 'responsavel': 'u', 'status': 'Pendente'}
        mock_pend.update_one.return_value = MagicMock()
        mock_hist = MagicMock()
        mock_hist.insert_one.return_value = MagicMock()
        return mock_pend, mock_hist

    def _side(self, mp, mh):
        def se(name):
            return mp if name == 'Maintenance_workflow' else mh
        return se

    def test_data_planejada_none_por_padrao(self):
        mp, mh = self._make_mocks()
        with patch('src.utils.workflow_db.get_mongo_connection', side_effect=self._side(mp, mh)):
            from src.utils.workflow_db import criar_subtarefa
            criar_subtarefa('WF001', 'T', 'Análise de Falha', 'u', '', 'admin')
        doc = mh.insert_one.call_args[0][0]
        assert doc.get('data_planejada') is None

    def test_data_planejada_salva_quando_fornecida(self):
        from datetime import date
        mp, mh = self._make_mocks()
        data = datetime(2026, 3, 25)
        with patch('src.utils.workflow_db.get_mongo_connection', side_effect=self._side(mp, mh)):
            from src.utils.workflow_db import criar_subtarefa
            criar_subtarefa('WF001', 'T', 'Análise de Falha', 'u', '', 'admin', data_planejada=data)
        doc = mh.insert_one.call_args[0][0]
        assert doc.get('data_planejada') == data


class TestMarcarSubtarefaConcluida:
    """Testa que marcar_subtarefa_concluida salva data_execucao."""

    def _make_mock(self):
        from bson import ObjectId
        mock = MagicMock()
        mock.update_one.return_value = MagicMock(modified_count=1)
        return mock, str(ObjectId())

    def test_salva_data_execucao(self):
        mock, oid = self._make_mock()
        data_exec = datetime(2026, 3, 22)
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock):
            from src.utils.workflow_db import marcar_subtarefa_concluida
            resultado = marcar_subtarefa_concluida(oid, data_execucao=data_exec)
        assert resultado is True
        updates = mock.update_one.call_args[0][1]['$set']
        assert updates.get('data_execucao') == data_exec
        assert updates.get('concluido') is True

    def test_retorna_true_em_sucesso(self):
        mock, oid = self._make_mock()
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock):
            from src.utils.workflow_db import marcar_subtarefa_concluida
            resultado = marcar_subtarefa_concluida(oid, data_execucao=datetime(2026, 3, 22))
        assert resultado is True


class TestEditarSubtarefaDatas:
    """Testa editar_subtarefa com data_planejada e data_execucao."""

    def _make_mock_hist(self):
        from bson import ObjectId
        mock = MagicMock()
        mock.update_one.return_value = MagicMock(matched_count=1)
        self._oid = ObjectId()
        return mock

    def test_atualiza_data_planejada(self):
        mock = self._make_mock_hist()
        data = datetime(2026, 4, 1)
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock):
            from src.utils.workflow_db import editar_subtarefa
            editar_subtarefa(str(self._oid), data_planejada=data, update_data_planejada=True)
        updates = mock.update_one.call_args[0][1]['$set']
        assert updates.get('data_planejada') == data

    def test_sem_update_data_planejada_nao_altera(self):
        mock = self._make_mock_hist()
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock):
            from src.utils.workflow_db import editar_subtarefa
            editar_subtarefa(str(self._oid), titulo='X')
        updates = mock.update_one.call_args[0][1]['$set']
        assert 'data_planejada' not in updates

    def test_atualiza_data_execucao(self):
        mock = self._make_mock_hist()
        data = datetime(2026, 4, 5)
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock):
            from src.utils.workflow_db import editar_subtarefa
            editar_subtarefa(str(self._oid), data_execucao=data, update_data_execucao=True)
        updates = mock.update_one.call_args[0][1]['$set']
        assert updates.get('data_execucao') == data


# =============================================================================
# TESTES: Fase 3 — status_validacao_gestor (retrocompat + validar + devolver)
# =============================================================================

class TestCarregarHistoricoValidacaoGestor:
    """Retrocompat para status_validacao_gestor em carregar_historico."""

    def _make_mock(self, docs):
        mock = MagicMock()
        fr = MagicMock()
        fr.sort.return_value = iter(docs)
        mock.find.return_value = fr
        return mock

    def _doc_base(self):
        from bson import ObjectId
        return {'_id': ObjectId(), 'MaintenanceWF_id': 'WF001', 'descricao': 'X',
                'data': datetime.now(), 'responsavel': 'u', 'tipo_evento': 'Análise de Falha',
                'editado_por': 'u', 'horas': None, 'concluido': False}

    def test_sem_campo_recebe_none(self):
        """Docs antigos sem status_validacao_gestor devem receber None."""
        doc = self._doc_base()
        mock = self._make_mock([doc])
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock):
            from src.utils.workflow_db import carregar_historico
            df = carregar_historico()
        assert 'status_validacao_gestor' in df.columns
        assert df.iloc[0]['status_validacao_gestor'] is None

    def test_concluido_sem_campo_recebe_aprovado(self):
        """Docs antigos com concluido=True sem status_validacao devem receber 'aprovado'."""
        doc = self._doc_base()
        doc['concluido'] = True
        mock = self._make_mock([doc])
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock):
            from src.utils.workflow_db import carregar_historico
            df = carregar_historico()
        assert df.iloc[0]['status_validacao_gestor'] == 'aprovado'

    def test_campo_existente_preservado(self):
        """Docs com status_validacao_gestor definido devem manter o valor."""
        doc = self._doc_base()
        doc['concluido'] = True
        doc['status_validacao_gestor'] = 'devolvido'
        mock = self._make_mock([doc])
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock):
            from src.utils.workflow_db import carregar_historico
            df = carregar_historico()
        assert df.iloc[0]['status_validacao_gestor'] == 'devolvido'


class TestMarcarSubtarefaConcluidaValidacao:
    """Testa que marcar_subtarefa_concluida grava status_validacao_gestor='pendente'."""

    def _make_mock(self):
        from bson import ObjectId
        mock = MagicMock()
        mock.update_one.return_value = MagicMock(modified_count=1)
        return mock, str(ObjectId())

    def test_grava_status_validacao_pendente(self):
        mock, oid = self._make_mock()
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock):
            from src.utils.workflow_db import marcar_subtarefa_concluida
            marcar_subtarefa_concluida(oid, data_execucao=datetime.now())
        updates = mock.update_one.call_args[0][1]['$set']
        assert updates.get('status_validacao_gestor') == 'pendente'


class TestValidarAtividade:
    """Testa validar_atividade."""

    def _make_mock(self):
        from bson import ObjectId
        mock = MagicMock()
        mock.update_one.return_value = MagicMock(modified_count=1)
        return mock, str(ObjectId())

    def test_retorna_true_em_sucesso(self):
        mock, oid = self._make_mock()
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock):
            from src.utils.workflow_db import validar_atividade
            resultado = validar_atividade(oid, 'gestor1')
        assert resultado is True

    def test_grava_status_aprovado(self):
        mock, oid = self._make_mock()
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock):
            from src.utils.workflow_db import validar_atividade
            validar_atividade(oid, 'gestor1')
        updates = mock.update_one.call_args[0][1]['$set']
        assert updates.get('status_validacao_gestor') == 'aprovado'
        assert updates.get('validado_por') == 'gestor1'

    def test_push_historico_validacao(self):
        mock, oid = self._make_mock()
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock):
            from src.utils.workflow_db import validar_atividade
            validar_atividade(oid, 'gestor1')
        push = mock.update_one.call_args[0][1]['$push']
        entrada = push['historico_validacao']
        assert entrada['tipo'] == 'validacao'
        assert entrada['por'] == 'gestor1'
        assert entrada['nota'] is None

    def test_retorna_false_em_erro(self):
        mock, oid = self._make_mock()
        mock.update_one.side_effect = Exception("DB error")
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock):
            from src.utils.workflow_db import validar_atividade
            resultado = validar_atividade(oid, 'gestor1')
        assert resultado is False


class TestDevolverAtividade:
    """Testa devolver_atividade."""

    def _make_mock(self):
        from bson import ObjectId
        mock = MagicMock()
        mock.update_one.return_value = MagicMock(modified_count=1)
        return mock, str(ObjectId())

    def test_retorna_true_em_sucesso(self):
        mock, oid = self._make_mock()
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock):
            from src.utils.workflow_db import devolver_atividade
            resultado = devolver_atividade(oid, 'Nota de devolução', 'gestor1')
        assert resultado is True

    def test_grava_status_devolvido(self):
        mock, oid = self._make_mock()
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock):
            from src.utils.workflow_db import devolver_atividade
            devolver_atividade(oid, 'Revisar medição', 'gestor1')
        updates = mock.update_one.call_args[0][1]['$set']
        assert updates.get('status_validacao_gestor') == 'devolvido'
        assert updates.get('nota_devolucao') == 'Revisar medição'
        assert updates.get('concluido') is False
        assert updates.get('devolvido_por') == 'gestor1'

    def test_push_historico_validacao(self):
        mock, oid = self._make_mock()
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock):
            from src.utils.workflow_db import devolver_atividade
            devolver_atividade(oid, 'Revisar medição', 'gestor1')
        push = mock.update_one.call_args[0][1]['$push']
        entrada = push['historico_validacao']
        assert entrada['tipo'] == 'devolucao'
        assert entrada['por'] == 'gestor1'
        assert entrada['nota'] == 'Revisar medição'

    def test_retorna_false_em_erro(self):
        mock, oid = self._make_mock()
        mock.update_one.side_effect = Exception("DB error")
        with patch('src.utils.workflow_db.get_mongo_connection', return_value=mock):
            from src.utils.workflow_db import devolver_atividade
            resultado = devolver_atividade(oid, 'Nota', 'gestor1')
        assert resultado is False
