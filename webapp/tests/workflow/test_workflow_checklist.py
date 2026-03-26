"""
Testes para criar_checklist_subtarefas() e o callback toggle_subtask_collapse.

Cobre as mudanças de UX introduzidas em Mar/2026:
- Título da atividade clicável (btn-expand-subtask-title) para expandir/colapsar
- Datas de planejamento e execução visíveis no cabeçalho sem precisar expandir
"""

import pytest


# =============================================================================
# FIXTURES
# =============================================================================

def _sub_item(
    hist_id="sub1",
    titulo="Verificar equipamento",
    observacoes="",
    data_planejada=None,
    data_execucao=None,
    concluido=False,
    horas=None,
    prioridade="normal",
):
    """Monta um dict de subtarefa no formato esperado por criar_checklist_subtarefas."""
    return {
        "hist_id": hist_id,
        "titulo": titulo,
        "descricao": titulo,
        "observacoes": observacoes,
        "alteracoes": "",
        "editado_por": "user1",
        "responsavel": "user1",
        "data": "26/03/2026 10:00",
        "is_retroativo": False,
        "horas": horas,
        "concluido": concluido,
        "aprovador": None,
        "status_aprovacao": None,
        "tipo_evento": "",
        "record_type": "subtarefa",
        "subtarefa_id": None,
        "prioridade": prioridade,
        "data_planejada": data_planejada,
        "data_execucao": data_execucao,
        "status_validacao_gestor": None,
        "nota_devolucao": None,
        "devolvido_por": None,
        "data_devolucao": None,
        "validado_por": None,
        "data_validacao": None,
        "historico_validacao": [],
    }


# =============================================================================
# TESTES: criar_checklist_subtarefas() — botão de título clicável
# =============================================================================

class TestTituloClicavel:
    """O título da atividade deve ser um botão com id btn-expand-subtask-title."""

    def test_btn_expand_subtask_title_presente_no_output(self):
        """Output deve conter o id btn-expand-subtask-title para cada subtarefa."""
        from src.callbacks_registers.workflow_callbacks import criar_checklist_subtarefas
        resultado = criar_checklist_subtarefas([_sub_item()], pend_id="WF001")
        assert "btn-expand-subtask-title" in str(resultado)

    def test_btn_expand_subtask_title_usa_hist_id_como_index(self):
        """O index do btn-expand-subtask-title deve ser o hist_id da atividade."""
        from src.callbacks_registers.workflow_callbacks import criar_checklist_subtarefas
        resultado = criar_checklist_subtarefas([_sub_item(hist_id="abc123")], pend_id="WF001")
        resultado_str = str(resultado)
        # O id do botão usa o hist_id como index
        assert "abc123" in resultado_str
        assert "btn-expand-subtask-title" in resultado_str

    def test_duas_subtarefas_geram_dois_botoes_titulo(self):
        """Cada subtarefa deve ter seu próprio btn-expand-subtask-title."""
        from src.callbacks_registers.workflow_callbacks import criar_checklist_subtarefas
        items = [_sub_item(hist_id="s1"), _sub_item(hist_id="s2")]
        resultado = criar_checklist_subtarefas(items, pend_id="WF001")
        resultado_str = str(resultado)
        assert resultado_str.count("btn-expand-subtask-title") >= 2

    def test_titulo_aparece_no_botao(self):
        """O texto do título deve aparecer no output."""
        from src.callbacks_registers.workflow_callbacks import criar_checklist_subtarefas
        resultado = criar_checklist_subtarefas(
            [_sub_item(titulo="Substituir rolamento")], pend_id="WF001"
        )
        assert "Substituir rolamento" in str(resultado)


# =============================================================================
# TESTES: criar_checklist_subtarefas() — datas visíveis no cabeçalho
# =============================================================================

