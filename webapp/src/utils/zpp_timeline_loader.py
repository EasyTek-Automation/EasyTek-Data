"""ZPP Timeline Loader — eventos da timeline a partir de ZPP_Paradas + ZPP_Producao.

DS-06 / IM-07: combina paradas (com código) + gaps de produção (verde) em DataFrame
unificado pronto pra renderização Plotly do timeline evocon-style na V2 e home.

DS-07 / IM-08: `_classify_status(code)` mapeia código SAP → categoria visual.
"""

from datetime import date, datetime, timedelta
import logging
from typing import Optional, List

import pandas as pd

logger = logging.getLogger("zpp_timeline_loader")

# Imports lazy — protegidos
try:
    from src.utils.zpp_kpi_calculator import (
        BREAKDOWN_CODES,
        fetch_zpp_production_data,
        fetch_zpp_breakdown_data,
        get_zpp_equipment_names,
    )
    from src.database.connection import get_mongo_connection
    _HAS_MONGO = True
except Exception as _e:
    logger.warning("zpp_timeline_loader: import V1 falhou (%s) — só mock", _e)
    _HAS_MONGO = False
    BREAKDOWN_CODES = ["201", "S201", "202", "S202", "203", "S203",
                       "204", "S204", "205", "S205", "110", "S110"]


# DS-06 — paleta canônica da timeline
EVOCON_PALETTE_TIMELINE = {
    "producao":    "#198754",  # verde
    "avaria":      "#dc3545",  # vermelho
    "setup":       "#ffc107",  # amarelo
    "logistica":   "#fd7e14",  # laranja
    "microparada": "#ffc107",  # amarelo (idem setup)
    "refeicao":    "#adb5bd",  # cinza
    "mtto_auto":   "#6c757d",  # cinza escuro
    "processo":    "#e85d04",  # laranja escuro
    "outros":      "#9aa0a6",  # cinza neutro
}


# Set pra lookup rápido — BR-04 + BR-14
_BREAKDOWN_SET = set(BREAKDOWN_CODES)


def _classify_status(code: Optional[str]) -> str:
    """Classifica código de parada SAP em categoria de status visual.

    Convenção (BR-14):
      201/S201..205/S205 → avaria     (afeta KPI)
      110/S110           → mtto_auto  (afeta KPI)
      102N, demais 1XX   → refeicao
      301..3XX           → setup
      401..4XX           → logistica
      501..5XX           → microparada
      601..6XX           → processo
      outros / None      → outros (cinza neutro)
    """
    if not code:
        return "outros"

    code_str = str(code).strip()
    if not code_str:
        return "outros"

    # Strip prefix "S" pra inspecionar dígito de família
    c = code_str.upper().lstrip("S")

    # Breakdown codes têm tratamento especial: separa avaria de mtto_auto
    if code_str in _BREAKDOWN_SET:
        if c.startswith("110"):
            return "mtto_auto"
        return "avaria"

    # Restante por família
    if not c or not c[0].isdigit():
        return "outros"

    head = c[0]
    if head == "1":
        return "refeicao"
    if head == "3":
        return "setup"
    if head == "4":
        return "logistica"
    if head == "5":
        return "microparada"
    if head == "6":
        return "processo"
    return "outros"


def _combine_date_hour(base: datetime, hora) -> datetime:
    """Combina data (sem hora) + string "HH:MM:SS" do SAP → datetime preciso.

    SAP ZPP exporta `inicio_execucao`/`fim_execucao` como meia-noite UTC e
    grava a hora em campo separado (`inicio_real_hora`, `hininotif`, etc) no
    formato "HH:MM:SS". Sem esta combinação, todas as paradas e produção do
    dia aparecem colapsadas em 00:00 no timeline.
    """
    if not isinstance(base, datetime):
        return base
    if not isinstance(hora, str) or not hora:
        return base
    try:
        parts = hora.split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        s = int(parts[2]) if len(parts) > 2 else 0
        return base.replace(hour=h, minute=m, second=s, microsecond=0)
    except (ValueError, IndexError, TypeError):
        return base


