"""Mini calendário Mon-first com coluna de número da semana à esquerda.

Alternativa controlada ao HTML5 `<input type="week">` (que segue o locale do Chrome,
fora do nosso controle) e ao `dcc.DatePickerSingle` (sem coluna de semana).

Cada linha = uma semana clicável (Seg→Dom + nº da semana). Hover pinta a linha
inteira em azul claro; semana selecionada fica destacada.
"""

from datetime import date, timedelta
from dash import html


_DIAS_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
_MESES_PT = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
             "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def build_week_picker(year, month, selected_iso=None, dmin=None, dmax=None):
    """Renderiza o calendário do mês com semanas clicáveis.

    Args:
        year, month: mês a exibir.
        selected_iso: ISO week ("YYYY-Www") atualmente selecionada (destaque).
        dmin/dmax: limites de data válida (semanas fora ficam desabilitadas).
    """
    first_of_month = date(year, month, 1)
    # Segunda da 1ª semana que toca o mês
    first_monday = first_of_month - timedelta(days=first_of_month.weekday())
    today = date.today()

    # ---- header de navegação (ano + mês) ----------------------------------
    nav_btn = lambda dir_, sym, title: html.Button(
        sym, id={"type": "hh-pickmonth", "dir": dir_}, n_clicks=0,
        title=title, className="hh-month-nav-btn",
        style={"border": "none", "background": "transparent", "cursor": "pointer",
               "fontSize": "1rem", "padding": "2px 8px",
               "color": "var(--bs-body-color)"},
    )
    header = html.Div([
        nav_btn("prev_year", "«", "Ano anterior"),
        nav_btn("prev", "‹", "Mês anterior"),
        html.Span(f"{_MESES_PT[month]} {year}", style={
            "fontWeight": "700", "fontSize": "0.95rem", "flex": "1",
            "textAlign": "center", "color": "var(--bs-body-color)",
        }),
        nav_btn("next", "›", "Próximo mês"),
        nav_btn("next_year", "»", "Próximo ano"),
    ], style={"display": "flex", "alignItems": "center",
              "padding": "4px 4px 6px", "borderBottom": "1px solid var(--bs-border-color)"})

    # ---- cabeçalho de colunas ---------------------------------------------
    head_cell = lambda txt, w: html.Th(
        txt, style={"width": w, "fontSize": "0.66rem", "fontWeight": "700",
                    "padding": "4px 2px", "textAlign": "center",
                    "color": "var(--bs-secondary)",
                    "background": "var(--bs-secondary-bg)"})
    head_row = html.Tr([head_cell("Sem", "38px"),
                        *[head_cell(d, "32px") for d in _DIAS_PT]])

    # ---- 6 linhas de semanas ----------------------------------------------
    rows = []
    for w_idx in range(6):
        week_start = first_monday + timedelta(weeks=w_idx)
        week_end = week_start + timedelta(days=6)
        iso_y, iso_w, _ = week_start.isocalendar()
        iso_str = f"{iso_y}-W{iso_w:02d}"

        disabled = False
        if dmin and week_end < dmin:
            disabled = True
        if dmax and week_start > dmax:
            disabled = True

        is_selected = (iso_str == selected_iso)

        # célula do nº da semana
        sem_cell = html.Td(f"S{iso_w}", style={
            "fontSize": "0.7rem", "fontWeight": "700", "padding": "5px 2px",
            "textAlign": "center", "color": ("#6c757d" if disabled else "#0d6efd"),
            "background": "var(--bs-tertiary-bg)",
            "borderRight": "1px solid var(--bs-border-color)",
        })

        # 7 células de dia
        day_cells = []
        for di in range(7):
            d = week_start + timedelta(days=di)
            in_month = (d.month == month)
            is_today = (d == today)
            cell_style = {
                "fontSize": "0.78rem", "padding": "5px 2px", "textAlign": "center",
                "color": ("#bbb" if not in_month else "var(--bs-body-color)"),
                "fontWeight": "700" if is_today else "400",
            }
            if is_today:
                cell_style.update({"background": "rgba(233,109,56,0.18)",
                                   "borderRadius": "50%"})
            day_cells.append(html.Td(str(d.day), style=cell_style))

        row_cls = "hh-pick-week-row"
        if is_selected:
            row_cls += " hh-pick-week-selected"
        if disabled:
            row_cls += " hh-pick-week-disabled"

        rows.append(html.Tr(
            [sem_cell, *day_cells],
            id={"type": "hh-pick-week", "iso": iso_str if not disabled else f"__off__{w_idx}"},
            n_clicks=0,
            className=row_cls,
        ))

    table = html.Table([html.Thead(head_row), html.Tbody(rows)],
                       style={"borderCollapse": "collapse", "width": "100%",
                              "fontFamily": "system-ui, sans-serif"})

    return html.Div([header, table],
                    style={"background": "var(--bs-body-bg)", "padding": "6px",
                           "minWidth": "300px"})
