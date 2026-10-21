# src/pages/dashboards/home.py
#
# Visão Geral da Manutenção — home de CONFRONTO (barras divergentes do centro).
# Cada métrica é um par de barras que crescem a partir de um eixo central:
# período anterior (esq) vs período atual (dir). Comprimento = valor real
# (normalizado ao maior dos dois); cor por valência (lado melhor verde, pior
# vermelho). Design system reusado da V2 (indicator-v2-card, v2-lang-flag).
#
# 3 granularidades de comparação (todas "até hoje", janela equivalente):
#   • month — mês até hoje (dia 1…D) vs mesmo intervalo do mês passado (clampa o dia)
#   • week  — semana ISO até hoje vs semana anterior (mesmos dias da semana)
#   • band  — faixa de dias do mês (mês dividido em N faixas, N = nº de semanas)
#             vs mesma faixa por número de dia no mês passado (problema só no último corte)
#
# DADOS REAIS — todas as métricas vêm de ZPP_Producao / ZPP_Paradas via o pipeline
# canônico V1 (fetch_zpp_production_data + fetch_zpp_breakdown_data), respeitando
# BR-04 (BREAKDOWN_CODES), BR-05 (month boundary 'fim'), BR-11 (totais brutos) e
# BR-12 (janela [start,end) semi-aberta). O "hoje" é ancorado na última data com
# registro (_data_anchor), não no relógio — a base ZPP é histórica.

import base64
import calendar
import datetime
import math
from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from flask_login import current_user
from src.sap_scheduler.rodape_component import build_rodape
from src.sap_scheduler.manual_trigger import build_rerun_controls

# Ordem do carrossel (present mode): 3 cortes do confronto + ROW de KPIs da V2 + Custos do mês
SLIDES = ["month", "week", "band", "kpis", "custos"]
GRAPH_SLIDES = {"kpis", "custos"}


# ============================================================
# DADOS REAIS — métricas do confronto vêm de ZPP_Producao / ZPP_Paradas
#   activity = Σ horasact (produção)          · stops = nº paradas de avaria
#   downtime = Σ duração avaria (h)            · mtbf/mttr/breakdown = BR-01/02/03
# unit + direção de melhora ("up" = maior melhor · "down" = menor melhor)
# ============================================================
METRIC_DEFS = {
    "activity":  ("h", "up"),
    "stops":     ("",  "down"),
    "downtime":  ("h", "down"),
    "mtbf":      ("h", "up"),
    "mttr":      ("min", "down"),
    "breakdown": ("%", "down"),
}

_WIN_CACHE = {}  # (start_iso, end_iso) → (ts, métricas) — TTL p/ refletir novas ingestões
_WIN_TTL = 60    # s — frescor vs perf (mesmo TTL da V2); defasagem irrelevante (ingestão diária)


def _window_metrics(start, end):
    """Busca métricas reais de uma janela [start, end) (BR-12 semi-aberta).

    Reusa o pipeline canônico V1: fetch_zpp_production_data (ffinnotif ∈ janela,
    BR-05 'fim') + fetch_zpp_breakdown_data (fim_execucao ∈ janela, BREAKDOWN_CODES).
    KPIs por BR-01/02/03 sobre os totais brutos da planta (BR-11).

    **Paridade com a Indicators-V2 (canônica):** NÃO aplica filter_force_zero_production —
    as horas dos equipamentos KPI_FORCE_ZERO (ex.: DECAP001) PERMANECEM no denominador da
    planta, exatamente como calculate_general_avg_by_month (V2/slide). Sem isto, Horas de
    Atividade / MTBF / Taxa de Avaria do telão divergiam da V2.

    Retorna: {activity, stops, downtime, mtbf, mttr, breakdown, durations}.
    Robusto a Mongo offline / janela vazia → zeros (nunca lança).
    """
    import time as _t
    key = (start.isoformat(), end.isoformat())
    cached = _WIN_CACHE.get(key)
    if cached and (_t.time() - cached[0]) < _WIN_TTL:
        return cached[1]
    out = {"activity": 0.0, "stops": 0, "downtime": 0.0,
           "mtbf": 0.0, "mttr": 0.0, "breakdown": 0.0, "durations": []}
    try:
        from src.utils.zpp_kpi_calculator import (
            fetch_zpp_production_data, fetch_zpp_breakdown_data, BREAKDOWN_CODES,
        )
        prod = fetch_zpp_production_data(start, end)  # planta inteira (inclui KPI_FORCE_ZERO)
        bd = fetch_zpp_breakdown_data(start, end, BREAKDOWN_CODES)  # já exclui DECAP001
        active_h = float(prod["horasact"].sum()) if prod is not None and not prod.empty else 0.0
        if bd is not None and not bd.empty:
            durations = [float(x) for x in bd["duracao_min"].tolist()]
            num_fail = len(durations)
            bd_min = float(sum(durations))
        else:
            durations, num_fail, bd_min = [], 0, 0.0
        bd_h = bd_min / 60.0
        if num_fail > 0 and active_h > 0:
            mtbf = (active_h - bd_h) / num_fail
            mttr = bd_min / num_fail  # MTTR em MINUTOS (convenção V1/V2)
            breakdown = (bd_h / active_h) * 100.0
        elif active_h > 0:
            mtbf, mttr, breakdown = active_h, 0.0, 0.0
        else:
            mtbf, mttr, breakdown = 0.0, 0.0, 0.0
        out = {"activity": active_h, "stops": num_fail, "downtime": bd_h,
               "mtbf": mtbf, "mttr": mttr, "breakdown": breakdown, "durations": durations}
    except Exception as e:  # Mongo offline, etc → zeros (UI não quebra)
        import logging
        logging.getLogger(__name__).warning("home _window_metrics falhou: %s", e)
    _WIN_CACHE[key] = (_t.time(), out)
    return out


_ANCHOR_CACHE = {"date": None, "ts": 0.0}


def _data_anchor():
    """'Hoje' da home = última data COM registro em ZPP_Producao (não o relógio do sistema).

    A base ZPP é histórica (pode estar atrás do calendário); ancorar no último dado
    faz o "período atual" ser sempre o mais recente com dados reais. Cache 60s.
    Fallback: datetime.date.today() se Mongo indisponível.
    """
    import time as _t
    if _ANCHOR_CACHE["date"] and (_t.time() - _ANCHOR_CACHE["ts"]) < 60:
        return _ANCHOR_CACHE["date"]
    d = None
    try:
        from src.database.connection import get_mongo_connection
        from src.utils.zpp_kpi_calculator import ZPP_PRODUCAO_COLLECTION
        col = get_mongo_connection(ZPP_PRODUCAO_COLLECTION)
        if col is not None:
            doc = col.find_one({"ffinnotif": {"$ne": None}},
                               {"ffinnotif": 1, "_id": 0}, sort=[("ffinnotif", -1)])
            v = doc.get("ffinnotif") if doc else None
            if hasattr(v, "date"):
                d = v.date()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("home _data_anchor falhou: %s", e)
    d = d or datetime.date.today()
    _ANCHOR_CACHE["date"], _ANCHOR_CACHE["ts"] = d, _t.time()
    return d


def _collect(period, lang):
    """Monta o dict do confronto (cur/prev/unit/good por métrica) + durações, com dados REAIS."""
    meta = period_meta(period, lang, today=_data_anchor())
    cur = _window_metrics(meta["cur_start"], meta["cur_end"])
    prev = _window_metrics(meta["prev_start"], meta["prev_end"])
    data = {k: {"cur": cur[k], "prev": prev[k], "unit": u, "good": g}
            for k, (u, g) in METRIC_DEFS.items()}
    data["__durations"] = cur["durations"]
    data["__durations_prev"] = prev["durations"]
    return data, meta


# Split de duração — cores de marca AMG (logo): curtas = azul Gonvarri, longas = laranja ArcelorMittal
C_SHORT = "#005687"  # azul AMG — paradas curtas
C_LONG = "#E96D38"   # laranja AMG — paradas longas

# Cores de marca AMG no confronto: lado MELHOR = azul Gonvarri, PIOR = laranja ArcelorMittal
C_GOOD = "#005687"  # azul AMG — lado melhor
C_BAD = "#E96D38"   # laranja AMG — lado pior
C_FLAT = "#6c757d"

# Operacionais — barras grandes
METRICS = [
    ("activity", "bi-activity"),
    ("stops", "bi-exclamation-octagon"),
    ("downtime", "bi-hourglass-split"),
]
# KPIs PRO017 — bloco "3-em-1" (MTBF · MTTR · Avaria)
KPIS = [
    ("mtbf", "bi-arrow-repeat"),
    ("mttr", "bi-wrench-adjustable"),
    ("breakdown", "bi-exclamation-diamond"),
]


# ============================================================
# i18n — pt / es / en
# ============================================================
_MON = {
    "pt": ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"],
    "es": ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"],
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}
_WD = {  # segunda..domingo (Mon=0)
    "pt": ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"],
    "es": ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"],
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
}

