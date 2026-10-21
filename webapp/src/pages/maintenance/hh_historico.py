# -*- coding: utf-8 -*-
"""Aba "Histórico Semanal" — visão analítica do planejamento HH ao longo das semanas.

3ª aba da página de backlog (/maintenance/backlog). **Adição pura** (BR-14): não altera as abas
existentes nem o quadro. Consome `hh_historico_data.py` (agregações retroativas). SDD hh-historico.

- Bloco B: aba lazy (contêiner `hist-content` preenchido na ativação).
- Bloco C: 6 cards + 4 gráficos retroativos + insights.
- Bloco D: interatividade — filtro de período (BR-11), 3 modos de comparação (BR-04), semana parcial
  tracejada + faixa de referência (BR-05), janela de insights editável e salva (BR-13). O layout com
  os controles é montado em `hist_body`; o painel (cards + gráficos) é reconstruído pelo callback
  reativo `build_painel`.
- Bloco E (pendente): captura Fase 2 → gráficos "Trabalho fora do plano" e "Estado do backlog".
"""
from datetime import datetime

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

try:
    from src.utils import hh_data as hd
    from src.utils import hh_historico_data as hh
except ImportError:
    from utils import hh_data as hd
    from utils import hh_historico_data as hh

META_ADERENCIA = 70          # linha de referência (BR-06)
MIN_SEMANAS_VIEW = 12        # slots mínimos no eixo (reserva espaço p/ barras não esticarem)
C1, C2, C3, C4 = "#2f4bd8", "#12a594", "#d98a15", "#8b5cf6"
AZUL_APP = "#08137C"
COR_MOTIVOS = [C1, C2, C3, C4, "#e5484d", "#7d879b", "#12a594"]
# cores/rótulos das disciplinas (BR-16) — paleta da MARCA do cliente (marca · marca),
# validada pelo dataviz (CVD-safe, ΔE≥19 em modo claro). Consistentes nos 4 gráficos do grupo.
# Elétrica = laranja marca · Mecânica = azul marca · Terceiros = teal do círculo marca
# · Outras = cinza neutro (saco de resto, não uma disciplina de comparação).
DISC_COR = {"Eletrica": "#E8622A", "Mecanica": "#175FA6", "Terceiros": "#0E9C8A", "Outras": "#9AA4B2"}
DISC_LABEL = {"Eletrica": "Elétrica", "Mecanica": "Mecânica", "Terceiros": "Terceiros", "Outras": "Outras"}
# acento de marca (gradiente marca→marca) — usado como filete no topo do grupo
MARCA_GRAD = "linear-gradient(90deg, #E8622A 0%, #175FA6 60%, #0E9C8A 100%)"
# capacidade (BR-19/20): Disponível total = fundo neutro (teto) · Planejado = empilhado por turno,
# rampa de azul marca (claro→escuro = A→C); lê como "planejado, decomposto por turno".
COR_DISP = "#CBD2DA"
TURNO_COR = {"A": "#7FB1DD", "B": "#2E74B5", "C": "#134A7C"}


def _turno_label(turno: str, disp_map: dict | None) -> str:
    """Rótulo do turno sem sigla crua (BR-20): 'Turno A · 6h' etc; 'Administrativo' p/ ADM."""
    if turno == "ADM":
        return "Administrativo"
    m = (disp_map or {}).get(turno)
    return f"Turno {turno} · {int(m) // 60}h" if m else f"Turno {turno}"
# cores semânticas do estado do backlog (BR-12)
STATUS_COR = {"Aberta": "#e5484d", "Em Tratamento": "#3e63dd", "Em Pausa": "#d98a15",
              "Aceitação de Espera": "#7d879b", "Encerrada": "#2f9e63", "Cancelada": "#8b5cf6"}
MODOS = [
    {"label": "Semana fechada × anterior", "value": "fechada"},
    {"label": "Week-to-date", "value": "wtd"},
    {"label": "Média de N semanas", "value": "media"},
]


def _wlabel(semana: str) -> str:
    return "W" + semana.split("-W")[1]


def _by_week(serie, key):
    return {r["semana"]: r.get(key) for r in serie}


def _shift(w, d):
    return hd.semana_shift(w, d)


# ---- modos de comparação (BR-04/BR-05) ------------------------------------------------

def _dow_frac() -> float:
    """Fração do dia-da-semana de hoje (segunda=1/7 … domingo=7/7) — escala week-to-date (BR-05)."""
    return hd._agora_brt().isoweekday() / 7.0


