# -*- coding: utf-8 -*-
"""Parsing dos valores brutos do ALV de HH (BR-10). Puro Python, testável isolado.

O ALV nativo (.xlsx) já chega tipado para a maioria dos campos, mas qualquer valor que
vier como texto precisa do parser PT (ponto=milhar, vírgula=decimal, sinal `-` no fim).
Também identifica a linha de TOTAL do ALV (ordem+operação em branco), que precisa ser
excluída antes de qualquer soma (senão dobra o realizado — BR-10).
"""
from __future__ import annotations

import datetime


def parse_num(v) -> float | None:
    """Lê um número no formato PT/SAP. Trata milhar (.), decimal (,) e negativo no fim.

    Aceita já-numérico (export nativo) ou texto. Retorna float ou None se vazio/ilegível.
    Ex.: '13.900,000' → 13900.0 · '11.000-' → -11000.0 · 105 → 105.0 · '' → None
    """
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    neg = False
    if s.endswith("-"):           # sinal de menos no fim (padrão SAP)
        neg = True
        s = s[:-1].strip()
    elif s.startswith("-"):
        neg = True
        s = s[1:].strip()
    s = s.replace(".", "").replace(",", ".")   # remove milhar, vírgula→ponto decimal
    try:
        n = float(s)
    except ValueError:
        return None
    return -n if neg else n


def parse_min(v) -> int | None:
    """Tempo em minutos (BR-03). Arredonda para inteiro; None se ilegível."""
    n = parse_num(v)
    return None if n is None else int(round(n))


def parse_data(v) -> datetime.datetime | None:
    """Data PT/SAP `dd.mm.aaaa` (ou objeto data nativo do xlsx) → datetime. None se vazio."""
    if v is None or v == "":
        return None
    if isinstance(v, datetime.datetime):
        return v
    if isinstance(v, datetime.date):
        return datetime.datetime(v.year, v.month, v.day)
    s = str(v).strip()
    if not s:
        return None
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def eh_linha_total(row: dict) -> bool:
    """Linha de TOTAL do ALV: ordem (AUFNR) E operação (VORNR) ambas em branco (BR-10).

    Essa linha carrega a somatória do SAP; se entrar no cálculo, DOBRA o realizado.
    """
    ordem = str(row.get("AUFNR", "") or "").strip()
    operacao = str(row.get("VORNR", "") or "").strip()
    return ordem == "" and operacao == ""


def limpar_linhas(rows: list[dict]) -> tuple[list[dict], dict]:
    """Remove a linha de total e linhas-ruído (sem ordem). Retorna (linhas_limpas, info).

    `info` traz a contagem removida para a checagem de sanidade (BR-10): a soma do
    realizado das linhas limpas tem de bater com o total removido.
    """
    limpas = []
    removidas = 0
    for r in rows:
        if eh_linha_total(r):
            removidas += 1
            continue
        if not str(r.get("AUFNR", "") or "").strip():
            removidas += 1     # ruído: sem ordem
            continue
        limpas.append(r)
    return limpas, {"removidas": removidas}