TRANS = {
    "pt": {
        "title": "Visão Geral da Manutenção",
        "subtitle": "Confronto direto: período atual vs anterior — quem está ganhando.",
        "mock_badge": "DADOS EM AUDITORIA",
        "mock_tooltip": "Dados reais do ZPP em validação — sujeitos a auditoria.",
        "btn_month": "Mês a mês", "btn_week": "Semana a semana", "btn_band": "Faixa de dias",
        "btn_present": "Apresentação", "btn_pause": "Pausar", "btn_play": "Retomar",
        "psub_month": "Mês até hoje vs mesmo dia do mês passado",
        "psub_week": "Semana até hoje vs semana anterior (mesmos dias)",
        "psub_band": "Faixa {a}/{b} do mês vs mesma faixa no mês passado",
        "now": "Atual", "prev": "Anterior", "lead": "à frente", "tie": "empate", "avg": "média",
        "ghost_label": "esperado p/ volume", "ghost_real": "descontando volume",
        "c_activity": "Horas de Atividade", "c_stops": "Paradas",
        "c_downtime": "Tempo de Parada", "c_breakdown": "Taxa de Avaria",
        "c_mtbf": "MTBF", "c_mttr": "MTTR",
        "s_activity": "Produção acumulada", "s_stops": "Ocorrências",
        "s_downtime": "Horas paradas", "s_breakdown": "% do tempo ativo em avaria",
        "s_mtbf": "Tempo médio entre falhas (h)", "s_mttr": "Tempo médio de reparo (min)",
        "kpi_section": "Indicadores de Manutenção",
        "split_title": "Paradas por duração", "split_short": "Curtas", "split_long": "Longas",
        "split_cut": "Corte", "split_help": "abaixo de {c} min = curta", "split_min": "min",
        "split_by_count": "por nº de paradas", "split_by_time": "por tempo total (min)",
        "v_up": "Operação melhorando", "v_down": "Requer atenção", "v_flat": "Operação estável",
        "v_detail": "Período atual vence em {n} de {total} indicadores",
        "fresh_title": "Atualização dos dados", "fresh_prod": "Produção", "fresh_stops": "Paradas",
        "fresh_collect": "última coleta", "fresh_through": "dado até",
        "kpi24h_section": "Indicadores — últimas 24h",
        "kpi24h_lastprod": "Último dia com produção: {d}",
        "kpi24h_bars": "Planta — últimos {n} dias",
        "costs_section": "Custo de Manutenção", "costs_month": "Mês de referência: {m}",
        "costs_rosca": "Custo por equipamento (mês)", "costs_bars": "Realizado por conta (% do orçado, mês)",
    },
    "es": {
        "title": "Visión General del Mantenimiento",
        "subtitle": "Confrontación directa: período actual vs anterior — quién está ganando.",
        "mock_badge": "DATOS EN AUDITORÍA",
        "mock_tooltip": "Datos reales del ZPP en validación — sujetos a auditoría.",
        "btn_month": "Mes a mes", "btn_week": "Semana a semana", "btn_band": "Franja de días",
        "btn_present": "Presentación", "btn_pause": "Pausar", "btn_play": "Reanudar",
        "psub_month": "Mes hasta hoy vs mismo día del mes pasado",
        "psub_week": "Semana hasta hoy vs semana anterior (mismos días)",
        "psub_band": "Franja {a}/{b} del mes vs misma franja del mes pasado",
        "now": "Actual", "prev": "Anterior", "lead": "adelante", "tie": "empate", "avg": "media",
        "ghost_label": "esperado p/ volumen", "ghost_real": "descontando volumen",
        "c_activity": "Horas de Actividad", "c_stops": "Paradas",
        "c_downtime": "Tiempo de Parada", "c_breakdown": "Tasa de Avería",
        "c_mtbf": "MTBF", "c_mttr": "MTTR",
        "s_activity": "Producción acumulada", "s_stops": "Ocurrencias",
        "s_downtime": "Horas paradas", "s_breakdown": "% del tiempo activo en avería",
        "s_mtbf": "Tiempo medio entre fallas (h)", "s_mttr": "Tiempo medio de reparación (min)",
        "kpi_section": "Indicadores de Mantenimiento",
        "split_title": "Paradas por duración", "split_short": "Cortas", "split_long": "Largas",
        "split_cut": "Corte", "split_help": "por debajo de {c} min = corta", "split_min": "min",
        "split_by_count": "por nº de paradas", "split_by_time": "por tiempo total (min)",
        "v_up": "Operación mejorando", "v_down": "Requiere atención", "v_flat": "Operación estable",
        "v_detail": "El período actual gana en {n} de {total} indicadores",
        "fresh_title": "Actualización de datos", "fresh_prod": "Producción", "fresh_stops": "Paradas",
        "fresh_collect": "última recolección", "fresh_through": "datos hasta",
        "kpi24h_section": "Indicadores — últimas 24h",
        "kpi24h_lastprod": "Último día con producción: {d}",
        "kpi24h_bars": "Planta — últimos {n} días",
        "costs_section": "Costo de Mantenimiento", "costs_month": "Mes de referencia: {m}",
        "costs_rosca": "Costo por equipo (mes)", "costs_bars": "Realizado por cuenta (% del presupuesto, mes)",
    },
    "en": {
        "title": "Maintenance Overview",
        "subtitle": "Head to head: current vs previous period — who is winning.",
        "mock_badge": "DATA IN AUDIT",
        "mock_tooltip": "Real ZPP data under validation — subject to audit.",
        "btn_month": "Month over month", "btn_week": "Week over week", "btn_band": "Day band",
        "btn_present": "Presentation", "btn_pause": "Pause", "btn_play": "Resume",
        "psub_month": "Month-to-date vs same day last month",
        "psub_week": "Week-to-date vs previous week (same days)",
        "psub_band": "Band {a}/{b} of month vs same band last month",
        "now": "Current", "prev": "Previous", "lead": "ahead", "tie": "tie", "avg": "avg",
        "ghost_label": "expected for volume", "ghost_real": "volume-adjusted",
        "c_activity": "Activity Hours", "c_stops": "Stops",
        "c_downtime": "Downtime", "c_breakdown": "Breakdown Rate",
        "c_mtbf": "MTBF", "c_mttr": "MTTR",
        "s_activity": "Accumulated production", "s_stops": "Events",
        "s_downtime": "Stopped hours", "s_breakdown": "% of active time in breakdown",
        "s_mtbf": "Mean time between failures (h)", "s_mttr": "Mean time to repair (min)",
        "kpi_section": "Maintenance Indicators",
        "split_title": "Stops by duration", "split_short": "Short", "split_long": "Long",
        "split_cut": "Cutoff", "split_help": "below {c} min = short", "split_min": "min",
        "split_by_count": "by stop count", "split_by_time": "by total time (min)",
        "v_up": "Operation improving", "v_down": "Needs attention", "v_flat": "Operation stable",
        "v_detail": "Current period wins {n} of {total} indicators",
        "fresh_title": "Data update", "fresh_prod": "Production", "fresh_stops": "Stops",
        "fresh_collect": "last collected", "fresh_through": "data through",
        "kpi24h_section": "Indicators — last 24h",
        "kpi24h_lastprod": "Last day with production: {d}",
        "kpi24h_bars": "Plant — last {n} days",
        "costs_section": "Maintenance Cost", "costs_month": "Reference month: {m}",
        "costs_rosca": "Cost by equipment (month)", "costs_bars": "Actual by account (% of budget, month)",
    },
}


def t(key, lang="pt"):
    """Tradução por key com fallback pt."""
    return TRANS.get(lang, TRANS["pt"]).get(key, key)


# ============================================================
# Janelas de período (datas REAIS — datetime.now)
# ============================================================
def _prev_month(year, month):
    return (year - 1, 12) if month == 1 else (year, month - 1)


def period_meta(period, lang, today=None):
    """Calcula as janelas reais de comparação e rótulos evidentes.

    Retorna dict: cur_range, prev_range (strings com datas), psub, band (a,b)|None.
    """
    today = today or datetime.date.today()
    mon, wd = _MON[lang], _WD[lang]
    band = None

    def _dt(d):  # date → datetime 00:00
        return datetime.datetime(d.year, d.month, d.day)

    def _excl(d):  # fim exclusivo (BR-12): primeiro instante do dia seguinte
        return _dt(d) + datetime.timedelta(days=1)

    if period == "week":
        wdid = today.weekday()  # Mon=0
        cur_start_d = today - datetime.timedelta(days=wdid)
        prev_start_d = cur_start_d - datetime.timedelta(days=7)
        prev_end_d = today - datetime.timedelta(days=7)
        cur_range = f"{wd[cur_start_d.weekday()]} {cur_start_d.day}–{wd[today.weekday()]} {today.day} {mon[today.month - 1]}"
        prev_range = f"{wd[prev_start_d.weekday()]} {prev_start_d.day}–{wd[prev_end_d.weekday()]} {prev_end_d.day} {mon[prev_end_d.month - 1]}"
        psub = t("psub_week", lang)
        cur_start, cur_end = _dt(cur_start_d), _excl(today)
        prev_start, prev_end = _dt(prev_start_d), _excl(prev_end_d)

    elif period == "band":
        BAND = 7  # semana cheia (inclui fim de semana — há hora extra no fds)
        ndays = calendar.monthrange(today.year, today.month)[1]
        nweeks = max(1, math.ceil(ndays / BAND))
        bidx = (today.day - 1) // BAND
        b_start = bidx * BAND + 1
        b_end_full = min((bidx + 1) * BAND, ndays)      # fim "cheio" da faixa (1-7, 8-14, ...)
        # Trunca no último dia COM dado (today = âncora): enquanto a faixa não fecha,
        # compara b_start..dia_atual vs b_start..dia_atual do mês passado (mesmo nº de dias).
        cur_end_day = min(b_end_full, today.day)
        py, pm = _prev_month(today.year, today.month)
        pdays = calendar.monthrange(py, pm)[1]
        prev_end_day = min(cur_end_day, pdays)          # mesmo dia no mês anterior (clampa)
        cur_range = f"{b_start}–{cur_end_day} {mon[today.month - 1]}"
        prev_range = f"{b_start}–{prev_end_day} {mon[pm - 1]}"
        band = (bidx + 1, nweeks)
        psub = t("psub_band", lang).format(a=band[0], b=band[1])
        cur_start = datetime.datetime(today.year, today.month, b_start)
        cur_end = _excl(datetime.date(today.year, today.month, cur_end_day))
        prev_start = datetime.datetime(py, pm, b_start)
        prev_end = _excl(datetime.date(py, pm, prev_end_day))

    else:  # month (MTD)
        D = today.day
        py, pm = _prev_month(today.year, today.month)
        pdays = calendar.monthrange(py, pm)[1]
        pD = min(D, pdays)  # clampa: ex. hoje=31 e mês passado tem 30
        cur_range = f"1–{D} {mon[today.month - 1]}"
        prev_range = f"1–{pD} {mon[pm - 1]}"
        psub = t("psub_month", lang)
        cur_start = datetime.datetime(today.year, today.month, 1)
        cur_end = _excl(today)
        prev_start = datetime.datetime(py, pm, 1)
        prev_end = _excl(datetime.date(py, pm, pD))

    return {"cur_range": cur_range, "prev_range": prev_range, "psub": psub, "band": band,
            "cur_start": cur_start, "cur_end": cur_end,
            "prev_start": prev_start, "prev_end": prev_end}


# ============================================================
# Cálculo do confronto
# ============================================================
_PUSH_SCALE = 2.6
_PUSH_CLAMP = 42.0


def _fmt(v, unit):
    return f"{int(round(v))}" if unit == "" else f"{v:.1f}{unit}"


