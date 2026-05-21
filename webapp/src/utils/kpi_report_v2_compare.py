"""KPIReport-v2 — cálculo de delta período-vs-período (DS-05, SP-14).

Funções puras — sem I/O, sem Mongo, sem Dash. Recebe valores já calculados
e devolve estrutura ∆_abs / ∆_pct / direção / favorabilidade pra UI consumir.

Convenções:
- MTBF↑ é favorável; MTTR↓ favorável; Taxa de Avaria↓ favorável.
- Δ < 1% absoluto é considerado "estável" (direction="flat").
- Sem base (anterior=0 ou None) gera direction="na" com sinalização adequada.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional


KPI_NAMES: tuple[str, ...] = ("mtbf", "mttr", "breakdown_rate")
"""KPIs comparáveis. Outros nomes são tratados como neutros."""

FLAT_THRESHOLD_PCT: float = 1.0
"""Δ% absoluto abaixo deste valor é tratado como 'estável' (sem direção)."""


def is_favorable(kpi: str, direction: str) -> Optional[bool]:
    """Direção é favorável para o KPI?

    - MTBF: up → True, down → False
    - MTTR: up → False, down → True
    - breakdown_rate: up → False, down → True
    - flat/na: None (sem julgamento)
    - kpi desconhecido: None
    """
    if direction in ("flat", "na"):
        return None
    if kpi == "mtbf":
        if direction == "up":
            return True
        if direction == "down":
            return False
    elif kpi in ("mttr", "breakdown_rate"):
        if direction == "up":
            return False
        if direction == "down":
            return True
    return None


def compute_period_delta(atual: Optional[float], anterior: Optional[float],
                          kpi: str) -> dict:
    """Calcula delta absoluto, percentual, direção e favorabilidade.

    Casos especiais:
    - atual=None ou anterior=None → direction="na", delta None.
    - anterior=0 e atual>0 → direction="up" (sem base de %), delta_pct=None marcado "novo".
    - atual=0 e anterior>0 → direction="down", delta_pct=-100.
    - |delta_pct| < FLAT_THRESHOLD_PCT → direction="flat".
    """
    out = {
        "delta_abs":      None,
        "delta_pct":      None,
        "direction":      "na",
        "favorable":      None,
        "anterior_value": anterior,
        "atual_value":    atual,
        "is_new":         False,
    }

    if atual is None or anterior is None:
        return out

    delta_abs = float(atual) - float(anterior)
    out["delta_abs"] = delta_abs

    # Anterior zero — sem base pra %. Marca "novo" se atual>0.
    if anterior == 0:
        if atual > 0:
            out["direction"] = "up"
            out["is_new"] = True
        elif atual == 0:
            out["direction"] = "flat"
        else:
            out["direction"] = "down"
            out["is_new"] = True
        out["favorable"] = is_favorable(kpi, out["direction"])
        return out

    delta_pct = (delta_abs / abs(float(anterior))) * 100.0
    out["delta_pct"] = delta_pct

    if abs(delta_pct) < FLAT_THRESHOLD_PCT:
        out["direction"] = "flat"
    elif delta_abs > 0:
        out["direction"] = "up"
    else:
        out["direction"] = "down"

    out["favorable"] = is_favorable(kpi, out["direction"])
    return out


def fetch_anterior_monthly_window(
    window_atual: tuple[datetime, datetime],
) -> tuple[datetime, datetime]:
    """Janela do mês anterior usando a duração da janela atual.

    Estratégia: end_anterior = start_atual; start_anterior = end_anterior - duração.
    Mantém comparabilidade com janelas tipo `MES_CORRENTE` (parciais).
    """
    start_atual, end_atual = window_atual
    if start_atual > end_atual:
        raise ValueError("window_atual: start > end")
    duracao = end_atual - start_atual
    end_anterior = start_atual
    start_anterior = end_anterior - duracao
    return start_anterior, end_anterior


def fetch_anterior_last24h_window(
    window_atual: tuple[datetime, datetime],
) -> tuple[datetime, datetime]:
    """Janela das 24h anteriores à janela 24h atual.

    Assume `window_atual = [ontem 00:00, hoje 00:00)`. Retorna
    `[anteontem 00:00, ontem 00:00)` — mesma duração, alinhado ao calendário (BR-02).
    """
    start_atual, end_atual = window_atual
    if start_atual > end_atual:
        raise ValueError("window_atual: start > end")
    duracao = end_atual - start_atual
    return start_atual - duracao, start_atual


def build_compare_dict(atual_kpis: dict, anterior_kpis: dict) -> dict:
    """Constrói o contrato `store-kpi-v2-compare` para um período.

    `atual_kpis` / `anterior_kpis` esperam chaves {'mtbf', 'mttr', 'breakdown_rate'}.
    Cada valor é `Optional[float]`. Retorna dict com mesmas chaves apontando
    para o resultado de `compute_period_delta`.
    """
    return {
        kpi: compute_period_delta(atual_kpis.get(kpi), anterior_kpis.get(kpi), kpi)
        for kpi in KPI_NAMES
    }
