"""Render do HH Gantt — duas visualizações sobre os dados reais do SAP.

View "ordem"     : lista de ordens; cada ordem empilha os técnicos que a apontaram.
                   Faixa pálida = janela planejada (dias FSAVD→FSEDD); blocos = apontamentos
                   reais no relógio (hora ISDZ/IEDZ). Colunas de contagem (apontamentos + técnicos).
View "funcionario": lista de técnicos; blocos reais dele + fundo tingido só nos dias anormais
                   (hora extra / inviável — BR-08, capacidade fake).

Granularidade: semana em cortes de 4h (cabe inteira). Clicar num dia → drill no dia em 0,5h.
Esquema de cor enxuto: barra real monocromática; planejado cinza; sem arco-íris por entidade.
Reusa o modelo de posicionamento por % do `gantt_chart` (HTML/CSS div, não Plotly).
"""

from datetime import datetime, timedelta

from dash import html

from src.components.gantt_chart import _to_pct
from src.utils import hh_gantt_data as data

LEFT_W = 300  # px coluna esquerda

# Capacidade fake por técnico (BR-08 é cadastro manual — inexistente, inventado p/ mock)
CAP_NOMINAL_MIN = 8 * 60    # 480
CAP_TETO_MIN = 10 * 60      # 600

# Esquema de cor — 3 camadas distintas
COL_REAL = "#2f6fb0"        # Executado: fallback azul (AUART desconhecido)
COL_PLAN = "#9ec5fe"        # Planejado: janela programada IW37 (azul claro sólido)
# Disponibilidade (turno) usa CSS class .hh-shift-cell (hachurado cinza + dotted)

# Cor do bloco Executado por tipo de ordem (AUART)
COL_BY_AUART = {
    "YPM1": "#c0392b",      # corretiva — vermelho terra
    "YPM2": "#27ae60",      # — verde
    "YPM9": "#8e44ad",      # preventiva — roxo
}


def _col_auart(auart):
    return COL_BY_AUART.get((auart or "").strip(), COL_REAL)


def _fmt_h(minutes):
    """Minutos → 'Xh Ymin' compacto."""
    minutes = int(round(minutes))
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h}h{m:02d}"
    if h:
        return f"{h}h"
    return f"{m}min"


# ---------------------------------------------------------------------------
# Eixo de tempo
# ---------------------------------------------------------------------------

_DIAS_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
_DIAS_PT_FULL = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def _axis(t_start, t_end, slot_h, clickable_days=False):
    """Marcadores: linha grossa + rótulo por dia; linha fina + hora a cada slot_h.
    clickable_days=True → o rótulo do dia vira botão (drill no dia)."""
    out = []
    cursor = t_start
    while cursor <= t_end:
        is_day = cursor.hour == 0 and cursor.minute == 0
        left = _to_pct(cursor, t_start, t_end)
        out.append(html.Div(style={
            "position": "absolute", "left": f"{left:.4f}%", "top": "0", "bottom": "0",
            "borderLeft": ("2px solid var(--bs-body-color)" if is_day else "1px dashed var(--bs-border-color)"),
            "zIndex": "1", "pointerEvents": "none",
        }))
        if is_day and cursor < t_end:
            if clickable_days:
                out.append(html.Button(
                    [html.Div([html.I(className="bi bi-zoom-in me-1", style={"fontSize": "0.6rem"}),
                               _DIAS_PT[cursor.weekday()]],
                              style={"fontWeight": "700", "fontSize": "0.72rem"}),
                     html.Div(cursor.strftime("%d/%m"), style={"fontSize": "0.66rem", "opacity": "0.8"})],
                    id={"type": "hh-day-btn", "date": cursor.date().isoformat()},
                    n_clicks=0, title="Abrir o dia em detalhe (cortes de 30 min)",
                    style={"position": "absolute", "left": f"{left:.4f}%", "top": "3px", "height": "34px",
                           "padding": "2px 8px 2px 4px", "whiteSpace": "nowrap", "textAlign": "left",
                           "color": "#fff"},
                    className="hh-day-btn"))
            else:
                # modo dia: o próprio chip é o ZOOM-OUT (mesma região do zoom-in) e carrega
                # a referência completa da data + semana sendo analisada.
                wk = cursor.isocalendar()[1]
                out.append(html.Button(
                    [html.Div([html.I(className="bi bi-zoom-out me-1", style={"fontSize": "0.62rem"}),
                               f"{_DIAS_PT_FULL[cursor.weekday()]}"],
                              style={"fontWeight": "700", "fontSize": "0.74rem"}),
                     html.Div(f"{cursor.strftime('%d/%m/%Y')} · Semana {wk}",
                              style={"fontSize": "0.66rem", "opacity": "0.85"})],
                    id={"type": "hh-day-btn", "date": "__back__"}, n_clicks=0,
                    title="Voltar à semana",
                    style={"position": "absolute", "left": f"{left:.4f}%", "top": "3px", "height": "34px",
                           "padding": "2px 10px 2px 6px", "whiteSpace": "nowrap", "textAlign": "left",
                           "color": "#fff"},
                    className="hh-day-btn hh-day-btn-back"))
        elif not is_day:
            out.append(html.Div(cursor.strftime("%H:%M"), style={
                "position": "absolute", "left": f"{left:.4f}%", "bottom": "2px",
                "paddingLeft": "2px", "fontSize": "0.56rem", "color": "var(--bs-secondary)",
                "whiteSpace": "nowrap"}))
        cursor += timedelta(hours=slot_h)
    return out