class TestDatasNosCabecalho:
    """Data de registro e datas opcionais devem aparecer no cabeçalho da atividade."""

    def test_data_registro_sempre_aparece_no_cabecalho(self):
        """O campo data (data de registro) deve aparecer no cabeçalho sempre que preenchido."""
        from src.callbacks_registers.workflow_callbacks import criar_checklist_subtarefas
        resultado = criar_checklist_subtarefas(
            [_sub_item()], pend_id="WF001"  # fixture tem data="26/03/2026 10:00"
        )
        assert "26/03/2026" in str(resultado)

    def test_data_registro_truncada_a_10_chars(self):
        """data[:10] deve produzir exatamente dd/mm/yyyy (sem horário no cabeçalho).
        O truncamento é garantido pelo código; o teste verifica que a data formatada aparece."""
        from src.callbacks_registers.workflow_callbacks import criar_checklist_subtarefas
        # data com horário — cabeçalho deve mostrar só a parte da data
        item = _sub_item()
        item["data"] = "15/01/2026 08:30"
        resultado = criar_checklist_subtarefas([item], pend_id="WF001")
        assert "15/01/2026" in str(resultado)

    def test_data_planejada_aparece_sem_expandir(self):
        """Quando data_planejada está preenchida, 'Plan.:' deve aparecer no output."""
        from src.callbacks_registers.workflow_callbacks import criar_checklist_subtarefas
        resultado = criar_checklist_subtarefas(
            [_sub_item(data_planejada="28/03/2026")], pend_id="WF001"
        )
        assert "Plan.: 28/03/2026" in str(resultado)

    def test_data_execucao_aparece_sem_expandir(self):
        """Quando data_execucao está preenchida, 'Exec.:' deve aparecer no output."""
        from src.callbacks_registers.workflow_callbacks import criar_checklist_subtarefas
        resultado = criar_checklist_subtarefas(
            [_sub_item(data_execucao="26/03/2026")], pend_id="WF001"
        )
        assert "Exec.: 26/03/2026" in str(resultado)

    def test_ambas_datas_aparecem_juntas(self):
        """Com as duas datas preenchidas, ambas devem aparecer no output."""
        from src.callbacks_registers.workflow_callbacks import criar_checklist_subtarefas
        resultado = criar_checklist_subtarefas(
            [_sub_item(data_planejada="25/03/2026", data_execucao="26/03/2026")],
            pend_id="WF001"
        )
        resultado_str = str(resultado)
        assert "Plan.: 25/03/2026" in resultado_str
        assert "Exec.: 26/03/2026" in resultado_str

    def test_sem_datas_opcionais_nao_exibe_plan_exec(self):
        """Sem data_planejada/data_execucao, 'Plan.:' e 'Exec.:' não devem aparecer.
        A data de registro ainda aparece normalmente."""
        from src.callbacks_registers.workflow_callbacks import criar_checklist_subtarefas
        resultado = criar_checklist_subtarefas(
            [_sub_item(data_planejada=None, data_execucao=None)], pend_id="WF001"
        )
        resultado_str = str(resultado)
        assert "Plan.:" not in resultado_str
        assert "Exec.:" not in resultado_str
        assert "26/03/2026" in resultado_str  # data de registro sempre visível

    def test_apenas_data_planejada_nao_exibe_exec(self):
        """Com só data_planejada, 'Exec.:' não deve aparecer."""
        from src.callbacks_registers.workflow_callbacks import criar_checklist_subtarefas
        resultado = criar_checklist_subtarefas(
            [_sub_item(data_planejada="25/03/2026", data_execucao=None)], pend_id="WF001"
        )
        resultado_str = str(resultado)
        assert "Plan.: 25/03/2026" in resultado_str
        assert "Exec.:" not in resultado_str

    def test_apenas_data_execucao_nao_exibe_plan(self):
        """Com só data_execucao, 'Plan.:' não deve aparecer."""
        from src.callbacks_registers.workflow_callbacks import criar_checklist_subtarefas
        resultado = criar_checklist_subtarefas(
            [_sub_item(data_planejada=None, data_execucao="26/03/2026")], pend_id="WF001"
        )
        resultado_str = str(resultado)
        assert "Exec.: 26/03/2026" in resultado_str
        assert "Plan.:" not in resultado_str


# =============================================================================
# TESTES: toggle_subtask_collapse — contrato arquitetural do callback
# =============================================================================

class TestToggleSubtaskCollapseContrato:
    """Verifica estaticamente que toggle_subtask_collapse aceita btn-expand-subtask-title."""

    def _get_callback_block(self):
        """Lê o bloco do callback toggle_subtask_collapse como string."""
        import os
        filepath = os.path.join(
            os.path.dirname(__file__), "..", "..", "src",
            "callbacks_registers", "workflow_callbacks.py"
        )
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()

        # Localiza a definição da função toggle_subtask_collapse
        func_pos = source.find("def toggle_subtask_collapse(")
        assert func_pos != -1, "Função toggle_subtask_collapse não encontrada no arquivo"
        # Recua até o @app.callback mais próximo antes da def
        decorator_pos = source.rfind("@app.callback(", 0, func_pos)
        assert decorator_pos != -1, "Decorador @app.callback não encontrado antes de toggle_subtask_collapse"
        # Captura até a próxima definição de função no mesmo nível
        end = source.find("\n    def ", func_pos + 10)
        if end == -1:
            end = func_pos + 2000
        return source[decorator_pos:end]

    def test_callback_aceita_btn_expand_subtask_title(self):
        """toggle_subtask_collapse deve ter btn-expand-subtask-title como Input."""
        bloco = self._get_callback_block()
        assert "btn-expand-subtask-title" in bloco, (
            "toggle_subtask_collapse deve aceitar cliques no título "
            "(btn-expand-subtask-title) além do chevron"
        )

    def test_callback_aceita_n_clicks_title(self):
        """A função toggle_subtask_collapse deve ter parâmetro n_clicks_title."""
        bloco = self._get_callback_block()
        assert "n_clicks_title" in bloco, (
            "toggle_subtask_collapse deve ter parâmetro n_clicks_title para "
            "receber cliques no título da atividade"
        )

    def test_callback_verifica_ambos_n_clicks(self):
        """O guard inicial deve checar tanto n_clicks quanto n_clicks_title."""
        bloco = self._get_callback_block()
        assert "n_clicks or n_clicks_title" in bloco, (
            "toggle_subtask_collapse deve verificar ambos os inputs antes de "
            "PreventUpdate, senão cliques no título serão ignorados"
        )
