# -*- coding: utf-8 -*-
"""Derivações de classificação do backlog (DS-03). Puro Python, testável isolado.

A partir do tipo da ordem (AUART) e do centro da operação 0010 (ARBPL), deriva:
  - categoria       (por tipo)              — sempre presente
  - disciplina      (por prefixo do centro) — só Preventiva/Corretiva, senão None
  - subclassificacao(por dígito do centro)  — só ordens em Z10-Z23, senão None

Regras: BR-02 (categoria), BR-04 (disciplina), BR-05 (subclassificação), BR-06 (não-class).
"""
from __future__ import annotations

# BR-02 — tipo de ordem (AUART) → categoria. Tipos fora deste mapa não entram no backlog.
CATEGORIA = {
    "YPM2": "Preventiva",
    "YPM1": "Corretiva",
    "YPM8": "Melhoria",
    "YPM9": "Matrizes",
}

# categorias que recebem quebra por disciplina/subclassificação (BR-04)
_CATEGORIAS_COM_DISCIPLINA = frozenset({"Preventiva", "Corretiva"})

# BR-05 — dígito final do centro Zxy → subclassificação (estratégia de manutenção)
_SUBCLASS = {"0": "Corretiva", "1": "PDCA", "2": "CorretivaProgramada", "3": "Preditiva"}


def derivar_categoria(tipo: str):
    """YPM2→Preventiva, YPM1→Corretiva, YPM8→Melhoria, YPM9→Matrizes. Outros→None."""
    return CATEGORIA.get((tipo or "").strip().upper())


# centros-texto (não-Z) com disciplina conhecida (descoberto no dado real, decisão 2026-06-27)
_CENTRO_MECANICA = frozenset({"MEC"})
_CENTRO_ELETRICA = frozenset()


def derivar_disciplina(centro: str):
    """Disciplina pelo centro da operação 0010 — vale para TODAS as categorias
    (revisão 2026-06-27: melhoria/matrizes também recebem disciplina).

    Mecanica: Z1x ou centro-texto mecânico (MEC). Eletrica: Z2x. Demais (Z02, Z01,
    Z03, Z04, MAN, sem centro): NaoClassificado.
    """
    c = (centro or "").strip().upper()
    if c.startswith("Z1") or c in _CENTRO_MECANICA:
        return "Mecanica"
    if c.startswith("Z2") or c in _CENTRO_ELETRICA:
        return "Eletrica"
    return "NaoClassificado"


def derivar_subclassificacao(centro: str):
    """Corretiva|PDCA|CorretivaProgramada|Preditiva pelo dígito do centro Z10-Z23.
    Centros fora do esquema (Z02/Z01/Z03/Z04/MAN/MEC/sem centro) → None."""
    c = (centro or "").strip().upper()
    if c[:2] not in ("Z1", "Z2") or len(c) < 3:
        return None
    return _SUBCLASS.get(c[2])


def local_pai(cod: str) -> str:
    """Local-pai = 2 primeiros segmentos do TPLNR. Ex: 'BR02-0700-0200' → 'BR02-0700'
    (agrupa sub-locais sob o equipamento/linha-pai). Código com <2 segmentos → ele mesmo."""
    parts = (cod or "").strip().split("-")
    return "-".join(parts[:2]) if len(parts) >= 2 else (cod or "").strip()


def montar_doc(ordem: dict, coleta_id: str, coletado_em) -> dict:
    """Monta o documento Mongo (DS-02) a partir de uma ordem crua da coleta SAP.

    `ordem` cru (do _coleta): ordem, tipo, descricao, local_instalacao, data_inicio,
    centro_operacao_0010.
    """
    tipo = (ordem.get("tipo") or "").strip().upper()
    centro = (ordem.get("centro_operacao_0010") or "").strip().upper()
    categoria = derivar_categoria(tipo)
    return {
        "ordem": str(ordem.get("ordem", "")).strip(),
        "tipo": tipo,
        "categoria": categoria,
        "descricao": ordem.get("descricao", ""),
        "local_instalacao": ordem.get("local_instalacao", ""),
        "local_descricao": ordem.get("local_descricao", ""),
        "local_pai": local_pai(ordem.get("local_instalacao", "")),
        "data_inicio": ordem.get("data_inicio"),  # datetime ou None
        "centro_operacao_0010": centro or None,
        "disciplina": derivar_disciplina(centro),
        "subclassificacao": derivar_subclassificacao(centro),
        "coleta_id": coleta_id,
        "coletado_em": coletado_em,
    }


def filtrar_categorias_validas(ordens: list) -> list:
    """Mantém só ordens cujo tipo está no mapa CATEGORIA (descarta PM04/ZPM*/etc — BR-02)."""
    return [o for o in ordens if derivar_categoria(o.get("tipo")) is not None]