def _calc(mapa, modo, n, *, ratio=False, acumula=True):
    """(valor, referência, rótulo) de uma métrica no modo escolhido. `mapa`={semana:valor}.
    `acumula`=True → métrica que enche ao longo da semana (escala no week-to-date); carry-over=False."""
    atual = hd.semana_atual()
    fechada = _shift(atual, -1)
    if modo == "wtd":
        cur = mapa.get(atual)
        r = mapa.get(fechada)
        ref = r if (ratio or not acumula or r is None) else round(r * _dow_frac(), 1)
        return cur, ref, f"{_wlabel(atual)} até hoje"
    if modo == "media":
        cur = mapa.get(fechada)
        win = [mapa.get(_shift(fechada, -i)) for i in range(1, int(n or 8) + 1)]
        win = [x for x in win if x is not None]
        ref = round(sum(win) / len(win), 1) if win else None
        return cur, ref, f"{_wlabel(fechada)} · média {n}"
    cur = mapa.get(fechada)
    return cur, mapa.get(_shift(fechada, -1)), f"{_wlabel(fechada)} fechada"


def _band_idx(weeks, modo, n):
    """Índices (i0, i1) das semanas que o modo usa como base, p/ a faixa de referência. None se fora."""
    atual = hd.semana_atual()
    fechada = _shift(atual, -1)
    def idx(w):
        return weeks.index(w) if w in weeks else None
    if modo == "wtd":
        i = idx(atual)
        return (i, i) if i is not None else None
    if modo == "media":
        fim = idx(fechada)
        if fim is None:
            return None
        ini = max(0, fim - int(n or 8))
        return (ini, fim - 1) if fim - 1 >= ini else None
    i = idx(fechada)
    return (i, i) if i is not None else None


# ---- cards ----------------------------------------------------------------------------

def _delta(cur, ref, good_up, suffix):
    if cur is None or ref is None:
        return None, "text-muted"
    dv = round(cur - ref, 1)
    if dv == 0:
        return f"→ 0{suffix}", "text-muted"
    subiu = dv > 0
    cls = "text-success" if (subiu == good_up) else "text-danger"
    return f"{'▲' if subiu else '▼'} {abs(dv)}{suffix}", cls


def _card(label, cur, ref, head, good_up, suffix=""):
    val = "—" if cur is None else f"{cur}{suffix}"
    dtxt, dcls = _delta(cur, ref, good_up, suffix)
    corpo = [html.Div(label, className="text-uppercase text-muted small fw-bold"),
             html.Div(val, className="fs-3 fw-bold lh-1 mt-1")]
    if dtxt:
        corpo.append(html.Div(dtxt, className=f"small fw-bold mt-1 {dcls}"))
    corpo.append(html.Div(head, className="text-muted mt-1", style={"fontSize": ".7rem"}))
    return dbc.Card(dbc.CardBody(corpo, className="py-2 px-3"), className="h-100 shadow-sm")


def _card_pendente(label, nota):
    return dbc.Card(dbc.CardBody([
        html.Div(label, className="text-uppercase text-muted small fw-bold"),
        html.Div("—", className="fs-3 fw-bold lh-1 mt-1 text-muted"),
        html.Div(nota, className="text-muted mt-1", style={"fontSize": ".7rem"}),
    ], className="py-2 px-3"), className="h-100 shadow-sm")


def _cards_row(fluxo, replan, ader, fora, modo, n):
    a, e, c = _by_week(fluxo, "atribuidas"), _by_week(fluxo, "entregues"), _by_week(fluxo, "carry_over")
    ad = _by_week(ader, "aderencia_pct")
    rep = {r["semana"]: sum(r["motivos"].values()) for r in replan}
    forah = _by_week(fora, "horas")
    especs = [
        ("Atribuídas", a, True, "", True),
        ("Entregues", e, True, "", True),
        ("Carry-over", c, False, "", False),   # carry-over não escala no wtd
        ("Replanejamentos", rep, False, "", True),
        ("Aderência", ad, True, "%", True),
        ("Trabalho fora do plano", forah, False, " h", True),
    ]
    cards = []
    for label, mapa, good_up, suf, acumula in especs:
        cur, ref, head = _calc(mapa, modo, n, ratio=(suf == "%"), acumula=acumula)
        cards.append(_card(label, cur, ref, head, good_up, suf))
    return dbc.Row([dbc.Col(k, xs=6, md=4, lg=2, className="mb-2") for k in cards], className="g-2")


# ---- gráficos -------------------------------------------------------------------------

def _layout_base(fig, h=260):
    fig.update_layout(height=h, margin=dict(l=8, r=8, t=8, b=28),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, font=dict(size=11)),
                      font=dict(size=11), bargap=0.25)
    fig.update_yaxes(gridcolor="rgba(128,128,128,.18)", zeroline=False)
    fig.update_xaxes(showgrid=False)
    return fig


def _graph(fig, graph_id=None):
    kw = {"id": graph_id} if graph_id else {}
    return dcc.Graph(figure=fig, config={"displayModeBar": False}, style={"width": "100%"}, **kw)


def _graph_h(fig, h):
    """Como `_graph`, mas com altura FIXA em px no container. Necessário dentro de `dbc.Col`/`dbc.Row`
    (flexbox): sem altura explícita, o Plotly ignora `layout.height` e estica a coluna sem limite."""
    return dcc.Graph(figure=fig, config={"displayModeBar": False},
                     style={"width": "100%", "height": f"{h}px"})


