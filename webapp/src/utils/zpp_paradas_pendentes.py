# -*- coding: utf-8 -*-
"""Paradas pendentes de consolidação na NT0001 (KPIReport-v2 BR-14 / SP-26 / DS-19).

A NT0001 (coleção `ZPP_Paradas`, fonte oficial dos indicadores) só traz a parada quando a
confirmação da ordem é lançada — até ~1 dia depois. O robô SAP grava em `ZPP_Paradas_Lancadas`
um retrato da ZPPPARADAS, que mostra a parada assim que o operador a registra. Pendente = parada
do retrato sem correspondente na oficial pela chave `linha + ordem + data/hora de início` exata.

Pendentes existem SÓ nas listas de paradas do relatório; nunca entram em indicador nenhum.
Qualquer falha vira log de aviso + lista vazia: o relatório nunca quebra por causa disto.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

RETRATO_COLLECTION = "ZPP_Paradas_Lancadas"
META_ID = "meta"

# Textos únicos do selo e da legenda (tela V2, DOCX e PDF — SP-27). PT-only (SP-23 revisado).
SELO = "⏳ PENDENTE"
LEGENDA = ("⏳ PENDENTE = parada lançada na ZPP Paradas, ainda não consolidada na NT0001 — "
           "não considerada no cálculo dos indicadores.")


def _get_coll(name: str):
    """Collection Mongo (import tardio — mantém o módulo importável nos testes sem Mongo)."""
    from src.database.connection import get_mongo_connection
    return get_mongo_connection(name)


def _ordem_int(v) -> Optional[int]:
    """Ordem de produção como inteiro — o SAP manda com zeros à esquerda (`000010624555`)."""
    if isinstance(v, (int,)) and not isinstance(v, bool):
        return v
    if isinstance(v, float):
        return int(v)
    s = re.sub(r"\D", "", str(v or ""))
    return int(s) if s else None


def _hora_str(v) -> str:
    """Normaliza a hora oficial (`inicio_real_hora`) para `HH:MM:SS`."""
    s = str(v or "").strip()
    partes = s.split(":")
    try:
        h = int(partes[0]); m = int(partes[1]) if len(partes) > 1 else 0
        sec = int(partes[2]) if len(partes) > 2 else 0
        return f"{h:02d}:{m:02d}:{sec:02d}"
    except (ValueError, IndexError):
        return s


def retrato_valido(agora: datetime) -> tuple[bool, Optional[datetime]]:
    """(ok, coletado_em) — o retrato só vale se a última coleta for do mesmo dia de `agora`."""
    try:
        meta = _get_coll(RETRATO_COLLECTION).find_one({"_id": META_ID}) or {}
    except Exception:
        logger.warning("retrato ZPPPARADAS: falha ao ler meta", exc_info=True)
        return False, None
    coletado = meta.get("coletado_em")
    if not isinstance(coletado, datetime):
        return False, None
    hoje = (agora.replace(tzinfo=None) if agora.tzinfo else agora).date()
    return coletado.date() == hoje, coletado


def aviso_checagem(coletado_em: Optional[datetime]) -> str:
    """Nota discreta quando a checagem não pôde ser feita (SP-28)."""
    if coletado_em is None:
        return "Checagem de paradas pendentes indisponível — nenhuma coleta da ZPP Paradas registrada."
    return ("Checagem de paradas pendentes indisponível — última coleta "
            f"{coletado_em.strftime('%d/%m %H:%M')}.")


def _chaves_oficiais(ini: datetime, fim: datetime) -> set:
    """Chaves `(linha, ordem, data, HH:MM:SS)` de TODAS as paradas oficiais da janela.

    Sem filtro de causa: se a parada já está na NT0001 com outro código (ex: `401` × `S401`),
    ela não é pendente.
    """
    dia_ini = ini.replace(hour=0, minute=0, second=0, microsecond=0)
    cur = _get_coll("ZPP_Paradas").find(
        {"inicio_execucao": {"$gte": dia_ini, "$lt": fim}},
        {"centro_de_trabalho": 1, "ordem": 1, "inicio_execucao": 1, "inicio_real_hora": 1, "_id": 0},
    )
    chaves = set()
    for r in cur:
        d = r.get("inicio_execucao")
        if not isinstance(d, datetime):
            continue
        chaves.add((str(r.get("centro_de_trabalho") or "").strip(), _ordem_int(r.get("ordem")),
                    d.date(), _hora_str(r.get("inicio_real_hora"))))
    return chaves


def buscar_pendentes(ini: datetime, fim: datetime,
                     breakdown_codes: Optional[list] = None,
                     equipamentos_excluidos: Optional[list] = None) -> list[dict]:
    """Avarias do retrato com início em `[ini, fim)` que ainda não estão na `ZPP_Paradas`.

    Mesmos filtros da lista oficial (`fetch_top_breakdowns_all`): códigos de avaria e
    equipamentos excluídos. Devolve no formato daquela função + `pendente=True`.
    """
    from src.utils.zpp_kpi_calculator import BREAKDOWN_CODES, KPI_FORCE_ZERO_EQUIPMENTS
    codes = BREAKDOWN_CODES if breakdown_codes is None else breakdown_codes
    if equipamentos_excluidos is None:
        from src.utils.kpi_report_config import EQUIPAMENTOS_EXCLUIDOS
        equipamentos_excluidos = EQUIPAMENTOS_EXCLUIDOS
    excl = set(equipamentos_excluidos) | set(KPI_FORCE_ZERO_EQUIPMENTS)

    try:
        q = {"_id": {"$ne": META_ID}, "causa": {"$in": list(codes)},
             "inicio": {"$gte": ini, "$lt": fim}}
        if excl:
            q["linha"] = {"$nin": sorted(excl)}
        candidatas = list(_get_coll(RETRATO_COLLECTION).find(q, {"_id": 0}))
        if not candidatas:
            return []
        oficiais = _chaves_oficiais(ini, fim)
    except Exception:
        logger.warning("paradas pendentes: falha na consulta — seguindo só com oficiais", exc_info=True)
        return []

    out = []
    for c in candidatas:
        inicio = c.get("inicio")
        if not isinstance(inicio, datetime):
            continue
        chave = (str(c.get("linha") or "").strip(), _ordem_int(c.get("ordem")),
                 inicio.date(), inicio.strftime("%H:%M:%S"))
        if chave in oficiais:
            continue
        dur = c.get("duracao_min")
        out.append({
            "equipamento": chave[0],
            "inicio_execucao": inicio,
            "duration_min": float(dur) if dur is not None else 0.0,
            "causa_do_desvio": c.get("causa", ""),
            "descricao": c.get("texto_operador") or c.get("descricao_motivo") or "",
            "pendente": True,
        })
    return out
