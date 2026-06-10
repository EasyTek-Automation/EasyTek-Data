"""Testes da Feature Reagendamento de plano (BR-19 / SP-16 / DS-16).

Cobre a parte de maior risco: a transação atômica do `reschedule_project`
(tudo-ou-nada nas 4 coleções + auditoria), o tratamento de "sem mudança",
o caminho de erro de transação não suportada, e a prévia sem gravação.

Mock pattern: patch.object em `gantt_db._collect_project_subtree`,
`gantt_db.get_mongo_client`, `gantt_db._col` e `gantt_db._detect_cross_project_conflicts`
para isolar a lógica de orquestração sem um MongoDB real.
"""

from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

from src.utils import gantt_db


# ---------------------------------------------------------------------------
# Fakes de sessão/transação pymongo
# ---------------------------------------------------------------------------

class _FakeTxn:
    """Context manager de transação — propaga exceção (não suprime) para o
    bloco try/except externo, simulando rollback automático do pymongo."""
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def start_transaction(self):
        return _FakeTxn()


class _FakeClient:
    def start_session(self):
        return _FakeSession()


def _subtree():
    """Subárvore fake com 2 categorias, 3 atividades, 4 atribuições."""
    return {
        "projeto":       {"_id": "P1", "nome": "Parada Forno", "data_hora_inicio": datetime(2026, 6, 2, 8, 0)},
        "pid":           "P1",
        "categoria_ids": ["C1", "C2"],
        "atividade_ids": ["A1", "A2", "A3"],
        "atribuicoes":   [{"_id": f"S{i}"} for i in range(4)],
        "contagens":     {"categorias": 2, "atividades": 3, "atribuicoes": 4},
    }


def _col_dispatcher():
    """Retorna (dispatcher, mocks) — _col(name) → MagicMock por coleção."""
    mocks = {n: MagicMock(name=n) for n in
             ("gantt_projects", "gantt_categories", "gantt_activities",
              "gantt_assignments", "gantt_audit_log")}
    return (lambda name: mocks.get(name, MagicMock())), mocks


# ---------------------------------------------------------------------------
# reschedule_project — caminho feliz (transação completa)
# ---------------------------------------------------------------------------

def test_reschedule_aplica_4_colecoes_e_auditoria_em_transacao():
    dispatcher, mocks = _col_dispatcher()
    novo = datetime(2026, 6, 4, 8, 0)  # +2 dias
    with patch.object(gantt_db, "_collect_project_subtree", return_value=_subtree()), \
         patch.object(gantt_db, "get_mongo_client", return_value=_FakeClient()), \
         patch.object(gantt_db, "_col", side_effect=dispatcher), \
         patch.object(gantt_db, "_detect_cross_project_conflicts", return_value=[]):
        result = gantt_db.reschedule_project("P1", novo, usuario_id="u1", usuario_nome="Rod")

    assert result["ok"] is True
    # projeto: update_one 1x; categorias/atividades/atribuições: update_many 1x cada
    assert mocks["gantt_projects"].update_one.call_count == 1
    assert mocks["gantt_categories"].update_many.call_count == 1
    assert mocks["gantt_activities"].update_many.call_count == 1
    assert mocks["gantt_assignments"].update_many.call_count == 1
    # auditoria inserida na mesma transação
    assert mocks["gantt_audit_log"].insert_one.call_count == 1
    # todas as escritas recebem o mesmo session= (transação)
    sess = mocks["gantt_projects"].update_one.call_args.kwargs["session"]
    assert mocks["gantt_assignments"].update_many.call_args.kwargs["session"] is sess
    assert mocks["gantt_audit_log"].insert_one.call_args.kwargs["session"] is sess


def test_reschedule_usa_dateadd_com_delta_em_ms():
    dispatcher, mocks = _col_dispatcher()
    novo = datetime(2026, 6, 2, 10, 0)  # +2 h = 7_200_000 ms
    with patch.object(gantt_db, "_collect_project_subtree", return_value=_subtree()), \
         patch.object(gantt_db, "get_mongo_client", return_value=_FakeClient()), \
         patch.object(gantt_db, "_col", side_effect=dispatcher), \
         patch.object(gantt_db, "_detect_cross_project_conflicts", return_value=[]):
        gantt_db.reschedule_project("P1", novo)

    pipeline = mocks["gantt_projects"].update_one.call_args.args[1]
    set_stage = pipeline[0]["$set"]
    add = set_stage["data_hora_inicio"]["$dateAdd"]
    assert add["unit"] == "millisecond"
    assert add["amount"] == 7_200_000


# ---------------------------------------------------------------------------
# reschedule_project — sem mudança / rollback / transação não suportada
# ---------------------------------------------------------------------------