def _duel(metric):
    """Confronto de uma métrica → cur, prev, perf_pct (+=atual melhor), state, color, cur_w (% à esq)."""
    cur, prev, good = metric["cur"], metric["prev"], metric["good"]
    raw_pct = ((cur - prev) / prev * 100) if prev else 0.0
    perf_pct = raw_pct if good == "up" else -raw_pct  # inverte quando menos é melhor
    if abs(perf_pct) < 0.05:
        state, color = "flat", C_FLAT
    elif perf_pct > 0:
        state, color = "good", C_GOOD
    else:
        state, color = "bad", C_BAD
    offset = max(-_PUSH_CLAMP, min(_PUSH_CLAMP, perf_pct * _PUSH_SCALE))
    cur_w = 50.0 + offset  # atual (esquerda) ocupa >50% quando ganha
    return cur, prev, perf_pct, state, color, cur_w


def _ghost(metric, r):
    """Marca-fantasma "esperado p/ volume": posição do divisor se a taxa por hora ativa
    fosse igual à do período anterior (esperado = prev × r, r = h.a.atual / h.a.anterior).

    Retorna (ghost_w, real_pct): ghost_w = posição (%) do fantasma na barra; real_pct =
    desempenho de atual vs esperado (>0 = ganho real ALÉM do que o volume explica;
    knob à direita do fantasma). (None, None) quando não dá para normalizar.
    """
    prev, good = metric["prev"], metric["good"]
    if not prev or not r:
        return None, None
    expected = prev * r
    raw_g = (r - 1) * 100.0
    perf_g = raw_g if good == "up" else -raw_g
    ghost_w = 50.0 + max(-_PUSH_CLAMP, min(_PUSH_CLAMP, perf_g * _PUSH_SCALE))
    cur = metric["cur"]
    raw_real = ((cur - expected) / expected * 100.0) if expected else 0.0
    real = raw_real if good == "up" else -raw_real
    return ghost_w, real


def _side_colors(perf_pct, state):
    """(cur_color, prev_color) p/ o trilho divergente. Melhor=verde, pior=vermelho, empate=cinza."""
    if state == "flat":
        return C_FLAT, C_FLAT
    if perf_pct > 0:            # período atual melhor → atual verde, anterior vermelho
        return C_GOOD, C_BAD
    return C_BAD, C_GOOD        # período anterior melhor → invertido


_SCALE_HEADROOM = 1.5  # fim da escala = maior valor × 1.5 → maior barra ocupa ~66.7% da
#                        metade, deixando fundo cinza nas pontas (forma divergente evidente)


def _div_track2(left_val, right_val, left_txt, right_txt, left_color, right_color, sm=False):
    """Trilho divergente genérico — barra esquerda e direita crescem a partir do eixo central.

    Comprimento = valor normalizado ao maior dos dois × _SCALE_HEADROOM (o maior ocupa
    ~66.7% da metade; sobra fundo cinza nas pontas). Cores explícitas (sem valência) —
    usado tanto pelo confronto (anterior×atual) quanto pelo split (curtas×longas).
    """
    m = (max(left_val, right_val, 0.0) * _SCALE_HEADROOM) or 1.0
    lw = max(0.0, left_val) / m * 100.0
    rw = max(0.0, right_val) / m * 100.0
    lgrad = f"linear-gradient(90deg, {left_color}, {left_color}dd)"
    rgrad = f"linear-gradient(90deg, {right_color}dd, {right_color})"
    return html.Div(
        [
            html.Div(
                html.Div(html.Span(left_txt),
                         className="home-div-bar home-div-bar-left",
                         style={"width": f"{lw:.1f}%", "background": lgrad}),
                className="home-div-half home-div-half-left",
            ),
            html.Div(
                html.Div(html.Span(right_txt),
                         className="home-div-bar home-div-bar-right",
                         style={"width": f"{rw:.1f}%", "background": rgrad}),
                className="home-div-half home-div-half-right",
            ),
            html.Div(className="home-div-axis"),
        ],
        className="home-div-track" + (" home-div-track-sm" if sm else ""),
    )


def _div_track(cur, prev, unit, perf_pct, state, sm=False):
    """Trilho divergente do confronto — anterior (esq) vs atual (dir), cor por valência."""
    cur_color, prev_color = _side_colors(perf_pct, state)
    return _div_track2(prev, cur, _fmt(prev, unit), _fmt(cur, unit),
                       prev_color, cur_color, sm=sm)


def _lbl(icon, title, sub, sm=False):
    """Rótulo de identidade genérico (padrão das barras): chip de ícone + título + subtítulo.

    Cor neutra/brand (não valência) — diz O QUE é a barra; o azul/laranja fica na própria
    barra. Reusado pelo confronto e pelo split (paradas por duração).
    """
    return html.Div(
        [
            html.Div(html.I(className=f"bi {icon}"), className="home-lbl-chip"),
            html.Div(
                [html.Span(title, className="home-lbl-title"),
                 html.Span(sub, className="home-lbl-sub")],
                className="home-lbl-text",
            ),
        ],
        className="home-lbl" + (" home-lbl-sm" if sm else ""),
    )


def _bar_label(key, icon, lang, sm=False):
    """Rótulo de identidade da métrica do confronto (chip + nome + subtítulo)."""
    return _lbl(icon, t(f"c_{key}", lang), t(f"s_{key}", lang), sm=sm)


def _compare_header(meta, lang):
    """Cabeçalho acima das barras: ANTERIOR (esq) vs ATUAL (dir) + período analisado (datas).

    Reusa a mesma estrutura das barras (espaçador da coluna de rótulo 218px + área flex
    dividida 50/50) para o divisor central cair EXATAMENTE no eixo das barras abaixo.
    """
    now_s, prev_s = t("now", lang), t("prev", lang)
    return html.Div(
        [
            html.Div(className="home-lbl"),  # espaçador = largura da coluna de identidade
            html.Div(
                [
                    html.Div(
                        [html.Span([html.I(className="bi bi-caret-left-fill me-1"), prev_s.upper()],
                                   className="home-cmp-period"),
                         html.Span(meta["prev_range"], className="home-cmp-range")],
                        className="home-cmp-side"),
                    html.Div(
                        [html.Span([now_s.upper(), html.I(className="bi bi-caret-right-fill ms-1")],
                                   className="home-cmp-period"),
                         html.Span(meta["cur_range"], className="home-cmp-range")],
                        className="home-cmp-side"),
                ],
                className="home-cmp-head",
            ),
        ],
        className="home-bar-line home-cmp-row",
    )


def _duel_bar(key, icon, lang, metric, meta, ghost_w=None, real_pct=None):
    """Barra divergente com rótulo de identidade à esquerda (chip+nome+subtítulo) + trilho.

    Demais infos (caption "à frente", datas, "descontando volume") seguem fora — a serem
    reintroduzidas gradativamente. ghost_w/real_pct/meta ignorados por ora.
    """
    cur, prev, perf_pct, state, color, _cur_w = _duel(metric)
    return html.Div(
        [_bar_label(key, icon, lang),
         _div_track(cur, prev, metric["unit"], perf_pct, state)],
        className="home-duel-row home-bar-line",
    )


def _kpi_mini(key, icon, lang, metric):
    """Mini barra divergente com rótulo de identidade compacto à esquerda + trilho."""
    cur, prev, perf_pct, state, color, _cur_w = _duel(metric)
    # Rótulo IDÊNTICO ao das barras grandes (mesma largura 188px) → trilhos cinza alinhados
    # entre os dois boxes e subtítulo não trunca. Só o trilho é compacto (sm=True).
    return html.Div(
        [_bar_label(key, icon, lang),
         _div_track(cur, prev, metric["unit"], perf_pct, state, sm=True)],
        className="home-kpi-mini home-bar-line",
    )


def render_duels(period, lang):
    """Arena de confronto — operacionais (barras grandes) + bloco KPI 3-em-1. Dados REAIS."""
    data, meta = _collect(period, lang)
    # Razão de volume (h.a. atual / h.a. anterior) p/ a marca-fantasma das barras absolutas
    act = data["activity"]
    r = (act["cur"] / act["prev"]) if act["prev"] else None
    bars = []
    for key, icon in METRICS:
        gw, real = (_ghost(data[key], r) if (r and key in ("stops", "downtime")) else (None, None))
        bars.append(_duel_bar(key, icon, lang, data[key], meta, ghost_w=gw, real_pct=real))
    # Versão minimalista (2026-06-09): sem linha de janela no topo nem título do bloco KPI.
    # As 3 operacionais ganham o MESMO box azul do bloco KPI (home-kpi-block).
    ops_block = html.Div(bars, className="home-kpi-block")
    kpi_block = html.Div(
        [_kpi_mini(key, icon, lang, data[key]) for key, icon in KPIS],
        className="home-kpi-block",
    )
    return dbc.Card(
        dbc.CardBody([_compare_header(meta, lang), ops_block, kpi_block], className="p-3"),
        className="shadow-sm indicator-v2-card-static home-duel-arena",
        style={"borderTop": "4px solid #0d6efd"},
    )


_FRESH_CACHE = {"data": None, "ts": 0.0}


def _data_freshness():
    """Datas de frescor dos dados ZPP (TTL 60s). Por fonte (produção/paradas):
      • última coleta  = ts do _id mais recente (ZPP faz delete+reinsert → última carga)
      • último dado    = maior ffinnotif (produção) / fim_execucao (paradas)
    Robusto a Mongo offline → None (UI mostra "—"). Coleta convertida p/ America/Sao_Paulo.
    """
    import time as _t
    if _FRESH_CACHE["data"] and (_t.time() - _FRESH_CACHE["ts"]) < 60:
        return _FRESH_CACHE["data"]
    out = {"prod_load": None, "prod_data": None, "par_load": None, "par_data": None}
    try:
        from src.database.connection import get_mongo_connection
        from src.utils.zpp_kpi_calculator import (
            ZPP_PRODUCAO_COLLECTION, ZPP_PARADAS_COLLECTION)
        try:
            from zoneinfo import ZoneInfo
            _TZ = ZoneInfo("America/Sao_Paulo")
        except Exception:
            _TZ = None

        def _last_load(col):
            d = col.find_one({}, {"_id": 1}, sort=[("_id", -1)])
            if not d:
                return None
            g = d["_id"].generation_time
            return g.astimezone(_TZ) if _TZ else g

        def _last_data(col, field):
            d = col.find_one({field: {"$ne": None}}, {field: 1, "_id": 0}, sort=[(field, -1)])
            return d.get(field) if d else None

        prod = get_mongo_connection(ZPP_PRODUCAO_COLLECTION)
        par = get_mongo_connection(ZPP_PARADAS_COLLECTION)
        if prod is not None:
            out["prod_load"], out["prod_data"] = _last_load(prod), _last_data(prod, "ffinnotif")
        if par is not None:
            out["par_load"], out["par_data"] = _last_load(par), _last_data(par, "fim_execucao")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("home _data_freshness falhou: %s", e)
    _FRESH_CACHE["data"], _FRESH_CACHE["ts"] = out, _t.time()
    return out


