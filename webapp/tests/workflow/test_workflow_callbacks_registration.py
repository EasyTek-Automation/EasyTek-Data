"""
Teste de integração: registro dos callbacks do Workflow.

Verifica que register_workflow_callbacks() e register_edit_callbacks() e
register_create_callbacks() completam sem erros de configuração do Dash,
como DuplicateCallback (allow_duplicate sem prevent_initial_call) ou
conflitos de Output.

Este teste pega exatamente a classe de erro que os testes de unidade não
cobrem: erros de inicialização do app Dash em runtime.
"""
import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import MagicMock, patch


def _make_app():
    """Cria Dash app mínimo para testes de registro de callbacks."""
    import dash
    import dash_bootstrap_components as dbc
    app = dash.Dash(
        __name__,
        suppress_callback_exceptions=True,
        external_stylesheets=[dbc.themes.BOOTSTRAP]
    )
    return app


def _make_user_mock(level=1, perfil='manutencao', username='testuser'):
    """Cria mock do current_user para layout que usa flask_login."""
    user = MagicMock()
    user.is_authenticated = True
    user.level = level
    user.perfil = perfil
    user.username = username
    return user


# =============================================================================
# TESTES: Registro de callbacks (smoke tests de inicialização)
# =============================================================================

class TestRegistroCallbacksWorkflow:
    """Testa que os callbacks registram sem erro de configuração Dash."""

    def test_register_workflow_callbacks_nao_levanta_excecao(self):
        """register_workflow_callbacks() deve completar sem DuplicateCallback ou similar."""
        app = _make_app()

        from src.callbacks_registers.workflow_callbacks import register_workflow_callbacks

        # Se levantar qualquer exceção aqui, o app não sobe em produção
        try:
            register_workflow_callbacks(app)
        except Exception as e:
            pytest.fail(f"register_workflow_callbacks() falhou: {type(e).__name__}: {e}")

    def test_register_edit_callbacks_nao_levanta_excecao(self):
        """register_edit_callbacks() deve completar sem erro."""
        app = _make_app()

        # Registrar workflow primeiro (edit depende dos mesmos Outputs com allow_duplicate)
        from src.callbacks_registers.workflow_callbacks import register_workflow_callbacks
        from src.callbacks_registers.workflow_edit_callbacks import register_edit_callbacks

        try:
            register_workflow_callbacks(app)
            register_edit_callbacks(app)
        except Exception as e:
            pytest.fail(f"register_edit_callbacks() falhou: {type(e).__name__}: {e}")

    def test_register_create_callbacks_nao_levanta_excecao(self):
        """register_create_callbacks() deve completar sem erro."""
        app = _make_app()

        from src.callbacks_registers.workflow_callbacks import register_workflow_callbacks
        from src.callbacks_registers.workflow_edit_callbacks import register_edit_callbacks
        from src.callbacks_registers.workflow_create_callbacks import register_create_callbacks

        try:
            register_workflow_callbacks(app)
            register_edit_callbacks(app)
            register_create_callbacks(app)
        except Exception as e:
            pytest.fail(f"register_create_callbacks() falhou: {type(e).__name__}: {e}")

    def test_todos_callbacks_juntos_sem_conflito(self):
        """Registrar todos os callbacks workflow juntos não deve gerar conflito."""
        app = _make_app()

        from src.callbacks_registers.workflow_callbacks import register_workflow_callbacks
        from src.callbacks_registers.workflow_edit_callbacks import register_edit_callbacks
        from src.callbacks_registers.workflow_create_callbacks import register_create_callbacks

        try:
            register_workflow_callbacks(app)
            register_edit_callbacks(app)
            register_create_callbacks(app)
        except Exception as e:
            pytest.fail(
                f"Conflito de callbacks detectado: {type(e).__name__}: {e}\n"
                f"Verifique allow_duplicate=True sem prevent_initial_call=True."
            )

    def test_nao_ha_allow_duplicate_sem_prevent_initial_call(self):
        """
        Verifica estaticamente que não há Output com allow_duplicate=True
        em callbacks sem prevent_initial_call=True.

        Regra do Dash: allow_duplicate exige prevent_initial_call=True
        (ou 'initial_duplicate').
        """
        import ast
        import os

        callback_files = [
            "webapp/src/callbacks_registers/workflow_callbacks.py",
            "webapp/src/callbacks_registers/workflow_edit_callbacks.py",
            "webapp/src/callbacks_registers/workflow_create_callbacks.py",
        ]

        base = "/e/Projetos Python/AMG/AMG_Data"

        violacoes = []

        for rel_path in callback_files:
            filepath = os.path.join(base, rel_path)
            if not os.path.exists(filepath):
                continue

            with open(filepath, 'r', encoding='utf-8') as f:
                source = f.read()

            # Heurística simples: procurar blocos @app.callback com allow_duplicate
            # e verificar se prevent_initial_call está presente e não é False
            import re

            # Encontrar todos os decoradores @app.callback com seu conteúdo
            # (busca entre @app.callback( e def nome():)
            pattern = r'@app\.callback\((.*?)\)\s*\ndef\s+\w+'
            matches = re.findall(pattern, source, re.DOTALL)

            for match in matches:
                has_allow_dup = 'allow_duplicate=True' in match
                has_prevent = 'prevent_initial_call' in match
                has_prevent_false = 'prevent_initial_call=False' in match

                if has_allow_dup:
                    # allow_duplicate=True exige prevent_initial_call=True
                    if not has_prevent or has_prevent_false:
                        violacoes.append(
                            f"{rel_path}: callback com allow_duplicate=True "
                            f"mas sem prevent_initial_call=True"
                        )

        if violacoes:
            pytest.fail(
                "Callbacks inválidos (allow_duplicate sem prevent_initial_call):\n"
                + "\n".join(violacoes)
            )