def _now_line(t_start, t_end):
    now = datetime.utcnow() - timedelta(hours=3)
    if not (t_start <= now <= t_end):
        return []
    return [html.Div(style={
        "position": "absolute", "left": f"{_to_pct(now, t_start, t_end):.4f}%",
        "top": "0", "bottom": "0", "width": "2px", "backgroundColor": "var(--bs-danger)",
        "zIndex": "5", "pointerEvents": "none",
    })]


def _min_width(t_start, t_end, slot_h):
    days = (t_end - t_start).total_seconds() / 86400.0
    slots = days * 24 / slot_h
    return int(max(slots * 34, 900))


def _seg(left_pct, width_pct, color, top, height, tooltip, opacity=0.92, radius="4px", border=True):
    """Bloco posicionado (segmento real ou faixa planejada)."""
    style = {
        "position": "absolute", "left": f"{left_pct:.4f}%", "width": f"{max(width_pct, 0.3):.4f}%",
        "top": top, "height": height, "minWidth": "3px",
        "backgroundColor": color, "opacity": str(opacity),
        "borderRadius": radius, "zIndex": "3", "cursor": "help",
    }
    if border:
        style["border"] = "1px solid rgba(255,255,255,0.75)"
    return html.Div(title=tooltip, style=style)


def _shift_cells(days, turno, t_start, t_end):
    """Lista de Divs hachurados (disponibilidade) + âmbar hachurado (extra +2h)
    para o turno do funcionário, um par por dia da janela."""
    out = []
    for d0 in days:
        ns_dt, ne_dt = data.shift_block(turno, d0)
        ex_dt = ne_dt + timedelta(hours=data.EXTRA_HORAS)
        ns_c = max(ns_dt, t_start); ne_c = min(ne_dt, t_end)
        if ne_c > ns_c:
            lp = _to_pct(ns_c, t_start, t_end)
            wp = _to_pct(ne_c, t_start, t_end) - lp
            out.append(html.Div(
                className="hh-shift-cell",
                title=f"{d0.strftime('%d/%m')} · disponível (turno {turno}) "
                      f"{ns_dt.strftime('%H:%M')}–{ne_dt.strftime('%H:%M')}",
                style={"position": "absolute", "left": f"{lp:.4f}%",
                       "width": f"{wp:.4f}%", "top": "0", "bottom": "0", "zIndex": "1"}))
        ex_s = max(ne_dt, t_start); ex_e = min(ex_dt, t_end)
        if ex_e > ex_s:
            lp = _to_pct(ex_s, t_start, t_end)
            wp = _to_pct(ex_e, t_start, t_end) - lp
            out.append(html.Div(
                className="hh-extra-cell",
                title=f"{d0.strftime('%d/%m')} · extra +{data.EXTRA_HORAS}h "
                      f"({ne_dt.strftime('%H:%M')}–{ex_dt.strftime('%H:%M')})",
                style={"position": "absolute", "left": f"{lp:.4f}%",
                       "width": f"{wp:.4f}%", "top": "0", "bottom": "0", "zIndex": "1"}))
    return out