def _add_band(fig, band):
    if band is None:
        return
    i0, i1 = band
    fig.add_vrect(x0=i0 - 0.5, x1=i1 + 0.5, fillcolor=AZUL_APP, opacity=0.08,
                  line_width=0, layer="below")


def _opac(weeks, partial_w):
    """Lista de opacidade por semana — a semana parcial (atual) vem apagada (BR-05)."""
    return [0.42 if w == partial_w else 1.0 for w in weeks]


def _fig_grouped(weeks, series, partial_w, band, graph_id=None):
    labels = [_wlabel(w) for w in weeks]
    op = _opac(weeks, partial_w)
    fig = go.Figure()
    for nome, dados, cor in series:
        fig.add_bar(x=labels, y=list(dados), name=nome,
                    marker=dict(color=cor, opacity=op))
    fig.update_layout(barmode="group")
    _add_band(fig, band)
    return _graph(_layout_base(fig), graph_id=graph_id)


def _fig_stacked_motivos(weeks, replan, partial_w, band):
    labels = [_wlabel(w) for w in weeks]
    op = _opac(weeks, partial_w)
    motivos = []
    for r in replan:
        for m in r["motivos"]:
            if m not in motivos:
                motivos.append(m)
    rep_by = {r["semana"]: r["motivos"] for r in replan}
    fig = go.Figure()
    for i, m in enumerate(motivos):
        fig.add_bar(x=labels, y=[rep_by.get(w, {}).get(m, 0) for w in weeks], name=m,
                    marker=dict(color=COR_MOTIVOS[i % len(COR_MOTIVOS)], opacity=op))
    fig.update_layout(barmode="stack")
    _add_band(fig, band)
    return _graph(_layout_base(fig))


def _fig_ader_disc(weeks, por_disc, partial_w, band):
    """Aderência POR DISCIPLINA ao longo das semanas — uma linha por disciplina (cor da marca);
    buraco onde a disciplina não teve entrega na semana (BR-18). Linha de meta de referência."""
    labels = [_wlabel(w) for w in weeks]
    sizes = [9 if w == partial_w else 6 for w in weeks]
    fig = go.Figure()
    for b in hh.DISC_BUCKETS:
        fig.add_scatter(x=labels, y=[por_disc[w][b]["aderencia_pct"] for w in weeks],
                        mode="lines+markers", name=DISC_LABEL[b], connectgaps=False,
                        line=dict(color=DISC_COR[b], width=2.2, shape="spline"),
                        marker=dict(size=sizes, line=dict(color="#ffffff", width=1.2)),
                        hovertemplate="%{x} · " + DISC_LABEL[b] + "<br>%{y}%<extra></extra>")
    fig.add_hline(y=META_ADERENCIA, line_dash="dash", line_color="#7d879b", opacity=0.6,
                  annotation_text=f"meta {META_ADERENCIA}%", annotation_position="top left")
    fig.update_yaxes(ticksuffix="%")
    _add_band(fig, band)
    return _graph(_layout_base(fig, h=250))


def _fig_backlog_status(weeks, serie, partial_w, band):
    """Estado do backlog empilhado por situação (Fase 2). Vazio nas semanas sem captura."""
    labels = [_wlabel(w) for w in weeks]
    by = {r["semana"]: r["status"] for r in serie}
    presentes = [s for s in hh.STATUS_ORDEM if any(by.get(w, {}).get(s) for w in weeks)]
    for w in weeks:                       # status fora do padrão (raro) vão pro fim
        for s in by.get(w, {}):
            if s not in presentes:
                presentes.append(s)
    op = _opac(weeks, partial_w)
    fig = go.Figure()
    for s in presentes:
        fig.add_bar(x=labels, y=[by.get(w, {}).get(s, 0) for w in weeks], name=s,
                    marker=dict(color=STATUS_COR.get(s, "#7d879b"), opacity=op))
    fig.update_layout(barmode="stack")
    _add_band(fig, band)
    if not presentes:                     # nenhuma captura ainda
        fig.add_annotation(text="Sem captura ainda — a série começa a partir do deploy.",
                           showarrow=False, xref="paper", yref="paper", x=0.5, y=0.5,
                           font=dict(color="#7d879b"))
    return _graph(_layout_base(fig))


def _fig_fora(weeks, serie, partial_w, band):
    """Trabalho fora do plano por semana (horas; ordens no hover). Fase 2 — vazio até a captura."""
    labels = [_wlabel(w) for w in weeks]
    horas = [r.get("horas") or 0 for r in serie]
    ordens = [r.get("ordens") or 0 for r in serie]
    op = _opac(weeks, partial_w)
    fig = go.Figure()
    fig.add_bar(x=labels, y=horas, name="Horas fora do plano",
                marker=dict(color=C3, opacity=op), customdata=ordens,
                hovertemplate="%{x}<br>%{y} h · %{customdata} ordens<extra></extra>")
    _add_band(fig, band)
    if not any(horas):
        fig.add_annotation(text="Sem captura ainda — a série começa a partir do deploy.",
                           showarrow=False, xref="paper", yref="paper", x=0.5, y=0.5,
                           font=dict(color="#7d879b"))
    return _graph(_layout_base(fig, h=230))


