# src/utils/gantt_db.py

from datetime import datetime
from bson import ObjectId
from src.database.connection import get_mongo_connection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize(doc):
    """Converte ObjectId para string e retorna cópia do documento."""
    if doc is None:
        return None
    d = dict(doc)
    d["_id"] = str(d["_id"])
    return d


def _col(name):
    return get_mongo_connection(name)


def _now():
    return datetime.utcnow()


# ---------------------------------------------------------------------------
# gantt_categories
# ---------------------------------------------------------------------------

def get_all_categories():
    """Retorna todas as categorias ordenadas por data_hora_inicio."""
    col = _col("gantt_categories")
    if col is None:
        return []
    return [_serialize(d) for d in col.find().sort("data_hora_inicio", 1)]


def get_category_by_id(category_id):
    """Retorna categoria por ID ou None."""
    col = _col("gantt_categories")
    if col is None:
        return None
    doc = col.find_one({"_id": ObjectId(category_id)})
    return _serialize(doc)


def create_category(data):
    """
    Insere nova categoria. Retorna o ID gerado como string.
    data: {"nome", "data_hora_inicio", "data_hora_fim"}
    """
    col = _col("gantt_categories")
    if col is None:
        return None
    doc = {
        "nome":             data["nome"],
        "data_hora_inicio": data["data_hora_inicio"],
        "data_hora_fim":    data["data_hora_fim"],
        "criado_em":        _now(),
        "atualizado_em":    _now(),
    }
    result = col.insert_one(doc)
    return str(result.inserted_id)


def update_category(category_id, data):
    """
    Atualiza campos da categoria. Retorna True se modificou.
    data: dict com campos a atualizar (nome, data_hora_inicio, data_hora_fim)
    """
    col = _col("gantt_categories")
    if col is None:
        return False
    allowed = ("nome", "data_hora_inicio", "data_hora_fim")
    update_fields = {k: v for k, v in data.items() if k in allowed}
    update_fields["atualizado_em"] = _now()
    result = col.update_one({"_id": ObjectId(category_id)}, {"$set": update_fields})
    return result.modified_count > 0


def delete_category(category_id):
    """
    Exclui categoria se não tiver atividades filhas.
    Retorna True se excluiu, ou string de erro se bloqueado.
    """
    col = _col("gantt_categories")
    if col is None:
        return "Sem conexão com o banco de dados."
    count = count_activities_in_category(category_id)
    if count > 0:
        return f"A categoria possui {count} atividade(s) vinculada(s) e não pode ser excluída."
    result = col.delete_one({"_id": ObjectId(category_id)})
    return result.deleted_count > 0


def count_activities_in_category(category_id):
    """Retorna o número de atividades vinculadas a uma categoria."""
    col = _col("gantt_activities")
    if col is None:
        return 0
    return col.count_documents({"categoria_id": ObjectId(category_id)})


# ---------------------------------------------------------------------------
# gantt_activities
# ---------------------------------------------------------------------------

def get_all_activities():
    """Retorna todas as atividades ordenadas por data_hora_inicio."""
    col = _col("gantt_activities")
    if col is None:
        return []
    return [_serialize(d) for d in col.find().sort("data_hora_inicio", 1)]


def get_activities_by_category(category_id):
    """Retorna atividades de uma categoria ordenadas por data_hora_inicio."""
    col = _col("gantt_activities")
    if col is None:
        return []
    return [
        _serialize(d)
        for d in col.find({"categoria_id": ObjectId(category_id)}).sort("data_hora_inicio", 1)
    ]


def get_activity_by_id(activity_id):
    """Retorna atividade por ID ou None."""
    col = _col("gantt_activities")
    if col is None:
        return None
    doc = col.find_one({"_id": ObjectId(activity_id)})
    return _serialize(doc)