def render_freshness(lang):
    """Bloco estático de atualização dos dados (substitui o veredito).
    Mostra, por fonte ZPP, a última coleta (data+hora) e o último dado (data)."""
    f = _data_freshness()

    def _dt(v):
        return v.strftime("%d/%m/%Y %H:%M") if v else "—"

    def _d(v):
        return v.strftime("%d/%m/%Y") if v else "—"

    def _row(icon, label, collected, through):
        return html.Div(
            [
                html.I(className=f"bi {icon} me-2", style={"color": "#0d6efd"}),
                html.Strong(label, className="home-fresh-label"),
                html.Span(
                    [html.I(className="bi bi-cloud-download me-1", style={"color": C_FLAT}),
                     html.Small(t("fresh_collect", lang) + ": ", className="text-muted"),
                     html.Small(html.Strong(_dt(collected)))],
                    className="me-3"),
                html.Span(
                    [html.I(className="bi bi-calendar-check me-1", style={"color": C_FLAT}),
                     html.Small(t("fresh_through", lang) + ": ", className="text-muted"),
                     html.Small(html.Strong(_d(through)))]),
            ],
            className="d-flex align-items-center flex-wrap home-fresh-row",
        )

    return html.Div(
        [
            html.Div(
                [html.I(className="bi bi-database-check me-2", style={"color": "#0d6efd"}),
                 html.Strong(t("fresh_title", lang), style={"fontSize": "0.82rem"})],
                className="home-fresh-head mb-1",
            ),
            _row("bi-activity", t("fresh_prod", lang), f["prod_load"], f["prod_data"]),
            _row("bi-exclamation-octagon", t("fresh_stops", lang), f["par_load"], f["par_data"]),
        ],
        className="home-verdict",
        style={"borderLeft": "5px solid #0d6efd"},
    )


def render_stops_split(period, lang, cutoff):
    """Composição das paradas por duração (curtas vs longas) — SEM valência bem/mal.

    Não é confronto: o corte (min) é ajustável pelo slider; cores neutras (tom = duração).
    """
    cutoff = cutoff or 30
    data, _meta = _collect(period, lang)  # paradas de AVARIA — mesma base dos KPIs

    def _split(durs):
        s = [d for d in durs if d < cutoff]
        l = [d for d in durs if d >= cutoff]
        return len(s), len(l), int(round(sum(s))), int(round(sum(l)))

    c_ns, c_nl, c_ms, c_ml = _split(data.get("__durations", []))       # período atual
    p_ns, p_nl, p_ms, p_ml = _split(data.get("__durations_prev", []))  # período anterior
    now_s, prev_s = t("now", lang), t("prev", lang)

    def _row(icon, period_label, group_sub, s_val, l_val):
        # MESMO padrão das barras de cima: rótulo de identidade (218px) + trilho divergente.
        # Título = período (Atual/Anterior); subtítulo = grupo (nº de paradas / tempo total).
        # curtas (azul) crescem p/ ESQUERDA, longas (laranja) p/ DIREITA do eixo central.
        track = _div_track2(s_val, l_val,
                            str(s_val) if s_val else "", str(l_val) if l_val else "",
                            C_SHORT, C_LONG, sm=True)
        return html.Div([_lbl(icon, period_label, group_sub), track],
                        className="home-kpi-mini home-bar-line")

    rows = [
        _row("bi-hash", now_s, t("split_by_count", lang), c_ns, c_nl),
        _row("bi-hash", prev_s, t("split_by_count", lang), p_ns, p_nl),
        _row("bi-stopwatch", now_s, t("split_by_time", lang), c_ms, c_ml),
        _row("bi-stopwatch", prev_s, t("split_by_time", lang), p_ms, p_ml),
    ]
    bars_box = html.Div(rows, className="home-kpi-block")  # mesmo box azul de cima

    # Chave de cor (curtas / longas)
    color_key = html.Div(
        [
            html.Small([html.Span(className="home-stops-dot", style={"background": C_SHORT}),
                        t("split_short", lang)], className="d-flex align-items-center"),
            html.Small([html.Span(className="home-stops-dot", style={"background": C_LONG}),
                        t("split_long", lang)], className="d-flex align-items-center"),
        ],
        className="d-flex mt-2", style={"fontSize": "0.7rem", "gap": "14px"},
    )

    return html.Div([bars_box, color_key])


# ============================================================
# Slide do carrossel: ROW de KPIs IDÊNTICA à V2 (MTBF · MTTR · Avaria)
# Reusa o PIPELINE REAL da V2: _fetch_planta_monthly (12 meses + status),
# _resolve_target, _period_agg, _to_display, _bar_rich. Ring/sparkline/trend
# reproduzidos verbatim. Dados REAIS do Mongo (default V2: ano, BREAKDOWN_CODES).
# ============================================================
def render_kpi_skeleton(lang=None):
    """Empty-state (skeleton shimmer) da row de KPIs — exibido enquanto o fetch real
    não confirma. Reutilizável para qualquer render de dados reais demorado."""
    def _sk_card(color):
        return dbc.Col(
            dbc.Card(
                [
                    dbc.CardHeader(
                        html.Div(
                            [html.Div(
                                [html.Div(className="skel-line", style={"width": "42%", "height": "14px"}),
                                 html.Div(className="skel-line", style={"width": "72%", "height": "10px", "marginTop": "8px"})],
                                style={"flex": "1"})],
                            className="d-flex", style={"minHeight": "74px"},
                        ),
                        className="py-2",
                    ),
                    dbc.CardBody(
                        [
                            html.Div(
                                [html.Div(className="skel-line", style={"width": "38%", "height": "26px"}),
                                 html.Div(className="skel-circle")],
                                className="d-flex justify-content-between align-items-center px-2 mb-2",
                                style={"height": "60px"},
                            ),
                            html.Div(className="skel-block", style={"height": "222px"}),
                        ],
                        className="p-2", style={"minHeight": "271px"},
                    ),
                ],
                className="shadow-sm h-100 indicator-v2-card",
                style={"borderTop": "4px solid " + color},
            ),
            xs=12, md=4,
        )
    return html.Div(dbc.Row([_sk_card(c) for c in ("#198754", "#0d6efd", "#dc3545")],
                            className="mb-4 kpi-row-v2"))