def test_reschedule_sem_mudanca_nao_grava():
    dispatcher, mocks = _col_dispatcher()
    igual = datetime(2026, 6, 2, 8, 0)  # == inicio atual
    with patch.object(gantt_db, "_collect_project_subtree", return_value=_subtree()), \
         patch.object(gantt_db, "get_mongo_client", return_value=_FakeClient()), \
         patch.object(gantt_db, "_col", side_effect=dispatcher):
        result = gantt_db.reschedule_project("P1", igual)

    assert result["ok"] is False
    assert result.get("sem_mudanca") is True
    mocks["gantt_projects"].update_one.assert_not_called()


def test_reschedule_rollback_em_falha_no_meio():
    """Se uma escrita falha no meio, a exceção propaga e nada é confirmado."""
    dispatcher, mocks = _col_dispatcher()
    mocks["gantt_assignments"].update_many.side_effect = RuntimeError("boom")
    novo = datetime(2026, 6, 4, 8, 0)
    with patch.object(gantt_db, "_collect_project_subtree", return_value=_subtree()), \
         patch.object(gantt_db, "get_mongo_client", return_value=_FakeClient()), \
         patch.object(gantt_db, "_col", side_effect=dispatcher), \
         patch.object(gantt_db, "_detect_cross_project_conflicts", return_value=[]):
        result = gantt_db.reschedule_project("P1", novo)

    assert result["ok"] is False
    assert "boom" in result["erro"]


def test_reschedule_transacao_nao_suportada_reporta_replica_set():
    dispatcher, _ = _col_dispatcher()

    class _NoTxnClient:
        def start_session(self):
            raise RuntimeError("Transaction numbers are only allowed on a replica set member or mongos")

    novo = datetime(2026, 6, 4, 8, 0)
    with patch.object(gantt_db, "_collect_project_subtree", return_value=_subtree()), \
         patch.object(gantt_db, "get_mongo_client", return_value=_NoTxnClient()), \
         patch.object(gantt_db, "_col", side_effect=dispatcher), \
         patch.object(gantt_db, "_detect_cross_project_conflicts", return_value=[]):
        result = gantt_db.reschedule_project("P1", novo)

    assert result["ok"] is False
    assert "replica set" in result["erro"].lower()


# ---------------------------------------------------------------------------
# preview_reschedule_project
# ---------------------------------------------------------------------------

def test_preview_calcula_delta_e_contagens_sem_gravar():
    dispatcher, mocks = _col_dispatcher()
    novo = datetime(2026, 6, 5, 8, 0)  # +3 dias
    with patch.object(gantt_db, "_collect_project_subtree", return_value=_subtree()), \
         patch.object(gantt_db, "_col", side_effect=dispatcher), \
         patch.object(gantt_db, "_detect_cross_project_conflicts", return_value=[]):
        prev = gantt_db.preview_reschedule_project("P1", novo)

    assert prev["sem_mudanca"] is False
    assert prev["delta_segundos"] == timedelta(days=3).total_seconds()
    assert prev["contagens"] == {"categorias": 2, "atividades": 3, "atribuicoes": 4}
    # prévia não grava
    mocks["gantt_projects"].update_one.assert_not_called()
    mocks["gantt_assignments"].update_many.assert_not_called()


def test_preview_sem_mudanca_marca_flag():
    dispatcher, _ = _col_dispatcher()
    igual = datetime(2026, 6, 2, 8, 0)
    with patch.object(gantt_db, "_collect_project_subtree", return_value=_subtree()), \
         patch.object(gantt_db, "_col", side_effect=dispatcher):
        prev = gantt_db.preview_reschedule_project("P1", igual)

    assert prev["sem_mudanca"] is True
    assert prev["conflitos"] == []


# ---------------------------------------------------------------------------
# Detecção de conflito cross-projeto (critério de sobreposição)
# ---------------------------------------------------------------------------

def test_detecta_conflito_cross_projeto_apos_shift():
    """Atribuição interna deslocada passa a sobrepor uma externa do mesmo
    funcionário em outro projeto → conflito. Interna do próprio projeto é
    excluída (mesmo funcionário, mas não conta)."""
    interna = {
        "_id": "S_int", "funcionario_id": "F1", "atividade_id": "A_int",
        "data_hora_entrada": datetime(2026, 6, 2, 8, 0),
        "data_hora_saida":   datetime(2026, 6, 2, 12, 0),
    }
    externa = {
        "_id": "S_ext", "funcionario_id": "F1", "atividade_id": "A_ext",
        "data_hora_entrada": datetime(2026, 6, 4, 10, 0),
        "data_hora_saida":   datetime(2026, 6, 4, 14, 0),
    }
    subtree = {"atribuicoes": [interna]}

    asg_col = MagicMock()
    # find por funcionario retorna interna + externa
    asg_col.find.return_value = [interna, externa]

    def dispatcher(name):
        return asg_col if name == "gantt_assignments" else None

    # delta = +2 dias → interna vira 04/06 08:00–12:00, NÃO sobrepõe externa 10:00–14:00? 12:00>10:00 → sobrepõe
    with patch.object(gantt_db, "_col", side_effect=dispatcher), \
         patch.object(gantt_db, "_enrich_conflicts", side_effect=lambda raw: raw):
        conflitos = gantt_db._detect_cross_project_conflicts(subtree, timedelta(days=2))

    assert len(conflitos) == 1
    assert conflitos[0]["atribuicao_id"] == "S_int"
    assert conflitos[0]["atribuicao_externa_id"] == "S_ext"


