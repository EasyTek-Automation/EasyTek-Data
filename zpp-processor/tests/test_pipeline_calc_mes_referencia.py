"""Regressão do bug 2026-06-01: operator precedence em _calc_mes_referencia
rejeitava 100% dos arquivos quando today.day == 1.

Bug: `if ratio < config.MIN_REFERENCE_MONTH_RATIO if hasattr(...) else 0.80`
era parseado como `if (ratio < ???) if hasattr(...) else (0.80)`; com a constante
ausente em config, a condição inteira colapsava para 0.80 (truthy) e qualquer
ratio era rejeitado.
"""
from datetime import datetime

import pandas as pd
import pytest

from pipeline import RejectionError, _calc_mes_referencia


def _df_zppprd(distribuicao: list[tuple[str, int]]) -> pd.DataFrame:
    """Constrói DataFrame zppprd com N timestamps por mês.

    distribuicao: lista de (mes_ref, qtd) ex: [("2026-05", 80), ("2026-06", 20)]
    """
    rows = []
    for mes_ref, qtd in distribuicao:
        year, month = map(int, mes_ref.split("-"))
        for i in range(qtd):
            day = (i % 27) + 1
            rows.append(pd.Timestamp(year=year, month=month, day=day, hour=12))
    return pd.DataFrame({"ffinnotif": rows})


def test_dia_1_ratio_100_aceito_retorna_mes_anterior():
    """Regressão direta do bug: 100% em maio, processado em 01/jun → aceitar."""
    df = _df_zppprd([("2026-05", 100)])
    today = datetime(2026, 6, 1)

    result = _calc_mes_referencia(df, tipo="zppprd", today=today)

    assert result == "2026-05"


def test_dia_1_ratio_80_aceito_limite_inferior():
    """80% no mês dominante anterior é o limite — deve ser aceito (ratio < 0.80 é False)."""
    df = _df_zppprd([("2026-05", 80), ("2026-06", 20)])
    today = datetime(2026, 6, 1)

    result = _calc_mes_referencia(df, tipo="zppprd", today=today)

    assert result == "2026-05"


def test_dia_1_ratio_79_rejeitado_abaixo_do_limite():
    """79% no mês dominante é abaixo do threshold de 80% — deve rejeitar."""
    df = _df_zppprd([("2026-05", 79), ("2026-06", 21)])
    today = datetime(2026, 6, 1)

    with pytest.raises(RejectionError, match="79%"):
        _calc_mes_referencia(df, tipo="zppprd", today=today)


def test_dia_qualquer_que_nao_seja_1_retorna_mes_corrente():
    """Fora da janela do dia 1 nem entra na lógica de threshold."""
    df = _df_zppprd([("2026-05", 100)])
    today = datetime(2026, 6, 15)

    result = _calc_mes_referencia(df, tipo="zppprd", today=today)

    assert result == "2026-06"


def test_dia_1_ratio_100_mes_corrente_aceito():
    """100% em junho, processado em 01/jun (atípico) → mês corrente também é aceito."""
    df = _df_zppprd([("2026-06", 100)])
    today = datetime(2026, 6, 1)

    result = _calc_mes_referencia(df, tipo="zppprd", today=today)

    assert result == "2026-06"
