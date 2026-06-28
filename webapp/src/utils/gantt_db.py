# src/utils/gantt_db.py

from datetime import datetime, timedelta
from bson import ObjectId
from src.database.connection import get_mongo_connection, get_mongo_client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize(doc):
    """Converte qualquer valor ObjectId em str e retorna cópia do documento.

    Cobre _id e chaves estrangeiras (projeto_id, categoria_id, atividade_id,
    funcionario_id) para que o documento seja JSON-serializável em dcc.Store.
    """
    if doc is None:
        return None
    out = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            out[k] = str(v)
        else:
            out[k] = v
    return out


def _col(name):
    return get_mongo_connection(name)


def _now():
    return datetime.utcnow()


# ---------------------------------------------------------------------------
# gantt_projects
# ---------------------------------------------------------------------------

PROJECT_TIPOS = [
    "Parada Preventiva",
    "Parada Corretiva",
    "Projeto de Melhoria",
    "Outro",
]


def get_all_projects(include_archived=False):
    """
    Retorna projetos ordenados por data de criação.
    Por padrão exclui arquivados. Passe include_archived=True para incluir todos.
    """
    col = _col("gantt_projects")
    if col is None:
        return []
    query = {} if include_archived else {"arquivado": {"$ne": True}}
    return [_serialize(d) for d in col.find(query).sort("criado_em", 1)]


def get_archived_projects():
    """Retorna apenas projetos arquivados, ordenados por arquivado_em decrescente."""
    col = _col("gantt_projects")
    if col is None:
        return []
    return [_serialize(d) for d in col.find({"arquivado": True}).sort("arquivado_em", -1)]


def archive_project(project_id):
    """Marca projeto como arquivado (não exclui — reversível via unarchive_project)."""
    col = _col("gantt_projects")
    if col is None:
        return False
    now = _now()
    result = col.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {"arquivado": True, "arquivado_em": now, "atualizado_em": now}},
    )
    return result.modified_count > 0


def unarchive_project(project_id):
    """Restaura projeto arquivado, removendo a flag arquivado e arquivado_em."""
    col = _col("gantt_projects")
    if col is None:
        return False
    now = _now()
    result = col.update_one(
        {"_id": ObjectId(project_id)},
        {"$set":   {"arquivado": False, "atualizado_em": now},
         "$unset": {"arquivado_em": ""}},
    )
    return result.modified_count > 0


def get_project_by_id(project_id):
    """Retorna projeto por ID ou None."""
    col = _col("gantt_projects")
    if col is None:
        return None
    doc = col.find_one({"_id": ObjectId(project_id)})
    return _serialize(doc)


def create_project(data):
    """
    Insere novo projeto. Retorna o ID gerado como string.
    data: {"nome", "tipo", "data_hora_inicio", "data_hora_fim", "observacoes"(opt)}
    """
    col = _col("gantt_projects")
    if col is None:
        return None
    doc = {
        "nome":             data["nome"],
        "tipo":             data["tipo"],
        "data_hora_inicio": data["data_hora_inicio"],
        "data_hora_fim":    data["data_hora_fim"],
        "observacoes":      data.get("observacoes", ""),
        "criado_em":        _now(),
        "atualizado_em":    _now(),
    }
    result = col.insert_one(doc)
    return str(result.inserted_id)


def update_project(project_id, data):
    """Atualiza campos do projeto. Retorna True se modificou."""
    col = _col("gantt_projects")
    if col is None:
        return False
    allowed = ("nome", "tipo", "observacoes", "data_hora_inicio", "data_hora_fim")
    update_fields = {k: v for k, v in data.items() if k in allowed}
    update_fields["atualizado_em"] = _now()
    result = col.update_one({"_id": ObjectId(project_id)}, {"$set": update_fields})
    return result.modified_count > 0