def create_activity(data):
    """
    Insere nova atividade. Retorna o ID gerado como string.
    data: {"titulo", "categoria_id", "data_hora_inicio", "data_hora_fim", "progresso_real"(opt)}
    """
    col = _col("gantt_activities")
    if col is None:
        return None
    doc = {
        "titulo":           data["titulo"],
        "categoria_id":     ObjectId(data["categoria_id"]),
        "data_hora_inicio": data["data_hora_inicio"],
        "data_hora_fim":    data["data_hora_fim"],
        "progresso_real":   int(data.get("progresso_real", 0)),
        "criado_em":        _now(),
        "atualizado_em":    _now(),
    }
    result = col.insert_one(doc)
    return str(result.inserted_id)


def update_activity(activity_id, data):
    """
    Atualiza campos da atividade. Retorna True se modificou.
    data: dict com campos a atualizar
    """
    col = _col("gantt_activities")
    if col is None:
        return False
    allowed = ("titulo", "categoria_id", "data_hora_inicio", "data_hora_fim", "progresso_real")
    update_fields = {k: v for k, v in data.items() if k in allowed}
    if "categoria_id" in update_fields:
        update_fields["categoria_id"] = ObjectId(update_fields["categoria_id"])
    if "progresso_real" in update_fields:
        update_fields["progresso_real"] = int(update_fields["progresso_real"])
    update_fields["atualizado_em"] = _now()
    result = col.update_one({"_id": ObjectId(activity_id)}, {"$set": update_fields})
    return result.modified_count > 0


def delete_activity(activity_id):
    """Exclui atividade e suas atribuições vinculadas. Retorna True se excluiu."""
    col_act = _col("gantt_activities")
    col_asg = _col("gantt_assignments")
    if col_act is None:
        return False
    oid = ObjectId(activity_id)
    if col_asg is not None:
        col_asg.delete_many({"atividade_id": oid})
    result = col_act.delete_one({"_id": oid})
    return result.deleted_count > 0


# ---------------------------------------------------------------------------
# gantt_assignments
# ---------------------------------------------------------------------------

def get_assignments_by_activity(activity_id):
    """Retorna atribuições de uma atividade ordenadas por data_hora_entrada."""
    col = _col("gantt_assignments")
    if col is None:
        return []
    return [
        _serialize(d)
        for d in col.find({"atividade_id": ObjectId(activity_id)}).sort("data_hora_entrada", 1)
    ]


def get_assignments_by_employee(employee_id, exclude_id=None):
    """
    Retorna todas as atribuições de um funcionário.
    exclude_id: ID string da atribuição a ignorar ao editar (exclui a própria do conflito).
    """
    col = _col("gantt_assignments")
    if col is None:
        return []
    docs = [_serialize(d) for d in col.find({"funcionario_id": ObjectId(employee_id)})]
    if exclude_id:
        docs = [d for d in docs if d["_id"] != exclude_id]
    return docs


def get_assignment_by_id(assignment_id):
    """Retorna atribuição por ID ou None."""
    col = _col("gantt_assignments")
    if col is None:
        return None
    doc = col.find_one({"_id": ObjectId(assignment_id)})
    return _serialize(doc)


def create_assignment(data):
    """
    Insere nova atribuição. Retorna o ID gerado como string.
    data: {"atividade_id", "funcionario_id", "data_hora_entrada", "data_hora_saida"}
    """
    col = _col("gantt_assignments")
    if col is None:
        return None
    doc = {
        "atividade_id":      ObjectId(data["atividade_id"]),
        "funcionario_id":    ObjectId(data["funcionario_id"]),
        "data_hora_entrada": data["data_hora_entrada"],
        "data_hora_saida":   data["data_hora_saida"],
        "criado_em":         _now(),
        "atualizado_em":     _now(),
    }
    result = col.insert_one(doc)
    return str(result.inserted_id)


