"""
Schema e helpers para o log de processamento do ZPP Processor.
Um documento por arquivo processado — não por job.
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

_BRT = ZoneInfo("America/Sao_Paulo")


class BRTFormatter(logging.Formatter):
    """Formatter com timestamp em America/Sao_Paulo (offset -03:00)."""

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=_BRT)
        return dt.strftime("%Y-%m-%dT%H:%M:%S%z")


def _fmt(dt: datetime) -> str:
    """Converte datetime para ISO 8601 com offset -03:00."""
    return dt.astimezone(_BRT).isoformat()


def build_log_doc(
    arquivo: str,
    tipo: str,
    canal: str,
    operador: str,
    justificativa: str | None,
    mes_referencia: str,
    iniciado_em: datetime,
    finalizado_em: datetime,
    status: str,
    registros_inseridos: int = 0,
    registros_deletados: int = 0,
    strays_descartados: list | None = None,
    duplicatas_ignoradas: int = 0,
    inconsistencias: list | None = None,
    motivo_rejeicao: str | None = None,
    erro: str | None = None,
) -> dict:
    """Constrói o documento de log para inserção no MongoDB."""
    return {
        "arquivo":              arquivo,
        "tipo":                 tipo,
        "canal":                canal,
        "operador":             operador,
        "justificativa":        justificativa,
        "mes_referencia":       mes_referencia,
        "iniciado_em":          _fmt(iniciado_em),
        "finalizado_em":        _fmt(finalizado_em),
        "status":               status,
        "registros_inseridos":  registros_inseridos,
        "registros_deletados":  registros_deletados,
        "strays_descartados":   strays_descartados or [],
        "duplicatas_ignoradas": duplicatas_ignoradas,
        "inconsistencias":      inconsistencias or [],
        "motivo_rejeicao":      motivo_rejeicao,
        "erro":                 erro,
    }