def _plan_cell(span, t_start, t_end, tooltip=None, opacity=0.45):
    """Faixa sólida (planejado IW37) clipada à janela. None se fora."""
    if not span:
        return None
    ps = datetime(span[0].year, span[0].month, span[0].day)
    pe = datetime(span[1].year, span[1].month, span[1].day) + timedelta(days=1)
    ps = max(ps, t_start); pe = min(pe, t_end)
    if pe <= ps:
        return None
    lp = _to_pct(ps, t_start, t_end); wp = _to_pct(pe, t_start, t_end) - lp
    tt = tooltip or f"Planejado: {span[0].strftime('%d/%m')}–{span[1].strftime('%d/%m')}"
    return html.Div(title=tt, className="hh-plan-cell", style={
        "position": "absolute", "left": f"{lp:.4f}%", "width": f"{wp:.4f}%",
        "top": "4%", "height": "22%", "backgroundColor": COL_PLAN,
        "opacity": str(opacity), "borderRadius": "3px", "zIndex": "2"})


def _left_cell(children, bg="var(--bs-body-bg)", extra=None):
    style = {
        "width": f"{LEFT_W}px", "minWidth": f"{LEFT_W}px", "flexShrink": "0",
        "position": "sticky", "left": "0", "zIndex": "6", "backgroundColor": bg,
        "display": "flex", "alignItems": "center", "padding": "0 8px",
        "borderRight": "1px solid var(--bs-border-color)", "overflow": "hidden",
    }
    if extra:
        style.update(extra)
    return html.Div(children, style=style)


def _axis_row(t_start, t_end, slot_h, left_label="", clickable_days=False):
    return html.Div([
        _left_cell(html.Span(left_label, style={"fontWeight": "700", "fontSize": "0.78rem"}),
                   bg="#e5e7eb"),
        html.Div(_axis(t_start, t_end, slot_h, clickable_days) + _now_line(t_start, t_end), style={
            "position": "relative", "flex": "1", "height": "62px",
            "minWidth": "var(--hh-tl-w, 0)",
        }),
    ], style={"display": "flex", "alignItems": "stretch", "backgroundColor": "#e5e7eb",
              "borderBottom": "1px solid #d1d5db"})


# ---------------------------------------------------------------------------
# View ORDEM
# ---------------------------------------------------------------------------

