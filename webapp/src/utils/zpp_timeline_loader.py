"""ZPP Timeline Loader — eventos da timeline a partir de ZPP_Paradas + ZPP_Producao.

DS-06 / IM-07: combina paradas (com código) + gaps de produção (verde) em DataFrame
unificado pronto pra renderização Plotly do timeline evocon-style na V2 e home.

DS-07 / IM-08: `_classify_status(code)` mapeia código SAP → categoria visual.
"""

from datetime import datetime, timedelta
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
            # Caminho otimizado quando switch ON: usa fetch V1 com filtro
            brk_df = fetch_zpp_breakdown_data(t_start, t_end, breakdown_codes=breakdown_codes)
        else:
            # Switch OFF: precisa todos os códigos — query direta sem filtro $in
            brk_df = _fetch_all_paradas(t_start, t_end)

        # 3. Buscar produção
        prod_df = fetch_zpp_production_data(t_start, t_end)

        # 4. Construir DataFrame por equipamento
        rows = []
        for y_idx, (eq_id, label) in enumerate(sorted(names.items())):
            # Eventos de parada do equipamento
            eq_brk = brk_df[brk_df.get("linea") == eq_id] if not brk_df.empty else pd.DataFrame()
            for _, row in eq_brk.iterrows():
                start_dt = row.get("date")  # já vem como datetime no fetch V1
                if not isinstance(start_dt, datetime):
                    continue
                dur_min = float(row.get("duracao_min", 0) or 0)
                if dur_min <= 0:
                    continue
                end_dt = start_dt + timedelta(minutes=dur_min)
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

            # 5. Gaps de produção (verde) — derivados de ZPP_Producao
            eq_prod = prod_df[prod_df.get("linea") == eq_id] if not prod_df.empty else pd.DataFrame()
            for _, prod_row in eq_prod.iterrows():
                # Cada doc de ZPP_Producao é uma janela de operação contígua
                # Aproximação: janela inteira é "producao" (refinar com gaps de paradas é TODO)
                p_start = prod_row.get("date")
                horas = float(prod_row.get("horasact", 0) or 0)
                if not isinstance(p_start, datetime) or horas <= 0:
                    continue
                p_end = p_start + timedelta(hours=horas)
                # Clampar à janela
                p_start = max(p_start, t_start)
                p_end = min(p_end, t_end)
                if p_end <= p_start:
                    continue
                rows.append({
                    "equipment_id": eq_id,
                    "label_eq":     label,
                    "y":            y_idx,
                    "start_dt":     p_start,
                    "end_dt":       p_end,
                    "duration_min": (p_end - p_start).total_seconds() / 60,
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
    Retorna DataFrame com schema compatível com fetch_zpp_breakdown_data da V1.
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
                "causa_do_desvio": 1,
                "duration_min": 1,
            },
        )
        rows = []
        for doc in cursor:
            start = doc.get("inicio_execucao")
            if not isinstance(start, datetime):
                continue
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


def _empty_df() -> pd.DataFrame:
    """Schema do DataFrame retornado, vazio (fallback)."""
    return pd.DataFrame(columns=[
        "equipment_id", "label_eq", "y", "start_dt", "end_dt",
        "duration_min", "status", "cod", "desc", "color", "pattern",
    ])