def delete_project(project_id):
    """
    Exclui projeto se não tiver categorias vinculadas.
    Retorna True se excluiu, ou string de erro se bloqueado.
    """
    col = _col("gantt_projects")
    if col is None:
        return "Sem conexão com o banco de dados."
    count = count_categories_in_project(project_id)
    if count > 0:
        return f"O projeto possui {count} categoria(s) vinculada(s) e não pode ser excluído."
    result = col.delete_one({"_id": ObjectId(project_id)})
    return result.deleted_count > 0


def count_categories_in_project(project_id):
    """Retorna número de categorias vinculadas a um projeto."""
    col = _col("gantt_categories")
    if col is None:
        return 0
    return col.count_documents({"projeto_id": ObjectId(project_id)})


def migrate_to_default_project():
    """
    Garante que toda categoria tenha projeto_id.
    SÓ cria o projeto 'Geral' se houver categorias órfãs para migrar.
    Idempotente e safe para concorrência (usa upsert + índice único em nome).
    """
    col_proj = _col("gantt_projects")
    col_cat  = _col("gantt_categories")
    if col_proj is None or col_cat is None:
        return None
    now = _now()

    # Índice único em nome para blindar contra futuras duplicatas
    try:
        col_proj.create_index("nome", unique=True, background=True)
    except Exception:
        pass

    # Se não há categorias órfãs, nada a fazer
    orphan_count = col_cat.count_documents({"projeto_id": {"$exists": False}})
    proj_id = None
    if orphan_count > 0:
        # Upsert atômico do projeto 'Geral' apenas quando necessário
        col_proj.update_one(
            {"nome": "Geral"},
            {
                "$setOnInsert": {
                    "nome":             "Geral",
                    "tipo":             "Outro",
                    "data_hora_inicio": now,
                    "data_hora_fim":    now,
                    "observacoes":      "Projeto padrão criado automaticamente para categorias migradas.",
                    "criado_em":        now,
                    "atualizado_em":    now,
                },
            },
            upsert=True,
        )
        proj_id = col_proj.find_one({"nome": "Geral"}, {"_id": 1})["_id"]
        col_cat.update_many(
            {"projeto_id": {"$exists": False}},
            {"$set": {"projeto_id": proj_id, "atualizado_em": now}},
        )

    # Backfill datas para projetos antigos (sem data_hora_inicio/fim)
    for proj in col_proj.find({"$or": [
        {"data_hora_inicio": {"$exists": False}},
        {"data_hora_fim":    {"$exists": False}},
    ]}):
        cats = list(col_cat.find({"projeto_id": proj["_id"]}))
        if cats:
            starts = [c["data_hora_inicio"] for c in cats if c.get("data_hora_inicio")]
            ends   = [c["data_hora_fim"]    for c in cats if c.get("data_hora_fim")]
            if starts and ends:
                col_proj.update_one(
                    {"_id": proj["_id"]},
                    {"$set": {
                        "data_hora_inicio": min(starts),
                        "data_hora_fim":    max(ends),
                        "atualizado_em":    now,
                    }},
                )
                continue
        col_proj.update_one(
            {"_id": proj["_id"]},
            {"$set": {"data_hora_inicio": now, "data_hora_fim": now, "atualizado_em": now}},
        )

    return str(proj_id)


