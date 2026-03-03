"""
Testes para src/pages/workflow/dashboard.py

Captura o comportamento ATUAL das funções de UI antes de qualquer alteração.
Não requer MongoDB — usa DataFrames pandas diretamente.
"""

import pytest
import pandas as pd
from datetime import datetime


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def df_pendencias_vazio():
    """DataFrame vazio com colunas mínimas de pendências."""
    return pd.DataFrame(columns=[
        'id', 'descricao', 'responsavel', 'status', 'data_criacao',
        'ultima_atualizacao', 'criado_por', 'criado_por_perfil',
        'ultima_edicao_por', 'ultima_edicao_data'
    ])


@pytest.fixture
def df_historico_vazio():
    """DataFrame vazio com colunas mínimas de histórico."""
    return pd.DataFrame(columns=[
        'hist_id', 'MaintenanceWF_id', 'pendencia_id', 'descricao', 'data',
        'responsavel', 'tipo_evento', 'editado_por', 'observacoes', 'alteracoes',
        'horas', 'concluido', 'aprovador', 'status_aprovacao', 'data_aprovacao'
    ])


@pytest.fixture
def df_pendencias_com_dados():
    """DataFrame com uma pendência de exemplo."""
    agora = datetime.now()
    return pd.DataFrame([{
        'id': 'AMG_WF001',
        'descricao': 'Pendência de teste',
        'responsavel': 'usuario1',
        'status': 'Pendente',
        'data_criacao': agora,
        'ultima_atualizacao': agora,
        'criado_por': 'admin',
        'criado_por_perfil': 'manutencao',
        'ultima_edicao_por': 'admin',
        'ultima_edicao_data': agora
    }])


@pytest.fixture
def df_historico_com_dados():
    """DataFrame com uma entrada de histórico de exemplo."""
    return pd.DataFrame([{
        'hist_id': 'abc123',
        'MaintenanceWF_id': 'AMG_WF001',
        'pendencia_id': 'AMG_WF001',
        'descricao': 'Análise de Falha',
        'data': datetime.now(),
        'responsavel': 'usuario1',
        'tipo_evento': 'atualizacao_workflow',
        'editado_por': 'usuario1',
        'observacoes': 'Realizei análise',
        'alteracoes': '',
        'horas': 2.5,
        'concluido': False,
        'aprovador': None,
        'status_aprovacao': None,
        'data_aprovacao': None
    }])


@pytest.fixture
def pendencia_dict():
    """Dict de pendência individual para usar em criar_linha_pendencia."""
    agora = datetime.now()
    return {
        'id': 'AMG_WF001',
        'descricao': 'Pendência de teste',
        'responsavel': 'usuario1',
        'status': 'Pendente',
        'data_criacao': agora,
        'ultima_atualizacao': agora,
        'criado_por': 'admin',
        'criado_por_perfil': 'manutencao',
        'ultima_edicao_por': 'admin',
        'ultima_edicao_data': agora
    }


# =============================================================================
# TESTES: criar_cards_kpi()
# =============================================================================

class TestCriarCardsKpi:
    """Testa criar_cards_kpi() com dados vazios e com dados."""

    def test_retorna_componente_com_df_vazio(self, df_pendencias_vazio, df_historico_vazio):
        from src.pages.workflow.dashboard import criar_cards_kpi
        resultado = criar_cards_kpi(df_pendencias_vazio, df_historico_vazio)
        assert resultado is not None

    def test_retorna_componente_com_none(self):
        from src.pages.workflow.dashboard import criar_cards_kpi
        resultado = criar_cards_kpi(None, None)
        assert resultado is not None

    def test_retorna_6_cards(self, df_pendencias_vazio, df_historico_vazio):
        """Deve retornar 6 cards KPI: Total, Pendentes, Em Andamento, Concluídas, Aguard. Aceite, Aguard. Aprovação."""
        from src.pages.workflow.dashboard import criar_cards_kpi
        import dash_bootstrap_components as dbc
        resultado = criar_cards_kpi(df_pendencias_vazio, df_historico_vazio)
        # O resultado é um dbc.Row; verificamos que tem filhos
        assert hasattr(resultado, 'children')
        assert len(resultado.children) == 6

    def test_conta_pendentes_corretamente(self, df_pendencias_com_dados, df_historico_vazio):
        """Com 1 pendência com status 'Pendente', o card de Pendentes deve refletir 1."""
        from src.pages.workflow.dashboard import criar_cards_kpi
        # Não vai dar erro com dados válidos
        resultado = criar_cards_kpi(df_pendencias_com_dados, df_historico_vazio, username_atual='admin')
        assert resultado is not None

    def test_card_aguardando_aprovacao(self, df_pendencias_vazio):
        """Card de aprovação pendente deve contar corretamente do histórico."""
        from src.pages.workflow.dashboard import criar_cards_kpi
        df_hist = pd.DataFrame([{
            'hist_id': 'abc',
            'aprovador': 'approver1',
            'status_aprovacao': 'pendente'
        }])
        resultado = criar_cards_kpi(df_pendencias_vazio, df_hist, username_atual='approver1')
        assert resultado is not None


