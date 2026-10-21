# -*- coding: utf-8 -*-
"""Agregação por operação (AUFNR+VORNR) das linhas brutas de HH. Puro Python, testável.

- Planejado (IW37): `ARBEI` é atributo da operação e se repete em cada linha → toma valor
  ÚNICO (dedup), NUNCA soma (BR-03).
- Realizado (IW47): `ISMNW` é apontamento → SOMA todas as confirmações da operação (BR-03).

Cada operação vira um doc da collection-fonte (`sap_hh_planejado` / `sap_hh_realizado`),
carimbado com `coleta_id`/`coletado_em`. A união planejado×realizado e a agregação por
ordem acontecem na leitura (webapp), não aqui.
"""
from __future__ import annotations

from . import _parse


def _chave(row: dict) -> tuple[str, str]:
    """Chave da operação = (AUFNR, VORNR) normalizados (BR-02)."""
    return (str(row.get("AUFNR", "") or "").strip(),
            str(row.get("VORNR", "") or "").strip())


def agregar_planejado(rows: list[dict], coleta_id: str, coletado_em) -> tuple[list[dict], dict]:
    """Agrupa IW37 por operação; planejado_min = ARBEI deduplicado (valor único — BR-03).

    Retorna (docs, info). `info.total_planejado_min` = soma do planejado (sanidade).
    """
    limpas, info = _parse.limpar_linhas(rows)
    por_op: dict[tuple[str, str], dict] = {}
    for r in limpas:
        k = _chave(r)
        if k in por_op:
            continue   # dedup: planejado é único por operação (não soma)
        plan = _parse.parse_min(r.get("ARBEI"))
        por_op[k] = {
            "ordem": k[0],
            "operacao": k[1],
            "texto_op": (str(r.get("LTXA1", "") or "").strip() or None),  # descrição da operação
            "planejado_min": plan if plan is not None else 0,
            "centro_planejado": (str(r.get("ARBPL", "") or "").strip().upper() or None),
            "data_inicio_plan": _parse.parse_data(r.get("FSAVD")),
            "coleta_id": coleta_id,
            "coletado_em": coletado_em,
        }
    docs = list(por_op.values())
    info["total_planejado_min"] = sum(d["planejado_min"] for d in docs)
    info["operacoes"] = len(docs)
    return docs, info


def agregar_realizado(rows: list[dict], coleta_id: str, coletado_em) -> tuple[list[dict], dict]:
    """Agrupa IW47 por operação; realizado_min = Σ ISMNW (soma das confirmações — BR-03).

    Guarda executores distintos (siglas que apontaram) e o status do SAP (STTXT).

    Também acumula `realizado_por_dia` = {"AAAA-MM-DD": Σ ISMNW naquele dia}, usando a data de
    execução do apontamento `ISDD` (fallback `BUDAT` quando `ISDD` vazio). Confirmações sem
    nenhuma das duas datas contam no total `realizado_min`, mas NÃO entram no `realizado_por_dia`
    (não há dia onde colocá-las) — por isso Σ(realizado_por_dia) ≤ realizado_min. Campo aditivo:
    o total e os demais campos permanecem idênticos; consumidores que só leem `realizado_min`
    (aderência das entregas, webapp) não são afetados. Fonte da granularidade diária do relatório
    de mão de obra (KPIReport-v2 BR-13/DS-13).

    Retorna (docs, info). `info.total_realizado_min` = soma (checagem de sanidade BR-10).
    """
    limpas, info = _parse.limpar_linhas(rows)
    por_op: dict[tuple[str, str], dict] = {}
    for r in limpas:
        k = _chave(r)
        d = por_op.get(k)
        if d is None:
            d = {
                "ordem": k[0],
                "operacao": k[1],
                "realizado_min": 0,
                "realizado_por_dia": {},
                "executores": [],
                "status_sap": (str(r.get("STTXT", "") or "").strip() or None),
                "coleta_id": coleta_id,
                "coletado_em": coletado_em,
            }
            por_op[k] = d
        real = _parse.parse_min(r.get("ISMNW"))
        if real is not None:
            d["realizado_min"] += real          # soma das confirmações (BR-03)
            # quebra por dia de execução (ISDD; fallback BUDAT). Sem data → só entra no total.
            dia = _parse.parse_data(r.get("ISDD")) or _parse.parse_data(r.get("BUDAT"))
            if dia is not None:
                chave = dia.strftime("%Y-%m-%d")
                d["realizado_por_dia"][chave] = d["realizado_por_dia"].get(chave, 0) + real
        sigla = (str(r.get("PERNR", "") or "").strip()
                 or str(r.get("NAME", "") or "").strip())
        if sigla and sigla not in d["executores"]:
            d["executores"].append(sigla)
        st = (str(r.get("STTXT", "") or "").strip() or None)
        if st:
            d["status_sap"] = st                # último status visto (atualiza)
    docs = list(por_op.values())
    info["total_realizado_min"] = sum(d["realizado_min"] for d in docs)
    info["operacoes"] = len(docs)
    return docs, info


def checar_sanidade_total(rows_brutas: list[dict], total_calculado: int, campo: str) -> bool:
    """Sanidade BR-10: a soma calculada bate com a linha de total do ALV (se houver)?

    A linha de total tem AUFNR+VORNR em branco e carrega a somatória no `campo`.
    Retorna True se não há linha de total OU se bate; False se diverge (não publicar).
    """
    total_alv = None
    for r in rows_brutas:
        if _parse.eh_linha_total(r):
            total_alv = _parse.parse_min(r.get(campo))
            break
    if total_alv is None:
        return True   # sem linha de total explícita → nada a conferir
    return abs(total_alv - total_calculado) <= 1   # tolerância de arredondamento
