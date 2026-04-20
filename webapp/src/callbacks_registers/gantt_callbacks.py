# src/callbacks_registers/gantt_callbacks.py

from datetime import datetime, timedelta

from dash import html, Input, Output, State, ALL, ctx, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from flask_login import current_user

from src.utils import gantt_db
from src.utils.gantt_validation import (
    CATEGORY_PIPELINE, ACTIVITY_PIPELINE, ASSIGNMENT_PIPELINE,
    ValidationContext,
)
from src.components.gantt_chart import build_gantt_chart


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _parse_dt(value):
    """Converte string ISO de input datetime-local para objeto datetime."""
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _fmt_dt(dt):
    """Formata datetime para input datetime-local (HTML5)."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt[:16]  # corta segundos se já for string
    return dt.strftime("%Y-%m-%dT%H:%M")


def _log(action, entity, entity_id, entity_name, field=None, old=None, new=None):
    gantt_db.append_audit_log({
        "timestamp":       datetime.utcnow(),
        "usuario_id":      current_user.id,
        "usuario_nome":    current_user.username,
        "entidade":        entity,
        "entidade_id":     str(entity_id),
        "entidade_nome":   entity_name,
        "acao":            action,
        "campo_alterado":  field,
        "valor_anterior":  str(old) if old is not None else None,
        "valor_novo":      str(new) if new is not None else None,
    })


def _validation_errors_output(errors):
    """Retorna (is_open_val_modal, list_items) para o modal de validação."""
    items = [html.Li(e) for e in errors]
    return True, items


TURNO_HORARIOS = {
    "A": ("00:00", "06:00"),
    "B": ("06:00", "15:00"),
    "C": ("15:00", "00:00"),
}


# ---------------------------------------------------------------------------
# Registro de callbacks
# ---------------------------------------------------------------------------

def register_gantt_callbacks(app):
    """Registra todos os callbacks da página Planejamento Gantt."""

    # ------------------------------------------------------------------
    # CB-01 — Renderizar Gantt
    # ------------------------------------------------------------------
    @app.callback(
        Output("gantt-chart-container", "children"),
        Input("store-gantt-refresh", "data"),
        Input("store-gantt-granularity", "data"),
        Input("store-gantt-categories-state", "data"),
        prevent_initial_call=False,
    )
    def render_gantt(refresh, granularity, categories_state):
        categories  = gantt_db.get_all_categories()
        activities  = gantt_db.get_all_activities()
        all_assignments = []
        for act in activities:
            all_assignments.extend(gantt_db.get_assignments_by_activity(act["_id"]))
        return build_gantt_chart(
            categories, activities, all_assignments,
            granularity=granularity or "dias",
            expanded_state=categories_state or {},
        )

    # ------------------------------------------------------------------
    # CB-02 — Troca de granularidade
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-gantt-granularity", "data"),
        Input("dropdown-gantt-granularity", "value"),
        prevent_initial_call=True,
    )
    def update_granularity(value):
        return value or "dias"

    # ------------------------------------------------------------------
    # CB-03 — Toggle expand/collapse de categoria
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-gantt-categories-state", "data"),
        Input({"type": "btn-toggle-category", "index": ALL}, "n_clicks"),
        State("store-gantt-categories-state", "data"),
        prevent_initial_call=True,
    )
    def toggle_category(n_clicks_list, current_state):
        if not any(n_clicks_list):
            raise PreventUpdate
        triggered = ctx.triggered_id
        if triggered is None:
            raise PreventUpdate
        cat_id = triggered["index"]
        state = dict(current_state or {})
        state[cat_id] = not state.get(cat_id, True)
        return state

    # ------------------------------------------------------------------
    # CB-04 — Expandir tudo / Recolher tudo
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-gantt-categories-state", "data", allow_duplicate=True),
        Input("btn-expand-all", "n_clicks"),
        Input("btn-collapse-all", "n_clicks"),
        prevent_initial_call=True,
    )
    def expand_collapse_all(expand_clicks, collapse_clicks):
        triggered_id = ctx.triggered_id
        if triggered_id is None:
            raise PreventUpdate
        categories = gantt_db.get_all_categories()
        value = triggered_id == "btn-expand-all"
        return {cat["_id"]: value for cat in categories}

    # ------------------------------------------------------------------
    # CB-05 — Abrir modal de categoria (criar ou editar)
    # ------------------------------------------------------------------
    @app.callback(
        Output("modal-category", "is_open"),
        Output("title-modal-category", "children"),
        Output("input-category-nome", "value"),
        Output("input-category-inicio", "value"),
        Output("input-category-fim", "value"),
        Output("store-category-editing-id", "data"),
        Input("btn-new-category", "n_clicks"),
        Input({"type": "btn-edit-category", "index": ALL}, "n_clicks"),
        Input("btn-cancel-category", "n_clicks"),
        prevent_initial_call=True,
    )
    def open_category_modal(new_clicks, edit_clicks, cancel):
        triggered_id = ctx.triggered_id
        if triggered_id is None:
            raise PreventUpdate
        if triggered_id == "btn-cancel-category":
            return False, no_update, no_update, no_update, no_update, no_update
        if triggered_id == "btn-new-category":
            return True, "Nova Categoria", "", "", "", None
        # edit
        if isinstance(triggered_id, dict) and triggered_id.get("type") == "btn-edit-category":
            if not any(edit_clicks):
                raise PreventUpdate
            cat_id = triggered_id["index"]
            cat = gantt_db.get_category_by_id(cat_id)
            if not cat:
                raise PreventUpdate
            return (
                True, "Editar Categoria",
                cat["nome"],
                _fmt_dt(cat["data_hora_inicio"]),
                _fmt_dt(cat["data_hora_fim"]),
                cat_id,
            )
        raise PreventUpdate

    # ------------------------------------------------------------------
    # CB-06 — Salvar categoria
    # ------------------------------------------------------------------
    @app.callback(
        Output("modal-category", "is_open", allow_duplicate=True),
        Output("store-gantt-refresh", "data", allow_duplicate=True),
        Output("modal-validation-errors", "is_open", allow_duplicate=True),
        Output("list-validation-errors", "children", allow_duplicate=True),
        Input("btn-save-category", "n_clicks"),
        State("input-category-nome", "value"),
        State("input-category-inicio", "value"),
        State("input-category-fim", "value"),
        State("store-category-editing-id", "data"),
        State("store-gantt-refresh", "data"),
        prevent_initial_call=True,
    )
    def save_category(n_clicks, nome, inicio, fim, editing_id, refresh):
        if not n_clicks:
            raise PreventUpdate
        if current_user.level < 2:
            raise PreventUpdate
        inicio_dt = _parse_dt(inicio)
        fim_dt    = _parse_dt(fim)
        if not nome or not inicio_dt or not fim_dt:
            errs = ["Todos os campos obrigatórios devem ser preenchidos."]
            items = [html.Li(e) for e in errs]
            return no_update, no_update, True, items
        data = {"nome": nome, "data_hora_inicio": inicio_dt, "data_hora_fim": fim_dt}
        ctx_val = ValidationContext()
        errors = CATEGORY_PIPELINE.run(data, ctx_val)
        if errors:
            items = [html.Li(e) for e in errors]
            return no_update, no_update, True, items
        if editing_id:
            old = gantt_db.get_category_by_id(editing_id)
            gantt_db.update_category(editing_id, data)
            if old:
                for field in ("nome", "data_hora_inicio", "data_hora_fim"):
                    if str(old.get(field)) != str(data[field]):
                        _log("edicao", "categoria", editing_id, nome, field, old.get(field), data[field])
        else:
            new_id = gantt_db.create_category(data)
            _log("criacao", "categoria", new_id, nome)
        return False, (refresh or 0) + 1, False, []

    # ------------------------------------------------------------------
    # CB-07 — Deletar categoria
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-confirm-delete", "data", allow_duplicate=True),
        Output("modal-confirm-delete", "is_open", allow_duplicate=True),
        Output("text-confirm-delete-name", "children", allow_duplicate=True),
        Output("modal-block-info", "is_open", allow_duplicate=True),
        Output("text-block-info-title", "children", allow_duplicate=True),
        Output("text-block-info-message", "children", allow_duplicate=True),
        Input({"type": "btn-delete-category", "index": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def request_delete_category(n_clicks_list):
        if not any(n_clicks_list):
            raise PreventUpdate
        triggered_id = ctx.triggered_id
        if not isinstance(triggered_id, dict):
            raise PreventUpdate
        cat_id = triggered_id["index"]
        cat = gantt_db.get_category_by_id(cat_id)
        if not cat:
            raise PreventUpdate
        count = gantt_db.count_activities_in_category(cat_id)
        if count > 0:
            return (
                no_update, False, no_update,
                True,
                "Exclusão não permitida",
                f"A categoria \"{cat['nome']}\" possui {count} atividade(s) vinculada(s) e não pode ser excluída.",
            )
        return (
            {"entity": "categoria", "id": cat_id, "name": cat["nome"]},
            True, cat["nome"],
            False, no_update, no_update,
        )

    # ------------------------------------------------------------------
    # CB-07b — Executar exclusão confirmada
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-gantt-refresh", "data", allow_duplicate=True),
        Output("modal-confirm-delete", "is_open", allow_duplicate=True),
        Input("btn-confirm-delete", "n_clicks"),
        State("store-confirm-delete", "data"),
        State("store-gantt-refresh", "data"),
        prevent_initial_call=True,
    )
    def execute_confirmed_delete(n_clicks, confirm_data, refresh):
        if not n_clicks or not confirm_data:
            raise PreventUpdate
        if current_user.level < 2:
            raise PreventUpdate
        entity  = confirm_data.get("entity")
        eid     = confirm_data.get("id")
        ename   = confirm_data.get("name", "")
        if entity == "categoria":
            gantt_db.delete_category(eid)
            _log("exclusao", "categoria", eid, ename)
        elif entity == "atividade":
            gantt_db.delete_activity(eid)
            _log("exclusao", "atividade", eid, ename)
        elif entity == "atribuicao":
            gantt_db.delete_assignment(eid)
            _log("exclusao", "atribuicao", eid, ename)
        elif entity == "funcionario":
            gantt_db.deactivate_employee(eid)
            _log("exclusao", "funcionario", eid, ename)
        return (refresh or 0) + 1, False

    # ------------------------------------------------------------------
    # CB-07c — Cancelar exclusão
    # ------------------------------------------------------------------
    @app.callback(
        Output("modal-confirm-delete", "is_open", allow_duplicate=True),
        Input("btn-cancel-delete", "n_clicks"),
        prevent_initial_call=True,
    )
    def cancel_delete(n_clicks):
        if n_clicks:
            return False
        raise PreventUpdate

    # ------------------------------------------------------------------
    # CB-08 — Abrir modal de atividade (criar ou editar)
    # ------------------------------------------------------------------
    @app.callback(
        Output("modal-activity", "is_open"),
        Output("title-modal-activity", "children"),
        Output("input-activity-titulo", "value"),
        Output("dropdown-activity-categoria", "options"),
        Output("dropdown-activity-categoria", "value"),
        Output("input-activity-inicio", "value"),
        Output("input-activity-fim", "value"),
        Output("input-activity-progresso", "value"),
        Output("div-activity-progresso", "style"),
        Output("store-activity-editing-id", "data"),
        Input("btn-new-activity", "n_clicks"),
        Input({"type": "btn-edit-activity", "index": ALL}, "n_clicks"),
        Input("btn-cancel-activity", "n_clicks"),
        prevent_initial_call=True,
    )
    def open_activity_modal(new_clicks, edit_clicks, cancel):
        triggered_id = ctx.triggered_id
        if triggered_id is None:
            raise PreventUpdate
        cats = gantt_db.get_all_categories()
        cat_options = [{"label": c["nome"], "value": c["_id"]} for c in cats]
        hidden = {"display": "none"}
        visible = {"display": "block"}
        if triggered_id == "btn-cancel-activity":
            return False, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update
        if triggered_id == "btn-new-activity":
            return True, "Nova Atividade", "", cat_options, None, "", "", 0, hidden, None
        if isinstance(triggered_id, dict) and triggered_id.get("type") == "btn-edit-activity":
            if not any(edit_clicks):
                raise PreventUpdate
            act_id = triggered_id["index"]
            act = gantt_db.get_activity_by_id(act_id)
            if not act:
                raise PreventUpdate
            return (
                True, "Editar Atividade",
                act["titulo"], cat_options,
                str(act["categoria_id"]),
                _fmt_dt(act["data_hora_inicio"]),
                _fmt_dt(act["data_hora_fim"]),
                act.get("progresso_real", 0),
                visible,
                act_id,
            )
        raise PreventUpdate

    # ------------------------------------------------------------------
    # CB-09 — Salvar atividade
    # ------------------------------------------------------------------
    @app.callback(
        Output("modal-activity", "is_open", allow_duplicate=True),
        Output("store-gantt-refresh", "data", allow_duplicate=True),
        Output("modal-validation-errors", "is_open", allow_duplicate=True),
        Output("list-validation-errors", "children", allow_duplicate=True),
        Input("btn-save-activity", "n_clicks"),
        State("input-activity-titulo", "value"),
        State("dropdown-activity-categoria", "value"),
        State("input-activity-inicio", "value"),
        State("input-activity-fim", "value"),
        State("input-activity-progresso", "value"),
        State("store-activity-editing-id", "data"),
        State("store-gantt-refresh", "data"),
        prevent_initial_call=True,
    )
    def save_activity(n_clicks, titulo, cat_id, inicio, fim, progresso, editing_id, refresh):
        if not n_clicks:
            raise PreventUpdate
        if current_user.level < 2:
            raise PreventUpdate
        inicio_dt = _parse_dt(inicio)
        fim_dt    = _parse_dt(fim)
        if not titulo or not cat_id or not inicio_dt or not fim_dt:
            items = [html.Li("Todos os campos obrigatórios devem ser preenchidos.")]
            return no_update, no_update, True, items
        cat = gantt_db.get_category_by_id(cat_id)
        if not cat:
            items = [html.Li("Categoria não encontrada.")]
            return no_update, no_update, True, items
        data = {
            "titulo":           titulo,
            "categoria_id":     cat_id,
            "data_hora_inicio": inicio_dt,
            "data_hora_fim":    fim_dt,
            "progresso_real":   int(progresso or 0),
        }
        ctx_val = ValidationContext(category={
            "data_hora_inicio": _parse_dt(_fmt_dt(cat["data_hora_inicio"])) if isinstance(cat["data_hora_inicio"], str) else cat["data_hora_inicio"],
            "data_hora_fim":    _parse_dt(_fmt_dt(cat["data_hora_fim"]))    if isinstance(cat["data_hora_fim"], str)    else cat["data_hora_fim"],
        })
        errors = ACTIVITY_PIPELINE.run(data, ctx_val)
        if errors:
            items = [html.Li(e) for e in errors]
            return no_update, no_update, True, items
        if editing_id:
            old = gantt_db.get_activity_by_id(editing_id)
            gantt_db.update_activity(editing_id, data)
            if old:
                for field in ("titulo", "data_hora_inicio", "data_hora_fim", "progresso_real"):
                    if str(old.get(field)) != str(data.get(field)):
                        _log("edicao", "atividade", editing_id, titulo, field, old.get(field), data[field])
        else:
            new_id = gantt_db.create_activity(data)
            _log("criacao", "atividade", new_id, titulo)
        return False, (refresh or 0) + 1, False, []

    # ------------------------------------------------------------------
    # CB-10 — Deletar atividade (solicita confirmação)
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-confirm-delete", "data", allow_duplicate=True),
        Output("modal-confirm-delete", "is_open", allow_duplicate=True),
        Output("text-confirm-delete-name", "children", allow_duplicate=True),
        Input({"type": "btn-delete-activity", "index": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def request_delete_activity(n_clicks_list):
        if not any(n_clicks_list):
            raise PreventUpdate
        triggered_id = ctx.triggered_id
        if not isinstance(triggered_id, dict):
            raise PreventUpdate
        act_id = triggered_id["index"]
        act = gantt_db.get_activity_by_id(act_id)
        if not act:
            raise PreventUpdate
        return (
            {"entity": "atividade", "id": act_id, "name": act["titulo"]},
            True, act["titulo"],
        )

    # ------------------------------------------------------------------
    # CB-11 — Abrir modal de atribuição (criar ou editar)
    # ------------------------------------------------------------------
    @app.callback(
        Output("modal-assignment", "is_open"),
        Output("title-modal-assignment", "children"),
        Output("dropdown-assignment-funcionario", "options"),
        Output("dropdown-assignment-funcionario", "value"),
        Output("input-assignment-entrada", "value"),
        Output("input-assignment-saida", "value"),
        Output("store-assignment-editing-id", "data"),
        Output("store-assignment-activity-id", "data"),
        Input({"type": "btn-new-assignment", "index": ALL}, "n_clicks"),
        Input({"type": "btn-edit-assignment", "index": ALL}, "n_clicks"),
        Input("btn-cancel-assignment", "n_clicks"),
        prevent_initial_call=True,
    )
    def open_assignment_modal(new_clicks, edit_clicks, cancel):
        triggered_id = ctx.triggered_id
        if triggered_id is None:
            raise PreventUpdate
        emps = gantt_db.get_active_employees()
        emp_options = [{"label": e["nome"], "value": e["_id"]} for e in emps]
        if triggered_id == "btn-cancel-assignment":
            return False, no_update, no_update, no_update, no_update, no_update, no_update, no_update
        if isinstance(triggered_id, dict) and triggered_id.get("type") == "btn-new-assignment":
            act_id = triggered_id["index"]
            return True, "Nova Atribuição", emp_options, None, "", "", None, act_id
        if isinstance(triggered_id, dict) and triggered_id.get("type") == "btn-edit-assignment":
            if not any(edit_clicks):
                raise PreventUpdate
            asg_id = triggered_id["index"]
            asg = gantt_db.get_assignment_by_id(asg_id)
            if not asg:
                raise PreventUpdate
            return (
                True, "Editar Atribuição", emp_options,
                str(asg["funcionario_id"]),
                _fmt_dt(asg["data_hora_entrada"]),
                _fmt_dt(asg["data_hora_saida"]),
                asg_id,
                str(asg["atividade_id"]),
            )
        raise PreventUpdate

    # ------------------------------------------------------------------
    # CB-12 — Pré-preenchimento de turno ao selecionar funcionário
    # ------------------------------------------------------------------
    @app.callback(
        Output("input-assignment-entrada", "value", allow_duplicate=True),
        Output("input-assignment-saida", "value", allow_duplicate=True),
        Input("dropdown-assignment-funcionario", "value"),
        State("input-assignment-entrada", "value"),
        prevent_initial_call=True,
    )
    def prefill_shift(emp_id, current_entrada):
        if not emp_id:
            raise PreventUpdate
        emp = gantt_db.get_employee_by_id(emp_id)
        if not emp:
            raise PreventUpdate
        turno = emp.get("turno_padrao", "B")
        hora_in, hora_out = TURNO_HORARIOS.get(turno, ("06:00", "15:00"))
        base_date = datetime.utcnow().date()
        if current_entrada:
            dt = _parse_dt(current_entrada)
            if dt:
                base_date = dt.date()
        entrada_str = f"{base_date}T{hora_in}"
        h_out_int = int(hora_out.split(":")[0])
        saida_date = base_date + timedelta(days=1) if h_out_int == 0 else base_date
        saida_str = f"{saida_date}T{hora_out}"
        return entrada_str, saida_str

    # ------------------------------------------------------------------
    # CB-13 — Salvar atribuição
    # ------------------------------------------------------------------
    @app.callback(
        Output("modal-assignment", "is_open", allow_duplicate=True),
        Output("store-gantt-refresh", "data", allow_duplicate=True),
        Output("modal-validation-errors", "is_open", allow_duplicate=True),
        Output("list-validation-errors", "children", allow_duplicate=True),
        Input("btn-save-assignment", "n_clicks"),
        State("dropdown-assignment-funcionario", "value"),
        State("input-assignment-entrada", "value"),
        State("input-assignment-saida", "value"),
        State("store-assignment-editing-id", "data"),
        State("store-assignment-activity-id", "data"),
        State("store-gantt-refresh", "data"),
        prevent_initial_call=True,
    )
    def save_assignment(n_clicks, emp_id, entrada, saida, editing_id, act_id, refresh):
        if not n_clicks:
            raise PreventUpdate
        if current_user.level < 2:
            raise PreventUpdate
        entrada_dt = _parse_dt(entrada)
        saida_dt   = _parse_dt(saida)
        if not emp_id or not entrada_dt or not saida_dt:
            items = [html.Li("Todos os campos obrigatórios devem ser preenchidos.")]
            return no_update, no_update, True, items
        data = {
            "atividade_id":      act_id,
            "funcionario_id":    emp_id,
            "data_hora_entrada": entrada_dt,
            "data_hora_saida":   saida_dt,
        }
        existing = gantt_db.get_assignments_by_employee(emp_id, exclude_id=editing_id)
        # Convert existing datetimes for conflict rule
        for a in existing:
            if isinstance(a.get("data_hora_entrada"), str):
                a["data_hora_entrada"] = _parse_dt(a["data_hora_entrada"])
            if isinstance(a.get("data_hora_saida"), str):
                a["data_hora_saida"] = _parse_dt(a["data_hora_saida"])
        ctx_val = ValidationContext(
            existing_assignments=existing,
            exclude_assignment_id=editing_id,
        )
        errors = ASSIGNMENT_PIPELINE.run(data, ctx_val)
        if errors:
            items = [html.Li(e) for e in errors]
            return no_update, no_update, True, items
        emp = gantt_db.get_employee_by_id(emp_id)
        emp_nome = emp["nome"] if emp else emp_id
        if editing_id:
            gantt_db.update_assignment(editing_id, data)
            _log("edicao", "atribuicao", editing_id, emp_nome)
        else:
            new_id = gantt_db.create_assignment(data)
            _log("criacao", "atribuicao", new_id, emp_nome)
        return False, (refresh or 0) + 1, False, []

    # ------------------------------------------------------------------
    # CB-14 — Deletar atribuição (solicita confirmação)
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-confirm-delete", "data", allow_duplicate=True),
        Output("modal-confirm-delete", "is_open", allow_duplicate=True),
        Output("text-confirm-delete-name", "children", allow_duplicate=True),
        Input({"type": "btn-delete-assignment", "index": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def request_delete_assignment(n_clicks_list):
        if not any(n_clicks_list):
            raise PreventUpdate
        triggered_id = ctx.triggered_id
        if not isinstance(triggered_id, dict):
            raise PreventUpdate
        asg_id = triggered_id["index"]
        asg = gantt_db.get_assignment_by_id(asg_id)
        if not asg:
            raise PreventUpdate
        emp = gantt_db.get_employee_by_id(str(asg["funcionario_id"]))
        nome = emp["nome"] if emp else "Funcionário"
        return (
            {"entity": "atribuicao", "id": asg_id, "name": nome},
            True, nome,
        )

    # ------------------------------------------------------------------
    # CB-15 — Abrir modal de funcionário (criar ou editar)
    # ------------------------------------------------------------------
    @app.callback(
        Output("modal-employee", "is_open"),
        Output("title-modal-employee", "children"),
        Output("input-employee-nome", "value"),
        Output("radio-employee-turno", "value"),
        Output("store-employee-editing-id", "data"),
        Input("btn-open-employee-list", "n_clicks"),
        Input({"type": "btn-edit-employee", "index": ALL}, "n_clicks"),
        Input("btn-cancel-employee", "n_clicks"),
        prevent_initial_call=True,
    )
    def open_employee_modal(open_clicks, edit_clicks, cancel):
        triggered_id = ctx.triggered_id
        if triggered_id is None:
            raise PreventUpdate
        if triggered_id == "btn-cancel-employee":
            return False, no_update, no_update, no_update, no_update
        if triggered_id == "btn-open-employee-list":
            return True, "Novo Funcionário", "", "B", None
        if isinstance(triggered_id, dict) and triggered_id.get("type") == "btn-edit-employee":
            emp_id = triggered_id["index"]
            emp = gantt_db.get_employee_by_id(emp_id)
            if not emp:
                raise PreventUpdate
            return True, "Editar Funcionário", emp["nome"], emp.get("turno_padrao", "B"), emp_id
        raise PreventUpdate

    # ------------------------------------------------------------------
    # CB-16 — Salvar funcionário
    # ------------------------------------------------------------------
    @app.callback(
        Output("modal-employee", "is_open", allow_duplicate=True),
        Output("store-gantt-refresh", "data", allow_duplicate=True),
        Output("modal-validation-errors", "is_open", allow_duplicate=True),
        Output("list-validation-errors", "children", allow_duplicate=True),
        Input("btn-save-employee", "n_clicks"),
        State("input-employee-nome", "value"),
        State("radio-employee-turno", "value"),
        State("store-employee-editing-id", "data"),
        State("store-gantt-refresh", "data"),
        prevent_initial_call=True,
    )
    def save_employee(n_clicks, nome, turno, editing_id, refresh):
        if not n_clicks:
            raise PreventUpdate
        if current_user.level < 2:
            raise PreventUpdate
        if not nome or not turno:
            items = [html.Li("Nome e turno são obrigatórios.")]
            return no_update, no_update, True, items
        if turno not in ("A", "B", "C"):
            items = [html.Li("Turno inválido.")]
            return no_update, no_update, True, items
        data = {"nome": nome.strip(), "turno_padrao": turno}
        if editing_id:
            old = gantt_db.get_employee_by_id(editing_id)
            gantt_db.update_employee(editing_id, data)
            if old:
                for field in ("nome", "turno_padrao"):
                    if old.get(field) != data[field]:
                        _log("edicao", "funcionario", editing_id, nome, field, old.get(field), data[field])
        else:
            new_id = gantt_db.create_employee(data)
            _log("criacao", "funcionario", new_id, nome)
        return False, (refresh or 0) + 1, False, []

    # ------------------------------------------------------------------
    # CB-17 — Fechar modais de erros de validação e bloqueio
    # ------------------------------------------------------------------
    @app.callback(
        Output("modal-validation-errors", "is_open", allow_duplicate=True),
        Input("btn-close-validation-errors", "n_clicks"),
        prevent_initial_call=True,
    )
    def close_validation_modal(n_clicks):
        if n_clicks:
            return False
        raise PreventUpdate

    @app.callback(
        Output("modal-block-info", "is_open", allow_duplicate=True),
        Input("btn-close-block-info", "n_clicks"),
        prevent_initial_call=True,
    )
    def close_block_info_modal(n_clicks):
        if n_clicks:
            return False
        raise PreventUpdate

    # ------------------------------------------------------------------
    # CB-25 — Carregar log de auditoria
    # ------------------------------------------------------------------
    @app.callback(
        Output("audit-log-table-container", "children"),
        Input("btn-refresh-audit-log", "n_clicks"),
        Input("store-audit-log-refresh", "data"),
        prevent_initial_call=False,
    )
    def load_audit_log(refresh_btn, refresh_store):
        entries = gantt_db.get_audit_log(limit=200)
        if not entries:
            return html.P("Nenhum registro encontrado.", className="text-muted p-3")
        rows = []
        for e in entries:
            ts = e.get("timestamp", "")
            if isinstance(ts, datetime):
                ts = ts.strftime("%d/%m/%Y %H:%M:%S")
            rows.append(
                html.Tr([
                    html.Td(str(ts)),
                    html.Td(e.get("usuario_nome", "")),
                    html.Td(e.get("acao", "")),
                    html.Td(e.get("entidade", "")),
                    html.Td(e.get("entidade_nome", "")),
                    html.Td(e.get("campo_alterado") or ""),
                    html.Td(str(e.get("valor_anterior") or "")),
                    html.Td(str(e.get("valor_novo") or "")),
                ])
            )
        return dbc.Table(
            [
                html.Thead(html.Tr([
                    html.Th("Timestamp"), html.Th("Usuário"), html.Th("Ação"),
                    html.Th("Entidade"), html.Th("Nome"), html.Th("Campo"),
                    html.Th("Valor anterior"), html.Th("Valor novo"),
                ])),
                html.Tbody(rows),
            ],
            bordered=True, striped=True, hover=True, size="sm", responsive=True,
        )
