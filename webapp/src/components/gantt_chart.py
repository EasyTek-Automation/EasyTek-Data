# src/components/gantt_chart.py

from datetime import datetime, timedelta
from dash import html

LEFT_WIDTH = 360  # px — painel fixo esquerdo (nome + botões de ação)

# estilo comum aplicado a todos os painéis esquerdos para "congelar" a coluna
# durante scroll horizontal (posição sticky com bg opaco)
LEFT_PANEL_STICKY = {
    "position": "sticky", "left": "0", "zIndex": "5",
}


# ---------------------------------------------------------------------------
# Helpers de posicionamento
# ---------------------------------------------------------------------------

def _to_pct(t, t_start, t_end):
    """Converte datetime t para porcentagem dentro de [t_start, t_end]."""
    total = (t_end - t_start).total_seconds()
    if total <= 0:
        return 0.0
    offset = (t - t_start).total_seconds()
    return max(0.0, min(100.0, offset / total * 100.0))


def _parse_dt(value):
    """Aceita datetime ou string ISO e retorna datetime."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    raise ValueError(f"Formato de data não reconhecido: {value!r}")


def _btn(btn_type, index, icon, color="secondary", title=""):
    """Botão de ação compacto com ícone Bootstrap para linhas do Gantt."""
    return html.Button(
        html.I(className=f"bi bi-{icon}"),
        id={"type": btn_type, "index": index},
        title=title,
        style={
            "background": "none",
            "border": "none",
            "padding": "0 3px",
            "cursor": "pointer",
            "color": f"var(--bs-{color})",
            "fontSize": "0.78rem",
            "lineHeight": "1",
        },
    )


# ---------------------------------------------------------------------------
# Eixo de tempo
# ---------------------------------------------------------------------------

def build_time_axis(t_start, t_end, granularity):
    """Gera lista de html.Div posicionados como marcadores do eixo de tempo."""
    MONTH_NAMES = [
        "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    ]
    markers = []

    if granularity == "horas":
        cursor = t_start.replace(minute=0, second=0, microsecond=0)
        while cursor <= t_end:
            is_midnight = cursor.hour == 0
            label = cursor.strftime("%d/%m") if is_midnight else cursor.strftime("%Hh")
            markers.append((_to_pct(cursor, t_start, t_end), label, is_midnight))
            cursor += timedelta(hours=1)

    elif granularity == "dias":
        cursor = t_start.replace(hour=0, minute=0, second=0, microsecond=0)
        if cursor < t_start:
            cursor += timedelta(days=1)
        while cursor <= t_end:
            markers.append((_to_pct(cursor, t_start, t_end), cursor.strftime("%d/%m")))
            cursor += timedelta(days=1)

    elif granularity == "semanas":
        cursor = t_start.replace(hour=0, minute=0, second=0, microsecond=0)
        cursor -= timedelta(days=cursor.weekday())
        if cursor < t_start:
            cursor += timedelta(weeks=1)
        while cursor <= t_end:
            markers.append((_to_pct(cursor, t_start, t_end), f"Sem {cursor.isocalendar()[1]}"))
            cursor += timedelta(weeks=1)

    elif granularity == "meses":
        cursor = t_start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if cursor < t_start:
            cursor = cursor.replace(month=cursor.month + 1) if cursor.month < 12 else cursor.replace(year=cursor.year + 1, month=1)
        while cursor <= t_end:
            markers.append((_to_pct(cursor, t_start, t_end), f"{MONTH_NAMES[cursor.month]} {cursor.year}"))
            cursor = cursor.replace(month=cursor.month + 1) if cursor.month < 12 else cursor.replace(year=cursor.year + 1, month=1)

    result = []

    # Linhas pontilhadas de meia hora (sem rótulo) — só no modo horas
    if granularity == "horas":
        cursor_h = t_start.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=30)
        while cursor_h <= t_end:
            if cursor_h >= t_start:
                result.append(html.Div(style={
                    "position":   "absolute",
                    "left":       f"{_to_pct(cursor_h, t_start, t_end):.4f}%",
                    "top":        "0",
                    "bottom":     "0",
                    "width":      "0",
                    "borderLeft": "1px dashed var(--bs-border-color)",
                }))
            cursor_h += timedelta(hours=1)

    for item in markers:
        left, label = item[0], item[1]
        is_midnight = len(item) > 2 and item[2]
        color_main  = "var(--bs-body-color)" if is_midnight else "var(--bs-secondary)"
        weight      = "600" if is_midnight else "400"

        # 1. Linha vertical divisória (altura total do eixo)
        result.append(html.Div(style={
            "position":   "absolute",
            "left":       f"{left:.4f}%",
            "top":        "0",
            "bottom":     "0",
            "width":      "0",
            "borderLeft": "2px solid var(--bs-body-color)" if is_midnight else "1px solid var(--bs-border-color)",
        }))

        # 2. Rótulo centralizado verticalmente
        result.append(html.Div(label, style={
            "position":    "absolute",
            "left":        f"{left:.4f}%",
            "top":         "50%",
            "transform":   "translate(-50%, -50%) rotate(180deg)",
            "whiteSpace":  "nowrap",
            "writingMode": "vertical-rl",
            "color":       color_main,
            "fontWeight":  weight,
            "fontSize":    "0.83rem",
            "paddingLeft": "3px",
        }))
    return result


def _axis_height_for(granularity):
    """Altura da faixa do eixo em pixels — rótulos verticais precisam de mais."""
    return {"horas": 64, "dias": 56, "semanas": 56, "meses": 88}.get(granularity, 64)


# ---------------------------------------------------------------------------
# Paleta viva para atividades
# ---------------------------------------------------------------------------

ACTIVITY_PALETTE = [
    "#E91E63",  # pink
    "#9C27B0",  # purple
    "#673AB7",  # deep purple
    "#3F51B5",  # indigo
    "#2196F3",  # blue
    "#00BCD4",  # cyan
    "#009688",  # teal
    "#4CAF50",  # green
    "#FF9800",  # orange
    "#FF5722",  # deep orange
    "#795548",  # brown
]


def _pick_color(key):
    """Escolhe cor da paleta consistentemente a partir de uma chave (ID)."""
    idx = sum(ord(c) for c in str(key)) % len(ACTIVITY_PALETTE)
    return ACTIVITY_PALETTE[idx]


STATUS_COLOR_ATRASADA = "#E53935"   # vermelho
STATUS_COLOR_NO_PRAZO = "#1E88E5"   # azul
STATUS_COLOR_ADIANTADA = "#43A047"  # verde
STATUS_TOLERANCE_PCT = 10.0


def _activity_status_color(activity):
    """
    Cor da atividade por delta (real − esperado):
      < −10%  → vermelho (atrasada)
      ±10%    → azul    (no prazo)
      > +10%  → verde   (adiantada)
    """
    try:
        act_start = _parse_dt(activity["data_hora_inicio"])
        act_end   = _parse_dt(activity["data_hora_fim"])
    except Exception:
        return STATUS_COLOR_NO_PRAZO

    now = datetime.utcnow() - timedelta(hours=3)
    total_sec = (act_end - act_start).total_seconds()
    if total_sec <= 0:
        return STATUS_COLOR_NO_PRAZO

    elapsed_sec = (now - act_start).total_seconds()
    progresso_esperado = max(0.0, min(100.0, elapsed_sec / total_sec * 100.0))
    progresso_real     = float(activity.get("progresso_real", 0) or 0)
    delta = progresso_real - progresso_esperado

    if delta <= -STATUS_TOLERANCE_PCT:
        return STATUS_COLOR_ATRASADA
    if delta >=  STATUS_TOLERANCE_PCT:
        return STATUS_COLOR_ADIANTADA
    return STATUS_COLOR_NO_PRAZO


# Paleta determinística para fallback de avatar (iniciais coloridas)
AVATAR_FALLBACK_PALETTE = [
    "#EF5350", "#AB47BC", "#5C6BC0", "#29B6F6", "#26A69A",
    "#66BB6A", "#FFA726", "#FF7043", "#8D6E63", "#78909C",
]


def _initials_from_nome(nome):
    """Extrai até 2 iniciais do nome para o avatar fallback."""
    parts = [p for p in (nome or "").strip().split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _avatar_color_for(nome):
    """Cor determinística pelo hash do nome — mesmo nome sempre mesma cor."""
    if not nome:
        return AVATAR_FALLBACK_PALETTE[0]
    idx = sum(ord(c) for c in nome) % len(AVATAR_FALLBACK_PALETTE)
    return AVATAR_FALLBACK_PALETTE[idx]


def _build_avatar(employee, size=20):
    """
    Avatar circular do funcionário. Usa foto servida via rota Flask se existir;
    caso contrário, iniciais coloridas com hash determinístico do nome.
    """
    if not employee:
        return html.Div(style={"width": f"{size}px", "height": f"{size}px"})
    emp_id = str(employee.get("_id", ""))
    nome   = employee.get("nome", "")
    has_photo = bool(employee.get("foto_bytes")) or employee.get("_has_photo")
    common = {
        "width": f"{size}px", "height": f"{size}px",
        "borderRadius": "50%",
        "border": "2px solid #ffffff",
        "boxShadow": "0 0 0 1px rgba(0,0,0,0.15)",
        "flexShrink": "0",
    }
    if has_photo and emp_id:
        style = {**common,
                 "backgroundImage": f"url(/api/gantt/employee-photo/{emp_id})",
                 "backgroundSize": "cover", "backgroundPosition": "center"}
        return html.Div(title=nome, style=style)
    style = {**common,
             "backgroundColor": _avatar_color_for(nome),
             "color": "#ffffff",
             "display": "flex", "alignItems": "center", "justifyContent": "center",
             "fontSize": f"{max(8, int(size*0.45))}px",
             "fontWeight": "700",
             "fontFamily": "system-ui, -apple-system, sans-serif"}
    return html.Div(_initials_from_nome(nome), title=nome, style=style)


def _build_now_line(t_start, t_end):
    """Linha vertical vermelha do 'agora' (Brasília UTC-3) que cruza a altura toda da linha."""
    now = datetime.utcnow() - timedelta(hours=3)
    if not (t_start <= now <= t_end):
        return []
    left_pct = _to_pct(now, t_start, t_end)
    return [html.Div(style={
        "position": "absolute", "left": f"{left_pct:.4f}%",
        "top": "0", "bottom": "0", "width": "2px",
        "backgroundColor": "var(--bs-danger)",
        "zIndex": "4", "pointerEvents": "none",
    })]


def _build_day_stripes(t_start, t_end):
    """Faixas verticais alternadas (zebra) para cada dia dentro do range."""
    stripes = []
    cursor = t_start.replace(hour=0, minute=0, second=0, microsecond=0)
    day_idx = 0
    while cursor < t_end:
        next_day = cursor + timedelta(days=1)
        left  = _to_pct(max(cursor,  t_start), t_start, t_end)
        right = _to_pct(min(next_day, t_end),  t_start, t_end)
        width = right - left
        if width > 0 and day_idx % 2 == 1:
            stripes.append(html.Div(style={
                "position": "absolute", "left": f"{left:.4f}%",
                "width": f"{width:.4f}%", "top": "0", "bottom": "0",
                "backgroundColor": "var(--bs-body-color)", "opacity": "0.04",
                "pointerEvents": "none", "zIndex": "0",
            }))
        cursor = next_day
        day_idx += 1
    return stripes


# ---------------------------------------------------------------------------
# Barras de atividade
# ---------------------------------------------------------------------------

def _build_activity_bar(activity, t_start, t_end, color=None):
    """Barra estilo pílula com cor vibrante + progresso interno + marcador 'agora'."""
    act_start = _parse_dt(activity["data_hora_inicio"])
    act_end   = _parse_dt(activity["data_hora_fim"])
    now       = datetime.utcnow() - timedelta(hours=3)
    left_pct  = _to_pct(act_start, t_start, t_end)
    right_pct = _to_pct(act_end,   t_start, t_end)
    width_pct = right_pct - left_pct
    progress  = int(activity.get("progresso_real", 0))
    green_w   = width_pct * progress / 100.0
    bar_color = color or _activity_status_color(activity)

    base_bar = html.Div(style={
        "position": "absolute", "left": f"{left_pct:.4f}%", "top": "15%",
        "height": "70%", "width": f"{width_pct:.4f}%", "minWidth": "4px",
        "backgroundColor": bar_color, "opacity": "0.35",
        "borderRadius": "999px", "zIndex": "1",
    })
    progress_bar = html.Div(style={
        "position": "absolute", "left": f"{left_pct:.4f}%", "top": "15%",
        "height": "70%", "width": f"{green_w:.4f}%", "minWidth": "0px",
        "backgroundColor": bar_color, "opacity": "0.95",
        "borderRadius": "999px", "zIndex": "2",
    })
    children = [base_bar, progress_bar]
    return html.Div(children, style={"position": "relative", "height": "28px", "margin": "2px 0"})


def _build_assignment_bar(assignment, t_start, t_end, activity=None):
    """
    Barra opaca e bem visível da atribuição do funcionário.
    (Removida a faixa translúcida de referência da atividade pai — estava
     gerando confusão visual com a barra real da atribuição.)
    """
    try:
        s = _parse_dt(assignment["data_hora_entrada"])
        e = _parse_dt(assignment["data_hora_saida"])
    except Exception:
        return None

    asg_left  = _to_pct(s, t_start, t_end)
    asg_width = _to_pct(e, t_start, t_end) - asg_left

    bar = html.Div(style={
        "position": "absolute", "left": f"{asg_left:.4f}%", "top": "20%",
        "height": "60%", "width": f"{asg_width:.4f}%", "minWidth": "12px",
        "backgroundColor": "#FBC02D", "opacity": "0.95",
        "borderRadius": "999px",
    })
    return html.Div([bar], style={"position": "relative", "height": "100%"})


# ---------------------------------------------------------------------------
# Construtor principal
# ---------------------------------------------------------------------------

def build_gantt_chart(categories, activities, assignments, granularity="dias",
                      expanded_state=None, employees=None, hour_offset=0,
                      activities_state=None, projects=None, projects_state=None,
                      filter_query=""):
    """
    Constrói o componente visual do Gantt com botões de ação em cada linha.

    filter_query: string para filtrar projetos/categorias/atividades por nome (cascata).
        - match em atividade → mostra também sua categoria e seu projeto
        - match em categoria → mostra também seu projeto (com todas suas atividades)
        - match em projeto   → mostra projeto inteiro
    """
    if expanded_state is None:
        expanded_state = {}
    emp_map      = {str(e["_id"]): e["nome"] for e in (employees or [])}
    emp_full_map = {str(e["_id"]): e          for e in (employees or [])}

    if not projects and not categories:
        return html.Div("Nenhum projeto cadastrado.", className="text-muted p-3")

    # Aplicar filtro em cascata
    q = (filter_query or "").strip().lower()
    if q:
        full_proj_ids = {str(p["_id"]) for p in (projects or []) if q in p.get("nome", "").lower()}
        full_cat_ids  = {str(c["_id"]) for c in categories       if q in c.get("nome", "").lower()}
        for c in categories:
            if str(c.get("projeto_id", "")) in full_proj_ids:
                full_cat_ids.add(str(c["_id"]))

        matched_act_ids = {str(a["_id"]) for a in activities if q in a.get("titulo", "").lower()}
        visible_act_ids = set(matched_act_ids)
        for a in activities:
            if str(a.get("categoria_id", "")) in full_cat_ids:
                visible_act_ids.add(str(a["_id"]))

        visible_cat_ids = set(full_cat_ids)
        for a in activities:
            if str(a["_id"]) in visible_act_ids:
                visible_cat_ids.add(str(a.get("categoria_id", "")))

        visible_proj_ids = set(full_proj_ids)
        for c in categories:
            if str(c["_id"]) in visible_cat_ids:
                visible_proj_ids.add(str(c.get("projeto_id", "")))

        projects   = [p for p in (projects or []) if str(p["_id"]) in visible_proj_ids]
        categories = [c for c in categories       if str(c["_id"]) in visible_cat_ids]
        activities = [a for a in activities       if str(a["_id"]) in visible_act_ids]

        if not projects:
            return html.Div(
                [html.I(className="bi bi-search me-2"),
                 f"Nenhum resultado para \"{filter_query}\"."],
                className="text-muted p-4 text-center",
            )

    if granularity == "horas":
        now_brt = datetime.utcnow() - timedelta(hours=3)
        center  = now_brt + timedelta(hours=hour_offset or 0)
        t_start = center - timedelta(hours=24)
        t_end   = center + timedelta(hours=24)
    else:
        all_starts = [_parse_dt(c["data_hora_inicio"]) for c in categories]
        all_ends   = [_parse_dt(c["data_hora_fim"])    for c in categories]
        for p in (projects or []):
            if p.get("data_hora_inicio"): all_starts.append(_parse_dt(p["data_hora_inicio"]))
            if p.get("data_hora_fim"):    all_ends.append(_parse_dt(p["data_hora_fim"]))
        if not all_starts or not all_ends:
            return html.Div("Nenhuma data cadastrada.", className="text-muted p-3")
        t_start_raw = min(all_starts)
        t_end_raw   = max(all_ends)
        PADDING = {
            "dias":    timedelta(days=1),
            "semanas": timedelta(weeks=1),
            "meses":   timedelta(days=30),
        }
        pad     = PADDING.get(granularity, timedelta(days=1))
        t_start = t_start_raw - pad
        t_end   = t_end_raw   + pad

    assignments_by_activity = {}
    for a in assignments:
        aid = str(a.get("atividade_id", ""))
        assignments_by_activity.setdefault(aid, []).append(a)

    activities_by_category = {}
    for act in activities:
        cid = str(act.get("categoria_id", ""))
        activities_by_category.setdefault(cid, []).append(act)

    day_stripes = _build_day_stripes(t_start, t_end)
    now_line    = _build_now_line(t_start, t_end)

    def _make_time_axis_row():
        """Gera uma linha de eixo de tempo fresca (para uso dentro de cada projeto)."""
        axis_bg = "#e5e7eb"  # cinza claro — sinaliza faixa reservada ao período
        return html.Div([
            html.Div(style={
                "width": f"{LEFT_WIDTH}px", "minWidth": f"{LEFT_WIDTH}px", "flexShrink": "0",
                "position": "sticky", "left": "0", "zIndex": "5",
                "backgroundColor": axis_bg,
            }),
            html.Div(
                _build_day_stripes(t_start, t_end) + build_time_axis(t_start, t_end, granularity) + now_line,
                style={
                    "position": "relative", "flex": "1",
                    "height": f"{_axis_height_for(granularity)}px",
                },
            ),
        ], style={"display": "flex", "alignItems": "flex-end", "marginBottom": "2px",
                  "backgroundColor": axis_bg,
                  "border": "1px solid #d1d5db",
                  "borderRadius": "3px"})

    # índice de categorias por projeto
    cats_by_project = {}
    for c in categories:
        pid = str(c.get("projeto_id", ""))
        cats_by_project.setdefault(pid, []).append(c)

    TIPO_COLOR = {
        "Parada Preventiva":   "#E96D38",
        "Parada Corretiva":    "var(--bs-danger)",
        "Projeto de Melhoria": "var(--bs-success)",
        "Outro":               "var(--bs-secondary)",
    }

    rows = []

    for proj in (projects or []):
        proj_id       = str(proj["_id"])
        proj_expanded = (projects_state or {}).get(proj_id, True)
        proj_icon     = "▼" if proj_expanded else "▶"
        tipo_color    = TIPO_COLOR.get(proj.get("tipo", ""), "var(--bs-secondary)")

        proj_bar_children = []
        try:
            p_start = _parse_dt(proj["data_hora_inicio"])
            p_end   = _parse_dt(proj["data_hora_fim"])
            p_left  = _to_pct(p_start, t_start, t_end)
            p_width = _to_pct(p_end,   t_start, t_end) - p_left
            proj_bar_children.append(html.Div(style={
                "position": "absolute", "left": f"{p_left:.4f}%", "top": "15%",
                "height": "70%", "width": f"{p_width:.4f}%", "minWidth": "4px",
                "backgroundColor": tipo_color, "opacity": "0.9",
                "borderRadius": "999px", "border": f"1px solid {tipo_color}",
            }))
        except Exception:
            pass

        proj_row = html.Div([
            html.Div([
                html.Div(
                    [
                        html.Span(proj_icon, style={"fontSize": "0.72rem", "flexShrink": "0", "paddingRight": "3px"}),
                        html.I(className="bi bi-folder-fill", style={
                            "fontSize": "0.82rem", "marginRight": "5px", "flexShrink": "0",
                            "color": tipo_color,
                        }),
                        html.Span(proj["nome"], style={
                            "fontWeight": "700", "fontSize": "0.9rem",
                            "overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap",
                        }),
                        html.Span(proj.get("tipo", ""), style={
                            "fontSize": "0.65rem", "color": tipo_color, "fontWeight": "400",
                            "marginLeft": "8px", "flexShrink": "0", "whiteSpace": "nowrap",
                            "border": f"1px solid {tipo_color}", "borderRadius": "3px",
                            "padding": "0 4px",
                        }),
                    ],
                    id={"type": "btn-toggle-project", "index": proj_id},
                    n_clicks=0,
                    style={"cursor": "pointer", "display": "flex", "alignItems": "center",
                           "flex": "1", "minWidth": "0", "overflow": "hidden"},
                ),
                _btn("btn-new-category-in-proj", proj_id, "plus-lg", "success",   "Nova categoria neste projeto"),
                _btn("btn-edit-project",         proj_id, "pencil",  "primary",   "Editar projeto"),
                _btn("btn-archive-project",      proj_id, "archive", "secondary", "Arquivar projeto"),
                _btn("btn-delete-project",       proj_id, "trash",   "danger",    "Excluir projeto"),
            ], style={
                "width": f"{LEFT_WIDTH}px", "minWidth": f"{LEFT_WIDTH}px", "flexShrink": "0",
                "display": "flex", "alignItems": "center", "paddingRight": "6px",
                "overflow": "hidden",
                "position": "sticky", "left": "0", "zIndex": "5",
                "backgroundColor": "var(--bs-secondary-bg)",
                "borderLeft": f"5px solid {tipo_color}",
            }),
            html.Div(day_stripes + proj_bar_children + now_line, style={"position": "relative", "flex": "1", "height": "32px"}),
        ], style={
            "display": "flex", "alignItems": "center", "height": "42px",
            "borderBottom": f"2px solid {tipo_color}",
            "backgroundColor": "var(--bs-secondary-bg)",
        })
        rows.append(proj_row)

        proj_cat_rows = [_make_time_axis_row()]
        for cat in cats_by_project.get(proj_id, []):
            cat_id      = str(cat["_id"])
            is_expanded = expanded_state.get(cat_id, True)
            cat_start   = _parse_dt(cat["data_hora_inicio"])
            cat_end     = _parse_dt(cat["data_hora_fim"])
            left_pct    = _to_pct(cat_start, t_start, t_end)
            width_pct   = _to_pct(cat_end, t_start, t_end) - left_pct
            toggle_icon = "▼" if is_expanded else "▶"

            cat_row = html.Div([
                html.Div([
                    html.Div(
                        [
                            html.Span(toggle_icon, style={"fontSize": "0.7rem", "flexShrink": "0", "paddingRight": "2px"}),
                            html.I(className="bi bi-tag", style={
                                "fontSize": "0.72rem", "marginRight": "5px",
                                "flexShrink": "0", "color": "var(--bs-info)",
                            }),
                            html.Span(cat["nome"], style={
                                "fontSize": "0.8rem", "fontWeight": "500",
                                "overflow": "hidden",
                                "textOverflow": "ellipsis", "whiteSpace": "nowrap",
                            }),
                        ],
                        id={"type": "btn-toggle-category", "index": cat_id},
                        n_clicks=0,
                        style={"cursor": "pointer", "display": "flex", "alignItems": "center",
                               "flex": "1", "minWidth": "0", "overflow": "hidden",
                               "paddingLeft": "14px"},
                    ),
                    _btn("btn-new-activity-in-cat", cat_id, "plus-lg", "success", "Nova atividade nesta categoria"),
                    _btn("btn-edit-category",        cat_id, "pencil",  "primary", "Editar categoria"),
                    _btn("btn-delete-category",      cat_id, "trash",   "danger",  "Excluir categoria"),
                ], style={
                    "width": f"{LEFT_WIDTH}px", "minWidth": f"{LEFT_WIDTH}px", "flexShrink": "0",
                    "display": "flex", "alignItems": "center", "paddingRight": "6px",
                    "overflow": "hidden",
                    "position": "sticky", "left": "0", "zIndex": "5",
                    "backgroundColor": "var(--bs-body-bg)",
                    "borderLeft": "2px dashed var(--bs-border-color)",
                }),
                html.Div(day_stripes + [
                    html.Div(style={
                        "position": "absolute", "left": f"{left_pct:.4f}%", "top": "20%",
                        "height": "60%", "width": f"{width_pct:.4f}%", "minWidth": "4px",
                        "backgroundColor": "#7E57C2", "opacity": "0.75",
                        "borderRadius": "999px",
                    }),
                ] + now_line, style={"position": "relative", "flex": "1", "height": "28px"}),
            ], style={
                "display": "flex", "alignItems": "center", "height": "30px",
                "borderBottom": "1px solid var(--bs-border-color-translucent)",
                "backgroundColor": "transparent",
            })
            proj_cat_rows.append(cat_row)

            cat_acts = activities_by_category.get(cat_id, [])
            act_rows = []

            for act in cat_acts:
                act_id       = str(act["_id"])
                act_asgs     = assignments_by_activity.get(act_id, [])
                act_bar      = _build_activity_bar(act, t_start, t_end)
                act_expanded = (activities_state or {}).get(act_id, False)
                act_icon     = "▼" if act_expanded else "▶"

                act_row = html.Div([
                    html.Div([
                        html.Div(
                            [
                                html.Span(act_icon, style={
                                    "fontSize": "0.62rem", "flexShrink": "0", "paddingRight": "2px",
                                    "color": "var(--bs-secondary)",
                                    "visibility": "visible" if act_asgs else "hidden",
                                }),
                                html.Span(act["titulo"], style={
                                    "overflow": "hidden", "textOverflow": "ellipsis",
                                    "whiteSpace": "nowrap", "fontSize": "0.78rem",
                                }),
                            ],
                            id={"type": "btn-toggle-activity", "index": act_id},
                            n_clicks=0,
                            style={"cursor": "pointer" if act_asgs else "default",
                                   "display": "flex", "alignItems": "center",
                                   "flex": "1", "minWidth": "0", "overflow": "hidden",
                                   "paddingLeft": "20px"},
                        ),
                        _btn("btn-edit-activity",   act_id, "pencil",     "primary", "Editar atividade"),
                        _btn("btn-delete-activity", act_id, "trash",       "danger",  "Excluir atividade"),
                        _btn("btn-new-assignment",  act_id, "person-plus", "success", "Atribuir funcionário"),
                    ], style={
                        "width": f"{LEFT_WIDTH}px", "minWidth": f"{LEFT_WIDTH}px", "flexShrink": "0",
                        "display": "flex", "alignItems": "center", "paddingRight": "6px",
                        "overflow": "hidden",
                        "position": "sticky", "left": "0", "zIndex": "5",
                        "backgroundColor": "var(--bs-body-bg)",
                    }),
                    html.Div(day_stripes + [act_bar] + now_line, style={"position": "relative", "flex": "1", "height": "28px"}),
                ], style={
                    "display": "flex", "alignItems": "center", "height": "32px",
                    "borderBottom": "1px solid var(--bs-border-color-translucent)",
                })
                act_rows.append(act_row)

                asg_rows = []
                for asg in act_asgs:
                    asg_id   = str(asg["_id"])
                    emp_nome = emp_map.get(str(asg.get("funcionario_id", "")), "Funcionário")
                    try:
                        entrada    = _parse_dt(asg["data_hora_entrada"])
                        saida      = _parse_dt(asg["data_hora_saida"])
                        time_range = f"{entrada.strftime('%H:%M')} – {saida.strftime('%H:%M')}"
                    except Exception:
                        time_range = ""
                    asg_bar = _build_assignment_bar(asg, t_start, t_end, activity=act)
                    emp_doc = emp_full_map.get(str(asg.get("funcionario_id", "")))

                    # Avatar grande posicionado no início da barra (pode sobrar da linha — intencional)
                    bar_avatar_children = []
                    try:
                        asg_s = _parse_dt(asg["data_hora_entrada"])
                        asg_left_pct = _to_pct(asg_s, t_start, t_end)
                        bar_avatar_children.append(html.Div(
                            _build_avatar(emp_doc, size=42),
                            style={
                                "position": "absolute", "left": f"{asg_left_pct:.4f}%",
                                "top": "50%",
                                "transform": "translate(-36px, -50%)",
                                "zIndex": "3",
                            },
                        ))
                    except Exception:
                        pass

                    asg_rows.append(html.Div([
                        html.Div([
                            html.Span("↳", style={"color": "var(--bs-secondary)",
                                                 "paddingLeft": "36px", "paddingRight": "4px",
                                                 "fontSize": "0.72rem", "flexShrink": "0"}),
                            _build_avatar(emp_doc, size=20),
                            html.Span(emp_nome, style={
                                "flex": "1", "overflow": "hidden", "textOverflow": "ellipsis",
                                "whiteSpace": "nowrap", "fontSize": "0.72rem",
                                "paddingLeft": "6px", "color": "var(--bs-secondary)", "minWidth": "0",
                            }),
                            html.Span(time_range, style={
                                "fontSize": "0.68rem", "color": "var(--bs-secondary)",
                                "whiteSpace": "nowrap", "paddingRight": "4px", "flexShrink": "0",
                            }),
                            _btn("btn-edit-assignment",   asg_id, "pencil", "primary", "Editar atribuição"),
                            _btn("btn-delete-assignment", asg_id, "trash",  "danger",  "Excluir atribuição"),
                        ], style={
                            "width": f"{LEFT_WIDTH}px", "minWidth": f"{LEFT_WIDTH}px", "flexShrink": "0",
                            "display": "flex", "alignItems": "center", "paddingRight": "6px",
                            "overflow": "hidden",
                            "position": "sticky", "left": "0", "zIndex": "5",
                            "backgroundColor": "var(--bs-light-bg-subtle, #f8f9fa)",
                        }),
                        html.Div(
                            day_stripes + ([asg_bar] if asg_bar else []) + bar_avatar_children + now_line,
                            style={"position": "relative", "flex": "1", "height": "28px", "overflow": "visible"},
                        ),
                    ], style={
                        "display": "flex", "alignItems": "center", "height": "30px",
                        "borderBottom": "1px dashed var(--bs-border-color-translucent)",
                        "backgroundColor": "var(--bs-light-bg-subtle)",
                        "overflow": "visible",
                    }))

                if asg_rows:
                    act_rows.append(html.Div(
                        asg_rows,
                        style={"display": "block" if act_expanded else "none"},
                    ))

            proj_cat_rows.append(html.Div(
                act_rows,
                id={"type": "gantt-category-rows", "index": cat_id},
                style={"display": "block" if is_expanded else "none"},
            ))

        rows.append(html.Div(
            proj_cat_rows,
            id={"type": "gantt-project-rows", "index": proj_id},
            style={"display": "block" if proj_expanded else "none"},
        ))

    return html.Div(rows, style={"overflowX": "auto", "width": "100%"})
