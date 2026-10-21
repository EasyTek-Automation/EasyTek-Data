# -*- coding: utf-8 -*-
"""Leitura da planilha da ZPPPARADAS → docs do retrato (KPIReport-v2 BR-14 / DS-17).

Módulo SEM imports relativos (só stdlib + openpyxl tardio): pode ser copiado e rodado sozinho
no PC do cliente para validar o export real antes do deploy (IM-32).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, time


def _norm(txt) -> str:
    s = unicodedata.normalize("NFKD", str(txt or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


# coluna lógica → prefixos aceitos do cabeçalho normalizado (rótulo curto do ALV ou longo do export)
_COLS = {
    "linha":     ("linea", "linha"),
    "ordem":     ("ordem", "orden"),
    "data_ini":  ("data inicio", "fecha inicio"),
    "data_fim":  ("data fim", "fecha fin"),
    "hora_ini":  ("hora inicio",),
    "hora_fim":  ("hora fim", "hora fin"),
    "causa":     ("motivo",),
    "descricao": ("descripcao", "descricao"),
    "texto":     ("observacao", "observacion"),
}
_OBRIGATORIAS = ("linha", "ordem", "data_ini", "data_fim", "hora_ini", "hora_fim", "causa")


def _mapear_cabecalho(row) -> dict | None:
    """Índice de cada coluna lógica, ou None se a linha não é o cabeçalho."""
    normed = [_norm(c) for c in row]
    idx = {}
    for chave, prefixos in _COLS.items():
        for i, h in enumerate(normed):
            if h and any(h.startswith(p) for p in prefixos):
                idx.setdefault(chave, i)
                break
    return idx if all(k in idx for k in _OBRIGATORIAS) else None


def _data(v) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v or "").strip()
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def _hora(v) -> time | None:
    if isinstance(v, datetime):
        return v.time().replace(microsecond=0)
    if isinstance(v, time):
        return v.replace(microsecond=0)
    if isinstance(v, (int, float)) and 0 <= v < 1:  # fração de dia (Excel)
        seg = int(round(v * 86400)) % 86400
        return time(seg // 3600, (seg % 3600) // 60, seg % 60)
    s = str(v or "").strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    return None


def _ordem(v) -> int | None:
    s = re.sub(r"\D", "", str(v or "").split(".")[0] if isinstance(v, float) else str(v or ""))
    return int(s) if s else None


def normalizar_linhas(rows, coleta_id: str, coletado_em) -> list[dict]:
    """Linhas cruas da grade (tuplas, cabeçalho incluído) → docs do retrato.

    - acha o cabeçalho pelos rótulos (levanta ValueError se não achar);
    - propaga MOTIVO dentro do grupo (a grade agrupada só o traz na 1ª linha);
    - descarta subtotal/total (linhas sem linha/ordem/início);
    - `duracao_min` = fim − início (a coluna da ZPP arredonda pro minuto; não é usada).
    """
    rows = list(rows)
    idx = None
    corpo = []
    for i, r in enumerate(rows):
        idx = _mapear_cabecalho(r or ())
        if idx:
            corpo = rows[i + 1:]
            break
    if not idx:
        raise ValueError("cabecalho da ZPPPARADAS nao encontrado na planilha")

    def cel(r, k):
        i = idx.get(k)
        return r[i] if i is not None and i < len(r) else None

    docs, motivo_grupo = [], ""
    for r in corpo:
        if not r:
            continue
        causa = str(cel(r, "causa") or "").strip()
        if causa:
            motivo_grupo = causa
        linha = str(cel(r, "linha") or "").strip()
        ordem = _ordem(cel(r, "ordem"))
        di, hi = _data(cel(r, "data_ini")), _hora(cel(r, "hora_ini"))
        df, hf = _data(cel(r, "data_fim")), _hora(cel(r, "hora_fim"))
        if not linha or ordem is None or di is None or hi is None:
            continue  # subtotal / total / linha vazia
        inicio = datetime.combine(di, hi)
        fim = datetime.combine(df, hf) if (df and hf) else None
        dur = round((fim - inicio).total_seconds() / 60.0, 2) if fim else None
        docs.append({
            "linha": linha,
            "ordem": ordem,
            "inicio": inicio,
            "fim": fim,
            "causa": causa or motivo_grupo,
            "descricao_motivo": str(cel(r, "descricao") or "").strip(),
            "texto_operador": str(cel(r, "texto") or "").strip(),
            "duracao_min": dur,
            "coleta_id": coleta_id,
            "coletado_em": coletado_em,
        })
    return docs


def ler_xlsx(path: str):
    import openpyxl  # import tardio: só o robô (Windows) precisa
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return [tuple(r) for r in wb.active.iter_rows(values_only=True)]
    finally:
        wb.close()