# =============================================================================
# TESTES: _kpi_filtrado() — filtros de data no card de horas
# =============================================================================

class TestKpiFiltrado:
    """Testa que _kpi_filtrado aplica filtros de data ao histórico dos cards KPI."""

    @pytest.fixture
    def df_pend(self):
        return pd.DataFrame([{
            'id': 'WF001', 'descricao': 'Demanda teste', 'responsavel': 'user1',
            'status': 'Em Andamento', 'data_criacao': datetime(2026, 3, 1),
            'status_aceite': 'aceito',
        }])

    @pytest.fixture
    def df_hist(self):
        """Histórico com atividade em 10/03 (2h) e em 18/03 (3.5h)."""
        return pd.DataFrame([
            {
                'hist_id': 'h1', 'pendencia_id': 'WF001', 'MaintenanceWF_id': 'WF001',
                'record_type': 'subtarefa', 'data': datetime(2026, 3, 10, 8, 0),
                'horas': 2.0, 'concluido': False, 'subtarefa_id': None,
                'aprovador': None, 'status_aprovacao': None, 'data_planejada': None,
            },
            {
                'hist_id': 'h2', 'pendencia_id': 'WF001', 'MaintenanceWF_id': 'WF001',
                'record_type': 'subtarefa', 'data': datetime(2026, 3, 18, 8, 0),
                'horas': 3.5, 'concluido': False, 'subtarefa_id': None,
                'aprovador': None, 'status_aprovacao': None, 'data_planejada': None,
            },
        ])

    def test_sem_filtros_totaliza_todas_horas(self, df_pend, df_hist):
        """Sem filtros, card horas deve exibir total de todas as atividades (5:30)."""
        from src.callbacks_registers.workflow_callbacks import _kpi_filtrado
        resultado = _kpi_filtrado(df_pend, df_hist, None)
        assert '5:30' in str(resultado)

    def test_com_filtro_data_totaliza_apenas_horas_do_periodo(self, df_pend, df_hist):
        """Com filtro 18/03, card horas deve exibir apenas 3:30 (não 5:30)."""
        from src.callbacks_registers.workflow_callbacks import _kpi_filtrado
        filtros = {'tipo_data': ['subtarefa'], 'data_inicio': '2026-03-18', 'data_fim': '2026-03-18'}
        resultado = _kpi_filtrado(df_pend, df_hist, None, filtros=filtros)
        resultado_str = str(resultado)
        assert '3:30' in resultado_str
        assert '5:30' not in resultado_str

    def test_filtro_tipo_tarefa_nao_filtra_historico(self, df_pend, df_hist):
        """filtros com tipo_data='tarefa' não deve filtrar as horas do histórico."""
        from src.callbacks_registers.workflow_callbacks import _kpi_filtrado
        filtros = {'tipo_data': ['tarefa'], 'data_inicio': '2026-03-18', 'data_fim': '2026-03-18'}
        resultado = _kpi_filtrado(df_pend, df_hist, None, filtros=filtros)
        assert '5:30' in str(resultado)

    def test_kpi_conta_15h_cenario_do_bug_relatado(self):
        """Regressão: 1 demanda, 3 atividades retroativas (semana passada), 3 logs de 5h cada.
        Filtro = semana das atividades. Card deve mostrar 15:00h, não 5:00h.

        Bug original: logs usavam datetime.now() como data (semana atual) e CB5 usava
        JSON roundtrip do store-historico. _normalizar_datas(utc=True) produzia Timestamps
        divergentes que excluíam logs válidos, resultando em apenas 5h no card.

        Fix: adicionar_log() herda data da atividade-pai + CB5 usa carregar_dados_csv().
        """
        from src.callbacks_registers.workflow_callbacks import _kpi_filtrado

        data_retroativa = datetime(2026, 3, 17, 12, 0, 0)  # semana passada

        df_pend = pd.DataFrame([{
            'id': 'WF001', 'descricao': 'Demanda', 'responsavel': 'user1',
            'status': 'Em Andamento', 'data_criacao': data_retroativa,
            'status_aceite': 'aceito',
        }])

        df_hist = pd.DataFrame([
            # A1: atividade retroativa semana passada
            {'hist_id': 'a1', 'MaintenanceWF_id': 'WF001', 'record_type': 'subtarefa',
             'data': data_retroativa, 'horas': None, 'concluido': False, 'subtarefa_id': None,
             'aprovador': None, 'status_aprovacao': None, 'data_planejada': None},
            # L1: log herda data da atividade-pai (semana passada, 5h)
            {'hist_id': 'l1', 'MaintenanceWF_id': 'WF001', 'record_type': 'log',
             'data': data_retroativa, 'horas': 5.0, 'concluido': False, 'subtarefa_id': 'a1',
             'aprovador': None, 'status_aprovacao': None, 'data_planejada': None},
            # A2: atividade retroativa semana passada
            {'hist_id': 'a2', 'MaintenanceWF_id': 'WF001', 'record_type': 'subtarefa',
             'data': data_retroativa, 'horas': None, 'concluido': False, 'subtarefa_id': None,
             'aprovador': None, 'status_aprovacao': None, 'data_planejada': None},
            # L2: log herda data da atividade-pai (semana passada, 5h)
            {'hist_id': 'l2', 'MaintenanceWF_id': 'WF001', 'record_type': 'log',
             'data': data_retroativa, 'horas': 5.0, 'concluido': False, 'subtarefa_id': 'a2',
             'aprovador': None, 'status_aprovacao': None, 'data_planejada': None},
            # A3: atividade retroativa semana passada
            {'hist_id': 'a3', 'MaintenanceWF_id': 'WF001', 'record_type': 'subtarefa',
             'data': data_retroativa, 'horas': None, 'concluido': False, 'subtarefa_id': None,
             'aprovador': None, 'status_aprovacao': None, 'data_planejada': None},
            # L3: log herda data da atividade-pai (semana passada, 5h)
            {'hist_id': 'l3', 'MaintenanceWF_id': 'WF001', 'record_type': 'log',
             'data': data_retroativa, 'horas': 5.0, 'concluido': False, 'subtarefa_id': 'a3',
             'aprovador': None, 'status_aprovacao': None, 'data_planejada': None},
        ])

        filtros = {
            'tipo_data': ['subtarefa'],
            'data_inicio': '2026-03-16',
            'data_fim': '2026-03-22',
        }
        resultado = _kpi_filtrado(df_pend, df_hist, None, filtros=filtros)
        assert '15:00' in str(resultado), \
            f"Card deve mostrar 15:00h (3 logs × 5h), mas retornou: {resultado}"