def build_view_order(t_start, t_end, slot_h, clickable_days=False, confs=None, show_plan=True,
                     sort="ordem", scope="exec"):
    ds = data.get_dataset()
    if confs is None:
        confs = data.confs_in_window(t_start, t_end)

    exec_set = {c["aufnr"] for c in confs}
    plan_set = data.orders_with_plan_in_window(t_start, t_end) if scope != "exec" else set()
    if scope == "plan":
        active = plan_set
    elif scope == "both":
        active = exec_set | plan_set
    else:
        active = exec_set
    if not active:
        return _empty()

    orders = {a: {"tecs": {}, "n_apont": 0, "pernrs": set(), "min_dt": None} for a in active}
    for c in confs:
        a = c["aufnr"]
        if a not in orders:
            continue
        o = orders[a]
        o["tecs"].setdefault(c["pernr"], {"name": c["name"], "confs": []})["confs"].append(c)
        o["n_apont"] += 1
        o["pernrs"].add(c["pernr"])
        if o["min_dt"] is None or c["start_dt"] < o["min_dt"]:
            o["min_dt"] = c["start_dt"]
    # ordens só-planejadas — usar início do plano como min_dt
    for a, o in orders.items():
        if o["min_dt"] is None:
            sp = ds["order_plan_span"].get(a)
            o["min_dt"] = sp[0] if sp else t_start

    rows = [_axis_row(t_start, t_end, slot_h, "Ordem / técnico", clickable_days)]
    min_w = _min_width(t_start, t_end, slot_h)
    shifts = data.infer_employee_shifts()
    days = []
    _d = t_start
    while _d < t_end:
        days.append(_d); _d += timedelta(days=1)

    if sort == "data":
        def _ord_key(a):
            sp = ds["order_plan_span"].get(a)
            return sp[0] if sp else orders[a]["min_dt"]
        ordered = sorted(orders, key=_ord_key)
    else:
        ordered = sorted(orders, key=lambda a: (int(a) if a.isdigit() else 0, a))
    for aufnr in ordered:
        o = orders[aufnr]
        label = ds["order_label"].get(aufnr, "")
        span = ds["order_plan_span"].get(aufnr)

        plan_band = []
        if span and show_plan:
            ps = max(span[0], t_start); pe = min(span[1], t_end)
            if pe > ps:
                lp = _to_pct(ps, t_start, t_end)
                wp = _to_pct(pe, t_start, t_end) - lp
                plan_band.append(_seg(lp, wp, COL_PLAN, "8%", "84%",
                                      f"Planejado: {span[0].strftime('%d/%m %H:%M')}–"
                                      f"{span[1].strftime('%d/%m %H:%M')}",
                                      opacity=0.45, radius="6px", border=False))

        # chevron clientside (JS em hh_gantt_toggle.js cuida do toggle, sem callback Dash)
        has_tecs = bool(o["tecs"])
        chevron = html.Button(
            html.I(className="bi bi-chevron-right hh-ord-chev-icon",
                   style={"fontSize": "0.7rem"}),
            n_clicks=0, className="hh-ord-chevron",
            title="Expandir técnicos",
            **{"data-aufnr": aufnr},
            style={"border": "none", "background": "transparent", "cursor": "pointer",
                   "padding": "0 6px", "color": "var(--bs-body-color)",
                   "visibility": "visible" if has_tecs else "hidden"},
        )
        order_left = _left_cell([
            chevron,
            html.Div([
                html.Span(aufnr, style={"fontWeight": "700", "fontSize": "0.8rem"}),
                html.Span(label, style={"fontSize": "0.66rem", "color": "#6c757d",
                                        "whiteSpace": "nowrap", "overflow": "hidden",
                                        "textOverflow": "ellipsis", "display": "block"}),
            ], style={"flex": "1", "minWidth": "0", "overflow": "hidden"}),
            html.Span([html.I(className="bi bi-card-list me-1"), f"{o['n_apont']}"],
                      title="apontamentos", className="badge bg-light text-dark border",
                      style={"fontSize": "0.6rem", "marginLeft": "4px"}),
            html.Span([html.I(className="bi bi-people me-1"), f"{len(o['pernrs'])}"],
                      title="técnicos", className="badge bg-light text-dark border",
                      style={"fontSize": "0.6rem", "marginLeft": "3px"}),
        ], bg="var(--bs-secondary-bg)")

        rows.append(html.Div([
            order_left,
            html.Div(plan_band + _now_line(t_start, t_end), style={
                "position": "relative", "flex": "1", "height": "34px",
                "minWidth": "var(--hh-tl-w, 0)",
            }),
        ], style={"display": "flex", "alignItems": "stretch", "height": "34px",
                  "backgroundColor": "var(--bs-secondary-bg)",
                  "borderBottom": "1px solid var(--bs-border-color)"}))

        # Sub-linhas dos técnicos — sempre renderizadas, escondidas via CSS
        # display:none. Toggle clientside via hh_gantt_toggle.js (sem callback Dash).
        sub_rows = []
        for pernr in sorted(o["tecs"], key=lambda p: o["tecs"][p]["name"]):
            tec = o["tecs"][pernr]
            tec_turno = shifts.get(pernr, "B")
            # 3 camadas: disponibilidade hachurada + planejado sólido + executado sólido
            segs = _shift_cells(days, tec_turno, t_start, t_end) + list(plan_band)
            tot = 0
            for c in tec["confs"]:
                s = max(c["start_dt"], t_start); e = min(c["end_dt"], t_end)
                if e <= s:
                    continue
                lp = _to_pct(s, t_start, t_end); wp = _to_pct(e, t_start, t_end) - lp
                tot += c["ismnw"]
                segs.append(_seg(lp, wp, _col_auart(c["auart"]), "26%", "48%",
                                 f"{tec['name']} · ordem {aufnr} op {c['vornr']} ({c['auart']})\n"
                                 f"{c['start_dt'].strftime('%d/%m %H:%M')}–{c['end_dt'].strftime('%H:%M')}\n"
                                 f"{_fmt_h(c['ismnw'])}"))
            segs += _now_line(t_start, t_end)
            tec_left = _left_cell([
                html.Span("↳", style={"color": "var(--bs-secondary)", "paddingLeft": "10px",
                                      "paddingRight": "8px", "fontSize": "0.72rem"}),
                html.Span(tec["name"], style={"flex": "1", "fontSize": "0.74rem",
                                              "whiteSpace": "nowrap", "overflow": "hidden",
                                              "textOverflow": "ellipsis", "minWidth": "0"}),
                html.Span(_fmt_h(tot), style={"fontSize": "0.66rem", "color": "var(--bs-secondary)",
                                              "flexShrink": "0"}),
            ], bg="var(--bs-body-bg)")
            sub_rows.append(html.Div([
                tec_left,
                html.Div(segs, style={"position": "relative", "flex": "1", "height": "28px",
                                      "minWidth": "var(--hh-tl-w, 0)"}),
            ], style={"display": "flex", "alignItems": "stretch", "height": "28px",
                      "borderBottom": "1px dashed var(--bs-border-color-translucent)"}))
        if sub_rows:
            rows.append(html.Div(sub_rows, id=f"hh-ord-rows-{aufnr}",
                                 className="hh-ord-rows",
                                 style={"display": "none"}))

    return _scroll(rows, min_w)