# ---- capacidade × planejado (BR-19/20) ------------------------------------------------

def _fig_cap_combo(serie, weeks, disp_map, partial_w, band):
    """Um gráfico só: por semana, 2 barras lado a lado — Disponível TOTAL (barra neutra) e Planejado
    EMPILHADO por turno (A/B/C). grouped+stacked via offsetgroup (disp | plan) + barmode='stack'.
    Escala bem com o nº de semanas."""
    by = {r["semana"]: r for r in serie}
    labels = [_wlabel(w) for w in weeks]
    op = _opac(weeks, partial_w)
    turnos = sorted({t for r in serie for t in r.get("por_turno", {})})   # A, B, C
    fig = go.Figure()
    # barra 1 — Disponível total (offsetgroup próprio → fica ao lado do planejado)
    fig.add_bar(x=labels, y=[by.get(w, {}).get("disponivel_h", 0) for w in weeks],
                name="Disponível total", offsetgroup="disp", legendgroup="disp",
                marker=dict(color=COR_DISP, opacity=op, cornerradius=4),
                hovertemplate="%{x}<br>Disponível total %{y} h<extra></extra>")
    # barra 2 — Planejado empilhado por turno (mesmo offsetgroup → empilha entre si)
    for t in turnos:
        y = [by.get(w, {}).get("por_turno", {}).get(t, {}).get("planejado_h", 0) for w in weeks]
        fig.add_bar(x=labels, y=y, name=_turno_label(t, disp_map),
                    offsetgroup="plan", legendgroup="plan",
                    marker=dict(color=TURNO_COR.get(t, "#9AA4B2"), opacity=op,
                                line=dict(color="#ffffff", width=1)),
                    hovertemplate="%{x} · " + _turno_label(t, disp_map) +
                                  "<br>Planejado %{y} h<extra></extra>")
    fig.update_layout(barmode="stack", bargap=0.34, legend=dict(traceorder="normal"))
    _add_band(fig, band)
    return _graph_h(_layout_base(fig, h=300), 300)


def _grade_capacidade(serie, weeks, disp_map, partial_w, band):
    """Grupo 'Capacidade × planejado': um gráfico — Disponível total × Planejado empilhado por turno."""
    return html.Div([
        html.Div(style={"height": "3px", "borderRadius": "2px", "background": MARCA_GRAD}, className="mb-3"),
        html.Div("Disponível total × planejado por turno", className="text-uppercase text-muted fw-bold mb-1",
                 style={"fontSize": ".68rem", "letterSpacing": ".05em"}),
        _fig_cap_combo(serie, weeks, disp_map, partial_w, band),
    ])


# ---- insights -------------------------------------------------------------------------

def _insights(eternas, motivos, janela):
    if eternas:
        linhas_e = [html.Div([
            html.Div([
                html.Span(e["ordem"], className="fw-bold"),
                html.Span(f" · {e.get('disciplina') or '—'}", className="text-muted"),
                dbc.Badge(f"{e['semanas_consec']} sem", color="warning", className="float-end"),
            ]),
            html.Div(e.get("linha") or "—", className="text-truncate",
                     style={"fontSize": ".72rem"}, title=e.get("linha") or ""),
            html.Div(e.get("descricao") or "—", className="text-muted text-truncate",
                     style={"fontSize": ".72rem"}, title=e.get("descricao") or ""),
        ], className="border rounded px-2 py-1 mb-1 small") for e in eternas]
    else:
        linhas_e = [html.Div("Nenhuma ordem em arrasto crônico (3+ semanas).", className="text-muted small")]
    if motivos:
        mx = max(m["total"] for m in motivos) or 1
        linhas_m = []
        for i, m in enumerate(motivos):
            linhas_m.append(html.Div([
                html.Div([html.Span(m["motivo"]), html.Span(m["total"], className="float-end fw-bold")],
                         className="small d-flex justify-content-between"),
                html.Div(html.Div(style={"width": f"{100*m['total']/mx}%", "height": "6px",
                                         "background": COR_MOTIVOS[i % len(COR_MOTIVOS)], "borderRadius": "3px"}),
                         className="mb-2", style={"background": "rgba(128,128,128,.15)", "borderRadius": "3px"}),
            ]))
    else:
        linhas_m = [html.Div("Sem replanejamentos na janela.", className="text-muted small")]
    return dbc.Row([
        dbc.Col([html.H6("Carry-over crônico", className="fw-bold"),
                 html.P("Ordens que arrastam 3+ semanas seguidas sem cumprir o plano — as “eternas”.",
                        className="text-muted small"), *linhas_e], md=6),
        dbc.Col([
            html.Div([
                html.H6("Top motivos de replanejamento", className="fw-bold mb-0"),
                dbc.Button("Ver detalhe →", id="hist-replan-btn", size="sm", color="link",
                           className="p-0 small"),
            ], className="d-flex justify-content-between align-items-center"),
            html.P(f"Acumulado das últimas {janela} semanas.", className="text-muted small"),
            *linhas_m], md=6),
    ])