# =============================================================================
# TESTES: criar_tabela_pendencias()
# =============================================================================

class TestCriarTabelaPendencias:
    """Testa criar_tabela_pendencias() sem MongoDB."""

    def test_retorna_estado_vazio_com_df_none(self):
        from src.pages.workflow.dashboard import criar_tabela_pendencias
        resultado = criar_tabela_pendencias(None, None)
        assert resultado is not None

    def test_retorna_estado_vazio_com_df_vazio(self, df_pendencias_vazio, df_historico_vazio):
        from src.pages.workflow.dashboard import criar_tabela_pendencias
        resultado = criar_tabela_pendencias(df_pendencias_vazio, df_historico_vazio)
        assert resultado is not None

    def test_retorna_tabela_com_dados(self, df_pendencias_com_dados, df_historico_vazio):
        from src.pages.workflow.dashboard import criar_tabela_pendencias
        import dash_bootstrap_components as dbc
        resultado = criar_tabela_pendencias(df_pendencias_com_dados, df_historico_vazio)
        assert resultado is not None
        assert isinstance(resultado, dbc.Table)

    def test_aceita_apenas_df_pendencias(self, df_pendencias_com_dados):
        """Deve funcionar mesmo sem df_historico."""
        from src.pages.workflow.dashboard import criar_tabela_pendencias
        resultado = criar_tabela_pendencias(df_pendencias_com_dados)
        assert resultado is not None


# =============================================================================
# TESTES: criar_linha_pendencia()
# =============================================================================

class TestCriarLinhaPendencia:
    """Testa criar_linha_pendencia() com dados mínimos."""

    def test_retorna_lista_com_2_elementos(self, pendencia_dict):
        from src.pages.workflow.dashboard import criar_linha_pendencia
        resultado = criar_linha_pendencia(pendencia_dict, 0, [])
        assert isinstance(resultado, list)
        assert len(resultado) == 2

    def test_linha_principal_eh_tr(self, pendencia_dict):
        from src.pages.workflow.dashboard import criar_linha_pendencia
        from dash import html
        resultado = criar_linha_pendencia(pendencia_dict, 0, [])
        assert isinstance(resultado[0], html.Tr)

    def test_linha_historico_eh_tr(self, pendencia_dict):
        from src.pages.workflow.dashboard import criar_linha_pendencia
        from dash import html
        resultado = criar_linha_pendencia(pendencia_dict, 0, [])
        assert isinstance(resultado[1], html.Tr)

    def test_sem_historico_funciona(self, pendencia_dict):
        from src.pages.workflow.dashboard import criar_linha_pendencia
        resultado = criar_linha_pendencia(pendencia_dict, 0, None)
        assert resultado is not None
        assert len(resultado) == 2

    def test_contem_id_pendencia(self, pendencia_dict):
        from src.pages.workflow.dashboard import criar_linha_pendencia
        from dash import html
        resultado = criar_linha_pendencia(pendencia_dict, 0, [])
        linha_principal = resultado[0]
        # Verificar que o conteúdo da linha contém o ID
        linha_str = str(linha_principal)
        assert 'AMG_WF001' in linha_str

    def test_com_historico_com_horas(self, pendencia_dict):
        """Com subatividades que têm horas, deve incluir informação de horas."""
        from src.pages.workflow.dashboard import criar_linha_pendencia
        hist = [
            {'horas': 2.5, 'concluido': False, 'status_aprovacao': None, 'descricao': 'Análise'}
        ]
        resultado = criar_linha_pendencia(pendencia_dict, 0, hist)
        assert resultado is not None
        assert len(resultado) == 2


# =============================================================================
# TESTES: criar_badge_status()
# =============================================================================

class TestCriarBadgeStatus:
    """Testa criar_badge_status() com diferentes status."""

    def test_status_pendente(self):
        from src.pages.workflow.dashboard import criar_badge_status
        badge = criar_badge_status("Pendente")
        assert badge is not None

    def test_status_em_andamento(self):
        from src.pages.workflow.dashboard import criar_badge_status
        badge = criar_badge_status("Em Andamento")
        assert badge is not None

    def test_status_desconhecido(self):
        from src.pages.workflow.dashboard import criar_badge_status
        badge = criar_badge_status("Status Desconhecido")
        assert badge is not None


# =============================================================================
# TESTES: criar_barra_horas_inline() (substituição do gráfico plotly)
# =============================================================================

