"""Período da aba de custo (BR-18) — resolve o seletor "Período" em meses e gera o rótulo.

Puro (sem Mongo/Dash). O orçamento do SAP é mensal (ZBRCO019), então o período é sempre em
meses inteiros. "Ano inteiro" devolve `None` — quem chama segue passando o `int` do ano,
mantendo o caminho e o cache de hoje. Qualquer outro período vira uma lista de 'YYYY-MM'.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

ANO_INTEIRO = "ano"
PERSONALIZADO = "custom"
ACUMULADO = "acum"

# (valor, rótulo, mês inicial, mês final) — trimestres/semestres do ano escolhido
_FAIXAS = {
    "T1": (1, 3), "T2": (4, 6), "T3": (7, 9), "T4": (10, 12),
    "S1": (1, 6), "S2": (7, 12),
}

OPCOES = [
    {"label": "Ano inteiro", "value": ANO_INTEIRO},
    {"label": "1º trimestre", "value": "T1"},
    {"label": "2º trimestre", "value": "T2"},
    {"label": "3º trimestre", "value": "T3"},
    {"label": "4º trimestre", "value": "T4"},
    {"label": "1º semestre", "value": "S1"},
    {"label": "2º semestre", "value": "S2"},
    {"label": "Acumulado do ano", "value": ACUMULADO},
    {"label": "Personalizado", "value": PERSONALIZADO},
]

_MESES_ABREV = ["jan", "fev", "mar", "abr", "mai", "jun",
                "jul", "ago", "set", "out", "nov", "dez"]


def _ym(ano: int, mes: int) -> str:
    """'YYYY-MM' de (ano, mês)."""
    return f"{ano}-{mes:02d}"


def _intervalo(de: str, ate: str) -> list[str]:
    """Todos os meses 'YYYY-MM' de `de` até `ate` (inclusive); inverte se vierem trocados."""
    if de > ate:
        de, ate = ate, de
    a, m = int(de[:4]), int(de[5:7])
    fim_a, fim_m = int(ate[:4]), int(ate[5:7])
    out = []
    while (a, m) <= (fim_a, fim_m):
        out.append(_ym(a, m))
        m += 1
        if m > 12:
            a, m = a + 1, 1
    return out


def resolver_meses(ano: int, tipo: Optional[str], de: Optional[str] = None,
                   ate: Optional[str] = None, hoje: Optional[date] = None) -> Optional[list[str]]:
    """Meses do período escolhido, ou `None` = ano inteiro (comportamento de hoje).

    - T1–T4 / S1–S2: faixa fixa do `ano` escolhido.
    - Acumulado: jan até o mês de `hoje` se `ano` é o corrente (mês atual entra, BR-18.2);
      ano passado ou futuro → ano inteiro.
    - Personalizado: `de`→`ate` (podem cruzar o ano; invertidos são corrigidos). Sem os dois
      preenchidos → ano inteiro (não deixa a tela vazia no meio da escolha).
    """
    hoje = hoje or date.today()
    if tipo in _FAIXAS:
        ini, fim = _FAIXAS[tipo]
        return [_ym(ano, m) for m in range(ini, fim + 1)]
    if tipo == ACUMULADO:
        if ano != hoje.year:
            return None
        return [_ym(ano, m) for m in range(1, hoje.month + 1)]
    if tipo == PERSONALIZADO:
        if not de or not ate:
            return None
        return _intervalo(de, ate)
    return None


def rotulo_mes(ym: str) -> str:
    """'2026-03' → 'mar/2026'."""
    return f"{_MESES_ABREV[int(ym[5:7]) - 1]}/{ym[:4]}"


def rotulo(ano: int, meses: Optional[list[str]]) -> str:
    """Texto do período p/ títulos: '2026' (ano inteiro), 'mar/2026', 'jan–mar/2026',
    'nov/2025–fev/2026'."""
    if not meses:
        return str(ano)
    ini, fim = meses[0], meses[-1]
    if ini == fim:
        return rotulo_mes(ini)
    if ini[:4] == fim[:4]:
        return f"{_MESES_ABREV[int(ini[5:7]) - 1]}–{rotulo_mes(fim)}"
    return f"{rotulo_mes(ini)}–{rotulo_mes(fim)}"