def _grupo(titulo, desc, corpo):
    return dbc.AccordionItem([html.P(desc, className="text-muted small mb-2"), corpo],
                             title=titulo, item_id=titulo)


# ---- painel reativo (reconstruído pelo callback) --------------------------------------

def build_painel(d_ini, d_fim, modo, n, janela):
    """Monta cards + gráficos + insights para o período e modo escolhidos. Chamado pelo callback."""
    modo = modo or "fechada"
    janela = max(1, min(52, int(janela or hh.INSIGHTS_JANELA_DEFAULT)))
    sem_ini = hd.iso_semana(datetime.fromisoformat(d_ini)) if d_ini else hd.semana_shift(hd.semana_atual(), -11)
    sem_fim = hd.iso_semana(datetime.fromisoformat(d_fim)) if d_fim else hd.semana_atual()
    weeks = hh._semanas_entre(sem_ini, sem_fim)
    if not weeks:
        return dbc.Alert("Período inválido — a data inicial é depois da final.", color="warning")
    # Layout padronizado: mínimo de 12 slots de semana. Com menos, reserva slots vazios à ESQUERDA
    # (semanas ISO anteriores a sem_ini, sem dado nesta fase) e alinha as reais à direita — barras
    # com largura constante, sem estica feia. Só afeta o eixo; as séries retornam vazio nesses slots.
    if len(weeks) < MIN_SEMANAS_VIEW:
        w = weeks[0]
        pad = []
        for _ in range(MIN_SEMANAS_VIEW - len(weeks)):
            w = hd.semana_shift(w, -1)
            pad.append(w)
        weeks = list(reversed(pad)) + weeks

    # Performance (SP-06.2): carrega cada collection UMA vez e reusa nos núcleos puros — evita
    # recarregar hh_planejamento 4× / hh_replanejamentos 2× por render.
    atrib_docs = hh._load_atrib_docs()
    replan_docs = hh._load_replan_docs()
    ref = hd.semana_atual()
    fluxo = hh._compute_fluxo(atrib_docs, weeks)
    hh_serie = hh._compute_hh(atrib_docs, weeks)
    ader = hh._compute_aderencia(atrib_docs, weeks)
    por_disc = hh._compute_por_disc(atrib_docs, weeks)   # aderência por disciplina (grupo "Aderência média")
    replan = hh._compute_replanejamentos(replan_docs, weeks)
    eternas = hh._compute_eternas(atrib_docs, ref, janela, info_map=hh._mapa_ordem_info())
    motivos = hh._compute_top_motivos(replan_docs, ref, janela)
    cap_serie = hh.serie_capacidade(sem_ini, sem_fim)    # BR-19/20
    disp_map = (hd.carregar_config_capacidade() or {}).get("disponivel_min")
    fora = hh.serie_fora_do_plano(sem_ini, sem_fim)
    backlog = hh.serie_backlog_status(sem_ini, sem_fim)

    atual = hd.semana_atual()
    partial_w = atual if atual in weeks else None
    band = _band_idx(weeks, modo, n)

    fig_fluxo = _fig_grouped(weeks, [
        ("Atribuídas", [r["atribuidas"] for r in fluxo], C1),
        ("Entregues", [r["entregues"] for r in fluxo], C2),
        ("Carry-over", [r["carry_over"] for r in fluxo], C3),
    ], partial_w, band, graph_id="hist-fluxo-graph")
    fig_hh = _fig_grouped(weeks, [
        ("Planejado (h)", [r["planejado_h"] for r in hh_serie], C1),
        ("Realizado (h)", [r["realizado_h"] for r in hh_serie], C2),
    ], partial_w, band)

    aviso = (html.Div([html.Span("▨ ", className="text-muted"),
                       f"{_wlabel(partial_w)} = semana atual, parcial — fora do headline no modo fechada."],
                      className="text-muted small mb-2") if partial_w else None)

    return html.Div([
        dcc.Store(id="hist-weeks", data=weeks),   # label clicado → semana ISO (modal de detalhe)
        _cards_row(fluxo, replan, ader, fora, modo, n),
        aviso,
        dbc.Accordion([
            _grupo("Fluxo do plano",
                   "Atribuídas × entregues × carry-over por semana — clique numa semana p/ o detalhe "
                   "por disciplina.", fig_fluxo),
            _grupo("Replanejamentos",
                   "Volume por semana e por motivo (empurrar + cancelar) — onde o plano falha.",
                   _fig_stacked_motivos(weeks, replan, partial_w, band)),
            _grupo("Hora-Homem: planejado × realizado",
                   "Horas planejadas e executadas por semana, das ordens entregues.", fig_hh),
            _grupo("Aderência média",
                   "Realizado ÷ planejado das ordens entregues (%), ponderado por horas — por "
                   "disciplina ao longo das semanas.",
                   _fig_ader_disc(weeks, por_disc, partial_w, band)),
            _grupo("Capacidade × planejado",
                   "Horas disponíveis (líquidas de folga) × horas planejadas por semana, no total e "
                   "por turno. Retroativo aproximado (roster atual; folgas datadas).",
                   _grade_capacidade(cap_serie, weeks, disp_map, partial_w, band)),
            _grupo("Trabalho fora do plano",
                   "Ordens com hora realizada sem estar no quadro da semana (captura a partir do deploy).",
                   _fig_fora(weeks, fora, partial_w, band)),
            _grupo("Estado do backlog ao longo do tempo",
                   "Aberta · Em tratamento · Em pausa · Aceitação · Encerrada (captura a partir do deploy).",
                   _fig_backlog_status(weeks, backlog, partial_w, band)),
            _grupo("Insights", "Carry-over crônico e principais motivos de replanejamento.",
                   _insights(eternas, motivos, janela)),
        ], id="hist-accordion", always_open=True, className="fa-a3-accordion",  # visual de marca (Análise de Falhas)
           active_item=["Fluxo do plano", "Capacidade × planejado", "Replanejamentos", "Insights"],
           persistence=True, persistence_type="local", persisted_props=["active_item"]),
    ])