# ---------------------------------------------------------------------------
# View FUNCIONÁRIO
# ---------------------------------------------------------------------------

def build_view_employee(t_start, t_end, slot_h, clickable_days=False, confs=None, sort="ordem",
                        scope="exec"):
    ds = data.get_dataset()
    if confs is None:
        confs = data.confs_in_window(t_start, t_end)

    exec_pernrs = {c["pernr"] for c in confs}
    plan_set = data.orders_with_plan_in_window(t_start, t_end) if scope != "exec" else set()
    all_emp_orders = data.emp_all_time_orders() if scope != "exec" else {}

    pernrs = set()
    if scope in ("exec", "both"):
        pernrs |= exec_pernrs
    if scope in ("plan", "both"):
        for p, orders in all_emp_orders.items():
            if orders & plan_set:
                pernrs.add(p)
    if not pernrs:
        return _empty()

    name_lookup = {c["pernr"]: c["name"] for c in ds["confs"]}
    emps = {p: {"name": name_lookup.get(p, p), "confs": [], "orders": set(), "min_dt": None}
            for p in pernrs}
    for c in confs:
        e = emps.get(c["pernr"])
        if not e:
            continue
        e["confs"].append(c)
        e["orders"].add(c["aufnr"])
        if e["min_dt"] is None or c["start_dt"] < e["min_dt"]:
            e["min_dt"] = c["start_dt"]
    if scope != "exec":
        for p, e in emps.items():
            plan_overlap = all_emp_orders.get(p, set()) & plan_set
            e["orders"] |= plan_overlap
            if e["min_dt"] is None:
                best = None
                for a in plan_overlap:
                    sp = ds["order_plan_span"].get(a)
                    if sp and (best is None or sp[0] < best):
                        best = sp[0]
                e["min_dt"] = best or t_start

    # Turno inferido por sigla (sobre TODO o dataset → estável entre semanas)
    shifts = data.infer_employee_shifts()

    rows = [_axis_row(t_start, t_end, slot_h, "Funcionário · turno", clickable_days)]
    min_w = _min_width(t_start, t_end, slot_h)

    days = []
    d = t_start
    while d < t_end:
        days.append(d)
        d += timedelta(days=1)

    ds_for_sort = data.get_dataset()
    if sort == "data":
        def _emp_key(p):
            best = None
            for a in emps[p]["orders"]:
                sp = ds_for_sort["order_plan_span"].get(a)
                if sp:
                    best = sp[0] if best is None else min(best, sp[0])
            return best or emps[p]["min_dt"]
        ordered_emps = sorted(emps, key=_emp_key)
    else:  # "ordem": menor nº de ordem tocado, depois nome
        ordered_emps = sorted(emps, key=lambda p: (min((int(a) for a in emps[p]["orders"] if a.isdigit()),
                                                        default=0), emps[p]["name"]))
    ds_full = data.get_dataset()
    for pernr in ordered_emps:
        e = emps[pernr]
        turno = shifts.get(pernr, "B")
        turno_lbl = data.turno_label(turno)

        # ---- 3 camadas ----
        # 1) Disponibilidade (hachurado cinza + extra hachurado âmbar)
        bg_cells = _shift_cells(days, turno, t_start, t_end)
        # 2) Planejado IW37 — empilhado verticalmente, uma faixa por ordem visível
        # order_plan_span agora carrega datetimes (data+hora programada, hora sintética do SAP)
        visible_plans = []
        for aufnr in e["orders"]:
            sp = ds_full["order_plan_span"].get(aufnr)
            if not sp:
                continue
            ps_c = max(sp[0], t_start); pe_c = min(sp[1], t_end)
            if pe_c <= ps_c:
                continue
            visible_plans.append((aufnr, sp, ps_c, pe_c))
        # ordena por início pra empilhar do mais cedo no topo
        visible_plans.sort(key=lambda x: x[2])
        n = len(visible_plans)
        if n > 0:
            BAND_H = 8; GAP_PX = 1; BOTTOM_MARGIN = 2
            # empilha do fundo pra cima — i=0 fica colado embaixo
            for i, (aufnr, sp, ps_c, pe_c) in enumerate(visible_plans):
                bottom_px = BOTTOM_MARGIN + i * (BAND_H + GAP_PX)
                if bottom_px + BAND_H > 30:        # reserva ~30px no topo pro executado
                    break       # estourou a área do row — ignora excedentes
                lp = _to_pct(ps_c, t_start, t_end); wp = _to_pct(pe_c, t_start, t_end) - lp
                bg_cells.append(html.Div(
                    title=f"Ordem {aufnr} planejada: "
                          f"{sp[0].strftime('%d/%m %H:%M')}–{sp[1].strftime('%d/%m %H:%M')}",
                    className="hh-plan-cell",
                    style={"position": "absolute", "left": f"{lp:.4f}%", "width": f"{wp:.4f}%",
                           "bottom": f"{bottom_px}px", "height": f"{BAND_H}px",
                           "backgroundColor": COL_PLAN, "opacity": "0.85",
                           "borderRadius": "1px", "zIndex": "2"}))

        segs = list(bg_cells)
        tot = 0
        for c in e["confs"]:
            s = max(c["start_dt"], t_start); ee = min(c["end_dt"], t_end)
            if ee <= s:
                continue
            lp = _to_pct(s, t_start, t_end); wp = _to_pct(ee, t_start, t_end) - lp
            tot += c["ismnw"]
            segs.append(_seg(lp, wp, _col_auart(c["auart"]), "5%", "55%",
                             f"{e['name']} · ordem {c['aufnr']} op {c['vornr']} ({c['auart']})\n"
                             f"{c['start_dt'].strftime('%d/%m %H:%M')}–{c['end_dt'].strftime('%H:%M')}\n"
                             f"{_fmt_h(c['ismnw'])}"))
        segs += _now_line(t_start, t_end)

        emp_left = _left_cell([
            html.Div([
                html.Div([e["name"], html.Span(turno_lbl, className="badge bg-light text-dark border ms-2",
                                               style={"fontSize": "0.58rem"})],
                         style={"fontWeight": "600", "fontSize": "0.8rem",
                                "whiteSpace": "nowrap", "overflow": "hidden",
                                "textOverflow": "ellipsis"}),
                html.Div(f"{len(e['orders'])} ordens · {_fmt_h(tot)} apontadas",
                         style={"fontSize": "0.64rem", "color": "var(--bs-secondary)"}),
            ], style={"flex": "1", "minWidth": "0", "overflow": "hidden"}),
        ])
        rows.append(html.Div([
            emp_left,
            html.Div(segs, style={"position": "relative", "flex": "1", "height": "60px",
                                  "minWidth": "var(--hh-tl-w, 0)"}),
        ], style={"display": "flex", "alignItems": "stretch", "height": "60px",
                  "borderBottom": "1px solid var(--bs-border-color-translucent)"}))

    return _scroll(rows, min_w)