def update_assignment(assignment_id, data):
    """Atualiza campos da atribuição. Retorna True se modificou."""
    col = _col("gantt_assignments")
    if col is None:
        return False
    allowed = ("funcionario_id", "data_hora_entrada", "data_hora_saida")
    update_fields = {k: v for k, v in data.items() if k in allowed}
    if "funcionario_id" in update_fields:
        update_fields["funcionario_id"] = ObjectId(update_fields["funcionario_id"])
    update_fields["atualizado_em"] = _now()
    result = col.update_one({"_id": ObjectId(assignment_id)}, {"$set": update_fields})
    return result.modified_count > 0


def delete_assignment(assignment_id):
    """Exclui atribuição. Retorna True se excluiu."""
    col = _col("gantt_assignments")
    if col is None:
        return False
    result = col.delete_one({"_id": ObjectId(assignment_id)})
    return result.deleted_count > 0


# ---------------------------------------------------------------------------
# gantt_employees
# ---------------------------------------------------------------------------

def get_active_employees():
    """Retorna funcionários ativos ordenados por nome."""
    col = _col("gantt_employees")
    if col is None:
        return []
    return [_serialize(d) for d in col.find({"ativo": True}).sort("nome", 1)]


def get_all_employees():
    """Retorna todos os funcionários (ativos e inativos) ordenados por nome."""
    col = _col("gantt_employees")
    if col is None:
        return []
    return [_serialize(d) for d in col.find().sort("nome", 1)]


def get_employee_by_id(employee_id):
    """Retorna funcionário por ID ou None."""
    col = _col("gantt_employees")
    if col is None:
        return None
    doc = col.find_one({"_id": ObjectId(employee_id)})
    return _serialize(doc)


def create_employee(data):
    """
    Insere novo funcionário. Retorna o ID gerado como string.
    data: {"nome", "turno_padrao"}
    """
    col = _col("gantt_employees")
    if col is None:
        return None
    doc = {
        "nome":          data["nome"],
        "turno_padrao":  data["turno_padrao"],
        "ativo":         True,
        "criado_em":     _now(),
        "atualizado_em": _now(),
    }
    result = col.insert_one(doc)
    return str(result.inserted_id)


def update_employee(employee_id, data):
    """Atualiza nome e/ou turno_padrao do funcionário. Retorna True se modificou."""
    col = _col("gantt_employees")
    if col is None:
        return False
    allowed = ("nome", "turno_padrao")
    update_fields = {k: v for k, v in data.items() if k in allowed}
    update_fields["atualizado_em"] = _now()
    result = col.update_one({"_id": ObjectId(employee_id)}, {"$set": update_fields})
    return result.modified_count > 0


def deactivate_employee(employee_id):
    """
    Desativa funcionário (ativo=False). Retorna True se modificou.
    Exclusão física não é permitida enquanto houver atribuições — use esta função.
    """
    col = _col("gantt_employees")
    if col is None:
        return False
    result = col.update_one(
        {"_id": ObjectId(employee_id)},
        {"$set": {"ativo": False, "atualizado_em": _now()}}
    )
    return result.modified_count > 0


def has_assignments(employee_id):
    """Verifica se funcionário possui atribuições registradas (bloqueia exclusão física)."""
    col = _col("gantt_assignments")
    if col is None:
        return False
    return col.count_documents({"funcionario_id": ObjectId(employee_id)}) > 0


# ---------------------------------------------------------------------------
# gantt_audit_log
# ---------------------------------------------------------------------------

def append_audit_log(entry):
    """
    Insere entrada no log de auditoria. Única operação de escrita permitida nesta coleção.
    entry: {"timestamp", "usuario_id", "usuario_nome", "entidade", "entidade_id",
            "entidade_nome", "acao", "campo_alterado"(opt), "valor_anterior"(opt), "valor_novo"(opt)}
    """
    col = _col("gantt_audit_log")
    if col is None:
        return
    col.insert_one(entry)


def get_audit_log(limit=200):
    """Retorna entradas do log ordenadas por timestamp decrescente."""
    col = _col("gantt_audit_log")
    if col is None:
        return []
    return [_serialize(d) for d in col.find().sort("timestamp", -1).limit(limit)]