def ensure_indexes():
    """Cria índices em FKs do módulo Gantt. Idempotente — MongoDB ignora chamada
    repetida em índice já existente. Background=True para não bloquear escrita
    durante o build inicial. SP-15 item 4."""
    pairs = [
        ("gantt_activities",  "categoria_id"),
        ("gantt_assignments", "atividade_id"),
        ("gantt_assignments", "funcionario_id"),
        ("gantt_categories",  "projeto_id"),
    ]
    for col_name, field in pairs:
        col = _col(col_name)
        if col is None:
            continue
        try:
            col.create_index(field, background=True)
        except Exception:
            # Conservador: índice conflitante pré-existente não derruba o boot.
            pass


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
    data: {"nome", "projeto_id", "data_hora_inicio", "data_hora_fim"}
    """
    col = _col("gantt_categories")
    if col is None:
        return None
    doc = {
        "nome":             data["nome"],
        "projeto_id":       ObjectId(data["projeto_id"]),
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
    allowed = ("nome", "projeto_id", "data_hora_inicio", "data_hora_fim")
    update_fields = {k: v for k, v in data.items() if k in allowed}
    if "projeto_id" in update_fields:
        update_fields["projeto_id"] = ObjectId(update_fields["projeto_id"])
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
    data: {"titulo", "categoria_id", "data_hora_inicio", "data_hora_fim",
           "progresso_real"(opt), "observacao"(opt)}
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
        "observacao":       (data.get("observacao") or "").strip(),
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
    allowed = ("titulo", "categoria_id", "data_hora_inicio", "data_hora_fim",
               "progresso_real", "observacao")
    update_fields = {k: v for k, v in data.items() if k in allowed}
    if "categoria_id" in update_fields:
        update_fields["categoria_id"] = ObjectId(update_fields["categoria_id"])
    if "progresso_real" in update_fields:
        update_fields["progresso_real"] = int(update_fields["progresso_real"])
    if "observacao" in update_fields:
        update_fields["observacao"] = (update_fields["observacao"] or "").strip()
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


def get_assignments_by_activities(activity_ids):
    """Retorna em UMA query MongoDB todas as atribuições do conjunto de atividades.
    Substitui o loop N+1 em render_gantt (SP-15 item 3). Aceita IDs str ou
    ObjectId; lista vazia → retorna [].
    """
    col = _col("gantt_assignments")
    if col is None or not activity_ids:
        return []
    oids = [a if isinstance(a, ObjectId) else ObjectId(a) for a in activity_ids]
    return [
        _serialize(d)
        for d in col.find({"atividade_id": {"$in": oids}}).sort("data_hora_entrada", 1)
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
    """
    Retorna todos os funcionários (ativos e inativos) ordenados por nome.
    Exclui 'foto_bytes' da projeção e adiciona flag '_has_photo' derivado
    da presença de 'foto_mime' — avatar é servido via rota dedicada, então
    não faz sentido carregar os bytes aqui (payload pesado).
    """
    col = _col("gantt_employees")
    if col is None:
        return []
    docs = []
    for d in col.find({}, {"foto_bytes": 0}).sort("nome", 1):
        d["_has_photo"] = bool(d.get("foto_mime"))
        docs.append(_serialize(d))
    return docs


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


def set_employee_photo(employee_id, photo_bytes, mime_type):
    """
    Persiste foto do funcionário como bytes binários + tipo MIME.
    Servida via rota /api/gantt/employee-photo/<id> para permitir cache de browser.
    """
    col = _col("gantt_employees")
    if col is None:
        return False
    result = col.update_one(
        {"_id": ObjectId(employee_id)},
        {"$set": {"foto_bytes": photo_bytes, "foto_mime": mime_type,
                  "atualizado_em": _now()}},
    )
    return result.modified_count > 0


def clear_employee_photo(employee_id):
    """Remove foto do funcionário, voltando ao fallback de iniciais coloridas."""
    col = _col("gantt_employees")
    if col is None:
        return False
    result = col.update_one(
        {"_id": ObjectId(employee_id)},
        {"$unset": {"foto_bytes": "", "foto_mime": ""},
         "$set":   {"atualizado_em": _now()}},
    )
    return result.modified_count > 0


def has_employee_photo(employee_id):
    """Retorna True se o funcionário tem foto salva."""
    col = _col("gantt_employees")
    if col is None:
        return False
    doc = col.find_one(
        {"_id": ObjectId(employee_id), "foto_bytes": {"$exists": True}},
        {"_id": 1},
    )
    return doc is not None


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


# ---------------------------------------------------------------------------
# Reagendamento de plano — deslocamento de baseline (BR-19 / SP-16 / DS-16)
# ---------------------------------------------------------------------------

def _collect_project_subtree(project_id):
    """Lê a subárvore completa do projeto em uma query por coleção (sem N+1).

    Retorna dict com o doc do projeto, listas de ObjectId de categorias/atividades,
    os docs brutos das atribuições (precisamos das datas + funcionário para detectar
    conflito) e as contagens por tipo. Retorna None se projeto inexistente/sem banco.
    """
    proj_col = _col("gantt_projects")
    cat_col  = _col("gantt_categories")
    act_col  = _col("gantt_activities")
    asg_col  = _col("gantt_assignments")
    if proj_col is None:
        return None
    pid = ObjectId(project_id)
    projeto = proj_col.find_one({"_id": pid})
    if projeto is None:
        return None
    cat_ids = [c["_id"] for c in cat_col.find({"projeto_id": pid}, {"_id": 1})]
    act_ids = (
        [a["_id"] for a in act_col.find({"categoria_id": {"$in": cat_ids}}, {"_id": 1})]
        if cat_ids else []
    )
    asg_docs = list(asg_col.find({"atividade_id": {"$in": act_ids}})) if act_ids else []
    return {
        "projeto":       projeto,
        "pid":           pid,
        "categoria_ids": cat_ids,
        "atividade_ids": act_ids,
        "atribuicoes":   asg_docs,
        "contagens": {
            "categorias":  len(cat_ids),
            "atividades":  len(act_ids),
            "atribuicoes": len(asg_docs),
        },
    }


def _project_names_for_activities(activity_ids):
    """Mapa atividade_id(str) -> nome do projeto (ativ→categoria→projeto) em batch."""
    act_col  = _col("gantt_activities")
    cat_col  = _col("gantt_categories")
    proj_col = _col("gantt_projects")
    if not activity_ids or act_col is None:
        return {}
    oids = [ObjectId(a) for a in activity_ids]
    acts = list(act_col.find({"_id": {"$in": oids}}, {"categoria_id": 1}))
    cat_ids = list({a["categoria_id"] for a in acts})
    cats = {c["_id"]: c.get("projeto_id") for c in cat_col.find({"_id": {"$in": cat_ids}}, {"projeto_id": 1})}
    proj_ids = list({v for v in cats.values() if v is not None})
    projs = {p["_id"]: p.get("nome", "") for p in proj_col.find({"_id": {"$in": proj_ids}}, {"nome": 1})}
    out = {}
    for a in acts:
        out[str(a["_id"])] = projs.get(cats.get(a["categoria_id"]), "")
    return out


def _enrich_conflicts(raw):
    """Resolve nomes de funcionário e projeto externo dos conflitos (batch) e
    serializa para JSON (ObjectId→str, datetime→ISO)."""
    if not raw:
        return []
    emp_ids = list({c["funcionario_id"] for c in raw})
    ext_act_ids = list({str(c["atividade_externa_id"]) for c in raw})
    emp_col = _col("gantt_employees")
    emp_names = {}
    if emp_col is not None and emp_ids:
        for e in emp_col.find({"_id": {"$in": emp_ids}}, {"nome": 1}):
            emp_names[e["_id"]] = e.get("nome", "")
    proj_names = _project_names_for_activities(ext_act_ids)
    out = []
    for c in raw:
        out.append({
            "funcionario_id":        str(c["funcionario_id"]),
            "funcionario_nome":      emp_names.get(c["funcionario_id"], "Funcionário"),
            "atribuicao_id":         str(c["atribuicao_id"]),
            "atividade_id":          str(c["atividade_id"]),
            "atribuicao_externa_id": str(c["atribuicao_externa_id"]),
            "projeto_externo":       proj_names.get(str(c["atividade_externa_id"]), ""),
            "janela_inicio":         c["janela_inicio"].isoformat(),
            "janela_fim":            c["janela_fim"].isoformat(),
        })
    return out


def _detect_cross_project_conflicts(subtree, delta):
    """Detecta conflitos de atribuição entre o projeto (datas + delta, em memória)
    e atribuições do MESMO funcionário em OUTROS projetos (não deslocadas).

    Mesmo critério de sobreposição de AssignmentConflictRule. Conflitos internos
    ao projeto nunca ocorrem (deslocamento uniforme) — por isso excluímos as
    próprias atribuições do projeto. delta=timedelta(0) recalcula pós-gravação.
    """
    asg_col = _col("gantt_assignments")
    if asg_col is None:
        return []
    internal_ids = {a["_id"] for a in subtree["atribuicoes"]}
    by_emp = {}
    for a in subtree["atribuicoes"]:
        by_emp.setdefault(a["funcionario_id"], []).append(a)

    raw = []
    for emp_id, internas in by_emp.items():
        todas = list(asg_col.find({"funcionario_id": emp_id}))
        externas = [e for e in todas if e["_id"] not in internal_ids]
        if not externas:
            continue
        for ai in internas:
            ai_s = ai["data_hora_entrada"] + delta
            ai_e = ai["data_hora_saida"] + delta
            for ext in externas:
                if ai_s < ext["data_hora_saida"] and ext["data_hora_entrada"] < ai_e:
                    raw.append({
                        "funcionario_id":        emp_id,
                        "atribuicao_id":         ai["_id"],
                        "atividade_id":          ai["atividade_id"],
                        "atribuicao_externa_id": ext["_id"],
                        "atividade_externa_id":  ext["atividade_id"],
                        "janela_inicio":         max(ai_s, ext["data_hora_entrada"]),
                        "janela_fim":            min(ai_e, ext["data_hora_saida"]),
                    })
    return _enrich_conflicts(raw)


def preview_reschedule_project(project_id, novo_inicio):
    """Calcula o efeito de reagendar o projeto SEM gravar nada (SP-16 item 4).

    Retorna dict com delta, datas, contagens por tipo e conflitos cross-projeto
    que seriam gerados. Retorna None se projeto inexistente/sem banco.
    """
    subtree = _collect_project_subtree(project_id)
    if subtree is None:
        return None
    inicio_atual = subtree["projeto"]["data_hora_inicio"]
    delta = novo_inicio - inicio_atual
    sem_mudanca = (delta == timedelta(0))
    conflitos = [] if sem_mudanca else _detect_cross_project_conflicts(subtree, delta)
    return {
        "sem_mudanca":   sem_mudanca,
        "delta_segundos": delta.total_seconds(),
        "inicio_atual":  inicio_atual.isoformat(),
        "inicio_novo":   novo_inicio.isoformat(),
        "contagens":     subtree["contagens"],
        "conflitos":     conflitos,
    }


def _build_reschedule_audit(subtree, inicio_atual, novo_inicio, n_conflitos,
                            usuario_id=None, usuario_nome=None):
    """Monta a entrada de auditoria (BR-13) do reagendamento."""
    c = subtree["contagens"]
    delta = novo_inicio - inicio_atual
    return {
        "timestamp":      _now(),
        "usuario_id":     usuario_id,
        "usuario_nome":   usuario_nome,
        "entidade":       "projeto",
        "entidade_id":    str(subtree["pid"]),
        "entidade_nome":  subtree["projeto"].get("nome", ""),
        "acao":           "reagendamento",
        "campo_alterado": "data_hora_inicio",
        "valor_anterior": inicio_atual.isoformat(),
        "valor_novo":     novo_inicio.isoformat(),
        "detalhe": {
            "delta_segundos":  delta.total_seconds(),
            "categorias":      c["categorias"],
            "atividades":      c["atividades"],
            "atribuicoes":     c["atribuicoes"],
            "conflitos_gerados": n_conflitos,
        },
    }


def reschedule_project(project_id, novo_inicio, usuario_id=None, usuario_nome=None):
    """Desloca todas as datas da subárvore do projeto pelo delta, atomicamente.

    SP-16 itens 5-7, 10. Aplica o mesmo delta (intervalo puro) a projeto,
    categorias, atividades e atribuições via $dateAdd, dentro de uma transação
    MongoDB (tudo-ou-nada). Registra auditoria na mesma transação. Retorna dict
    {ok, contagens, conflitos} ou {ok: False, erro}.
    """
    subtree = _collect_project_subtree(project_id)
    if subtree is None:
        return {"ok": False, "erro": "Projeto não encontrado."}
    inicio_atual = subtree["projeto"]["data_hora_inicio"]
    delta = novo_inicio - inicio_atual
    if delta == timedelta(0):
        return {"ok": False, "sem_mudanca": True, "erro": "Nova data igual à atual — nada a fazer."}

    client = get_mongo_client()
    if client is None:
        return {"ok": False, "erro": "Sem conexão com o banco de dados."}

    pid      = subtree["pid"]
    cat_ids  = subtree["categoria_ids"]
    act_ids  = subtree["atividade_ids"]
    delta_ms = int(delta.total_seconds() * 1000)

    def _shift(field):
        return {field: {"$dateAdd": {"startDate": f"${field}", "unit": "millisecond", "amount": delta_ms}}}

    proj_col  = _col("gantt_projects")
    cat_col   = _col("gantt_categories")
    act_col   = _col("gantt_activities")
    asg_col   = _col("gantt_assignments")
    audit_col = _col("gantt_audit_log")

    # Conflitos calculados em memória (pré-gravação) para gravar a contagem na auditoria.
    conflitos_preview = _detect_cross_project_conflicts(subtree, delta)

    try:
        with client.start_session() as session:
            with session.start_transaction():
                proj_col.update_one(
                    {"_id": pid},
                    [{"$set": {**_shift("data_hora_inicio"), **_shift("data_hora_fim"),
                               "atualizado_em": _now()}}],
                    session=session,
                )
                if cat_ids:
                    cat_col.update_many(
                        {"projeto_id": pid},
                        [{"$set": {**_shift("data_hora_inicio"), **_shift("data_hora_fim"),
                                   "atualizado_em": _now()}}],
                        session=session,
                    )
                if act_ids:
                    act_col.update_many(
                        {"categoria_id": {"$in": cat_ids}},
                        [{"$set": {**_shift("data_hora_inicio"), **_shift("data_hora_fim"),
                                   "atualizado_em": _now()}}],
                        session=session,
                    )
                    asg_col.update_many(
                        {"atividade_id": {"$in": act_ids}},
                        [{"$set": {**_shift("data_hora_entrada"), **_shift("data_hora_saida"),
                                   "atualizado_em": _now()}}],
                        session=session,
                    )
                if audit_col is not None:
                    audit_col.insert_one(
                        _build_reschedule_audit(subtree, inicio_atual, novo_inicio,
                                                len(conflitos_preview), usuario_id, usuario_nome),
                        session=session,
                    )
    except Exception as e:
        msg = str(e)
        low = msg.lower()
        if "replica set" in low or "transaction numbers" in low or "transaction" in low:
            return {"ok": False, "erro": (
                "Transação não suportada pelo MongoDB atual (reagendamento exige replica set). "
                f"Detalhe: {msg}"
            )}
        return {"ok": False, "erro": f"Falha ao reagendar: {msg}"}

    # Recalcula conflitos a partir do banco já deslocado (SP-16 item 9).
    subtree_after = _collect_project_subtree(project_id)
    conflitos = _detect_cross_project_conflicts(subtree_after, timedelta(0)) if subtree_after else []
    return {
        "ok":        True,
        "contagens": subtree["contagens"],
        "conflitos": conflitos,
    }
