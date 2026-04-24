# src/components/gantt_chart.py

from datetime import datetime, timedelta
from dash import html
import dash_bootstrap_components as dbc

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


def _render_multiline(text):
    """
    Converte texto multi-linha em lista de elementos Dash para uso dentro
    de dbc.Tooltip. Cada linha vira string seguida de html.Br(); ao final
    insere html.Hr() como separador visual antes das demais linhas do tooltip.
    Retorna lista vazia se o texto for vazio/branco — o consumer omite a
    linha do tooltip (SP-13 item 7: sem rótulo "Observação: (vazio)").
    """
    if not text or not text.strip():
        return []
    linhas = text.strip().split("\n")
    out = []
    for linha in linhas:
        out.append(linha)
        out.append(html.Br())
    out.append(html.Hr(style={"margin": "4px 0"}))
    return out


def _progresso_esperado_pct(activity, now=None):
    """Percentual esperado pelo tempo decorrido (BR-06). 0..100 ou None se datas inválidas.
    Usa hora de Brasília (UTC-3) por consistência com _activity_status_color."""
    try:
        ini = _parse_dt(activity["data_hora_inicio"])
        fim = _parse_dt(activity["data_hora_fim"])
    except Exception:
        return None
    n = now if now is not None else (datetime.utcnow() - timedelta(hours=3))
    total = (fim - ini).total_seconds()
    if total <= 0:
        return 100.0 if n >= fim else 0.0
    elapsed = (n - ini).total_seconds()
    return max(0.0, min(100.0, elapsed / total * 100.0))


def _fmt_dt_label(value):
    """Formata datetime como 'dd/mm/YYYY HH:MM' para exibição em tooltips."""
    try:
        return _parse_dt(value).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return "—"


def _build_project_tooltip_content(proj):
    """Conteúdo do tooltip de Projeto (DS-09 §2)."""
    out = [html.Strong(proj.get("nome", "—")), html.Br()]
    tipo = proj.get("tipo", "")
    if tipo:
        out.extend([f"Tipo: {tipo}", html.Br()])
    out.extend(_render_multiline(proj.get("observacoes", "")))
    out.extend([
        f"Início: {_fmt_dt_label(proj.get('data_hora_inicio'))}", html.Br(),
        f"Fim: {_fmt_dt_label(proj.get('data_hora_fim'))}",
    ])
    return out


def _build_category_tooltip_content(cat):
    """Conteúdo do tooltip de Categoria (DS-09 §2 — sem campo descritivo nesta entrega)."""
    return [
        html.Strong(cat.get("nome", "—")), html.Br(),
        f"Início: {_fmt_dt_label(cat.get('data_hora_inicio'))}", html.Br(),
        f"Fim: {_fmt_dt_label(cat.get('data_hora_fim'))}",
    ]


def _build_activity_tooltip_content(act):
    """Conteúdo do tooltip de Atividade (DS-09 §2)."""
    out = [html.Strong(act.get("titulo", "—")), html.Br()]
    out.extend(_render_multiline(act.get("observacao", "")))
    out.extend([
        f"Início: {_fmt_dt_label(act.get('data_hora_inicio'))}", html.Br(),
        f"Fim: {_fmt_dt_label(act.get('data_hora_fim'))}", html.Br(),
        f"Progresso real: {int(act.get('progresso_real', 0))}%", html.Br(),
    ])
    esperado = _progresso_esperado_pct(act)
    if esperado is not None:
        out.append(f"Progresso esperado: {int(round(esperado))}%")
    return out


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
    progresso_esperado = _progresso_esperado_pct(activity)
    if progresso_esperado is None:
        return STATUS_COLOR_NO_PRAZO
    progresso_real = float(activity.get("progresso_real", 0) or 0)
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

    linhas = [activity.get("titulo", "—")]
    obs = (activity.get("observacao") or "").strip()
    if obs:
        linhas.append(obs)
    linhas.extend([
        f"Início:    {act_start.strftime('%d/%m/%Y %H:%M')}",
        f"Fim:       {act_end.strftime('%d/%m/%Y %H:%M')}",
        f"Progresso: {progress}%",
    ])
    tooltip_text = "\n".join(linhas)
    base_bar = html.Div(title=tooltip_text, style={
        "position": "absolute", "left": f"{left_pct:.4f}%", "top": "15%",
        "height": "70%", "width": f"{width_pct:.4f}%", "minWidth": "4px",
        "backgroundColor": bar_color, "opacity": "0.35",
        "borderRadius": "999px", "zIndex": "1", "cursor": "help",
    })
    progress_bar = html.Div(title=tooltip_text, style={
        "position": "absolute", "left": f"{left_pct:.4f}%", "top": "15%",
        "height": "70%", "width": f"{green_w:.4f}%", "minWidth": "0px",
        "backgroundColor": bar_color, "opacity": "0.95",
        "borderRadius": "999px", "zIndex": "2", "cursor": "help",
    })
    children = [base_bar, progress_bar]
    return html.Div(children, style={"position": "relative", "height": "28px", "margin": "2px 0"})