# =============================================================================
# TESTES: CB5 — contrato arquitetural (não usar JSON roundtrip para df_historico)
# =============================================================================

class TestCB5UsaDadosFrescos:
    """Verifica que atualizar_cards_kpi (CB5) carrega o histórico direto do MongoDB.

    Regressão: a versão buggada usava pd.DataFrame(historico_data), onde historico_data
    vinha do dcc.Store via JSON roundtrip. Isso fazia _normalizar_datas(utc=True) produzir
    Timestamps diferentes dos do MongoDB fresco, excluindo logs válidos do cálculo de KPI.

    Fix: CB5 chama carregar_dados_csv() diretamente, ignorando o conteúdo de historico_data
    para construir df_historico (o parâmetro historico_data ainda é usado como Input para
    disparar o callback quando os dados mudam).
    """

    def _get_cb5_body(self):
        """Lê e retorna o corpo da função atualizar_cards_kpi como string."""
        import os
        filepath = os.path.join(
            os.path.dirname(__file__), '..', '..', 'src',
            'callbacks_registers', 'workflow_callbacks.py'
        )
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Localiza a definição da função
        func_start = None
        for i, line in enumerate(lines):
            if 'def atualizar_cards_kpi(' in line:
                func_start = i
                break
        assert func_start is not None, "Função atualizar_cards_kpi não encontrada no arquivo"

        # Captura o corpo até a próxima def no mesmo nível de indentação
        indent = len(lines[func_start]) - len(lines[func_start].lstrip())
        body_lines = []
        for line in lines[func_start + 1:]:
            stripped = line.strip()
            if not stripped:
                continue
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= indent and stripped.startswith('def '):
                break
            body_lines.append(line)

        return ''.join(body_lines)

    def test_cb5_usa_carregar_dados_csv_para_df_historico(self):
        """CB5 deve chamar carregar_dados_csv() para obter df_historico fresco."""
        body = self._get_cb5_body()
        assert 'carregar_dados_csv()' in body, (
            "CB5 (atualizar_cards_kpi) deve chamar carregar_dados_csv() diretamente "
            "para obter df_historico fresco do MongoDB"
        )

    def test_cb5_nao_constroi_df_historico_do_store(self):
        """CB5 NÃO deve usar pd.DataFrame(historico_data) para construir df_historico.

        pd.DataFrame(historico_data) a partir do dcc.Store causa divergência de datas:
        o JSON roundtrip serializa pd.Timestamp para strings ISO, que _normalizar_datas
        converte com utc=True, produzindo Timestamps diferentes dos do MongoDB fresco.
        Resultado: logs válidos ficam fora dos ids_validos em _filtrar_hist_df_por_filtros.
        """
        body = self._get_cb5_body()
        assert 'pd.DataFrame(historico_data)' not in body, (
            "CB5 não deve usar pd.DataFrame(historico_data) para df_historico — "
            "isso causa divergência de datas no roundtrip JSON e produz KPIs incorretos. "
            "Use carregar_dados_csv() para dados frescos do MongoDB."
        )