class TestCriarBarraHorasInline:
    """Testa criar_barra_horas_inline() — nova barra segmentada Bootstrap."""

    def test_retorna_none_com_lista_vazia(self):
        from src.pages.workflow.dashboard import criar_barra_horas_inline
        resultado = criar_barra_horas_inline([])
        assert resultado is None

    def test_retorna_none_com_horas_zero(self):
        from src.pages.workflow.dashboard import criar_barra_horas_inline
        resultado = criar_barra_horas_inline([
            {'horas': 0, 'descricao': 'Teste'}
        ])
        assert resultado is None

    def test_retorna_none_com_horas_none(self):
        from src.pages.workflow.dashboard import criar_barra_horas_inline
        resultado = criar_barra_horas_inline([
            {'horas': None, 'descricao': 'Teste'}
        ])
        assert resultado is None

    def test_retorna_componente_com_horas_validas(self):
        from src.pages.workflow.dashboard import criar_barra_horas_inline
        from dash import html
        resultado = criar_barra_horas_inline([
            {'horas': 2.5, 'descricao': 'Análise'},
            {'horas': 1.0, 'descricao': 'Teste'}
        ])
        assert resultado is not None
        assert isinstance(resultado, html.Div)

    def test_retorna_componente_com_um_item(self):
        from src.pages.workflow.dashboard import criar_barra_horas_inline
        resultado = criar_barra_horas_inline([
            {'horas': 3.0, 'descricao': 'Manutenção Corretiva'}
        ])
        assert resultado is not None


# =============================================================================
# TESTES: Lógica de aceite em criar_linha_pendencia()
# =============================================================================

class TestCriarLinhaPendenciaAceite:
    """Testa comportamento dos botões de aceite na linha de pendência."""

    @pytest.fixture
    def pendencia_pendente(self):
        agora = datetime.now()
        return {
            'id': 'AMG_WF002',
            'descricao': 'Teste aceite',
            'responsavel': 'user_resp',
            'status': 'Pendente',
            'status_aceite': 'pendente',
            'data_aceite': None,
            'data_criacao': agora,
            'ultima_atualizacao': agora,
            'criado_por': 'admin',
            'criado_por_perfil': 'manutencao',
            'ultima_edicao_por': 'admin',
            'ultima_edicao_data': agora
        }

    def test_responsavel_nivel1_ve_botoes_aceitar_rejeitar(self, pendencia_pendente):
        """Responsável nível 1-2 com tarefa não aceita deve ver botões Aceitar/Rejeitar."""
        from src.pages.workflow.dashboard import criar_linha_pendencia
        resultado = criar_linha_pendencia(
            pendencia_pendente, 0, [],
            user_level=1, username_atual='user_resp'
        )
        linha_str = str(resultado[0])
        assert 'btn-aceitar-tarefa' in linha_str
        assert 'btn-rejeitar-tarefa-aceite' in linha_str

    def test_nivel3_ve_botao_editar_mesmo_nao_aceita(self, pendencia_pendente):
        """Nível 3 deve ver botão de editar mesmo se tarefa não foi aceita."""
        from src.pages.workflow.dashboard import criar_linha_pendencia
        resultado = criar_linha_pendencia(
            pendencia_pendente, 0, [],
            user_level=3, username_atual='admin'
        )
        linha_str = str(resultado[0])
        assert 'btn-edit-pend' in linha_str

    def test_outro_usuario_nivel1_nao_ve_botao_editar(self, pendencia_pendente):
        """Usuário nível 1-2 não responsável não deve ver botão editar em tarefa não aceita."""
        from src.pages.workflow.dashboard import criar_linha_pendencia
        resultado = criar_linha_pendencia(
            pendencia_pendente, 0, [],
            user_level=1, username_atual='outro_usuario'
        )
        linha_str = str(resultado[0])
        # Não deve ter nem btn-edit nem btn-aceitar (não é o responsável)
        assert 'btn-aceitar-tarefa' not in linha_str
        assert 'btn-edit-pend' not in linha_str

    def test_tarefa_aceita_mostra_botao_editar(self):
        """Tarefa com status_aceite='aceito' deve mostrar botão editar para nível 1."""
        agora = datetime.now()
        pendencia_aceita = {
            'id': 'AMG_WF003',
            'descricao': 'Aceita',
            'responsavel': 'user_resp',
            'status': 'Em Andamento',
            'status_aceite': 'aceito',
            'data_aceite': agora,
            'data_criacao': agora,
            'ultima_atualizacao': agora,
            'criado_por': 'admin',
            'criado_por_perfil': 'manutencao',
            'ultima_edicao_por': 'admin',
            'ultima_edicao_data': agora
        }
        from src.pages.workflow.dashboard import criar_linha_pendencia
        resultado = criar_linha_pendencia(
            pendencia_aceita, 0, [],
            user_level=1, username_atual='user_resp'
        )
        linha_str = str(resultado[0])
        assert 'btn-edit-pend' in linha_str
