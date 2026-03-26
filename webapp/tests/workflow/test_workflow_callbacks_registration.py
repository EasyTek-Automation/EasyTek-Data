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

    def test_com_filtro_data_exibe_todas_horas_da_demanda_visivel(self, df_pend, df_hist):
        """Com filtro 18/03, card deve exibir TODAS as horas da demanda visível (5:30, não 3:30).

        O filtro de data determina quais demandas aparecem — WF001 aparece porque tem
        atividade em 18/03. Uma vez visível, o KPI soma TODAS as suas horas (10/03 + 18/03 = 5:30).
        Filtrar o histórico por data dentro do card causava o bug relatado em 2026-03-26:
        logs com data=hoje eram excluídos mesmo com atividade-pai dentro do período.
        """
        from src.callbacks_registers.workflow_callbacks import _kpi_filtrado
        filtros = {'tipo_data': ['subtarefa'], 'data_inicio': '2026-03-18', 'data_fim': '2026-03-18'}
        resultado = _kpi_filtrado(df_pend, df_hist, None, filtros=filtros)
        resultado_str = str(resultado)
        assert '5:30' in resultado_str

    def test_filtro_tipo_tarefa_nao_filtra_historico(self, df_pend, df_hist):
        """filtros com tipo_data='tarefa' não deve filtrar as horas do histórico."""
        from src.callbacks_registers.workflow_callbacks import _kpi_filtrado
        filtros = {'tipo_data': ['tarefa'], 'data_inicio': '2026-03-18', 'data_fim': '2026-03-18'}
        resultado = _kpi_filtrado(df_pend, df_hist, None, filtros=filtros)
        assert '5:30' in str(resultado)