def test_sem_conflito_quando_nao_sobrepoe():
    interna = {
        "_id": "S_int", "funcionario_id": "F1", "atividade_id": "A_int",
        "data_hora_entrada": datetime(2026, 6, 2, 8, 0),
        "data_hora_saida":   datetime(2026, 6, 2, 9, 0),
    }
    externa = {
        "_id": "S_ext", "funcionario_id": "F1", "atividade_id": "A_ext",
        "data_hora_entrada": datetime(2026, 6, 4, 18, 0),
        "data_hora_saida":   datetime(2026, 6, 4, 20, 0),
    }
    subtree = {"atribuicoes": [interna]}
    asg_col = MagicMock()
    asg_col.find.return_value = [interna, externa]

    def dispatcher(name):
        return asg_col if name == "gantt_assignments" else None

    with patch.object(gantt_db, "_col", side_effect=dispatcher), \
         patch.object(gantt_db, "_enrich_conflicts", side_effect=lambda raw: raw):
        conflitos = gantt_db._detect_cross_project_conflicts(subtree, timedelta(days=2))

    assert conflitos == []


# ---------------------------------------------------------------------------
# Render do destaque .gantt-conflict (DS-17 §4) — prova determinística
# ---------------------------------------------------------------------------

def _all_classnames(comp, acc=None):
    """Coleta recursivamente todos os className do tree de componentes Dash."""
    if acc is None:
        acc = []
    cn = getattr(comp, "className", None)
    if isinstance(cn, str) and cn:
        acc.append(cn)
    ch = getattr(comp, "children", None)
    if isinstance(ch, (list, tuple)):
        for c in ch:
            _all_classnames(c, acc)
    elif ch is not None and hasattr(ch, "children"):
        _all_classnames(ch, acc)
    return acc


def _minimal_gantt_data():
    """Projeto/categoria/atividade/atribuição in-window (datas relativas a 'agora')."""
    from src.components import gantt_chart
    base = (datetime.utcnow() - timedelta(hours=3)) + timedelta(days=1)
    proj = {"_id": "P1", "nome": "Proj", "tipo": "Parada Corretiva",
            "data_hora_inicio": base, "data_hora_fim": base + timedelta(days=2)}
    cat = {"_id": "C1", "nome": "Cat", "projeto_id": "P1",
           "data_hora_inicio": base, "data_hora_fim": base + timedelta(days=2)}
    act = {"_id": "A1", "titulo": "Ativ", "categoria_id": "C1", "progresso_real": 0,
           "observacao": "", "data_hora_inicio": base, "data_hora_fim": base + timedelta(hours=6)}
    asg = {"_id": "S1", "atividade_id": "A1", "funcionario_id": "E1",
           "data_hora_entrada": base, "data_hora_saida": base + timedelta(hours=2)}
    emp = {"_id": "E1", "nome": "João"}
    return gantt_chart, [cat], [act], [asg], [proj], [emp]


def test_render_aplica_gantt_conflict_quando_atribuicao_em_conflito():
    gc, cats, acts, asgs, projs, emps = _minimal_gantt_data()
    tree = gc.build_gantt_chart(
        cats, acts, asgs, granularity="dias", projects=projs, employees=emps,
        conflict_ids=[{"atribuicao_id": "S1", "projeto_externo": "Proj Externo"}])
    classes = _all_classnames(tree)
    assert "gantt-conflict" in classes, "barra da atribuição em conflito deveria ter .gantt-conflict"
    assert "gantt-conflict-flag" in classes, "⚠ deveria aparecer na coluna esquerda"


def test_render_sem_conflito_nao_aplica_classe():
    gc, cats, acts, asgs, projs, emps = _minimal_gantt_data()
    tree = gc.build_gantt_chart(
        cats, acts, asgs, granularity="dias", projects=projs, employees=emps,
        conflict_ids=[])
    classes = _all_classnames(tree)
    assert "gantt-conflict" not in classes
    assert "gantt-conflict-flag" not in classes
