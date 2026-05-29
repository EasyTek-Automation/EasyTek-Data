"""Loader do mock HH Gantt — lê os exports reais do SAP (3 meses, BR02) e
monta as estruturas consumidas pela página `/maintenance/hh-gantt`.

NÃO conecta no SAP nem no Mongo: lê dois CSVs em `src/data/hh_mock/` (dados reais
de produção, gitignorados). Espelha o padrão `INDICATORS_V2_FORCE_MOCK` — fonte de
dados trocável depois sem mexer na UI.

Fontes:
- `IW47_realizado_3meses.csv` — confirmações (1 linha = 1 apontamento de técnico),
  com hora real de início/fim (`ISDD`+`ISDZ` / `IEDD`+`IEDZ`).
- `IW37_planejado_3meses.csv` — operações planejadas (grão ordem+operação) com datas
  programadas (`FSAVD`→`FSEDD`). A hora programada do IW37 é sintética → usamos só a DATA.
"""

from __future__ import annotations

import os
import csv
import threading
from datetime import datetime, timedelta, date

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "hh_mock")
_REALIZADO_CSV = os.path.join(_DATA_DIR, "IW47_realizado_3meses.csv")
_PLANEJADO_CSV = os.path.join(_DATA_DIR, "IW37_planejado_3meses.csv")

_CACHE = None
_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Parsers (formato PT/SAP)
# ---------------------------------------------------------------------------

def _parse_pt_int(s):
    """'1.566' → 1566 · '5.883' → 5883 · '105' → 105 · '11.000-' → -11000 · '' → 0.
    Ponto = separador de milhar; sinal de menos no fim = negativo."""
    s = (s or "").strip()
    if not s:
        return 0
    neg = s.endswith("-")
    if neg:
        s = s[:-1]
    s = s.replace(".", "").replace(",", ".")
    try:
        v = int(round(float(s)))
    except ValueError:
        return 0
    return -v if neg else v


def _parse_dt(d, t):
    """Combina data 'dd.mm.aaaa' + hora 'HH:MM:SS' em datetime. Hora vazia → 00:00."""
    d = (d or "").strip()
    if not d:
        return None
    try:
        dd, mm, yy = d.split(".")
        day, month, year = int(dd), int(mm), int(yy)
    except ValueError:
        return None
    hh = mi = ss = 0
    t = (t or "").strip()
    if t:
        parts = t.split(":")
        try:
            hh = int(parts[0]); mi = int(parts[1]); ss = int(parts[2]) if len(parts) > 2 else 0
        except (ValueError, IndexError):
            hh = mi = ss = 0
    try:
        return datetime(year, month, day, hh, mi, ss)
    except ValueError:
        return None


def _parse_date(d):
    """Data 'dd.mm.aaaa' → date (sem hora). None se vazio/inválido."""
    dt = _parse_dt(d, "")
    return dt.date() if dt else None


# ---------------------------------------------------------------------------
# Leitura dos CSVs
# ---------------------------------------------------------------------------

