# src/callbacks_registers/gantt_callbacks.py

from datetime import datetime, timedelta

from dash import html, Input, Output, State, ALL, ctx, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from flask import Response, abort
from flask_login import current_user, login_required

from src.utils import gantt_db
from src.utils.gantt_validation import (
    CATEGORY_PIPELINE, ACTIVITY_PIPELINE, ASSIGNMENT_PIPELINE,
    ValidationContext,
)
from src.components.gantt_chart import build_gantt_chart, build_gantt_resource_view


# Rota da página do Gantt — usada como guard em callbacks globais (Feature C).
ROUTE_GANTT = "/maintenance/gantt"


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


# ---------------------------------------------------------------------------
# Empty states — Feature C / DS-14 (loading, erro de leitura, vazio)
# ---------------------------------------------------------------------------

def _gantt_loading_state():
    """Placeholder enquanto os stores de dados estruturais ainda estão None.
    Em uso normal o dcc.Loading do gantt-chart-container cobre a transição;
    este helper é fallback defensivo."""
    return html.Div(
        [
            dbc.Spinner(color="primary", size="md"),
            html.Div("Carregando planejamento...", className="mt-3 text-muted small"),
        ],
        className="d-flex flex-column align-items-center justify-content-center py-5",
        style={"minHeight": "300px"},
    )


def _gantt_error_state():
    """Mensagem para falha de leitura do MongoDB. Diferenciada visualmente de
    'sem dados' por ícone amarelo de alerta e texto de ação."""
    return html.Div(
        [
            html.I(className="bi bi-exclamation-triangle-fill text-warning",
                   style={"fontSize": "2.5rem"}),
            html.H5("Sem conexão com o banco", className="mt-3 mb-1"),
            html.P(
                "Não foi possível ler os dados do planejamento. "
                "Verifique a conexão e clique em Atualizar.",
                className="text-muted small mb-0",
            ),
        ],
        className="d-flex flex-column align-items-center justify-content-center text-center py-5",
        style={"minHeight": "300px"},
    )


def _gantt_empty_state():
    """Mensagem para banco respondendo OK mas sem projetos/categorias/atividades.
    Diferenciada do estado de erro por ícone neutro e texto de orientação."""
    return html.Div(
        [
            html.I(className="bi bi-calendar-x text-muted",
                   style={"fontSize": "2.5rem"}),
            html.H5("Sem planejamento cadastrado", className="mt-3 mb-1"),
            html.P(
                "Crie um Projeto e adicione Categorias e Atividades para começar.",
                className="text-muted small mb-0",
            ),
        ],
        className="d-flex flex-column align-items-center justify-content-center text-center py-5",
        style={"minHeight": "300px"},
    )


# ---------------------------------------------------------------------------
# Invalidação seletiva de stores — Feature C / DS-12 / SP-14 item 3
# ---------------------------------------------------------------------------

def _reload_stores(entities):
    """Recarrega entidades especificadas do banco e retorna tupla ordenada
    (projects, categories, activities, assignments, employees) — a ordem casa
    com os 5 Outputs de stores de dados dos callbacks de save.

    Stores fora do `entities` recebem `dash.no_update` (preservam último valor).

    `entities`: set de strings em {"projects","categories","activities",
                                   "assignments","employees"}.
    """
    projects   = gantt_db.get_all_projects()    if "projects"   in entities else no_update
    categories = gantt_db.get_all_categories()  if "categories" in entities else no_update
    activities = gantt_db.get_all_activities()  if "activities" in entities else no_update
    employees  = gantt_db.get_all_employees()   if "employees"  in entities else no_update
    if "assignments" in entities:
        # Reaproveita lista de atividades se já foi recarregada — evita 2ª query
        act_source = activities if activities is not no_update else gantt_db.get_all_activities()
        ids = [a["_id"] for a in act_source]
        assignments = gantt_db.get_assignments_by_activities(ids)
    else:
        assignments = no_update
    return projects, categories, activities, assignments, employees


TURNO_HORARIOS = {
    "A": ("00:00", "06:00"),
    "B": ("06:00", "15:00"),
    "C": ("15:00", "00:00"),
    "ADM": ("08:00", "17:00"),
}


# ---------------------------------------------------------------------------
# Registro de callbacks
# ---------------------------------------------------------------------------