def render_v2_kpi_row(period, lang):
    """Slide do carrossel: a ROW de KPIs idêntica à página V2 (dados reais)."""
    import plotly.graph_objects as go
    from src.callbacks_registers.indicators_v2_callbacks import (
        _bar_rich, KPI_META, _fetch_planta_monthly, _resolve_target,
        _period_agg, _to_display, _unpack_filters,
    )
    from src.pages.maintenance.indicators_v2 import TRANS as _TRANS
    lang = lang or "pt"
    td_lang = _TRANS.get(lang, _TRANS["pt"])
    title_planta = td_lang.get("tl_planta_mensal", "Planta — mensal")
    start, end, codes, equipment_filter, year, lwb = _unpack_filters(None)

    def _planta_fig(kpi, labels, values, target, statuses=None):
        fig = _bar_rich(labels, values, title_planta,
                        KPI_META[kpi]["color"], KPI_META[kpi]["unit"],
                        target=target, direction=KPI_META[kpi]["direction"],
                        td=td_lang, bar_statuses=statuses)
        fig.update_layout(height=222)
        return fig

    def _ring(kpi, value, target):
        direction = KPI_META[kpi]["direction"]
        if not target or value is None:
            achievement = 0
        elif direction == "lower":
            achievement = min(1.0, target / value) if value > 0 else 1.0
        else:
            achievement = min(1.0, value / target) if target > 0 else 0
        pct = int(round(achievement * 100))
        ring_color = "#198754" if achievement >= 0.95 else ("#ffc107" if achievement >= 0.7 else "#dc3545")
        fig = go.Figure(go.Pie(values=[achievement, max(0, 1 - achievement)],
                               marker=dict(colors=[ring_color, "rgba(0,0,0,0.06)"], line=dict(width=0)),
                               hole=0.72, textinfo="none", hoverinfo="skip", sort=False,
                               direction="clockwise", rotation=0))
        fig.add_annotation(text="<b>%d%%</b>" % pct, showarrow=False,
                           font=dict(size=12, color=ring_color, family="Arial Black"), x=0.5, y=0.5)
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=60, width=60)
        return dcc.Graph(figure=fig, config={"displayModeBar": False, "staticPlot": True, "responsive": False},
                         style={"height": "60px", "width": "60px"})

    def _hex_to_rgba(hex_color, alpha=0.15):
        h = hex_color.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        try:
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return "rgba(%d,%d,%d,%s)" % (r, g, b, alpha)
        except Exception:
            return "rgba(108,117,125,%s)" % alpha

    def _sparkline(kpi, values, color):
        cut = len(values)
        while cut > 0 and values[cut - 1] in (0, None):
            cut -= 1
        truncated = values[:cut]
        non_zero = [v for v in truncated if v not in (0, None)]
        if len(non_zero) < 2:
            return None
        fig = go.Figure(go.Scatter(x=list(range(len(truncated))), y=truncated, mode="lines",
                                   line=dict(color=color, width=2, shape="spline"),
                                   fill="tozeroy", fillcolor=_hex_to_rgba(color, 0.18), hoverinfo="skip"))
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), xaxis=dict(visible=False),
                          yaxis=dict(visible=False), plot_bgcolor="rgba(0,0,0,0)",
                          paper_bgcolor="rgba(0,0,0,0)", height=28, width=90, showlegend=False)
        return dcc.Graph(figure=fig, config={"displayModeBar": False, "staticPlot": True},
                         style={"height": "28px", "width": "90px"})

    def _trend_delta(kpi, values):
        non_zero = [(i, v) for i, v in enumerate(values) if v not in (0, None)]
        if len(non_zero) < 2:
            return html.Span()
        last_v, prev_v = non_zero[-1][1], non_zero[-2][1]
        if prev_v == 0:
            return html.Span()
        delta_pct = ((last_v - prev_v) / prev_v) * 100
        direction = KPI_META[kpi]["direction"]
        improving = (delta_pct < 0) if direction == "lower" else (delta_pct > 0)
        cls_mod = "delta-neutral" if abs(delta_pct) < 1 else ("delta-good" if improving else "delta-bad")
        arrow = "↓" if delta_pct < 0 else ("↑" if delta_pct > 0 else "→")
        return html.Span("%s %.1f%%" % (arrow, abs(delta_pct)), className="kpi-trend-delta " + cls_mod,
                         title="Último: %s%s vs anterior: %s%s" % (last_v, KPI_META[kpi]["unit"], prev_v, KPI_META[kpi]["unit"]))

    def _pulse_class(kpi, values, target):
        non_zero = [v for v in values if v not in (0, None)]
        if not non_zero or target is None:
            return ""
        last = non_zero[-1]
        direction = KPI_META[kpi]["direction"]
        excedeu = (last > target) if direction == "lower" else (last < target)
        return " v2-pulse-warning" if excedeu else ""

    agg = _period_agg(start, end, codes, equipment_filter, lwb_simulate=lwb)
    aggval = {"breakdown": _to_display("breakdown", agg.get("breakdown_rate", 0)),
              "mtbf": _to_display("mtbf", agg.get("mtbf", 0)),
              "mttr": _to_display("mttr", agg.get("mttr", 0))}
    _i18n = {"mtbf": "mtbf", "mttr": "mttr", "breakdown": "br"}
    _dec = {"mtbf": 2, "mttr": 2, "breakdown": 2}  # idêntico à V2 (default _kpi_card)

    def card(kpi):
        meta = KPI_META[kpi]
        color, unit = meta["color"], meta["unit"]
        labels, values, statuses = _fetch_planta_monthly(kpi, start, end, codes, equipment_filter, lwb_simulate=lwb)
        target = _resolve_target(kpi)
        fig = _planta_fig(kpi, labels, values, target, statuses)
        val = aggval[kpi]
        short = _i18n[kpi]
        title = td_lang.get("kpi_%s_title" % short, meta["label"])
        subtitle = td_lang.get("kpi_%s_sub" % short, "")
        pulse = _pulse_class(kpi, values, target)
        return html.Div(
            dbc.Card(
                [
                    dbc.CardHeader(
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Span([html.Strong(title, style={"fontSize": "1rem"}),
                                                   _trend_delta(kpi, values)]),
                                        html.Div(
                                            [html.Span(subtitle, className="text-muted",
                                                       style={"fontSize": "0.78rem", "lineHeight": "1.2"}),
                                             html.Span(_sparkline(kpi, values, color), className="v2-sparkline-mini")],
                                            className="d-flex justify-content-between align-items-center mt-1",
                                        ),
                                    ],
                                    style={"flex": "1"},
                                ),
                                dbc.Badge([html.I(className="bi bi-zoom-in me-1"), "drilldown"],
                                          color="light", text_color="primary", className="border align-self-start",
                                          style={"fontSize": "0.7rem", "fontWeight": "500"}),
                            ],
                            className="d-flex justify-content-between align-items-start gap-2",
                            style={"minHeight": "74px"},
                        ),
                        className="py-2",
                    ),
                    dbc.CardBody(
                        [
                            html.Div(
                                [
                                    html.Span("—", **{"data-v2-anim": str(val), "data-v2-unit": unit,
                                                      "data-v2-decimals": str(_dec[kpi])},
                                              style={"fontSize": "1.7rem", "fontWeight": "700", "color": color,
                                                     "letterSpacing": "-0.5px", "lineHeight": "1"}),
                                    html.Div(_ring(kpi, val, target), style={"width": "60px", "height": "60px"}),
                                ],
                                className="d-flex justify-content-between align-items-center px-2 mb-2",
                                style={"height": "60px"},
                            ),
                            dcc.Graph(figure=fig,
                                      config={"displayModeBar": False, "staticPlot": True, "responsive": True},
                                      style={"height": "222px", "width": "100%"}),
                        ],
                        className="p-2", style={"minHeight": "271px"},
                    ),
                ],
                className="shadow-sm h-100 indicator-v2-card" + pulse,
                style={"borderTop": "4px solid " + color},
            ),
            n_clicks=0, style={"cursor": "default", "height": "100%"},
        )

    row = dbc.Row([dbc.Col(card(k), xs=12, md=4) for k in ("mtbf", "mttr", "breakdown")],
                  className="mb-4 kpi-row-v2")
    return html.Div(row)


# ------------------------------------------------------------
# Recorte 24h (último dia com produção) — helpers de nível de módulo.
# Cópias isoladas dos closures de `render_v2_kpi_row` para NÃO tocar na função
# anual já validada (premissa de preservação de UI). Usados só pela row de 24h.
# ------------------------------------------------------------
def _h24_hex_to_rgba(hex_color, alpha=0.15):
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return "rgba(%d,%d,%d,%s)" % (r, g, b, alpha)
    except Exception:
        return "rgba(108,117,125,%s)" % alpha


def _h24_ring(kpi_meta, value, target):
    import plotly.graph_objects as go
    direction = kpi_meta["direction"]
    if not target or value is None:
        achievement = 0
    elif direction == "lower":
        achievement = min(1.0, target / value) if value > 0 else 1.0
    else:
        achievement = min(1.0, value / target) if target > 0 else 0
    pct = int(round(achievement * 100))
    ring_color = "#198754" if achievement >= 0.95 else ("#ffc107" if achievement >= 0.7 else "#dc3545")
    fig = go.Figure(go.Pie(values=[achievement, max(0, 1 - achievement)],
                           marker=dict(colors=[ring_color, "rgba(0,0,0,0.06)"], line=dict(width=0)),
                           hole=0.72, textinfo="none", hoverinfo="skip", sort=False,
                           direction="clockwise", rotation=0))
    fig.add_annotation(text="<b>%d%%</b>" % pct, showarrow=False,
                       font=dict(size=12, color=ring_color, family="Arial Black"), x=0.5, y=0.5)
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=60, width=60)
    return dcc.Graph(figure=fig, config={"displayModeBar": False, "staticPlot": True, "responsive": False},
                     style={"height": "60px", "width": "60px"})


def _h24_sparkline(values, color):
    import plotly.graph_objects as go
    cut = len(values)
    while cut > 0 and values[cut - 1] in (0, None):
        cut -= 1
    truncated = values[:cut]
    non_zero = [v for v in truncated if v not in (0, None)]
    if len(non_zero) < 2:
        return None
    fig = go.Figure(go.Scatter(x=list(range(len(truncated))), y=truncated, mode="lines",
                               line=dict(color=color, width=2, shape="spline"),
                               fill="tozeroy", fillcolor=_h24_hex_to_rgba(color, 0.18), hoverinfo="skip"))
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), xaxis=dict(visible=False),
                      yaxis=dict(visible=False), plot_bgcolor="rgba(0,0,0,0)",
                      paper_bgcolor="rgba(0,0,0,0)", height=28, width=90, showlegend=False)
    return dcc.Graph(figure=fig, config={"displayModeBar": False, "staticPlot": True},
                     style={"height": "28px", "width": "90px"})


def _h24_trend_delta(kpi_meta, values):
    non_zero = [(i, v) for i, v in enumerate(values) if v not in (0, None)]
    if len(non_zero) < 2:
        return html.Span()
    last_v, prev_v = non_zero[-1][1], non_zero[-2][1]
    if prev_v == 0:
        return html.Span()
    delta_pct = ((last_v - prev_v) / prev_v) * 100
    direction = kpi_meta["direction"]
    improving = (delta_pct < 0) if direction == "lower" else (delta_pct > 0)
    cls_mod = "delta-neutral" if abs(delta_pct) < 1 else ("delta-good" if improving else "delta-bad")
    arrow = "↓" if delta_pct < 0 else ("↑" if delta_pct > 0 else "→")
    return html.Span("%s %.1f%%" % (arrow, abs(delta_pct)), className="kpi-trend-delta " + cls_mod,
                     title="Último: %s%s vs anterior: %s%s" % (last_v, kpi_meta["unit"], prev_v, kpi_meta["unit"]))


def _h24_pulse_class(kpi_meta, values, target):
    non_zero = [v for v in values if v not in (0, None)]
    if not non_zero or target is None:
        return ""
    last = non_zero[-1]
    direction = kpi_meta["direction"]
    excedeu = (last > target) if direction == "lower" else (last < target)
    return " v2-pulse-warning" if excedeu else ""


def render_24h_kpi_row(lang):
    """Row de KPIs do recorte 24h: MTBF/MTTR/Avaria do último dia com produção,
    com barras dos últimos N dias. Visual idêntico à row anual (`render_v2_kpi_row`),
    mas alimentada por `build_last_production_24h_series` (fallback fim de semana)."""
    from src.callbacks_registers.indicators_v2_callbacks import _bar_rich, KPI_META, _resolve_target
    from src.pages.maintenance.indicators_v2 import TRANS as _TRANS
    from src.utils.kpi_report_config import _now_in_report_timezone
    from src.utils.kpi_report_v2_series import build_last_production_24h_series

    lang = lang or "pt"
    td_lang = _TRANS.get(lang, _TRANS["pt"])
    n_days = 7
    series = build_last_production_24h_series(_now_in_report_timezone(), n_days=n_days)
    labels = series["labels"]
    cur = series.get("current_idx", len(labels) - 1)
    bars_title = t("kpi24h_bars", lang).format(n=n_days)

    # mapa kpi (KPI_META) → chave da série
    _skey = {"mtbf": "mtbf", "mttr": "mttr", "breakdown": "taxa_avaria"}
    _short = {"mtbf": "mtbf", "mttr": "mttr", "breakdown": "br"}
    _dec = {"mtbf": 2, "mttr": 2, "breakdown": 2}

    def card(kpi):
        meta = KPI_META[kpi]
        color, unit = meta["color"], meta["unit"]
        values = series.get(_skey[kpi], [0.0] * len(labels))
        target = _resolve_target(kpi)
        big = values[cur] if 0 <= cur < len(values) else 0.0
        fig = _bar_rich(labels, values, bars_title, color, unit,
                        target=target, direction=meta["direction"], td=td_lang)
        fig.update_layout(height=222)
        title = td_lang.get("kpi_%s_title" % _short[kpi], meta["label"])
        subtitle = td_lang.get("kpi_%s_sub" % _short[kpi], "")
        pulse = _h24_pulse_class(meta, values, target)
        return html.Div(
            dbc.Card(
                [
                    dbc.CardHeader(
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Span([html.Strong(title, style={"fontSize": "1rem"}),
                                                   _h24_trend_delta(meta, values)]),
                                        html.Div(
                                            [html.Span(subtitle, className="text-muted",
                                                       style={"fontSize": "0.78rem", "lineHeight": "1.2"}),
                                             html.Span(_h24_sparkline(values, color), className="v2-sparkline-mini")],
                                            className="d-flex justify-content-between align-items-center mt-1",
                                        ),
                                    ],
                                    style={"flex": "1"},
                                ),
                                dbc.Badge([html.I(className="bi bi-clock-history me-1"), "24h"],
                                          color="light", text_color="primary", className="border align-self-start",
                                          style={"fontSize": "0.7rem", "fontWeight": "500"}),
                            ],
                            className="d-flex justify-content-between align-items-start gap-2",
                            style={"minHeight": "74px"},
                        ),
                        className="py-2",
                    ),
                    dbc.CardBody(
                        [
                            html.Div(
                                [
                                    html.Span("—", **{"data-v2-anim": str(big), "data-v2-unit": unit,
                                                      "data-v2-decimals": str(_dec[kpi])},
                                              style={"fontSize": "1.7rem", "fontWeight": "700", "color": color,
                                                     "letterSpacing": "-0.5px", "lineHeight": "1"}),
                                    html.Div(_h24_ring(meta, big, target), style={"width": "60px", "height": "60px"}),
                                ],
                                className="d-flex justify-content-between align-items-center px-2 mb-2",
                                style={"height": "60px"},
                            ),
                            dcc.Graph(figure=fig,
                                      config={"displayModeBar": False, "staticPlot": True, "responsive": True},
                                      style={"height": "222px", "width": "100%"}),
                        ],
                        className="p-2", style={"minHeight": "271px"},
                    ),
                ],
                className="shadow-sm h-100 indicator-v2-card" + pulse,
                style={"borderTop": "4px solid " + color},
            ),
            n_clicks=0, style={"cursor": "default", "height": "100%"},
        )

    section = html.Div(
        [
            html.Span(t("kpi24h_section", lang), className="home-kpi24h-title"),
            html.Span(t("kpi24h_lastprod", lang).format(d=series.get("highlight_date", "—")),
                      className="home-kpi24h-sub"),
        ],
        className="home-kpi24h-header",
    )
    row = dbc.Row([dbc.Col(card(k), xs=12, md=4) for k in ("mtbf", "mttr", "breakdown")],
                  className="mb-2 kpi-row-v2")
    return html.Div([section, row], className="home-kpi24h-block")


