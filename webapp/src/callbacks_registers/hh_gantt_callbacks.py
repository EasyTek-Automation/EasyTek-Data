"""Callbacks do HH Gantt — troca de view, navegação de semana, drill no dia e render.

Modos:
- Semana: cortes de 4h, semana inteira; rótulos de dia são clicáveis (zoom-in → drill).
- Dia: janela de 1 dia em cortes de 0,5h; o próprio chip do dia é o zoom-out (volta à semana).

Navegação: ‹ Hoje › (semana a semana) + DatePicker (salto direto pra qualquer semana).
"""

from datetime import timedelta, datetime, date

from dash import Input, Output, State, ctx, html, ALL, no_update
import dash_bootstrap_components as dbc

from src.utils import hh_gantt_data as data
from src.components import hh_gantt_chart as gantt
from src.components import hh_week_picker

_DIAS_FULL = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def _kpi_cards(k):
    def card(label, value, sub, color):
        return dbc.Card(dbc.CardBody([
            html.Div(value, style={"fontSize": "1.4rem", "fontWeight": "700",
                                   "color": f"var(--bs-{color})", "lineHeight": "1.1"}),
            html.Div(label, style={"fontSize": "0.68rem", "fontWeight": "600",
                                   "textTransform": "uppercase"}),
            html.Div(sub, style={"fontSize": "0.64rem", "color": "var(--bs-secondary)"}),
        ], style={"padding": "10px 12px"}), style={"flex": "1", "minWidth": "118px"})

    return [
        card("Aproveit. típico", f"{k['mediana']:.0f}%", "mediana das operações", "success"),
        card("Aproveit. total", f"{k['total']:.0f}%", "Σreal ÷ Σplanejado", "info"),
        card("Taxa execução", f"{k['taxa_exec']:.0f}%", "plano concluído", "primary"),
        card("Não iniciadas", f"{k['nao_iniciadas']}", "planejadas sem apontamento", "warning"),
        card("Apontamentos", f"{k['n_apont']}", f"{k['n_ordens']} ordens · {k['n_tecnicos']} técnicos", "secondary"),
        card("Horas reais", gantt._fmt_h(k["horas_real"]), "no período", "dark"),
    ]