def _build_assignment_bar(assignment, t_start, t_end, activity=None, employee_name=""):
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
    tooltip = (
        f"{employee_name or 'Funcionário'}\n"
        f"Entrada: {s.strftime('%d/%m/%Y %H:%M')}\n"
        f"Saída:   {e.strftime('%d/%m/%Y %H:%M')}"
    )

    bar = html.Div(title=tooltip, style={
        "position": "absolute", "left": f"{asg_left:.4f}%", "top": "40%",
        "height": "20%", "width": f"{asg_width:.4f}%", "minWidth": "12px",
        "backgroundColor": "#FBC02D", "opacity": "0.95",
        "borderRadius": "999px", "cursor": "help",
    })
    return html.Div([bar], style={"position": "relative", "height": "100%"})


# ---------------------------------------------------------------------------
# Construtor principal
# ---------------------------------------------------------------------------

def build_gantt_resource_view(employees, activities, assignments, categories, projects,
                              granularity="dias", hour_offset=0, filter_query="",
                              employees_state=None):
    """
    View invertida: agrupa por funcionário em vez de projeto.
    Cada funcionário vira uma 'swimlane' horizontal mostrando todas suas
    atribuições no tempo — útil pra analisar carga de trabalho.
    """
    if not employees or not activities:
        return html.Div(
            "Nenhum funcionário ou atividade cadastrada.",
            className="text-muted p-3",
        )

    cat_map = {str(c["_id"]): c for c in (categories or [])}
    proj_map = {str(p["_id"]): p for p in (projects or [])}
    act_map = {str(a["_id"]): a for a in (activities or [])}

    # Determinar janela temporal (mesma lógica do build_gantt_chart)
    now_brt = datetime.utcnow() - timedelta(hours=3)
    offset_td = timedelta(hours=hour_offset or 0)

    if granularity == "horas":
        center  = now_brt + offset_td
        t_start = center - timedelta(hours=24)
        t_end   = center + timedelta(hours=24)
    else:
        PAST_WINDOW = {
            "dias":    timedelta(days=3),
            "semanas": timedelta(weeks=1),
            "meses":   timedelta(days=30),
        }
        MIN_FUTURE = {
            "dias":    timedelta(days=14),
            "semanas": timedelta(weeks=6),
            "meses":   timedelta(days=150),
        }
        past       = PAST_WINDOW.get(granularity, timedelta(days=3))
        min_future = MIN_FUTURE.get(granularity, timedelta(days=14))
        all_ends   = [_parse_dt(a["data_hora_fim"]) for a in activities]
        data_end   = max(all_ends) if all_ends else now_brt
        t_start    = (now_brt - past) + offset_td
        t_end      = max(data_end, now_brt + min_future) + offset_td

    day_stripes = _build_day_stripes(t_start, t_end)
    now_line    = _build_now_line(t_start, t_end)

    # Contar e filtrar atribuições totalmente fora da janela (saída antes de t_start)
    hidden_past_count = 0
    visible_assignments = []
    for a in assignments:
        try:
            a_end = _parse_dt(a["data_hora_saida"])
            if a_end < t_start:
                hidden_past_count += 1
                continue
        except Exception:
            pass
        visible_assignments.append(a)
    assignments = visible_assignments

    # Filtrar funcionários que têm atribuições (ativos)
    asgs_by_emp = {}
    for a in assignments:
        asgs_by_emp.setdefault(str(a.get("funcionario_id", "")), []).append(a)

    # Aplicar filtro: se filter_query, só mostra funcionários cujas atribuições batam
    q = (filter_query or "").strip().lower()
    filtered_employees = []
    for e in employees:
        emp_id = str(e["_id"])
        emp_asgs = asgs_by_emp.get(emp_id, [])
        if not emp_asgs and not e.get("ativo", True):
            continue  # pula inativos sem atribuições
        if q:
            name_match = q in e.get("nome", "").lower()
            asg_match = False
            for a in emp_asgs:
                act = act_map.get(str(a.get("atividade_id", "")))
                if act and q in act.get("titulo", "").lower():
                    asg_match = True; break
            if not (name_match or asg_match):
                continue
        filtered_employees.append(e)

    if not filtered_employees:
        return html.Div("Nenhum funcionário com atribuições no filtro atual.",
                        className="text-muted p-4 text-center")

    def _make_axis_row():
        axis_bg = "#e5e7eb"
        right_content = _build_day_stripes(t_start, t_end) + build_time_axis(t_start, t_end, granularity) + now_line
        if hidden_past_count > 0:
            right_content.append(html.Div(
                [html.I(className="bi bi-chevron-double-left me-1"),
                 f"{hidden_past_count} anterior" + ("es" if hidden_past_count > 1 else "")],
                title=f"{hidden_past_count} atribuição(ões) fora da janela visível",
                style={
                    "position": "absolute", "left": "4px", "top": "50%",
                    "transform": "translateY(-50%)",
                    "zIndex": "6",
                    "backgroundColor": "#E96D38", "color": "#ffffff",
                    "fontSize": "0.66rem", "fontWeight": "600",
                    "padding": "2px 8px", "borderRadius": "999px",
                    "whiteSpace": "nowrap", "pointerEvents": "auto",
                    "boxShadow": "0 1px 3px rgba(0,0,0,0.2)",
                },
            ))
        return html.Div([
            html.Div(style={
                "width": f"{LEFT_WIDTH}px", "minWidth": f"{LEFT_WIDTH}px", "flexShrink": "0",
                "position": "sticky", "left": "0", "zIndex": "5",
                "backgroundColor": axis_bg,
            }),
            html.Div(
                right_content,
                style={"position": "relative", "flex": "1", "marginLeft": "36px",
                       "height": f"{_axis_height_for(granularity)}px"},
            ),
        ], style={"display": "flex", "alignItems": "flex-end", "marginBottom": "2px",
                  "backgroundColor": axis_bg, "border": "1px solid #d1d5db",
                  "borderRadius": "3px"})

    rows = [_make_axis_row()]

    for emp in filtered_employees:
        emp_id = str(emp["_id"])
        emp_asgs = sorted(asgs_by_emp.get(emp_id, []),
                          key=lambda a: _parse_dt(a.get("data_hora_entrada") or t_start))

        # Contador de horas totais no período visível
        total_hours = 0.0
        for a in emp_asgs:
            try:
                s = _parse_dt(a["data_hora_entrada"])
                e = _parse_dt(a["data_hora_saida"])
                total_hours += max(0, (e - s).total_seconds() / 3600.0)
            except Exception:
                pass

        # Painel esquerdo: avatar + nome + turno + total de horas + toggle expand/collapse
        turno = (emp.get("turno_padrao") or "?")
        emp_expanded = (employees_state or {}).get(emp_id, False)
        toggle_icon  = "▼" if emp_expanded else "▶"

        left_panel = html.Div(
            [
                html.Span(toggle_icon, style={
                    "fontSize": "0.7rem", "flexShrink": "0",
                    "color": "var(--bs-secondary)", "paddingRight": "4px",
                    "visibility": "visible" if emp_asgs else "hidden",
                }),
                _build_avatar(emp, size=28),
                html.Div([
                    html.Div(emp["nome"], style={
                        "fontWeight": "600", "fontSize": "0.85rem",
                        "whiteSpace": "nowrap", "overflow": "hidden", "textOverflow": "ellipsis",
                    }),
                    html.Div([
                        html.Span(f"Turno {turno}", className="badge bg-secondary me-1",
                                  style={"fontSize": "0.62rem"}),
                        html.Span(f"{total_hours:.1f}h atribuídas", style={
                            "fontSize": "0.7rem", "color": "var(--bs-secondary)",
                        }),
                    ]),
                ], style={"flex": "1", "marginLeft": "10px", "minWidth": "0", "overflow": "hidden"}),
            ],
            id={"type": "btn-toggle-employee-row", "index": emp_id},
            n_clicks=0,
            style={
                "width": f"{LEFT_WIDTH}px", "minWidth": f"{LEFT_WIDTH}px", "flexShrink": "0",
                "display": "flex", "alignItems": "center", "paddingRight": "6px", "paddingLeft": "8px",
                "overflow": "hidden",
                "position": "sticky", "left": "0", "zIndex": "5",
                "backgroundColor": "var(--bs-body-bg)",
                "cursor": "pointer" if emp_asgs else "default",
            },
        )

        # Painel direito: bars de todas as atribuições + avatar no início de cada uma
        right_items = list(day_stripes)
        for a in emp_asgs:
            try:
                s = _parse_dt(a["data_hora_entrada"])
                e = _parse_dt(a["data_hora_saida"])
            except Exception:
                continue
            asg_left_pct = _to_pct(s, t_start, t_end)
            asg_width = _to_pct(e, t_start, t_end) - asg_left_pct

            # Nome curto da atividade (para tooltip)
            act = act_map.get(str(a.get("atividade_id", "")))
            cat = cat_map.get(str(act.get("categoria_id", ""))) if act else None
            proj = proj_map.get(str(cat.get("projeto_id", ""))) if cat else None
            title_parts = []
            if proj:  title_parts.append(proj.get("nome", ""))
            if cat:   title_parts.append(cat.get("nome", ""))
            if act:   title_parts.append(act.get("titulo", ""))
            tooltip_parts = []
            if title_parts:
                tooltip_parts.append(" → ".join(title_parts))
            tooltip_parts.append(f"Entrada: {s.strftime('%d/%m/%Y %H:%M')}")
            tooltip_parts.append(f"Saída:   {e.strftime('%d/%m/%Y %H:%M')}")
            tooltip = "\n".join(tooltip_parts)

            bar_color = _activity_status_color(act) if act else "#FBC02D"
            right_items.append(html.Div(title=tooltip, style={
                "position": "absolute", "left": f"{asg_left_pct:.4f}%", "top": "20%",
                "height": "60%", "width": f"{asg_width:.4f}%", "minWidth": "12px",
                "backgroundColor": bar_color, "opacity": "0.85",
                "borderRadius": "999px", "cursor": "help",
            }))

        right_items += now_line

        row = html.Div([
            left_panel,
            html.Div(right_items, style={
                "position": "relative", "flex": "1", "marginLeft": "36px", "height": "36px",
                "overflow": "visible",
            }),
        ], style={
            "display": "flex", "alignItems": "center", "height": "44px",
            "borderBottom": "1px solid var(--bs-border-color-translucent)",
            "overflow": "visible",
        })
        rows.append(row)

        # Sub-linhas quando o funcionário está expandido:
        # mostra apenas os pares únicos (projeto, categoria) onde ele tem atribuição.
        # Se o funcionário tem 3 atribuições na mesma categoria do mesmo projeto,
        # aparece UMA linha só. Se trabalha em projetos/categorias distintos, cada
        # combinação única vira uma linha.
        if emp_expanded and emp_asgs:
            seen = set()
            unique_contexts = []
            for a in emp_asgs:
                act = act_map.get(str(a.get("atividade_id", "")))
                cat = cat_map.get(str(act.get("categoria_id", ""))) if act else None
                proj = proj_map.get(str(cat.get("projeto_id", ""))) if cat else None
                if not proj or not cat:
                    continue
                key = (str(proj["_id"]), str(cat["_id"]))
                if key in seen:
                    continue
                seen.add(key)
                unique_contexts.append((proj, cat))

            for proj, cat in unique_contexts:
                sub_left = html.Div(
                    [
                        html.Span("↳", style={"color": "var(--bs-secondary)",
                                              "paddingLeft": "48px", "paddingRight": "6px",
                                              "fontSize": "0.75rem", "flexShrink": "0"}),
                        html.I(className="bi bi-folder-fill me-1",
                               style={"color": "#E96D38", "fontSize": "0.78rem",
                                      "flexShrink": "0"}),
                        html.Span(proj.get("nome", "—"), style={
                            "fontWeight": "600", "fontSize": "0.75rem",
                            "whiteSpace": "nowrap", "overflow": "hidden",
                            "textOverflow": "ellipsis", "flexShrink": "1",
                            "minWidth": "0",
                        }),
                        html.I(className="bi bi-chevron-right mx-1",
                               style={"fontSize": "0.6rem",
                                      "color": "var(--bs-secondary)", "flexShrink": "0"}),
                        html.I(className="bi bi-tag me-1",
                               style={"color": "var(--bs-info)",
                                      "fontSize": "0.72rem", "flexShrink": "0"}),
                        html.Span(cat.get("nome", "—"), style={
                            "fontWeight": "500", "fontSize": "0.72rem",
                            "whiteSpace": "nowrap", "overflow": "hidden",
                            "textOverflow": "ellipsis",
                            "color": "var(--bs-body-color)",
                            "flexShrink": "1", "minWidth": "0",
                        }),
                    ],
                    style={
                        "width": f"{LEFT_WIDTH}px", "minWidth": f"{LEFT_WIDTH}px",
                        "flexShrink": "0",
                        "display": "flex", "alignItems": "center",
                        "overflow": "hidden",
                        "position": "sticky", "left": "0", "zIndex": "5",
                        "backgroundColor": "var(--bs-light-bg-subtle, #f8f9fa)",
                    },
                )

                sub_row = html.Div([
                    sub_left,
                    html.Div(list(day_stripes) + list(now_line), style={
                        "position": "relative", "flex": "1", "marginLeft": "36px",
                        "height": "22px", "overflow": "visible",
                    }),
                ], style={
                    "display": "flex", "alignItems": "center", "height": "26px",
                    "borderBottom": "1px dashed var(--bs-border-color-translucent)",
                    "backgroundColor": "var(--bs-light-bg-subtle, #f8f9fa)",
                })
                rows.append(sub_row)

    return html.Div(rows, style={"overflowX": "auto", "width": "100%"})


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

    # Janela deslizante por granularidade; offset em horas permite navegação
    # ◀ / Hoje / ▶ em qualquer modo (não só horas).
    now_brt = datetime.utcnow() - timedelta(hours=3)
    offset_td = timedelta(hours=hour_offset or 0)

    if granularity == "horas":
        center  = now_brt + offset_td
        t_start = center - timedelta(hours=24)
        t_end   = center + timedelta(hours=24)
    else:
        PAST_WINDOW = {
            "dias":    timedelta(days=3),
            "semanas": timedelta(weeks=1),
            "meses":   timedelta(days=30),
        }
        MIN_FUTURE = {
            "dias":    timedelta(days=14),
            "semanas": timedelta(weeks=6),
            "meses":   timedelta(days=150),
        }
        past       = PAST_WINDOW.get(granularity, timedelta(days=3))
        min_future = MIN_FUTURE.get(granularity, timedelta(days=14))

        all_ends = [_parse_dt(c["data_hora_fim"]) for c in categories]
        for p in (projects or []):
            if p.get("data_hora_fim"):
                all_ends.append(_parse_dt(p["data_hora_fim"]))

        data_end = max(all_ends) if all_ends else now_brt
        t_start  = (now_brt - past) + offset_td
        t_end    = max(data_end, now_brt + min_future) + offset_td

    # Contar atividades fora da janela visível (entirely before t_start)
    # e filtrá-las — evita a compressão à esquerda conforme o tempo avança.
    hidden_past_count = 0
    visible_activities = []
    for a in activities:
        try:
            a_end = _parse_dt(a["data_hora_fim"])
            if a_end < t_start:
                hidden_past_count += 1
                continue
        except Exception:
            pass
        visible_activities.append(a)
    activities = visible_activities

    assignments_by_activity = {}
    visible_act_ids = {str(a["_id"]) for a in activities}
    for a in assignments:
        aid = str(a.get("atividade_id", ""))
        if aid not in visible_act_ids:
            continue
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

        right_content = _build_day_stripes(t_start, t_end) + build_time_axis(t_start, t_end, granularity) + now_line
        if hidden_past_count > 0:
            right_content.append(html.Div(
                [html.I(className="bi bi-chevron-double-left me-1"),
                 f"{hidden_past_count} anterior" + ("es" if hidden_past_count > 1 else "")],
                title=f"{hidden_past_count} atividade(s) fora da janela visível (terminaram antes do período exibido)",
                style={
                    "position": "absolute", "left": "4px", "top": "50%",
                    "transform": "translateY(-50%)",
                    "zIndex": "6",
                    "backgroundColor": "#E96D38", "color": "#ffffff",
                    "fontSize": "0.66rem", "fontWeight": "600",
                    "padding": "2px 8px", "borderRadius": "999px",
                    "whiteSpace": "nowrap", "pointerEvents": "auto",
                    "boxShadow": "0 1px 3px rgba(0,0,0,0.2)",
                },
            ))

        return html.Div([
            html.Div(style={
                "width": f"{LEFT_WIDTH}px", "minWidth": f"{LEFT_WIDTH}px", "flexShrink": "0",
                "position": "sticky", "left": "0", "zIndex": "5",
                "backgroundColor": axis_bg,
            }),
            html.Div(
                right_content,
                style={
                    "position": "relative", "flex": "1", "marginLeft": "36px",
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

    # Cor única da marca do cliente para TODOS os tipos de projeto —
    # mantém identidade visual consistente e evita "salada de cores"
    # quando combinada com as cores de status das atividades.
    # O TIPO do projeto continua sinalizado pelo texto no badge.
    BRAND_COLOR = "#E96D38"
    TIPO_COLOR = {
        "Parada Preventiva":   BRAND_COLOR,
        "Parada Corretiva":    BRAND_COLOR,
        "Projeto de Melhoria": BRAND_COLOR,
        "Outro":               BRAND_COLOR,
    }

    # Eixo global no topo: só aparece quando TODOS os projetos estão colapsados,
    # oferecendo referência temporal sem repetir o eixo dentro dos containers.
    # Se qualquer projeto estiver expandido, cada um exibe seu próprio eixo interno.
    any_project_expanded = any(
        (projects_state or {}).get(str(p["_id"]), True)
        for p in (projects or [])
    )
    rows = []
    if projects and not any_project_expanded:
        rows.append(_make_time_axis_row())

    for proj in (projects or []):
        proj_id       = str(proj["_id"])
        proj_expanded = (projects_state or {}).get(proj_id, True)
        proj_icon     = "▼" if proj_expanded else "▶"
        tipo_color    = TIPO_COLOR.get(proj.get("tipo", ""), BRAND_COLOR)

        proj_bar_children = []
        try:
            p_start = _parse_dt(proj["data_hora_inicio"])
            p_end   = _parse_dt(proj["data_hora_fim"])
            p_left  = _to_pct(p_start, t_start, t_end)
            p_width = _to_pct(p_end,   t_start, t_end) - p_left
            linhas = [f"{proj.get('nome','—')} ({proj.get('tipo','—')})"]
            obs = (proj.get("observacoes") or "").strip()
            if obs:
                linhas.append(obs)
            linhas.extend([
                f"Início: {p_start.strftime('%d/%m/%Y %H:%M')}",
                f"Fim:    {p_end.strftime('%d/%m/%Y %H:%M')}",
            ])
            proj_tooltip = "\n".join(linhas)
            proj_bar_children.append(html.Div(title=proj_tooltip, style={
                "position": "absolute", "left": f"{p_left:.4f}%", "top": "15%",
                "height": "70%", "width": f"{p_width:.4f}%", "minWidth": "4px",
                "backgroundColor": tipo_color, "opacity": "0.9",
                "borderRadius": "999px", "border": f"1px solid {tipo_color}",
                "cursor": "help",
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
                        html.Span(proj["nome"],
                            id={"type": "gantt-label-project", "index": proj_id},
                            tabIndex=0,
                            style={
                                "fontWeight": "700", "fontSize": "0.9rem",
                                "overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap",
                            }),
                        dbc.Tooltip(
                            children=_build_project_tooltip_content(proj),
                            target={"type": "gantt-label-project", "index": proj_id},
                            delay={"show": 500, "hide": 100},
                            className="gantt-tooltip",
                            placement="right",
                        ),
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
            html.Div(day_stripes + proj_bar_children + now_line, style={"position": "relative", "flex": "1", "marginLeft": "36px", "height": "32px"}),
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
                            html.Span(cat["nome"],
                                id={"type": "gantt-label-category", "index": cat_id},
                                tabIndex=0,
                                style={
                                    "fontSize": "0.8rem", "fontWeight": "500",
                                    "overflow": "hidden",
                                    "textOverflow": "ellipsis", "whiteSpace": "nowrap",
                                }),
                            dbc.Tooltip(
                                children=_build_category_tooltip_content(cat),
                                target={"type": "gantt-label-category", "index": cat_id},
                                delay={"show": 500, "hide": 100},
                                className="gantt-tooltip",
                                placement="right",
                            ),
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
                    html.Div(title=(
                        f"{cat.get('nome','—')}\n"
                        f"Início: {cat_start.strftime('%d/%m/%Y %H:%M')}\n"
                        f"Fim:    {cat_end.strftime('%d/%m/%Y %H:%M')}"
                    ), style={
                        "position": "absolute", "left": f"{left_pct:.4f}%", "top": "20%",
                        "height": "60%", "width": f"{width_pct:.4f}%", "minWidth": "4px",
                        "backgroundColor": "#7E57C2", "opacity": "0.75",
                        "borderRadius": "999px", "cursor": "help",
                    }),
                ] + now_line, style={"position": "relative", "flex": "1", "marginLeft": "36px", "height": "28px"}),
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
                                html.Span(act["titulo"],
                                    id={"type": "gantt-label-activity", "index": act_id},
                                    tabIndex=0,
                                    style={
                                        "overflow": "hidden", "textOverflow": "ellipsis",
                                        "whiteSpace": "nowrap", "fontSize": "0.78rem",
                                    }),
                                dbc.Tooltip(
                                    children=_build_activity_tooltip_content(act),
                                    target={"type": "gantt-label-activity", "index": act_id},
                                    delay={"show": 500, "hide": 100},
                                    className="gantt-tooltip",
                                    placement="right",
                                ),
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
                    html.Div(day_stripes + [act_bar] + now_line, style={"position": "relative", "flex": "1", "marginLeft": "36px", "height": "28px"}),
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
                    asg_bar = _build_assignment_bar(asg, t_start, t_end, activity=act,
                                                    employee_name=emp_nome)
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
                            style={"position": "relative", "flex": "1", "marginLeft": "36px", "height": "28px", "overflow": "visible"},
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
