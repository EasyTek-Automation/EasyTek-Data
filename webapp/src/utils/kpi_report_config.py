"""Constantes, funções puras e helpers de formatação do KPIReport.

Camada de configuração compartilhada — sem I/O, sem dependência de Dash/Mongo.
Editável pelo desenvolvedor; mudanças exigem rebuild do container.

Origem: projeto SDD KPIReport (DS-01 / DS-02 / DS-05) — implementado em IM-03.
"""
from __future__ import annotations

import logging
import math
import os
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.utils.zpp_kpi_calculator import BREAKDOWN_CODES  # símbolo canônico — RV-01 G4

logger = logging.getLogger(__name__)


# =========================================================================
# Constantes — janelas, fuso, locale (BR-01, BR-02, BR-08, SP-19)
# =========================================================================
PERIODO_RELATORIO_MODO: str = "MES_CORRENTE"  # ou "ULTIMOS_30_DIAS"
TZ_FALLBACK: str = "America/Sao_Paulo"
FUSO_LABEL: str = "horário de Brasília"

# =========================================================================
# Constantes — escopo de equipamentos (BR-05)
# =========================================================================
# Lista vazia — BR-05 item 3 desativada em 2026-05-13 (IM-07): tela inclui
# DECAP001 nos KPIs de planta; invariante de equivalência tela ↔ relatório
# prevalece. Texto original do item 3 movido para `## Desativadas` no
# `02-business-rules.md`. Lista permanece editável caso futura regra exija.
EQUIPAMENTOS_EXCLUIDOS: list[str] = []

# =========================================================================
# Constantes — performance e timeout (BR-09, SP-12, RV-03)
# =========================================================================
LATENCIA_GUIDELINE_S: float = 10.0   # log WARNING ao ultrapassar (sem aborto)
TIMEOUT_GERACAO_S: float = 60.0      # aborto duro via ThreadPoolExecutor

# =========================================================================
# Constantes — template (SP-06 D6)
# =========================================================================
TEMPLATE_PATH_DEFAULT: str = "src/assets/templates/kpi_report.docx"

# =========================================================================
# Constantes — labels visuais dos KPIs (SP-13)
# =========================================================================
KPI_LABELS: dict[str, str] = {
    "mtbf": "MTBF",
    "mttr": "MTTR",
    "taxa_avaria": "Taxa de Avaria",
}


# =========================================================================
# Fuso horário (BR-08, SP-03)
# =========================================================================

def _resolve_timezone() -> ZoneInfo:
    """Retorna ZoneInfo da env `TZ`; cai para TZ_FALLBACK em nome inválido (SP-17 L3)."""
    tz_name = os.environ.get("TZ", TZ_FALLBACK)
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        logger.warning("TZ inválida (%r); usando fallback %r", tz_name, TZ_FALLBACK)
        return ZoneInfo(TZ_FALLBACK)


def _now_in_report_timezone() -> datetime:
    """`datetime.now()` aware no fuso resolvido — substituível em testes via mock."""
    return datetime.now(tz=_resolve_timezone())


# =========================================================================
# Janelas temporais (BR-01, BR-02, SP-03)
# =========================================================================

def compute_monthly_window(
    now: datetime,
    modo: Optional[str] = None,
) -> tuple[datetime, datetime]:
    """Janela mensal `(inicio, fim)` em datetimes naïve compatíveis com pipeline ZPP.

    Modo `MES_CORRENTE` retorna `[1º 00:00, hoje 00:00)`; `ULTIMOS_30_DIAS` retorna
    `[now-30d, now]`. Naïve consistente com regime do Mongo (RV-04). Lança `ValueError`
    se `modo` não for reconhecido.
    """
    modo = modo or PERIODO_RELATORIO_MODO

    if modo == "MES_CORRENTE":
        # [1º do mês 00:00, hoje 00:00) — exclui dia atual parcial (BR-01 item 1)
        inicio = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        fim = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif modo == "ULTIMOS_30_DIAS":
        # [now-30d, now] — janela rolante incluindo dia parcial (BR-01 item 2)
        inicio = now - timedelta(days=30)
        fim = now
    else:
        raise ValueError(f"Modo inválido: {modo!r}")

    return inicio.replace(tzinfo=None), fim.replace(tzinfo=None)


def compute_last_24h_window(now: datetime) -> tuple[datetime, datetime]:
    """Janela do dia anterior cheio `[ontem 00:00, hoje 00:00)` (BR-02).

    Independente da hora do clique — janela alinhada ao calendário. Retorna tupla naïve.
    """
    hoje_meianoite = now.replace(hour=0, minute=0, second=0, microsecond=0)
    ontem_meianoite = hoje_meianoite - timedelta(days=1)
    return ontem_meianoite.replace(tzinfo=None), hoje_meianoite.replace(tzinfo=None)


# =========================================================================
# Nome do arquivo de download (SP-05)
# =========================================================================

def gerar_nome_arquivo(
    agora: datetime,
    modo: Optional[str] = None,
) -> str:
    """Gera `kpi-report_<YYYY-MM-DD>_<modo-com-hifen>.docx` (SP-05).

    `agora` aware no fuso configurado; `modo` opcional (lê `PERIODO_RELATORIO_MODO` se None).
    """
    modo = modo or PERIODO_RELATORIO_MODO
    data_str = agora.strftime("%Y-%m-%d")
    modo_str = modo.lower().replace("_", "-")
    return f"kpi-report_{data_str}_{modo_str}.docx"


# =========================================================================
# Formatação (SP-19 — locale pt_BR)
# =========================================================================

def fmt_numero(valor: Optional[float], casas: int = 1) -> str:
    """Formata número em locale pt_BR — vírgula decimal, ponto milhar.

    None / NaN / Inf retornam `"N/D"` (SP-19, BR-07). Usa replace manual
    em vez de `locale.setlocale` para evitar dependência de locale do sistema.
    """
    if valor is None:
        return "N/D"
    try:
        if math.isnan(valor) or math.isinf(valor):
            return "N/D"
    except (TypeError, ValueError):
        return "N/D"

    formatado = f"{valor:,.{casas}f}"
    # Converte separadores en_US → pt_BR (3-step swap via placeholder)
    return formatado.replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_data(dt: datetime) -> str:
    """Formata datetime como `DD/MM/AAAA`."""
    return dt.strftime("%d/%m/%Y")


def fmt_data_hora(dt: datetime) -> str:
    """Formata datetime como `DD/MM/AAAA HH:MM` 24h."""
    return dt.strftime("%d/%m/%Y %H:%M")