# ---------------------------------------------------------------------------
# KPIs (BR-04 / BR-06) sobre a janela
# ---------------------------------------------------------------------------

def compute_kpis(t_start, t_end, confs=None):
    """Métricas da janela: aproveitamento mediana/total, taxa execução, não iniciadas, totais."""
    ds = data.get_dataset()
    if confs is None:
        confs = data.confs_in_window(t_start, t_end)

    op_real, op_plan = {}, {}
    pernrs, orders, n_apont = set(), set(), 0
    for c in confs:
        k = (c["aufnr"], c["vornr"])
        op_real[k] = op_real.get(k, 0) + c["ismnw"]
        op_plan[k] = max(op_plan.get(k, 0), c["arbei"])
        pernrs.add(c["pernr"]); orders.add(c["aufnr"]); n_apont += 1

    aproveit = []
    sum_real = sum_plan = sum_capped = 0
    for k, real in op_real.items():
        plan = op_plan.get(k, 0)
        if plan > 0 and real > 0:
            aproveit.append(real / plan * 100.0)
            sum_real += real; sum_plan += plan; sum_capped += min(real, plan)

    aproveit.sort()
    mediana = aproveit[len(aproveit) // 2] if aproveit else 0.0
    total = (sum_real / sum_plan * 100.0) if sum_plan else 0.0

    realized_ops = set(op_real.keys())
    nao_iniciadas = 0
    for (aufnr, vornr), p in ds["planned"].items():
        fs = p["fsavd"]
        if fs and t_start.date() <= fs < t_end.date() and (aufnr, vornr) not in realized_ops:
            nao_iniciadas += 1

    taxa_exec = (sum_capped / sum_plan * 100.0) if sum_plan else 0.0

    return {
        "mediana": mediana, "total": total, "taxa_exec": taxa_exec,
        "nao_iniciadas": nao_iniciadas, "n_ordens": len(orders),
        "n_apont": n_apont, "n_tecnicos": len(pernrs),
        "horas_real": sum(op_real.values()),
    }


# ---------------------------------------------------------------------------
# Helpers de container
# ---------------------------------------------------------------------------

def _scroll(rows, min_w):
    return html.Div(rows, className="hh-gantt-root", style={
        "overflowX": "auto", "width": "100%", "border": "1px solid var(--bs-border-color)",
        "borderRadius": "4px", "--hh-tl-w": f"{min_w}px",
    })


def _empty():
    return html.Div([
        html.I(className="bi bi-calendar-x", style={"fontSize": "1.6rem"}),
        html.Div("Sem apontamentos neste período.", style={"marginTop": "6px"}),
    ], className="text-muted p-5 text-center")