def _load_realizado():
    """IW47 (limpo, 23 colunas). Retorna lista de confirmações.
    Exclui linha de total (AUFNR vazio) e apontamentos estornados (STOKZ preenchido)."""
    out = []
    if not os.path.exists(_REALIZADO_CSV):
        return out
    with open(_REALIZADO_CSV, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        for row in reader:
            if len(row) < 23:
                continue
            aufnr = row[0].strip()
            if not aufnr:          # linha de total do ALV
                continue
            if row[19].strip():    # STOKZ preenchido = estorno → descarta
                continue
            start_dt = _parse_dt(row[13], row[14])   # ISDD + ISDZ
            end_dt = _parse_dt(row[15], row[16])      # IEDD + IEDZ
            if start_dt is None:
                continue
            if end_dt is None or end_dt < start_dt:
                end_dt = start_dt
            out.append({
                "aufnr": aufnr,
                "vornr": row[1].strip(),
                "auart": row[3].strip(),
                "pernr": row[4].strip(),
                "name": (row[5].strip() or row[4].strip() or "—"),
                "tplnr": row[6].strip(),              # local de instalação (equipamento)
                "ismnw": _parse_pt_int(row[7]),       # realizado (min)
                "arbei": _parse_pt_int(row[9]),       # planejado-esforço (min)
                "parbpl": row[11].strip(),
                "start_dt": start_dt,
                "end_dt": end_dt,
            })
    return out


def _load_planejado():
    """IW37 (texto livre com vírgulas → ancora head[0:3] + tail[-13:]).
    Retorna dict {(aufnr,vornr): {...}}. Datas + HORAS programadas (FSAVD+FSAVZ → FSEDD+FSEDZ).
    Hora é sintética no SAP (scheduling auto), mas serve pra apertar visualmente."""
    by_op = {}
    if not os.path.exists(_PLANEJADO_CSV):
        return by_op
    with open(_PLANEJADO_CSV, encoding="utf-8") as f:
        next(f, None)  # header
        for line in f:
            line = line.rstrip("\n").rstrip("\r")
            if not line:
                continue
            parts = line.split(",")
            if len(parts) < 16:
                continue
            aufnr = parts[0].strip()
            vornr = parts[1].strip()
            if not aufnr:
                continue
            tail = parts[-13:]   # ARBEI,ARBEH,FSAVD,FSAVZ,FSEDD,FSEDZ,SSAVD,SSAVZ,SSEDD,SSEDZ,ISDD,IEDD,PERNR
            ltxa1 = parts[3].strip()
            arbei = _parse_pt_int(tail[0])
            fsavd = _parse_date(tail[2]);  fsavz = tail[3].strip()
            fsedd = _parse_date(tail[4]);  fsedz = tail[5].strip()
            fsav_dt = _parse_dt(tail[2], tail[3]) if fsavz else (
                _parse_dt(tail[2], "00:00:00") if fsavd else None)
            fsed_dt = _parse_dt(tail[4], tail[5]) if fsedz else (
                _parse_dt(tail[4], "23:59:00") if fsedd else None)
            by_op[(aufnr, vornr)] = {
                "aufnr": aufnr, "vornr": vornr, "ltxa1": ltxa1,
                "arbei": arbei, "fsavd": fsavd, "fsedd": fsedd,
                "fsav_dt": fsav_dt, "fsed_dt": fsed_dt,
                "auart": parts[2].strip(),
            }
    return by_op


def _build():
    """Monta o dataset uma vez: confirmações + planejado + índices por ordem."""
    confs = _load_realizado()
    planned = _load_planejado()

    # Rótulo e janela planejada por ORDEM (agrega operações) — DATETIMES (data+hora)
    order_label = {}
    order_plan_span = {}   # aufnr -> (min_fsav_dt, max_fsed_dt) — datetimes
    for (aufnr, vornr), p in planned.items():
        if aufnr not in order_label and p["ltxa1"]:
            order_label[aufnr] = p["ltxa1"]
        fs, fe = p["fsav_dt"], p["fsed_dt"]
        if fs and fe:
            cur = order_plan_span.get(aufnr)
            lo = min(cur[0], fs) if cur else fs
            hi = max(cur[1], fe) if cur else fe
            order_plan_span[aufnr] = (lo, hi)

    # bounds de data (das confirmações reais)
    dates = [c["start_dt"].date() for c in confs]
    dmin = min(dates) if dates else date(2026, 5, 1)
    dmax = max(dates) if dates else date(2026, 5, 31)

    return {
        "confs": confs,
        "planned": planned,
        "order_label": order_label,
        "order_plan_span": order_plan_span,
        "date_min": dmin,
        "date_max": dmax,
    }


def get_dataset():
    """Dataset cacheado (lê os CSVs só uma vez por processo)."""
    global _CACHE
    if _CACHE is None:
        with _LOCK:
            if _CACHE is None:
                _CACHE = _build()
    return _CACHE


# ---------------------------------------------------------------------------
# Janela semanal
# ---------------------------------------------------------------------------

def default_week_start():
    """Segunda-feira da semana mais recente com dados (last ISDD)."""
    ds = get_dataset()
    d = ds["date_max"]
    monday = d - timedelta(days=d.weekday())
    return datetime(monday.year, monday.month, monday.day)


def week_window(offset_weeks=0):
    """Retorna (t_start, t_end) da semana = default + offset semanas. [Seg 00:00, próx Seg 00:00)."""
    base = default_week_start() + timedelta(weeks=offset_weeks)
    return base, base + timedelta(days=7)


# ---------------------------------------------------------------------------
# Turnos (janelas nominais + extra +2h por jornada típica industrial)
# ---------------------------------------------------------------------------

TURNOS_HORAS = {
    "A": ((0, 15), (6, 15)),       # 00:15 → 06:15  (madrugada)
    "B": ((6, 15), (15, 39)),      # 06:15 → 15:39  (manhã/tarde)
    "C": ((15, 24), (0, 29)),      # 15:24 → 00:29  (cruza meia-noite)
}
EXTRA_HORAS = 2


def _t_to_min(t):
    """(HH, MM) → minutos desde 00:00."""
    return t[0] * 60 + t[1]


def _in_turno(minute_of_day, turno):
    s, e = (_t_to_min(x) for x in TURNOS_HORAS[turno])
    if s < e:
        return s <= minute_of_day < e
    return minute_of_day >= s or minute_of_day < e   # cruza meia-noite


def infer_employee_shifts(confs=None):
    """Por sigla (pernr), turno predominante via histograma das horas de início."""
    ds = get_dataset()
    confs = confs if confs is not None else ds["confs"]
    by_p = {}
    for c in confs:
        m = c["start_dt"].hour * 60 + c["start_dt"].minute
        by_p.setdefault(c["pernr"], []).append(m)
    out = {}
    for p, mins in by_p.items():
        scores = {t: sum(1 for m in mins if _in_turno(m, t)) for t in ("A", "B", "C")}
        best = max(scores, key=lambda k: scores[k])
        out[p] = best if scores[best] > 0 else "B"
    return out


def turno_label(turno):
    """'Turno A (00:15–06:15)' — formato curto pra UI."""
    (sh, sm), (eh, em) = TURNOS_HORAS[turno]
    return f"Turno {turno} ({sh:02d}:{sm:02d}–{eh:02d}:{em:02d})"


def shift_block(turno, day_dt):
    """Janela nominal (start_dt, end_dt) do turno num dado dia.
    Para turno que cruza meia-noite, end fica no dia seguinte."""
    (sh, sm), (eh, em) = TURNOS_HORAS[turno]
    start = day_dt + timedelta(hours=sh, minutes=sm)
    end_same = day_dt + timedelta(hours=eh, minutes=em)
    end = end_same if end_same > start else day_dt + timedelta(days=1, hours=eh, minutes=em)
    return start, end


def offset_for_date(d):
    """Offset em semanas (relativo à semana default) que contém a data `d` (date ou ISO str).
    Permite saltar direto pra qualquer semana via datepicker."""
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    base = default_week_start().date()          # segunda da semana default
    chosen_monday = d - timedelta(days=d.weekday())
    return (chosen_monday - base).days // 7


def confs_in_window(t_start, t_end):
    """Confirmações que tocam a janela [t_start, t_end)."""
    ds = get_dataset()
    out = []
    for c in ds["confs"]:
        if c["end_dt"] >= t_start and c["start_dt"] < t_end:
            out.append(c)
    return out


def orders_with_plan_in_window(t_start, t_end):
    """Conjunto de AUFNR cujo order_plan_span sobrepõe a janela."""
    ds = get_dataset()
    out = set()
    for a, sp in ds["order_plan_span"].items():
        if sp[1] >= t_start and sp[0] < t_end:
            out.add(a)
    return out


def emp_all_time_orders():
    """{pernr: set(aufnr)} agregando todo o dataset (independe da janela)."""
    ds = get_dataset()
    out = {}
    for c in ds["confs"]:
        out.setdefault(c["pernr"], set()).add(c["aufnr"])
    return out


# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------

def filter_options():
    """Opções (estáveis, de todo o dataset) para os dropdowns de filtro."""
    ds = get_dataset()
    tec, cen, tip, eq = {}, set(), set(), set()
    for c in ds["confs"]:
        tec[c["pernr"]] = c["name"]
        if c["parbpl"]:
            cen.add(c["parbpl"])
        if c["auart"]:
            tip.add(c["auart"])
        if c["tplnr"]:
            eq.add(c["tplnr"])
    return {
        "tecnicos": sorted(({"label": f"{v} ({k})", "value": k} for k, v in tec.items()),
                           key=lambda o: o["label"]),
        "centros": [{"label": x, "value": x} for x in sorted(cen)],
        "tipos": [{"label": x, "value": x} for x in sorted(tip)],
        "equipamentos": [{"label": x, "value": x} for x in sorted(eq)],
    }


def _band(pct):
    """Faixa de aproveitamento/estouro (BR-05)."""
    if pct <= 100:
        return "dentro"
    if pct <= 150:
        return "leve"
    if pct <= 300:
        return "alto"
    return "extremo"


def apply_filters(confs, f):
    """Aplica o dict de filtros a uma lista de confirmações."""
    f = f or {}
    out = confs
    if f.get("tecnicos"):
        s = set(f["tecnicos"]); out = [c for c in out if c["pernr"] in s]
    if f.get("centros"):
        s = set(f["centros"]); out = [c for c in out if c["parbpl"] in s]
    if f.get("tipos"):
        s = set(f["tipos"]); out = [c for c in out if c["auart"] in s]
    if f.get("equipamentos"):
        s = set(f["equipamentos"]); out = [c for c in out if c["tplnr"] in s]
    if f.get("ordem"):
        q = str(f["ordem"]).strip(); out = [c for c in out if q in c["aufnr"]]
    dm = f.get("dur_min") or 0
    if dm > 0:
        out = [c for c in out if c["ismnw"] >= dm]
    if f.get("so_nao_planejadas"):
        # "não planejada" = operação que NEM foi agendada no IW37
        # (não tem FSAVD/FSEDD — surgiu só na execução)
        ds = get_dataset()
        planned_keys = ds["planned"]
        out = [c for c in out if (c["aufnr"], c["vornr"]) not in planned_keys]
    if f.get("bandas"):
        sel = set(f["bandas"])
        op_r, op_p = {}, {}
        for c in out:
            k = (c["aufnr"], c["vornr"])
            op_r[k] = op_r.get(k, 0) + c["ismnw"]
            op_p[k] = max(op_p.get(k, 0), c["arbei"])
        keep = set()
        for k, r in op_r.items():
            p = op_p.get(k, 0)
            if p > 0 and r > 0:
                if _band(r / p * 100) in sel:
                    keep.add(k)
            elif "sem_plano" in sel:
                keep.add(k)
        out = [c for c in out if (c["aufnr"], c["vornr"]) in keep]
    return out