def render_kpis_dual(period, lang):
    """Slide de KPIs: row anual (intacta) em cima + row 24h (novo) embaixo."""
    return html.Div([
        render_v2_kpi_row(period, lang),
        render_24h_kpi_row(lang),
    ])


# ============================================================
# Slide do carrossel: Custo de Manutenção do MÊS corrente (BR-14 / DS-12)
# Réplica ESTÁTICA da "geral de custos" (aba de custos da V2): rosca por equipamento
# (esq) + barras orçado×executado por conta (dir). Importa as figuras de custo e a
# leitura por dentro da função (import lazy) — mesmo padrão de reuso de render_v2_kpi_row,
# evita import circular no topo do módulo. Sem clique/slider/modal (telão = leitura).
# ============================================================
def render_costs_slide(lang):
    """Slide de custos do mês corrente: rosca (equipamento) + barras (% por conta), estático."""
    lang = lang or "pt"
    try:
        from src.callbacks_registers.custo_callbacks import (
            _fig_rosca, _fig_barras, _filtra_por_contas, _contas_efetivas)
        from src.custos import leitura as L
        from src.utils.kpi_report_config import _now_in_report_timezone
        now = _now_in_report_timezone()
        ano, mm = now.year, now.month
        mes = f"{ano}-{mm:02d}"  # BR-14: mês do relógio; executado já cortado em ≤ D-1 na coleta
        # Rosca e barras herdam as contas fixadas na aba via "Fixar no telão" (vazio = todas);
        # GERAL e rosca somam só esse recorte (BR-17).
        contas = _contas_efetivas(L.ler_slide_contas() or None, ano)  # telão nunca fica vazio
        rosca = _fig_rosca(L.fetch_por_equipamento(ano, None, mes=mes, contas=contas))
        rosca.update_layout(title_text=t("costs_rosca", lang))  # figura diz "(ano)"; aqui é mês
        rows = _filtra_por_contas(L.fetch_contas_geral(ano, mes=mes), contas)
        barras = _fig_barras(rows, True, t("costs_bars", lang), h=460, modo="pct")
        cfg = {"displayModeBar": False, "staticPlot": True, "responsive": True}
        row = dbc.Row(
            [
                dbc.Col(dcc.Graph(figure=rosca, config=cfg,
                                  style={"height": "460px", "width": "100%"}), xs=12, md=4),
                dbc.Col(dcc.Graph(figure=barras, config=cfg,
                                  style={"height": "460px", "width": "100%"}), xs=12, md=8),
            ],
            className="g-2 align-items-center",
        )
        mes_lbl = f"{_MON[lang][mm - 1]}/{ano}"
        section = html.Div(
            [
                html.Span(t("costs_section", lang), className="home-kpi24h-title"),
                html.Span(t("costs_month", lang).format(m=mes_lbl), className="home-kpi24h-sub"),
            ],
            className="home-kpi24h-header",
        )
        return html.Div([section, row], className="home-costs-slide")
    except Exception as e:  # custos offline / sem dados do mês → cabeçalho + aviso (UI não quebra)
        import logging
        logging.getLogger(__name__).warning("home render_costs_slide falhou: %s", e)
        return html.Div(
            html.Span(t("costs_section", lang), className="home-kpi24h-title"),
            className="home-costs-slide",
        )


def render_costs_skeleton():
    """Empty-state (shimmer) do slide de Custos — círculo (rosca) + bloco (barras), mesma grade."""
    return html.Div(
        dbc.Row(
            [
                dbc.Col(html.Div(className="skel-circle",
                                 style={"width": "260px", "height": "260px",
                                        "borderRadius": "50%", "margin": "40px auto"}),
                        xs=12, md=4),
                dbc.Col(html.Div(className="skel-block", style={"height": "420px"}), xs=12, md=8),
            ],
            className="g-2 align-items-center",
        ),
        className="home-costs-slide",
    )


# ============================================================
# Bandeiras (lang switcher)
# ============================================================
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
    flags = [("pt", "Português"), ("es", "Español"), ("en", "English")]
    return html.Div(
        [
            html.Button(
                html.Img(
                    src="data:image/svg+xml;base64," + base64.b64encode(_FLAG_SVGS[code].encode()).decode(),
                    alt=title,
                    style={"width": "28px", "height": "20px", "borderRadius": "3px",
                           "boxShadow": "0 1px 3px rgba(0,0,0,0.2)"},
                ),
                id={"type": "home-lang-btn", "lang": code},
                title=title, n_clicks=0, className="v2-lang-flag",
            )
            for code, title in flags
        ],
        className="d-flex align-items-center gap-2 v2-lang-switcher",
    )


# ============================================================
# DISPATCH DA HOME POR PERFIL + NÍVEL (DS-13 / BR-15)
# A rota '/' é única; o conteúdo varia conforme current_user.perfil/.level.
# Blocos internos obedecem perfil + nível via registry (home_blocks — BR-16).
# ============================================================
from src.pages.dashboards.home_blocks import HomeBlock, render_blocos  # noqa: E402


def _home_card(icon, title, desc, href, btn_label, color="primary", btn_id=None):
    """Card-atalho padrão de uma home por perfil."""
    return dbc.Col(
        dbc.Card(
            dbc.CardBody([
                html.Div(
                    [html.I(className=f"bi {icon} me-2",
                            style={"fontSize": "1.4rem", "color": "#0d6efd"}),
                     html.H5(title, className="d-inline align-middle mb-0")],
                    className="mb-2 d-flex align-items-center",
                ),
                html.P(desc, className="text-muted",
                       style={"fontSize": "0.85rem", "minHeight": "2.4rem"}),
                dbc.Button(
                    [html.I(className="bi bi-arrow-right-circle me-2"), btn_label],
                    href=href, color=color, size="sm",
                    **({"id": btn_id} if btn_id else {}),
                ),
            ]),
            className="shadow-sm h-100",
        ),
        xs=12, md=6, lg=4, className="mb-3",
    )


def _home_shell(titulo, icone, subtitulo, corpo):
    """Casca comum das homes por perfil: header + container fluido."""
    return dbc.Container(
        [
            dbc.Row(dbc.Col(html.Div([
                html.H2(
                    [html.I(className=f"bi {icone} me-3", style={"color": "#0d6efd"}),
                     html.Span(titulo)],
                    className="mb-1 d-flex align-items-center",
                ),
                html.P(subtitulo, className="text-muted mb-0", style={"fontSize": "0.9rem"}),
            ])), className="mb-3"),
            corpo,
        ],
        fluid=True, className="p-3",
    )


# ============================================================
# HOME DE MANUTENÇÃO (Etapa 2 — IM-13): boas-vindas + cards de insight
# Visual herdado do design system da Indicators-V2 (indicator-v2-card, contador
# animado v2_animated_counter.js, spotlight). Dados reais: veredito semanal (reuso
# do confronto da própria home) + backlog SAP (utils/backlog_data).
# ============================================================
_MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
             "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
_KPI_LABELS = {"mtbf": "MTBF", "mttr": "MTTR", "breakdown": "Taxa de Avaria"}


def _week_verdict():
    """Veredito da semana: dos 3 KPIs (MTBF/MTTR/Avaria), quantos pioraram vs a semana
    anterior. Reusa o confronto da home (_collect/_duel) — sem query nova. None se falhar."""
    try:
        data, _meta = _collect("week", "pt")
    except Exception:
        return None
    keys = ["mtbf", "mttr", "breakdown"]
    worse = better = flat = 0
    worst = None  # (key, perf_pct) — o mais negativo
    for k in keys:
        _cur, _prev, perf_pct, state, _c, _w = _duel(data[k])
        if state == "bad":
            worse += 1
        elif state == "good":
            better += 1
        else:
            flat += 1
        if worst is None or perf_pct < worst[1]:
            worst = (k, perf_pct)
    return {"worse": worse, "better": better, "flat": flat,
            "total": len(keys), "worst": worst}


def _backlog_summary():
    """Resumo do backlog SAP p/ o card da home: total de ordens visíveis + dias da mais
    antiga. Degrada para None se o módulo/coleção não existir (RNF graceful)."""
    try:
        from src.utils import backlog_data as bd
        snap = bd.carregar_snapshot(silent=True)
        if not snap:
            return None
        bd.enriquecer_local(snap["ordens"], bd.carregar_ativos())
        visiveis = bd.filtrar(snap["ordens"], {})
        ins = bd.insights(visiveis)
        return {"total": ins.get("total", 0),
                "mais_antiga_dias": ins.get("mais_antiga_dias")}
    except Exception:
        return None


