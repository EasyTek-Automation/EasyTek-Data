"""Indicadores de Manutenção V2 — POC drilldown.

Layout:
- 3 cards KPI clicáveis (Avaria em cima centralizada, MTBF/MTTR embaixo) — barra mensal da planta.
- Click em qualquer região do card → modal de equipamentos.
- Click em equipamento → modal de meses ampliado.
- Click em mês → modal de dias ampliado.
- Click em dia → modal com tabela de paradas.

Dados mockados (random seed determinístico).
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go


def _blank_fig(color="#0d6efd", height=280):
    """Figure placeholder limpa (sem 'No data' default Plotly). Mostra só fundo branco
    e ícone sutil — substituída pelo callback assim que dados chegam.
    """
    fig = go.Figure()
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        plot_bgcolor="rgba(248,250,252,0.6)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, showgrid=False, zeroline=False),
        yaxis=dict(visible=False, showgrid=False, zeroline=False),
        showlegend=False,
        annotations=[dict(
            text="⌛ Carregando…",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color=color, family="Arial"),
            opacity=0.5,
        )],
    )
    return fig


def _blank_sparkline(color="#0d6efd"):
    """Sparkline skeleton — barra cinza animada via CSS."""
    return html.Div(className="v2-skeleton",
                    style={"width": "90px", "height": "20px"})


def _blank_ring():
    """Ring skeleton — círculo cinza."""
    return html.Div(className="v2-skeleton",
                    style={"width": "60px", "height": "60px", "borderRadius": "50%"})


# ==================== i18n — dicionário de traduções ====================
TRANS = {
    "pt": {
        "page_title":    "Indicadores de Manutenção V2",
        "page_subtitle": "POC drilldown — Clique em qualquer card pra explorar Avaria / MTBF / MTTR.",
        "btn_refresh":   "Atualizar",
        "btn_filters":   "Filtros",
        "btn_export":    "Exportar",
        "btn_apply":     "Aplicar",
        "filter_period": "Período",
        "filter_year":   "Ano de referência",
        "filter_range":  "Período personalizado",
        "filter_equip":  "Equipamentos",
        "filter_codes":  "Códigos de avaria",
        "period_year":   "Ano completo",
        "period_last12": "Últimos 12 meses",
        "period_custom": "Personalizado",
        "tab_general":   "📊 Geral",
        "tab_data":      "📋 Dados",
        "tab_report":    "📅 Relatório",
        "tl_title":      "Linha do Tempo de Estados",
        "tl_scale":      "Escala do eixo",
        "tl_nav":        "Navegação no tempo",
        "tl_today":      "Hoje",
        "tl_hours":      "Horas",
        "tl_days":       "Dias",
        "tl_focus":      "Foco manutenção",
        "tl_only_av":    "Só avaria",
        "lg_producao":   "Produção",
        "lg_avaria":     "Avaria",
        "lg_setup":      "Setup",
        "lg_logistica":  "Logística",
        "lg_refeicao":   "Refeição",
        "lg_mtto":       "MTTO Aut.",
        "lg_processo":   "Processo",
        "kpi_mtbf_sub":  "Mean Time Between Failures (horas)",
        "kpi_mttr_sub":  "Mean Time To Repair (minutos)",
        "kpi_br_sub":    "Breakdown Rate — Planta (mensal)",
        "kpi_mtbf_title": "M01 - MTBF",
        "kpi_mttr_title": "M02 - MTTR",
        "kpi_br_title":   "M03 - Taxa de Avaria",
        "beta_badge":    "BETA · Dados em Auditoria",
        "beta_tooltip":  "Página em validação. Dados sintéticos — não refletem a operação real.",
        # Chart traces / titles
        "chart_trend":   "Tendência",
        "chart_target":  "Meta",
        "chart_value":   "Valor",
        "chart_status":  "Status",
        "chart_delta":   "Δ",
        "chart_top_n_paradas": "Top {n} Paradas",
        "chart_duracao_min": "Duração (min)",
        "chart_eventos":     "Eventos",
        "chart_codigo":      "Código",
        "tl_planta_mensal":  "Planta — mensal",
        # Modal drilldown
        "mdl_back":      "Voltar",
        "mdl_close":     "Fechar",
        "mdl_equipamentos":   "Equipamentos",
        "mdl_meses":     "12 meses",
        "mdl_top_paradas":    "Top paradas",
        "mdl_top_5_paradas":  "Top 5 Paradas",
        "mdl_top_10_paradas": "Top 10 paradas — detalhe:",
        "mdl_paradas_em":     "Paradas em",
        "mdl_eventos":   "eventos",
        "mdl_no_paradas_mes": "Mês limpo!",
        "mdl_no_paradas_mes_desc": "Nenhuma parada registrada nesse período.",
        "mdl_no_paradas_dia": "Dia perfeito!",
        "mdl_no_paradas_dia_desc": "Nenhuma parada registrada nesse dia.",
        "mdl_click_barra_mes":  "Clique numa barra ou num card pra ver os dias:",
        "mdl_click_barra_dia":  "Clique numa barra ou num card pra ver as paradas:",
        "mdl_kpi_avaria":    "Taxa de Avaria",
        "mdl_kpi_mtbf":      "MTBF",
        "mdl_kpi_mttr":      "MTTR",
        # DataTable colunas
        "tbl_hora":      "Hora",
        "tbl_equipamento":"Equipamento",
        "tbl_causa":     "Causa",
        "tbl_duracao":   "Duração (min)",
        "tbl_codigo":    "Código",
        "tbl_data":      "Data",
        "tbl_eventos":   "Eventos",
        "tbl_num":       "#",
        # Meses curtos
        "month_short":   ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"],
    },
    "es": {
        "page_title":    "Indicadores de Mantenimiento V2",
        "page_subtitle": "POC drilldown — Clic en cualquier tarjeta para explorar Avería / MTBF / MTTR.",
        "btn_refresh":   "Actualizar",
        "btn_filters":   "Filtros",
        "btn_export":    "Exportar",
        "btn_apply":     "Aplicar",
        "filter_period": "Período",
        "filter_year":   "Año de referencia",
        "filter_range":  "Período personalizado",
        "filter_equip":  "Equipos",
        "filter_codes":  "Códigos de avería",
        "period_year":   "Año completo",
        "period_last12": "Últimos 12 meses",
        "period_custom": "Personalizado",
        "tab_general":   "📊 General",
        "tab_data":      "📋 Datos",
        "tab_report":    "📅 Informe",
        "tl_title":      "Línea de Tiempo de Estados",
        "tl_scale":      "Escala del eje",
        "tl_nav":        "Navegación temporal",
        "tl_today":      "Hoy",
        "tl_hours":      "Horas",
        "tl_days":       "Días",
        "tl_focus":      "Foco mantenimiento",
        "tl_only_av":    "Solo avería",
        "lg_producao":   "Producción",
        "lg_avaria":     "Avería",
        "lg_setup":      "Setup",
        "lg_logistica":  "Logística",
        "lg_refeicao":   "Comida",
        "lg_mtto":       "MTTO Aut.",
        "lg_processo":   "Proceso",
        "kpi_mtbf_sub":  "Mean Time Between Failures (horas)",
        "kpi_mttr_sub":  "Mean Time To Repair (minutos)",
        "kpi_br_sub":    "Tasa de Avería — Planta (mensual)",
        "kpi_mtbf_title": "M01 - MTBF",
        "kpi_mttr_title": "M02 - MTTR",
        "kpi_br_title":   "M03 - Tasa de Avería",
        "beta_badge":    "BETA · Datos en Auditoría",
        "beta_tooltip":  "Página en validación. Datos sintéticos — no reflejan la operación real.",
        "chart_trend":   "Tendencia",
        "chart_target":  "Meta",
        "chart_value":   "Valor",
        "chart_status":  "Estado",
        "chart_delta":   "Δ",
        "chart_top_n_paradas": "Top {n} Paradas",
        "chart_duracao_min": "Duración (min)",
        "chart_eventos":     "Eventos",
        "chart_codigo":      "Código",
        "tl_planta_mensal":  "Planta — mensual",
        "mdl_back":      "Volver",
        "mdl_close":     "Cerrar",
        "mdl_equipamentos":   "Equipos",
        "mdl_meses":     "12 meses",
        "mdl_top_paradas":    "Top paradas",
        "mdl_top_5_paradas":  "Top 5 Paradas",
        "mdl_top_10_paradas": "Top 10 paradas — detalle:",
        "mdl_paradas_em":     "Paradas en",
        "mdl_eventos":   "eventos",
        "mdl_no_paradas_mes": "¡Mes limpio!",
        "mdl_no_paradas_mes_desc": "Ninguna parada registrada en ese período.",
        "mdl_no_paradas_dia": "¡Día perfecto!",
        "mdl_no_paradas_dia_desc": "Ninguna parada registrada en ese día.",
        "mdl_click_barra_mes":  "Clic en una barra o tarjeta para ver los días:",
        "mdl_click_barra_dia":  "Clic en una barra o tarjeta para ver las paradas:",
        "mdl_kpi_avaria":    "Tasa de Avería",
        "mdl_kpi_mtbf":      "MTBF",
        "mdl_kpi_mttr":      "MTTR",
        "tbl_hora":      "Hora",
        "tbl_equipamento":"Equipo",
        "tbl_causa":     "Causa",
        "tbl_duracao":   "Duración (min)",
        "tbl_codigo":    "Código",
        "tbl_data":      "Fecha",
        "tbl_eventos":   "Eventos",
        "tbl_num":       "#",
        "month_short":   ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"],
    },
    "en": {
        "page_title":    "Maintenance Indicators V2",
        "page_subtitle": "Drilldown POC — Click any card to explore Breakdown / MTBF / MTTR.",
        "btn_refresh":   "Refresh",
        "btn_filters":   "Filters",
        "btn_export":    "Export",
        "btn_apply":     "Apply",
        "filter_period": "Period",
        "filter_year":   "Reference year",
        "filter_range":  "Custom range",
        "filter_equip":  "Equipment",
        "filter_codes":  "Breakdown codes",
        "period_year":   "Full year",
        "period_last12": "Last 12 months",
        "period_custom": "Custom",
        "tab_general":   "📊 Overview",
        "tab_data":      "📋 Data",
        "tab_report":    "📅 Report",
        "tl_title":      "States Timeline",
        "tl_scale":      "Axis scale",
        "tl_nav":        "Time navigation",
        "tl_today":      "Today",
        "tl_hours":      "Hours",
        "tl_days":       "Days",
        "tl_focus":      "Maintenance focus",
        "tl_only_av":    "Breakdown only",
        "lg_producao":   "Production",
        "lg_avaria":     "Breakdown",
        "lg_setup":      "Setup",
        "lg_logistica":  "Logistics",
        "lg_refeicao":   "Meal",
        "lg_mtto":       "Auto MTTO",
        "lg_processo":   "Process",
        "kpi_mtbf_sub":  "Mean Time Between Failures (hours)",
        "kpi_mttr_sub":  "Mean Time To Repair (minutes)",
        "kpi_br_sub":    "Breakdown Rate — Plant (monthly)",
        "kpi_mtbf_title": "M01 - MTBF",
        "kpi_mttr_title": "M02 - MTTR",
        "kpi_br_title":   "M03 - Breakdown Rate",
        "beta_badge":    "BETA · Data in Audit",
        "beta_tooltip":  "Page under validation. Synthetic data — does not reflect real operation.",
        "chart_trend":   "Trend",
        "chart_target":  "Target",
        "chart_value":   "Value",
        "chart_status":  "Status",
        "chart_delta":   "Δ",
        "chart_top_n_paradas": "Top {n} Breakdowns",
        "chart_duracao_min": "Duration (min)",
        "chart_eventos":     "Events",
        "chart_codigo":      "Code",
        "tl_planta_mensal":  "Plant — monthly",
        "mdl_back":      "Back",
        "mdl_close":     "Close",
        "mdl_equipamentos":   "Equipment",
        "mdl_meses":     "12 months",
        "mdl_top_paradas":    "Top breakdowns",
        "mdl_top_5_paradas":  "Top 5 Breakdowns",
        "mdl_top_10_paradas": "Top 10 breakdowns — detail:",
        "mdl_paradas_em":     "Breakdowns in",
        "mdl_eventos":   "events",
        "mdl_no_paradas_mes": "Clean month!",
        "mdl_no_paradas_mes_desc": "No breakdowns recorded in this period.",
        "mdl_no_paradas_dia": "Perfect day!",
        "mdl_no_paradas_dia_desc": "No breakdowns recorded that day.",
        "mdl_click_barra_mes":  "Click a bar or card to see the days:",
        "mdl_click_barra_dia":  "Click a bar or card to see the breakdowns:",
        "mdl_kpi_avaria":    "Breakdown Rate",
        "mdl_kpi_mtbf":      "MTBF",
        "mdl_kpi_mttr":      "MTTR",
        "tbl_hora":      "Time",
        "tbl_equipamento":"Equipment",
        "tbl_causa":     "Cause",
        "tbl_duracao":   "Duration (min)",
        "tbl_codigo":    "Code",
        "tbl_data":      "Date",
        "tbl_eventos":   "Events",
        "tbl_num":       "#",
        "month_short":   ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],
    },
}


def t(key: str, lang: str = "pt") -> str:
    """Tradução por key. Fallback pra 'pt' se lang inválido."""
    return TRANS.get(lang, TRANS["pt"]).get(key, key)


_FLAG_SVGS = {
    "pt": '''<svg viewBox="0 0 60 42" xmlns="http://www.w3.org/2000/svg">
        <rect width="60" height="42" fill="#009c3b"/>
        <polygon points="30,5 55,21 30,37 5,21" fill="#ffdf00"/>
        <circle cx="30" cy="21" r="8.5" fill="#002776"/>
        <path d="M22,21 a8,8 0 0 1 16,0" stroke="#fff" stroke-width="1.4" fill="none"/>
    </svg>''',
    "es": '''<svg viewBox="0 0 60 42" xmlns="http://www.w3.org/2000/svg">
        <rect width="60" height="11" fill="#aa151b"/>
        <rect y="11" width="60" height="20" fill="#f1bf00"/>
        <rect y="31" width="60" height="11" fill="#aa151b"/>
    </svg>''',
    "en": '''<svg viewBox="0 0 60 42" xmlns="http://www.w3.org/2000/svg">
        <rect width="60" height="42" fill="#012169"/>
        <path d="M0,0 L60,42 M60,0 L0,42" stroke="#fff" stroke-width="5"/>
        <path d="M0,0 L60,42" stroke="#c8102e" stroke-width="2.5" stroke-dasharray="30 30"/>
        <path d="M60,0 L0,42" stroke="#c8102e" stroke-width="2.5" stroke-dasharray="30 30"/>
        <rect x="25" width="10" height="42" fill="#fff"/>
        <rect y="16" width="60" height="10" fill="#fff"/>
        <rect x="27" width="6" height="42" fill="#c8102e"/>
        <rect y="18" width="60" height="6" fill="#c8102e"/>
    </svg>''',
}


def _lang_switcher():
    """3 bandeiras SVG inline + badge BETA discreta. Alinhamento controlado pelo container pai."""
    import base64
    flags = [("pt", "Português"), ("es", "Español"), ("en", "English")]
    return html.Div(
        [
            *[
                html.Button(
                    html.Img(
                        src="data:image/svg+xml;base64," + base64.b64encode(_FLAG_SVGS[code].encode()).decode(),
                        alt=title,
                        style={"width": "28px", "height": "20px", "borderRadius": "3px",
                               "boxShadow": "0 1px 3px rgba(0,0,0,0.2)"},
                    ),
                    id={"type": "v2-lang-btn", "lang": code},
                    title=title,
                    n_clicks=0,
                    className="v2-lang-flag",
                ) for code, title in flags
            ],
            html.Span("BETA", className="v2-beta-badge", title="Recurso em fase beta"),
        ],
        className="d-flex align-items-center gap-2 mb-2 v2-lang-switcher",
    )


def _kpi_card(card_id, title, subtitle, color, graph_id):
    """Card KPI clicável — html.Div wrapper porque dbc.Card v2.0.3 não aceita n_clicks.
    Header: title + trend-delta-{kpi_key} placeholder + drilldown badge.
    """
    # Deriva kpi key do graph_id (kpi-graph-mtbf → mtbf)
    kpi_key = graph_id.replace("kpi-graph-", "")
    return html.Div(
        dbc.Card(
            [
                dbc.CardHeader(
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Span(
                                        [
                                            html.Strong(title, id=f"v2-i18n-kpi-title-{kpi_key}", style={"fontSize": "1rem"}),
                                            html.Span(id=f"trend-delta-{kpi_key}"),  # callback preenche
                                        ],
                                    ),
                                    html.Div(
                                        [
                                            html.Span(
                                                subtitle,
                                                id=f"v2-i18n-kpi-sub-{kpi_key}",
                                                className="text-muted",
                                                style={"fontSize": "0.78rem", "lineHeight": "1.2"},
                                            ),
                                            html.Span(
                                                _blank_sparkline(color),
                                                id=f"sparkline-{kpi_key}",
                                                className="v2-sparkline-mini",
                                            ),
                                        ],
                                        className="d-flex justify-content-between align-items-center mt-1",
                                    ),
                                ],
                                style={"flex": "1"},
                            ),
                            dbc.Badge(
                                [html.I(className="bi bi-zoom-in me-1"), "drilldown"],
                                color="light",
                                text_color="primary",
                                className="border align-self-start",
                                style={"fontSize": "0.7rem", "fontWeight": "500"},
                            ),
                        ],
                        className="d-flex justify-content-between align-items-start gap-2",
                        style={"minHeight": "74px"},  # +22px pra acomodar sparkline
                    ),
                    className="py-2",
                ),
                dbc.CardBody(
                    [
                        # Linha topo: valor grande animado + ring progress (alcance da meta)
                        html.Div(
                            [
                                html.Span(
                                    "—",  # placeholder até JS animar (Dash não toca)
                                    id=f"value-anim-{kpi_key}",
                                    **{
                                        "data-v2-anim": "0",
                                        "data-v2-unit": "",
                                        "data-v2-decimals": "2",
                                    },
                                    style={
                                        "fontSize": "1.7rem",
                                        "fontWeight": "700",
                                        "color": color,
                                        "letterSpacing": "-0.5px",
                                        "lineHeight": "1",
                                    },
                                ),
                                html.Div(
                                    _blank_ring(),
                                    id=f"ring-{kpi_key}",
                                    style={"width": "60px", "height": "60px"},
                                ),
                            ],
                            className="d-flex justify-content-between align-items-center px-2 mb-2",
                            style={"height": "60px"},
                        ),
                        dcc.Graph(
                            id=graph_id,
                            figure=_blank_fig(color, 280),  # placeholder bonito antes do callback
                            config={"displayModeBar": False, "staticPlot": True, "responsive": True},
                            style={"height": "280px", "width": "100%"},
                        ),
                    ],
                    className="p-2",
                    style={"minHeight": "340px"},
                ),
            ],
            className="shadow-sm h-100 indicator-v2-card",
            style={"borderTop": f"4px solid {color}"},
        ),
        id=card_id,
        n_clicks=0,
        style={"cursor": "pointer", "height": "100%"},
    )


def _toolbar_field(label, control, width="auto", label_id=None):
    """Wrapper consistente pra controle de toolbar — label uniforme + altura fixa.

    label_id opcional pra permitir i18n (callback troca children por idioma).
    """
    label_kwargs = {"id": label_id} if label_id else {}
    return dbc.Col(
        html.Div(
            [
                html.Label(
                    label,
                    className="text-muted fw-semibold d-block mb-1",
                    style={
                        "fontSize": "0.72rem",
                        "letterSpacing": "0.4px",
                        "textTransform": "uppercase",
                    },
                    **label_kwargs,
                ),
                html.Div(
                    control,
                    style={
                        "minHeight": "31px",
                        "display": "flex",
                        "alignItems": "center",
                    },
                ),
            ]
        ),
        width=width,
        className="evocon-toolbar-field",
    )


def layout():
    return dbc.Container(
        [
            # Store de idioma — persiste entre sessões via localStorage
            dcc.Store(id="store-v2-lang", storage_type="local", data="pt"),

            # Header
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            [
                                html.H2(
                                    [
                                        html.I(
                                            className="bi bi-graph-up-arrow me-3",
                                            style={"color": "#0d6efd"},
                                        ),
                                        html.Span(
                                            "Indicadores de Manutenção V2",
                                            id="v2-i18n-page-title",
                                        ),
                                        dbc.Badge(
                                            [
                                                html.I(className="bi bi-exclamation-triangle-fill me-2"),
                                                html.Span(
                                                    "BETA · Dados em Auditoria",
                                                    id="v2-i18n-beta-badge",
                                                ),
                                            ],
                                            id="v2-beta-badge",
                                            color="warning",
                                            text_color="dark",
                                            className="v2-beta-badge ms-3 align-middle",
                                            pill=True,
                                        ),
                                        dbc.Tooltip(
                                            "Página em validação. Dados sintéticos — não refletem a operação real.",
                                            id="v2-beta-tooltip",
                                            target="v2-beta-badge",
                                            placement="bottom",
                                        ),
                                    ],
                                    className="mb-1 d-flex align-items-center flex-wrap",
                                ),
                                html.P(
                                    "POC drilldown — Clique em qualquer card pra explorar Avaria / MTBF / MTTR.",
                                    id="v2-i18n-page-subtitle",
                                    className="text-muted mb-0",
                                    style={"fontSize": "0.9rem"},
                                ),
                            ]
                        ),
                        xs=12, md=8,
                    ),
                    dbc.Col(
                        html.Div(
                            [
                                # Bandeiras centralizadas em relação aos botões + badge BETA
                                _lang_switcher(),
                                dbc.ButtonGroup(
                                    [
                                        dbc.Button(
                                            [html.I(className="bi bi-arrow-clockwise me-2"),
                                             html.Span("Atualizar", id="v2-i18n-btn-refresh")],
                                            id="btn-refresh-indicators-v2",
                                            color="primary", size="sm", outline=True,
                                        ),
                                        dbc.Button(
                                            [html.I(className="bi bi-funnel me-2"),
                                             html.Span("Filtros", id="v2-i18n-btn-filters")],
                                            id="btn-filters-indicators-v2",
                                            color="secondary", size="sm", outline=True,
                                        ),
                                        dbc.Button(
                                            [html.I(className="bi bi-file-earmark-excel me-2"),
                                             html.Span("Exportar", id="v2-i18n-btn-export")],
                                            id="btn-export-v2-xlsx",
                                            color="success", size="sm", outline=True,
                                        ),
                                    ]
                                ),
                                # Toggle de visualização v1.0 / v2.0
                                dbc.ButtonGroup(
                                    [
                                        dbc.Button(
                                            "v1.0",
                                            id="btn-view-v1-from-v2",
                                            color="primary",
                                            size="sm",
                                            outline=True,
                                            href="/maintenance/indicators",
                                        ),
                                        dbc.Button(
                                            "v2.0",
                                            id="btn-view-v2-from-v2",
                                            color="primary",
                                            size="sm",
                                            outline=False,
                                        ),
                                    ]
                                ),
                            ],
                            className="d-flex flex-column align-items-md-end align-items-start gap-2",
                        ),
                        xs=12, md=4,
                        className="d-flex align-items-end justify-content-md-end justify-content-start mt-3 mt-md-0",
                    ),
                ],
                className="mb-4 align-items-start",
            ),

            # IM-11 — Filtros V2 (collapse, paridade V1)
            dbc.Collapse(
                dbc.Card(
                    dbc.CardBody(
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        html.Label("Período", id="v2-i18n-filter-period",
                                                   className="form-label small fw-semibold mb-1"),
                                        dcc.Dropdown(
                                            id="filter-v2-period-type",
                                            options=[
                                                {"label": "Ano completo", "value": "year"},
                                                {"label": "Últimos 12 meses", "value": "last12"},
                                                {"label": "Personalizado", "value": "custom"},
                                            ],
                                            value="year",
                                            clearable=False,
                                        ),
                                    ],
                                    md=3,
                                ),
                                dbc.Col(
                                    [
                                        html.Label("Ano de referência", id="v2-i18n-filter-year",
                                                   className="form-label small fw-semibold mb-1"),
                                        dcc.Dropdown(
                                            id="filter-v2-reference-year",
                                            options=[{"label": str(y), "value": y} for y in (2024, 2025, 2026)],
                                            value=2026,
                                            clearable=False,
                                        ),
                                    ],
                                    md=2,
                                    id="col-filter-v2-year",
                                ),
                                dbc.Col(
                                    [
                                        html.Label("Período personalizado", id="v2-i18n-filter-range",
                                                   className="form-label small fw-semibold mb-1"),
                                        dcc.DatePickerRange(
                                            id="filter-v2-date-range",
                                            display_format="DD/MM/YYYY",
                                            className="d-block",
                                        ),
                                    ],
                                    md=3,
                                    id="col-filter-v2-range",
                                    style={"display": "none"},
                                ),
                                dbc.Col(
                                    [
                                        html.Label("Equipamentos", id="v2-i18n-filter-equip",
                                                   className="form-label small fw-semibold mb-1"),
                                        dcc.Dropdown(
                                            id="filter-v2-equipment",
                                            multi=True,
                                            placeholder="(todos)",
                                        ),
                                    ],
                                    md=4,
                                ),
                                dbc.Col(
                                    [
                                        html.Label("Códigos de avaria", id="v2-i18n-filter-codes",
                                                   className="form-label small fw-semibold mb-1"),
                                        dcc.Dropdown(
                                            id="filter-v2-breakdown-codes",
                                            options=[{"label": c, "value": c} for c in
                                                     ["201", "S201", "202", "S202", "203", "S203",
                                                      "204", "S204", "205", "S205", "110", "S110"]],
                                            value=["201", "S201", "202", "S202", "203", "S203",
                                                   "204", "S204", "205", "S205", "110", "S110"],
                                            multi=True,
                                        ),
                                    ],
                                    md=4,
                                ),
                                dbc.Col(
                                    dbc.Button(
                                        [html.I(className="bi bi-check2 me-1"),
                                         html.Span("Aplicar", id="v2-i18n-btn-apply")],
                                        id="btn-apply-v2-filters",
                                        color="primary",
                                        className="w-100",
                                    ),
                                    md=2,
                                    className="d-flex align-items-end",
                                ),
                            ],
                            className="g-3",
                        ),
                    ),
                    className="shadow-sm mb-3",
                ),
                id="collapse-v2-filters",
                is_open=False,
            ),

            # Store de filtros V2 (IM-11)
            dcc.Store(id="store-v2-filters", storage_type="memory"),
            dcc.Download(id="download-v2-xlsx"),

            # Tabs (replica indicators atual)
            dbc.Tabs(
                [
                    dbc.Tab(
                        label="📊 Geral",
                        id="tab-v2-general-component",
                        tab_id="tab-v2-general",
                        children=html.Div(
                            [
                                # Stores/interval do evocon (independem da ordem visual)
                                dcc.Store(id="store-evocon-granularity", storage_type="local", data="horas"),
                                dcc.Store(id="store-evocon-offset", storage_type="memory", data=0),
                                dcc.Store(id="evocon-anim-dummy", storage_type="memory"),
                                dcc.Store(id="store-evocon-mtto-only", storage_type="local", data=False),
                                dcc.Interval(id="interval-evocon-now", interval=30_000, n_intervals=0),

                                # ===== ROW 1: 3 KPI cards alinhados (MTBF, MTTR, AVARIA) =====
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            _kpi_card(
                                                card_id="kpi-card-mtbf",  # noqa: alinhamento spotlight via .kpi-row-v2
                                                title="M01 - MTBF",
                                                subtitle="Mean Time Between Failures (horas)",
                                                color="#198754",
                                                graph_id="kpi-graph-mtbf",
                                            ),
                                            xs=12, md=4,
                                        ),
                                        dbc.Col(
                                            _kpi_card(
                                                card_id="kpi-card-mttr",
                                                title="M02 - MTTR",
                                                subtitle="Mean Time To Repair (minutos)",
                                                color="#0d6efd",
                                                graph_id="kpi-graph-mttr",
                                            ),
                                            xs=12, md=4,
                                        ),
                                        dbc.Col(
                                            _kpi_card(
                                                card_id="kpi-card-breakdown",
                                                title="M03 - Taxa de Avaria",
                                                subtitle="Breakdown Rate — Planta (mensal)",
                                                color="#dc3545",
                                                graph_id="kpi-graph-breakdown",
                                            ),
                                            xs=12, md=4,
                                        ),
                                    ],
                                    className="mb-4 kpi-row-v2",
                                ),

                                # ===== ROW 2: TIMELINE (visual sofisticado matching cards top) =====
                                dbc.Row(
                                    dbc.Col(
                                        html.Div(
                                            dbc.Card(
                                                [
                                                    dbc.CardHeader(
                                                        html.Div(
                                                            [
                                                                html.Div(
                                                                    [
                                                                        html.I(className="bi bi-activity me-2",
                                                                               style={"color": "#0d6efd",
                                                                                      "fontSize": "1.15rem"}),
                                                                        html.Strong(
                                                                            "Linha do Tempo de Estados",
                                                                            id="v2-i18n-tl-title",
                                                                            style={"fontSize": "1rem"},
                                                                        ),
                                                                    ],
                                                                    style={"flex": "1"},
                                                                ),
                                                                dbc.Badge(
                                                                    [html.I(className="bi bi-clock-history me-1"),
                                                                     html.Span(
                                                                         "—",
                                                                         id="label-evocon-period",
                                                                         className="evocon-period-text",
                                                                     )],
                                                                    color="light",
                                                                    text_color="primary",
                                                                    className="border evocon-period-pill",
                                                                ),
                                                            ],
                                                            className="d-flex justify-content-between align-items-center gap-2",
                                                        ),
                                                        className="py-2",
                                                    ),
                                                    dbc.CardBody(
                                                        [
                                                            # Toolbar — controles consistentes com cards top
                                                            dbc.Row(
                                                                [
                                                                    _toolbar_field(
                                                                        "Escala do eixo",
                                                                        dbc.ButtonGroup(
                                                                            [
                                                                                dbc.Button(
                                                                                    [html.I(className="bi bi-clock me-1"),
                                                                                     html.Span("Horas", id="v2-i18n-tl-btn-hours")],
                                                                                    id="btn-evocon-gran-horas",
                                                                                    color="primary", size="sm",
                                                                                    outline=False, n_clicks=0,
                                                                                    className="evocon-gran-btn",
                                                                                ),
                                                                                dbc.Button(
                                                                                    [html.I(className="bi bi-calendar-day me-1"),
                                                                                     html.Span("Dias", id="v2-i18n-tl-btn-days")],
                                                                                    id="btn-evocon-gran-dias",
                                                                                    color="primary", size="sm",
                                                                                    outline=True, n_clicks=0,
                                                                                    className="evocon-gran-btn",
                                                                                ),
                                                                            ],
                                                                            className="shadow-sm",
                                                                        ),
                                                                        label_id="v2-i18n-tl-scale",
                                                                    ),
                                                                    _toolbar_field(
                                                                        "Navegação no tempo",
                                                                        dbc.ButtonGroup(
                                                                            [
                                                                                dbc.Button(html.I(className="bi bi-chevron-left"),
                                                                                           id="btn-evocon-prev",
                                                                                           color="secondary", outline=True, size="sm"),
                                                                                dbc.Button(
                                                                                    [html.I(className="bi bi-house-door me-1"),
                                                                                     html.Span("Hoje", id="v2-i18n-tl-btn-today")],
                                                                                    id="btn-evocon-today",
                                                                                    color="primary", outline=True, size="sm"),
                                                                                dbc.Button(html.I(className="bi bi-chevron-right"),
                                                                                           id="btn-evocon-next",
                                                                                           color="secondary", outline=True, size="sm"),
                                                                            ],
                                                                            className="shadow-sm",
                                                                        ),
                                                                        label_id="v2-i18n-tl-nav",
                                                                    ),
                                                                    dbc.Col(
                                                                        html.Div(
                                                                            [
                                                                                html.Label(
                                                                                    "Foco manutenção",
                                                                                    id="v2-i18n-tl-focus",
                                                                                    className="text-muted fw-semibold d-block mb-1",
                                                                                    style={
                                                                                        "fontSize": "0.72rem",
                                                                                        "letterSpacing": "0.4px",
                                                                                        "textTransform": "uppercase",
                                                                                    },
                                                                                ),
                                                                                html.Div(
                                                                                    dbc.Switch(
                                                                                        id="switch-v2-mtto-only",
                                                                                        label="Só avaria",
                                                                                        value=False,
                                                                                        className="mb-0",
                                                                                    ),
                                                                                    style={"minHeight": "31px",
                                                                                           "display": "flex",
                                                                                           "alignItems": "center"},
                                                                                ),
                                                                            ]
                                                                        ),
                                                                        width="auto",
                                                                        className="evocon-toolbar-field",
                                                                    ),
                                                                ],
                                                                className="g-3 mb-3 align-items-end",
                                                            ),
                                                            # Legenda — chips estilizados
                                                            html.Div(
                                                                [
                                                                    html.Small("Legenda:",
                                                                               className="text-muted fw-semibold me-2",
                                                                               style={"fontSize": "0.72rem",
                                                                                      "textTransform": "uppercase",
                                                                                      "letterSpacing": "0.4px"}),
                                                                    html.Span("Produção",  id="v2-i18n-lg-producao",  className="evocon-chip evocon-chip-producao"),
                                                                    html.Span("Avaria",    id="v2-i18n-lg-avaria",    className="evocon-chip evocon-chip-avaria"),
                                                                    html.Span("Setup",     id="v2-i18n-lg-setup",     className="evocon-chip evocon-chip-setup"),
                                                                    html.Span("Logística", id="v2-i18n-lg-logistica", className="evocon-chip evocon-chip-logistica"),
                                                                    html.Span("Refeição",  id="v2-i18n-lg-refeicao",  className="evocon-chip evocon-chip-refeicao"),
                                                                    html.Span("MTTO Aut.", id="v2-i18n-lg-mtto",      className="evocon-chip evocon-chip-mtto"),
                                                                    html.Span("Processo",  id="v2-i18n-lg-processo",  className="evocon-chip evocon-chip-processo"),
                                                                ],
                                                                className="d-flex flex-wrap align-items-center gap-2 mb-3 pb-3 border-bottom",
                                                            ),
                                                            dcc.Loading(
                                                                id="loading-home-evocon",
                                                                type="dot",
                                                                color="#0d6efd",
                                                                children=[
                                                                    html.Div(
                                                                        id="evocon-anim-wrap",
                                                                        children=[
                                                                            dcc.Graph(
                                                                                id="graph-home-evocon-timeline",
                                                                                config={"responsive": True,
                                                                                        "displayModeBar": False,
                                                                                        "showTips": False},
                                                                                style={"visibility": "hidden",
                                                                                       "height": "560px"},
                                                                            )
                                                                        ],
                                                                    )
                                                                ],
                                                            ),
                                                        ],
                                                        className="p-3",
                                                    ),
                                                ],
                                                className="shadow-sm indicator-v2-card-timeline",
                                                style={"borderTop": "4px solid #0d6efd"},
                                            ),
                                        ),
                                    ),
                                    className="mb-4",
                                ),

                            ],
                            className="p-3",
                        ),
                    ),
                    dbc.Tab(
                        label="📋 Dados",
                        id="tab-v2-data-component",
                        tab_id="tab-v2-data",
                        children=html.Div(
                            [
                                dcc.Loading(
                                    id="rd-v2-data-loading",
                                    type="circle",
                                    color="#0d6efd",
                                    children=html.Div(
                                        [
                                            html.Div(id="rd-v2-data-coverage",
                                                      className="mb-4"),
                                            html.H5(
                                                [html.I(className="bi bi-eyeglasses me-2"),
                                                 "Como os Cards do Topo São Calculados"],
                                                className="mt-3 mb-1",
                                            ),
                                            html.P(
                                                "Para cada mês: KPI calculado dos totais brutos. "
                                                "O valor exibido nos cards é a média aritmética desses valores mensais.",
                                                className="text-muted small mb-3",
                                            ),
                                            html.Div(id="rd-v2-data-monthly", className="mb-4"),
                                            html.H5(
                                                [html.I(className="bi bi-calculator me-2"),
                                                 "Resumo da Planta"],
                                                className="mt-3 mb-3",
                                            ),
                                            html.Div(id="rd-v2-data-summary", className="mb-4"),
                                            html.H5(
                                                [html.I(className="bi bi-list-ul me-2"),
                                                 "Motivos de Parada"],
                                                className="mt-3 mb-3",
                                            ),
                                            html.Div(id="rd-v2-data-motivos", className="mb-4"),
                                            html.H5(
                                                [html.I(className="bi bi-table me-2"),
                                                 "Detalhamento por Equipamento"],
                                                className="mb-3",
                                            ),
                                            html.Div(id="rd-v2-data-table"),
                                        ],
                                        className="p-3",
                                    ),
                                ),
                            ],
                        ),
                    ),
                    dbc.Tab(
                        label="📅 Relatório",
                        id="tab-v2-report-component",
                        tab_id="tab-v2-report",
                        children=html.Div(
                            [
                                # Header: período + DatePicker BR-02b + botões export
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                html.Small(
                                                    id="rd-v2-periodo-label",
                                                    className="text-muted d-block",
                                                ),
                                                html.Div(
                                                    [
                                                        html.Label(
                                                            "Dia das 24h:",
                                                            htmlFor="kpi-v2-date-24h",
                                                            className="me-2 small text-muted",
                                                        ),
                                                        dcc.DatePickerSingle(
                                                            id="kpi-v2-date-24h",
                                                            display_format="DD/MM/YYYY",
                                                            first_day_of_week=1,
                                                            placeholder="Escolha o dia",
                                                            persistence=False,
                                                            clearable=True,
                                                        ),
                                                    ],
                                                    className="d-flex align-items-center mt-2",
                                                ),
                                            ],
                                        ),
                                        html.Div(
                                            [
                                                dbc.Button(
                                                    [html.I(className="bi bi-filetype-pdf me-2"),
                                                     "Exportar PDF"],
                                                    id="btn-kpi-v2-export-pdf",
                                                    color="primary",
                                                    size="sm",
                                                    disabled=True,
                                                    className="me-2",
                                                ),
                                                dbc.Button(
                                                    [html.I(className="bi bi-file-earmark-word me-2"),
                                                     "Exportar DOCX"],
                                                    id="btn-kpi-v2-export-docx",
                                                    color="secondary",
                                                    size="sm",
                                                    disabled=True,
                                                    className="me-2",
                                                ),
                                                dbc.Button(
                                                    [html.I(className="bi bi-link-45deg me-2"),
                                                     "Copiar Link"],
                                                    id="btn-kpi-v2-share",
                                                    color="info",
                                                    outline=True,
                                                    size="sm",
                                                ),
                                            ],
                                        ),
                                    ],
                                    className="d-flex justify-content-between align-items-start flex-wrap gap-2 mt-3 mb-3",
                                ),
                                # Container preenchido pelo callback ao ativar a aba
                                dcc.Loading(
                                    id="rd-v2-loading",
                                    type="circle",
                                    color="#0d6efd",
                                    children=html.Div(
                                        id="rd-v2-content-container",
                                        children=html.Div(
                                            "Carregue a aba para gerar o relatório…",
                                            className="text-muted text-center py-5",
                                        ),
                                    ),
                                ),
                                # Downloads + clipboard helpers
                                dcc.Download(id="download-kpi-v2-pdf"),
                                dcc.Download(id="download-kpi-v2-docx"),
                                dcc.Clipboard(id="kpi-v2-share-clipboard",
                                              target_id=None,
                                              style={"display": "none"}),
                                # Toast feedback (share/erro)
                                dbc.Toast(
                                    id="kpi-v2-share-toast",
                                    header="KPI Report v2",
                                    is_open=False,
                                    dismissable=True,
                                    duration=4000,
                                    icon="info",
                                    style={"position": "fixed", "top": 66, "right": 10,
                                           "width": 350, "zIndex": 9999},
                                ),
                                # Toast progresso geração PDF/DOCX (auto-dismiss 10s, portado V1).
                                dbc.Toast(
                                    children=[
                                        "As informações estão sendo compiladas e renderizadas "
                                        "para geração do seu relatório. "
                                        "Esse processo pode durar de 15 a 30s.",
                                        dbc.Progress(
                                            id="toast-kpi-v2-generating-progress",
                                            value=100,
                                            color="info",
                                            striped=True,
                                            animated=True,
                                            className="mt-2",
                                            style={"height": "5px"},
                                        ),
                                    ],
                                    id="toast-kpi-v2-generating",
                                    header="Gerando relatório...",
                                    is_open=False,
                                    dismissable=True,
                                    duration=10000,
                                    icon="info",
                                    style={
                                        "position": "fixed",
                                        "top": "155px",
                                        "right": "20px",
                                        "zIndex": 1999,
                                        "minWidth": "320px",
                                        "maxWidth": "420px",
                                    },
                                ),
                                dcc.Interval(
                                    id="interval-toast-kpi-v2-tick",
                                    interval=100,
                                    disabled=True,
                                    n_intervals=0,
                                ),
                                # Stores compartilhados com a rota standalone
                                dcc.Store(id="store-kpi-v2-data", storage_type="memory"),
                                dcc.Store(id="store-kpi-v2-lang",
                                          storage_type="local", data="pt"),
                                dcc.Store(id="store-kpi-v2-blocks-toggle",
                                          storage_type="local",
                                          data={str(i): True for i in range(1, 6)}),
                            ],
                        ),
                    ),
                ],
                id="tabs-indicators-v2",
                active_tab="tab-v2-general",
            ),

            # Stores drilldown
            dcc.Store(id="store-v2-level", data="planta"),
            dcc.Store(id="store-v2-kpi", data=None),
            dcc.Store(id="store-v2-equipment", data=None),
            dcc.Store(id="store-v2-month", data=None),
            dcc.Store(id="store-v2-year", data=None),
            dcc.Store(id="store-v2-day", data=None),

            # Modal drilldown (XL, scrollable)
            dbc.Modal(
                [
                    dbc.ModalHeader(
                        [
                            dbc.ModalTitle(id="modal-v2-title"),
                        ],
                        close_button=True,
                    ),
                    dbc.ModalBody(
                        [
                            html.Div(id="modal-v2-breadcrumb", className="mb-3"),
                            dcc.Loading(
                                id="loading-modal-v2",
                                type="circle",
                                color="#0d6efd",
                                children=html.Div(id="modal-v2-content"),
                                delay_show=120,  # evita piscar spinner em renders muito rápidos
                            ),
                        ]
                    ),
                    dbc.ModalFooter(
                        [
                            dbc.Button(
                                [
                                    html.I(className="bi bi-arrow-left me-1"),
                                    html.Span("Voltar", id="v2-i18n-btn-back"),
                                ],
                                id="btn-v2-back",
                                color="secondary",
                                outline=True,
                            ),
                            dbc.Button(
                                html.Span("Fechar", id="v2-i18n-btn-close"),
                                id="btn-v2-close",
                                color="primary",
                                className="ms-auto",
                            ),
                        ]
                    ),
                ],
                id="modal-v2",
                size="xl",
                is_open=False,
                scrollable=True,
                # Bootstrap não suporta nativamente "quase full screen" via size,
                # então usamos fullscreen breakpoint
                fullscreen="lg-down",
                # Custom dialog class pra controlar largura
                content_class_name="modal-v2-content",
                dialog_class_name="modal-v2-dialog",
            ),
        ],
        fluid=True,
        className="p-4",
    )
