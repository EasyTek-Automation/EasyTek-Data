# src/components/gantt_chart.py

from datetime import datetime, timedelta
from dash import html

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


# ---------------------------------------------------------------------------
# Eixo de tempo
# ---------------------------------------------------------------------------

def build_time_axis(t_start, t_end, granularity):
    """
    Gera lista de html.Div posicionados como marcadores do eixo de tempo.
    granularity: 'horas' | 'dias' | 'semanas' | 'meses'
    """
    MONTH_NAMES = [
        "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    ]

    markers = []

    if granularity == "horas":
        # passo de 30 minutos, alinhado ao início da hora
        cursor = t_start.replace(minute=0, second=0, microsecond=0)
        if cursor < t_start:
            cursor += timedelta(minutes=30)
        while cursor <= t_end:
            label = cursor.strftime("%H:%M")
            left = _to_pct(cursor, t_start, t_end)
            markers.append((left, label))
            cursor += timedelta(minutes=30)

    elif granularity == "dias":
        cursor = t_start.replace(hour=0, minute=0, second=0, microsecond=0)
        if cursor < t_start:
            cursor += timedelta(days=1)
        while cursor <= t_end:
            label = cursor.strftime("%d/%m")
            left = _to_pct(cursor, t_start, t_end)
            markers.append((left, label))
            cursor += timedelta(days=1)

    elif granularity == "semanas":
        # início na segunda-feira
        cursor = t_start.replace(hour=0, minute=0, second=0, microsecond=0)
        cursor -= timedelta(days=cursor.weekday())
        if cursor < t_start:
            cursor += timedelta(weeks=1)
        while cursor <= t_end:
            week_num = cursor.isocalendar()[1]
            week_end = cursor + timedelta(days=6)
            label = f"Sem {week_num}\n{cursor.strftime('%d/%m')}–{week_end.strftime('%d/%m')}"
            left = _to_pct(cursor, t_start, t_end)
            markers.append((left, label))
            cursor += timedelta(weeks=1)

    elif granularity == "meses":
        cursor = t_start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if cursor < t_start:
            # avança um mês
            if cursor.month == 12:
                cursor = cursor.replace(year=cursor.year + 1, month=1)
            else:
                cursor = cursor.replace(month=cursor.month + 1)
        while cursor <= t_end:
            label = f"{MONTH_NAMES[cursor.month]} {cursor.year}"
            left = _to_pct(cursor, t_start, t_end)
            markers.append((left, label))
            if cursor.month == 12:
                cursor = cursor.replace(year=cursor.year + 1, month=1)
            else:
                cursor = cursor.replace(month=cursor.month + 1)

    axis_divs = []
    for left, label in markers:
        axis_divs.append(
            html.Div(
                label,
                style={
                    "position": "absolute",
                    "left":     f"{left:.4f}%",
                    "top":      "0",
                    "fontSize": "0.7rem",
                    "color":    "var(--bs-secondary)",
                    "whiteSpace": "pre",
                    "transform": "translateX(-50%)",
                    "borderLeft": "1px solid var(--bs-border-color)",
                    "paddingLeft": "3px",
                },
            )
        )
    return axis_divs


# ---------------------------------------------------------------------------
# Barras de atividade
# ---------------------------------------------------------------------------

def _build_activity_bar(activity, assignments, t_start, t_end):
    """Constrói uma linha de atividade com as 3 camadas CSS."""
    act_start = _parse_dt(activity["data_hora_inicio"])
    act_end   = _parse_dt(activity["data_hora_fim"])
    now       = datetime.utcnow()

    left_pct  = _to_pct(act_start, t_start, t_end)
    right_pct = _to_pct(act_end,   t_start, t_end)
    width_pct = right_pct - left_pct

    progress  = int(activity.get("progresso_real", 0))
    green_width_pct = width_pct * progress / 100.0

    # marcador da hora atual (só visível se now está entre início e fim)
    marker_div = None
    if act_start <= now <= act_end:
        marker_left_pct = left_pct + _to_pct(now, act_start, act_end) * width_pct / 100.0
        marker_div = html.Div(
            style={
                "position":        "absolute",
                "left":            f"{marker_left_pct:.4f}%",
                "top":             "0",
                "bottom":          "0",
                "width":           "2px",
                "backgroundColor": "var(--bs-danger)",
                "zIndex":          "3",
            }
        )

    # barra verde (progresso)
    green_bar = html.Div(
        style={
            "position":        "absolute",
            "left":            f"{left_pct:.4f}%",
            "top":             "25%",
            "height":          "50%",
            "width":           f"{green_width_pct:.4f}%",
            "minWidth":        "0px",
            "backgroundColor": "var(--bs-success)",
            "opacity":         "0.85",
            "borderRadius":    "2px",
            "zIndex":          "2",
        }
    )

    # barra ciano (período planejado)
    cyan_bar = html.Div(
        style={
            "position":        "absolute",
            "left":            f"{left_pct:.4f}%",
            "top":             "20%",
            "height":          "60%",
            "width":           f"{width_pct:.4f}%",
            "minWidth":        "4px",
            "backgroundColor": "var(--bs-info)",
            "opacity":         "0.5",
            "borderRadius":    "2px",
            "zIndex":          "1",
        }
    )

    label = html.Span(
        activity["titulo"],
        style={
            "position":   "absolute",
            "left":       f"{left_pct:.4f}%",
            "top":        "0",
            "fontSize":   "0.72rem",
            "color":      "var(--bs-body-color)",
            "whiteSpace": "nowrap",
            "zIndex":     "4",
            "paddingLeft": "4px",
        }
    )

    children = [cyan_bar, green_bar, label]
    if marker_div:
        children.append(marker_div)

    return html.Div(
        children,
        style={
            "position": "relative",
            "height":   "28px",
            "margin":   "2px 0",
        },
    )


# ---------------------------------------------------------------------------
# Construtor principal
# ---------------------------------------------------------------------------

def build_gantt_chart(categories, activities, assignments, granularity="dias", expanded_state=None):
    """
    Constrói o componente visual do Gantt.

    categories: lista de dicts (gantt_categories)
    activities: lista de dicts (gantt_activities)
    assignments: lista de dicts (gantt_assignments)
    granularity: 'horas' | 'dias' | 'semanas' | 'meses'
    expanded_state: dict {category_id: bool} — True = expandido
    """
    if expanded_state is None:
        expanded_state = {}

    if not categories:
        return html.Div(
            "Nenhuma categoria cadastrada.",
            className="text-muted p-3",
        )

    # Determinar intervalo visível com padding
    all_starts = [_parse_dt(c["data_hora_inicio"]) for c in categories]
    all_ends   = [_parse_dt(c["data_hora_fim"])    for c in categories]
    t_start_raw = min(all_starts)
    t_end_raw   = max(all_ends)

    PADDING = {
        "horas":   timedelta(hours=1),
        "dias":    timedelta(days=1),
        "semanas": timedelta(weeks=1),
        "meses":   timedelta(days=30),
    }
    pad = PADDING.get(granularity, timedelta(days=1))
    t_start = t_start_raw - pad
    t_end   = t_end_raw   + pad

    # índices de atribuição por atividade
    assignments_by_activity = {}
    for a in assignments:
        aid = str(a.get("atividade_id", ""))
        assignments_by_activity.setdefault(aid, []).append(a)

    # índice de atividades por categoria
    activities_by_category = {}
    for act in activities:
        cid = str(act.get("categoria_id", ""))
        activities_by_category.setdefault(cid, []).append(act)

    # eixo de tempo
    axis_markers = build_time_axis(t_start, t_end, granularity)
    time_axis = html.Div(
        axis_markers,
        style={
            "position":   "relative",
            "height":     "32px",
            "borderBottom": "1px solid var(--bs-border-color)",
            "marginBottom": "4px",
        },
    )

    # linhas de categoria + atividades
    rows = []
    for cat in categories:
        cat_id    = str(cat["_id"])
        is_expanded = expanded_state.get(cat_id, True)

        cat_start = _parse_dt(cat["data_hora_inicio"])
        cat_end   = _parse_dt(cat["data_hora_fim"])
        left_pct  = _to_pct(cat_start, t_start, t_end)
        right_pct = _to_pct(cat_end,   t_start, t_end)
        width_pct = right_pct - left_pct

        cat_bar = html.Div(
            html.Span(cat["nome"], style={"fontSize": "0.8rem", "fontWeight": "600", "paddingLeft": "4px"}),
            style={
                "position":        "absolute",
                "left":            f"{left_pct:.4f}%",
                "top":             "10%",
                "height":          "80%",
                "width":           f"{width_pct:.4f}%",
                "minWidth":        "4px",
                "backgroundColor": "var(--bs-primary)",
                "opacity":         "0.35",
                "borderRadius":    "3px",
            },
        )

        toggle_icon = "▼" if is_expanded else "▶"
        cat_row = html.Div(
            [
                # coluna do nome (fixo à esquerda)
                html.Div(
                    [
                        html.Span(toggle_icon, className="me-1", style={"cursor": "pointer"},
                                  id={"type": "btn-toggle-category", "index": cat_id}),
                        html.Strong(cat["nome"], style={"fontSize": "0.82rem"}),
                    ],
                    style={"width": "200px", "minWidth": "200px", "overflow": "hidden",
                           "textOverflow": "ellipsis", "whiteSpace": "nowrap",
                           "paddingRight": "8px", "flexShrink": "0"},
                ),
                # área de barras
                html.Div(
                    [cat_bar],
                    style={"position": "relative", "flex": "1", "height": "30px"},
                ),
            ],
            style={
                "display":       "flex",
                "alignItems":    "center",
                "height":        "34px",
                "borderBottom":  "1px solid var(--bs-border-color)",
                "backgroundColor": "var(--bs-tertiary-bg)",
            },
        )
        rows.append(cat_row)

        # linhas de atividade (colapsáveis)
        cat_acts = activities_by_category.get(cat_id, [])
        act_rows = []
        for act in cat_acts:
            act_id   = str(act["_id"])
            act_asgs = assignments_by_activity.get(act_id, [])
            act_bar  = _build_activity_bar(act, act_asgs, t_start, t_end)
            act_row  = html.Div(
                [
                    html.Div(
                        act["titulo"],
                        style={"width": "200px", "minWidth": "200px", "overflow": "hidden",
                               "textOverflow": "ellipsis", "whiteSpace": "nowrap",
                               "paddingLeft": "24px", "paddingRight": "8px",
                               "fontSize": "0.78rem", "flexShrink": "0"},
                    ),
                    html.Div(
                        [act_bar],
                        style={"position": "relative", "flex": "1", "height": "28px"},
                    ),
                ],
                style={
                    "display":     "flex",
                    "alignItems":  "center",
                    "height":      "32px",
                    "borderBottom": "1px solid var(--bs-border-color-translucent)",
                },
            )
            act_rows.append(act_row)

        activities_container = html.Div(
            act_rows,
            id={"type": "gantt-category-rows", "index": cat_id},
            style={"display": "block" if is_expanded else "none"},
        )
        rows.append(activities_container)

    chart = html.Div(
        [time_axis] + rows,
        style={"overflowX": "auto", "width": "100%"},
    )

    return chart