# ---- barra de controles + corpo da aba ------------------------------------------------

def _control_bar(d_ini, d_fim, janela):
    """Filtro de período (BR-11) + modo de comparação (BR-04) + N + janela de insights (BR-13)."""
    return dbc.Card(dbc.CardBody(dbc.Row([
        dbc.Col([dbc.Label("Período", className="small fw-bold mb-1 d-block"),
                 dcc.DatePickerRange(id="hist-periodo", start_date=d_ini, end_date=d_fim,
                                     display_format="DD/MM/YY", first_day_of_week=1,
                                     minimum_nights=0, className="d-block v2-date-range-inline")],
                width="auto", style={"minWidth": "260px"}),
        dbc.Col([dbc.Label("Comparar", className="small fw-bold mb-1 d-block"),
                 dbc.RadioItems(id="hist-modo", options=MODOS, value="fechada", inline=True,
                                className="small")], width="auto"),
        dbc.Col([dbc.Label("N (média)", className="small fw-bold mb-1 d-block"),
                 dcc.Dropdown(id="hist-n", options=[{"label": str(x), "value": x} for x in (4, 8, 12)],
                              value=8, clearable=False, style={"width": "90px"})], width="auto"),
        dbc.Col([dbc.Label("Insights (semanas)", className="small fw-bold mb-1 d-block"),
                 dbc.Input(id="hist-insights-janela", type="number", min=1, max=52, step=1,
                           value=janela, style={"width": "90px"})], width="auto"),
    ], className="g-3 align-items-end"), className="py-2 px-2"), className="mb-3 shadow-sm")


def hist_body():
    """Corpo da aba (Bloco D): cabeçalho + controles + painel reativo (`hist-painel`)."""
    prim = hh.primeira_semana() or hd.semana_shift(hd.semana_atual(), -11)
    d_ini = hd.inicio_da_semana(prim).date().isoformat()
    d_fim = hd.inicio_da_semana(hd.semana_atual()).date().isoformat()
    janela = hh.carregar_insights_janela()
    return html.Div([
        html.Div([
            html.H5("Histórico semanal", className="fw-bold mb-0"),
            html.Small("Tendência das semanas — plano, entregas, replanejamentos e aderência.",
                       className="text-muted"),
        ], className="mb-3"),
        _control_bar(d_ini, d_fim, janela),
        dcc.Store(id="hist-insights-saved"),
        dcc.Loading(html.Div(id="hist-painel"), type="default"),
        _replan_modal(),
        _semana_modal(),
    ])


# ---- modal de detalhe dos replanejamentos (drill-down do Top motivos, BR-13) ----------

def _replan_modal():
    """Modal (vazio até abrir) com a tabela que compõe o Top motivos — o callback popula o corpo."""
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Detalhe dos replanejamentos")),
        dbc.ModalBody(html.Div(id="hist-replan-modal-body")),
    ], id="hist-replan-modal", size="xl", scrollable=True, is_open=False)


# ---- modal de detalhe da semana (clique no Fluxo) → mini-gráficos por disciplina --------

def _semana_modal():
    """Modal (vazio até clicar numa semana no Fluxo). Abre NA HORA no clique; o `dcc.Loading` mostra
    spinner enquanto o corpo é montado (2 callbacks: abrir+guardar semana, depois preencher)."""
    return html.Div([
        dcc.Store(id="hist-semana-sel"),
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Detalhe da semana")),
            dbc.ModalBody(dcc.Loading(html.Div(id="hist-semana-modal-body"), type="default")),
        ], id="hist-semana-modal", size="xl", scrollable=True, is_open=False),
    ])