def register_gantt_callbacks(app):
    """Registra todos os callbacks da página Planejamento Gantt."""

    # Migração idempotente: garante que todas as categorias têm projeto_id
    gantt_db.migrate_to_default_project()
    # Cria índices em FKs (idempotente, background) — SP-15 item 4
    gantt_db.ensure_indexes()

    # ------------------------------------------------------------------
    # Rota Flask — servir foto do funcionário com cache de browser.
    # Os bytes ficam no documento mas são entregues via endpoint dedicado
    # para não inflar os payloads de render do Dash.
    # ------------------------------------------------------------------
    @app.server.route("/api/gantt/employee-photo/<emp_id>")
    @login_required
    def gantt_employee_photo(emp_id):
        col = gantt_db._col("gantt_employees")
        if col is None:
            abort(503)
        try:
            doc = col.find_one(
                {"_id": gantt_db.ObjectId(emp_id)},
                {"foto_bytes": 1, "foto_mime": 1},
            )
        except Exception:
            abort(400)
        if not doc or "foto_bytes" not in doc:
            abort(404)
        return Response(
            doc["foto_bytes"],
            mimetype=doc.get("foto_mime", "image/jpeg"),
            # Cache agressivo + cache-busting via ?v=atualizado_em na URL (Feature C / DS-15).
            # Veracidade preservada — URL muda quando o funcionário é editado.
            headers={"Cache-Control": "public, max-age=86400, immutable"},
        )

    # ------------------------------------------------------------------
    # CB-00 — Carregar dados estruturais do banco para os stores de dados.
    # Feature C (DS-10 / SP-14). Disparadores:
    #   - Entrada na rota do Gantt (url.pathname).
    #   - Clique em "Atualizar" (btn-gantt-refresh).
    #   - Gatilho legado (store-gantt-refresh) — fallback até IM-75.
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-gantt-data-projects",    "data"),
        Output("store-gantt-data-categories",  "data"),
        Output("store-gantt-data-activities",  "data"),
        Output("store-gantt-data-assignments", "data"),
        Output("store-gantt-data-employees",   "data"),
        Output("store-gantt-data-status",      "data"),
        Input("url",                 "pathname"),
        Input("btn-gantt-refresh",   "n_clicks"),
        Input("store-gantt-refresh", "data"),
        prevent_initial_call=False,
    )
    def load_gantt_data(pathname, refresh_clicks, internal_refresh):
        """Lê todas as entidades estruturais do MongoDB e popula os stores."""
        # Guard de rota — só atua na página do Gantt
        if pathname != ROUTE_GANTT:
            raise PreventUpdate

        # Sinaliza erro explícito se alguma coleção do Gantt estiver inacessível
        # (sem depender de exceção que pymongo raramente levanta).
        for col_name in ("gantt_projects", "gantt_categories", "gantt_activities",
                         "gantt_assignments", "gantt_employees"):
            if gantt_db._col(col_name) is None:
                return None, None, None, None, None, "error"

        try:
            projects   = gantt_db.get_all_projects()
            employees  = gantt_db.get_all_employees()
            categories = gantt_db.get_all_categories()
            activities = gantt_db.get_all_activities()
            ids = [a["_id"] for a in activities]
            assignments = gantt_db.get_assignments_by_activities(ids)
            return projects, categories, activities, assignments, employees, "ready"
        except Exception:
            return None, None, None, None, None, "error"

    # ------------------------------------------------------------------
    # CB-01 — Renderizar Gantt
    # Consome stores de dados (CB-00) e stores de UI; zero queries MongoDB
    # em re-renders visuais (SP-15 item 1).
    # ------------------------------------------------------------------
    @app.callback(
        Output("gantt-chart-container", "children"),
        Input("store-gantt-data-projects",    "data"),
        Input("store-gantt-data-categories",  "data"),
        Input("store-gantt-data-activities",  "data"),
        Input("store-gantt-data-assignments", "data"),
        Input("store-gantt-data-employees",   "data"),
        Input("store-gantt-data-status",      "data"),
        Input("store-gantt-granularity",      "data"),
        State("store-gantt-projects-state",   "data"),
        State("store-gantt-categories-state", "data"),
        State("store-gantt-activities-state", "data"),
        Input("store-gantt-hour-offset",      "data"),
        Input("store-gantt-filter",           "data"),
        Input("store-gantt-view-mode",        "data"),
        State("store-gantt-employees-state",  "data"),
        prevent_initial_call=False,
    )
    def render_gantt(projects, categories, activities, assignments, employees, status,
                     granularity, projects_state, categories_state, activities_state,
                     hour_offset, filter_query, view_mode, employees_state):
        # Empty states (DS-14) — prioridade: erro > loading > vazio
        if status == "error":
            return _gantt_error_state()
        if any(s is None for s in (projects, categories, activities,
                                   assignments, employees)):
            return _gantt_loading_state()
        if not projects and not categories and not activities:
            return _gantt_empty_state()

        # Cascata: só renderizar categorias/atividades de projetos ativos
        # (filtragem em memória, zero queries — SP-15 item 6)
        active_proj_ids = {str(p["_id"]) for p in projects}
        categories_active = [
            c for c in categories
            if str(c.get("projeto_id", "")) in active_proj_ids
        ]
        active_cat_ids = {str(c["_id"]) for c in categories_active}
        activities_active = [
            a for a in activities
            if str(a.get("categoria_id", "")) in active_cat_ids
        ]

        if view_mode == "funcionario":
            return build_gantt_resource_view(
                employees, activities_active, assignments,
                categories_active, projects,
                granularity=granularity or "dias",
                hour_offset=hour_offset or 0,
                filter_query=filter_query or "",
                employees_state=employees_state or {},
            )
        return build_gantt_chart(
            categories_active, activities_active, assignments,
            granularity=granularity or "dias",
            projects=projects,
            projects_state=projects_state or {},
            expanded_state=categories_state or {},
            activities_state=activities_state or {},
            employees=employees,
            hour_offset=hour_offset or 0,
            filter_query=filter_query or "",
        )

    # ------------------------------------------------------------------
    # CB-01d — Toggle entre view "Projeto" e view "Funcionário"
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-gantt-view-mode",   "data"),
        Output("btn-view-projeto",        "color"),
        Output("btn-view-projeto",        "outline"),
        Output("btn-view-funcionario",    "color"),
        Output("btn-view-funcionario",    "outline"),
        Input("btn-view-projeto",         "n_clicks"),
        Input("btn-view-funcionario",     "n_clicks"),
        Input("store-gantt-view-mode",    "data"),
    )
    def toggle_view_mode(n_p, n_f, current):
        triggered = ctx.triggered_id
        if triggered == "btn-view-funcionario":
            new_mode = "funcionario"
        elif triggered == "btn-view-projeto":
            new_mode = "projeto"
        else:
            new_mode = current or "projeto"
        is_proj = new_mode == "projeto"
        return (
            new_mode,
            "primary" if is_proj else "secondary", not is_proj,
            "primary" if not is_proj else "secondary", is_proj,
        )

    # ------------------------------------------------------------------
    # CB-01e — Toggle expand/collapse de funcionário na view de Recursos
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-gantt-employees-state", "data"),
        Input({"type": "btn-toggle-employee-row", "index": ALL}, "n_clicks"),
        State("store-gantt-employees-state", "data"),
        prevent_initial_call=True,
    )
    def toggle_employee_row(n_clicks_list, current_state):
        if not any(n_clicks_list):
            raise PreventUpdate
        triggered = ctx.triggered_id
        if triggered is None:
            raise PreventUpdate
        emp_id = triggered["index"]
        state = dict(current_state or {})
        state[emp_id] = not state.get(emp_id, False)
        return state

    # ------------------------------------------------------------------
    # CB-01c — Cards de KPI (resumo rápido do estado atual)
    # ------------------------------------------------------------------
    @app.callback(
        Output("row-gantt-kpis", "children"),
        Input("store-gantt-refresh", "data"),
        Input("store-gantt-filter", "data"),
        prevent_initial_call=False,
    )
    def render_kpi_cards(refresh, filter_query):
        from src.components.gantt_chart import _activity_status_color, STATUS_COLOR_ATRASADA, STATUS_COLOR_ADIANTADA

        projects = gantt_db.get_all_projects()  # só ativos (não arquivados)
        active_proj_ids = {str(p["_id"]) for p in projects}
        categories = [c for c in gantt_db.get_all_categories()
                      if str(c.get("projeto_id", "")) in active_proj_ids]
        active_cat_ids = {str(c["_id"]) for c in categories}
        activities = [a for a in gantt_db.get_all_activities()
                      if str(a.get("categoria_id", "")) in active_cat_ids]

        # Aplica filtro se houver
        q = (filter_query or "").strip().lower()
        if q:
            matched_proj = {str(p["_id"]) for p in projects if q in p.get("nome", "").lower()}
            matched_cat  = {str(c["_id"]) for c in categories if q in c.get("nome", "").lower()}
            matched_act  = {str(a["_id"]) for a in activities if q in a.get("titulo", "").lower()}
            for c in categories:
                if str(c.get("projeto_id", "")) in matched_proj:
                    matched_cat.add(str(c["_id"]))
            for a in activities:
                if (str(a["_id"]) in matched_act
                        or str(a.get("categoria_id", "")) in matched_cat):
                    matched_act.add(str(a["_id"]))
            activities = [a for a in activities if str(a["_id"]) in matched_act]

        # Contadores por status
        n_atrasadas = n_no_prazo = n_adiantadas = 0
        for a in activities:
            c = _activity_status_color(a)
            if c == STATUS_COLOR_ATRASADA:
                n_atrasadas += 1
            elif c == STATUS_COLOR_ADIANTADA:
                n_adiantadas += 1
            else:
                n_no_prazo += 1

        def _card(titulo, valor, icone, cor):
            return dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className=f"bi {icone}",
                               style={"fontSize": "1.8rem", "color": cor, "opacity": "0.85"}),
                        html.Div([
                            html.Div(titulo, className="text-muted small",
                                     style={"fontSize": "0.72rem", "textTransform": "uppercase",
                                            "letterSpacing": "0.5px", "fontWeight": "600"}),
                            html.Div(str(valor), style={
                                "fontSize": "1.7rem", "fontWeight": "700", "color": cor,
                                "lineHeight": "1.1",
                            }),
                        ], style={"flex": "1", "marginLeft": "12px"}),
                    ], style={"display": "flex", "alignItems": "center"}),
                ], className="py-3 px-3"),
            ], className="shadow-sm",
               style={"border": "1px solid var(--bs-border-color)",
                      "borderLeft": f"4px solid {cor}"}),
                md=3, sm=6)

        return [
            _card("Projetos ativos", len(projects),     "bi-folder-fill",       "#66A593"),
            _card("Atividades",      len(activities),   "bi-list-check",        "#1E88E5"),
            _card("Atrasadas",       n_atrasadas,       "bi-exclamation-triangle-fill", "#E53935"),
            _card("Adiantadas",      n_adiantadas,      "bi-check-circle-fill", "#43A047"),
        ]

    # ------------------------------------------------------------------
    # CB-01b — Sincronizar input de busca → store
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-gantt-filter", "data"),
        Input("input-gantt-filter", "value"),
        prevent_initial_call=True,
    )
    def update_filter_store(value):
        return (value or "").strip()

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
    # CB-03b — Toggle expand/collapse de projeto
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-gantt-projects-state", "data"),
        Input({"type": "btn-toggle-project", "index": ALL}, "n_clicks"),
        State("store-gantt-projects-state", "data"),
        prevent_initial_call=True,
    )
    def toggle_project(n_clicks_list, current_state):
        if not any(n_clicks_list):
            raise PreventUpdate
        triggered = ctx.triggered_id
        if triggered is None:
            raise PreventUpdate
        proj_id = triggered["index"]
        state = dict(current_state or {})
        state[proj_id] = not state.get(proj_id, True)
        return state

    # ------------------------------------------------------------------
    # CB-04 — Expandir tudo / Recolher tudo
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-gantt-projects-state",   "data", allow_duplicate=True),
        Output("store-gantt-categories-state", "data", allow_duplicate=True),
        Output("store-gantt-activities-state", "data", allow_duplicate=True),
        Output("store-gantt-employees-state",  "data", allow_duplicate=True),
        Input("btn-expand-all",  "n_clicks"),
        Input("btn-collapse-all", "n_clicks"),
        prevent_initial_call=True,
    )
    def expand_collapse_all(expand_clicks, collapse_clicks):
        triggered_id = ctx.triggered_id
        if triggered_id is None:
            raise PreventUpdate
        value = triggered_id == "btn-expand-all"
        projects   = gantt_db.get_all_projects()
        categories = gantt_db.get_all_categories()
        activities = gantt_db.get_all_activities()
        employees  = gantt_db.get_all_employees()
        return (
            {p["_id"]: value for p in projects},
            {c["_id"]: value for c in categories},
            {a["_id"]: value for a in activities},
            {e["_id"]: value for e in employees},
        )

    # ------------------------------------------------------------------
    # CB-05 — Abrir modal de categoria (criar ou editar)
    # ------------------------------------------------------------------
    @app.callback(
        Output("modal-category", "is_open"),
        Output("title-modal-category", "children"),
        Output("dropdown-category-projeto", "options"),
        Output("dropdown-category-projeto", "value"),
        Output("input-category-nome", "value"),
        Output("input-category-inicio", "value"),
        Output("input-category-fim", "value"),
        Output("store-category-editing-id", "data"),
        Input({"type": "btn-new-category-in-proj", "index": ALL}, "n_clicks"),
        Input({"type": "btn-edit-category",       "index": ALL}, "n_clicks"),
        Input("btn-cancel-category", "n_clicks"),
        prevent_initial_call=True,
    )
    def open_category_modal(new_in_proj_clicks, edit_clicks, cancel):
        triggered_id = ctx.triggered_id
        if triggered_id is None:
            raise PreventUpdate
        projects = gantt_db.get_all_projects()
        proj_opts = [{"label": p["nome"], "value": p["_id"]} for p in projects]
        if triggered_id == "btn-cancel-category":
            return False, no_update, no_update, no_update, no_update, no_update, no_update, no_update
        if isinstance(triggered_id, dict) and triggered_id.get("type") == "btn-new-category-in-proj":
            if not any(new_in_proj_clicks):
                raise PreventUpdate
            proj_id = triggered_id["index"]
            return True, "Nova Categoria", proj_opts, proj_id, "", "", "", None
        if isinstance(triggered_id, dict) and triggered_id.get("type") == "btn-edit-category":
            if not any(edit_clicks):
                raise PreventUpdate
            cat_id = triggered_id["index"]
            cat = gantt_db.get_category_by_id(cat_id)
            if not cat:
                raise PreventUpdate
            return (
                True, "Editar Categoria",
                proj_opts, str(cat.get("projeto_id", "")),
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
        State("dropdown-category-projeto", "value"),
        State("input-category-nome", "value"),
        State("input-category-inicio", "value"),
        State("input-category-fim", "value"),
        State("store-category-editing-id", "data"),
        State("store-gantt-refresh", "data"),
        prevent_initial_call=True,
    )
    def save_category(n_clicks, projeto_id, nome, inicio, fim, editing_id, refresh):
        if not n_clicks:
            raise PreventUpdate
        if current_user.level < 2:
            raise PreventUpdate
        inicio_dt = _parse_dt(inicio)
        fim_dt    = _parse_dt(fim)
        if not nome or not inicio_dt or not fim_dt or not projeto_id:
            items = [html.Li("Todos os campos obrigatórios devem ser preenchidos.")]
            return no_update, no_update, True, items
        data = {"nome": nome, "projeto_id": projeto_id,
                "data_hora_inicio": inicio_dt, "data_hora_fim": fim_dt}
        ctx_val = ValidationContext()
        errors = CATEGORY_PIPELINE.run(data, ctx_val)
        if errors:
            items = [html.Li(e) for e in errors]
            return no_update, no_update, True, items
        if editing_id:
            old = gantt_db.get_category_by_id(editing_id)
            gantt_db.update_category(editing_id, data)
            if old:
                for field in ("nome", "projeto_id", "data_hora_inicio", "data_hora_fim"):
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
        if entity == "projeto":
            gantt_db.delete_project(eid)
            _log("exclusao", "projeto", eid, ename)
        elif entity == "categoria":
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
        Output("dropdown-activity-projeto", "options"),
        Output("dropdown-activity-projeto", "value"),
        Output("dropdown-activity-categoria", "options"),
        Output("dropdown-activity-categoria", "value"),
        Output("input-activity-inicio", "value"),
        Output("input-activity-fim", "value"),
        Output("input-activity-progresso", "value"),
        Output("div-activity-progresso", "style"),
        Output("input-activity-observacao", "value"),
        Output("store-activity-editing-id", "data"),
        Input({"type": "btn-new-activity-in-cat", "index": ALL}, "n_clicks"),
        Input({"type": "btn-edit-activity",       "index": ALL}, "n_clicks"),
        Input("btn-cancel-activity", "n_clicks"),
        prevent_initial_call=True,
    )
    def open_activity_modal(new_in_cat_clicks, edit_clicks, cancel):
        triggered_id = ctx.triggered_id
        if triggered_id is None:
            raise PreventUpdate
        projects   = gantt_db.get_all_projects()
        proj_opts  = [{"label": p["nome"], "value": p["_id"]} for p in projects]
        hidden  = {"display": "none"}
        visible = {"display": "block"}
        if triggered_id == "btn-cancel-activity":
            return False, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update
        if isinstance(triggered_id, dict) and triggered_id.get("type") == "btn-new-activity-in-cat":
            if not any(new_in_cat_clicks):
                raise PreventUpdate
            cat_id = triggered_id["index"]
            cat = gantt_db.get_category_by_id(cat_id)
            if not cat:
                raise PreventUpdate
            proj_id = str(cat.get("projeto_id", ""))
            cats_for_proj = [
                c for c in gantt_db.get_all_categories()
                if str(c.get("projeto_id", "")) == proj_id
            ]
            cat_opts = [{"label": c["nome"], "value": c["_id"]} for c in cats_for_proj]
            return (
                True, "Nova Atividade", "",
                proj_opts, proj_id,
                cat_opts, cat_id,
                "", "", 0, hidden, "", None,
            )
        if isinstance(triggered_id, dict) and triggered_id.get("type") == "btn-edit-activity":
            if not any(edit_clicks):
                raise PreventUpdate
            act_id = triggered_id["index"]
            act = gantt_db.get_activity_by_id(act_id)
            if not act:
                raise PreventUpdate
            cat = gantt_db.get_category_by_id(str(act["categoria_id"]))
            proj_id = str(cat["projeto_id"]) if cat and cat.get("projeto_id") else None
            cats_for_proj = [
                c for c in gantt_db.get_all_categories()
                if proj_id and str(c.get("projeto_id", "")) == proj_id
            ]
            cat_opts = [{"label": c["nome"], "value": c["_id"]} for c in cats_for_proj]
            return (
                True, "Editar Atividade",
                act["titulo"],
                proj_opts, proj_id,
                cat_opts, str(act["categoria_id"]),
                _fmt_dt(act["data_hora_inicio"]),
                _fmt_dt(act["data_hora_fim"]),
                act.get("progresso_real", 0),
                visible,
                act.get("observacao", ""),
                act_id,
            )
        raise PreventUpdate

    # ------------------------------------------------------------------
    # CB-08b — Filtrar categorias ao trocar projeto no modal de atividade
    # ------------------------------------------------------------------
    @app.callback(
        Output("dropdown-activity-categoria", "options", allow_duplicate=True),
        Output("dropdown-activity-categoria", "value",   allow_duplicate=True),
        Input("dropdown-activity-projeto", "value"),
        State("dropdown-activity-categoria", "value"),
        State("modal-activity", "is_open"),
        prevent_initial_call=True,
    )
    def filter_categories_by_project(proj_id, current_cat, modal_open):
        if not modal_open or not proj_id:
            raise PreventUpdate
        cats = [
            c for c in gantt_db.get_all_categories()
            if str(c.get("projeto_id", "")) == proj_id
        ]
        opts = [{"label": c["nome"], "value": c["_id"]} for c in cats]
        valid_ids = {c["_id"] for c in cats}
        new_value = current_cat if current_cat in valid_ids else None
        return opts, new_value

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
        State("input-activity-observacao", "value"),
        State("store-activity-editing-id", "data"),
        State("store-gantt-refresh", "data"),
        prevent_initial_call=True,
    )
    def save_activity(n_clicks, titulo, cat_id, inicio, fim, progresso, observacao,
                      editing_id, refresh):
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
            "observacao":       (observacao or "").strip(),
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
                for field in ("titulo", "data_hora_inicio", "data_hora_fim",
                              "progresso_real", "observacao"):
                    old_val = old.get(field)
                    if field == "observacao":
                        old_val = old_val or ""
                    if str(old_val) != str(data.get(field)):
                        _log("edicao", "atividade", editing_id, titulo, field, old_val, data[field])
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
            if not any(new_clicks):
                raise PreventUpdate
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
    # CB-15a — Abrir/fechar modal de funcionários
    # ------------------------------------------------------------------
    @app.callback(
        Output("modal-employee-list", "is_open"),
        Input("btn-open-employee-list", "n_clicks"),
        Input("btn-close-employee-list", "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_employee_list(open_clicks, close_clicks):
        return ctx.triggered_id == "btn-open-employee-list"

    # ------------------------------------------------------------------
    # CB-15b — Carregar aba "Cadastrados"
    # ------------------------------------------------------------------
    @app.callback(
        Output("div-employee-list-content", "children"),
        Input("modal-employee-list", "is_open"),
        Input("store-gantt-refresh", "data"),
        prevent_initial_call=True,
    )
    def load_employee_list(is_open, refresh):
        if not is_open:
            raise PreventUpdate
        employees = gantt_db.get_all_employees()
        if not employees:
            return html.P("Nenhum funcionário cadastrado. Use a aba 'Novo / Editar' para criar.",
                          className="text-muted")
        TURNO_LABEL = {"A": "Turno A (00h–06h)", "B": "Turno B (06h–15h)", "C": "Turno C (15h–00h)", "ADM": "Administrativo (08h–17h)"}
        rows = []
        for emp in employees:
            emp_id = str(emp["_id"])
            ativo  = emp.get("ativo", True)
            rows.append(html.Tr([
                html.Td(emp["nome"]),
                html.Td(TURNO_LABEL.get(emp.get("turno_padrao", "B"), "—")),
                html.Td(html.Span("Ativo" if ativo else "Inativo",
                                  className=f"badge bg-{'success' if ativo else 'secondary'}")),
                html.Td([
                    html.Button(
                        html.I(className="bi bi-pencil"),
                        id={"type": "btn-edit-employee", "index": emp_id},
                        title="Editar",
                        style={"background": "none", "border": "none", "padding": "0 4px",
                               "cursor": "pointer", "color": "var(--bs-primary)", "fontSize": "0.82rem"},
                    ),
                    html.Button(
                        html.I(className="bi bi-slash-circle" if ativo else "bi bi-check-circle"),
                        id={"type": "btn-deactivate-employee", "index": emp_id},
                        title="Desativar" if ativo else "Reativar",
                        style={"background": "none", "border": "none", "padding": "0 4px",
                               "cursor": "pointer",
                               "color": "var(--bs-warning)" if ativo else "var(--bs-success)",
                               "fontSize": "0.82rem"},
                    ),
                ]),
            ]))
        return dbc.Table(
            [
                html.Thead(html.Tr([
                    html.Th("Nome"), html.Th("Turno"), html.Th("Status"), html.Th("Ações"),
                ])),
                html.Tbody(rows),
            ],
            bordered=True, hover=True, size="sm", responsive=True,
        )

    # ------------------------------------------------------------------
    # CB-15 — Controlar aba ativa e preencher formulário
    # ------------------------------------------------------------------
    @app.callback(
        Output("tabs-employee", "active_tab"),
        Output("employee-form-title", "children"),
        Output("input-employee-nome", "value"),
        Output("radio-employee-turno", "value"),
        Output("store-employee-editing-id", "data"),
        Output("div-employee-photo-preview", "children"),
        Output("btn-clear-employee-photo", "style"),
        Output("store-employee-photo-staged", "data"),
        Input({"type": "btn-edit-employee", "index": ALL}, "n_clicks"),
        Input("btn-cancel-employee", "n_clicks"),
        prevent_initial_call=True,
    )
    def open_employee_form(edit_clicks, cancel):
        triggered_id = ctx.triggered_id
        if triggered_id is None:
            raise PreventUpdate
        if triggered_id == "btn-cancel-employee":
            return ("tab-emp-list", no_update, no_update, no_update, no_update,
                    no_update, no_update, no_update)
        if isinstance(triggered_id, dict) and triggered_id.get("type") == "btn-edit-employee":
            if not any(edit_clicks):
                raise PreventUpdate
            emp_id = triggered_id["index"]
            emp = gantt_db.get_employee_by_id(emp_id)
            if not emp:
                raise PreventUpdate
            if gantt_db.has_employee_photo(emp_id):
                preview = html.Img(
                    src=f"/api/gantt/employee-photo/{emp_id}?t={int(datetime.utcnow().timestamp())}",
                    style={"width": "64px", "height": "64px", "borderRadius": "50%",
                           "objectFit": "cover", "border": "2px solid var(--bs-border-color)"},
                )
                btn_style = {"display": "inline-block"}
            else:
                preview = ""
                btn_style = {"display": "none"}
            return ("tab-emp-form", "Editar Funcionário", emp["nome"],
                    emp.get("turno_padrao", "B"), emp_id,
                    preview, btn_style, None)
        raise PreventUpdate

    # ------------------------------------------------------------------
    # CB-18 — Solicitar desativação de funcionário
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-confirm-delete", "data", allow_duplicate=True),
        Output("modal-confirm-delete", "is_open", allow_duplicate=True),
        Output("text-confirm-delete-name", "children", allow_duplicate=True),
        Input({"type": "btn-deactivate-employee", "index": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def request_deactivate_employee(n_clicks_list):
        if not any(n_clicks_list):
            raise PreventUpdate
        triggered_id = ctx.triggered_id
        if not isinstance(triggered_id, dict):
            raise PreventUpdate
        emp_id = triggered_id["index"]
        emp = gantt_db.get_employee_by_id(emp_id)
        if not emp:
            raise PreventUpdate
        return (
            {"entity": "funcionario", "id": emp_id, "name": emp["nome"]},
            True, emp["nome"],
        )

    # ------------------------------------------------------------------
    # CB-16 — Salvar funcionário e retornar à aba de lista
    # ------------------------------------------------------------------
    @app.callback(
        Output("tabs-employee", "active_tab", allow_duplicate=True),
        Output("store-gantt-refresh", "data", allow_duplicate=True),
        Output("modal-validation-errors", "is_open", allow_duplicate=True),
        Output("list-validation-errors", "children", allow_duplicate=True),
        Output("input-employee-nome", "value", allow_duplicate=True),
        Output("radio-employee-turno", "value", allow_duplicate=True),
        Output("store-employee-editing-id", "data", allow_duplicate=True),
        Output("store-employee-photo-staged", "data", allow_duplicate=True),
        Input("btn-save-employee", "n_clicks"),
        State("input-employee-nome", "value"),
        State("radio-employee-turno", "value"),
        State("store-employee-editing-id", "data"),
        State("store-gantt-refresh", "data"),
        State("store-employee-photo-staged", "data"),
        prevent_initial_call=True,
    )
    def save_employee(n_clicks, nome, turno, editing_id, refresh, photo_staged):
        if not n_clicks:
            raise PreventUpdate
        if current_user.level < 2:
            raise PreventUpdate
        if not nome or not turno:
            items = [html.Li("Nome e turno são obrigatórios.")]
            return no_update, no_update, True, items, no_update, no_update, no_update, no_update
        if turno not in ("A", "B", "C", "ADM"):
            items = [html.Li("Turno inválido.")]
            return no_update, no_update, True, items, no_update, no_update, no_update, no_update
        data = {"nome": nome.strip(), "turno_padrao": turno}
        if editing_id:
            old = gantt_db.get_employee_by_id(editing_id)
            gantt_db.update_employee(editing_id, data)
            target_id = editing_id
            if old:
                for field in ("nome", "turno_padrao"):
                    if old.get(field) != data[field]:
                        _log("edicao", "funcionario", editing_id, nome, field, old.get(field), data[field])
        else:
            target_id = gantt_db.create_employee(data)
            _log("criacao", "funcionario", target_id, nome)

        # Aplica mudanças pendentes de foto staged no store
        if photo_staged == "__clear__":
            gantt_db.clear_employee_photo(target_id)
            _log("edicao", "funcionario", target_id, nome, "foto", "presente", "removida")
        elif isinstance(photo_staged, dict) and photo_staged.get("bytes_b64"):
            import base64
            photo_bytes = base64.b64decode(photo_staged["bytes_b64"])
            gantt_db.set_employee_photo(target_id, photo_bytes, photo_staged.get("mime", "image/jpeg"))
            _log("edicao", "funcionario", target_id, nome, "foto", "anterior", "atualizada")

        return "tab-emp-list", (refresh or 0) + 1, False, [], "", "B", None, None

    # ------------------------------------------------------------------
    # CB-16b — Upload de foto: processa arquivo, faz resize e salva no store
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-employee-photo-staged", "data", allow_duplicate=True),
        Output("div-employee-photo-preview", "children", allow_duplicate=True),
        Output("btn-clear-employee-photo", "style", allow_duplicate=True),
        Input("upload-employee-photo", "contents"),
        State("upload-employee-photo", "filename"),
        prevent_initial_call=True,
    )
    def stage_employee_photo(contents, filename):
        if not contents:
            raise PreventUpdate
        try:
            import base64, io
            from PIL import Image
            header, b64data = contents.split(",", 1)
            mime = header.split(":")[1].split(";")[0] if ":" in header else "image/jpeg"
            if mime not in ("image/jpeg", "image/png"):
                raise ValueError("Formato inválido")
            raw = base64.b64decode(b64data)
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            img.thumbnail((128, 128))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            out_bytes = buf.getvalue()
            out_b64 = base64.b64encode(out_bytes).decode("ascii")
            preview = html.Img(
                src=f"data:image/jpeg;base64,{out_b64}",
                style={"width": "64px", "height": "64px", "borderRadius": "50%",
                       "objectFit": "cover", "border": "2px solid var(--bs-border-color)"},
            )
            btn_visible = {"display": "inline-block"}
            return {"bytes_b64": out_b64, "mime": "image/jpeg"}, preview, btn_visible
        except Exception as e:
            msg = html.Small(f"Erro ao processar imagem: {e}", className="text-danger")
            return no_update, msg, no_update

    # ------------------------------------------------------------------
    # CB-16c — Botão "Remover foto" no formulário: marca staged como __clear__
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-employee-photo-staged", "data", allow_duplicate=True),
        Output("div-employee-photo-preview", "children", allow_duplicate=True),
        Output("btn-clear-employee-photo", "style", allow_duplicate=True),
        Input("btn-clear-employee-photo", "n_clicks"),
        prevent_initial_call=True,
    )
    def clear_staged_photo(n_clicks):
        if not n_clicks:
            raise PreventUpdate
        return "__clear__", "", {"display": "none"}

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
    # CB-22 — Abrir modal de projeto (criar ou editar)
    # ------------------------------------------------------------------
    @app.callback(
        Output("modal-project", "is_open"),
        Output("title-modal-project", "children"),
        Output("input-project-nome", "value"),
        Output("dropdown-project-tipo", "value"),
        Output("input-project-inicio", "value"),
        Output("input-project-fim", "value"),
        Output("input-project-observacoes", "value"),
        Output("store-project-editing-id", "data"),
        Input("btn-new-project", "n_clicks"),
        Input({"type": "btn-edit-project", "index": ALL}, "n_clicks"),
        Input("btn-cancel-project", "n_clicks"),
        prevent_initial_call=True,
    )
    def open_project_modal(new_clicks, edit_clicks, cancel):
        triggered_id = ctx.triggered_id
        if triggered_id is None:
            raise PreventUpdate
        if triggered_id == "btn-cancel-project":
            return False, no_update, no_update, no_update, no_update, no_update, no_update, no_update
        if triggered_id == "btn-new-project":
            return True, "Novo Projeto", "", None, "", "", "", None
        if isinstance(triggered_id, dict) and triggered_id.get("type") == "btn-edit-project":
            if not any(edit_clicks):
                raise PreventUpdate
            proj_id = triggered_id["index"]
            proj = gantt_db.get_project_by_id(proj_id)
            if not proj:
                raise PreventUpdate
            return (
                True, "Editar Projeto",
                proj["nome"], proj.get("tipo"),
                _fmt_dt(proj.get("data_hora_inicio")),
                _fmt_dt(proj.get("data_hora_fim")),
                proj.get("observacoes", ""),
                proj_id,
            )
        raise PreventUpdate

    # ------------------------------------------------------------------
    # CB-23 — Salvar projeto
    # ------------------------------------------------------------------
    @app.callback(
        Output("modal-project", "is_open", allow_duplicate=True),
        Output("store-gantt-refresh", "data", allow_duplicate=True),
        Output("modal-validation-errors", "is_open", allow_duplicate=True),
        Output("list-validation-errors", "children", allow_duplicate=True),
        Input("btn-save-project", "n_clicks"),
        State("input-project-nome", "value"),
        State("dropdown-project-tipo", "value"),
        State("input-project-inicio", "value"),
        State("input-project-fim", "value"),
        State("input-project-observacoes", "value"),
        State("store-project-editing-id", "data"),
        State("store-gantt-refresh", "data"),
        prevent_initial_call=True,
    )
    def save_project(n_clicks, nome, tipo, inicio, fim, observacoes, editing_id, refresh):
        if not n_clicks:
            raise PreventUpdate
        if current_user.level < 2:
            raise PreventUpdate
        inicio_dt = _parse_dt(inicio)
        fim_dt    = _parse_dt(fim)
        errs = []
        if not nome: errs.append("Nome é obrigatório.")
        if not tipo: errs.append("Tipo é obrigatório.")
        if not inicio_dt: errs.append("Data de início é obrigatória.")
        if not fim_dt:    errs.append("Data de fim é obrigatória.")
        if inicio_dt and fim_dt and fim_dt <= inicio_dt:
            errs.append("A data de fim deve ser posterior à de início.")
        if errs:
            return no_update, no_update, True, [html.Li(e) for e in errs]
        data = {
            "nome": nome.strip(), "tipo": tipo,
            "data_hora_inicio": inicio_dt, "data_hora_fim": fim_dt,
            "observacoes": observacoes or "",
        }
        if editing_id:
            old = gantt_db.get_project_by_id(editing_id)
            gantt_db.update_project(editing_id, data)
            if old:
                for field in ("nome", "tipo", "observacoes", "data_hora_inicio", "data_hora_fim"):
                    if str(old.get(field)) != str(data[field]):
                        _log("edicao", "projeto", editing_id, nome, field, old.get(field), data[field])
        else:
            new_id = gantt_db.create_project(data)
            _log("criacao", "projeto", new_id, nome)
        return False, (refresh or 0) + 1, False, []

    # ------------------------------------------------------------------
    # CB-24 — Solicitar exclusão de projeto
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-confirm-delete", "data", allow_duplicate=True),
        Output("modal-confirm-delete", "is_open", allow_duplicate=True),
        Output("text-confirm-delete-name", "children", allow_duplicate=True),
        Output("modal-block-info", "is_open", allow_duplicate=True),
        Output("text-block-info-title", "children", allow_duplicate=True),
        Output("text-block-info-message", "children", allow_duplicate=True),
        Input({"type": "btn-delete-project", "index": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def request_delete_project(n_clicks_list):
        if not any(n_clicks_list):
            raise PreventUpdate
        triggered_id = ctx.triggered_id
        if not isinstance(triggered_id, dict):
            raise PreventUpdate
        proj_id = triggered_id["index"]
        proj = gantt_db.get_project_by_id(proj_id)
        if not proj:
            raise PreventUpdate
        count = gantt_db.count_categories_in_project(proj_id)
        if count > 0:
            return (
                no_update, False, no_update,
                True,
                "Exclusão não permitida",
                f"O projeto \"{proj['nome']}\" possui {count} categoria(s) vinculada(s) e não pode ser excluído.",
            )
        return (
            {"entity": "projeto", "id": proj_id, "name": proj["nome"]},
            True, proj["nome"],
            False, no_update, no_update,
        )

    # ------------------------------------------------------------------
    # CB-26 — Arquivar projeto (ação direta, sem modal de confirmação)
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-gantt-refresh", "data", allow_duplicate=True),
        Input({"type": "btn-archive-project", "index": ALL}, "n_clicks"),
        State("store-gantt-refresh", "data"),
        prevent_initial_call=True,
    )
    def archive_project_action(n_clicks_list, refresh):
        if not any(n_clicks_list):
            raise PreventUpdate
        triggered_id = ctx.triggered_id
        if not isinstance(triggered_id, dict):
            raise PreventUpdate
        if current_user.level < 2:
            raise PreventUpdate
        proj_id = triggered_id["index"]
        proj = gantt_db.get_project_by_id(proj_id)
        if not proj:
            raise PreventUpdate
        gantt_db.archive_project(proj_id)
        _log("arquivamento", "projeto", proj_id, proj["nome"])
        return (refresh or 0) + 1

    # ------------------------------------------------------------------
    # CB-27 — Abrir/fechar modal de projetos arquivados
    # ------------------------------------------------------------------
    @app.callback(
        Output("modal-archived-projects", "is_open"),
        Input("btn-open-archived-projects", "n_clicks"),
        Input("btn-close-archived-projects", "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_archived_projects_modal(open_clicks, close_clicks):
        return ctx.triggered_id == "btn-open-archived-projects"

    # ------------------------------------------------------------------
    # CB-28 — Carregar lista de projetos arquivados
    # ------------------------------------------------------------------
    @app.callback(
        Output("div-archived-projects-content", "children"),
        Input("modal-archived-projects", "is_open"),
        Input("store-gantt-refresh", "data"),
        prevent_initial_call=True,
    )
    def load_archived_projects(is_open, refresh):
        if not is_open:
            raise PreventUpdate
        projects = gantt_db.get_archived_projects()
        if not projects:
            return html.P("Nenhum projeto arquivado.", className="text-muted")
        rows = []
        for p in projects:
            pid = str(p["_id"])
            arq_em = p.get("arquivado_em")
            arq_str = arq_em.strftime("%d/%m/%Y %H:%M") if isinstance(arq_em, datetime) else "—"
            rows.append(html.Tr([
                html.Td(p["nome"]),
                html.Td(p.get("tipo", "—")),
                html.Td(arq_str),
                html.Td(
                    html.Button(
                        [html.I(className="bi bi-arrow-counterclockwise me-1"), "Restaurar"],
                        id={"type": "btn-unarchive-project", "index": pid},
                        className="btn btn-sm btn-outline-success",
                        style={"fontSize": "0.78rem"},
                    ),
                ),
            ]))
        return dbc.Table(
            [
                html.Thead(html.Tr([
                    html.Th("Nome"), html.Th("Tipo"), html.Th("Arquivado em"), html.Th("Ações"),
                ])),
                html.Tbody(rows),
            ],
            bordered=True, hover=True, size="sm", responsive=True,
        )

    # ------------------------------------------------------------------
    # CB-29 — Restaurar projeto arquivado
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-gantt-refresh", "data", allow_duplicate=True),
        Input({"type": "btn-unarchive-project", "index": ALL}, "n_clicks"),
        State("store-gantt-refresh", "data"),
        prevent_initial_call=True,
    )
    def unarchive_project_action(n_clicks_list, refresh):
        if not any(n_clicks_list):
            raise PreventUpdate
        triggered_id = ctx.triggered_id
        if not isinstance(triggered_id, dict):
            raise PreventUpdate
        if current_user.level < 2:
            raise PreventUpdate
        proj_id = triggered_id["index"]
        proj = gantt_db.get_project_by_id(proj_id)
        if not proj:
            raise PreventUpdate
        gantt_db.unarchive_project(proj_id)
        _log("restauracao", "projeto", proj_id, proj["nome"])
        return (refresh or 0) + 1

    # ------------------------------------------------------------------
    # CB-21 — Toggle expand/collapse de atividade (atribuições)
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-gantt-activities-state", "data"),
        Input({"type": "btn-toggle-activity", "index": ALL}, "n_clicks"),
        State("store-gantt-activities-state", "data"),
        prevent_initial_call=True,
    )
    def toggle_activity(n_clicks_list, current_state):
        if not any(n_clicks_list):
            raise PreventUpdate
        triggered = ctx.triggered_id
        if triggered is None:
            raise PreventUpdate
        act_id = triggered["index"]
        state = dict(current_state or {})
        state[act_id] = not state.get(act_id, False)
        return state

    # ------------------------------------------------------------------
    # CB-19 — Mostrar/ocultar navegação de horas
    # ------------------------------------------------------------------
    @app.callback(
        Output("div-hour-nav", "style"),
        Input("store-gantt-granularity", "data"),
        prevent_initial_call=False,
    )
    def toggle_hour_nav(granularity):
        # Navegação de tempo sempre visível — funciona em todas as granularidades
        # (o offset é interpretado em horas, mas empurra a janela em qualquer modo).
        return {"display": "flex", "alignItems": "center", "gap": "0"}

    # ------------------------------------------------------------------
    # CB-20 — Atualizar offset de horas (◀ / ▶ / Hoje)
    # ------------------------------------------------------------------
    @app.callback(
        Output("store-gantt-hour-offset", "data"),
        Input("btn-hour-prev",  "n_clicks"),
        Input("btn-hour-next",  "n_clicks"),
        Input("btn-hour-today", "n_clicks"),
        Input("store-gantt-granularity", "data"),
        State("store-gantt-hour-offset", "data"),
        State("dropdown-hour-step", "value"),
        prevent_initial_call=True,
    )
    def update_hour_offset(prev, next_, today, granularity, current_offset, step):
        triggered = ctx.triggered_id
        if triggered in ("btn-hour-today", "store-gantt-granularity"):
            return 0
        step = step or 6
        offset = current_offset or 0
        if triggered == "btn-hour-prev":
            return offset - step
        if triggered == "btn-hour-next":
            return offset + step
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