def register_hh_gantt_callbacks(app):

    # --- troca de view ---
    @app.callback(
        Output("store-hh-view", "data"),
        Output("btn-hh-view-ordem", "outline"),
        Output("btn-hh-view-func", "outline"),
        Input("btn-hh-view-ordem", "n_clicks"),
        Input("btn-hh-view-func", "n_clicks"),
        prevent_initial_call=True,
    )
    def _view(_o, _f):
        view = "funcionario" if ctx.triggered_id == "btn-hh-view-func" else "ordem"
        return view, view != "ordem", view != "funcionario"

    # --- navegação de semana (e sai do modo dia) ---
    @app.callback(
        Output("store-hh-week-offset", "data"),
        Output("store-hh-day", "data", allow_duplicate=True),
        Input("btn-hh-week-prev", "n_clicks"),
        Input("btn-hh-week-next", "n_clicks"),
        Input("btn-hh-week-today", "n_clicks"),
        State("store-hh-week-offset", "data"),
        prevent_initial_call=True,
    )
    def _week(_p, _n, _t, cur):
        off = cur or 0
        if ctx.triggered_id == "btn-hh-week-prev":
            return off - 1, None
        if ctx.triggered_id == "btn-hh-week-next":
            return off + 1, None
        return 0, None

    # --- navegação de mês no picker custom ---
    @app.callback(
        Output("store-hh-picker-month", "data"),
        Input({"type": "hh-pickmonth", "dir": ALL}, "n_clicks"),
        State("store-hh-picker-month", "data"),
        prevent_initial_call=True,
    )
    def _nav_month(nclicks, cur):
        if not any(nclicks or []):
            return no_update
        trig = ctx.triggered_id
        if not isinstance(trig, dict):
            return no_update
        y, m = map(int, cur.split("-"))
        d = trig.get("dir")
        if d == "prev":
            m -= 1
            if m == 0:
                m = 12; y -= 1
        elif d == "next":
            m += 1
            if m == 13:
                m = 1; y += 1
        elif d == "prev_year":
            y -= 1
        elif d == "next_year":
            y += 1
        return f"{y}-{m:02d}"

    # --- re-renderiza o conteúdo do picker (mês atual + semana selecionada) ---
    @app.callback(
        Output("hh-weekpick-content", "children"),
        Input("store-hh-picker-month", "data"),
        Input("store-hh-week-offset", "data"),
        Input("store-hh-day", "data"),
    )
    def _render_picker(month_iso, offset, day_iso):
        ds = data.get_dataset()
        y, m = map(int, month_iso.split("-"))
        if day_iso:
            d_sel = date.fromisoformat(day_iso)
        else:
            ws, _ = data.week_window(offset or 0)
            d_sel = ws.date()
        iso_y, iso_w, _ = d_sel.isocalendar()
        selected_iso = f"{iso_y}-W{iso_w:02d}"
        return hh_week_picker.build_week_picker(y, m, selected_iso,
                                                dmin=ds["date_min"], dmax=ds["date_max"])

    # --- clicar numa semana → salta + fecha popover ---
    @app.callback(
        Output("store-hh-week-offset", "data", allow_duplicate=True),
        Output("store-hh-day", "data", allow_duplicate=True),
        Output("pop-hh-weekpick", "is_open"),
        Input({"type": "hh-pick-week", "iso": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def _pick_week(nclicks):
        if not any(nclicks or []):
            return no_update, no_update, no_update
        trig = ctx.triggered_id
        iso = trig.get("iso", "") if isinstance(trig, dict) else ""
        if not iso or iso.startswith("__off__"):
            return no_update, no_update, no_update
        y, w = iso.split("-W")
        target = date.fromisocalendar(int(y), int(w), 1)
        return data.offset_for_date(target), None, False

    # --- zoom-in (clique no dia) / zoom-out (chip __back__) ---
    @app.callback(
        Output("store-hh-day", "data", allow_duplicate=True),
        Input({"type": "hh-day-btn", "date": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def _day_nav(day_clicks):
        trig = ctx.triggered_id
        if isinstance(trig, dict) and trig.get("type") == "hh-day-btn":
            if not any(day_clicks or []):
                return no_update
            dt = trig.get("date")
            return None if dt == "__back__" else dt
        return no_update

    # --- abrir/fechar painel de filtros ---
    @app.callback(
        Output("hh-filters-collapse", "is_open"),
        Input("btn-hh-filters-toggle", "n_clicks"),
        State("hh-filters-collapse", "is_open"),
        prevent_initial_call=True,
    )
    def _toggle_filters(_n, is_open):
        return not is_open

    # --- aplicar filtros ---
    @app.callback(
        Output("store-hh-filters", "data"),
        Output("hh-filters-summary", "children"),
        Input("btn-hh-apply-filters", "n_clicks"),
        State("hh-f-tecnicos", "value"), State("hh-f-centros", "value"), State("hh-f-tipos", "value"),
        State("hh-f-equip", "value"), State("hh-f-ordem", "value"), State("hh-f-bandas", "value"),
        State("hh-f-durmin", "value"), State("hh-f-showplan", "value"), State("hh-f-naoplan", "value"),
        prevent_initial_call=True,
    )
    def _apply(_n, tec, cen, tip, eq, ordem, bandas, durmin, showplan, naoplan):
        f = {"tecnicos": tec or [], "centros": cen or [], "tipos": tip or [],
             "equipamentos": eq or [], "ordem": (ordem or "").strip(), "bandas": bandas or [],
             "dur_min": int(durmin or 0), "show_plan": "plan" in (showplan or []),
             "so_nao_planejadas": "naoplan" in (naoplan or [])}
        n = sum(bool(f[k]) for k in ("tecnicos", "centros", "tipos", "equipamentos", "ordem", "bandas"))
        n += 1 if f["dur_min"] > 0 else 0
        n += 1 if f["so_nao_planejadas"] else 0
        return f, ("sem filtros" if n == 0 else f"{n} filtro(s) ativo(s)")

    # --- limpar filtros ---
    @app.callback(
        Output("hh-f-tecnicos", "value"), Output("hh-f-centros", "value"),
        Output("hh-f-tipos", "value"), Output("hh-f-equip", "value"),
        Output("hh-f-ordem", "value"), Output("hh-f-bandas", "value"),
        Output("hh-f-durmin", "value"), Output("hh-f-showplan", "value"),
        Output("hh-f-naoplan", "value"),
        Output("store-hh-filters", "data", allow_duplicate=True),
        Output("hh-filters-summary", "children", allow_duplicate=True),
        Input("btn-hh-clear-filters", "n_clicks"),
        prevent_initial_call=True,
    )
    def _clear(_n):
        return None, None, None, None, "", None, 0, ["plan"], [], {}, "sem filtros"

    # --- ordenação das linhas ---
    @app.callback(
        Output("store-hh-sort", "data"),
        Output("btn-hh-sort-data", "outline"),
        Output("btn-hh-sort-ordem", "outline"),
        Input("btn-hh-sort-data", "n_clicks"),
        Input("btn-hh-sort-ordem", "n_clicks"),
        prevent_initial_call=True,
    )
    def _sort(_d, _o):
        s = "data" if ctx.triggered_id == "btn-hh-sort-data" else "ordem"
        return s, s != "data", s != "ordem"

    # --- escopo das linhas (executado / planejado / ambos) ---
    @app.callback(
        Output("store-hh-scope", "data"),
        Output("btn-hh-scope-exec", "outline"),
        Output("btn-hh-scope-plan", "outline"),
        Output("btn-hh-scope-both", "outline"),
        Input("btn-hh-scope-exec", "n_clicks"),
        Input("btn-hh-scope-plan", "n_clicks"),
        Input("btn-hh-scope-both", "n_clicks"),
        prevent_initial_call=True,
    )
    def _scope(_e, _p, _b):
        tid = ctx.triggered_id or "btn-hh-scope-exec"
        s = {"btn-hh-scope-exec": "exec", "btn-hh-scope-plan": "plan",
             "btn-hh-scope-both": "both"}.get(tid, "exec")
        return s, s != "exec", s != "plan", s != "both"

    # (expand/collapse de ordens é 100% clientside via assets/hh_gantt_toggle.js)

    # --- render principal ---
    @app.callback(
        Output("hh-gantt-container", "children"),
        Output("hh-kpi-strip", "children"),
        Output("hh-week-label", "children"),
        Input("store-hh-view", "data"),
        Input("store-hh-week-offset", "data"),
        Input("store-hh-day", "data"),
        Input("store-hh-filters", "data"),
        Input("store-hh-sort", "data"),
        Input("store-hh-scope", "data"),
    )
    def _render(view, offset, day_iso, filters, sort, scope):
        if day_iso:
            d = date.fromisoformat(day_iso)
            t_start = datetime(d.year, d.month, d.day)
            t_end = t_start + timedelta(days=1)
            slot, clickable = 0.5, False
            wk = d.isocalendar()[1]
            label = f"🔍 {_DIAS_FULL[d.weekday()]}, {d.strftime('%d/%m/%Y')} · Semana {wk} · detalhe 30 min"
        else:
            t_start, t_end = data.week_window(offset or 0)
            slot, clickable = 4, True
            wk = t_start.isocalendar()[1]
            label = f"Semana {wk} · {t_start.strftime('%d/%m')} – {(t_end - timedelta(days=1)).strftime('%d/%m/%Y')}"

        confs = data.apply_filters(data.confs_in_window(t_start, t_end), filters)
        fdict = filters or {}
        # se filtro "só não planejadas" ligado → faixa azul não faz sentido (sem agendamento)
        show_plan = fdict.get("show_plan", True) and not fdict.get("so_nao_planejadas")
        sort = sort or "ordem"
        scope = scope or "exec"
        if view == "funcionario":
            body = gantt.build_view_employee(t_start, t_end, slot, clickable_days=clickable,
                                             confs=confs, sort=sort, scope=scope)
        else:
            body = gantt.build_view_order(t_start, t_end, slot, clickable_days=clickable,
                                          confs=confs, show_plan=show_plan, sort=sort,
                                          scope=scope)
        kpis = _kpi_cards(gantt.compute_kpis(t_start, t_end, confs=confs))
        return body, kpis, label