def _stat(label, valor):
    return dbc.Col(html.Div([
        html.Div(label, className="text-uppercase text-muted fw-bold", style={"fontSize": ".62rem"}),
        html.Div(valor, className="fs-5 fw-bold lh-1"),
    ]), xs=6, md="auto")


def _mini_disc(titulo, por_disc, campo, tipo):
    """Mini-gráfico por disciplina: `tipo`='donut' (rosca de contagem), 'bar' (barras de contagem)
    ou 'aderencia' (barras % + linha de meta; disciplina sem entrega = sem barra). Cores da marca."""
    labels = [DISC_LABEL[b] for b in hh.DISC_BUCKETS]
    vals = [por_disc[b][campo] for b in hh.DISC_BUCKETS]
    cores = [DISC_COR[b] for b in hh.DISC_BUCKETS]
    if tipo == "donut":
        fig = go.Figure(go.Pie(labels=labels, values=vals, marker=dict(colors=cores),
                               hole=0.58, sort=False, direction="clockwise",
                               texttemplate="%{value}", textposition="inside",
                               hovertemplate="%{label}: %{value} (%{percent})<extra></extra>"))
        fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.08, font=dict(size=10)),
                          margin=dict(l=6, r=6, t=8, b=6))
    elif tipo == "aderencia":
        txt = [f"{v}%" if v is not None else "" for v in vals]
        fig = go.Figure(go.Bar(x=labels, y=vals, marker=dict(color=cores, cornerradius=4),
                               text=txt, textposition="outside", cliponaxis=False,
                               textfont=dict(size=11), hovertemplate="%{x}: %{y}%<extra></extra>"))
        fig.add_hline(y=META_ADERENCIA, line_dash="dash", line_color="#7d879b", opacity=0.6,
                      annotation_text=f"meta {META_ADERENCIA}%", annotation_position="top left",
                      annotation_font_size=9)
        fig.update_layout(showlegend=False, margin=dict(l=6, r=6, t=26, b=6))
        vmax = max([v for v in vals if v is not None] or [META_ADERENCIA])
        fig.update_yaxes(ticksuffix="%", showgrid=False, range=[0, vmax * 1.22])
    else:
        fig = go.Figure(go.Bar(x=labels, y=vals, marker=dict(color=cores, cornerradius=4),
                               text=vals, textposition="outside", cliponaxis=False,
                               textfont=dict(size=11), hovertemplate="%{x}: %{y}<extra></extra>"))
        fig.update_layout(showlegend=False, margin=dict(l=6, r=6, t=26, b=6))  # topo folgado p/ o rótulo
        # headroom no eixo p/ o número acima da barra não ser cortado
        fig.update_yaxes(visible=False, range=[0, (max(vals) or 1) * 1.22])
    fig.update_layout(height=240, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(size=11))
    return dbc.Card(dbc.CardBody([
        html.Div(titulo, className="text-uppercase text-muted fw-bold mb-1",
                 style={"fontSize": ".68rem", "letterSpacing": ".05em"}),
        _graph_h(fig, 240),
    ], className="p-2"), className="h-100 shadow-sm")