def _anim_number(value, unit="", decimals=0):
    """Número grande com contador animado (v2_animated_counter.js anima [data-v2-anim])."""
    return html.Span(
        "—",
        **{"data-v2-anim": str(value), "data-v2-unit": unit,
           "data-v2-decimals": str(decimals)},
        className="home-mtn-headline",
    )


def _pill(text, variant):
    """Chip de tendência. variant: 'down' (pior/vermelho), 'up' (melhor/verde), 'flat'."""
    return html.Span(text, className=f"home-mtn-pill home-mtn-pill-{variant}")


def _fmt_brl(v):
    """R$ compacto: 1.234.567 → '1,2 mi'; 12.345 → '12 mil'; senão inteiro."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "—"
    a = abs(v)
    if a >= 1_000_000:
        return f"{v / 1_000_000:.1f} mi".replace(".", ",")
    if a >= 1_000:
        return f"{v / 1_000:.0f} mil"
    return f"{v:.0f}"


def _insight_card(chip_icon, accent, eyebrow, headline, support, btn_label, href,
                  btn_id, pill=None):
    """Card de insight sofisticado da home de manutenção (estilo indicator-v2-card)."""
    return dbc.Col(
        html.Div(
            dbc.Card(
                dbc.CardBody(
                    [
                        html.Div(
                            [
                                html.Div(html.I(className=f"bi {chip_icon}"),
                                         className="home-mtn-chip",
                                         style={"background": accent}),
                                pill if pill is not None else html.Span(),
                            ],
                            className="d-flex justify-content-between align-items-start mb-2",
                        ),
                        html.Div(eyebrow, className="home-mtn-eyebrow"),
                        html.Div(headline, className="home-mtn-headline-wrap"),
                        html.Div(support, className="home-mtn-support"),
                        dbc.Button(
                            [html.Span(btn_label), html.I(className="bi bi-arrow-right ms-1")],
                            href=href, id=btn_id, size="sm", color="link",
                            className="home-mtn-btn-link mt-auto",
                            style={"color": accent},
                        ),
                    ],
                    className="d-flex flex-column h-100",
                ),
                className="shadow-sm h-100 indicator-v2-card home-mtn-card",
                style={"borderTop": f"4px solid {accent}"},
            ),
            className="home-mtn-card-wrap h-100",
        ),
        xs=12, sm=6, xl=True, className="mb-3 d-flex",
    )


def _blk_indicadores(lang):
    """Card de Indicadores — veredito semana×semana dos 3 KPIs (BR-16/SP-F16)."""
    v = _week_verdict()
    accent = "#0d6efd"
    if not v:
        head, support, pill = html.Span("—", className="home-mtn-headline"), \
            "Sem dados desta semana.", None
    else:
        if v["worse"] > v["better"]:
            head = html.Span([_anim_number(v["worse"]),
                              html.Span(f" de {v['total']}", className="home-mtn-head-sub")])
            verbo, pill = "pioraram", _pill("piora", "down")
        elif v["better"] > v["worse"]:
            head = html.Span([_anim_number(v["better"]),
                              html.Span(f" de {v['total']}", className="home-mtn-head-sub")])
            verbo, pill = "melhoraram", _pill("melhora", "up")
        else:
            head = html.Span("estável", className="home-mtn-headline")
            verbo, pill = "sem mudança", _pill("estável", "flat")
        wk, wp = v["worst"]
        support = html.Span([f"indicadores {verbo} esta semana · destaque: ",
                             html.Strong(_KPI_LABELS.get(wk, wk)),
                             f" ({wp:+.0f}%)"])
    return _insight_card("bi-graph-up-arrow", accent, "Indicadores da semana",
                         head, support, "Ver Indicadores",
                         "/maintenance/indicators-v2", "btn-home-mtn-indicadores", pill)


def _blk_backlog(lang):
    """Card de Backlog SAP — total de ordens + mais antiga (SP-F16)."""
    b = _backlog_summary()
    accent = "#08137C"  # navy do backlog
    if not b:
        head = html.Span("—", className="home-mtn-headline")
        support, pill = "Backlog indisponível no momento.", None
    else:
        head = html.Span([_anim_number(b["total"]),
                          html.Span(" ordens", className="home-mtn-head-sub")])
        dias = b.get("mais_antiga_dias")
        if dias is not None:
            support = html.Span(["mais antiga há ", html.Strong(f"{dias} dias")])
            pill = _pill(f"{dias}d", "down" if dias > 90 else "flat")
        else:
            support, pill = "ordens em aberto no backlog.", None
    return _insight_card("bi-card-checklist", accent, "Backlog de manutenção",
                         head, support, "Abrir Backlog",
                         "/maintenance/backlog", "btn-home-mtn-backlog", pill)


def _blk_visao_geral(lang):
    """Atalho para a Visão Geral da Manutenção (home rica migrada — BR-17)."""
    return _insight_card(
        "bi-speedometer2", "#E96D38", "Dashboard Manutenção",
        html.Span("Visão Geral", className="home-mtn-headline-text"),
        "Evolução da saúde de ativos",
        "Abrir Visão Geral", "/maintenance/overview?present=1", "btn-home-mtn-overview")


def _blk_custos(lang):
    """Card de Custos — executado × planejado (orçado) do mês corrente (gated nível ≥2).

    Mostra o % do orçado já executado no mês e sinaliza estouro (acima do plano). Reusa a
    leitura de custos ([[project-costsmanagement-sdd]]); degrada se a coleção não existir."""
    accent = "#1a8754"
    orc = exe = pct = None
    estouro = False
    try:
        from src.utils.kpi_report_config import _now_in_report_timezone
        from src.custos import leitura as L
        now = _now_in_report_timezone()
        geral = L.fetch_contas_geral(now.year, mes=f"{now.year}-{now.month:02d}")[0]
        orc, exe, pct, estouro = (geral["orcado"], geral["executado"],
                                  geral.get("pct"), geral.get("estouro"))
    except Exception:
        pass

    if pct is None:
        head = html.Span("—", className="home-mtn-headline")
        support, pill = "Sem orçamento lançado neste mês.", None
    else:
        head = html.Span(_anim_number(pct, unit="%", decimals=0))
        support = html.Span([f"R$ {_fmt_brl(exe)} de ",
                             html.Strong(f"R$ {_fmt_brl(orc)}"), " orçado · este mês"])
        pill = _pill("acima do plano", "down") if estouro else _pill("dentro do plano", "up")
    return _insight_card(
        "bi-cash-coin", accent, "Custos do mês · nível avançado",
        head, support, "Análise de Custos",
        "/maintenance/indicators-v2?tab=custo", "btn-home-mtn-custos", pill)


def _blk_analise_falhas(lang):
    """Atalho para a Análise de Falhas (gated nível ≥2). Nasce como esqueleto visual."""
    return _insight_card(
        "bi-exclamation-triangle", "#c0392b", "Confiabilidade · nível avançado",
        html.Span("Análise de Falhas", className="home-mtn-headline-text"),
        "Padrões e ofensores de parada",
        "Abrir Análise", "/maintenance/analise-de-falhas", "btn-home-mtn-falhas")


MANUTENCAO_BLOCKS = [
    HomeBlock("indicadores", _blk_indicadores, perfis=["manutencao"], min_level=1),
    HomeBlock("backlog", _blk_backlog, perfis=["manutencao"], min_level=1),
    HomeBlock("visao-geral", _blk_visao_geral, perfis=["manutencao"], min_level=1),
    HomeBlock("custos", _blk_custos, perfis=["manutencao"], min_level=2),
    HomeBlock("analise-falhas", _blk_analise_falhas, perfis=["manutencao"], min_level=2),
]


def _clock_chip(cidade, span_id, valor_inicial):
    """Chip de relógio (cidade + hora). O valor é atualizado client-side (home_clocks.js)."""
    return html.Span(
        [
            html.I(className="bi bi-clock me-1"),
            html.Span(f"{cidade} ", className="home-mtn-clock-city"),
            html.Span(valor_inicial, id=span_id, className="home-mtn-clock-time"),
        ],
        className="home-mtn-clock",
    )


def _home_mtn_hero(nome, level):
    """Cabeçalho leve de boas-vindas (estilo header da Indicators-V2) com o logo do
    cliente (AMG) à direita — sem banner colorido, alinhado às demais páginas."""
    from zoneinfo import ZoneInfo
    now = datetime.datetime.now()
    data_txt = f"{now.day} de {_MESES_PT[now.month - 1]} de {now.year}"
    hora = now.hour
    saud = "Bom dia" if hora < 12 else ("Boa tarde" if hora < 18 else "Boa noite")
    # valores iniciais (server-side) p/ não piscar; o JS mantém atualizado sem custo de servidor
    brt = datetime.datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%H:%M")
    mad = datetime.datetime.now(ZoneInfo("Europe/Madrid")).strftime("%H:%M")
    return html.Div(
        [
        dbc.Row(
            [
                dbc.Col(
                    html.Div(
                        [
                            html.H2(
                                [
                                    html.Span(f"{saud}, ", className="home-mtn-hero-greet"),
                                    html.Span(f"{nome}", className="home-mtn-hero-name"),
                                ],
                                className="mb-1 d-flex align-items-baseline flex-wrap",
                            ),
                            html.P(f"EasyTek-Data · {data_txt}",
                                   className="text-muted mb-0", style={"fontSize": "0.9rem"}),
                            html.Div(
                                [
                                    _clock_chip("Brasília", "clock-brt", brt),
                                    _clock_chip("Madrid", "clock-mad", mad),
                                ],
                                className="home-mtn-clocks mt-2",
                            ),
                        ]
                    ),
                    xs=8, md=9,
                ),
                dbc.Col(
                    html.Img(src="/assets/LogoAMG.png", className="home-mtn-hero-logo",
                             alt="AMG"),
                    xs=4, md=3, className="text-end",
                ),
            ],
            className="align-items-center g-0",
        ),
        # Linha divisória + "Powered by" (esquerda, abaixo)
        html.Hr(className="home-mtn-hero-divider"),
        html.Div(
            [
                html.Span("Powered by", className="home-mtn-powered-text"),
                html.A(
                    html.Img(src="/assets/logo.png", className="home-mtn-powered-logo",
                             alt="Tekmont"),
                    href="https://www.tekmont.com.br", target="_blank",
                    rel="noopener noreferrer", title="Tekmont",
                ),
            ],
            className="home-mtn-powered",
        ),
    ],
        className="home-mtn-hero",
    )


def _home_mtn_bg():
    """Camadas de fundo full-bleed (largura total da viewport), atrás dos cards
    (z-index < conteúdo): fábrica no topo + bobinas no rodapé, bem esmaecidas."""
    return html.Div(
        [
            html.Img(src="/assets/home-abstract.svg",
                     className="home-mtn-bg-img home-mtn-bg-top", alt=""),
            html.Img(src="/assets/home-abstract.svg",
                     className="home-mtn-bg-img home-mtn-bg-bottom", alt=""),
        ],
        className="home-mtn-bg", **{"aria-hidden": "true"},
    )


def _home_scene(level, cards=None):
    """Cena de boas-vindas UNIVERSAL (todos os perfis): fundo da planta + hero
    (logo, nome, saudação, relógios). `cards` (opcional) são blocos específicos do
    perfil — hoje só a manutenção tem; demais perfis veem apenas a cena."""
    nome = (getattr(current_user, "username", None) or "Equipe").strip().title()
    filhos = [_home_mtn_bg(), _home_mtn_hero(nome, level)]
    if cards:
        filhos.append(dbc.Row(cards, className="home-mtn-cards"))
    return dbc.Container(filhos, fluid=True, className="p-3 p-md-4 home-mtn")


def render_home_manutencao(perfil, level):
    """Home da Manutenção: cena universal + cards de insight com gating de nível
    (Custos só nível ≥2) via registry (BR-15/16, SP-F16)."""
    return _home_scene(level, cards=render_blocos(MANUTENCAO_BLOCKS, current_user, "pt"))


def render_home_default(perfil, level):
    """Demais perfis: a MESMA cena de boas-vindas, sem os cards de manutenção."""
    return _home_scene(level)


def layout():
    """Dispatch da home (BR-15/DS-13). URL '/' única e compartilhada: TODOS os perfis
    veem a mesma cena de boas-vindas; a manutenção adiciona seus cards de insight.
    Chamado dentro do request — current_user sempre presente (roteador trata login antes)."""
    perfil = getattr(current_user, "perfil", None)
    level = getattr(current_user, "level", 1) or 1
    if perfil == "manutencao":
        return render_home_manutencao(perfil, level)
    return render_home_default(perfil, level)


def overview_layout():
    """Visão Geral da Manutenção (rota /maintenance/overview, ex-home / — BR-17/DS-15).

    Conteúdo inalterado da home anterior: confronto de períodos + KPIs + paradas +
    modo apresentação. Migrada de `/` para página secundária de manutenção; os IDs são
    preservados para que os callbacks de `home_callbacks.py` continuem ligando por ID.
    """
    return dbc.Container(
        [
            dcc.Store(id="store-home-lang", storage_type="local", data="pt"),
            dcc.Store(id="store-home-period", storage_type="memory", data="month"),
            dcc.Store(id="store-home-present", storage_type="memory", data=False),
            dcc.Store(id="store-home-paused", storage_type="memory", data=False),
            dcc.Store(id="store-home-slide", storage_type="memory", data=0),
            dcc.Store(id="store-home-graph", storage_type="memory", data=None),
            dcc.Store(id="store-home-rendered", storage_type="memory", data=0),
            dcc.Store(id="store-rendered-graph", storage_type="memory", data=0),
            dcc.Store(id="store-rendered-cuts", storage_type="memory", data=0),
            # DDS no telão — overlay de imagem aberto pelo botão "DDS" ou pela tecla F9
            dcc.Store(id="store-home-dds", storage_type="memory", data=False),
            # Rotação automática dos cortes no modo apresentação (8s) — desabilitado fora dele
            dcc.Interval(id="interval-home-present", interval=15000, n_intervals=0, disabled=True),

            # Header
            dbc.Row(
                [
                    dbc.Col(
                        html.Div([
                            html.H2(
                                [
                                    html.I(className="bi bi-speedometer2 me-3", style={"color": "#0d6efd"}),
                                    html.Span("Visão Geral da Manutenção", id="home-i18n-title"),
                                    dbc.Badge(
                                        [html.I(className="bi bi-clipboard2-check me-2"),
                                         html.Span("DADOS EM AUDITORIA", id="home-i18n-mock-badge")],
                                        id="home-mock-badge", color="warning", text_color="dark",
                                        className="v2-beta-badge ms-3 align-middle", pill=True,
                                    ),
                                    dbc.Tooltip("Valores de demonstração — não refletem a operação real.",
                                                id="home-mock-tooltip", target="home-mock-badge",
                                                placement="bottom"),
                                ],
                                className="mb-1 d-flex align-items-center flex-wrap",
                            ),
                            html.P("Confronto direto: período atual vs anterior — quem está ganhando.",
                                   id="home-i18n-subtitle", className="text-muted mb-0",
                                   style={"fontSize": "0.9rem"}),
                        ]),
                        xs=12, md=8,
                    ),
                    dbc.Col(
                        html.Div(_lang_switcher(), className="d-flex justify-content-md-end mt-2 mt-md-0"),
                        xs=12, md=4,
                    ),
                ],
                className="mb-2 align-items-center",
            ),

            # Controles do carrossel: Anterior/Próximo navegam TODOS os slides (3 cortes +
            # KPIs + Custos) em qualquer modo. Pausar/Retomar só no modo apresentação.
            # Os botões de período (mês/semana/faixa) foram removidos — viram slides.
            dbc.Row(
                dbc.Col(html.Div(
                    [
                        dbc.ButtonGroup(
                            [
                                dbc.Button([html.I(className="bi bi-chevron-left me-1"),
                                            html.Span("Anterior", id="home-i18n-btn-prev")],
                                           id="btn-home-present-prev", color="dark",
                                           outline=True, size="sm", n_clicks=0, title="Anterior"),
                                dbc.Button([html.Span("Próximo", id="home-i18n-btn-next"),
                                            html.I(className="bi bi-chevron-right ms-1")],
                                           id="btn-home-present-next", color="dark",
                                           outline=True, size="sm", n_clicks=0, title="Próximo"),
                            ],
                            className="shadow-sm me-2",
                        ),
                        # Pausar/Retomar — só no modo apresentação
                        dbc.Button(
                            [html.I(className="bi bi-pause-fill me-1", id="icon-home-pause"),
                             html.Span("Pausar", id="home-i18n-btn-pause")],
                            id="btn-home-present-pause", color="dark", outline=True,
                            size="sm", n_clicks=0, className="home-present-only me-2"),
                        # DDS — abre o guia do Diálogo Diário de Segurança em tela cheia
                        # e congela o carrossel enquanto estiver aberto (atalho: F9).
                        # Sem callback próprio: o clique é tratado em `home_dds.js`,
                        # que aciona o gatilho global do overlay (`btn-dds-trigger`).
                        dbc.Button(
                            [html.I(className="bi bi-shield-check me-1"),
                             html.Span("DDS", id="home-i18n-btn-dds")],
                            id="btn-home-dds", color="warning", outline=True,
                            size="sm", n_clicks=0, className="me-2",
                            title="Exibir o DDS em tela cheia (F9)"),
                        # Apresentação (auto-rotação + fullscreen) — à direita
                        dbc.Button(
                            [html.I(className="bi bi-display me-2"),
                             html.Span("Apresentação", id="home-i18n-btn-present")],
                            id="btn-home-present", color="dark", outline=True, size="sm",
                            n_clicks=0, className="ms-auto"),
                    ],
                    className="d-flex align-items-center flex-wrap gap-2",
                )),
                className="mb-2",
            ),

            # Barrinha discreta de tempo regressivo do carrossel (só no present mode)
            html.Div(id="home-countdown", className="home-countdown"),

            # Palco do carrossel com transição chique de 1500ms (mascara render real dos gráficos)
            html.Div(
                [
                    html.Div(id="home-transition", className="home-transition"),
                    html.Div([

            # Conteúdo dos CORTES (confronto + paradas) — oculto durante slides de gráfico
            html.Div([

            # Veredito
            dbc.Row(dbc.Col(html.Div(id="home-verdict-container")), className="mb-2"),

            # Arena de confronto
            html.Div(id="home-charts-container"),

            # ===== Bloco SEPARADO: Paradas por duração (sem win/lose, cores neutras) =====
            dbc.Card(
                dbc.CardBody(
                    [
                        html.Div(
                            [
                                html.Div(
                                    [html.I(className="bi bi-stopwatch me-2", style={"color": "#495057"}),
                                     html.Strong("Paradas por duração", id="home-i18n-split-title",
                                                 style={"fontSize": "0.85rem"})],
                                    className="d-flex align-items-center",
                                ),
                                html.Small(id="home-i18n-split-help", className="text-muted"),
                            ],
                            className="d-flex justify-content-between align-items-center mb-2 flex-wrap",
                        ),
                        html.Div(id="home-stops-split"),
                        # Slider de corte (min)
                        html.Div(
                            [
                                html.Small([html.Span(id="home-i18n-split-cut"), ": ",
                                            html.Strong(id="home-split-cut-val")],
                                           className="text-muted d-block mb-1",
                                           style={"fontSize": "0.72rem"}),
                                dcc.Slider(
                                    id="slider-home-cutoff", min=5, max=120, step=5, value=30,
                                    marks={m: {"label": f"{m}", "style": {"fontSize": "0.65rem"}}
                                           for m in (5, 30, 60, 90, 120)},
                                    tooltip={"placement": "bottom", "always_visible": False},
                                ),
                            ],
                            className="mt-2",
                        ),
                    ],
                    className="p-3",
                ),
                className="shadow-sm home-stops-card mt-3",
                style={"borderTop": "4px solid #0d6efd"},
            ),

            ], id="home-cuts-view"),

            # Slide de GRÁFICO (MTBF/MTTR/Avaria) — visível só nos slides de gráfico do carrossel.
            # Skeleton (3 cards na mesma posição/tamanho) entra no slide-enter; render real substitui.
            html.Div(html.Div(id="home-graph-slide"), id="home-graph-view", style={"display": "none"}),

                    ], className="home-stage-content"),
                ],
                id="home-stage", className="home-stage",
            ),
            dcc.Store(id="store-home-transition"),


            build_rodape(),
            # "Rodar agora" movido para /maintenance/coletas-sap (página consolidada)
        ],
        fluid=True,
        className="p-3",
    )