def _subtract_intervals(big_start: datetime, big_end: datetime,
                        blockers: list) -> list:
    """Subtrai intervalos `blockers` de `[big_start, big_end)` → lista de gaps.

    Resolve overlap visual entre janela ZPP_Producao (cobre ~24h) e paradas que
    caem dentro dela: sem subtração, barra verde da produção é renderizada por
    cima e oculta as paradas. Algoritmo: clampa cada blocker à janela, faz merge
    dos sobrepostos, retorna os trechos livres entre cuts.
    """
    if big_end <= big_start:
        return []
    cuts = []
    for s, e in blockers:
        s2, e2 = max(s, big_start), min(e, big_end)
        if e2 > s2:
            cuts.append((s2, e2))
    if not cuts:
        return [(big_start, big_end)]
    cuts.sort()
    merged = [list(cuts[0])]
    for s, e in cuts[1:]:
        if s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    gaps = []
    cursor = big_start
    for s, e in merged:
        if s > cursor:
            gaps.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < big_end:
        gaps.append((cursor, big_end))
    return gaps


def fetch_timeline_events(
    t_start: datetime,
    t_end: datetime,
    equipment_ids: Optional[List[str]] = None,
    breakdown_codes: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Eventos da timeline pra janela [t_start, t_end) por equipamento.

    Combina:
      - ZPP_Paradas: documentos com `causa_do_desvio` (status via `_classify_status`)
      - ZPP_Producao: janelas de operação; gaps entre paradas viram registros `producao`

    Args:
        t_start, t_end: janela semi-aberta [start, end) — BR-12.
        equipment_ids: filtro de equipamentos (None = todos via `get_zpp_equipment_names`).
        breakdown_codes: se passado, filtra ZPP_Paradas por `causa_do_desvio ∈ codes`
                         (BR-15 — switch foco mtto ON). None = todos os códigos.

    Returns:
        DataFrame com colunas:
        ['equipment_id', 'label_eq', 'y', 'start_dt', 'end_dt',
         'duration_min', 'status', 'cod', 'desc', 'color', 'pattern']
    """
    if not _HAS_MONGO:
        return _empty_df()

    try:
        # 1. Resolver lista de equipamentos
        all_names = get_zpp_equipment_names()  # {LONGI001: "LCL-08", ...}
        if equipment_ids:
            names = {eid: all_names.get(eid, eid) for eid in equipment_ids if eid}
        else:
            names = all_names

        if not names:
            return _empty_df()

        # 2. Buscar paradas
        if breakdown_codes is not None:
            # Switch ON: query local com filtro $in que preserva hora real.
            # NÃO usar fetch_zpp_breakdown_data — descarta hora e retorna
            # `date` como datetime.date, que isinstance(_, datetime) rejeita.
            brk_df = _fetch_avaria_paradas(t_start, t_end, breakdown_codes)
        else:
            # Switch OFF: precisa todos os códigos — query direta sem filtro $in
            brk_df = _fetch_all_paradas(t_start, t_end)

        # 3. Buscar produção — query local pra preservar hora real (`hininotif`).
        # `fetch_zpp_production_data` da V1 descarta hora e devolve date sem
        # timestamp, o que colapsa todas as barras verdes em 00:00 do dia.
        prod_df = _fetch_all_producao(t_start, t_end)

        # 4. Construir DataFrame por equipamento
        rows = []
        for y_idx, (eq_id, label) in enumerate(sorted(names.items())):
            # Eventos de parada do equipamento — acumula intervalos pra subtrair
            # do janelão de produção (evita overlay visual da barra verde).
            eq_brk = brk_df[brk_df.get("linea") == eq_id] if not brk_df.empty else pd.DataFrame()
            brk_intervals = []
            for _, row in eq_brk.iterrows():
                start_dt = row.get("date")  # já vem como datetime no fetch V1
                if not isinstance(start_dt, datetime):
                    continue
                dur_min = float(row.get("duracao_min", 0) or 0)
                if dur_min <= 0:
                    continue
                end_dt = start_dt + timedelta(minutes=dur_min)
                brk_intervals.append((start_dt, end_dt))
                cod = str(row.get("motivo", "") or "")
                status = _classify_status(cod)
                rows.append({
                    "equipment_id": eq_id,
                    "label_eq":     label,
                    "y":            y_idx,
                    "start_dt":     start_dt,
                    "end_dt":       end_dt,
                    "duration_min": dur_min,
                    "status":       status,
                    "cod":          cod,
                    "desc":         "—",  # ZPP_Paradas tem descricao mas fetch V1 não retorna
                    "color":        EVOCON_PALETTE_TIMELINE.get(status, "#9aa0a6"),
                    "pattern":      "/" if status == "setup" else "",
                })

            # 5. Gaps de produção (verde) — janelas ZPP_Producao menos paradas
            eq_prod = prod_df[prod_df.get("linea") == eq_id] if not prod_df.empty else pd.DataFrame()
            for _, prod_row in eq_prod.iterrows():
                p_start_raw = prod_row.get("date")
                horas = float(prod_row.get("horasact", 0) or 0)
                if horas <= 0:
                    continue
                # `fetch_zpp_production_data` retorna `date` como `datetime.date`
                # (linha 306: `fim.date()`). `isinstance(date_obj, datetime)` é
                # False — date NÃO é subclasse de datetime. Aceitar ambos e
                # promover date → datetime na meia-noite local.
                if isinstance(p_start_raw, datetime):
                    p_start = p_start_raw
                elif isinstance(p_start_raw, date):
                    p_start = datetime(p_start_raw.year, p_start_raw.month, p_start_raw.day)
                else:
                    continue
                p_end = p_start + timedelta(hours=horas)
                p_start = max(p_start, t_start)
                p_end = min(p_end, t_end)
                if p_end <= p_start:
                    continue
                # Subtrai paradas do equipamento que caem dentro da janela —
                # uma barra verde por gap entre paradas, em vez de uma única
                # barra cobrindo o dia todo (que escondia as paradas).
                for g_start, g_end in _subtract_intervals(p_start, p_end, brk_intervals):
                    rows.append({
                        "equipment_id": eq_id,
                        "label_eq":     label,
                        "y":            y_idx,
                        "start_dt":     g_start,
                        "end_dt":       g_end,
                        "duration_min": (g_end - g_start).total_seconds() / 60,
                        "status":       "producao",
                        "cod":          "—",
                        "desc":         "Produção",
                        "color":        EVOCON_PALETTE_TIMELINE["producao"],
                        "pattern":      "",
                    })

        df = pd.DataFrame(rows)
        return df if not df.empty else _empty_df()

    except Exception as e:
        logger.warning("fetch_timeline_events falhou (%s) — retorna vazio", e)
        return _empty_df()


def _fetch_all_paradas(t_start: datetime, t_end: datetime) -> pd.DataFrame:
    """Query direta em ZPP_Paradas SEM filtro de breakdown codes (switch OFF).
    Retorna DataFrame com schema compatível com fetch_zpp_breakdown_data da V1
    + combina `inicio_real_hora` (HH:MM:SS) com `inicio_execucao` (data) pra
    posicionar a barra no horário real do dia.
    """
    if not _HAS_MONGO:
        return pd.DataFrame()
    try:
        col = get_mongo_connection("ZPP_Paradas")
        if col is None:
            return pd.DataFrame()
        cursor = col.find(
            {
                "fim_execucao": {"$gte": t_start, "$lt": t_end},  # BR-05 month_boundary=fim
            },
            {
                "_id": 0,
                "centro_de_trabalho": 1,
                "inicio_execucao": 1,
                "fim_execucao": 1,
                "inicio_real_hora": 1,
                "causa_do_desvio": 1,
                "duration_min": 1,
            },
        )
        rows = []
        for doc in cursor:
            start_date = doc.get("inicio_execucao")
            if not isinstance(start_date, datetime):
                continue
            start = _combine_date_hour(start_date, doc.get("inicio_real_hora"))
            dur = float(doc.get("duration_min", 0) or 0)
            rows.append({
                "linea":        doc.get("centro_de_trabalho", ""),
                "date":         start,
                "year":         start.year,
                "month":        start.month,
                "year_month":   f"{start.year}-{start.month:02d}",
                "motivo":       str(doc.get("causa_do_desvio", "") or ""),
                "duracao_min":  dur,
                "boundary_case": False,
            })
        return pd.DataFrame(rows)
    except Exception as e:
        logger.warning("_fetch_all_paradas falhou (%s)", e)
        return pd.DataFrame()


def _fetch_avaria_paradas(t_start: datetime, t_end: datetime,
                          codes: list) -> pd.DataFrame:
    """Query direta em ZPP_Paradas com filtro $in de breakdown codes.

    Substitui `fetch_zpp_breakdown_data` (V1) no path do timeline state porque
    V1 retorna `date` como `datetime.date` (linha 463: `inicio.date()`), o que
    faz o isinstance(start_dt, datetime) descartar TODAS as paradas — sintoma
    "switch Só avaria + dia antigo = só verde, paradas sumiram".
    """
    if not _HAS_MONGO:
        return pd.DataFrame()
    try:
        col = get_mongo_connection("ZPP_Paradas")
        if col is None:
            return pd.DataFrame()
        cursor = col.find(
            {
                "_processed": True,
                "causa_do_desvio": {"$in": codes},
                "fim_execucao": {"$gte": t_start, "$lt": t_end},
            },
            {
                "_id": 0,
                "centro_de_trabalho": 1,
                "inicio_execucao": 1,
                "inicio_real_hora": 1,
                "causa_do_desvio": 1,
                "duration_min": 1,
            },
        )
        rows = []
        for doc in cursor:
            base = doc.get("inicio_execucao")
            if not isinstance(base, datetime):
                continue
            start = _combine_date_hour(base, doc.get("inicio_real_hora"))
            rows.append({
                "linea":        doc.get("centro_de_trabalho", ""),
                "date":         start,
                "motivo":       str(doc.get("causa_do_desvio", "") or ""),
                "duracao_min":  float(doc.get("duration_min", 0) or 0),
            })
        return pd.DataFrame(rows)
    except Exception as e:
        logger.warning("_fetch_avaria_paradas falhou (%s)", e)
        return pd.DataFrame()


def _fetch_all_producao(t_start: datetime, t_end: datetime) -> pd.DataFrame:
    """Query direta em ZPP_Producao para o timeline state — mantém hora real.

    `fetch_zpp_production_data` (zpp_kpi_calculator) descarta `hininotif` e
    retorna `date` como `datetime.date` (sem hora) porque KPI mensais não
    precisam de hora. Pro timeline state precisamos da hora real do dia
    (`hininotif` = "HH:MM:SS" combinado com `fininotif`).
    """
    if not _HAS_MONGO:
        return pd.DataFrame()
    try:
        col = get_mongo_connection("ZPP_Producao")
        if col is None:
            return pd.DataFrame()
        cursor = col.find(
            {
                "_processed": True,
                "ffinnotif": {"$gte": t_start, "$lt": t_end},
            },
            {
                "_id": 0,
                "pto_trab": 1,
                "fininotif": 1,
                "hininotif": 1,
                "horasact": 1,
            },
        )
        rows = []
        for doc in cursor:
            base = doc.get("fininotif")
            if not isinstance(base, datetime):
                continue
            start = _combine_date_hour(base, doc.get("hininotif"))
            horas = float(doc.get("horasact", 0) or 0)
            rows.append({
                "linea":        doc.get("pto_trab", ""),
                "date":         start,
                "horasact":     horas,
            })
        return pd.DataFrame(rows)
    except Exception as e:
        logger.warning("_fetch_all_producao falhou (%s)", e)
        return pd.DataFrame()


def _empty_df() -> pd.DataFrame:
    """Schema do DataFrame retornado, vazio (fallback)."""
    return pd.DataFrame(columns=[
        "equipment_id", "label_eq", "y", "start_dt", "end_dt",
        "duration_min", "status", "cod", "desc", "color", "pattern",
    ])