def _mini_entregues(por_disc):
    """Entregues por disciplina DISTINGUINDO a origem (BR-07/BR-22): 'No plano' (planejada e fechada
    na mesma semana) × 'Carry-over' (planejada antes, fechou agora) × 'Fora do plano' (fechou sem
    nunca ter sido planejada — só aparece quando existe). Stack por categoria, cores semânticas."""
    labels = [DISC_LABEL[b] for b in hh.DISC_BUCKETS]
    plano = [por_disc[b]["entregues_plano"] for b in hh.DISC_BUCKETS]
    carry = [por_disc[b]["entregues_carry"] for b in hh.DISC_BUCKETS]
    fora = [por_disc[b]["entregues_fora"] for b in hh.DISC_BUCKETS]
    fig = go.Figure()
    fig.add_bar(x=labels, y=plano, name="No plano", marker=dict(color="#2f9e63", cornerradius=3),
                hovertemplate="%{x} · No plano: %{y}<extra></extra>")
    fig.add_bar(x=labels, y=carry, name="Carry-over (atrasada)", marker=dict(color="#d98a15", cornerradius=3),
                hovertemplate="%{x} · Carry-over: %{y}<extra></extra>")
    if sum(fora):   # só mostra a categoria quando ela existe (extensível)
        fig.add_bar(x=labels, y=fora, name="Fora do plano", marker=dict(color="#e5484d", cornerradius=3),
                    hovertemplate="%{x} · Fora do plano: %{y}<extra></extra>")
    fig.update_layout(barmode="stack", showlegend=True, height=240,
                      legend=dict(orientation="h", y=-0.12, font=dict(size=10)),
                      margin=dict(l=6, r=6, t=8, b=6), font=dict(size=11),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    fig.update_yaxes(visible=False)
    return dbc.Card(dbc.CardBody([
        html.Div("Entregues por disciplina · no plano × carry-over",
                 className="text-uppercase text-muted fw-bold mb-1",
                 style={"fontSize": ".68rem", "letterSpacing": ".05em"}),
        _graph_h(fig, 240),
    ], className="p-2"), className="h-100 shadow-sm")


def _semana_modal_body(det):
    """Corpo do modal da semana: cabeçalho + resumo + rosca de atribuídas e barras de entregues,
    ambas por disciplina (BR-16). `det` = saída de `hh.detalhe_semana`."""
    sem = det["semana"]
    datas = hd.datas_da_semana(sem)
    periodo = f"{datas[0].strftime('%d')}–{datas[6].strftime('%d/%m')}"
    f, hhs, ad = det["fluxo"], det["hh"], det["aderencia_pct"]
    return html.Div([
        html.Div([
            html.Span(_wlabel(sem), className="h5 fw-bold me-2"),
            html.Span(periodo, className="text-muted"),
        ], className="mb-2"),
        dbc.Row([
            _stat("Atribuídas", f["atribuidas"]),
            _stat("Entregues", f["entregues"]),
            _stat("Carry-over", f["carry_over"]),
            _stat("Aderência", f"{ad}%" if ad is not None else "—"),
            _stat("HH plan/real", f"{hhs['planejado_h']}/{hhs['realizado_h']} h"),
        ], className="g-3 mb-2"),
        html.Div(style={"height": "3px", "borderRadius": "2px", "background": MARCA_GRAD}, className="mb-3"),
        dbc.Row([
            dbc.Col(_mini_disc("Atribuídas por disciplina", det["por_disc"], "atribuidas", "donut"), md=6),
            dbc.Col(_mini_entregues(det["por_disc"]), md=6),
        ], className="g-3 mb-3"),
        dbc.Row([
            dbc.Col(_mini_disc("Carry-over por disciplina", det["por_disc"], "carry_over", "bar"), md=6),
            dbc.Col(_mini_disc("Aderência por disciplina", det["por_disc"], "aderencia_pct", "aderencia"), md=6),
        ], className="g-3"),
    ])


def _replan_detalhe_body(rows, motivos, motivo_sel):
    """Corpo do modal: filtro por motivo + tabela. `motivos` = [(motivo, total)]."""
    opts = [{"label": "Todos os motivos", "value": "__all"}]
    opts += [{"label": f"{m} ({n})", "value": m} for m, n in motivos]
    return html.Div([
        dbc.Row([
            dbc.Col(dcc.Dropdown(id="hist-replan-motivo", options=opts, value=motivo_sel or "__all",
                                 clearable=False), md=7),
        ], className="mb-2 g-2"),
        html.Div(_replan_table(rows), id="hist-replan-table"),
    ])


def _replan_table(rows):
    """Tabela dos registros de replanejamento (Semana · Ordem · Descrição · Tipo · Motivo ·
    Observação · Quem · Quando). O `texto` (observação livre) é o 'porquê' — chave p/ 'Outro'."""
    if not rows:
        return html.Div("Sem replanejamentos nessa seleção.", className="text-muted p-2")
    cols = ["Semana", "Ordem", "Descrição", "Tipo", "Motivo", "Observação", "Quem", "Quando"]
    head = html.Thead(html.Tr([html.Th(c) for c in cols]))
    linhas = []
    for r in rows:
        tipo = {"remover": "Cancelada", "mover_semana": "Empurrada"}.get(r["tipo"], r["tipo"])
        quando = r["em"].strftime("%d/%m/%y %H:%M") if r.get("em") else "—"
        linhas.append(html.Tr([
            html.Td(_wlabel(r["semana"]) if r["semana"] else "—"),
            html.Td(r["ordem"]),
            html.Td(r["descricao"] or "—", className="small"),
            html.Td(tipo),
            html.Td(r["categoria"]),
            html.Td(r["texto"] or "—", className="small"),
            html.Td(r["por"] or "—", className="small"),
            html.Td(quando, className="small text-nowrap"),
        ]))
    return html.Div([
        html.Div(f"{len(rows)} registro(s)", className="text-muted small mb-1"),
        dbc.Table([head, html.Tbody(linhas)], striped=True, hover=True, size="sm", responsive=True),
    ])


def hist_tab():
    """A `dbc.Tab` do Histórico Semanal — contêiner lazy (preenchido pelo callback na ativação)."""
    return dbc.Tab(html.Div(id="hist-content", className="py-2"),
                   label="Histórico Semanal", tab_id="tab-historico")


def hist_placeholder():
    """Fallback simples (Mongo indisponível)."""
    return dbc.Alert("Histórico Semanal indisponível no momento (sem conexão com o banco).",
                     color="light", className="border mb-0")
